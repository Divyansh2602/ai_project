# TrustSphere AI

**Before doing anything, read [`PROJECT_STATE.md`](./PROJECT_STATE.md), then [`HANDOFF.md`](./HANDOFF.md).**
PROJECT_STATE.md is the durable source of truth (scope, architecture, results, claim rules, run commands, gotchas).
HANDOFF.md is the session-to-session baton. **Update HANDOFF.md at the end of every session.**

Quick facts:
- Image-only multi-agent forgery detection with a signed evidence layer (college project, VIT).
- Backend FastAPI + SQLAlchemy (+ Celery in full mode); local mode uses SQLite and eager tasks. Web app served at `/app/`.
- The trained EfficientNet-B0 detector (multi-quality ELA) governs the image verdict.
- Windows + PowerShell/bash. Use a Python that has torch, transformers, reportlab, fastapi and timm.

Rules that must not be broken:
- Report only out-of-fold or held-out numbers; never compare a dev-split number to a paper.
- The project report lists only the methods we exceed (no "best"/"state of the art"); the full comparison stays in `docs/evaluation/EVALUATION.md`.
- Keep this repository free of audio, document and unrelated-paper content.
- Never commit `.env`, signing keys, databases or training caches. Never print secrets.
