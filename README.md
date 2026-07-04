# OonexBIM — Floor Plan Auto-Labeler & BIM Pipeline

A FastAPI web application that processes architectural floor plan images to automatically generate YOLO segmentation labels, IFC (BIM) files, and train a custom object detection model.

## What It Does

1. **Upload** floor plan images (JPG, PNG, SVG)
2. **Auto-Label** — detects rooms, doors, windows, furniture, and sanitary elements using either:
   - **Gemini Vision API** — cloud-based extraction that also generates IFC files
   - **Local Heuristics** — OpenCV-based detection with OCR room text mapping
3. **Review & Correct** labels via the web UI (draw, relabel, remove, resize)
4. **Train** a YOLOv8 segmentation model on the labelled dataset
5. **Export IFC** — generates `.ifc` BIM files compatible with ArchiCAD / Revit
6. **Test** the trained model on new floor plans

---

## Project Structure

```
web_git/
├── server.py                    # Main FastAPI server (port 8002)
├── automated_bim_v4_connected.py # Gemini API extraction + IFC compiler
├── utils.py                     # Shared helpers (image encoding, YOLO utils)
├── index.html                   # Web dashboard UI
├── handlers/
│   ├── upload.py                # File upload endpoint
│   ├── detect.py                # Detection & analysis endpoints
│   ├── images.py                # Image serving endpoints
│   ├── labels.py                # Label management endpoints
│   └── models.py                # Model management endpoints
└── static/
    ├── css/style.css
    └── js/                      # Panel JS modules (train, correct, test, etc.)
```

The server expects a sibling `logic/` directory and a `gdrive_dataset/` folder at the project root (`sam_env_v1/`).

---

## Prerequisites

- Python 3.10+
- A virtual environment (recommended: `sam_env`)
- (Optional) NVIDIA GPU or Apple Silicon for faster training

---

## Setup

### 1. Install dependencies

```bash
pip install fastapi uvicorn opencv-python numpy ultralytics \
            ifcopenshell google-genai pydantic gdown
```

### 2. Configure Gemini API key (optional, for cloud extraction)

Create a file at the project root:

```bash
echo "GEMINI_API_KEY=your_key_here" > ../gemini.key
```

Or set the environment variable:

```bash
export GEMINI_API_KEY=your_key_here
```

### 3. Place the YOLOv8 base model

Download `yolov8n-seg.pt` to the project root (`sam_env_v1/`):

```bash
# Ultralytics will auto-download on first train, or manually:
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n-seg.pt -P ../
```

---

## Running the Server

```bash
cd /path/to/sam_env_v1/web_git
python server.py
```

The server starts at **http://localhost:8002**

Or with uvicorn directly:

```bash
uvicorn server:app --host 0.0.0.0 --port 8002 --reload
```

---

## Using the Dashboard

Open **http://localhost:8002** in your browser.

| Panel | Description |
|-------|-------------|
| **Dashboard** | Upload images, run auto-label pipeline, view live logs |
| **Train** | Configure and launch YOLOv8 training |
| **Correct** | Review labels, draw new regions, relabel or remove detections |
| **Test** | Run inference on a floor plan with a selected model |
| **IFC Props** | Edit IFC property sets per element |
| **OCR** | Run room text mapping analysis |
| **Convert** | Run full Gemini extraction + evaluation |
| **Models** | View model versions, set active model, merge models |

### Typical Workflow

1. **Upload** floor plan images via the Dashboard
2. Select processing engine: `Gemini` (requires API key) or `Local`
3. Click **Execute Auto-Label & IFC Compile** — labels and IFC files are generated automatically; YOLO training starts in the background
4. Switch to **Correct** to review and fix any labelling errors
5. Click **Update Model** to fine-tune on corrected labels
6. Use **Test** to validate detection on new images

---

## Running IFC Generation Standalone

To generate an IFC file from a single floor plan image without the web server:

```bash
cd /path/to/sam_env_v1
python web_git/automated_bim_v4_connected.py \
    --image "floor_plan.jpg" \
    --output "output.ifc" \
    --debug
```

Options:
- `--force` — re-run Gemini extraction even if a cache file exists
- `--allow-low-detail` — write IFC even if extraction appears incomplete
- `--cache <file>` — path to JSON cache file (default: `<image_stem>_Detailed_Cache.json`)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Server status, image lists, active model |
| POST | `/api/upload` | Upload floor plan images |
| POST | `/api/autolabel` | Run auto-labelling pipeline |
| POST | `/api/train` | Start YOLO training |
| POST | `/api/detect` | Run detection on an uploaded image |
| GET | `/api/stream` | SSE stream for live logs |
| GET | `/api/model_versions` | List all trained models |
| POST | `/api/train_from_corrections` | Fine-tune from corrected labels |
| GET | `/api/ifc/export/{basename}` | Export IFC properties as JSON |

---

## Dataset Layout (auto-created)

```
sam_env_v1/gdrive_dataset/
├── images_raw/       # Source floor plan images
├── images/train/     # Processed training images
├── labels/train/     # YOLO segmentation label files (.txt)
├── marked/           # Labelled overlay images
├── metadata/         # JSON metadata + IFC property files
├── runs/             # YOLO training run outputs
└── dataset.yaml      # Auto-generated YOLO dataset config
```
