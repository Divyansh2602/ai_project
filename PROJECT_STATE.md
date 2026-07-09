# TrustSphere AI — Project State & Handoff

> **READ THIS FIRST when continuing the project in a new session (CLI or app).**
> This is the single source of truth for status, how to run things, gotchas, and
> how to push updates to Obsidian. Keep it updated as phases complete.
>
> Last updated: **2026-07-10** · Progress: **6 / 11 phases (~55%)**

---

## 1. What this is

**TrustSphere AI: Autonomous Deepfake Detection and Digital Evidence Verification Using Multi-Agent Forensic Analysis** — a college project (VIT, Divyansh Gupta).

Multi-agent AI system: takes an image/video/audio/document, runs parallel forensic
agents, and returns a verdict (Authentic / Fake / Inconclusive) **plus how it was
faked and which generator made it**, with heatmaps, blockchain audit trail, and a
legal PDF report.

- **No quantum** components (dropped — not feasible).
- Full 33-day plan: `C:\Users\Divyansh Gupta\.claude\plans\i-have-a-project-fluttering-charm.md`
- Auto-memory (portfolio project scope): `C:\Users\Divyansh Gupta\.claude\projects\C--Users-Divyansh-Gupta-Documents-portfolio\memory\trustsphere-project.md`

---

## 2. Two folders (don't confuse them)

| Folder | Purpose |
|---|---|
| `C:\Users\Divyansh Gupta\Desktop\trustsphere-ai\` | **The code** (backend + frontend). This file lives here. |
| `C:\Users\Divyansh Gupta\Desktop\TrustSphere AI\` | **Obsidian docs vault** (knowledge graph, phase notes). |

⚠️ **Memory is keyed to `C:\Users\Divyansh Gupta\Documents\portfolio`.** To get the
auto-memory loaded in the CLI, launch `claude` from *that* directory. This
`PROJECT_STATE.md` is the fallback if you work from the code dir instead.

---

## 3. Current status

| # | Phase | Status |
|---|---|---|
| 1 | Project Setup | ✅ Done |
| 2 | Backend Core | ✅ Done |
| 3 | AI Agents ×4 | ✅ Done (community deep models; industrial upgrade deferred → Phase 8) |
| 4 | Decision Engine | ✅ Done (verdict + manipulation type + GAN attribution + reasoning) |
| 5 | Security Layer | ✅ Done (C2PA + watermark agent, Ed25519 signing, Polygon **Amoy** anchor — **LIVE**, contract deployed at `0xe5C0eA5B1070cF5577200ecd310f8cdB5092DE49`, verified with a real on-chain tx) |
| 6 | XAI + Legal PDF | ✅ Done (Grad-CAM + Shapley + timeline + PDF + **LLM summary — LIVE via local Ollama**, `llama3.1:8b`, verified generating real forensic summaries, see §5.14) |
| 7 | Frontend Dashboard | ⬜ **NEXT** |
| 7.5 | OSINT Layer | ⬜ |
| 7.6 | Browser Extension | ⬜ |
| 8 | Integration + Testing | ⬜ (do the industrial model upgrade here) |
| 9 | Deployment | ⬜ |

---

## 4. What's built (backend file map)

```
backend/
├── main.py                     FastAPI app; wires routers; Base.metadata.create_all()
├── models/
│   ├── database.py             SQLAlchemy engine, SessionLocal, get_db()
│   └── evidence.py             Evidence, AgentResult, FinalVerdict, AuditLog
├── core/
│   ├── celery_app.py           Celery + Upstash Redis (SSL fix); threads pool
│   ├── tasks.py                analyze_evidence task; _run_agents; persists agent extras (P6)
│   ├── decision_engine.py      decide(); classify_manipulation(); attribute_generator()
│   ├── xai.py                 ⭐P6 Grad-CAM (ViT-aware + occlusion fallback) · exact Shapley
│   │                            for metadata · timeline/importance charts (matplotlib Agg)
│   └── pdf_report.py          ⭐P6 Legal Evidence Package PDF (reportlab)
├── agents/
│   ├── base.py                 AgentOutput, Finding, clamp — shared 0..1 authenticity contract
│   ├── metadata_agent.py       EXIF/software/timestamp/GPS anomalies
│   ├── image_agent.py          ELA (+heatmap PNG) · FFT fingerprint · deep deepfake model
│   ├── video_agent.py          per-frame FFT · duplicate frames · scene cuts · frame_scores
│   ├── audio_agent.py          librosa spectral · deep synthetic-speech model
│   └── security_agent.py      ⭐P5 C2PA manifest check + invisible-watermark (SD) — runs on ALL file types
├── security/
│   ├── signing.py             ⭐P5 Ed25519 record signing; key auto-gen at keys/ (gitignored)
│   └── blockchain.py          ⭐P5 Polygon Amoy anchor (env-gated, never fails pipeline)
├── contracts/
│   └── TrustSphereAudit.sol   ⭐P5 storeVerdict(fileHash, verdict, timestamp) + getVerdict
├── routers/
│   ├── upload.py               POST /api/upload
│   ├── analyze.py              POST /api/analyze/{file_id}
│   ├── result.py               GET /api/result/{task_id} · GET /api/status/{file_id}
│   ├── report.py               GET /api/report/{file_id} · ⭐P6 GET /api/report/{file_id}/pdf
│   └── verify.py              ⭐P5 GET /api/verify/{file_id} — file hash + signature + on-chain re-check
├── .env                        secrets + config (see gotchas)
└── requirements.txt

