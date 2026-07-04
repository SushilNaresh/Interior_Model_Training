#!/usr/bin/env python3
"""
web/server.py 
Consolidated FastAPI Server Backend.
AUTO-TRIGGERS local YOLO training immediately following successful Gemini IFC structural processing.
"""

import os
import sys
import glob
import time
import json
import math
import base64
import shutil
import asyncio
import threading
import traceback
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ── Environment Path Routing Setup ────────────────────────────────────────────
# ── Corrected Path Routing Setup ──────────────────────────────────────────────
WEB_DIR      = Path(__file__).resolve().parent                # sam_env/web
PROJECT_ROOT = WEB_DIR.parent                                 # sam_env
LOGIC_DIR    = PROJECT_ROOT / "logic"                         # sam_env/logic

for p in [str(PROJECT_ROOT), str(LOGIC_DIR), str(WEB_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)



#LOGIC_DIR = Path(__file__).resolve().parent.parent          # logic/
#PROJECT_ROOT = LOGIC_DIR                                    # sam_env/
#for p in [str(PROJECT_ROOT), str(LOGIC_DIR)]:
#    if p not in sys.path:
#        sys.path.insert(0, p)

# ── System Module Imports ─────────────────────────────────────────────────────
from config.classes import CLASS_IDS, ID_TO_CLASS
from logic.auto_label import generate_labels, draw_labelled_image, contour_to_yolo_seg
from logic.ifc_properties import IFC_SCHEMA, MATERIALS, get_default_pset, validate_pset
from logic import bim_compiler
from logic.image_metadata import save_metadata

# Check Cloud API Engine Dependencies
try:
    from google import genai
    from google.genai import types
    HAS_GEMINI_SDK = True
except ImportError:
    HAS_GEMINI_SDK = False

DATASET_DIR = PROJECT_ROOT / "gdrive_dataset"
IMG_EXTS    = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

_log_queue: list[str] = []          
_progress: dict       = {"pct": 0, "status": "Ready", "metrics": {}}
_analysis: dict       = {}          
_ifc_props: dict      = {}          
_corrected_basenames  = set()       
_training_lock        = threading.Lock()
_training_active      = False

def _push(msg: str, pct: float = None, status: str = None, metrics: dict = None):
    _log_queue.append(msg)
    if pct is not None: _progress["pct"] = round(pct, 1)
    if status: _progress["status"] = status
    if metrics: _progress["metrics"].update(metrics)

app = FastAPI(title="Unified Floor Plan Auto-Labeling and Training Core Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

#WEB_DIR = Path(__file__).resolve().parent
if (WEB_DIR / "static").is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

# Ensure index path reads accurately from the updated WEB_DIR
@app.get("/", response_class=HTMLResponse)
def index():
    html_path = WEB_DIR / "index.html"
    if html_path.exists(): 
        return html_path.read_text()
    return "<h3>Integrated Dashboard active, but index.html was not found in web/ folder.</h3>"

def _cv_to_b64(img: np.ndarray) -> str:
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode()

def _convert_gemini_to_yolo_contours(building_data, img_w, img_h, scale=100.0):
    """Maps continuous meters measurements cleanly into discrete 2D canvas poly arrays."""
    labelled_contours = {"Room": [], "Door": [], "Window": [], "Furniture": [], "FlowTerminal": [], "ElectricAppliance": []}
    
    for wall in building_data.walls:
        x1, y1 = wall.start_pt[0] * scale, wall.start_pt[1] * scale
        x2, y2 = wall.end_pt[0] * scale, wall.end_pt[1] * scale
        thick = wall.thickness * scale
        dx, dy = x2 - x1, y2 - y1
        angle = math.atan2(dy, dx)
        px, py = -math.sin(angle) * (thick / 2.0), math.cos(angle) * (thick / 2.0)
        
        poly = np.array([
            [x1 - px, y1 - py], [x2 - px, y2 - py],
            [x2 + px, y2 + py], [x1 + px, y1 + py]
        ], dtype=np.int32).reshape(-1, 1, 2)
        labelled_contours["Room"].append(poly)

    for item in building_data.interiors:
        cx, cy = item.location_pt[0] * scale, item.location_pt[1] * scale
        w = (item.dimensions[0] if len(item.dimensions) > 0 else 0.8) * scale
        d = (item.dimensions[1] if len(item.dimensions) > 1 else 0.8) * scale
        x, y = int(cx - w/2), int(cy - d/2)
        poly = np.array([[x, y], [x+w, y], [x+w, y+d], [x, y+d]], dtype=np.int32).reshape(-1, 1, 2)
        
        if item.category == "furnishing": labelled_contours["Furniture"].append(poly)
        elif item.category == "sanitary": labelled_contours["FlowTerminal"].append(poly)
        elif item.category == "appliance": labelled_contours["ElectricAppliance"].append(poly)
        
    return labelled_contours

@app.get("/api/stream")
async def stream():
    async def event_gen():
        sent = 0
        while True:
            while sent < len(_log_queue):
                yield f"data: {json.dumps({'log': _log_queue[sent], 'progress': _progress})}\n\n"
                sent += 1
            await asyncio.sleep(0.3)
    return StreamingResponse(event_gen(), media_type="text/event-stream")

@app.get("/api/status")
def get_status():
    return {
        **_progress, "training": _training_active,
        "raw_images": sorted([f for f in os.listdir(DATASET_DIR / "images_raw") if Path(f).suffix.lower() in IMG_EXTS]) if (DATASET_DIR / "images_raw").is_dir() else [],
        "labelled_images": sorted(_analysis.keys())
    }

@app.post("/api/upload")
async def upload_images(files: list[UploadFile] = File(...)):
    dl_dir = DATASET_DIR / "images_raw"
    dl_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for f in files:
        if Path(f.filename).suffix.lower() in IMG_EXTS:
            (dl_dir / f.filename).write_bytes(await f.read())
            saved += 1
    return {"saved": saved}

@app.post("/api/autolabel")
def autolabel(background_tasks: BackgroundTasks, body: dict = None):
    body = body or {}
    selected = body.get("files", [])
    metadata_choice = body.get("metadata_choice", "local")
    background_tasks.add_task(_autolabel_worker, selected, metadata_choice, background_tasks)
    return {"ok": True}

def _autolabel_worker(selected_files: list, metadata_choice: str, background_tasks: BackgroundTasks):
    raw_dir, img_out, lbl_out, mark_out = DATASET_DIR / "images_raw", DATASET_DIR / "images" / "train", DATASET_DIR / "labels" / "train", DATASET_DIR / "marked"
    for d in [img_out, lbl_out, mark_out]: d.mkdir(parents=True, exist_ok=True)
    
    all_files = sorted([raw_dir / f for f in os.listdir(raw_dir) if Path(f).suffix.lower() in IMG_EXTS])
    files = [f for f in all_files if f.name in set(selected_files)] if selected_files else all_files
    
    new_labels_produced = False

    for i, img_path in enumerate(files):
        basename = img_path.stem
        _push(f"Parsing model architecture layer configuration mapping vectors {i+1}/{len(files)}: {basename}", pct=((i+1)/len(files))*100)
        
        try:
            img = cv2.imread(str(img_path))
            h, w = img.shape[:2]
            
            if metadata_choice == "gemini":
                if not os.environ.get("GEMINI_API_KEY") or not HAS_GEMINI_SDK:
                    _push("⚠️ Processing skipped: GEMINI_API_KEY initialization target maps are missing."); continue
                
                client = genai.Client()
                with open(str(img_path), 'rb') as f: img_bytes = f.read()
                image_part = types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg')
                
                response = client.models.generate_content(
                    model='gemini-3-flash-preview',
                    contents=[image_part, "Extract structural partitions, coordinate wall alignments, structural elements, and furniture metrics."],
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=bim_compiler.BuildingAnalysis, temperature=0.0)
                )
                building_data = response.parsed
                labelled = _convert_gemini_to_yolo_contours(building_data, w, h)
                
                # ── CORE IFCBlueprint Writing Sequence Trigger ──
                save_metadata(str(img_path), DATASET_DIR, building_data.model_dump())
                ifc_file_target = DATASET_DIR / "metadata" / f"{basename}.ifc"
                bim_compiler.build_detailed_ifc(building_data, str(ifc_file_target))
                _push(f"📄 Generated high-fidelity standard model configuration blueprint: {basename}.ifc")
            else:
                continue # Skip placeholder fallback routines to preserve scope
                
            label_lines = []
            for cls_name, contours in labelled.items():
                cid = CLASS_IDS.get(cls_name)
                if cid is None: continue
                for cnt in contours:
                    line = contour_to_yolo_seg(cnt, w, h, cid)
                    if line: label_lines.append(line)
            
            if not label_lines: continue
            
            shutil.copy2(str(img_path), str(img_out / img_path.name))
            (lbl_out / f"{basename}.txt").write_text("\n".join(label_lines) + "\n")
            draw_labelled_image(img, labelled, str(mark_out / f"{basename}_labelled.jpg"))
            
            _analysis[basename] = {"label_lines": label_lines, "n_labels": len(label_lines)}
            new_labels_produced = True
        except Exception as e:
            _push(f"❌ Structural extraction sequence pipeline fault context ({basename}): {e}")
            traceback.print_exc()

    _push("✅ Ground spatial maps verification lifecycle routines complete.", pct=100, status="Ready")

    # ── CRITICAL AUTO-TRAIN SEQUENCER ──
    if new_labels_produced and background_tasks is not None:
        _push("🚀 Auto-Train Event: Commencing neural training loop using newly generated cloud telemetry annotations...")
        background_tasks.add_task(_train_worker, 5, 4, 640) # Default configuration: 5 epochs, batch 4

@app.post("/api/train")
def train(body: dict, background_tasks: BackgroundTasks):
    global _training_active
    if _training_active: return JSONResponse({"error": "System neural training execution loop locked."}, status_code=409)
    background_tasks.add_task(_train_worker, int(body.get("epochs", 5)), int(body.get("batch", 4)), int(body.get("imgsz", 640)))
    return {"ok": True}

def _train_worker(epochs: int, batch: int, imgsz: int):
    global _training_active
    if not _training_lock.acquire(blocking=False):
        _push("⚠️ Process collision skipped: Multi-thread fitting blocker triggered.")
        return
    _training_active = True
    _push("Initializing local machine learning dataset verification operations parameter matching...", status="Training...")
    try:
        from ultralytics import YOLO
        import torch
        
        yaml_path = DATASET_DIR / "dataset.yaml"
        if not yaml_path.exists():
            # Build inline standard training manifests
            yaml_content = f"path: {str(DATASET_DIR)}\ntrain: images/train\nval: images/train\nnc: {len(CLASS_IDS)}\nnames:\n" + "\n".join([f"  {v}: {k}" for k, v in CLASS_IDS.items()])
            yaml_path.write_text(yaml_content)
            
        model_base = str(PROJECT_ROOT / "yolov8n-seg.pt")
        model = YOLO(model_base if os.path.exists(model_base) else "yolov8n-seg.pt")
        device = "cuda" if torch.cuda.is_available() else ("mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else "cpu")
        
        _push(f"Starting fitting process optimization loops: Hardware acceleration compute framework -> [{device}]")
        model.train(data=str(yaml_path), epochs=epochs, batch=batch, imgsz=imgsz, device=device, project=str(DATASET_DIR / "runs"), name="train", workers=0, verbose=False)
        
        cands = glob.glob(os.path.join(str(DATASET_DIR / "runs"), "**", "best.pt"), recursive=True)
        if cands:
            shutil.copy2(max(cands, key=os.path.getmtime), str(PROJECT_ROOT / "best_gdrive.pt"))
            _push(f"✅ Auto-Train complete! Active network weights updated successfully: best_gdrive.pt", pct=100, status="Ready")
    except Exception as e:
        _push(f"❌ Training pipeline failure context event logging state trace: {e}")
    finally:
        _training_active = False
        _training_lock.release()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
