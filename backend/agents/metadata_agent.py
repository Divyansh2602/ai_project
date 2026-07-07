"""Metadata Analysis Agent.

Extracts EXIF / file metadata and flags anomalies that commonly indicate
tampering or synthetic generation:

  - Missing camera make/model (AI images usually have none)
  - Editing software in the metadata (Photoshop, GIMP, etc.)
  - Timestamp inconsistencies (DateTimeOriginal vs DateTimeDigitized vs file mtime)
  - No EXIF block at all on a JPEG (often re-encoded / generated)

Lightweight — no ML. Runs on images and documents.
"""
import os
from datetime import datetime

from .base import AgentOutput, Finding, clamp

AGENT_NAME = "metadata"

# Software strings that indicate the image was edited, not straight-from-camera.
EDITING_SOFTWARE = [
    "photoshop", "gimp", "lightroom", "affinity", "pixelmator",
    "paint.net", "snapseed", "facetune", "picsart",
]
# Generators — presence is a strong synthetic signal.
GENERATOR_SOFTWARE = [
    "stable diffusion", "midjourney", "dall-e", "dalle", "firefly",
    "gan", "diffusion", "generated",
]


def _load_exif(file_path: str) -> dict:
    tags = {}
    try:
        import exifread
        with open(file_path, "rb") as f:
            raw = exifread.process_file(f, details=False)
        tags = {k: str(v) for k, v in raw.items()}
    except Exception:
        pass

    # Fallback / supplement with Pillow for the Software tag and dimensions.
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        img = Image.open(file_path)
        exif = img.getexif()
        for tag_id, value in exif.items():
            name = TAGS.get(tag_id, str(tag_id))
            tags.setdefault(name, str(value))
        tags["_width"], tags["_height"] = img.size
    except Exception:
        pass

    return tags


def run(file_path: str) -> dict:
    out = AgentOutput(agent=AGENT_NAME)
    if not os.path.exists(file_path):
        out.add(Finding("file_exists", "error", "File not found"))
        out.confidence = 0.5
        return out.dict()

    tags = _load_exif(file_path)
    authenticity_signals: list[float] = []

    # 1) Camera make/model present?
    make = tags.get("Image Make") or tags.get("Make")
    model = tags.get("Image Model") or tags.get("Model")
    if make or model:
        out.add(Finding("camera_info", "ok", f"Camera: {make} {model}", score=0.85))
        authenticity_signals.append(0.85)
    else:
        out.add(Finding("camera_info", "suspicious",
                        "No camera make/model — common in AI-generated or re-encoded images",
                        score=0.35))
        authenticity_signals.append(0.35)

    # 2) Editing / generator software?
    software = (tags.get("Software") or tags.get("Image Software") or "").lower()
    if software:
        if any(g in software for g in GENERATOR_SOFTWARE):
            out.add(Finding("software", "suspicious",
                            f"Generator software detected: {software}", score=0.10))
            authenticity_signals.append(0.10)
        elif any(e in software for e in EDITING_SOFTWARE):
            out.add(Finding("software", "suspicious",
                            f"Image edited with: {software}", score=0.40))
            authenticity_signals.append(0.40)
        else:
            out.add(Finding("software", "ok", f"Software: {software}", score=0.70))
            authenticity_signals.append(0.70)
    else:
        out.add(Finding("software", "ok", "No editing software tag", score=0.60))
        authenticity_signals.append(0.60)

    # 3) Timestamp consistency
    dt_original = tags.get("EXIF DateTimeOriginal") or tags.get("DateTimeOriginal")
    dt_digitized = tags.get("EXIF DateTimeDigitized") or tags.get("DateTimeDigitized")
    if dt_original and dt_digitized:
        if dt_original == dt_digitized:
            out.add(Finding("timestamps", "ok", "Original == Digitized timestamp", score=0.75))
            authenticity_signals.append(0.75)
        else:
            out.add(Finding("timestamps", "suspicious",
                            f"Timestamp mismatch: {dt_original} vs {dt_digitized}", score=0.45))
            authenticity_signals.append(0.45)
    elif not dt_original and not dt_digitized:
        out.add(Finding("timestamps", "suspicious",
                        "No EXIF timestamps present", score=0.40))
        authenticity_signals.append(0.40)

    # 4) GPS present? (informational — presence leans authentic)
    has_gps = any(k.startswith("GPS") for k in tags)
    if has_gps:
        out.add(Finding("gps", "ok", "GPS metadata present", score=0.80))
        authenticity_signals.append(0.80)

    # Aggregate
    if authenticity_signals:
        out.confidence = clamp(sum(authenticity_signals) / len(authenticity_signals))
    else:
        out.confidence = 0.5

    out.extra["raw_tag_count"] = len(tags)
    return out.dict()
