from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
import glob
import os
from pathlib import Path

router = APIRouter()

@router.get("/api/base_models")
def get_base_models():
    from server import PROJECT_ROOT
    candidates = [
        PROJECT_ROOT / "yolov8n-seg.pt",
        PROJECT_ROOT / "yolov8s-seg.pt",
        PROJECT_ROOT / "yolov8m-seg.pt",
    ]
    return {"base_models": [
        {"path": str(p), "name": p.name}
        for p in candidates if p.exists()
    ]}


@router.get("/api/model_versions")
def get_model_versions():
    from server import _find_best_model, _model_versions, DATASET_DIR, LOGIC_DIR, PROJECT_ROOT
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


@router.post("/api/set_model")
def set_model(body: dict):
    path = body.get("path")
    if not path or not os.path.exists(path):
        return JSONResponse({"error": "Model file not found"}, status_code=404)
    final = str(Path(__import__('pathlib').Path.cwd()) / "best_gdrive.pt")
    import shutil
    shutil.copy2(path, final)
    from server import _push
    _push(f"✅ Active model set to: {Path(path).name}", status="Model updated")
    return {"ok": True, "active": final}


@router.get("/api/corrected_files")
def get_corrected_files():
    from server import DATASET_DIR, _corrected_basenames
    lbl_dir  = DATASET_DIR / "labels" / "train"
    all_lbls = sorted([f.stem for f in lbl_dir.glob("*.txt")]) if lbl_dir.exists() else []
    return {"corrected": sorted(_corrected_basenames), "all": all_lbls}


@router.post("/api/train_from_corrections")
def train_from_corrections(body: dict, background_tasks: BackgroundTasks):
    from server import _training_active, DATASET_DIR, _find_best_model, _push, _finetune_worker
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
        from server import _corrected_basenames
        selected = [b for b in _corrected_basenames if (lbl_dir / (b + ".txt")).exists()]
        if not selected:
            return JSONResponse({"error": "No corrected images found this session. Make corrections first, or choose 'All Images'."}, status_code=400)
    else:
        selected = []
    if mode == "scratch":
        base = str(Path(__import__('pathlib').Path.cwd() / "yolov8n-seg.pt"))
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


@router.post("/api/merge_models")
def merge_models(body: dict, background_tasks: BackgroundTasks):
    model_a = body.get("model_a", "")
    model_b = body.get("model_b", "")
    alpha   = float(body.get("alpha", 0.5))
    name    = body.get("name", "merged")
    for p, label in [(model_a, "model_a"), (model_b, "model_b")]:
        if not p or not os.path.exists(p):
            return JSONResponse({"error": f"{label} not found: {p}"}, status_code=400)
    background_tasks.add_task(__import__('server')._merge_worker, model_a, model_b, alpha, name)
    return {"ok": True}


@router.post("/api/train")
def train(body: dict, background_tasks: BackgroundTasks):
    if __import__('server')._training_active:
        return JSONResponse({"error": "System neural training execution loop locked."}, status_code=409)
    background_tasks.add_task(__import__('server')._train_worker, int(body.get("epochs", 5)), int(body.get("batch", 4)), int(body.get("imgsz", 640)))
    return {"ok": True}
