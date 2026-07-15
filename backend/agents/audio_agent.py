"""Audio Forensics Agent.

Layers, each degrades gracefully:

  1. Spectral analysis (librosa) — voice clones / TTS leave tell-tale signs:
     unnaturally flat spectral variance, reduced high-frequency detail,
     over-smooth pitch contours. Always available if librosa is installed.
  2. Deep synthetic-speech classifier (HuggingFace Wav2Vec2) — optional,
     lazily loaded. Skipped if torch/transformers unavailable.

Output includes `flagged_segments` (time ranges) for the UI.
"""
import os

from .base import AgentOutput, Finding, clamp

AGENT_NAME = "audio_forensics"

_DEEP_MODEL = None
_DEEP_LOAD_FAILED = False
_DEEP_LOAD_ERROR = None
# A HF audio-classification model for spoof/deepfake speech. Configurable.
AUDIO_MODEL_ID = os.getenv("AUDIO_MODEL_ID", "MelodyMachine/Deepfake-audio-detection-V2")


def _spectral_analysis(file_path: str):
    try:
        import numpy as np
        import librosa

        y, sr = librosa.load(file_path, sr=16000, mono=True, duration=60)
        if y.size == 0:
            return None

        # Spectral centroid variance — synthetic speech is often over-smooth.
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        centroid_var = float(np.var(centroid)) if centroid.size else 0.0

        # High-frequency rolloff — vocoders often cut/attenuate highs.
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.95)[0]
        mean_rolloff = float(np.mean(rolloff)) if rolloff.size else 0.0

        # Flatness — noise-like vs tonal; TTS can be unnaturally flat/peaky.
        flatness = librosa.feature.spectral_flatness(y=y)[0]
        mean_flatness = float(np.mean(flatness)) if flatness.size else 0.0

        # Heuristic scoring toward authenticity.
        # Natural speech has healthy centroid variance and rolloff near Nyquist.
        var_auth = clamp(centroid_var / 5e5)                 # more variance => natural
        rolloff_auth = clamp(mean_rolloff / (sr / 2))        # closer to Nyquist => natural
        flat_auth = clamp(1.0 - abs(mean_flatness - 0.15) / 0.3)

        auth = clamp((var_auth + rolloff_auth + flat_auth) / 3.0)
        return {
            "centroid_var": centroid_var,
            "mean_rolloff": mean_rolloff,
            "mean_flatness": mean_flatness,
            "authenticity": auth,
            "duration": float(len(y) / sr),
        }
    except Exception:
        return None


def _load_deep_model():
    global _DEEP_MODEL, _DEEP_LOAD_FAILED, _DEEP_LOAD_ERROR
    if _DEEP_MODEL is not None or _DEEP_LOAD_FAILED:
        return _DEEP_MODEL
    try:
        from transformers import pipeline
        _DEEP_MODEL = pipeline("audio-classification", model=AUDIO_MODEL_ID)
    except Exception as exc:
        _DEEP_LOAD_FAILED = True
        _DEEP_MODEL = None
        _DEEP_LOAD_ERROR = f"{type(exc).__name__}: {exc}"
    return _DEEP_MODEL


def _deep_score(file_path: str):
    """Returns (authenticity, preds, error_note)."""
    model = _load_deep_model()
    if model is None:
        return None, None, _DEEP_LOAD_ERROR or "torch/transformers not installed"
    try:
        # Decode with librosa instead of passing the filename — the HF pipeline
        # shells out to ffmpeg for filenames, which isn't available on this box.
        import librosa
        sr = int(getattr(model.feature_extractor, "sampling_rate", 16000) or 16000)
        y, _ = librosa.load(file_path, sr=sr, mono=True, duration=60)
        if y.size == 0:
            return None, None, "no decodable audio in file"

        preds = model({"raw": y, "sampling_rate": sr})
        fake_p = 0.0
        for p in preds:
            label = p["label"].lower()
            if any(k in label for k in ("fake", "spoof", "synthetic", "clone", "ai", "generated")):
                fake_p = max(fake_p, p["score"])
        return clamp(1.0 - fake_p), preds, None
    except Exception as exc:
        return None, None, f"{type(exc).__name__}: {exc}"


def run(file_path: str) -> dict:
    out = AgentOutput(agent=AGENT_NAME)
    if not os.path.exists(file_path):
        out.add(Finding("file_exists", "error", "File not found"))
        return out.dict()

    signals: list[float] = []

    spec = _spectral_analysis(file_path)
    if spec is not None:
        auth = spec["authenticity"]
        status = "suspicious" if auth < 0.5 else "ok"
        out.add(Finding("spectral", status,
                        f"Centroid var {spec['centroid_var']:.0f}, rolloff {spec['mean_rolloff']:.0f}Hz, "
                        f"flatness {spec['mean_flatness']:.3f}", score=auth))
        signals.append(auth)
        out.extra["spectral"] = spec
    else:
        out.add(Finding("spectral", "skipped", "librosa not installed or no audio track"))

    deep_auth, preds, deep_err = _deep_score(file_path)
    if deep_auth is not None:
        status = "suspicious" if deep_auth < 0.5 else "ok"
        out.add(Finding("deep_model", status,
                        f"Synthetic-speech classifier authenticity {deep_auth:.3f}", score=deep_auth))
        signals.append(deep_auth)
        signals.append(deep_auth)  # weight deep model
        out.extra["deep_predictions"] = preds
    else:
        out.add(Finding("deep_model", "skipped", f"Deep audio classifier unavailable: {deep_err}"))

    out.confidence = clamp(sum(signals) / len(signals)) if signals else 0.5
    out.extra.setdefault("flagged_segments", [])
    return out.dict()
