"""Explainability layer (Phase 6).

Three explainers, each degrades gracefully and never raises out of this module:

  1. Grad-CAM on the image agent's deep deepfake classifier — WHERE in the
     image the model looked when it called it fake. Works for both CNN
     (EfficientNet/ResNet: last Conv2d) and ViT backbones (last encoder block
     layernorm + token→grid reshape). Falls back to a model-agnostic occlusion
     sensitivity map if Grad-CAM can't handle the architecture.
  2. Shapley feature attribution for the metadata agent — its confidence is an
     unweighted mean of per-check scores, i.e. an additive model, for which
     Shapley values have the exact closed form (score_i - baseline) / n.
     No `shap` package needed; the values are exact, not sampled.
  3. Chart renderers (matplotlib/Agg) for the legal PDF: video confidence
     timeline with tampered segments in red, and a feature-importance bar chart.
"""
import logging
import os

logger = logging.getLogger(__name__)

HEATMAP_DIR = os.getenv("HEATMAP_DIR", "uploads/heatmaps")

# ── 1. Grad-CAM ────────────────────────────────────────────────────────────


def _fake_class_index(model) -> int:
    """Index of the 'fake' class in the classifier head (mirrors image_agent)."""
    id2label = getattr(model.config, "id2label", {}) or {}
    for idx, label in id2label.items():
        if any(k in str(label).lower() for k in ("fake", "deepfake", "ai", "synthetic", "generated")):
            return int(idx)
    return 0


def _vit_reshape_transform(tensor):
    """[B, 1+N, C] token sequence → [B, C, H, W] grid (drops the CLS token)."""
    import math
    n = tensor.size(1) - 1
    side = int(math.sqrt(n))
    result = tensor[:, 1:side * side + 1, :].reshape(tensor.size(0), side, side, tensor.size(2))
    return result.permute(0, 3, 1, 2)


