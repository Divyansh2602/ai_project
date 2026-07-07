# HANDOFF — for the next Claude session

> **Read order: `CLAUDE.md` → `PROJECT_STATE.md` → this file.**
> PROJECT_STATE.md is the durable reference (status table, run commands, gotchas §5).
> This file is the *session-to-session baton*: what just happened, what's in flight,
> what to do next, and traps that aren't obvious from the code.
> **Standing rule: update this file at the end of every session** (user request, 2026-07-07).
>
> Last session: **2026-07-07 (second session)** (repo committed; Phase 6 built+tested)

---

## 1. Where the project stands

- **Phases 1–6 done (6/11, ~55%). Phase 7 (Frontend Dashboard) is next.**
- Backend is feature-complete for the demo loop: upload → 5 agents → decision engine
  → XAI (Grad-CAM, Shapley, video timeline) → Ed25519-signed record → audit log →
  `/api/verify` → **downloadable Legal Evidence PDF** (`GET /api/report/{id}/pdf`).
- Blockchain anchoring still env-gated/skipped until the user deploys the contract (§4).
- Frontend (Next.js) is still the Phase 1 scaffold — Phase 7 builds it out.

## 2. Git status

Repo is now committed: `969bd45` (Phases 2–5 + docs, single commit per user choice)
on top of `c544675` (Phase 1). Phase 6 should be committed at the end of the session
that finishes reading this (or was — check `git log`). **No remote configured; don't
push without asking.** Before committing docs/scripts, never reintroduce secrets —
they live only in `backend/.env` (incl. `OBSIDIAN_API_KEY`, moved there this session;
PROJECT_STATE.md §5.13).

## 3. What the 2026-07-07 (second) session did

**Housekeeping:**
- Committed Phases 2–5 as one commit (user chose single commit over per-phase).
- **Secrets scrubbed before committing**: Supabase password + Obsidian API token
  removed from PROJECT_STATE.md; token removed from `scripts/obsidian_sync.py`
  (now loads `OBSIDIAN_API_KEY` from `backend/.env` via explicit-path load_dotenv;
  exits with a clear message if unset). Verified script still works.

**Phase 6 — XAI + Legal PDF (complete except LLM summary, tested end-to-end):**
- `backend/core/xai.py` — the explainability module:
  - **Grad-CAM** on the image agent's deep classifier ('fake' class target).
    ViT-aware: target layer found by module-name suffix `layernorm_before`
    (transformers 5.x moved `vit.encoder.layer[i]` → `vit.layers[i]` — hardcoded
    paths break, PROJECT_STATE §5.11). CNN branch = last Conv2d. Model-agnostic
    **occlusion-map fallback** if Grad-CAM fails. Overlay saved as
    `{base}_gradcam.png` next to the ELA heatmap.
  - **Shapley attribution** for the metadata agent — its confidence is an
    unweighted mean of check scores (additive model) so Shapley values are the
    exact closed form `(score_i − 0.5)/n`. No `shap` package. Stored as
    `feature_importance` in extras.
  - **Timeline helpers**: `flagged_segments_from_scores()` merges low-score
    frames into contiguous tampered segments; matplotlib (Agg) renderers for the
    timeline + importance charts (rendered at PDF time, not in the worker).
- `backend/core/pdf_report.py` — Legal Evidence Package (reportlab): identity +
  SHA-256, verdict (color-coded), manipulation type + attribution, per-agent
  findings tables, XAI exhibits (ELA, Grad-CAM, importance chart, timeline),
  chain of custody, blockchain block, Ed25519 signature block. Served by new
  `GET /api/report/{file_id}/pdf` (routers/report.py); PDFs land in
  `backend/reports/` (gitignored).
- **DB**: `agent_results.extras` JSONB added (`scripts/migrate_phase6.py`, already
  run, idempotent). `core/tasks.py` now persists every agent-output key beyond
  the core four into extras — frame_scores were previously being **discarded**.
  JSON report (`GET /api/report/{id}`) now includes extras per agent.
