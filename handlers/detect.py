from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import numpy as np
import cv2

router = APIRouter()

@router.post("/api/detect")
async def detect(file: UploadFile = File(...), model_path: str = Form(""), imgsz: int = Form(640), conf_thresh: float = Form(0.1)):
    from server import _find_best_model, _push, _cv_to_b64, ID_TO_CLASS
    import os
    data = await file.read()
    arr  = np.frombuffer(data, dtype=np.uint8)
    img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse({"error": "Cannot decode image"}, status_code=400)

    if not model_path:
        model_path = _find_best_model()
    if not model_path or not os.path.exists(model_path):
        return JSONResponse({"error": "No model found. Train first."}, status_code=400)

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


@router.post("/api/analyse")
async def analyse_endpoint(file: UploadFile = File(...), basename: str = Form(default="")):
    from server import _cv_to_b64, _push
    data = await file.read()
    arr  = np.frombuffer(data, dtype=np.uint8)
    img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse({"error": "Cannot decode image"}, status_code=400)
    if not basename:
        from pathlib import Path
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
