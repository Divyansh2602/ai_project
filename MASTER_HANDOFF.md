# TrustSphere AI — Master Handoff Document

> **Purpose:** this is the single document to hand to a fresh Claude Code session
> (new account, new machine, or both) so it has full context in one read — no
> memory system required. Read this before touching any code.
>
> Last compiled: **2026-07-13** · Progress: **6 / 11 phases (~55%)**

---

## 1. Identity & Goal

**Title:** TrustSphere AI: Autonomous Deepfake Detection and Digital Evidence
Verification Using Multi-Agent Forensic Analysis

**Type:** College project (VIT, student Divyansh Gupta).

**Goal:** A multi-agent AI system that takes any image, video, audio, or document
and determines whether it's authentic or AI-manipulated — not just a fake/real
score, but **how** it was faked (face swap, voice clone, GAN-generated), **which
AI likely made it**, and a **court-admissible evidence package**: a signed,
blockchain-anchored report with visual explanations.

**Why it matters:** Deepfakes are a documented, funded problem (Meta ran a $1M
public challenge — DFDC — specifically because detection is hard). Existing
tools give a bare score; nobody gives you evidence you could show in a dispute,
newsroom, or court. That gap — detection + explainability + tamper-proof
evidence — is what this targets.

**No quantum components** — dropped early as infeasible for a college project;
uses standard cryptography (Ed25519, C2PA, Polygon blockchain) instead.

---

## 2. Two folders — don't confuse them

| Folder | Purpose |
|---|---|
| `C:\Users\Divyansh Gupta\Desktop\trustsphere-ai\` | **The code** (backend + frontend). This file lives here. |
| `C:\Users\Divyansh Gupta\Desktop\TrustSphere AI\` | **Obsidian docs vault** (knowledge graph, phase notes, decisions log). |

---

## 3. Current status (6 / 11 phases)

| # | Phase | Status | One-liner |
|---|---|---|---|
| 1 | Project Setup | ✅ Done | Supabase + Upstash cloud, venv, Next.js scaffold |
| 2 | Backend Core | ✅ Done | FastAPI, 4 DB tables, upload/analyze/result/report, Celery |
| 3 | AI Agents ×5 | ✅ Done | Metadata, Image, Video, Audio + Security (added Ph.5) |
| 4 | Decision Engine | ✅ Done | Weighted verdict + manipulation type + GAN attribution |
| 5 | Security Layer | ✅ Done | C2PA + watermark, Ed25519 signing, Polygon Amoy anchor — **LIVE** |
| 6 | XAI + Legal PDF | ✅ Done | Grad-CAM, exact Shapley, timeline, PDF, **local Ollama LLM summary — LIVE** |
| 7 | Frontend Dashboard | ⬜ **NEXT** | Next.js scaffold exists, not built out |
| 7.5 | OSINT Layer | ⬜ Not started | Reverse image search / cross-platform mismatch |
| 7.6 | Browser Extension | ⬜ Not started | Right-click "Verify with TrustSphere" |
| 8 | Integration + Testing | ⬜ Not started | Industrial model upgrade happens here |
| 9 | Deployment | ⬜ Not started | Docker Compose / Render + Vercel |

**Concrete, real (not aspirational) proof points:**
- A real transaction is live on Polygon Amoy, anchoring an actual analysis verdict.
- A real 3-page legal PDF has been generated end-to-end from a real upload through the real API/task queue.
- Full pipeline (upload → 5 agents → verdict → sign → anchor on-chain → PDF) tested against the live running system.

---

## 4. Architecture

### Backend file map
```
backend/
├── main.py                     FastAPI app; wires routers; Base.metadata.create_all()
├── models/
│   ├── database.py             SQLAlchemy engine, SessionLocal, get_db()
│   └── evidence.py             Evidence, AgentResult, FinalVerdict, AuditLog
├── core/
│   ├── celery_app.py           Celery + Upstash Redis (SSL fix); threads pool
│   ├── tasks.py                analyze_evidence task; _run_agents; persists agent extras
│   ├── decision_engine.py      decide(); classify_manipulation(); attribute_generator()
│   ├── xai.py                  Grad-CAM (ViT-aware + occlusion fallback) · exact Shapley
│   │                            for metadata · timeline/importance charts (matplotlib Agg)
│   ├── pdf_report.py           Legal Evidence Package PDF (reportlab)
│   └── llm_summary.py          generate_summary() — local Ollama call, env-gated, fails safe
├── agents/
│   ├── base.py                 AgentOutput, Finding, clamp — shared 0..1 authenticity contract
│   ├── metadata_agent.py       EXIF/software/timestamp/GPS anomalies — images only (see §9 gap)
│   ├── image_agent.py          ELA (+heatmap PNG) · FFT fingerprint · deep deepfake model (ViT)
│   ├── video_agent.py          per-frame FFT · duplicate frames · scene cuts · frame_scores
│   ├── audio_agent.py          librosa spectral · deep synthetic-speech model (Wav2Vec2)
│   └── security_agent.py       C2PA manifest check + invisible-watermark (SD) — runs on ALL file types
├── security/
│   ├── signing.py              Ed25519 record signing; key auto-gen at keys/ (gitignored)
│   └── blockchain.py           Polygon Amoy anchor (env-gated, never fails pipeline)
├── contracts/
│   └── TrustSphereAudit.sol    storeVerdict(fileHash, verdict, timestamp) + getVerdict
├── routers/
│   ├── upload.py                POST /api/upload
│   ├── analyze.py               POST /api/analyze/{file_id}
│   ├── result.py                GET /api/result/{task_id} · GET /api/status/{file_id}
│   ├── report.py                GET /api/report/{file_id} · GET /api/report/{file_id}/pdf
│   └── verify.py                GET /api/verify/{file_id} — hash + signature + on-chain re-check
├── .env                         secrets + config (gitignored, see §8)
└── requirements.txt

