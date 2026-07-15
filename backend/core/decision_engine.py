"""Forensic Decision Engine (Phase 4).

Takes the list of per-agent outputs and produces the final forensic verdict:

    {
        "verdict": "Authentic" | "Fake" | "Inconclusive",
        "overall_score": float,               # authenticity 0..1
        "manipulation_type": str | None,      # HOW it was faked
        "manipulation_confidence": float,
        "gan_attribution": str | None,        # WHICH generator, best guess
        "gan_confidence": float,
        "reasoning": [str, ...],              # human-readable bullets (feeds Phase 6 LLM)
    }

The manipulation-type and GAN-attribution logic is rule-based over the agent
findings for now. It's structured so a trained classifier head (Phase 8) can
replace `classify_manipulation()` / `attribute_generator()` without touching
callers.
"""
from agents.base import clamp

# Per-agent weight in the final authenticity score.
AGENT_WEIGHTS = {
    "metadata": 0.20,
    "image_forensics": 0.30,
    "audio_forensics": 0.20,
    "security": 0.25,     # C2PA + watermark provenance (Phase 5)
}

# Verdict thresholds on the authenticity score.
AUTHENTIC_THRESHOLD = 0.75
FAKE_THRESHOLD = 0.40


def _find_agent(results, name):
    for r in results:
        if r.get("agent") == name:
            return r
    return None


def _find_check(agent_result, check):
    if not agent_result:
        return None
    for f in agent_result.get("findings", []):
        if f.get("check") == check:
            return f
    return None


def _is_suspicious(finding):
    return finding is not None and finding.get("status") == "suspicious"


def aggregate_score(results):
    """Weighted authenticity average across agents.

    Agents may report confidence=None (e.g. security agent when no provenance
    data exists either way) — those are excluded rather than counted as 0.5.
    """
    total_w = 0.0
    acc = 0.0
    for r in results:
        conf = r.get("confidence", 0.5)
        if conf is None:
            continue
        w = AGENT_WEIGHTS.get(r.get("agent"), 0.25)
        acc += float(conf) * w
        total_w += w
    return acc / total_w if total_w > 0 else 0.5


def verdict_from_score(score):
    if score >= AUTHENTIC_THRESHOLD:
        return "Authentic"
    if score <= FAKE_THRESHOLD:
        return "Fake"
    return "Inconclusive"


def classify_manipulation(results, file_type):
    """Infer HOW the media was manipulated from agent signals.

    Returns (label, confidence, reasons[]). label is None if nothing suspicious.
    """
    reasons = []
    candidates = []  # (label, confidence)

    meta = _find_agent(results, "metadata")
    image = _find_agent(results, "image_forensics")
    audio = _find_agent(results, "audio_forensics")
    security = _find_agent(results, "security")

    # ── Provenance signals (Phase 5) — near-decisive when present ──
    if security:
        wm = _find_check(security, "invisible_watermark")
        if _is_suspicious(wm):
            gen = security.get("watermark_generator", "AI generator")
            candidates.append(("GAN / AI-Generated Image", 0.95))
            reasons.append(f"Invisible watermark identifies the image as {gen} output.")
        c2pa = _find_check(security, "c2pa_manifest")
        if _is_suspicious(c2pa):
            candidates.append(("Tampered After Signing (C2PA validation failed)", 0.9))
            reasons.append("Embedded C2PA content credentials no longer validate — "
                           "the file was modified after it was signed.")

    # ── AI-generated (GAN/diffusion) — deep model + FFT fingerprint on images ──
    if image:
        deep = _find_check(image, "deep_model")
        fft = _find_check(image, "fft")
        ela = _find_check(image, "ela")

        if _is_suspicious(deep):
            conf = 1.0 - (deep.get("score") or 0.5)
            candidates.append(("GAN / AI-Generated Image", clamp(conf)))
            reasons.append(f"Deep classifier flagged synthetic imagery (p={conf:.2f}).")

        if _is_suspicious(fft):
            conf = 1.0 - (fft.get("score") or 0.5)
            candidates.append(("GAN / AI-Generated Image", clamp(conf * 0.8)))
            reasons.append("Frequency-domain fingerprint consistent with generative models.")

        # Localized ELA anomalies point to splicing / copy-move rather than full synthesis.
        if _is_suspicious(ela):
            conf = 1.0 - (ela.get("score") or 0.5)
            candidates.append(("Spliced / Copy-Move Forgery", clamp(conf)))
            reasons.append("Error-level analysis shows inconsistent compression regions (splice).")

    # ── Editing / retouching — metadata software tags ──
    if meta:
        sw = _find_check(meta, "software")
        if _is_suspicious(sw):
            note = (sw.get("note") or "").lower()
            if any(g in note for g in ("stable diffusion", "midjourney", "dall", "diffusion", "generated", "gan")):
                candidates.append(("GAN / AI-Generated Image", 0.85))
                reasons.append("Generator software recorded in metadata.")
            else:
                candidates.append(("Digitally Retouched", 0.55))
                reasons.append("Photo-editing software recorded in metadata.")

    # ── Audio voice clone ──
    if audio:
        spec = _find_check(audio, "spectral")
        deep = _find_check(audio, "deep_model")
        if _is_suspicious(deep):
            conf = 1.0 - (deep.get("score") or 0.5)
            candidates.append(("Voice Clone / Synthetic Speech", clamp(conf)))
            reasons.append("Synthetic-speech classifier flagged the audio track.")
        elif _is_suspicious(spec):
            conf = 1.0 - (spec.get("score") or 0.5)
            candidates.append(("Voice Clone / Synthetic Speech", clamp(conf * 0.8)))
            reasons.append("Spectral profile atypical for natural human speech.")

    if not candidates:
        return None, 0.0, reasons

    # Pick the highest-confidence manipulation hypothesis.
    candidates.sort(key=lambda c: c[1], reverse=True)
    label, conf = candidates[0]
    return label, round(float(conf), 4), reasons


