from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
import os
import cv2
import base64
import numpy as np

router = APIRouter()

@router.post("/api/correct")
def correct_label(body: dict):
    from server import _analysis, CLASS_IDS, ID_TO_CLASS, _push, _correct_label_lines, _corrected_basenames, draw_labelled_image, _cv_to_b64, DATASET_DIR
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
        msg = f"Removed {cls_name} #{idx+1}"
    elif action == "relabel":
        if new_cls not in CLASS_IDS:
            return JSONResponse({"error": f"Unknown class: {new_cls}"}, status_code=400)
        cnt = info["labelled"][cls_name].pop(idx)
        info["labelled"].setdefault(new_cls, []).append(cnt)
        msg = f"Relabelled {cls_name} #{idx+1} → {new_cls}"
    else:
        return JSONResponse({"error": "action must be remove or relabel"}, status_code=400)

    # Rebuild labels
    from server import _rebuild_labels
    _rebuild_labels(basename, info)
    _push(msg, status=msg)
    labels_out = {k: len(v) for k, v in info["labelled"].items() if v}
    info["_counts"] = labels_out
    _corrected_basenames.add(basename)
    return {"ok": True, "msg": msg, "labels": labels_out, "marked_b64": info.get("marked_b64", "")}


@router.post("/api/save_corrections")
def save_corrections(body: dict):
    from server import _analysis, DATASET_DIR, draw_labelled_image, _cv_to_b64
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
    from server import _corrected_basenames
    _corrected_basenames.add(basename)
    return {"ok": True, "saved": str(lbl_path), "n_labels": len(lines)}


@router.post("/api/revert")
def revert_corrections(body: dict):
    from server import DATASET_DIR, _analysis
    basename = body.get("basename")
    lbl_path = DATASET_DIR / "labels" / "train" / (basename + ".txt")
    bak_path = lbl_path.with_suffix(lbl_path.suffix + ".bak")
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


@router.post("/api/section")
def add_section(body: dict):
    from server import _analysis, CLASS_IDS, _push, _rebuild_labels
    basename = body.get("basename")
    bbox     = body.get("bbox")
    label    = body.get("label", "Room")
    info = _analysis.get(basename)
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
    cnt = __import__('numpy').array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]], dtype=__import__('numpy').int32).reshape(-1, 1, 2)
    if not info.get("from_disk") or info.get("labelled"):
        info["labelled"].setdefault(label, []).append(cnt)
    else:
        info["labelled"] = {label: [cnt]}
    _rebuild_labels(basename, info)
    labels_out = {k: len(v) for k, v in info["labelled"].items() if v}
    info["_counts"] = labels_out
    import hashlib
    guid = hashlib.md5(f"{basename}_{x}_{y}_{w}_{h}_{label}".encode()).hexdigest()[:12].upper()
    return {"ok": True, "guid": guid, "label": label, "bbox": [x, y, w, h], "labels": labels_out, "n_labels": info["n_labels"]}


@router.get("/api/label_details/{basename}")
def get_label_details(basename: str):
    from server import _analysis, _cv_to_b64, ID_TO_CLASS
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
                x, y, w, h = __import__('cv2').boundingRect(cnt)
                area = float(__import__('cv2').contourArea(cnt))
                eps = 0.02 * __import__('cv2').arcLength(cnt, True)
                approx = __import__('cv2').approxPolyDP(cnt, eps, True)
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
                cnt = __import__('numpy').array(pts, dtype=__import__('numpy').int32).reshape(-1, 1, 2)
                x, y, w, h = __import__('cv2').boundingRect(cnt)
                area = float(__import__('cv2').contourArea(cnt))
                details.setdefault(cls, []).append({"idx": len(details.get(cls, [])) + 1, "bbox": [x, y, w, h], "poly": pts, "area": round(area)})
            except Exception:
                pass
    return {"details": details, "img_w": img_w, "img_h": img_h}


@router.post("/api/resize_label")
def resize_label(body: dict):
    from server import _analysis, _rebuild_labels, ID_TO_CLASS
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
    new_cnt = __import__('numpy').array([[x,y],[x+w,y],[x+w,y+h],[x,y+h]], dtype=__import__('numpy').int32).reshape(-1, 1, 2)
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
                        cnt = __import__('numpy').array(pts, dtype=__import__('numpy').int32).reshape(-1, 1, 2)
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
    from server import _push
    _push(msg, status=msg)
    return {"ok": True, "msg": msg, "labels": labels_out, "marked_b64": info.get("marked_b64", "")}


@router.post("/api/autolabel")
def autolabel(background_tasks: BackgroundTasks, body: dict = None):
    from server import _autolabel_worker, _push, _log_queue, _progress
    body = body or {}
    selected = body.get("files", [])
    metadata_choice = body.get("metadata_choice", "local")
    _push(f"Received autolabel request. Mode Strategy: [{metadata_choice}]. Scope Selected count: {len(selected)}")
    background_tasks.add_task(_autolabel_worker, selected, metadata_choice, background_tasks)
    # return immediate log snippets so UI can show initial progress when EventSource isn't yet attached
    recent = list(_log_queue[-8:]) if isinstance(_log_queue, list) else []
    return {"ok": True, "queued": True, "logs": recent, "progress": _progress}
