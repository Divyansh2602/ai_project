"""Image / Artifact Forensics Agent.

Three layers, each degrades gracefully:

  1. ELA (Error Level Analysis) — resave the JPEG at a known quality and diff.
     Spliced / pasted regions compress differently and light up. Always available.
  2. FFT high-frequency energy — GAN/diffusion images have characteristic
     frequency-domain fingerprints. Always available (numpy).
  3. Deep deepfake classifier (HuggingFace / EfficientNet) — optional, loaded
     lazily. If torch/transformers aren't installed, this layer is skipped.

Produces an ELA heatmap PNG saved next to the upload so the frontend
(Phase 7) can overlay it.
"""
import os

from .base import AgentOutput, Finding, clamp

AGENT_NAME = "image_forensics"

HEATMAP_DIR = os.getenv("HEATMAP_DIR", "uploads/heatmaps")

# Lazy singletons for the deep model so we load weights only once per worker.
_DEEP_MODEL = None
_DEEP_LOAD_FAILED = False
# Set to a HF image-classification model id to enable layer 3. Kept configurable
# so we can swap in a fine-tuned deepfake checkpoint without code changes.
DEEPFAKE_MODEL_ID = os.getenv("DEEPFAKE_MODEL_ID", "prithivMLmods/Deep-Fake-Detector-v2-Model")


def _ela(file_path: str, quality: int = 90):
    """Return (mean_error, heatmap_path) or (None, None) on failure."""
    try:
        import numpy as np
        from PIL import Image, ImageChops

        original = Image.open(file_path).convert("RGB")

        os.makedirs(HEATMAP_DIR, exist_ok=True)
        base = os.path.splitext(os.path.basename(file_path))[0]
        resaved = os.path.join(HEATMAP_DIR, f"{base}_ela_tmp.jpg")
        original.save(resaved, "JPEG", quality=quality)

        recompressed = Image.open(resaved)
        diff = ImageChops.difference(original, recompressed)

        extrema = diff.getextrema()
        max_diff = max([e[1] for e in extrema]) or 1
        scale = 255.0 / max_diff

        arr = np.asarray(diff, dtype=np.float32) * scale
        mean_error = float(arr.mean())

        # Save an amplified heatmap for the UI.
        heatmap = np.clip(arr, 0, 255).astype("uint8")
        heatmap_path = os.path.join(HEATMAP_DIR, f"{base}_ela.png")
        Image.fromarray(heatmap).save(heatmap_path)

        try:
            os.remove(resaved)
        except OSError:
            pass

        return mean_error, heatmap_path
    except Exception:
        return None, None


def _fft_high_freq_ratio(file_path: str):
    """Ratio of high-frequency energy. GAN images tend to run high."""
    try:
        import numpy as np
        from PIL import Image

        img = Image.open(file_path).convert("L").resize((256, 256))
        arr = np.asarray(img, dtype=np.float32)

        f = np.fft.fftshift(np.fft.fft2(arr))
        mag = np.abs(f)

        h, w = mag.shape
        cy, cx = h // 2, w // 2
        r = 32  # low-frequency radius
        yy, xx = np.ogrid[:h, :w]
        low_mask = (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r

        low_energy = mag[low_mask].sum()
        high_energy = mag[~low_mask].sum()
        total = low_energy + high_energy
        return float(high_energy / total) if total > 0 else None
    except Exception:
        return None


def _load_deep_model():
    global _DEEP_MODEL, _DEEP_LOAD_FAILED
    if _DEEP_MODEL is not None or _DEEP_LOAD_FAILED:
        return _DEEP_MODEL
    try:
        from transformers import pipeline
        _DEEP_MODEL = pipeline("image-classification", model=DEEPFAKE_MODEL_ID)
    except Exception:
        _DEEP_LOAD_FAILED = True
        _DEEP_MODEL = None
    return _DEEP_MODEL


def _deep_score(file_path: str):
    """Return authenticity 0..1 from the deep classifier, or None if unavailable."""
    model = _load_deep_model()
    if model is None:
        return None, None
    try:
        from PIL import Image
        preds = model(Image.open(file_path).convert("RGB"))
        # Normalize: find the "fake"-ish label probability.
        fake_p = 0.0
        for p in preds:
            label = p["label"].lower()
            if any(k in label for k in ("fake", "deepfake", "ai", "synthetic", "generated")):
                fake_p = max(fake_p, p["score"])
        return clamp(1.0 - fake_p), preds
    except Exception:
        return None, None


def run(file_path: str) -> dict:
    out = AgentOutput(agent=AGENT_NAME)
    if not os.path.exists(file_path):
        out.add(Finding("file_exists", "error", "File not found"))
        return out.dict()

    signals: list[float] = []

    # Layer 1 — ELA
    mean_error, heatmap_path = _ela(file_path)
    if mean_error is not None:
        # Higher ELA error => more likely edited. Map ~[0,30]+ to authenticity.
        ela_auth = clamp(1.0 - (mean_error / 30.0))
        status = "suspicious" if ela_auth < 0.5 else "ok"
        out.add(Finding("ela", status,
                        f"Mean error level {mean_error:.2f} (heatmap saved)", score=ela_auth))
        signals.append(ela_auth)
        out.heatmap_path = heatmap_path
    else:
        out.add(Finding("ela", "skipped", "ELA could not run on this file"))

    # Layer 2 — FFT
    hf_ratio = _fft_high_freq_ratio(file_path)
    if hf_ratio is not None:
        # Empirically, natural photos ~0.55–0.75; GAN images push higher.
        fft_auth = clamp(1.0 - clamp((hf_ratio - 0.75) / 0.20))
        status = "suspicious" if fft_auth < 0.5 else "ok"
        out.add(Finding("fft", status,
                        f"High-frequency energy ratio {hf_ratio:.3f}", score=fft_auth))
        signals.append(fft_auth)
    else:
        out.add(Finding("fft", "skipped", "FFT could not run"))

    # Layer 3 — deep model (optional)
    deep_auth, preds = _deep_score(file_path)
    if deep_auth is not None:
        status = "suspicious" if deep_auth < 0.5 else "ok"
        out.add(Finding("deep_model", status,
                        f"Deepfake classifier authenticity {deep_auth:.3f}", score=deep_auth))
        # Weight the deep model heavily when present.
        signals.append(deep_auth)
        signals.append(deep_auth)
        out.extra["deep_predictions"] = preds
    else:
        out.add(Finding("deep_model", "skipped",
                        "Deep classifier not loaded (install torch+transformers or set DEEPFAKE_MODEL_ID)"))

    out.confidence = clamp(sum(signals) / len(signals)) if signals else 0.5
    return out.dict()