- Agents integrated: image → gradcam extras + finding; metadata →
  feature_importance; video → flagged_segments.
- requirements.txt: + grad-cam, matplotlib, reportlab (installed in venv).
- **Tested end-to-end**: real Evidence row → `analyze_evidence.apply()` → extras
  persisted → TestClient GET report JSON + PDF (3 pages, all 6 sections, real
  ViT Grad-CAM, exhibit images verified visually). Test rows/files cleaned up.

**Obsidian synced:** Phase 6 note rewritten & marked ✅ Done; 5/6 tasks ticked,
LLM-summary task left **unchecked** (deferred by user choice — see §4.2).

**Full-codebase review (same session, commit `8539d2e`) — 4 bugs fixed, all
regression-tested (re-analysis ×2, hostile-chars PDF, MIME, path separators):**
- re-analysis IntegrityError (unique final_verdicts/audit_logs) → old rows now
  cleared at task start; `POST /api/analyze/{id}` works repeatedly.
- upload 415 on .mov/.mkv/.avi/.wav → real MIME names added (video/quicktime etc.).
- PDF crashed on findings notes containing `<`/`&` (agents surface raw exception
  text by design) → all dynamic Paragraph text is now XML-escaped.
- heatmap paths stored with mixed `\`/`/` on Windows → normalized to `/`.
- `/api/result` now returns agent `extras` (parity with `/api/report`).

**Known design debts (deliberate, don't "fix" casually):**
- upload reads the whole file into RAM before the size check (fine at 100 MB cap;
  revisit streaming at Phase 9 deploy).
- deep models run on CPU — `pipeline(...)` gets no `device`; GPU wiring is part
  of the Phase 8 industrial-model upgrade.
- `_fake_class_index()` / fake-label keyword matching depends on model label
  names — revisit when swapping models in Phase 8.
- audio agent `flagged_segments` is always `[]` (windowed audio scoring is a
  Phase 8 nicety). No API auth (college demo).

## 4. TODO — next session, in order

1. **Phase 7 — Frontend Dashboard** (plan file § Phase 7, Day 20–25): Next.js +
   TailwindCSS + shadcn/ui, dark theme. Pages `/`, `/analyze`, `/result/[id]`.
   Components incl. HeatmapViewer (ELA + Grad-CAM overlays), ConfidenceChart,
   VideoTimeline (Recharts — frame_scores/flagged_segments now come from
   `GET /api/report/{id}` → `agent_results[].extras`), BlockchainProof,
   DownloadReportButton (hits `/api/report/{id}/pdf`). Frontend needs a static
   route for heatmap PNGs — currently only paths are stored; add a
   `/api/heatmap/{file_id}/{kind}` endpoint or StaticFiles mount in FastAPI.
2. **LLM forensic summary (deferred from Phase 6 by user choice, 2026-07-07):**
   user explicitly chose "skip for now" this session — **don't build unasked**.
   Agreed design when they want it: env-gated `core/llm_report.py`, model
   `claude-opus-4-8`, no key → llm_summary stays None, never fails the pipeline.
   PDF + JSON already render it when populated. No `ANTHROPIC_API_KEY` exists yet.
3. **User-only action (remind, don't nag): blockchain go-live** (~5 min):
   throwaway wallet → test POL at faucet.polygon.technology (network: Amoy) →
   `POLYGON_PRIVATE_KEY` in backend/.env → `python scripts\deploy_contract.py` →
   paste printed address as `TRUSTSPHERE_CONTRACT_ADDRESS`. Then verify a tx on
   amoy.polygonscan.com and tick the 2 unchecked tasks in the Phase 5 Obsidian note.
4. **Phase 8 (deferred, don't start early):** industrial models — DFDC-winner
   EfficientNet-B7 ensemble + MTCNN/RetinaFace (image/video), AASIST (audio);
   swap via `DEEPFAKE_MODEL_ID` / `AUDIO_MODEL_ID`. Also: per-frame video
   Grad-CAM (noted in Phase 6 Obsidian task), optional trained classifier heads
   for classify_manipulation()/attribute_generator(). GPU ready (RTX 3070 Ti).

## 5. Traps that WILL bite (full list: PROJECT_STATE.md §5)

- **Supabase: session pooler only** (direct host is IPv6-only → DNS failure).
- **Upstash Redis**: `rediss://` needs `ssl_cert_reqs` (handled in celery_app.py).
- **`HF_HUB_DISABLE_XET=1`** — Xet backend hangs on this machine (.env has it; bare
  scripts must set it manually).
