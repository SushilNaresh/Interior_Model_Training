from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
import os
import cv2
import numpy as np

router = APIRouter()

@router.get("/api/raw/{filename}")
def get_raw_image(filename: str):
    from server import DATASET_DIR, IMG_EXTS, _cv_to_b64, _push
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


@router.get("/api/raw_thumb/{filename}")
def get_raw_thumb(filename: str):
    from server import DATASET_DIR, IMG_EXTS, _cv_to_b64
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
    _, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@router.get("/api/thumb/{basename}")
def get_thumb(basename: str):
    from server import _analysis, DATASET_DIR, _cv_to_b64
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
    _, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return Response(content=buf.tobytes(), media_type="image/jpeg")