scripts/
├── obsidian_sync.py             Obsidian vault helper (see §10)
├── migrate_phase5.py            idempotent ALTERs — audit_logs signature/blockchain columns
├── migrate_phase6.py            idempotent ALTER — agent_results.extras JSONB
└── deploy_contract.py           compile + deploy TrustSphereAudit to Polygon Amoy (one-time)
```

### Data flow
`POST /api/upload` → SHA-256 hash computed, file stored, `Evidence` row created →
`POST /api/analyze/{file_id}` → Celery task `analyze_evidence` → `_run_agents()`
runs the relevant agents sequentially for the file type (see table below) →
`core/decision_engine.decide()` weight-fuses scores into a verdict →
Ed25519-signs the record → anchors SHA-256 + verdict on Polygon Amoy →
`core/xai.py` generates Grad-CAM/Shapley/timeline → `core/llm_summary.py` asks
local Ollama for a prose summary → `core/pdf_report.py` renders the Legal
Evidence PDF → everything persisted to Supabase Postgres (`final_verdicts`,
`agent_results`, `audit_logs`).

### Which agents run per file type (`core/tasks.py: _run_agents`)
| file_type | Agents that run |
|---|---|
| image | metadata, image, **security** |
| video | metadata, video, audio (extracted track via ffmpeg), **security** |
| audio | metadata, audio, **security** |
| document | metadata **(EXIF-only — see gap in §9)**, **security** |

### Database (Supabase Postgres)
- `evidence` — file_id, file_type, upload_time, status, file_path, file_hash
- `agent_results` — agent_name, evidence_id, findings JSON, confidence, **extras JSONB** (frame_scores, flagged_segments, gradcam_path/method, feature_importance, deep_predictions)
- `final_verdicts` — verdict, overall_score, manipulation_type, manipulation_confidence, gan_attribution, gan_confidence, reasoning (jsonb), **llm_summary**
- `audit_logs` — record_signature, signature_algorithm, signature_key_fingerprint, signed_payload (jsonb), blockchain_hash (tx), blockchain_network, blockchain_status, chain_of_custody (jsonb)

**Confidence convention across all agents:** `0.0 = definitely fake, 1.0 = definitely authentic`.
Decision engine weights: image 30% · video 30% · audio 20% · metadata 20% · security 25%
(security excluded from the average entirely when it has no provenance signal
either way, rather than counted as neutral 0.5). A valid C2PA manifest
fast-tracks the verdict to Authentic (floored at 0.9). Thresholds: ≥0.75
Authentic · ≤0.40 Fake · else Inconclusive.

### Smart contract mechanics
`storeVerdict(fileHash, verdict, timestamp)` writes a record keyed by
`keccak256(abi.encodePacked(fileHash))`. `getVerdict(fileHash)` is a free public
read. **Only the SHA-256 hash + verdict + timestamps + submitter address go
on-chain** — never the media file or rich findings (those live in Supabase,
the actual read path for reports). Deployed contract:
`0xe5C0eA5B1070cF5577200ecd310f8cdB5092DE49` on Polygon Amoy (chain 80002) —
verify at https://amoy.polygonscan.com/address/0xe5C0eA5B1070cF5577200ecd310f8cdB5092DE49

---

## 5. Tech stack — planned vs. actual

| Category | Planned | Actual (built) |
|---|---|---|
| Backend | FastAPI, SQLAlchemy, Celery, Redis | Same, **Upstash Redis (TLS)** instead of local |
| Database | PostgreSQL | **Supabase Postgres via session pooler** (direct host is IPv6-only, unreachable here) |
| Agent orchestration | CrewAI | **Plain sequential calls in one Celery task** — simpler, agents don't need to negotiate with each other |
| Image/Video agents | HuggingFace, OpenCV, EfficientNet | OpenCV, numpy, **HF ViT classifier** (`prithivMLmods/Deep-Fake-Detector-v2-Model`, swappable via env) |
| Audio agent | librosa, Wav2Vec2 | librosa, **HF Wav2Vec2-based classifier** (`MelodyMachine/Deepfake-audio-detection-V2`), ffmpeg subprocess for track extraction |
| GAN Fingerprinting | torch, custom HF classifier | **Rule-based heuristic** (FFT high-freq ratio + watermark hit) — trained model deferred to Phase 8 |
| Manipulation classifier | Trained classification head | **Rule-based inference** over agent findings — trained model deferred to Phase 8 |
| Security | cryptography, c2pa-python, web3.py | Same, **Ed25519** specifically, + **invisible-watermark** (DWT-DCT, SD payloads) |
| Blockchain | Solidity, **Polygon Mumbai**, web3.py | Solidity, **Polygon Amoy** (Mumbai decommissioned April 2024) — **contract deployed & live** |
| XAI | Grad-CAM, SHAP | `grad-cam` package, **exact closed-form Shapley** (metadata confidence is an additive mean, so Shapley has closed form `(score_i − 0.5)/n` — no `shap` package needed) |
| LLM report | Claude API | **Local Ollama (`llama3.1:8b`)** — free, fully offline, evidence never leaves the machine |
| PDF Report | reportlab or weasyprint | **reportlab** |
| OSINT | Google Vision API or SerpAPI | Not started (Phase 7.5) |
| Frontend | Next.js, TailwindCSS, shadcn/ui, Recharts | Scaffold only (Phase 7) |
| Browser Extension | Vanilla JS, Chrome Manifest V3 | Not started (Phase 7.6) |
| Test Datasets | FaceForensics++, ASVspoof | Not started (Phase 8) — see §11 for the demo-file workaround used instead |

---

## 6. Key decisions made (and why)

- **Dropped quantum components** (QKD, CRYSTALS-Kyber) — not feasible for a college project timeline.
- **Polygon Amoy, not Mumbai** — Mumbai was decommissioned April 2024; Amoy (chain 80002) is its replacement, free test POL.
- **Ed25519 over RSA** for record signatures — smaller, faster, modern.
- **C2PA + watermark merged into one 5th "security" agent** rather than separate modules — single weight in the decision engine, one wire-in point.
- **Local Ollama over Claude API** for the LLM summary — free, fully offline, keeps evidence on-machine (privacy-appropriate for a forensics tool).
- **CrewAI dropped for plain function calls** — the 5 agents don't negotiate with each other, they each independently score the same file, so CrewAI's message-passing overhead bought nothing.
- **Rule-based (not trained) manipulation classifier & GAN attribution** for now — a real trained classifier is deferred to Phase 8, after the industrial model upgrade.
- **Dark theme** for the eventual frontend (forensic/security aesthetic).
- **reportlab over weasyprint** for PDF generation — lighter dependency.

---

## 7. Mistakes made & how they were fixed (postmortem log)

Keeping this section honest and complete on purpose — it's the fastest way for
a new session (or a new account) to avoid repeating the same errors.

1. **rPPG patentability overclaim.** Early on, rPPG (heartbeat-from-video) was
   called "a plausible basis for a provisional patent" *without doing a
   prior-art search first*. When challenged, a real prior-art search was run
   (FakeCatcher, DeepRhythm, and close published equivalents for every
   candidate "novel" technique considered). **Conclusion: none of it is
   patentable as conceived** — reframed as project features / possible
   publication angle, not a patent filing. See §12 for the full list of future
   detection features kept from this research.
2. **Accidentally deleted a completed Ollama installer download** — misread
   the file size in `ls -la` output (a space in the Windows username shifted
   column alignment, making a completed ~1.36GB file look like a stub). Fixed
   by re-downloading with `curl -C -` (resume). Acknowledged directly, no
   excuse-making — just re-did the download correctly.
3. **Audio deep model silently returned `skipped`.** Root cause: **ffmpeg was
   not installed** — the HF audio pipeline shells out to ffmpeg when given a
   filename. Fixed: `audio_agent._deep_score` now decodes via librosa and
   passes the raw array (no ffmpeg needed for audio files); ffmpeg was also
   installed (Gyan.FFmpeg 8.1.2 via winget) so video→audio-track extraction
   works too. **Gotcha that persists:** shells opened *before* the ffmpeg
   install won't have it on PATH — restart terminals.
4. **transformers 5.x moved ViT internals** (`vit.encoder.layer[i]` →
   `vit.layers[i]`), which broke a hardcoded Grad-CAM target-layer path. Fixed
   by locating the target layer by **module-name suffix** (`layernorm_before`)
   instead of a hardcoded index path — survives future transformers version bumps.
5. **Windows console is cp1252** — any script printing ✅/→/— crashed with
   `UnicodeEncodeError`. Fixed with `sys.stdout.reconfigure(encoding="utf-8",
   errors="replace")` before any print statements (done in `obsidian_sync.py`
   and PDF-text-extraction scripts).
6. **python-dotenv resolves `.env` from the calling file's directory, not
   cwd.** Scripts living outside `backend/` (e.g. `scripts/deploy_contract.py`)
   silently got `DATABASE_URL=None` → "Could not parse SQLAlchemy URL" until
   `load_dotenv()` was passed an explicit path to `backend/.env`.
7. **reportlab `<font color=...>` needs a `#`-prefixed hex** — bare hex crashes
   Paragraph parsing with "Invalid color value".
