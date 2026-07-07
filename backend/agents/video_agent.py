"""Video Forensics Agent.

Samples frames from the video and runs per-frame image forensics, then looks
for temporal anomalies that betray deepfakes:

  - Per-frame authenticity scores (reuses the image agent's ELA+FFT+deep stack
    conceptually, but computes lightweight FFT per sampled frame for speed)
  - Duplicate / near-duplicate frames (perceptual hash) — splice / loop artifact
  - Inter-frame difference spikes — abrupt scene/blending changes

Output includes `frame_scores` (timestamp -> authenticity) so the frontend
(Phase 6) can draw the Video Confidence Timeline and highlight tampered
segments in red.
"""
import os

from .base import AgentOutput, Finding, clamp

AGENT_NAME = "video_forensics"

MAX_SAMPLES = int(os.getenv("VIDEO_MAX_SAMPLES", "40"))


def _fft_auth_for_frame(gray):
    import numpy as np
    arr = gray.astype("float32")
    f = np.fft.fftshift(np.fft.fft2(arr))
    mag = np.abs(f)
    h, w = mag.shape
    cy, cx = h // 2, w // 2
    r = min(h, w) // 8
    yy, xx = np.ogrid[:h, :w]
    low_mask = (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r
    low = mag[low_mask].sum()
    high = mag[~low_mask].sum()
    total = low + high
    if total <= 0:
        return 0.5
    hf_ratio = high / total
    return clamp(1.0 - clamp((hf_ratio - 0.75) / 0.20))


def run(file_path: str) -> dict:
    out = AgentOutput(agent=AGENT_NAME)
    if not os.path.exists(file_path):
        out.add(Finding("file_exists", "error", "File not found"))
        return out.dict()

    try:
        import cv2
        import numpy as np
    except Exception:
        out.add(Finding("opencv", "skipped", "OpenCV not installed — video analysis unavailable"))
        out.confidence = 0.5
        return out.dict()

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        out.add(Finding("open", "error", "Could not open video"))
        out.confidence = 0.5
        return out.dict()

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total_frames <= 0:
        total_frames = MAX_SAMPLES
    step = max(1, total_frames // MAX_SAMPLES)

    frame_scores = []       # [{"t": seconds, "score": auth}]
    prev_gray = None
    prev_hash = None
    duplicate_count = 0
    diff_spike_count = 0
    idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (256, 256))

            auth = _fft_auth_for_frame(small)
            t = round(idx / fps, 2)
            frame_scores.append({"t": t, "score": round(float(auth), 4)})

            # perceptual hash (avg-hash) for duplicate detection
            tiny = cv2.resize(gray, (8, 8))
            phash = (tiny > tiny.mean()).flatten()
            if prev_hash is not None:
                hamming = int(np.count_nonzero(phash != prev_hash))
                if hamming <= 3:
                    duplicate_count += 1
            prev_hash = phash

            # inter-frame difference spike
            if prev_gray is not None:
                d = float(np.mean(cv2.absdiff(small, prev_gray)))
                if d > 40.0:
                    diff_spike_count += 1
            prev_gray = small
        idx += 1

    cap.release()

    if not frame_scores:
        out.add(Finding("frames", "error", "No frames could be sampled"))
        out.confidence = 0.5
        return out.dict()

    avg_auth = sum(f["score"] for f in frame_scores) / len(frame_scores)
    flagged = [f["t"] for f in frame_scores if f["score"] < 0.45]

    out.add(Finding("frame_analysis", "ok" if avg_auth >= 0.5 else "suspicious",
                    f"Sampled {len(frame_scores)} frames, avg authenticity {avg_auth:.3f}",
                    score=avg_auth))

    if duplicate_count:
        out.add(Finding("duplicate_frames", "suspicious",
                        f"{duplicate_count} near-duplicate frame(s) detected"))
    else:
        out.add(Finding("duplicate_frames", "ok", "No duplicate frames"))

    if diff_spike_count:
        out.add(Finding("scene_discontinuity", "suspicious",
                        f"{diff_spike_count} abrupt inter-frame change(s)"))
    else:
        out.add(Finding("scene_discontinuity", "ok", "Smooth frame transitions"))

    # Penalize authenticity slightly for structural anomalies.
    penalty = clamp(0.03 * duplicate_count + 0.02 * diff_spike_count, 0.0, 0.3)
    out.confidence = clamp(avg_auth - penalty)

    out.extra["frame_scores"] = frame_scores
    out.extra["flagged_timestamps"] = flagged
    out.extra["fps"] = round(float(fps), 2)

    # Phase 6 XAI — merge low-score frames into contiguous tampered segments
    # for the confidence timeline (red highlights).
    try:
        from core.xai import flagged_segments_from_scores
        out.extra["flagged_segments"] = flagged_segments_from_scores(frame_scores)
    except Exception:
        out.extra["flagged_segments"] = []

    return out.dict()
