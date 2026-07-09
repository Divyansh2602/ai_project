"""Phase 6 — LLM forensic report summary.

Turns the structured decision + agent findings into a short, human-readable,
court-style narrative for the report / PDF. Runs against a LOCAL Ollama server
(free, offline — the evidence never leaves the machine).

Fully env-gated and fail-safe: if disabled, Ollama is unreachable, or anything
errors, `generate_summary()` returns None and the pipeline continues unaffected.

Env:
  ENABLE_LLM_SUMMARY   "1"/"true" to enable (default off)
  OLLAMA_URL           default http://localhost:11434
  OLLAMA_MODEL         default llama3.1:8b
"""
import os
import logging

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return os.getenv("ENABLE_LLM_SUMMARY", "").lower() in ("1", "true", "yes", "on")


def _build_prompt(decision: dict, agent_results: list[dict], evidence: dict) -> str:
    lines = [
        "You are a digital-forensics analyst writing a concise, court-admissible "
        "summary of an automated media-authenticity analysis. Be factual and neutral. "
        "Do not invent findings beyond those provided. 120-180 words, no headings, "
        "no markdown, plain prose.",
        "",
        f"File: {evidence.get('original_filename')} ({evidence.get('file_type')})",
        f"SHA-256: {evidence.get('file_hash')}",
        f"Verdict: {decision.get('verdict')} "
        f"(authenticity score {decision.get('overall_score')})",
    ]
    if decision.get("manipulation_type"):
        lines.append(
            f"Suspected manipulation: {decision['manipulation_type']} "
            f"(confidence {decision.get('manipulation_confidence')})"
        )
    if decision.get("gan_attribution"):
        lines.append(f"Attributed generator: {decision['gan_attribution']}")

    lines.append("")
    lines.append("Per-agent authenticity confidence (0=fake, 1=authentic):")
    for r in agent_results:
        conf = r.get("confidence")
        conf_s = f"{conf:.2f}" if isinstance(conf, (int, float)) else "n/a"
        lines.append(f"  - {r.get('agent')}: {conf_s}")

    reasoning = decision.get("reasoning") or []
    if reasoning:
        lines.append("")
        lines.append("Key findings:")
        for r in reasoning:
            lines.append(f"  - {r}")

    lines.append("")
    lines.append("Write the summary paragraph now:")
    return "\n".join(lines)


def generate_summary(decision: dict, agent_results: list[dict], evidence: dict) -> str | None:
    """Return an LLM-written summary paragraph, or None if unavailable/disabled."""
    if not _enabled():
        return None

    url = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    prompt = _build_prompt(decision, agent_results, evidence)

    try:
        import requests
        resp = requests.post(
            f"{url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 320},
            },
            timeout=120,
        )
        resp.raise_for_status()
        text = (resp.json().get("response") or "").strip()
        return text or None
    except Exception as exc:
        logger.warning("LLM summary generation failed (%s) — continuing without it", exc)
        return None