8. **Re-analysis IntegrityError** — re-running `/api/analyze/{id}` on the same
   evidence hit a unique-constraint violation on `final_verdicts`/`audit_logs`.
   Fixed: old rows are now cleared at task start before re-inserting.
9. **Upload returned 415 on `.mov`/`.mkv`/`.avi`/`.wav`** — browsers send
   informal MIME names (`video/quicktime`, `video/x-matroska`, etc.) that
   weren't in `ALLOWED_TYPES`. Fixed by adding the real MIME names.
10. **PDF generation crashed on hostile characters** — agent findings
    sometimes surface raw exception text containing `<` or `&`, which broke
    reportlab's Paragraph XML parser. Fixed: all dynamic Paragraph text is now
    XML-escaped before rendering.
11. **Heatmap paths stored with mixed `\`/`/` separators on Windows** — broke
    path handling downstream. Normalized to `/` at storage time.
12. **Metadata agent is EXIF-only, doesn't parse PDF-native metadata** — found
    2026-07-13 while building document-type test files. `metadata_agent.py`
    uses `exifread` + Pillow, both of which only understand image EXIF —
    **a real PDF's `/Producer`/`/CreationDate`/`/ModDate` fields are never
    read**, so an original vs. tampered PDF currently score identically. **Not
    yet fixed** — flagged as a known gap, not silently papered over (see §9).

---

## 8. Environment setup (what a fresh machine/account needs)

### One-time installs (per machine, not per Claude account)
- Python venv: `python -m venv venv` in `backend/`, then `pip install -r requirements.txt`
- **Ollama** — binary + `llama3.1:8b` model (4.9 GB) pulled. Runs as a background service once installed.
- **ffmpeg** — required for video→audio-track extraction and audio deep-model decoding path.
- **GPU (optional but available on the dev machine):** RTX 3070 Ti, `torch 2.6.0+cu124`, CUDA available. Industrial models (Phase 8) need this; current models run fine on CPU.
- Node.js + npm for the `frontend/` Next.js scaffold (Phase 7 work).

### `backend/.env` — must be recreated on any new machine (gitignored, never committed)
| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Supabase **session pooler** connection string (not the direct host — IPv6-only, fails here) |
| `REDIS_URL` (or similar, `rediss://`) | Upstash Redis, needs `ssl_cert_reqs=CERT_REQUIRED` appended (handled in code, not the env value itself) |
| `HF_HUB_DISABLE_XET=1` | Xet download backend hangs on this machine |
| `DEEPFAKE_MODEL_ID` | HF image deepfake model, default `prithivMLmods/Deep-Fake-Detector-v2-Model` |
| `AUDIO_MODEL_ID` | HF audio deepfake model, default `MelodyMachine/Deepfake-audio-detection-V2` |
| `SIGNING_KEY_PATH` | Path to Ed25519 PEM (auto-generated at `backend/keys/server_signing_key.pem` on first run — **never delete this, it breaks verification of previously signed records**) |
| `POLYGON_PRIVATE_KEY` | Throwaway wallet private key, funded with test POL from faucet.polygon.technology (Amoy network) |
| `TRUSTSPHERE_CONTRACT_ADDRESS` | `0xe5C0eA5B1070cF5577200ecd310f8cdB5092DE49` (or a freshly deployed one via `scripts/deploy_contract.py`) |
| `POLYGON_RPC_URL` / `POLYGON_CHAIN_ID` | Point at Amoy (80002), not Mumbai |
| `ENABLE_LLM_SUMMARY=1` | Gates the Ollama call |
| `OLLAMA_URL=http://localhost:11434` | Local Ollama server |
| `OLLAMA_MODEL=llama3.1:8b` | Model name |
| `OBSIDIAN_API_KEY` | For `scripts/obsidian_sync.py` (Local REST API plugin token — regenerate per-vault if the vault moves) |