def attribute_generator(results, manipulation_type):
    """Best-guess of WHICH generator produced synthetic content.

    Rule-based placeholder until a trained GAN-fingerprint classifier lands
    (Phase 8). Returns (generator, confidence).
    """
    if not manipulation_type or "GAN" not in manipulation_type and "AI-Generated" not in manipulation_type:
        return None, 0.0

    # Watermark hit names the generator outright (Phase 5) — highest confidence.
    security = _find_agent(results, "security")
    if security and security.get("watermark_generator"):
        return security["watermark_generator"], 0.9

    image = _find_agent(results, "image_forensics")
    if image:
        # If the deep model exposed raw predictions we could map labels here.
        preds = image.get("deep_predictions")
        fft = _find_check(image, "fft")
        # High-frequency energy leans toward diffusion models; lower toward GANs.
        if fft and fft.get("score") is not None:
            hf_auth = fft["score"]
            if hf_auth < 0.4:
                return "Diffusion model (e.g. Stable Diffusion / Midjourney)", 0.45
            return "GAN family (e.g. StyleGAN)", 0.4

    return "Unknown generator", 0.2


def decide(results, file_type):
    score = aggregate_score(results)
    verdict = verdict_from_score(score)

    # C2PA fast-track (Phase 5.1): a cryptographically valid manifest is
    # authoritative provenance — override the statistical verdict.
    security = _find_agent(results, "security")
    fast_track = bool(security and security.get("fast_track_authentic"))
    if fast_track:
        verdict = "Authentic"
        score = max(score, 0.9)

    manip_type, manip_conf, reasons = classify_manipulation(results, file_type)
    gen, gen_conf = attribute_generator(results, manip_type)

    # If the score says authentic but a manipulation was hypothesized weakly,
    # keep manipulation_type only when the verdict isn't clean-authentic.
    if verdict == "Authentic" and manip_conf < 0.5:
        manip_type, manip_conf = None, 0.0
        gen, gen_conf = None, 0.0

    summary_reasons = [f"Overall authenticity score {score:.2f} → {verdict}."]
    if fast_track:
        issuer = (security.get("c2pa") or {}).get("issuer", "a trusted issuer")
        summary_reasons.append(
            f"Fast-tracked Authentic: valid C2PA content credentials signed by {issuer}.")
    summary_reasons += reasons

    return {
        "verdict": verdict,
        "overall_score": round(float(score), 4),
        "manipulation_type": manip_type,
        "manipulation_confidence": manip_conf,
        "gan_attribution": gen,
        "gan_confidence": gen_conf,
        "reasoning": summary_reasons,
    }
