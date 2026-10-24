"""Shared helpers for the trained TrustSphere detectors: dataset indexing, forensic input maps, metrics."""
import io
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFile
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score, roc_curve)

ImageFile.LOAD_TRUNCATED_IMAGES = True   # a few dataset PNGs are truncated; decode what is there

DATASETS_ROOT = Path(os.environ.get("TRUSTSPHERE_DATA", r"C:\Users\Divyansh Gupta\Desktop\TrustSphere AI - Datasets"))


def find(prefix):
    return next(p for p in DATASETS_ROOT.iterdir() if p.name.startswith(prefix))


# ── dataset indexes: (path, label, group) with label 1 = manipulated ──────────────────────────
def index_casia():
    """CASIA v2.0 (HF compilation). Tampered images carry their source authentic image in the .json sidecar,
    so a tampered image and its source can be kept in the same group (leakage-aware split)."""
    root = find("Image - CASIA")
    items = []
    for f in sorted((root / "auth").glob("*.png")):
        items.append((f, 0, f.name.replace(".png", "")))
    for f in sorted((root / "manip").glob("*.png")):
        if f.name.endswith(".mask.png"):
            continue
        js = f.with_name(f.name.replace(".png", ".json"))
        src = json.loads(js.read_text(encoding="utf-8")).get("auth", "") if js.exists() else ""
        group = Path(src).name + ".png" if src else f.name
        items.append((f, 1, group.replace(".png", "")))
    return items


def index_columbia():
    root = find("Image - Columbia")
    def scene(f):   # file names end in _sub_NN: the same NN is the same scene photographed or composited from
        return f.name.split("_sub_")[-1].split(".")[0]
    items = [(f, 0, scene(f)) for f in sorted((root / "auth").glob("*.png"))]
    items += [(f, 1, scene(f)) for f in sorted((root / "manip").glob("*.png")) if not f.name.endswith(".mask.png")]
    return items


def index_docs(prefix):
    root = find(prefix)
    items = [(f, 0, f.stem) for f in sorted((root / "auth").glob("*.png"))]
    items += [(f, 1, f.stem) for f in sorted((root / "manip").glob("*.png"))]
    return items


INDEXES = {"casia_v2": index_casia, "columbia": index_columbia,
           "t_sroie": lambda: index_docs("Document - T-SROIE"), "sifta": lambda: index_docs("Document - SIFTA")}


# ── forensic input: error-level analysis map ───────────────────────────────────────────────
def ela_map(img: Image.Image, quality=90, gain=12):
    """Difference between the image and its JPEG re-save, amplified. Returns uint8 HxWx3."""
    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    re_img = Image.open(buf).convert("RGB")
    d = np.asarray(ImageChops.difference(img, re_img), dtype=np.float32) * gain
    return np.clip(d, 0, 255).astype(np.uint8)


def ela_multi(img: Image.Image, qualities=(70, 85, 95), gain=14):
    """Grey-scale ELA at several JPEG qualities stacked as three channels (double-compression traces at different strengths)."""
    img = img.convert("RGB")
    chans = []
    for q in qualities:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=q)
        buf.seek(0)
        d = np.asarray(ImageChops.difference(img, Image.open(buf).convert("RGB")), dtype=np.float32).mean(2) * gain
        chans.append(np.clip(d, 0, 255).astype(np.uint8))
    return np.stack(chans, 2)


def ela_multi_rgb(img: Image.Image):
    """Six channels: multi-quality ELA (3) + the image itself (3)."""
    return np.concatenate([ela_multi(img), np.asarray(img.convert("RGB"))], axis=2)


_SRM = [np.array(k, np.float32) / d for k, d in (
    ([[0, 0, 0, 0, 0], [0, -1, 2, -1, 0], [0, 2, -4, 2, 0], [0, -1, 2, -1, 0], [0, 0, 0, 0, 0]], 4),
    ([[-1, 2, -2, 2, -1], [2, -6, 8, -6, 2], [-2, 8, -12, 8, -2], [2, -6, 8, -6, 2], [-1, 2, -2, 2, -1]], 12),
    ([[0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 1, -2, 1, 0], [0, 0, 0, 0, 0], [0, 0, 0, 0, 0]], 2))]


def srm_map(img: Image.Image, scale=40):
    """Noise residual: three fixed SRM high-pass filters on the grey image (the noise-based traces ELA cannot see on uncompressed photos)."""
    import cv2
    g = np.asarray(img.convert("L"), dtype=np.float32)
    ch = [np.clip(cv2.filter2D(g, -1, k) * scale / 8 + 128, 0, 255) for k in _SRM]
    return np.stack(ch, 2).astype(np.uint8)


def srm_rgb(img: Image.Image):
    return np.concatenate([srm_map(img), np.asarray(img.convert("RGB"))], axis=2)


INPUTS = {"ela90": ela_map, "multiq": ela_multi, "multiq_rgb": ela_multi_rgb, "srm": srm_map, "srm_rgb": srm_rgb}
CHANNELS = {"ela90": 3, "multiq": 3, "multiq_rgb": 6, "srm": 3, "srm_rgb": 6}


# ── metrics ────────────────────────────────────────────────────────────────────────────────
def eer(y, score):
    fpr, tpr, _ = roc_curve(y, score)
    fnr = 1 - tpr
    i = int(np.nanargmin(np.abs(fnr - fpr)))
    return float((fpr[i] + fnr[i]) / 2)


def metrics(y, p, thr=0.5):
    y = np.asarray(y)
    p = np.asarray(p)
    pred = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {"n": int(len(y)), "accuracy": float(accuracy_score(y, pred)), "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
            "precision": float(precision_score(y, pred, zero_division=0)), "recall": float(recall_score(y, pred, zero_division=0)),
            "specificity": float(tn / max(1, tn + fp)), "f1": float(f1_score(y, pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)), "eer": eer(y, p),
            "confusion": [[int(tn), int(fp)], [int(fn), int(tp)]]}
