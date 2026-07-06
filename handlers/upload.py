from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional
import os
import sys
import time
import cv2
import traceback

router = APIRouter()

@router.post("/api/upload")
async def upload_images(files: list[UploadFile] = File(...)):
    from server import DATASET_DIR, IMG_EXTS, _push, _list_raw_images
    dl_dir = DATASET_DIR / "images_raw"
    dl_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for f in files:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext in IMG_EXTS:
            dest = dl_dir / f.filename
            dest.write_bytes(await f.read())
            _push(f"[UPLOAD] Saved incoming raw blueprint asset: {dest}")
            saved += 1
    _push(f"Successfully staged {saved} incoming image files onto local filesystem.")
    return {
        "saved": saved,
        "images": _list_raw_images(),
        "raw_folder": str(dl_dir),
    }


@router.post("/api/convert_and_evaluate")
async def convert_and_evaluate(file: UploadFile = File(...), metadata_choice: str = Form("gemini"), weights_before: Optional[str] = Form(None), weights_after: Optional[str] = Form(None)):
    from server import (
        DATASET_DIR, _push, _gemini_ready, _convert_gemini_to_yolo_contours,
        _run_local_inference, _compare_preds_to_labels,
        _write_ifc_from_analysis, _write_ifc_from_labelled,
    )
    try:
        from google import genai
        from google.genai import types
    except Exception:
        genai = None
        types = None

    from pathlib import Path
    import automated_bim_v4_connected

    dl_dir = DATASET_DIR / "images_raw"
    dl_dir.mkdir(parents=True, exist_ok=True)
    dest = dl_dir / file.filename
    dest.write_bytes(await file.read())
    basename = dest.stem
    _push(f"[CONVERT] Saved upload: {dest.name}")

    response_payload = {"basename": basename, "ifc": None, "labels": None}
    try:
        img = cv2.imread(str(dest))
        if img is None:
            return JSONResponse({"error": "Invalid image"}, status_code=400)

        labelled = {}
        gemini_ok, gemini_reason = _gemini_ready(metadata_choice)
        _push(f"[CONVERT] mode={metadata_choice}  gemini_ready={gemini_ok}  ({gemini_reason})")

        if metadata_choice == "gemini" and gemini_ok and genai is not None:
            try:
                _push("[CONVERT] Dispatching to Gemini (gemini-2.5-flash)…")
                client = genai.Client()
                main_prompt = automated_bim_v4_connected._build_extraction_prompt(str(dest))
                _, packed_buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                img_bytes = packed_buffer.tobytes()
                image_part = types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg')
                t0 = time.time()
                resp = client.models.generate_content(
                    model='gemini-2.5-flash', contents=[image_part, main_prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json',
                        response_schema=automated_bim_v4_connected.BuildingAnalysis,
                        temperature=0.0,
                    ),
                )
                _push(f"[CONVERT] Gemini responded in {time.time()-t0:.1f}s")
                building_data = resp.parsed
                if building_data is None:
                    raise ValueError("Empty Gemini parsed response")
                _push(f"[CONVERT] walls={len(building_data.walls)} interiors={len(building_data.interiors)}")
                labelled = _convert_gemini_to_yolo_contours(building_data, img.shape[1], img.shape[0])
                response_payload["labels"] = {k: len(v) for k, v in labelled.items() if v}
                ifc_file_target = _write_ifc_from_analysis(building_data, basename, "gemini")
                response_payload["ifc"] = str(ifc_file_target)
                response_payload["ifc_source"] = "gemini"
                if ifc_file_target.exists():
                    _push(f"[CONVERT] 📄 IFC written: {ifc_file_target.name} ({ifc_file_target.stat().st_size // 1024} KB) [source=gemini]")
                else:
                    _push(f"[CONVERT] ⚠️ IFC path set but file not found: {ifc_file_target}")
            except Exception as e:
                _push(f"❌ [CONVERT-GEMINI-FAIL] {type(e).__name__}: {e}")
                _push(traceback.format_exc())
                traceback.print_exc()
        elif metadata_choice == "gemini":
            _push(f"⚠️ [CONVERT] Gemini skipped: {gemini_reason}")
        else:
            _push("[CONVERT] Local mode — heuristic labels + IFC compile…")
            try:
                from logic.detector import FloorPlanDetector
                from logic.auto_label import generate_labels
                detector = FloorPlanDetector(debug_mode=False, output_dir=".", remove_captions=True, detection_mode="heuristic_only")
                label_lines, img2, labelled = generate_labels(str(dest), detector)
                if not label_lines:
                    _push("[CONVERT] No local labels detected — IFC not generated")
                else:
                    ifc_path = _write_ifc_from_labelled(labelled, basename, img.shape[1], img.shape[0], source="local")
                    response_payload["ifc"] = str(ifc_path)
                    response_payload["ifc_source"] = "local"
                    response_payload["labels"] = {k: len(v) for k, v in labelled.items() if isinstance(v, list) and v}
                    _push(f"[CONVERT] 📄 IFC written: {ifc_path.name} ({ifc_path.stat().st_size // 1024} KB) [source=local]")
            except Exception as e:
                _push(f"❌ [CONVERT-LOCAL-FAIL] {type(e).__name__}: {e}")
                _push(traceback.format_exc())

        # ── Load corrected labels from disk (Correct panel edits) ──────────────
        from config.classes import ID_TO_CLASS as _ID2CLS
        import numpy as _np
        corrected_labelled = {}
        lbl_path = DATASET_DIR / "labels" / "train" / (basename + ".txt")
        if lbl_path.exists() and img is not None:
            h, w = img.shape[:2]
            for line in lbl_path.read_text().splitlines():
                parts = line.strip().split()
                if len(parts) < 7:
                    continue
                try:
                    cid = int(parts[0])
                    cls = _ID2CLS.get(cid, f"cls{cid}")
                    coords = list(map(float, parts[1:]))
                    pts = [[int(coords[k]*w), int(coords[k+1]*h)] for k in range(0, len(coords)-1, 2)]
                    if len(pts) >= 3:
                        cnt = _np.array(pts, dtype=_np.int32).reshape(-1, 1, 2)
                        corrected_labelled.setdefault(cls, []).append(cnt)
                except Exception:
                    pass
        # Use corrected labels as ground truth if available, else fall back to freshly detected
        gt_labelled = corrected_labelled if corrected_labelled else labelled
        n_corrected = sum(len(v) for v in corrected_labelled.values())
        _push(f"[CONVERT] Ground truth: {n_corrected} corrected labels" if corrected_labelled else "[CONVERT] Ground truth: heuristic labels (no corrections found)")
        response_payload["gt_labels"] = {k: len(v) for k, v in gt_labelled.items()}
        response_payload["used_corrections"] = bool(corrected_labelled)

        eval_report = {}
        if weights_before:
            preds_before = _run_local_inference(str(dest), weights_before)
            eval_report["before"] = _compare_preds_to_labels(preds_before, gt_labelled)
            _push(f"[CONVERT] Eval before: {eval_report.get('before')}")
        if weights_after:
            preds_after = _run_local_inference(str(dest), weights_after)
            eval_report["after"] = _compare_preds_to_labels(preds_after, gt_labelled)
            _push(f"[CONVERT] Eval after: {eval_report.get('after')}")

        response_payload["eval"] = eval_report
        return response_payload
    except Exception as e:
        _push(f"❌ [CONVERT-FAIL] {type(e).__name__}: {e}")
        _push(traceback.format_exc())
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)
