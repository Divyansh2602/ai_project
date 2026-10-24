"""Trained manipulation detector used by the image agent.

An EfficientNet-B0 trained on error-level-analysis maps of the CASIA v2.0 / Columbia splicing benchmarks (see training/). The model looks at
224 x 224 crops of the ELA map at native resolution and averages the crops, so forensic traces are not destroyed by resizing.

Weights live in backend/models/trained/ and are listed in manifest.json (first entry that exists is used). If no weights are installed the
agent falls back to its original heuristics, so the app still runs.
"""
import json
import os
import threading
from pathlib import Path

import numpy as np

_DIR = Path(__file__).resolve().parent.parent / "models" / "trained"
CROP = 224
_lock = threading.Lock()
_state = {"loaded": False, "model": None, "meta": None, "device": None, "error": None}


def _manifest():
    p = Path(os.getenv("TRUSTSPHERE_DETECTOR_MANIFEST", _DIR / "manifest.json"))
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"detectors": []}


def _load():
    with _lock:
        if _state["loaded"]:
            return
        _state["loaded"] = True
        try:
            import timm
            import torch
            for entry in _manifest().get("detectors", []):
                w = _DIR / entry["file"]
                if not w.is_file():
                    continue
                ck = torch.load(w, map_location="cpu", weights_only=True)
                ch = 6 if ck.get("input") == "multiq_rgb" else 3
                m = timm.create_model(ck["backbone"], pretrained=False, num_classes=1, in_chans=ch)
                m.load_state_dict(ck["state_dict"])
                dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                _state.update(model=m.to(dev).eval(), meta={**entry, "input": ck.get("input", "multiq"), "channels": ch}, device=dev)
                return
        except Exception as exc:   # a missing optional model must never break an analysis
            _state["error"] = f"{type(exc).__name__}: {exc}"


def available() -> bool:
    _load()
    return _state["model"] is not None


def info() -> dict | None:
    _load()
    return _state["meta"]


def _input_map(img):
    import io
    from PIL import ImageChops
    rgb = img.convert("RGB")
    chans = []
    for q in (70, 85, 95):
        buf = io.BytesIO()
        rgb.save(buf, "JPEG", quality=q)
        buf.seek(0)
        from PIL import Image
        d = np.asarray(ImageChops.difference(rgb, Image.open(buf).convert("RGB")), dtype=np.float32).mean(2) * 14
        chans.append(np.clip(d, 0, 255).astype(np.uint8))
    ela = np.stack(chans, 2)
    if _state["meta"]["input"] == "multiq_rgb":
        return np.concatenate([ela, np.asarray(rgb)], axis=2)
    return ela


def _crops(arr, k=6):
    h, w, _ = arr.shape
    if h < CROP or w < CROP:
        arr = np.pad(arr, ((0, max(0, CROP - h)), (0, max(0, CROP - w)), (0, 0)), mode="reflect")
        h, w, _ = arr.shape
    ys = np.linspace(0, h - CROP, min(k, max(1, (h - CROP) // 64 + 1))).astype(int) if h > CROP else [0]
    xs = np.linspace(0, w - CROP, min(k, max(1, (w - CROP) // 64 + 1))).astype(int) if w > CROP else [0]
    grid = [arr[y:y + CROP, x:x + CROP] for y in ys for x in xs]
    if len(grid) > k:
        grid = [grid[i] for i in np.linspace(0, len(grid) - 1, k).astype(int)]
    return grid


def predict(file_path: str) -> dict | None:
    """Return {"p_fake": float, "crops": int, "model": str} or None when no detector is installed."""
    if not available():
        return None
    import torch
    from PIL import Image, ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    img = Image.open(file_path)
    arr = _input_map(img)
    ch = _state["meta"]["channels"]
    mean = np.tile(np.array([0.485, 0.456, 0.406], np.float32), 2)[:ch]
    std = np.tile(np.array([0.229, 0.224, 0.225], np.float32), 2)[:ch]
    crops = _crops(arr)
    x = (np.stack([np.ascontiguousarray(c) for c in crops]).astype(np.float32) / 255.0 - mean) / std
    t = torch.from_numpy(x).permute(0, 3, 1, 2).to(_state["device"])
    with torch.no_grad():
        lg = _state["model"](t).squeeze(1).float()
    return {"p_fake": float(torch.sigmoid(lg.mean())), "crops": len(crops), "model": _state["meta"].get("name", _state["meta"]["file"])}