scripts/
├── obsidian_sync.py            Obsidian vault helper (see §7)
├── migrate_phase5.py           idempotent ALTERs — audit_logs signature/blockchain columns
├── migrate_phase6.py           idempotent ALTER — agent_results.extras JSONB (already run)
└── deploy_contract.py          compile + deploy TrustSphereAudit to Polygon Amoy (one-time)
```

**DB tables** (in Supabase): `evidence`, `agent_results`, `final_verdicts`, `audit_logs`.
`agent_results` (Phase 6) includes `extras` (jsonb) — frame_scores, flagged_segments,
gradcam_path/method, feature_importance, deep_predictions; previously these were discarded.
`final_verdicts` includes `manipulation_type`, `manipulation_confidence`,
`gan_attribution`, `gan_confidence`, `reasoning` (jsonb), `llm_summary` (still None —
LLM summary deferred by user choice; agreed design in HANDOFF §Phase-6 notes).
`audit_logs` (Phase 5) includes `record_signature`, `signature_algorithm`,
`signature_key_fingerprint`, `signed_payload` (jsonb — exactly what the signature covers),
`blockchain_hash` (tx), `blockchain_network`, `blockchain_status`, `chain_of_custody` (jsonb).

**Confidence convention across all agents:** `0.0 = definitely fake, 1.0 = definitely authentic`.
Decision engine weight-averages: image 30% · video 30% · audio 20% · metadata 20% · security 25%.
The security agent reports `confidence=None` (excluded from the average) when there is no
provenance data either way; a valid C2PA manifest **fast-tracks the verdict to Authentic**.
Thresholds: ≥0.75 Authentic · ≤0.40 Fake · else Inconclusive.

---

## 5. ⚠️ Runtime gotchas (these WILL bite if forgotten)

1. **Database — use the SESSION POOLER, not the direct host.**
   The direct host `db.<ref>.supabase.co` is **IPv6-only** and this machine has no
   working IPv6 → `could not translate host name`. `backend/.env` already uses the
   pooler (`DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres`).
   Special chars in the password must be URL-encoded (e.g. `@` → `%40`).

2. **Redis (Upstash) — `rediss://` needs `ssl_cert_reqs`.**
   Handled in `core/celery_app.py` (`_with_ssl_reqs` appends `?ssl_cert_reqs=CERT_REQUIRED`).
   Don't remove it or Celery raises at startup.

3. **HuggingFace — `HF_HUB_DISABLE_XET=1`.**
   The Xet download backend hangs on this machine. Already set in `.env`, so anything
   that calls `load_dotenv()` (the app, tasks) picks it up automatically. For a bare
   `python -c` test that doesn't load `.env`, prefix manually:
   `$env:HF_HUB_DISABLE_XET=1; .\venv\Scripts\python.exe ...`