def _gradcam_grayscale(hf_pipeline, pil_image):
    """Run pytorch-grad-cam against the HF pipeline's model. Returns HxW float 0..1."""
    import torch
    from pytorch_grad_cam import GradCAM
    from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

    model = hf_pipeline.model
    processor = hf_pipeline.image_processor
    inputs = processor(images=pil_image, return_tensors="pt")
    pixel_values = inputs["pixel_values"].to(model.device)

    class _LogitsOnly(torch.nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner

        def forward(self, x):
            return self.inner(pixel_values=x).logits

    wrapped = _LogitsOnly(model)

    # Pick target layers by architecture. Located by module-name suffix so it
    # survives transformers refactors (v4: vit.encoder.layer[i], v5: vit.layers[i]).
    target_layers, reshape = None, None
    ln_before = [m for n, m in model.named_modules() if n.endswith("layernorm_before")]
    if ln_before:  # ViT-style transformer blocks
        target_layers = [ln_before[-1]]
        reshape = _vit_reshape_transform
    else:  # CNN: last Conv2d anywhere in the graph
        convs = [m for m in model.modules() if isinstance(m, torch.nn.Conv2d)]
        if convs:
            target_layers = [convs[-1]]
    if not target_layers:
        raise RuntimeError("no Grad-CAM target layer found for this architecture")

    targets = [ClassifierOutputTarget(_fake_class_index(model))]
    with GradCAM(model=wrapped, target_layers=target_layers, reshape_transform=reshape) as cam:
        grayscale = cam(input_tensor=pixel_values, targets=targets)[0]  # HxW in 0..1
    return grayscale


def _occlusion_grayscale(hf_pipeline, pil_image, grid=8):
    """Model-agnostic fallback: how much does hiding each cell drop P(fake)?"""
    import numpy as np
    import torch
    from PIL import Image

    model = hf_pipeline.model
    processor = hf_pipeline.image_processor
    fake_idx = _fake_class_index(model)

    def p_fake(img):
        inputs = processor(images=img, return_tensors="pt")
        with torch.no_grad():
            logits = model(pixel_values=inputs["pixel_values"].to(model.device)).logits
        return float(torch.softmax(logits, dim=-1)[0, fake_idx])

    base = p_fake(pil_image)
    arr = np.asarray(pil_image.convert("RGB"))
    h, w = arr.shape[:2]
    mean_color = arr.reshape(-1, 3).mean(axis=0).astype("uint8")
    heat = np.zeros((grid, grid), dtype="float32")

    for gy in range(grid):
        for gx in range(grid):
            y0, y1 = h * gy // grid, h * (gy + 1) // grid
            x0, x1 = w * gx // grid, w * (gx + 1) // grid
            occluded = arr.copy()
            occluded[y0:y1, x0:x1] = mean_color
            # Importance = how much this region contributed to the fake call.
            heat[gy, gx] = max(0.0, base - p_fake(Image.fromarray(occluded)))

    if heat.max() > 0:
        heat /= heat.max()
    return np.asarray(Image.fromarray((heat * 255).astype("uint8")).resize((w, h))) / 255.0


def gradcam_heatmap(hf_pipeline, file_path: str) -> dict | None:
    """Generate a Grad-CAM overlay PNG for the deep model's 'fake' decision.

    Returns {"path": ..., "method": "gradcam"|"occlusion"} or None if neither
    explainer could run. Never raises.
    """
    method = None
    try:
        import numpy as np
        from PIL import Image
        from pytorch_grad_cam.utils.image import show_cam_on_image

        pil_image = Image.open(file_path).convert("RGB")
        try:
            grayscale = _gradcam_grayscale(hf_pipeline, pil_image)
            method = "gradcam"
        except Exception:
            logger.info("Grad-CAM failed for %s — falling back to occlusion map",
                        file_path, exc_info=True)
            grayscale = _occlusion_grayscale(hf_pipeline, pil_image)
            method = "occlusion"

        # Overlay on the (resized-to-cam) original.
        cam_h, cam_w = grayscale.shape[:2]
        rgb = np.asarray(pil_image.resize((cam_w, cam_h)), dtype=np.float32) / 255.0
        overlay = show_cam_on_image(rgb, grayscale.astype(np.float32), use_rgb=True)

        os.makedirs(HEATMAP_DIR, exist_ok=True)
        base = os.path.splitext(os.path.basename(file_path))[0]
        out_path = os.path.join(HEATMAP_DIR, f"{base}_gradcam.png")
        Image.fromarray(overlay).save(out_path)
        return {"path": out_path, "method": method}
    except Exception:
        logger.warning("XAI heatmap generation failed for %s", file_path, exc_info=True)
        return None


# ── 2. Shapley attribution for the metadata agent ──────────────────────────

BASELINE = 0.5  # neutral authenticity — the agent's score with no evidence


def shapley_attribution(findings: list[dict]) -> list[dict]:
    """Exact Shapley values for the metadata agent's additive scoring.

    confidence = mean(score_i), so each check's Shapley contribution to
    (confidence - 0.5) is exactly (score_i - 0.5) / n. Positive = pushed
    toward authentic, negative = pushed toward fake.
    """
    scored = [f for f in findings if f.get("score") is not None]
    n = len(scored)
    if n == 0:
        return []
    rows = []
    for f in scored:
        contrib = (float(f["score"]) - BASELINE) / n
        rows.append({
            "feature": f["check"],
            "note": f.get("note", ""),
            "score": float(f["score"]),
            "contribution": round(contrib, 4),
            "direction": "authentic" if contrib >= 0 else "fake",
        })
    rows.sort(key=lambda r: abs(r["contribution"]), reverse=True)
    return rows


# ── 3. Chart renderers for the PDF ──────────────────────────────────────────


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def render_timeline_chart(frame_scores: list[dict], flagged_segments: list[dict],
                          out_path: str) -> str | None:
    """Video confidence timeline PNG: authenticity vs time, tampering in red."""
    try:
        plt = _plt()
        ts = [f["t"] for f in frame_scores]
        scores = [f["score"] for f in frame_scores]

        fig, ax = plt.subplots(figsize=(7.2, 2.6), dpi=150)
        ax.plot(ts, scores, color="#1f6feb", linewidth=1.6)
        ax.axhline(0.45, color="#999999", linewidth=0.8, linestyle="--")
        for seg in flagged_segments:
            ax.axvspan(seg["start"], seg["end"], color="#d73a49", alpha=0.25)
        ax.set_xlabel("time (s)")
        ax.set_ylabel("authenticity")
        ax.set_ylim(0, 1)
        ax.set_title("Per-frame authenticity (flagged segments in red)", fontsize=9)
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        return out_path
    except Exception:
        logger.warning("timeline chart failed", exc_info=True)
        return None


def render_importance_chart(attribution: list[dict], out_path: str) -> str | None:
    """Horizontal bar chart of metadata Shapley contributions."""
    try:
        plt = _plt()
        rows = attribution[:8][::-1]  # top 8, biggest at top
        labels = [r["feature"] for r in rows]
        values = [r["contribution"] for r in rows]
        colors = ["#2da44e" if v >= 0 else "#d73a49" for v in values]

        fig, ax = plt.subplots(figsize=(6.4, 0.5 * max(2, len(rows)) + 0.9), dpi=150)
        ax.barh(labels, values, color=colors)
        ax.axvline(0, color="#333333", linewidth=0.8)
        ax.set_xlabel("Shapley contribution to authenticity")
        ax.set_title("Metadata feature importance", fontsize=9)
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        return out_path
    except Exception:
        logger.warning("importance chart failed", exc_info=True)
        return None


def flagged_segments_from_scores(frame_scores: list[dict],
                                 threshold: float = 0.45) -> list[dict]:
    """Merge consecutive low-authenticity frames into contiguous segments."""
    segments = []
    current = None
    for f in frame_scores:
        if f["score"] < threshold:
            if current is None:
                current = {"start": f["t"], "end": f["t"], "min_score": f["score"]}
            else:
                current["end"] = f["t"]
                current["min_score"] = min(current["min_score"], f["score"])
        elif current is not None:
            segments.append(current)
            current = None
    if current is not None:
        segments.append(current)
    return segments