### How to run (from `backend/`)
```powershell
.\venv\Scripts\Activate.ps1
.\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
# separate terminal:
.\venv\Scripts\python.exe -m celery -A core.celery_app.celery_app worker --pool=threads -l info
```
Swagger UI for manual testing (no frontend yet): `http://localhost:8000/docs`

---

## 9. Known design debts (deliberate — don't "fix" casually without reading why)

- **Document-type metadata is non-diagnostic** (§7.12) — `metadata_agent.py` is EXIF-only; a real fix means reading PDF-native metadata via `pypdf` directly, not just EXIF/Pillow. ~30 min fix, not yet done.
- Upload reads the whole file into RAM before the size check (fine at the 100MB cap; revisit streaming at Phase 9 deploy).
- Deep models run on CPU currently — GPU wiring is part of the Phase 8 industrial-model upgrade.
- `_fake_class_index()` / fake-label keyword matching depends on the current model's label names — will need revisiting when models are swapped in Phase 8.
- Audio agent's `flagged_segments` is always `[]` — windowed audio scoring is a Phase 8 nicety.
- No API auth (acceptable for a college demo, not for real deployment).
- DWT-DCT watermark decode fails on smooth/gradient images — use textured images for watermark demos.

---

## 10. Obsidian vault — structure & sync tooling

