"""Common interface for all forensic agents.

Every agent takes a file path and returns a normalized dict:

    {
        "agent": "<name>",
        "confidence": float,      # 0.0 = definitely fake, 1.0 = definitely authentic
        "findings": [ {check, status, note, ...}, ... ],
        ...agent-specific extras (heatmap_path, frame_scores, flagged_segments)
    }

Confidence semantics are consistent across all agents so the decision engine
(Phase 4) can weight-average them: HIGHER = more authentic.
"""
from dataclasses import dataclass, field, asdict


@dataclass
class Finding:
    check: str
    status: str            # "ok" | "suspicious" | "error" | "skipped"
    note: str = ""
    score: float | None = None   # per-check authenticity 0..1 (optional)

    def dict(self):
        return asdict(self)


@dataclass
class AgentOutput:
    agent: str
    confidence: float = 0.5
    findings: list = field(default_factory=list)
    heatmap_path: str | None = None
    extra: dict = field(default_factory=dict)

    def add(self, finding: Finding):
        self.findings.append(finding.dict())

    def dict(self):
        d = {
            "agent": self.agent,
            "confidence": round(float(self.confidence), 4),
            "findings": self.findings,
        }
        if self.heatmap_path:
            d["heatmap_path"] = self.heatmap_path
        d.update(self.extra)
        return d


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
