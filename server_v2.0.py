#!/usr/bin/env python3
"""
web/server.py 
Consolidated FastAPI Server Backend with Enhanced Diagnostic Logging.
AUTO-TRIGGERS local YOLO training immediately following successful Gemini IFC structural processing.
Includes robust selective file execution constraints.
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
import logging
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

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
from logic.ifc_properties import IFC_SCHEMA, MATERIALS, get_default_pset, validate_pset
from logic import bim_compiler
from logic.image_metadata import save_metadata

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
IMG_EXTS    = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

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

def _cv_to_b64(img: np.ndarray) -> str:
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode()

def _convert_gemini_to_yolo_contours(building_data, img_w, img_h, scale=100.0):
    _push(f"Starting metric spatial projection to pixel conversions (Canvas size: {img_w}x{img_h})...")
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

    _push(f"Projected {len(building_data.walls)} structural wall segments onto centerline canvas paths.")

    for item in building_data.interiors:
        cx, cy = item.location_pt[0] * scale, item.location_pt[1] * scale
        w = (item.dimensions[0] if len(item.dimensions) > 0 else 0.8) * scale
        d = (item.dimensions[1] if len(item.dimensions) > 1 else 0.8) * scale
        x, y = int(cx - w/2), int(cy - d/2)
        poly = np.array([[x, y], [x+w, y], [x+w, y+d], [x, y+d]], dtype=np.int32).reshape(-1, 1, 2)
        
        if item.category == "furnishing": labelled_contours["Furniture"].append(poly)
        elif item.category == "sanitary": labelled_contours["FlowTerminal"].append(poly)
        elif item.category == "appliance": labelled_contours["ElectricAppliance"].append(poly)
        
    _push(f"Projected {len(building_data.interiors)} interior component boundary rings.")
    return labelled_contours

@app.get("/api/stream")
async def stream():
    async def event_gen():
        sent = 0
        while True:
            while sent < len(_log_queue):
                yield f"data: {json.dumps({'log': _log_queue[sent], 'progress': _progress})}\n\n"
                sent += 1
            await asyncio.sleep(0.1)
    return StreamingResponse(event_gen(), media_type="text/event-stream")

@app.get("/api/status")
def get_status():
    raw_dir = DATASET_DIR / "images_raw"
    images = sorted([f for f in os.listdir(raw_dir) if Path(f).suffix.lower() in IMG_EXTS]) if raw_dir.is_dir() else []
    return {
        **_progress, "training": _training_active,
        "raw_images": images,
        "labelled_images": sorted(_analysis.keys())
    }

# ── ROBUST IMAGE RESOLUTION ROUTE WITH UNLABELLED FALLBACK ───────────────────
@app.get("/api/image/{filename_or_basename}")
def get_image(filename_or_basename: str):
    basename = Path(filename_or_basename).stem
    filename = filename_or_basename if "." in filename_or_basename else f"{basename}.jpg"
    
    print(f"[ROUTE HIT] View request received for token: '{filename_or_basename}'")

    # 1. Check current runtime active session map
    info = _analysis.get(basename)
    if info and info.get("marked_b64"):
        print(f"[VIEW-SUCCESS] Serving active session marked overlay for: {basename}")
        return {"marked_b64": info.get("marked_b64"), "n_labels": info.get("n_labels", 0)}

    # 2. Check disk historical mark copies
    marked_file = DATASET_DIR / "marked" / f"{basename}_labelled.jpg"
    if marked_file.exists():
        print(f"[VIEW-SUCCESS] Loading saved marked layout overlay from disk cache: {marked_file.name}")
        img_b64 = _cv_to_b64(cv2.imread(str(marked_file)))
        return {"marked_b64": img_b64, "n_labels": 0}

    # 3. Serve original raw uploaded blueprint asset
    raw_dir = DATASET_DIR / "images_raw"
    if raw_dir.is_dir():
        direct_target = raw_dir / filename
        if direct_target.exists():
            raw_img = cv2.imread(str(direct_target))
            if raw_img is not None:
                print(f"[VIEW-SUCCESS] Serving raw unlabelled blueprint match directly: {direct_target.name}")
                return {"marked_b64": _cv_to_b64(raw_img), "n_labels": 0}

        for f in os.listdir(raw_dir):
            if Path(f).stem == basename and Path(f).suffix.lower() in IMG_EXTS:
                candidate = raw_dir / f
                raw_img = cv2.imread(str(candidate))
                if raw_img is not None:
                    print(f"[VIEW-SUCCESS] Serving raw layout match via signature verification: {candidate.name}")
                    return {"marked_b64": _cv_to_b64(raw_img), "n_labels": 0}

    print(f"[VIEW-ERROR] 404 - No raw baseline asset or overlay files matched key: {filename_or_basename}")
    return JSONResponse({"error": "No matching floor plan found on server storage disk."}, status_code=404)

@app.post("/api/upload")
async def upload_images(files: list[UploadFile] = File(...)):
    dl_dir = DATASET_DIR / "images_raw"
    dl_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for f in files:
        if Path(f.filename).suffix.lower() in IMG_EXTS:
            dest = dl_dir / f.filename
            dest.write_bytes(await f.read())
            print(f"[UPLOAD] Saved incoming raw blueprint asset: {dest}")
            saved += 1
    _push(f"Successfully staged {saved} incoming image files onto local filesystem.")
    return {"saved": saved}

@app.post("/api/autolabel")
def autolabel(background_tasks: BackgroundTasks, body: dict = None):
    body = body or {}
    selected = body.get("files", [])
    metadata_choice = body.get("metadata_choice", "local")
    _push(f"Received autolabel request. Mode Strategy: [{metadata_choice}]. Scope Selected count: {len(selected)}")
    background_tasks.add_task(_autolabel_worker, selected, metadata_choice, background_tasks)
    return {"ok": True}

def _autolabel_worker(selected_files: list, metadata_choice: str, background_tasks: BackgroundTasks):
    raw_dir, img_out, lbl_out, mark_out = DATASET_DIR / "images_raw", DATASET_DIR / "images" / "train", DATASET_DIR / "labels" / "train", DATASET_DIR / "marked"
    for d in [img_out, lbl_out, mark_out]: d.mkdir(parents=True, exist_ok=True)
    
    all_files = sorted([raw_dir / f for f in os.listdir(raw_dir) if Path(f).suffix.lower() in IMG_EXTS])
    
    # Filter only explicitly checked boxes, or default to entire directory matching
    if selected_files and len(selected_files) > 0:
        target_set = set(selected_files)
        files = [f for f in all_files if f.name in target_set]
        print(f"[PIPELINE STAGING] Selective processing filter active. Handling {len(files)} targeted candidates.")
    else:
        files = all_files
        print(f"[PIPELINE STAGING] No explicit constraints passed. Processing all {len(files)} total files.")
    
    if not files:
        return _push("⚠️ Auto-labeling skipped: No valid processing candidates found in input storage folder.")

    new_labels_produced = False

    for i, img_path in enumerate(files):
        basename = img_path.stem
        _push(f"Parsing structure geometry metrics {i+1}/{len(files)}: '{img_path.name}'", pct=((i+1)/len(files))*100, status="Extracting...")
        
        try:
            img = cv2.imread(str(img_path))
            if img is None:
                _push(f"❌ Critical Error: Failed to open or decode target file: '{img_path.name}'"); continue
                
            h, w = img.shape[:2]
            
            if metadata_choice == "gemini":
                if not os.environ.get("GEMINI_API_KEY") or not HAS_GEMINI_SDK:
                    _push("❌ Operational stop: GEMINI_API_KEY environment initialization targets missing."); continue
                
                client = genai.Client()
                with open(str(img_path), 'rb') as f: img_bytes = f.read()
                image_part = types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg')
                
                # Fetch original complex extraction prompt blocks dynamically
                prompt_generator = getattr(bim_compiler, "_build_extraction_prompt", None)
                main_prompt = prompt_generator(str(img_path)) if prompt_generator else "Extract architectural wall vectors and interiors matching schema."
                
                response = client.models.generate_content(
		    model='gemini-2.5-flash',
                    #model='gemini-3-flash-preview',
                    contents=[image_part, main_prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", 
                        response_schema=bim_compiler.BuildingAnalysis, 
                        temperature=0.0,
                        max_output_tokens=65535
                    )
                )
                building_data = response.parsed
                
                # Trigger suspicious density evaluation retry loop blocks
                is_suspicious_func = getattr(bim_compiler, "_is_extraction_suspicious", None)
                if is_suspicious_func:
                    suspicious, summary, expected = is_suspicious_func(building_data, str(img_path))
                    if suspicious:
                        _push(f"[API-WARN] Extraction counts look partial ({summary}). Re-dispatching strict verification retry query...")
                        retry_prompt = prompt_generator(str(img_path), summary, expected)
                        retry_resp = client.models.generate_content(
                            model='gemini-3-flash-preview',
                            contents=[image_part, retry_prompt],
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json", response_schema=bim_compiler.BuildingAnalysis, temperature=0.0, max_output_tokens=65535
                            )
                        )
                        retry_data = retry_resp.parsed
                        score_func = getattr(bim_compiler, "_extraction_score", None)
                        if score_func and score_func(retry_data) >= score_func(building_data):
                            building_data = retry_data
                
                _push(f"Cloud AI analysis successful. Walls parsed: {len(building_data.walls)}, Interiors: {len(building_data.interiors)}")
                labelled = _convert_gemini_to_yolo_contours(building_data, w, h)
                
                # Save structural metadata caches and trigger high detail IFC assembly blocks
                save_metadata(str(img_path), DATASET_DIR, building_data.model_dump())
                ifc_file_target = DATASET_DIR / "metadata" / f"{basename}.ifc"
                
                _push(f"Compiling structural dimensions mapping graph into target destination: {ifc_file_target.name}")
                bim_compiler.build_detailed_ifc(building_data, str(ifc_file_target), props_module=sys.modules.get('logic.ifc_properties'))
                _push(f"📄 Generated high-fidelity industry-standard model configuration blueprint: {basename}.ifc")
            else:
                _push("Heuristic fallback skipped to maintain focused pipeline scope.")
                continue
                
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
            
            _analysis[basename] = {
                "label_lines": label_lines, "n_labels": len(label_lines),
                "marked_b64": _cv_to_b64(cv2.imread(str(mark_out / f"{basename}_labelled.jpg")))
            }
            new_labels_produced = True
        except Exception as e:
            _push(f"❌ Critical exception hit inside worker thread pool: {e}")
            traceback.print_exc()

    _push("✅ Data positioning and IFC structural parsing operations complete.", pct=100, status="Ready")

    # ── CRITICAL AUTO-TRAIN SEQUENCER LINKED CHAIN ──
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
    if html_path.exists(): return html_path.read_text()
    return "<h3>Integrated Dashboard UI Platform Interface Module Active.</h3>"

if __name__ == "__main__":
    import uvicorn
    print("[INIT] Launching Uvicorn production server process loop at port 8000...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
