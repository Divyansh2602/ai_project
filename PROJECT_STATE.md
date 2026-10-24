# TrustSphere AI: project state (image-only)

Durable source of truth for what this repository is, how to run it and what is true about it. Session-to-session
notes live in [HANDOFF.md](HANDOFF.md).

## 1. Scope

Multi-agent image-forgery detection with an evidence layer. **Image only.** Audio, document and video branches
were removed on purpose. Nothing here is connected to any other paper or project; the base papers for the
comparison are the five in the course folder (Ranjan 2026, Ravula 2025, Rehman 2025, Deb 2026, Chen/GIFT 2026).

## 2. Architecture

| Part | Where | Notes |
|---|---|---|
| API | `backend/main.py`, `backend/routers/` | upload, analyze, result, report, verify, history; web app static files at `/app/` |
| Agents | `backend/agents/` | metadata (EXIF), image forensics, security/provenance (C2PA, watermark) |
| Trained detector | `backend/core/trained_detector.py`, `backend/models/trained/` | EfficientNet-B0 on multi-quality ELA (JPEG q70/85/95), manifest-driven |
| Decision engine | `backend/core/decision_engine.py` | weights metadata 0.20, image 0.30, security 0.25; agents with `None` confidence are excluded; Authentic >= 0.75, Fake <= 0.40, else Inconclusive |
| Evidence layer | `backend/security/`, `backend/core/pdf_report.py` | SHA-256, Ed25519 signature (`backend/keys/`, gitignored), chain of custody, optional Polygon Amoy anchor, ReportLab PDF |
| Web app | `backend/static/` | Analyze, report, History, How it works |
| Training / evaluation | `training/`, `scripts/evaluate_images.py` | CV, source-disjoint CV, patch detector, localiser, pipeline hold-out |
| Report | `scripts/build_report.py`, `docs/report/` | Word report from the VIT template, diagrams from `scripts/make_report_diagrams.py` |

The image agent's verdict comes from the trained detector (`out.confidence = 1 - p_fake`). ELA, FFT, Grad-CAM and
the Hugging Face deepfake classifier are supporting evidence and are labelled as such.

## 3. Weights in `backend/models/trained/`

| File | Use |
|---|---|
| `casia_v2_effnet_b0.pt` | app default, trained on all of CASIA v2.0 (listed in `manifest.json`) |
| `casia_v2_group_holdout.pt` | trained on 80% source-disjoint; used only for the pipeline hold-out evaluation |
| `columbia_random.pt`, `columbia_random_patch_srm.pt` | Columbia whole-image and patch-based models (evaluation only) |
| `localizer_effnet_b0.pt` | U-Net-style localiser (evaluation only) |

## 4. Results (all out-of-fold or held-out)

See [docs/evaluation/EVALUATION.md](docs/evaluation/EVALUATION.md) and `docs/evaluation/metrics.json`.

- CASIA v2.0: 95.53% (random 5-fold), 95.32% (source-disjoint), AUC 0.99.
- Columbia: 97.25% patch-based (random 5-fold), 96.97% with every scene kept in one fold (AUC 0.980); whole-image ELA detector 87.60%.
- Pipeline on 588 held-out CASIA images: forced two-way 96.43% (AUC 0.9943); three-way: 90.5% decided, 97.9% accurate on decided.
- Localisation (train CASIA, test Columbia): pixel F1 0.433, below GIFT's 0.6497. Reported as a limit.
- Some published CASIA results (96 to 99%) are above ours; they are listed in EVALUATION.md, not hidden.

### Rules for claims

1. Never compare a development/tuning-split number to a paper. Only out-of-fold or held-out numbers.
2. The project report lists only the methods our detector exceeds, framed as "exceeds", never "best" or "state of the art". The full comparison, including papers above us and the localisation gap, stays in EVALUATION.md.
3. No audio, document or other-paper content anywhere in this repository.

## 5. Run

```bash
cd backend && python -m uvicorn main:app --port 8000     # or START_APP.bat
```

Local mode (`backend/.env`): `DATABASE_URL=sqlite:///./trustsphere.db`, `CELERY_ALWAYS_EAGER=true`. Full mode:
PostgreSQL + Redis + Celery worker (see `backend/.env.example`). Python with torch, transformers, reportlab,
fastapi, timm. GPU is optional for inference; training used an RTX 3070 Ti (8 GB).

Tests: `python scripts/e2e_test.py` (19 checks: upload, analysis, report, PDF, signature, tamper detection of the
evidence record, history).

## 6. Gotchas

- `JSONB` columns map to JSON on SQLite through a type variant in `models/`; on PostgreSQL they stay JSONB.
- Naive timestamps from SQLite are treated as UTC in the web app (`when()` in `static/app.js`).
- The Hugging Face deepfake model downloads on first run (`HF_HUB_DISABLE_XET=1` helps on some networks).
- Training caches (`training/cache/`) are large and gitignored; scripts rebuild them.
- Windows paths in Python patch scripts: use raw strings or write files with an editor tool; `\U` in a normal string breaks.
- Polygon Amoy anchoring is env-gated. Leave `POLYGON_PRIVATE_KEY` empty to disable it in tests. Use a throwaway test wallet only.
- `backend/.env`, `backend/keys/`, `backend/*.db`, `backend/reports/`, `backend/uploads/` are gitignored. Never commit them.