Vault folder: `C:\Users\Divyansh Gupta\Desktop\TrustSphere AI\` (separate from
the code repo — don't confuse the two).

**Structure:** `Phases/` (Phase 1–9 + 7.5 + 7.6 notes), `Agents/` (Metadata/
Image/Video/Audio), `Decisions/` (Decisions Log, Blockers, Demo Flow, Research
Papers, Team Roles), `🏠 Home.md`.

**Sync helper — use it, don't hand-write API calls:** `scripts/obsidian_sync.py`
(run with the backend venv python; only works while the Obsidian app is open).
```powershell
$py = ".\backend\venv\Scripts\python.exe"
& $py scripts\obsidian_sync.py check                                  # is Obsidian reachable?
& $py scripts\obsidian_sync.py list "Phases/"                         # list phase notes
& $py scripts\obsidian_sync.py get  "Phases/Phase 5 - Security.md"    # read a note
& $py scripts\obsidian_sync.py status "Phases/Phase 5 - Security.md" "✅ Done"
& $py scripts\obsidian_sync.py check-tasks "Phases/Phase 5 - Security.md"
& $py scripts\obsidian_sync.py put "Phases/Phase 5 - Security.md" newbody.md
```
**Per-phase ritual (standing rule):** when a phase finishes → `check` (if
OFFLINE, ask the user to open Obsidian) → `status` + `check-tasks` on that
phase's note → tell the user what was updated.

**This document is also pushed into the vault** as
`Decisions/Master Handoff.md`, linked from `🏠 Home.md`, so the full context is
reachable both from the code repo (this file) and from Obsidian.

---

## 11. Demo assets & flow

Test files live in `backend/uploads/` — original/deepfake **pairs** for every
supported media type (images, video, audio, document), generated locally since
the true identity-matched deepfake datasets (FaceForensics++, DFDC) require
gated account access:
- `demo_real.jpg` / `demo_deepfake.jpg` — obvious manipulation
- `demo_hard_real.jpg` / `demo_hard_fake.jpg` — subtle manipulation, real CC0 internet photo as the base
- `demo_video_real.mp4` / `demo_video_deepfake.mp4` — 8s public-domain interview clip, every frame face-warped for the fake version
- `demo_audio_real.wav` / `demo_audio_deepfake.wav` — pitch/formant-shifted voice-conversion artifact
- `demo_document_real.pdf` / `demo_document_deepfake.pdf` — forged `/Producer`/date metadata (see §9 gap — won't currently score differently)

**Demo script (no frontend yet — drive `/docs` Swagger UI):**
1. Upload a fake image → expect low confidence + manipulation type filled in.
2. Upload an authentic/C2PA-valid file → expect fast-tracked Authentic.
3. Upload a video → show the per-frame timeline + manipulation start point.
4. Download the Legal Evidence PDF → heatmaps, chain of custody, blockchain block, signature.
5. Open the Polygon Amoy explorer link → show the real anchored transaction.

Steps involving the browser extension (7.6) and OSINT panel (7.5) are **not
yet built** — don't promise them live in a demo.

---

## 12. Future plans

**Immediate next (Phase 7):** Frontend Dashboard — Next.js + TailwindCSS +
shadcn/ui, dark theme. Pages `/`, `/analyze`, `/result/[id]`. Needs a static
route for heatmap PNGs (currently only paths are stored — add
`/api/heatmap/{file_id}/{kind}` or a StaticFiles mount).

**Then, in order:** 7.5 OSINT (SerpAPI/Google Vision reverse image search),
7.6 Browser Extension (Chrome MV3), 8 Integration+Testing (**industrial model
upgrade goes here** — DFDC-winner EfficientNet-B7 ensemble + MTCNN/RetinaFace
for image/video, AASIST for audio; swap is drop-in via `DEEPFAKE_MODEL_ID`/
`AUDIO_MODEL_ID` env vars), 9 Deployment (Docker Compose, Render backend +
Vercel frontend).

**Advanced detection features (STANDING HOLD — do not build until Phase 7–9
are done AND the user explicitly says to start):** a real prior-art search
(2026-07-09) found close published equivalents for every "novel" technique
considered, so **none of this is a patent claim** — build as genuine project
features / possible publication material instead:
- **Tier 1 (feasible, obscure, strong):** rPPG heartbeat forensics (prototyped
  once, core proven — 72bpm detected on a real-like signal — then reverted
  per user instruction; re-implement from FakeCatcher/DeepRhythm papers when
  given the go-ahead); corneal specular-highlight symmetry; sun/shadow physics
  vs. EXIF GPS+timestamp cross-check.
- **Tier 2 (novel, systems-level):** robust perceptual-hash provenance
  anchoring (survives re-encoding, fixes a real weakness in the current
  SHA-256-only anchor); cross-modal audio-visual consistency (lip-motion vs.
  phonemes).
- **Tier 3 (frontier):** zkML attestation (zero-knowledge proof of correct
  model + verdict without revealing media/weights, via EZKL).

Recommended combo when the time comes: rPPG + sun/shadow physics as one
"physiological & physics consistency" agent, plus perceptual-hash anchoring.

**Honest framing for faculty/coordinator conversations:** "We did a real
prior-art search and found close published work for each technique we
considered, so we're not claiming a patent. Our contribution is the
system-level integration — fusing statistical detection, cryptographic
provenance, and blockchain-anchored evidence into one explainable pipeline —
which we're treating as a possible publication angle rather than a patent
filing." This is a stronger answer to a skeptical reviewer than overclaiming.

---

## 13. Team roles (if group project)

| Role | Responsibility |
|---|---|
| Person 1 | AI Agents (Image + Video) + GAN Fingerprinting |
| Person 2 | AI Agents (Audio + Metadata) + Manipulation Type Classifier |
| Person 3 | Backend API + Blockchain + C2PA + OSINT |
| Person 4 | Frontend Dashboard + XAI + Video Timeline + Browser Extension |

---

## 14. How to onboard a new Claude Code session (new account or new machine)

1. Read this file first.
2. Then read `PROJECT_STATE.md` (durable reference — status table, run commands, gotchas) and `HANDOFF.md` (session-to-session baton — what just happened, what's next) in the repo root.
3. Then read the full 33-day plan file if implementing a specific phase in
   depth: `C:\Users\Divyansh Gupta\.claude\plans\i-have-a-project-fluttering-charm.md`
   (**this lives outside the code repo, under the local Claude plans folder —
   see §15 for what that means when migrating accounts**).
4. Confirm `backend/.env` exists and is populated (§8) before running anything.
5. Standing rules to keep following: update `PROJECT_STATE.md` + `HANDOFF.md`
   every session; run the Obsidian per-phase ritual (§10) when a phase
   completes; don't re-suggest already-decided things (CrewAI, quantum,
   Mumbai vs Amoy — see §6); don't build the Tier 1–3 future features (§12)
   without an explicit go-ahead.

---

## 15. Migrating to a new Claude Code account — what actually needs to move

**What's account-independent (travels with the files, not the login):**
- The code repo itself (`trustsphere-ai/`) — copy the whole folder, or better, push it to a git remote and clone it fresh (see below).
- The Obsidian vault (`TrustSphere AI/`) — copy the whole folder; re-point Obsidian's Local REST API plugin at it and regenerate `OBSIDIAN_API_KEY` if needed.
- This `MASTER_HANDOFF.md`, `PROJECT_STATE.md`, `HANDOFF.md` — all inside the repo, git-tracked, travel automatically if you copy/clone the repo.

**What does NOT automatically travel — and why this document exists:**
- The **auto-memory** system (the `trustsphere-project.md` "living memory" file
  a Claude session builds up over time) is stored locally under
  `C:\Users\Divyansh Gupta\.claude\projects\<hashed-directory-path>\memory\` —
  keyed to a local directory path, and *possibly* to the logged-in account too
  (not fully verified). **Do not assume it will show up for a new account or a
  new machine.** That's exactly why this document exists: it's the
  account-independent substitute. Tell the new session to read it as step 1.
- The `.claude/plans/*.md` file (the 33-day plan) lives outside the repo, in
  the local Claude Code user directory — same caveat. **Copy this specific
  file into the repo** (or reference its content from this document, which it
  already is, in condensed form in §12) so it isn't lost on migration.
- `backend/.env` is gitignored on purpose (secrets) — **must be manually
  recreated** on the new setup using §8's variable list and your own copies of
  the actual secret values (DB password, Polygon private key, Obsidian API
  key, etc.). Never commit these.
- Local machine installs: Ollama + the `llama3.1:8b` model, ffmpeg, the Python
  venv, CUDA torch if using the GPU — none of this is account-related, but all
  of it needs reinstalling on a genuinely new machine (not needed if it's the
  same machine, just a different Claude Code login).

**Recommended concrete steps:**
1. If not already done: `git init` in the repo (if not already a git repo) and
   push to a **private** GitHub remote — ask before doing this, since creating
   a remote/pushing is a "shares state" action. This makes the code migration
   a `git clone` instead of a manual folder copy, and is generally worth doing
   regardless of the account move.
2. Copy the Obsidian vault folder (`TrustSphere AI/`) to wherever it'll live
   next — Obsidian vaults are just folders, no special export needed.
3. Log into the new account in Claude Code (`claude` then the login flow, or
   set `ANTHROPIC_API_KEY` if using API-key auth instead of a Claude.ai
   subscription login — the exact command may have changed since this was
   written; check `claude --help` or the in-app login prompt).
4. Open a Claude Code session **from the repo directory** and give it this
   file's path as the very first instruction — that fully substitutes for
   whatever the memory system does or doesn't carry over.
5. Recreate `backend/.env` (§8), reinstall local tooling (Ollama, ffmpeg,
   venv), and run the "how to run" commands (§8) to confirm everything still
   works before continuing feature work.
