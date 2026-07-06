#!/usr/bin/env python3
"""
web/server.py 
Consolidated FastAPI Server Backend with Diagnostic Logging and Image Optimization.
AUTO-TRIGGERS local YOLO training immediately following successful Gemini IFC structural processing.
Includes robust selective file execution constraints and timeout protections.
"""

import os
import sys
import re
import glob
import time
import json
import math
import base64
import shutil
import asyncio
import threading
import traceback
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── VERBOSE HTTP TRANSPORT LOGGING INSTRUMENTATION ────────────────────────────
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.DEBUG)
logger = logging.getLogger("bim_trainer")
logger.setLevel(logging.DEBUG)

# ── Environment Path Routing Setup ────────────────────────────────────────────
WEB_DIR      = Path(__file__).resolve().parent                # sam_env/web
PROJECT_ROOT = WEB_DIR.parent                                 # sam_env
LOGIC_DIR    = PROJECT_ROOT / "logic"                         # sam_env/logic

for p in [str(PROJECT_ROOT), str(LOGIC_DIR), str(WEB_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

print(f"[SYSTEM STARTUP] PROJECT_ROOT mapped to: {PROJECT_ROOT}")
print(f"[SYSTEM STARTUP] LOGIC_DIR mapped to: {LOGIC_DIR}")
print(f"[SYSTEM STARTUP] WEB_DIR mapped to: {WEB_DIR}")

# ── System Module Imports ─────────────────────────────────────────────────────
from config.classes import CLASS_IDS, ID_TO_CLASS
from logic.auto_label import generate_labels, draw_labelled_image, contour_to_yolo_seg

# ADD THIS LINE TO FIX THE NAMEERROR:
from logic.image_metadata import save_metadata

# Explicitly import the fully functional original pipeline script from your root directory
try:
    import automated_bim_v4_connected
    print("[SYSTEM STARTUP] Successfully imported 'automated_bim_v4_connected' pipeline engine.")
except ImportError as ie:
    print(f"[SYSTEM STARTUP] ❌ CRITICAL: Could not find 'automated_bim_v4_connected.py' in {PROJECT_ROOT}. Error: {ie}")

# Check Cloud API Engine Dependencies
try:
    from google import genai
    from google.genai import types
    HAS_GEMINI_SDK = True
    print("[SYSTEM STARTUP] Google GenAI SDK found and successfully loaded.")
except ImportError:
    HAS_GEMINI_SDK = False
    print("[SYSTEM STARTUP] ⚠️ WARNING: Google GenAI SDK missing. Cloud endpoints will look for fallback options.")

DATASET_DIR = PROJECT_ROOT / "gdrive_dataset"
IMG_EXTS    = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp", ".svg"}


def _load_gemini_api_key() -> bool:
    """Load GEMINI_API_KEY from environment or project-root gemini.key file."""
    if os.environ.get("GEMINI_API_KEY", "").strip():
        return True
    for key_path in (PROJECT_ROOT / "gemini.key", WEB_DIR / "gemini.key"):
        if not key_path.is_file():
            continue
        text = key_path.read_text(encoding="utf-8", errors="ignore").strip()
        m = re.search(r'GEMINI_API_KEY\s*=\s*["\']?([^"\'#\s]+)', text)
        if m:
            os.environ["GEMINI_API_KEY"] = m.group(1).strip('"\'')
            print(f"[SYSTEM STARTUP] GEMINI_API_KEY loaded from {key_path.name} (…{os.environ['GEMINI_API_KEY'][-4:]})")
            return True
        if text and not text.startswith("#") and "=" not in text:
            os.environ["GEMINI_API_KEY"] = text.strip('"\'')
            print(f"[SYSTEM STARTUP] GEMINI_API_KEY loaded from {key_path.name}")
            return True
    return False


def _gemini_ready(metadata_choice: str) -> Tuple[bool, str]:
    """Return (ready, reason) for Gemini cloud extraction."""
    if metadata_choice != "gemini":
        return False, f"mode is '{metadata_choice}' (not gemini)"
    if not HAS_GEMINI_SDK:
        return False, "Google GenAI SDK not installed"
    _load_gemini_api_key()
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        return False, "GEMINI_API_KEY missing — set env var or create gemini.key in project root"
    return True, "ok"


_GEMINI_KEY_LOADED = _load_gemini_api_key()
if _GEMINI_KEY_LOADED:
    print("[SYSTEM STARTUP] Gemini API key is configured.")
else:
    print("[SYSTEM STARTUP] ⚠️ GEMINI_API_KEY not set — Gemini autolabel will fall back to local heuristics.")


# --- Backwards-compatible helpers from server_old.py (non-duplicating) ---
def _find_best_model() -> str:
    active = PROJECT_ROOT / "best_gdrive.pt"
    if active.exists():
        return str(active)
    return _find_best_by_map()


def _find_best_by_map() -> str:
    search_roots = [
        PROJECT_ROOT / "gdrive_dataset" / "runs",
        PROJECT_ROOT / "runs",
        PROJECT_ROOT / "iterations",
        LOGIC_DIR / "gdrive_dataset" / "runs",
    ]
    best_path, best_map = "", 0.0
    for root in search_roots:
        for pt in glob.glob(str(root / "**" / "best.pt"), recursive=True):
            try:
                from ultralytics import YOLO as _YOLO
                m = _YOLO(pt)
                tr = (m.ckpt or {}).get("train_results", {})
                map50 = max(tr.get("metrics/mAP50(B)", [0]))
                if map50 > best_map:
                    best_map = map50
                    best_path = pt
            except Exception:
                pass
    return best_path


def _list_raw_images() -> list[str]:
    raw = DATASET_DIR / "images_raw"
    if not raw.is_dir():
        return []
    return sorted([f for f in os.listdir(raw) if Path(f).suffix.lower() in IMG_EXTS])


def _list_labelled_images() -> list[str]:
    return sorted(_analysis.keys())


def _load_existing_labels():
    # Load/refresh labelled images from disk into _analysis (from server_old)
    marked_dir = DATASET_DIR / "marked"
    lbl_dir    = DATASET_DIR / "labels" / "train"
    raw_dir    = DATASET_DIR / "images_raw"
    if not marked_dir.is_dir():
        return

    for marked_path in sorted(marked_dir.glob("*_labelled.jpg")):
        basename = marked_path.stem.replace("_labelled", "")
        img = cv2.imread(str(marked_path))
        if img is None:
            continue

        orig = None
        for ext in list(IMG_EXTS):
            for candidate in [raw_dir / (basename + ext), raw_dir / (basename + ext.upper())]:
                if candidate.exists():
                    orig = cv2.imread(str(candidate))
                    break
            if orig is not None:
                break
        h, w = (orig.shape[:2] if orig is not None else img.shape[:2])

        lbl_file = lbl_dir / (basename + ".txt")
        label_lines = []
        if lbl_file.exists():
            label_lines = [l.strip() for l in lbl_file.read_text().splitlines() if l.strip()]

        counts: dict = {}
        labelled: dict = {}
        for line in label_lines:
            parts = line.split()
            if len(parts) < 7:
                continue
            try:
                cid = int(parts[0])
                cls = ID_TO_CLASS.get(cid, f"cls{cid}")
                coords = list(map(float, parts[1:]))
                pts = []
                for k in range(0, len(coords) - 1, 2):
                    px = int(coords[k] * w)
                    py = int(coords[k+1] * h)
                    pts.append([px, py])
                if len(pts) >= 3:
                    cnt = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
                    labelled.setdefault(cls, []).append(cnt)
                    counts[cls] = counts.get(cls, 0) + 1
            except Exception:
                pass

        pre_path  = marked_dir / (basename + "_pre_label.jpg")
        post_path = marked_dir / (basename + "_post_label.jpg")

        entry = {
            "labelled":       labelled,
            "marked_path":    str(marked_path),
            "n_labels":       len(label_lines),
            "label_lines":    label_lines,
            "img_h":          h, "img_w": w,
            "img_b64":        _cv_to_b64(orig) if orig is not None else "",
            "marked_b64":     _cv_to_b64(img),
            "pre_label_b64":  _cv_to_b64(cv2.imread(str(pre_path)))  if pre_path.exists()  else "",
            "post_label_b64": _cv_to_b64(cv2.imread(str(post_path))) if post_path.exists() else "",
            "_counts":        counts,
            "from_disk":      True,
        }
        _analysis[basename] = entry


def _rebuild_labels(basename: str, info: dict):
    img_h, img_w = info["img_h"], info["img_w"]
    lines = []
    for cls_name, contours in info["labelled"].items():
        cid = CLASS_IDS.get(cls_name)
        if cid is None: continue
        for cnt in contours:
            line = contour_to_yolo_seg(cnt, img_w, img_h, cid)
            if line: lines.append(line)
    info["label_lines"] = lines
    info["n_labels"] = len(lines)
    lbl_path = DATASET_DIR / "labels" / "train" / (basename + ".txt")
    if lbl_path.exists():
        lbl_path.write_text("\n".join(lines) + "\n")
    marked = info.get("marked_path")
    if marked:
        img_data = base64.b64decode(info.get("img_b64", ""))
        arr = np.frombuffer(img_data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is not None:
            draw_labelled_image(img, info["labelled"], marked)
            info["marked_b64"] = _cv_to_b64(cv2.imread(marked))


def _correct_label_lines(basename, info, action, cls_name, idx, new_cls):
    lines = info.get("label_lines", [])
    cid_target = CLASS_IDS.get(cls_name)
    if cid_target is None:
        return JSONResponse({"error": f"Unknown class: {cls_name}"}, status_code=400)

    matching = [(i, l) for i, l in enumerate(lines) if l.split()[0] == str(cid_target)]
    if idx < 0 or idx >= len(matching):
        return JSONResponse({"error": f"Index out of range (1-{len(matching)})"}, status_code=400)

    line_idx, line = matching[idx]

    if action == "remove":
        lines.pop(line_idx)
        msg = f"Removed {cls_name} #{idx+1}"
    elif action == "relabel":
        if new_cls not in CLASS_IDS:
            return JSONResponse({"error": f"Unknown class: {new_cls}"}, status_code=400)
        new_cid = CLASS_IDS[new_cls]
        parts = line.split()
        parts[0] = str(new_cid)
        lines[line_idx] = " ".join(parts)
        msg = f"Relabelled {cls_name} #{idx+1} → {new_cls}"
    else:
        return JSONResponse({"error": "action must be remove or relabel"}, status_code=400)

    info["label_lines"] = lines
    info["n_labels"] = len(lines)

    lbl_path = DATASET_DIR / "labels" / "train" / (basename + ".txt")
    lbl_path.write_text("\n".join(lines) + "\n")

    # Rebuild labelled contours from updated lines so marked overlay is redrawn
    img_h, img_w = info.get("img_h", 0), info.get("img_w", 0)
    if img_h and img_w:
        rebuilt: dict = {}
        for ln in lines:
            parts = ln.split()
            if len(parts) < 7:
                continue
            try:
                cid = int(parts[0])
                cls = ID_TO_CLASS.get(cid, f"cls{cid}")
                coords = list(map(float, parts[1:]))
                pts = [[int(coords[k] * img_w), int(coords[k+1] * img_h)] for k in range(0, len(coords) - 1, 2)]
                if len(pts) >= 3:
                    cnt = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
                    rebuilt.setdefault(cls, []).append(cnt)
            except Exception:
                pass
        info["labelled"] = rebuilt
        marked = info.get("marked_path")
        if marked and info.get("img_b64"):
            img_data = base64.b64decode(info["img_b64"])
            arr = np.frombuffer(img_data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                draw_labelled_image(img, rebuilt, marked)
                info["marked_b64"] = _cv_to_b64(cv2.imread(marked))

    counts: dict = {}
    for l in lines:
        try:
            cid = int(l.split()[0])
            cls = ID_TO_CLASS.get(cid, f"cls{cid}")
            counts[cls] = counts.get(cls, 0) + 1
        except Exception:
            pass
    info["_counts"] = counts

    _push(msg, status=msg)
    _corrected_basenames.add(basename)
    return {"ok": True, "msg": msg, "labels": counts,
            "marked_b64": info.get("marked_b64", "")}


def _register_model(path: str, epochs: int, source: str, n_images: int,
                    mAP50: str = "—", mAP50_95: str = "—"):
    import datetime
    if not hasattr(_register_model, "store"):
        _register_model.store = []
    _register_model.store.append({
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "path": path, "name": Path(path).name, "epochs": epochs,
        "mAP50": mAP50, "mAP50_95": mAP50_95, "source": source, "n_images": n_images
    })


_log_queue: list[str] = []          
_progress: dict       = {"pct": 0, "status": "Ready", "metrics": {}}
_analysis: dict       = {}          
_ifc_props: dict      = {}          
_corrected_basenames  = set()       
_training_lock        = threading.Lock()
_training_active      = False

def _push(msg: str, pct: float = None, status: str = None, metrics: dict = None):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [PIPELINE LOG] {msg}")
    _log_queue.append(msg)
    if pct is not None: _progress["pct"] = round(pct, 1)
    if status: _progress["status"] = status
    if metrics: _progress["metrics"].update(metrics)

app = FastAPI(title="Unified Floor Plan Auto-Labeling and Training Core Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if (WEB_DIR / "static").is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

from utils import (
    _cv_to_b64, _convert_gemini_to_yolo_contours, _run_local_inference,
    _compare_preds_to_labels, _contour_to_bbox, _bbox_iou, label_lines_from_labelled,
)


class ConvertRequest(BaseModel):
    metadata_choice: Optional[str] = "gemini"
    weights_before: Optional[str] = None
    weights_after: Optional[str] = None

@app.get("/api/stream")
async def stream():
    async def event_gen():
        # Announce new SSE client connection for debugging/UI visibility
        try:
            _push("[SSE] Client connected to /api/stream")
        except Exception:
            pass
        sent = 0
        while True:
            while sent < len(_log_queue):
                yield f"data: {json.dumps({'log': _log_queue[sent], 'progress': _progress})}\n\n"
                sent += 1
            await asyncio.sleep(0.1)
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_gen(), media_type="text/event-stream", headers=headers)

@app.get("/api/status")
def get_status():
    # Ensure any labelled overlays saved on disk are loaded into in-memory analysis
    try:
        _load_existing_labels()
    except Exception:
        pass
    raw_dir = DATASET_DIR / "images_raw"
    images = sorted([f for f in os.listdir(raw_dir) if Path(f).suffix.lower() in IMG_EXTS]) if raw_dir.is_dir() else []
    return {
        **_progress, "training": _training_active,
        "raw_images": images,
        "labelled_images": sorted(_analysis.keys()),
        "best_model": _find_best_model(),
        "raw_folder": str(DATASET_DIR / "images_raw"),
        "labelled_folder": str(DATASET_DIR / "marked"),
    }


@app.get("/api/classes")
def get_classes():
    try:
        from config.classes import YOLO_CLASS_NAMES, IFC_ONLY_CLASS_NAMES
        return {
            "classes": dict(CLASS_IDS),
            "yolo_classes": YOLO_CLASS_NAMES,
            "ifc_only_classes": IFC_ONLY_CLASS_NAMES,
        }
    except Exception:
        return {"classes": dict(CLASS_IDS), "yolo_classes": [], "ifc_only_classes": []}


@app.get('/api/logs')
def get_logs(n: int = 40):
    """Return the last `n` pipeline logs and progress snapshot."""
    try:
        recent = list(_log_queue[-n:]) if isinstance(_log_queue, list) else []
        return {"logs": recent, "progress": _progress}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# --- Additional endpoints merged from server_old.py ---
@app.post("/api/download")
def download_gdrive(background_tasks: BackgroundTasks):
    background_tasks.add_task(_download_worker)
    return {"ok": True}


def _download_worker():
    dl_dir = DATASET_DIR / "images_raw"
    dl_dir.mkdir(parents=True, exist_ok=True)
    _push("Downloading from Google Drive...", status="Downloading...")
    try:
        import gdown
        url = f"https://drive.google.com/drive/folders/18IThRKRGUHFXnSiMtJlhqHSphDIuphNk"
        gdown.download_folder(url, output=str(dl_dir), quiet=False, use_cookies=False)
        for root_d, _, files in os.walk(dl_dir):
            for f in files:
                if Path(f).suffix.lower() in IMG_EXTS:
                    src, dst = Path(root_d) / f, dl_dir / f
                    if src != dst and not dst.exists():
                        shutil.move(str(src), str(dst))
        count = len([f for f in os.listdir(dl_dir) if Path(f).suffix.lower() in IMG_EXTS])
        _push(f"✅ Downloaded {count} images", pct=100, status=f"Downloaded {count} images")
    except Exception as e:
        _push(f"ERROR: {e}", status="Download failed")


@app.post("/api/detect")
async def detect(file: UploadFile = File(...),
                 model_path: str = Form(""),
                 imgsz: int = Form(640),
                 conf_thresh: float = Form(0.1)):
    if not model_path:
        model_path = _find_best_model()
    if not model_path or not os.path.isfile(model_path):
        return JSONResponse({"error": "No model found. Train first."}, status_code=400)

    data = await file.read()
    arr  = np.frombuffer(data, dtype=np.uint8)
    img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse({"error": "Cannot decode image"}, status_code=400)

    try:
        from ultralytics import YOLO
        model   = YOLO(model_path)
        model_quality = "unknown"
        model_warning = ""
        try:
            ckpt = model.ckpt or {}
            tr   = ckpt.get("train_results", {})
            map50_list = tr.get("metrics/mAP50(B)", [0])
            best_map50 = max(map50_list) if map50_list else 0
            epochs_trained = len(tr.get("epoch", []))
            if best_map50 < 0.01 or epochs_trained == 0:
                model_quality = "undertrained"
                model_warning = (f"⚠️ Model undertrained (mAP50={best_map50:.4f}, {epochs_trained} epochs). Need more images (100+ per class) for reliable detection. Showing heuristic fallback.")
            elif best_map50 < 0.3:
                model_quality = "weak"
                model_warning = f"⚠️ Model weak (mAP50={best_map50:.2f}). Results may be inaccurate."
            else:
                model_quality = "good"
        except Exception:
            pass

        COLORS = {0:(0,0,200),1:(255,0,255),2:(0,165,255),3:(0,200,0),4:(100,100,100)}
        img_h, img_w = img.shape[:2]
        max_dim = max(img_h, img_w)
        font_scale = max(0.4, max_dim / 2500.0)
        thick = max(1, int(max_dim * 0.002))

        results = model(img, imgsz=imgsz, conf=conf_thresh, verbose=False)
        result  = results[0]
        vis     = img.copy()
        counts  = {}
        source  = "yolo"

        if getattr(result, 'masks', None) and len(getattr(result, 'boxes', [])) > 0:
            masks = result.masks.data.cpu().numpy()
            boxes = result.boxes.data.cpu().numpy()
            for i, box in enumerate(boxes):
                cls_id = int(box[5]); conf = float(box[4])
                cls_name = ID_TO_CLASS.get(cls_id, f"cls{cls_id}")
                color    = COLORS.get(cls_id, (128,128,128))
                counts[cls_name] = counts.get(cls_name, 0) + 1
                mask = masks[i]
                if mask.shape != (img_h, img_w):
                    mask = cv2.resize(mask, (img_w, img_h))
                mask_bin = (mask > 0.5).astype(np.uint8)
                overlay  = vis.copy(); overlay[mask_bin > 0] = color
                vis = cv2.addWeighted(overlay, 0.3, vis, 0.7, 0)
                cnts, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(vis, cnts, -1, color, thick)
                x1, y1 = int(box[0]), int(box[1])
                cv2.putText(vis, f"{cls_name} {conf:.2f}", (x1, max(y1-5,10)), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thick, cv2.LINE_AA)

        if not counts:
            source = "heuristic"
            if not model_warning:
                model_warning = "ℹ️ YOLO found 0 detections — showing heuristic fallback."
            try:
                from logic.detector import FloorPlanDetector
                from logic.floor_plan_analyzer import analyse_floor_plan
                detector = FloorPlanDetector(debug_mode=False, output_dir='.', remove_captions=True, detection_mode='heuristic_only')
                heur = detector.detect(img)
                enhanced = analyse_floor_plan(img, heur)
                for key in ['rooms','doors','windows','furniture','stairs','flow_terminals']:
                    if enhanced.get(key):
                        heur[key] = enhanced[key]
                vis = img.copy()
                cls_map = {'rooms':'Room','doors':'Door','windows':'Window','furniture':'Furniture','stairs':'Stair','flow_terminals':'FlowTerminal'}
                for res_key, cls_name in cls_map.items():
                    color = COLORS.get({'Room':3,'Door':2,'Window':1,'Furniture':11,'Stair':8,'FlowTerminal':15}.get(cls_name,3),(128,128,128))
                    for cnt in heur.get(res_key, []):
                        overlay = vis.copy()
                        cv2.drawContours(overlay, [cnt], -1, color, -1)
                        vis = cv2.addWeighted(overlay, 0.25, vis, 0.75, 0)
                        cv2.drawContours(vis, [cnt], -1, color, thick)
                        M = cv2.moments(cnt)
                        if M["m00"] > 0:
                            cx2, cy2 = int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"])
                            cv2.putText(vis, cls_name, (cx2, cy2), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thick, cv2.LINE_AA)
                        n = counts.get(cls_name, 0) + 1
                        counts[cls_name] = n
            except Exception as he:
                model_warning += f" Heuristic also failed: {he}"

        if model_warning:
            banner_h = max(36, int(max_dim * 0.025))
            banner = np.zeros((banner_h, img_w, 3), dtype=np.uint8)
            banner[:] = (30, 80, 180) if source == 'heuristic' else (30, 30, 80)
            cv2.putText(banner, model_warning[:120], (8, banner_h - 8), cv2.FONT_HERSHEY_SIMPLEX, max(0.35, max_dim/4000.0), (255,255,255), 1, cv2.LINE_AA)
            vis = np.vstack([banner, vis])

        orig_b64   = _cv_to_b64(img)
        result_b64 = _cv_to_b64(vis)
        return {"orig_b64": orig_b64, "result_b64": result_b64, "counts": counts, "source": source, "model_quality": model_quality, "warning": model_warning}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/analyse")
async def analyse_endpoint(file: UploadFile = File(...), basename: str = Form(default="")):
    data = await file.read()
    arr  = np.frombuffer(data, dtype=np.uint8)
    img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse({"error": "Cannot decode image"}, status_code=400)
    # Derive basename from filename if not explicitly provided
    if not basename:
        basename = Path(file.filename).stem if file.filename else ""
    try:
        from logic.room_text_mapper import analyse_image, draw_text_mapping_overlay
        result = analyse_image(img, basename=basename)
        overlay = draw_text_mapping_overlay(img, result["mappings"])
        return {
            "orig_b64":    _cv_to_b64(img),
            "overlay_b64": _cv_to_b64(overlay),
            "mappings":    [{"text": m["text"], "class": m["class"], "subtype": m.get("subtype", ""), "cx": m["cx"], "cy": m["cy"], "conf": m.get("conf", 0)} for m in result["mappings"]],
            "summary":     result["summary"],
            "ocr_words":   [{"text": r["text"], "clean": r.get("clean_text", r["text"]), "conf": r.get("conf", 0), "x": r.get("x", 0), "y": r.get("y", 0)} for r in result.get("regions", [])],
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/raw/{filename}")
def get_raw_image(filename: str):
    raw_dir = DATASET_DIR / "images_raw"
    path = raw_dir / filename
    if not path.exists():
        matches = [f for f in raw_dir.iterdir() if f.name.lower() == filename.lower()]
        if not matches:
            return JSONResponse({"error": "not found"}, status_code=404)
        path = matches[0]
    ext = path.suffix.lower()
    if ext == ".svg":
        try:
            import cairosvg
            png_data = cairosvg.svg2png(url=str(path), output_width=1024)
            arr = np.frombuffer(png_data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception:
            return JSONResponse({"error": "SVG load failed"}, status_code=500)
    else:
        img = cv2.imread(str(path))
    if img is None:
        return JSONResponse({"error": "cannot decode"}, status_code=500)
    return {"img_b64": _cv_to_b64(img), "filename": filename, "width": img.shape[1], "height": img.shape[0]}


@app.get("/api/raw_thumb/{filename}")
def get_raw_thumb(filename: str):
    raw_dir = DATASET_DIR / "images_raw"
    path = raw_dir / filename
    if not path.exists():
        matches = [f for f in raw_dir.iterdir() if f.name.lower() == filename.lower()]
        if not matches:
            return JSONResponse({"error": "not found"}, status_code=404)
        path = matches[0]
    ext = path.suffix.lower()
    if ext == ".svg":
        try:
            import cairosvg
            png_data = cairosvg.svg2png(url=str(path), output_width=120)
            arr = np.frombuffer(png_data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception:
            return JSONResponse({"error": "SVG load failed"}, status_code=500)
    else:
        img = cv2.imread(str(path))
    if img is None:
        return JSONResponse({"error": "cannot decode"}, status_code=500)
    h, w = img.shape[:2]
    scale = 80 / max(h, w)
    thumb = cv2.resize(img, (max(1, int(w*scale)), max(1, int(h*scale))))
    from fastapi.responses import Response
    _, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@app.get("/api/thumb/{basename}")
def get_thumb(basename: str):
    info = _analysis.get(basename)
    if not info:
        return JSONResponse({"error": "not found"}, status_code=404)
    marked = info.get("marked_path")
    if not marked or not os.path.exists(marked):
        return JSONResponse({"error": "no marked image"}, status_code=404)
    img = cv2.imread(marked)
    if img is None:
        return JSONResponse({"error": "cannot read"}, status_code=500)
    h, w = img.shape[:2]
    scale = 80 / max(h, w)
    thumb = cv2.resize(img, (max(1, int(w*scale)), max(1, int(h*scale))))
    from fastapi.responses import Response
    _, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@app.post("/api/correct")
def correct_label(body: dict):
    basename  = body.get("basename")
    action    = body.get("action")
    cls_name  = body.get("cls_name")
    idx       = int(body.get("idx", 1)) - 1
    new_cls   = body.get("new_cls", "")

    info = _analysis.get(basename)
    if not info:
        return JSONResponse({"error": "Image not labelled yet"}, status_code=404)

    items = info["labelled"].get(cls_name, []) if info.get("labelled") else []

    if len(items) == 0 and info.get("from_disk"):
        return _correct_label_lines(basename, info, action, cls_name, idx, new_cls)

    if idx < 0 or idx >= len(items):
        return JSONResponse({"error": f"Index out of range (1-{len(items)})"}, status_code=400)

    if action == "remove":
        info["labelled"][cls_name].pop(idx)
        if not info["labelled"][cls_name]:
            del info["labelled"][cls_name]
        msg = f"Removed {cls_name} #{idx+1}"
    elif action == "relabel":
        if new_cls not in CLASS_IDS:
            return JSONResponse({"error": f"Unknown class: {new_cls}"}, status_code=400)
        cnt = info["labelled"][cls_name].pop(idx)
        if not info["labelled"][cls_name]:
            del info["labelled"][cls_name]
        info["labelled"].setdefault(new_cls, []).append(cnt)
        msg = f"Relabelled {cls_name} #{idx+1} → {new_cls}"
    else:
        return JSONResponse({"error": "action must be remove or relabel"}, status_code=400)

    _rebuild_labels(basename, info)
    _push(msg, status=msg)
    labels_out = {k: len(v) for k, v in info["labelled"].items() if v}
    info["_counts"] = labels_out
    _corrected_basenames.add(basename)
    return {"ok": True, "msg": msg, "labels": labels_out, "marked_b64": info.get("marked_b64", "")}


@app.post("/api/save_corrections")
def save_corrections(body: dict):
    basename = body.get("basename")
    info = _analysis.get(basename)
    if not info:
        return JSONResponse({"error": "not found"}, status_code=404)
    lbl_path = DATASET_DIR / "labels" / "train" / (basename + ".txt")
    lines = info.get("label_lines", [])
    lbl_path.write_text("\n".join(lines) + "\n")
    if info.get("labelled") and not info.get("from_disk"):
        marked = info.get("marked_path")
        if marked:
            img_data = base64.b64decode(info.get("img_b64", ""))
            arr = np.frombuffer(img_data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                draw_labelled_image(img, info["labelled"], marked)
                info["marked_b64"] = _cv_to_b64(cv2.imread(marked))
    _corrected_basenames.add(basename)
    return {"ok": True, "saved": str(lbl_path), "n_labels": len(lines)}


@app.post("/api/revert")
def revert_corrections(body: dict):
    basename = body.get("basename")
    lbl_path = DATASET_DIR / "labels" / "train" / (basename + ".txt")
    bak_path = Path(str(lbl_path) + ".bak")
    if bak_path.exists():
        import shutil as _sh
        _sh.copy2(str(bak_path), str(lbl_path))
        lines = [l.strip() for l in bak_path.read_text().splitlines() if l.strip()]
        if basename in _analysis:
            _analysis[basename]["label_lines"] = lines
            _analysis[basename]["n_labels"] = len(lines)
            counts: dict = {}
            for line in lines:
                try:
                    cid = int(line.split()[0])
                    cls = ID_TO_CLASS.get(cid, f"cls{cid}")
                    counts[cls] = counts.get(cls, 0) + 1
                except Exception:
                    pass
            _analysis[basename]["_counts"] = counts
        return {"ok": True, "reverted_to": str(bak_path)}
    if lbl_path.exists():
        lines = [l.strip() for l in lbl_path.read_text().splitlines() if l.strip()]
        if basename in _analysis:
            _analysis[basename]["label_lines"] = lines
            _analysis[basename]["n_labels"] = len(lines)
        return {"ok": True, "note": "No backup found, reloaded current file"}
    return JSONResponse({"error": "No label file found"}, status_code=404)


@app.post("/api/section")
def add_section(body: dict):
    basename = body.get("basename")
    bbox     = body.get("bbox")
    label    = body.get("label", "Room")
    subtype  = body.get("subtype", "")
    info = _analysis.get(basename)
    if not info:
        try:
            _load_existing_labels()
            info = _analysis.get(basename)
        except Exception:
            info = None
    if not info:
        return JSONResponse({"error": "Image not labelled yet — run auto-label first"}, status_code=404)
    if not bbox or len(bbox) < 4:
        return JSONResponse({"error": "bbox required: [x, y, w, h]"}, status_code=400)
    if label not in CLASS_IDS:
        return JSONResponse({"error": f"Unknown class: {label}"}, status_code=400)
    x, y, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
    img_h, img_w = info["img_h"], info["img_w"]
    x = max(0, min(x, img_w - 1)); y = max(0, min(y, img_h - 1))
    w = max(1, min(w, img_w - x)); h = max(1, min(h, img_h - y))
    cnt = np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]], dtype=np.int32).reshape(-1, 1, 2)
    if not info.get("from_disk") or info.get("labelled"):
        info["labelled"].setdefault(label, []).append(cnt)
    else:
        info["labelled"] = {label: [cnt]}
    _rebuild_labels(basename, info)
    labels_out = {k: len(v) for k, v in info["labelled"].items() if v}
    info["_counts"] = labels_out
    import hashlib
    guid = hashlib.md5(f"{basename}_{x}_{y}_{w}_{h}_{label}".encode()).hexdigest()[:12].upper()
    idx = len(info["labelled"].get(label, []))
    if subtype:
        key = f"{label}_{idx}"
        if basename not in _ifc_props:
            _ifc_props[basename] = {}
        from logic.ifc_properties import IFC_SCHEMA
        _ifc_props[basename][key] = {
            "cls_name": label, "idx": idx,
            "ifc_class": IFC_SCHEMA.get(label, {}).get("ifc_class", "IfcBuildingElement"),
            "subtype": subtype, "psets": {}, "material": "", "color": "", "dimensions": {},
            "updated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        }
        props_path = DATASET_DIR / "metadata" / (basename + "_ifc_props.json")
        props_path.parent.mkdir(parents=True, exist_ok=True)
        props_path.write_text(json.dumps(_ifc_props[basename], indent=2))
    marked_b64 = info.get("marked_b64", "")
    return {
        "ok": True, "guid": guid, "label": label, "subtype": subtype,
        "bbox": [x, y, w, h], "labels": labels_out, "n_labels": info["n_labels"],
        "marked_b64": marked_b64,
    }


@app.get("/api/label_details/{basename}")
def get_label_details(basename: str):
    info = _analysis.get(basename)
    if not info:
        return JSONResponse({"error": "not found"}, status_code=404)
    img_h, img_w = info["img_h"], info["img_w"]
    details = {}
    labelled = info.get("labelled", {})
    if labelled:
        for cls_name, contours in labelled.items():
            if not isinstance(contours, list) or not contours:
                continue
            items = []
            for i, cnt in enumerate(contours):
                x, y, w, h = cv2.boundingRect(cnt)
                area = float(cv2.contourArea(cnt))
                eps = 0.02 * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, eps, True)
                poly = approx.reshape(-1, 2).tolist()
                items.append({"idx": i + 1, "bbox": [x, y, w, h], "poly": poly, "area": round(area)})
            details[cls_name] = items
    else:
        for line in info.get("label_lines", []):
            parts = line.split()
            if len(parts) < 7:
                continue
            try:
                cid = int(parts[0])
                cls = ID_TO_CLASS.get(cid, f"cls{cid}")
                coords = list(map(float, parts[1:]))
                pts = [[int(coords[k]*img_w), int(coords[k+1]*img_h)] for k in range(0, len(coords)-1, 2)]
                if len(pts) < 3:
                    continue
                cnt = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
                x, y, w, h = cv2.boundingRect(cnt)
                area = float(cv2.contourArea(cnt))
                details.setdefault(cls, []).append({"idx": len(details.get(cls, [])) + 1, "bbox": [x, y, w, h], "poly": pts, "area": round(area)})
            except Exception:
                pass
    return {"details": details, "img_w": img_w, "img_h": img_h}


@app.post("/api/resize_label")
def resize_label(body: dict):
    basename = body.get("basename")
    cls_name = body.get("cls_name")
    idx      = int(body.get("idx", 1)) - 1
    new_bbox = body.get("bbox")
    info = _analysis.get(basename)
    if not info:
        return JSONResponse({"error": "not found"}, status_code=404)
    if not new_bbox or len(new_bbox) < 4:
        return JSONResponse({"error": "bbox required"}, status_code=400)
    img_h, img_w = info["img_h"], info["img_w"]
    x, y, w, h = [int(v) for v in new_bbox]
    x = max(0, min(x, img_w - 1)); y = max(0, min(y, img_h - 1))
    w = max(4, min(w, img_w - x)); h = max(4, min(h, img_h - y))
    new_cnt = np.array([[x,y],[x+w,y],[x+w,y+h],[x,y+h]], dtype=np.int32).reshape(-1, 1, 2)
    labelled = info.get("labelled", {})
    items = labelled.get(cls_name, [])
    if idx < 0 or idx >= len(items):
        if info.get("from_disk"):
            rebuilt: dict = {}
            for line in info.get("label_lines", []):
                parts = line.split()
                if len(parts) < 7: continue
                try:
                    cid = int(parts[0])
                    cls = ID_TO_CLASS.get(cid, f"cls{cid}")
                    coords = list(map(float, parts[1:]))
                    pts = [[int(coords[k]*img_w), int(coords[k+1]*img_h)] for k in range(0, len(coords)-1, 2)]
                    if len(pts) >= 3:
                        cnt = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
                        rebuilt.setdefault(cls, []).append(cnt)
                except Exception:
                    pass
            info["labelled"] = rebuilt
            labelled = rebuilt
            items = labelled.get(cls_name, [])
    if idx < 0 or idx >= len(items):
        return JSONResponse({"error": f"Index out of range (1-{len(items)})"}, status_code=400)
    items[idx] = new_cnt
    _rebuild_labels(basename, info)
    labels_out = {k: len(v) for k, v in info["labelled"].items() if v}
    info["_counts"] = labels_out
    msg = f"Resized {cls_name} #{idx+1} → [{x},{y},{w},{h}]"
    _push(msg, status=msg)
    return {"ok": True, "msg": msg, "labels": labels_out, "marked_b64": info.get("marked_b64", "")}


_model_versions: list = []

@app.get("/api/model_versions")
def get_model_versions():
    search_roots = [
        PROJECT_ROOT / "gdrive_dataset" / "runs",
        PROJECT_ROOT / "runs",
        PROJECT_ROOT / "iterations",
        LOGIC_DIR / "gdrive_dataset" / "runs",
    ]
    active = _find_best_model()
    scanned = []
    seen = set()
    for root in search_roots:
        for pt in sorted(glob.glob(str(root / "**" / "best.pt"), recursive=True), key=os.path.getmtime, reverse=True):
            if pt in seen: continue
            seen.add(pt)
            ts = Path(pt).stat().st_mtime
            size_mb = round(os.path.getsize(pt) / 1024 / 1024, 1)
            map50, map50_95, epochs, nc, source = "—", "—", "?", "?", "scan"
            try:
                from ultralytics import YOLO as _YOLO
                m = _YOLO(pt)
                ckpt = m.ckpt or {}
                tr   = ckpt.get("train_results", {})
                map50_list = tr.get("metrics/mAP50(B)", [])
                if map50_list:
                    map50    = f"{max(map50_list):.3f}"
                    map50_95 = f"{max(tr.get('metrics/mAP50-95(B)', [0])):.3f}"
                epochs = len(tr.get("epoch", []))
                nc     = m.model.nc if hasattr(m.model, "nc") else "?"
                ta     = ckpt.get("train_args", {})
                source = "corrections" if "finetune" in pt else "full_train"
            except Exception:
                pass
            parts = Path(pt).parts
            name = "/".join(parts[-4:-1]) if len(parts) >= 4 else pt
            scanned.append({"ts": ts, "path": pt, "name": name, "epochs": epochs, "mAP50": map50, "mAP50_95": map50_95, "source": source, "n_images": "?", "size_mb": size_mb, "nc": nc, "is_active": (pt == active)})
    all_versions = list(reversed(_model_versions)) + scanned
    for v in all_versions:
        v["is_active"] = (v["path"] == active)
    return {"versions": all_versions, "best_model": active, "best_exists": bool(active)}


@app.post("/api/set_model")
def set_model(body: dict):
    path = body.get("path")
    if not path or not os.path.exists(path):
        return JSONResponse({"error": "Model file not found"}, status_code=404)
    final = str(PROJECT_ROOT / "best_gdrive.pt")
    shutil.copy2(path, final)
    _push(f"✅ Active model set to: {Path(path).name}", status="Model updated")
    return {"ok": True, "active": final}


@app.get("/api/corrected_files")
def get_corrected_files():
    lbl_dir  = DATASET_DIR / "labels" / "train"
    all_lbls = sorted([f.stem for f in lbl_dir.glob("*.txt")]) if lbl_dir.exists() else []
    return {"corrected": sorted(_corrected_basenames), "all": all_lbls}


@app.post("/api/train_from_corrections")
def train_from_corrections(body: dict, background_tasks: BackgroundTasks):
    global _training_active
    if _training_active:
        return JSONResponse({"error": "Training already running"}, status_code=409)
    epochs      = int(body.get("epochs", 5))
    batch       = int(body.get("batch", 2))
    imgsz       = int(body.get("imgsz", 640))
    mode        = body.get("mode", "incremental")
    base_model  = body.get("base_model", "")
    train_scope = body.get("train_scope", "all")
    train_files = body.get("train_files", [])
    lbl_dir = DATASET_DIR / "labels" / "train"
    if not lbl_dir.exists() or not list(lbl_dir.glob("*.txt")):
        return JSONResponse({"error": "No labels found. Run auto-label first."}, status_code=400)
    if train_files:
        selected = [b for b in train_files if (lbl_dir / (b + ".txt")).exists()]
    elif train_scope == "corrected":
        selected = [b for b in _corrected_basenames if (lbl_dir / (b + ".txt")).exists()]
        if not selected:
            return JSONResponse({"error": "No corrected images found this session. Make corrections first, or choose 'All Images'."}, status_code=400)
    else:
        selected = []
    if mode == "scratch":
        base = str(PROJECT_ROOT / "yolov8n-seg.pt")
        if not os.path.exists(base):
            base = "yolov8n-seg.pt"
    elif base_model and os.path.exists(base_model):
        base = base_model
    else:
        base = _find_best_model()
        if not base:
            return JSONResponse({"error": "No trained model found. Run full training first."}, status_code=400)
    background_tasks.add_task(_finetune_worker, epochs, batch, imgsz, base, selected)
    return {"ok": True, "base_model": base, "mode": mode, "train_scope": train_scope, "n_files": len(selected) if selected else "all"}


@app.post("/api/merge_models")
def merge_models(body: dict, background_tasks: BackgroundTasks):
    model_a = body.get("model_a", "")
    model_b = body.get("model_b", "")
    alpha   = float(body.get("alpha", 0.5))
    name    = body.get("name", "merged")
    for p, label in [(model_a, "model_a"), (model_b, "model_b")]:
        if not p or not os.path.exists(p):
            return JSONResponse({"error": f"{label} not found: {p}"}, status_code=400)
    background_tasks.add_task(_merge_worker, model_a, model_b, alpha, name)
    return {"ok": True}


def _merge_worker(model_a: str, model_b: str, alpha: float, name: str):
    import torch, datetime as _dt
    _push(f"\n{'='*50}")
    _push(f"Merging models (alpha={alpha})")
    _push(f"  A: {Path(model_a).name}")
    _push(f"  B: {Path(model_b).name}")
    try:
        ckpt_a = torch.load(model_a, map_location="cpu")
        ckpt_b = torch.load(model_b, map_location="cpu")
        sd_a = ckpt_a["model"].state_dict() if hasattr(ckpt_a.get("model",""), "state_dict") else ckpt_a["model"]
        sd_b = ckpt_b["model"].state_dict() if hasattr(ckpt_b.get("model",""), "state_dict") else ckpt_b["model"]
        merged_sd = {}
        for key in sd_a:
            if key in sd_b:
                ta = sd_a[key].float()
                tb = sd_b[key].float()
                if ta.shape == tb.shape:
                    merged_sd[key] = (alpha * ta + (1 - alpha) * tb).to(sd_a[key].dtype)
                else:
                    merged_sd[key] = ta
                    _push(f"  ⚠️ Shape mismatch for {key}, keeping model A")
            else:
                merged_sd[key] = sd_a[key]
        merged_ckpt = dict(ckpt_a)
        if hasattr(ckpt_a.get("model",""), "load_state_dict"):
            ckpt_a["model"].load_state_dict(merged_sd)
            merged_ckpt["model"] = ckpt_a["model"]
        else:
            merged_ckpt["model"] = merged_sd
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = DATASET_DIR / "runs" / f"merged_{ts}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(out_dir / "best.pt")
        torch.save(merged_ckpt, out_path)
        final = str(PROJECT_ROOT / "best_gdrive.pt")
        shutil.copy2(out_path, final)
        _register_model(path=out_path, epochs=0, source="merged", n_images="A+B", mAP50="—", mAP50_95="—")
        _push(f"\n✅ Merged model saved: {out_path}", pct=100, status="Merge complete!")
        _push(f"   Set as active model: {final}")
    except Exception as e:
        _push(f"ERROR merging: {e}\n{traceback.format_exc()}", status="Merge failed")


def _finetune_worker(epochs: int, batch: int, imgsz: int, base_model: str, train_files: list = None):
    global _training_active
    _training_active = True
    yaml_path = DATASET_DIR / "dataset.yaml"
    if not yaml_path.exists():
        _push("ERROR: No dataset.yaml", status="Error")
        _training_active = False; return
    try:
        from ultralytics import YOLO
        import torch
        _push(f"\n{'='*50}")
        _push(f"Fine-tuning FROM: {base_model}")
        _push(f"Epochs: {epochs}  Batch: {batch}  ImgSz: {imgsz}")
        model = YOLO(base_model)
        size_mb = os.path.getsize(base_model) / 1024 / 1024
        _push(f"  Loaded: {Path(base_model).name}  ({size_mb:.1f}MB)")
        lbl_dir      = DATASET_DIR / "labels" / "train"
        img_dir      = DATASET_DIR / "images" / "train"
        all_lbl      = sorted(lbl_dir.glob("*.txt"))
        if train_files:
            sel_set   = set(train_files)
            use_files = [lf for lf in all_lbl if lf.stem in sel_set]
            scope_tag = f"corrected ({len(use_files)} image(s))"
        else:
            use_files = all_lbl
            scope_tag = f"all ({len(use_files)} image(s))"
        n_images = len(use_files)
        _push(f"  Training scope: {scope_tag}")
        for lf in use_files:
            n = len([l for l in lf.read_text().splitlines() if l.strip()])
            _push(f"    [{lf.stem}]  labels: {n}")
        if n_images == 0:
            _push("ERROR: No matching label files found", status="Error")
            _training_active = False; return
        import tempfile, datetime as _dt
        if train_files:
            tmp_dir  = Path(tempfile.mkdtemp(prefix="ft_subset_"))
            tmp_imgs = tmp_dir / "images" / "train"
            tmp_lbls = tmp_dir / "labels" / "train"
            tmp_imgs.mkdir(parents=True); tmp_lbls.mkdir(parents=True)
            for lf in use_files:
                shutil.copy2(str(lf), str(tmp_lbls / lf.name))
                for ext in [".jpg", ".jpeg", ".png", ".bmp"]:
                    src_img = img_dir / (lf.stem + ext)
                    if src_img.exists():
                        shutil.copy2(str(src_img), str(tmp_imgs / src_img.name))
                        break
            tmp_yaml = tmp_dir / "dataset.yaml"
            orig_yaml = yaml_path.read_text()
            new_yaml = "\n".join((f"path: {tmp_dir}" if l.startswith("path:") else l) for l in orig_yaml.splitlines())
            tmp_yaml.write_text(new_yaml)
            active_yaml = str(tmp_yaml)
            _push(f"  Temp dataset created at: {tmp_dir}")
        else:
            active_yaml = str(yaml_path)
            tmp_dir = None
        metrics_final = {}
        def on_epoch_end(trainer):
            ep = trainer.epoch + 1
            _push(f"  Epoch {ep}/{epochs}", pct=ep/epochs*100, status=f"Fine-tune epoch {ep}/{epochs}", metrics={"Epoch": f"{ep}/{epochs}"})
            loss = trainer.label_loss_items(trainer.tloss)
            if loss:
                m = {}
                if "train/box_loss" in loss: m["Box Loss"] = f"{loss['train/box_loss']:.4f}"
                if "train/seg_loss" in loss: m["Seg Loss"] = f"{loss['train/seg_loss']:.4f}"
                if m: _progress["metrics"].update(m)
        def on_fit_end(trainer):
            m = trainer.metrics
            rd = m.results_dict if hasattr(m, "results_dict") else (m if isinstance(m, dict) else {})
            if "metrics/mAP50(B)" in rd:
                metrics_final["mAP50"]    = f"{rd['metrics/mAP50(B)']:.4f}"
                metrics_final["mAP50_95"] = f"{rd.get('metrics/mAP50-95(B)', 0):.4f}"
                _progress["metrics"].update({"mAP50": metrics_final["mAP50"]})
        model.add_callback("on_train_epoch_end", on_epoch_end)
        model.add_callback("on_fit_epoch_end", on_fit_end)
        device = "cuda" if __import__('torch').cuda.is_available() else ("mps" if hasattr(__import__('torch').backends, 'mps') and __import__('torch').backends.mps.is_available() else "cpu")
        _push(f"  Device: {device}")
        run_name    = f"finetune_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_dir = str(DATASET_DIR / "runs")
        model.train(data=active_yaml, epochs=epochs, batch=batch, imgsz=imgsz, device=device, project=project_dir, name=run_name, workers=0, amp=True, verbose=False, optimizer="SGD", lr0=0.0005, lrf=0.01, momentum=0.937, weight_decay=0.0005, warmup_epochs=1, freeze=10, close_mosaic=0)
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(str(tmp_dir), ignore_errors=True)
        cands = glob.glob(os.path.join(project_dir, run_name, "weights", "best.pt"))
        if not cands:
            cands = glob.glob(os.path.join(project_dir, "**", "best.pt"), recursive=True)
        if cands:
            best_new = max(cands, key=os.path.getmtime)
            final = str(PROJECT_ROOT / "best_gdrive.pt")
            shutil.copy2(best_new, final)
            _register_model(path=best_new, epochs=epochs, source="corrections", n_images=n_images, mAP50=metrics_final.get("mAP50", "—"), mAP50_95=metrics_final.get("mAP50_95", "—"))
            _push(f"\n✅ Fine-tune complete! Model updated: {final}", pct=100, status="Fine-tune complete!")
            _push(f"   mAP50: {metrics_final.get('mAP50','—')}  mAP50-95: {metrics_final.get('mAP50_95','—')}")
        else:
            _push("⚠️ No best.pt produced", status="Done (no model)")
    except Exception as e:
        _push(f"ERROR: {e}\n{traceback.format_exc()}", status="Fine-tune failed")
    finally:
        _training_active = False


# --- Metadata and IFC endpoints ---
from logic.image_metadata import (
    get_metadata_path, metadata_exists, load_metadata,
    save_metadata, build_metadata_from_ocr, list_all_metadata, build_metadata_from_gemini
)

@app.get("/api/metadata/check")
def check_metadata(basename: str):
    img_path = DATASET_DIR / "images_raw" / basename
    if not img_path.exists():
        for ext in IMG_EXTS:
            candidate = DATASET_DIR / "images_raw" / (basename + ext)
            if candidate.exists():
                img_path = candidate
                break
    exists = metadata_exists(str(img_path), DATASET_DIR)
    if exists:
        data = load_metadata(str(img_path), DATASET_DIR)
        return {"exists": True, "source": data.get("source", "unknown"), "saved_at": data.get("_saved_at", ""), "n_labels": data.get("n_labels", 0), "n_rooms": len(data.get("rooms", [])), "label_counts": data.get("label_counts", {}), "ifc_classes": data.get("ifc_classes", {}), "notes": data.get("notes", "")}
    return {"exists": False}


@app.get("/api/metadata/{basename}")
def get_metadata(basename: str):
    img_path = DATASET_DIR / "images_raw" / basename
    if not img_path.exists():
        for ext in IMG_EXTS:
            c = DATASET_DIR / "images_raw" / (basename + ext)
            if c.exists(): img_path = c; break
    data = load_metadata(str(img_path), DATASET_DIR)
    if not data:
        return JSONResponse({"error": "No metadata found"}, status_code=404)
    return data


@app.get("/api/metadata")
def list_metadata():
    return {"metadata": list_all_metadata(DATASET_DIR)}


@app.post("/api/metadata/save_gemini")
async def save_gemini_metadata(body: dict):
    basename = body.get("basename")
    gemini   = body.get("gemini", {})
    if not basename:
        return JSONResponse({"error": "basename required"}, status_code=400)
    img_path = DATASET_DIR / "images_raw" / basename
    if not img_path.exists():
        for ext in IMG_EXTS:
            c = DATASET_DIR / "images_raw" / (basename + ext)
            if c.exists(): img_path = c; break
    data = build_metadata_from_gemini(str(img_path), gemini)
    path = save_metadata(str(img_path), DATASET_DIR, data)
    return {"ok": True, "path": str(path)}


@app.post("/api/metadata/delete")
def delete_metadata(body: dict):
    basename = body.get("basename")
    img_path = DATASET_DIR / "images_raw" / basename
    meta_path = get_metadata_path(str(img_path), DATASET_DIR)
    if meta_path.exists():
        meta_path.unlink()
        return {"ok": True, "deleted": str(meta_path)}
    return {"ok": False, "error": "No metadata file found"}


from logic.ifc_properties import IFC_SCHEMA, MATERIALS, get_default_pset, validate_pset

@app.get("/api/ifc/schema")
def get_ifc_schema():
    return {"schema": IFC_SCHEMA, "materials": MATERIALS}


@app.get("/api/ifc/schema/{cls_name}")
def get_ifc_schema_for_class(cls_name: str):
    from logic.ifc_properties import get_schema
    schema = get_schema(cls_name)
    if not schema:
        return JSONResponse({"error": f"No schema for {cls_name}"}, status_code=404)
    return {"cls_name": cls_name, "schema": schema, "defaults": get_default_pset(cls_name)}


@app.get("/api/ifc/props/{basename}")
def get_ifc_props(basename: str):
    props = _ifc_props.get(basename, {})
    props_path = DATASET_DIR / "metadata" / (basename + "_ifc_props.json")
    if not props and props_path.exists():
        try:
            props = json.loads(props_path.read_text())
            _ifc_props[basename] = props
        except Exception:
            pass
    return {"basename": basename, "props": props}


@app.post("/api/ifc/props/{basename}")
def save_ifc_props(basename: str, body: dict):
    cls_name  = body.get("cls_name")
    idx       = int(body.get("idx", 1))
    subtype   = body.get("subtype", "")
    pset_data = body.get("psets", {})
    material  = body.get("material", "")
    color     = body.get("color", "")
    dims      = body.get("dimensions", {})
    if not cls_name:
        return JSONResponse({"error": "cls_name required"}, status_code=400)
    cleaned = validate_pset(cls_name, pset_data)
    key = f"{cls_name}_{idx}"
    if basename not in _ifc_props:
        _ifc_props[basename] = {}
    _ifc_props[basename][key] = {
        "cls_name":   cls_name,
        "idx":        idx,
        "ifc_class":  IFC_SCHEMA.get(cls_name, {}).get("ifc_class", "IfcBuildingElement"),
        "subtype":    subtype,
        "psets":      cleaned,
        "material":   material,
        "color":      color,
        "dimensions": dims,
        "updated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }
    props_path = DATASET_DIR / "metadata" / (basename + "_ifc_props.json")
    props_path.parent.mkdir(parents=True, exist_ok=True)
    props_path.write_text(json.dumps(_ifc_props[basename], indent=2))
    return {"ok": True, "key": key, "ifc_class": _ifc_props[basename][key]["ifc_class"]}


@app.delete("/api/ifc/props/{basename}/{key}")
def delete_ifc_prop(basename: str, key: str):
    if basename in _ifc_props and key in _ifc_props[basename]:
        del _ifc_props[basename][key]
        props_path = DATASET_DIR / "metadata" / (basename + "_ifc_props.json")
        if props_path.exists():
            props_path.write_text(json.dumps(_ifc_props.get(basename, {}), indent=2))
        return {"ok": True}
    return JSONResponse({"error": "Not found"}, status_code=404)


@app.get("/api/ifc/export/{basename}")
def export_ifc_props(basename: str):
    props = _ifc_props.get(basename, {})
    if not props:
        props_path = DATASET_DIR / "metadata" / (basename + "_ifc_props.json")
        if props_path.exists():
            props = json.loads(props_path.read_text())
    export = {"basename": basename, "elements": [], "summary": {}}
    for key, data in props.items():
        export["elements"].append(data)
        cls = data.get("cls_name", "Unknown")
        export["summary"][cls] = export["summary"].get(cls, 0) + 1
    return export

@app.get("/api/image/{filename_or_basename}")
def get_image(filename_or_basename: str):
    basename = Path(filename_or_basename).stem
    filename = filename_or_basename if "." in filename_or_basename else f"{basename}.jpg"

    info = _analysis.get(basename)
    if not info:
        try:
            _load_existing_labels()
            info = _analysis.get(basename)
        except Exception:
            info = None

    if info:
        counts: dict = {}
        if info.get("labelled"):
            counts = {k: len(v) for k, v in info["labelled"].items() if v}
        else:
            for line in info.get("label_lines", []):
                try:
                    cid = int(line.split()[0])
                    cls = ID_TO_CLASS.get(cid, f"cls{cid}")
                    counts[cls] = counts.get(cls, 0) + 1
                except Exception:
                    pass
        info["_counts"] = counts
        ta = info.get("text_analysis") or {}
        if isinstance(ta, dict) and ta.get("summary") and isinstance(ta["summary"], dict):
            ta = {**ta, "summary": "\n".join(f"{k}: {v}" for k, v in ta["summary"].items())}
        return {
            "marked_b64": info.get("marked_b64", ""),
            "pre_label_b64": info.get("pre_label_b64", ""),
            "post_label_b64": info.get("post_label_b64", ""),
            "text_analysis": ta,
            "labels": counts,
            "n_labels": info.get("n_labels", sum(counts.values())),
        }

    marked_file = DATASET_DIR / "marked" / f"{basename}_labelled.jpg"
    if marked_file.exists():
        img_b64 = _cv_to_b64(cv2.imread(str(marked_file)))
        return {"marked_b64": img_b64, "n_labels": 0, "labels": {}}

    raw_dir = DATASET_DIR / "images_raw"
    if raw_dir.is_dir():
        direct_target = raw_dir / filename
        if direct_target.exists():
            raw_img = cv2.imread(str(direct_target))
            if raw_img is not None:
                return {"marked_b64": _cv_to_b64(raw_img), "n_labels": 0, "labels": {}}
        for f in os.listdir(raw_dir):
            if Path(f).stem == basename and Path(f).suffix.lower() in IMG_EXTS:
                candidate = raw_dir / f
                raw_img = cv2.imread(str(candidate))
                if raw_img is not None:
                    return {"marked_b64": _cv_to_b64(raw_img), "n_labels": 0, "labels": {}}

    return JSONResponse({"error": "No matching floor plan found on server storage disk."}, status_code=404)

from handlers.upload import router as upload_router
from handlers.detect import router as detect_router
from handlers.images import router as images_router
from handlers.labels import router as labels_router
from handlers.models import router as models_router

app.include_router(upload_router)
app.include_router(detect_router)
app.include_router(images_router)
app.include_router(labels_router)
app.include_router(models_router)

def _ifc_props_module():
    prop_paths = automated_bim_v4_connected.find_ifc_properties_files(str(PROJECT_ROOT))
    if prop_paths:
        return automated_bim_v4_connected.load_ifc_properties_module(prop_paths[0])
    return sys.modules.get("logic.ifc_properties")


def _write_ifc_from_analysis(building_data, basename: str, source: str) -> Path:
    """Write IFC as metadata/{basename}_{source}.ifc (e.g. floor_plan_gemini.ifc)."""
    from logic.local_bim_builder import ifc_output_path
    out = ifc_output_path(DATASET_DIR, basename, source)
    out.parent.mkdir(parents=True, exist_ok=True)
    building_data.building_name = f"{basename} ({source})"
    automated_bim_v4_connected.build_detailed_ifc(
        building_data, str(out), props_module=_ifc_props_module(), debug=True,
    )
    return out


def _write_ifc_from_labelled(labelled: dict, basename: str, img_w: int, img_h: int, source: str = "local") -> Path:
    from logic.local_bim_builder import build_ifc_from_labelled
    # Load per-element IFC props saved via the IFC Props panel / Correct panel
    saved_props = _ifc_props.get(basename, {})
    if not saved_props:
        props_path = DATASET_DIR / "metadata" / (basename + "_ifc_props.json")
        if props_path.exists():
            try:
                saved_props = json.loads(props_path.read_text())
            except Exception:
                saved_props = {}
    return build_ifc_from_labelled(
        labelled, img_w, img_h, basename, DATASET_DIR,
        source=source, props_module=_ifc_props_module(),
        saved_element_props=saved_props, debug=True,
    )


def _autolabel_worker(selected_files: list, metadata_choice: str, background_tasks: BackgroundTasks):
    raw_dir, img_out, lbl_out, mark_out = DATASET_DIR / "images_raw", DATASET_DIR / "images" / "train", DATASET_DIR / "labels" / "train", DATASET_DIR / "marked"
    for d in [img_out, lbl_out, mark_out]: d.mkdir(parents=True, exist_ok=True)
    
    all_files = sorted([raw_dir / f for f in os.listdir(raw_dir) if Path(f).suffix.lower() in IMG_EXTS])
    
    if selected_files and len(selected_files) > 0:
        target_set = set(selected_files)
        files = [f for f in all_files if f.name in target_set]
        _push(f"[PIPELINE STAGING] Selective processing filter active. Handling {len(files)} targeted candidates.")
    else:
        files = all_files
        _push(f"[PIPELINE STAGING] No explicit constraints passed. Processing all {len(files)} total files.")
    
    if not files:
        return _push("⚠️ Auto-labeling skipped: No valid processing candidates found in input storage folder.")

    gemini_ok, gemini_reason = _gemini_ready(metadata_choice)
    _push(f"[AUTO-LABEL] Engine={metadata_choice}  gemini_ready={gemini_ok}  ({gemini_reason})")

    new_labels_produced = False

    for i, img_path in enumerate(files):
        basename = img_path.stem
        _push(f"[AUTO-LABEL] ({i+1}/{len(files)}) Processing '{img_path.name}' ({img_path.stat().st_size // 1024} KB)", pct=((i+1)/len(files))*100, status="Extracting...")
        
        try:
            img = cv2.imread(str(img_path))
            if img is None:
                _push(f"❌ Failed to decode image: '{img_path.name}'"); continue
                
            orig_h, orig_w = img.shape[:2]
            _push(f"[AUTO-LABEL] Image size: {orig_w}x{orig_h}px")
            
            labelled = {}
            label_lines = []
            label_source = "none"

            if metadata_choice == "gemini":
                if not gemini_ok:
                    _push(f"⚠️ [GEMINI-SKIP] {gemini_reason} — will use local heuristics for '{basename}'")
                else:
                    try:
                        _push(f"[GEMINI] Calling gemini-2.5-flash for '{basename}'…")
                        client = genai.Client()
                        _push("[GEMINI] Optimizing image for API upload…")
                        MAX_TRANSMIT_SIDE = 2500
                        if max(orig_h, orig_w) > MAX_TRANSMIT_SIDE:
                            scale_ratio = MAX_TRANSMIT_SIDE / max(orig_h, orig_w)
                            payload_img = cv2.resize(img, (int(orig_w * scale_ratio), int(orig_h * scale_ratio)), interpolation=cv2.INTER_AREA)
                            _push(f"[GEMINI] Downscaled to {payload_img.shape[1]}x{payload_img.shape[0]} for upload")
                        else:
                            payload_img = img
                        _, packed_buffer = cv2.imencode('.jpg', payload_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        img_bytes = packed_buffer.tobytes()
                        _push(f"[GEMINI] Payload size: {len(img_bytes) // 1024} KB")
                        image_part = types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg')
                        main_prompt = automated_bim_v4_connected._build_extraction_prompt(str(img_path))
                        t0 = time.time()
                        response = client.models.generate_content(model='gemini-2.5-flash', contents=[image_part, main_prompt], config=types.GenerateContentConfig(response_mime_type='application/json', response_schema=automated_bim_v4_connected.BuildingAnalysis, temperature=0.0, max_output_tokens=65535))
                        _push(f"[GEMINI] Primary response in {time.time()-t0:.1f}s")
                        building_data = response.parsed
                        if building_data is None:
                            raise ValueError("Gemini returned empty parsed response")
                        suspicious, summary, expected = automated_bim_v4_connected._is_extraction_suspicious(building_data, str(img_path))
                        _push(f"[GEMINI] walls={len(building_data.walls)} interiors={len(building_data.interiors)} rooms={len(building_data.rooms)} suspicious={suspicious}")
                        if suspicious:
                            _push(f"[GEMINI] Partial extraction ({summary}) — retrying with gemini-3-flash-preview…")
                            retry_prompt = automated_bim_v4_connected._build_extraction_prompt(str(img_path), summary, expected)
                            retry_resp = client.models.generate_content(model='gemini-3-flash-preview', contents=[image_part, retry_prompt], config=types.GenerateContentConfig(response_mime_type='application/json', response_schema=automated_bim_v4_connected.BuildingAnalysis, temperature=0.0, max_output_tokens=65535))
                            retry_data = retry_resp.parsed
                            if retry_data and automated_bim_v4_connected._extraction_score(retry_data) >= automated_bim_v4_connected._extraction_score(building_data):
                                building_data = retry_data
                                _push(f"[GEMINI] Retry accepted: walls={len(building_data.walls)} interiors={len(building_data.interiors)}")
                            else:
                                _push("[GEMINI] Retry did not improve — keeping primary result")
                        labelled = _convert_gemini_to_yolo_contours(building_data, orig_w, orig_h)
                        label_lines = label_lines_from_labelled(labelled, orig_w, orig_h)
                        label_counts = {k: len(v) for k, v in labelled.items() if v}
                        _push(f"[GEMINI] YOLO contours: {label_counts}  ({len(label_lines)} label lines)")
                        meta_payload = building_data.model_dump()
                        meta_payload["ifc_source"] = "gemini"
                        save_metadata(str(img_path), DATASET_DIR, meta_payload)
                        _push(f"[GEMINI] Metadata saved: metadata/{basename}.json")
                        ifc_file_target = _write_ifc_from_analysis(building_data, basename, "gemini")
                        _push(f"[GEMINI] Building IFC → {ifc_file_target.name}")
                        if ifc_file_target.exists():
                            _push(f"📄 Generated IFC: {ifc_file_target} ({ifc_file_target.stat().st_size // 1024} KB) [source=gemini]")
                        else:
                            _push(f"⚠️ [GEMINI] IFC build finished but file missing: {ifc_file_target}")
                        label_source = "gemini"
                    except Exception as e:
                        _push(f"❌ [GEMINI-FAIL] {type(e).__name__}: {e}")
                        _push(traceback.format_exc())
                        traceback.print_exc()

            # If no labels from Gemini, run local detector + analyzer
            if not label_lines and not labelled:
                _push(f"[LOCAL] Running heuristic detector for '{basename}'…")
                try:
                    from logic.detector import FloorPlanDetector
                    from logic.floor_plan_analyzer import analyse_floor_plan
                    from logic.room_text_mapper import analyse_image
                    detector = FloorPlanDetector(debug_mode=False, output_dir='.', remove_captions=True, detection_mode='heuristic_only')
                    label_lines, img2, labelled = generate_labels(str(img_path), detector)
                    _push(f"[LOCAL] Heuristic pass: {len(label_lines)} raw label line(s)")
                    if not label_lines:
                        _push(f"  SKIP: {basename} (no labels from local detector)")
                        continue
                    enhanced = analyse_floor_plan(img2, labelled)
                    for key in ["rooms", "stairs", "flow_terminals", "furniture"]:
                        if enhanced.get(key) and len(enhanced[key]) > len(labelled.get(key, [])):
                            labelled[key] = enhanced[key]
                            _push(f"  [LOCAL] Enhanced {key}: {len(enhanced[key])}")
                    label_lines = label_lines_from_labelled(labelled, orig_w, orig_h)
                    label_source = "local"
                    _push(f"[LOCAL] Final: {len(label_lines)} label line(s)  classes={ {k: len(v) for k, v in labelled.items() if v} }")
                    try:
                        ifc_path = _write_ifc_from_labelled(labelled, basename, orig_w, orig_h, source="local")
                        _push(f"📄 Generated IFC: {ifc_path} ({ifc_path.stat().st_size // 1024} KB) [source=local]")
                        from logic.local_bim_builder import labelled_to_building_analysis
                        local_meta = labelled_to_building_analysis(labelled, orig_w, orig_h, basename, "local").model_dump()
                        local_meta["ifc_source"] = "local"
                        local_meta["ifc_path"] = str(ifc_path)
                        save_metadata(str(img_path), DATASET_DIR, local_meta)
                        _push(f"[LOCAL] Metadata saved with ifc_source=local")
                    except Exception as ifc_err:
                        _push(f"⚠️ [LOCAL-IFC] Failed to compile IFC: {ifc_err}")
                        _push(traceback.format_exc())
                except Exception as e:
                    _push(f"❌ [LOCAL-FAIL] {type(e).__name__}: {e}")
                    _push(traceback.format_exc())
                    traceback.print_exc()
                    continue
            elif label_lines and label_source == "none":
                label_source = "gemini"

            if not label_lines:
                _push(f"⚠️ SKIP '{basename}': no labels after processing (source attempted: {metadata_choice})")
                continue

            _push(f"[AUTO-LABEL] Persisting {len(label_lines)} labels for '{basename}' (source={label_source})")
            shutil.copy2(str(img_path), str(img_out / img_path.name))
            (lbl_out / f"{basename}.txt").write_text("\n".join(label_lines) + "\n")
            draw_labelled_image(img if 'img' in locals() and img is not None else img2, labelled, str(mark_out / f"{basename}_labelled.jpg"))

            # run OCR/text analysis for pre/post views
            try:
                text_analysis = analyse_image(img if 'img' in locals() and img is not None else img2, labelled.get('Room', []))
            except Exception:
                text_analysis = {"mappings": [], "assigned": [], "summary": {}, "pre_label_img": (img if 'img' in locals() and img is not None else img2), "post_label_img": (img if 'img' in locals() and img is not None else img2)}

            pre_path  = str(mark_out / (basename + "_pre_label.jpg"))
            post_path = str(mark_out / (basename + "_post_label.jpg"))
            try:
                cv2.imwrite(pre_path,  text_analysis.get('pre_label_img'))
                cv2.imwrite(post_path, text_analysis.get('post_label_img'))
            except Exception:
                pass

            _analysis[basename] = {
                "labelled": labelled,
                "marked_path": str(mark_out / f"{basename}_labelled.jpg"),
                "n_labels": len(label_lines),
                "label_lines": label_lines,
                "img_h": (img.shape[0] if 'img' in locals() and img is not None else img2.shape[0]),
                "img_w": (img.shape[1] if 'img' in locals() and img is not None else img2.shape[1]),
                "text_analysis": {
                    "mappings": text_analysis.get('mappings', []),
                    "summary": text_analysis.get('summary', {}),
                    "was_corrected": text_analysis.get('_analyzer_used', False)
                },
                "pre_label_path": pre_path,
                "post_label_path": post_path,
            }
            try:
                _analysis[basename]["img_b64"] = _cv_to_b64(cv2.imread(str(img_out / img_path.name)))
                _analysis[basename]["marked_b64"] = _cv_to_b64(cv2.imread(str(mark_out / f"{basename}_labelled.jpg")))
                _analysis[basename]["pre_label_b64"] = _cv_to_b64(cv2.imread(pre_path))
                _analysis[basename]["post_label_b64"] = _cv_to_b64(cv2.imread(post_path))
            except Exception:
                pass

            new_labels_produced = True
        except Exception as e:
            _push(f"❌ Critical exception hit inside worker thread pool: {e}")
            traceback.print_exc()

    _push(f"✅ Auto-label complete. Processed {len(files)} file(s).", pct=100, status="Ready")

    if new_labels_produced and background_tasks is not None:
        _push("🚀 AUTO-TRAIN CHAIN INTERCEPT: Passing freshly compiled label documents into local neural training loop background worker...")
        background_tasks.add_task(_train_worker, 5, 4, 640)

@app.post("/api/train")
def train(body: dict, background_tasks: BackgroundTasks):
    global _training_active
    if _training_active: return JSONResponse({"error": "System neural training execution loop locked."}, status_code=409)
    background_tasks.add_task(_train_worker, int(body.get("epochs", 5)), int(body.get("batch", 4)), int(body.get("imgsz", 640)))
    return {"ok": True}

def _train_worker(epochs: int, batch: int, imgsz: int):
    global _training_active
    if not _training_lock.acquire(blocking=False):
        _push("⚠️ Concurrency Blocker: Another neural training workflow is already active. Request skipped.")
        return
    _training_active = True
    _push("Staging network arrays and building training execution manifest maps...", status="Training...")
    try:
        from ultralytics import YOLO
        import torch
        
        yaml_path = DATASET_DIR / "dataset.yaml"
        if not yaml_path.exists():
            yaml_content = f"path: {str(DATASET_DIR)}\ntrain: images/train\nval: images/train\nnc: {len(CLASS_IDS)}\nnames:\n" + "\n".join([f"  {v}: {k}" for k, v in CLASS_IDS.items()])
            yaml_path.write_text(yaml_content)
            
        model_base = str(PROJECT_ROOT / "yolov8n-seg.pt")
        model = YOLO(model_base if os.path.exists(model_base) else "yolov8n-seg.pt")
        device = "cuda" if torch.cuda.is_available() else ("mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else "cpu")
        
        _push(f"Commencing deep neural fitting run. Hardware Acceleration Node: [{device.upper()}]")
        model.train(data=str(yaml_path), epochs=epochs, batch=batch, imgsz=imgsz, device=device, project=str(DATASET_DIR / "runs"), name="train", workers=0, verbose=False)
        
        cands = glob.glob(os.path.join(str(DATASET_DIR / "runs"), "**", "best.pt"), recursive=True)
        if cands:
            output_weights_target = str(PROJECT_ROOT / "best_gdrive.pt")
            shutil.copy2(max(cands, key=os.path.getmtime), output_weights_target)
            _push(f"✅ Neural training run optimized. Updated inference weights target node: '{output_weights_target}'", pct=100, status="Ready")
    except Exception as e:
        _push(f"❌ Operational tracking failure during deep learning optimization loop: {e}")
    finally:
        _training_active = False
        _training_lock.release()

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = WEB_DIR / "index.html"
    if html_path.exists(): 
        return html_path.read_text()
    return "<h3>Integrated Dashboard UI Platform Interface Module Active.</h3>"

if __name__ == "__main__":
    import uvicorn
    print("[INIT] Launching Uvicorn production server process loop at port 8002..")
    uvicorn.run("server:app", host="0.0.0.0", port=8002, reload=False)
