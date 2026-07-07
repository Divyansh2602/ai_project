# HANDOFF — for the next Claude session

> **Read order: `CLAUDE.md` → `PROJECT_STATE.md` → this file.**
> PROJECT_STATE.md is the durable reference (status table, run commands, gotchas §5).
> This file is the *session-to-session baton*: what just happened, what's in flight,
> what to do next, and traps that aren't obvious from the code.
> **Standing rule: update this file at the end of every session** (user request, 2026-07-07).
>
> Last session: **2026-07-07** (Phase 5 built+tested; audio bug fixed; ffmpeg installed)

---

## 1. Where the project stands

- **Phases 1–5 done (5/11, ~45%). Phase 6 (XAI + Legal PDF) is next.**
- Backend pipeline is fully working end-to-end: upload → 4–5 agents → decision engine
  (verdict + manipulation type + GAN attribution) → Ed25519-signed record → audit log
  → `/api/verify` re-check. Blockchain anchoring is built but **skipped** until the
  user deploys the contract (see §4).
- Frontend (Next.js) is still the Phase 1 scaffold — untouched until Phase 7.

## 2. ⚠️ GIT: almost everything is UNCOMMITTED

`master` has **one commit** (Phase 1 scaffold). All Phase 2–5 code, CLAUDE.md,
PROJECT_STATE.md, scripts/, this file — all uncommitted. The user hasn't asked for
commits. **Early next session, offer to commit** (suggest one commit per phase or a
single "Phases 2–5" commit — user's call). Don't push without asking; no remote
configured checks done yet.

## 3. What the 2026-07-07 session did

**Phase 5 — Security Layer (complete, tested end-to-end):**
- `backend/agents/security_agent.py` — 5th agent, runs on ALL file types:
  C2PA manifest verification (c2pa-python 0.36; valid manifest → decision engine
  fast-tracks verdict to Authentic, score floored at 0.9) + invisible-watermark
  detection (DWT-DCT; detects `StableDiffusionV1` / `SDV2` payloads → near-certain
  Fake + generator attribution). Reports `confidence=None` when no provenance data
  exists so it's excluded from the weighted average (decision engine handles None).
- `backend/security/signing.py` — Ed25519 record signing. Key auto-generated at
  `backend/keys/server_signing_key.pem` — **this key EXISTS now (created during
  tests), is gitignored, and must never be deleted** or old signatures can't verify.
- `backend/security/blockchain.py` + `backend/contracts/TrustSphereAudit.sol` +
  `scripts/deploy_contract.py` — Polygon **Amoy** (chain 80002; Mumbai is DEAD,
  decommissioned 2024). Env-gated; currently returns `skipped` gracefully.
- `scripts/migrate_phase5.py` — already run against Supabase (idempotent). Added to
  `audit_logs`: record_signature, signature_algorithm, signature_key_fingerprint,
  signed_payload (jsonb — exactly what the signature covers), blockchain_network,
  blockchain_status.
- `backend/routers/verify.py` — `GET /api/verify/{file_id}`: re-hash file vs stored
  hash + verify signature + read verdict back from chain. Returns `verified: bool`.
- Decision engine: `AGENT_WEIGHTS["security"] = 0.25`; None-confidence exclusion;
  C2PA fast-track; watermark → manipulation candidate + attribution.
- Test artifacts were cleaned up (test evidence row deleted from Supabase).

**Bug fix — audio deep model (was PROJECT_STATE §5.6):**
- Root cause was **missing ffmpeg**, not torch/transformers — HF audio pipeline
  shells out to ffmpeg for filename inputs; broad try/excepts hid the error.
- Fix: `audio_agent._deep_score` now decodes via librosa and passes
  `{"raw": y, "sampling_rate": sr}` to the pipeline; all audio-path exceptions now
  surface real error text in finding notes / Celery logs.
- **ffmpeg 8.1.2 installed** (winget, Gyan build) → video→audio-track extraction
  verified working (all 4 agents ran on a test video; sine-tone audio correctly
  flagged synthetic at 0.008 authenticity). Shells opened before the install need
  restarting to see ffmpeg on PATH.

**Docs/sync done this session:**
- Obsidian: Phases 3, 4, 5 marked ✅ Done; Phase 5 note rewritten (Amoy correction;
  two on-chain tasks left honestly UNCHECKED pending user wallet — see §4).
- `scripts/obsidian_sync.py`: added UTF-8 stdout reconfigure (cp1252 console crashed
  on ✅/→ — fixed permanently).
- PROJECT_STATE.md + portfolio auto-memory updated to match all of the above.

## 4. TODO — next session, in order

1. **Offer to commit the repo** (§2).
2. **Phase 6 — XAI + Legal PDF** (plan file § Phase 6, Day 18–19):
   - Grad-CAM heatmaps (image agent's deep model regions)
   - SHAP feature importance (metadata agent)
   - Video confidence timeline (frame_scores already exist in video agent output)
   - **LLM forensic summary via Claude API** → fills `final_verdicts.llm_summary`
     (currently hardcoded None in `core/tasks.py`). ⚠️ **This was started and
     rolled back**: user REJECTED the `pip install anthropic` this session (may have
     just been mid-interrupt for the audio bug — but do NOT assume; confirm before
     installing). No `ANTHROPIC_API_KEY` anywhere yet (checked env, .env, no ant CLI).
     Design sketch agreed: env-gated like blockchain (skip → None if no key),
     `core/llm_report.py`, model `claude-opus-4-8`, never fails the pipeline.
   - Legal Evidence PDF (reportlab — already the decided choice): SHA-256, chain of
     custody, blockchain proof link, findings, manipulation type + attribution,
     heatmaps, signature.
   - When Phase 6 finishes: Obsidian ritual (§6) on `Phases/Phase 6 - XAI.md`.
3. **User-only action (remind, don't nag): blockchain go-live** (~5 min):
   throwaway wallet → test POL at faucet.polygon.technology (network: Amoy) →
   `POLYGON_PRIVATE_KEY` in backend/.env → `python scripts\deploy_contract.py` →
   paste printed address as `TRUSTSPHERE_CONTRACT_ADDRESS`. Then: verify a tx on
   amoy.polygonscan.com and tick the 2 unchecked tasks in the Phase 5 Obsidian note.
4. **Phase 8 (deferred, don't start early):** industrial models — DFDC-winner
   EfficientNet-B7 ensemble + MTCNN/RetinaFace (image/video), AASIST (audio);
   swap via `DEEPFAKE_MODEL_ID` / `AUDIO_MODEL_ID` env vars. Optional trained
   classifier heads replacing rule-based `classify_manipulation()` /
   `attribute_generator()`. GPU ready (RTX 3070 Ti, torch 2.6.0+cu124).

## 5. Traps that WILL bite (full list: PROJECT_STATE.md §5)

- **Supabase: session pooler only** (direct host is IPv6-only → DNS failure).
- **Upstash Redis**: `rediss://` needs `ssl_cert_reqs` (handled in celery_app.py).
- **`HF_HUB_DISABLE_XET=1`** — Xet backend hangs on this machine (.env has it; bare
  scripts must set it manually).
- **Celery on Windows**: `--pool=threads` only.
- **python-dotenv resolves `.env` from the CALLING FILE's dir, not cwd** — scripts
  outside `backend/` must `load_dotenv(<explicit path>)` or DATABASE_URL is None
  ("Could not parse SQLAlchemy URL").
- **Windows console is cp1252** — scripts printing ✅/→/— need
  `sys.stdout.reconfigure(encoding="utf-8")` (obsidian_sync.py does this).
- **PowerShell 5.1 tool calls**: no `&&`; heredocs to python -c mangle quotes —
  write temp .py files to the scratchpad instead.
- **`backend/keys/server_signing_key.pem` is precious** (see §3).
- **DWT-DCT watermark decode fails on smooth/gradient images** — needs texture;
  use textured/natural images for demos of watermark detection.
- **ffmpeg**: on PATH only in shells opened after 2026-07-07 install.

## 6. Standing user rules (obey without being asked)

1. **Obsidian ritual when a phase completes**: `obsidian_sync.py check` (if OFFLINE →
   ask user to open Obsidian) → `status "Phases/Phase N - <name>.md" "✅ Done"` →
   `check-tasks` → tell the user exactly what changed in the vault. Use the script,
   never hand-written API calls. Only tick tasks that are actually done.
2. **Keep PROJECT_STATE.md and the auto-memory in sync** as things change
   (auto-memory: `C:\Users\Divyansh Gupta\.claude\projects\C--Users-Divyansh-Gupta-Documents-portfolio\memory\trustsphere-project.md`).
3. **Update this HANDOFF.md every session** (added 2026-07-07).
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
| Uploads / heatmaps | `backend/uploads/` (currently empty), `backend/heatmaps/` |
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
