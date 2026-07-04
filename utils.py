import math
import base64
import cv2
import numpy as np
from typing import Optional

from config.classes import CLASS_IDS, ID_TO_CLASS
from logic.auto_label import contour_to_yolo_seg


def _cv_to_b64(img: np.ndarray) -> str:
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode()


def label_lines_from_labelled(labelled: dict, img_w: int, img_h: int) -> list:
    """Build YOLO segmentation label lines from a labelled contour dict."""
    lines = []
    for cls_name, contours in (labelled or {}).items():
        if cls_name.startswith("_") or not isinstance(contours, list):
            continue
        cid = CLASS_IDS.get(cls_name)
        if cid is None:
            continue
        for cnt in contours:
            line = contour_to_yolo_seg(cnt, img_w, img_h, cid)
            if line:
                lines.append(line)
    return lines


def _convert_gemini_to_yolo_contours(building_data, img_w, img_h, scale=100.0):
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


def _run_local_inference(image_path: str, weights_path: str):
    try:
        from ultralytics import YOLO
        model = YOLO(weights_path)
        results = model.predict(source=image_path, imgsz=640, conf=0.25, verbose=False)
        out = []
        for r in results:
            boxes = r.boxes
            for b in boxes:
                cls = int(b.cls[0]) if hasattr(b, 'cls') else None
                xyxy = b.xyxy[0].cpu().numpy().tolist()
                conf = float(b.conf[0]) if hasattr(b, 'conf') else None
                out.append({"class": cls, "xyxy": xyxy, "conf": conf})
        return out
    except Exception as e:
        # Keep error handling minimal here; caller should log
        return []


def _bbox_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    boxAArea = max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1])
    boxBArea = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])
    denom = boxAArea + boxBArea - interArea
    return interArea / denom if denom > 0 else 0.0


def _contour_to_bbox(cnt):
    xs = cnt[:, 0, 0]
    ys = cnt[:, 0, 1]
    x1, y1, x2, y2 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    return [x1, y1, x2, y2]


def _compare_preds_to_labels(preds, labelled_contours, iou_thresh=0.25):
    gt_boxes = []
    for cls_name, contours in labelled_contours.items():
        cid = CLASS_IDS.get(cls_name)
        if cid is None: continue
        for cnt in contours:
            gt_boxes.append({"class": cid, "bbox": _contour_to_bbox(cnt)})
    matched = 0
    used_gt = set()
    for p in preds:
        pbox = p.get("xyxy")
        pcl = p.get("class")
        best_iou = 0
        best_idx = None
        for i, g in enumerate(gt_boxes):
            if g["class"] != pcl: continue
            iou = _bbox_iou(pbox, g["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_idx = i
        if best_iou >= iou_thresh and best_idx is not None and best_idx not in used_gt:
            matched += 1
            used_gt.add(best_idx)
    n_gt = len(gt_boxes)
    n_pred = len(preds)
    precision = matched / n_pred if n_pred > 0 else 0.0
    recall = matched / n_gt if n_gt > 0 else 0.0
    return {"n_gt": n_gt, "n_pred": n_pred, "matched": matched, "precision": precision, "recall": recall}