- **Celery on Windows**: `--pool=threads` only.
- **python-dotenv resolves `.env` from the CALLING FILE's dir, not cwd** — scripts
  outside `backend/` must `load_dotenv(<explicit path>)`.
- **Windows console is cp1252** — scripts printing ✅/→ need
  `sys.stdout.reconfigure(encoding="utf-8")`.
- **PowerShell 5.1 tool calls**: no `&&`; write temp .py files instead of heredocs.
- **`backend/keys/server_signing_key.pem` is precious** — never delete.
- **transformers 5.x ViT structure** — find Grad-CAM target by name suffix (§3).
- **reportlab font colors need `#` prefix** or Paragraph parsing crashes.
- **DWT-DCT watermark decode fails on smooth/gradient images** — use textured
  images for watermark demos.
- **ffmpeg**: on PATH only in shells opened after the 2026-07-07 install.

## 6. Standing user rules (obey without being asked)

1. **Obsidian ritual when a phase completes**: `obsidian_sync.py check` (if OFFLINE →
   ask user to open Obsidian) → update the phase note → tell the user exactly what
   changed. Use the script, never hand-written API calls. **Only tick tasks that are
   actually done** (Phase 6 LLM task is intentionally unchecked).
2. **Keep PROJECT_STATE.md and the auto-memory in sync**
   (auto-memory: `C:\Users\Divyansh Gupta\.claude\projects\C--Users-Divyansh-Gupta-Documents-portfolio\memory\trustsphere-project.md`).
3. **Update this HANDOFF.md every session.**
4. Before writing code for a new phase: read PROJECT_STATE.md fully + the plan-file
   section for that phase, and **summarize status + plan back to the user in 3–4
   lines first** (they explicitly asked for this pattern).

## 7. Locations

| What | Where |
|---|---|
| Code repo (this) | `C:\Users\Divyansh Gupta\Desktop\trustsphere-ai\` |
| Obsidian vault (docs) | `C:\Users\Divyansh Gupta\Desktop\TrustSphere AI\` (separate folder!) |
| Full 33-day plan | `C:\Users\Divyansh Gupta\.claude\plans\i-have-a-project-fluttering-charm.md` |
| Auto-memory (portfolio-keyed) | see §6.2 path |
| venv python | `.\backend\venv\Scripts\python.exe` (run from repo root or backend/) |
| Uploads / heatmaps / PDFs | `backend/uploads/`, `backend/uploads/heatmaps/`, `backend/reports/` |
| Signing key | `backend/keys/server_signing_key.pem` (gitignored, do not delete) |

## 8. Verify-it-still-works quick checks

```powershell
# from backend/ — API app + all routers import, DB reachable
.\venv\Scripts\python.exe -c "from main import app; print('ok')"

# agent smoke test (any image)
$env:HF_HUB_DISABLE_XET=1
.\venv\Scripts\python.exe -c "from dotenv import load_dotenv; load_dotenv(); from agents import security_agent; import json; print(json.dumps(security_agent.run('<path>'), indent=2))"
```

Full run commands (uvicorn + celery worker): PROJECT_STATE.md §6.