4. **GPU is ready.** `torch 2.6.0+cu124`, CUDA available, RTX 3070 Ti (8 GB).
   Industrial models (DFDC-B7 ensemble + AASIST) are **deferred to Phase 8**.

5. **Celery on Windows** uses `worker_pool="threads"` (prefork doesn't work on Win).

6. **~~Known bug~~ FIXED (2026-07-07):** the audio deep model silently returned `skipped`.
   Root cause: **ffmpeg is not installed** — the HF audio pipeline shells out to ffmpeg
   when given a filename. Fix: `audio_agent._deep_score` now decodes with librosa and
   feeds the raw array to the pipeline (no ffmpeg needed), and all audio try/excepts now
   surface the real error in the finding note / Celery log instead of swallowing it.
   **ffmpeg is now installed** (Gyan.FFmpeg 8.1.2 via winget, 2026-07-07), so video →
   audio-track extraction works too — verified end-to-end (all 4 agents ran on a test
   video, deep model correctly flagged synthetic audio). ⚠️ Terminals opened *before*
   the install (including a running Celery worker / uvicorn) won't have ffmpeg on PATH —
   restart them.

7. **✅ Blockchain anchoring is LIVE (as of 2026-07-09).** Polygon **Mumbai is dead**
   (decommissioned 2024) — we use **Amoy** (chain 80002). Wallet `0x75222e25...A022`
   funded with test POL; contract `TrustSphereAudit.sol` deployed at
   `0xe5C0eA5B1070cF5577200ecd310f8cdB5092DE49`. Every analysis now anchors a real
   on-chain transaction — verify at
   https://amoy.polygonscan.com/address/0xe5C0eA5B1070cF5577200ecd310f8cdB5092DE49.
   `POLYGON_PRIVATE_KEY` and `TRUSTSPHERE_CONTRACT_ADDRESS` are both set in `backend/.env`.

8. **python-dotenv resolves `.env` from the CALLING FILE's directory, not cwd.**
   Scripts outside `backend/` must `load_dotenv(<explicit path to backend/.env>)`
   or DATABASE_URL comes back None (→ "Could not parse SQLAlchemy URL").

9. **Windows console is cp1252** — python scripts that print ✅/→/— crash unless they
   `sys.stdout.reconfigure(encoding="utf-8")` first (obsidian_sync.py does this now).

10. **Signing key:** Ed25519 PEM auto-generated at `backend/keys/server_signing_key.pem`
    on first signature (path via `SIGNING_KEY_PATH`). Gitignored. Losing it breaks
    verification of previously signed records — don't delete it.

11. **transformers 5.x moved ViT internals** (`vit.encoder.layer[i]` → `vit.layers[i]`).
    `core/xai.py` locates the Grad-CAM target layer by module-name suffix
    (`layernorm_before`) instead of a hardcoded path — keep it that way when upgrading.

12. **reportlab `<font color=...>` needs `#`-prefixed hex** (`color="#d73a49"`);
    bare hex crashes Paragraph parsing with "Invalid color value".

13. **Secrets live ONLY in `backend/.env`** (gitignored) — incl. `OBSIDIAN_API_KEY`
    (moved out of scripts/docs before the Phases 2–5 commit). Never paste the DB
    password or Obsidian token back into committed files.

14. **✅ Ollama is installed and working (2026-07-10).** Binary at
    `C:\Users\Divyansh Gupta\AppData\Local\Programs\Ollama\ollama.exe` (not on PATH
    by default in every shell — use the full path, or open a fresh terminal).
    Model `llama3.1:8b` pulled (4.9 GB). Runs as a background service automatically
    (`ollama` + `ollama app` processes) once installed — no need to manually start it.
    `.env` has `ENABLE_LLM_SUMMARY=1`, `OLLAMA_URL=http://localhost:11434`,
    `OLLAMA_MODEL=llama3.1:8b`. Verified: `core/llm_summary.py: generate_summary()`
    produces real, coherent forensic-report paragraphs from live decision data.
    **Uncommitted:** `core/llm_summary.py` (new), `core/tasks.py` (wired in),
    `requirements.txt` (added `requests`, removed unused `imagehash`) — commit
    when ready.

---

## 6. How to run

All commands from `C:\Users\Divyansh Gupta\Desktop\trustsphere-ai\backend`.

```powershell
# activate venv
.\venv\Scripts\Activate.ps1

# run API server
.\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000

# run Celery worker (separate terminal) — needed for real async /api/upload
.\venv\Scripts\python.exe -m celery -A core.celery_app.celery_app worker --pool=threads -l info

# quick test of one agent
$env:HF_HUB_DISABLE_XET=1
.\venv\Scripts\python.exe -c "from dotenv import load_dotenv; load_dotenv(); from agents import image_agent; import json; print(json.dumps(image_agent.run('uploads/test_sample.jpg'), indent=2, default=str))"
```

Frontend (`frontend/`, Next.js) exists from Phase 1 but is not built out yet (Phase 7).

---

## 7. 📓 Pushing updates to Obsidian (DO THIS YOURSELF — automatically)

There is a helper script — **use it, don't hand-write API calls**:
`scripts/obsidian_sync.py`. Run it with the backend venv python. It only works
**while the Obsidian app is open** (it prints a clear "OFFLINE" message otherwise).

```powershell
# from repo root: C:\Users\Divyansh Gupta\Desktop\trustsphere-ai
$py = ".\backend\venv\Scripts\python.exe"

& $py scripts\obsidian_sync.py check                                  # is Obsidian reachable?
& $py scripts\obsidian_sync.py list "Phases/"                         # list phase notes
& $py scripts\obsidian_sync.py get  "Phases/Phase 5 - Security.md"    # read a note
& $py scripts\obsidian_sync.py status "Phases/Phase 5 - Security.md" "✅ Done"   # set status
& $py scripts\obsidian_sync.py check-tasks "Phases/Phase 5 - Security.md"        # tick all [ ]->[x]
& $py scripts\obsidian_sync.py put "Phases/Phase 5 - Security.md" newbody.md     # replace whole note
```

**Standing instruction from the user — the per-phase ritual (do it without being asked):**
1. When a phase finishes, run `check`. If OFFLINE, tell the user to open Obsidian, then proceed.
2. `status "Phases/Phase N - <name>.md" "✅ Done"` and `check-tasks` on that same note.
3. Also **tell the user** what you updated in Obsidian (they like the confirmation).

**Raw API (only if the script is unavailable):** `https://127.0.0.1:27124/`,
header `Bearer <OBSIDIAN_API_KEY from backend/.env>`,
self-signed cert (skip verification). Endpoints: `GET/PUT /vault/<url-encoded-path>`,
`GET /vault/<folder>/` to list. PUT body = full markdown, `Content-Type: text/markdown`.

**Vault structure:** `Phases/` (Phase 1–9 + 7.5 + 7.6), `Agents/` (Metadata/Image/Video/Audio),
`Decisions/` (Decisions Log, Blockers, Demo Flow, Research Papers, Team Roles), `🏠 Home.md`.
Vault folder on disk: `C:\Users\Divyansh Gupta\Desktop\TrustSphere AI\`.

**⏳ Pending Obsidian sync:** none — Phases 1–6 all marked ✅ Done in the vault (synced 2026-07-07).
(Phase 6 note: LLM-summary task left honestly unchecked — deferred by user choice.)

---

## 8. Deferred: industrial model upgrade (Phase 8)

User wants **patent/industrial-level** models, but chose to build the full system
first. When Phase 8 arrives, on the GPU:
- **Image/Video:** DFDC-winner **EfficientNet-B7 ensemble** (Selim Seferbekov weights) +
  face detection (MTCNN/RetinaFace). Benchmarkable, citable.
- **Audio:** **AASIST** (ASVspoof top performer) or Wav2Vec2-AASIST hybrid.
- Swap is drop-in: model IDs are env vars (`DEEPFAKE_MODEL_ID`, `AUDIO_MODEL_ID`);
  agents already layer gracefully.

---

## 9. How to update THIS file

When a phase completes or a decision/gotcha changes:
1. Update the status table (§3) and the "Last updated" date at the top.
2. Add any new runtime gotcha to §5.
3. Mirror the change into the auto-memory file (`trustsphere-project.md`) so both stay in sync.
4. Remind the user of the Obsidian updates for that phase.
