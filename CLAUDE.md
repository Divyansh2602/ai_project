# TrustSphere AI

**Before doing anything, read [`PROJECT_STATE.md`](./PROJECT_STATE.md), then
[`HANDOFF.md`](./HANDOFF.md) in this directory.**
PROJECT_STATE.md is the durable source of truth (status, run commands, runtime gotchas —
Supabase pooler, Redis SSL, HF Xet, GPU — Obsidian sync). HANDOFF.md is the
session-to-session baton: what just happened, in-flight work, and next steps.
**Update HANDOFF.md at the end of every session** (standing user rule).

Quick facts:
- Multi-agent deepfake / synthetic-media forensics system (college project).
- Phases 1–6 done; **Phase 7 (Frontend Dashboard, Next.js) is next**.
  (Phase 5 note: on-chain anchoring is env-gated & skipped until the user deploys the
  contract — PROJECT_STATE.md §5.7. Phase 6 note: LLM summary deferred by user choice.)
- Backend: FastAPI + SQLAlchemy + Celery. DB = Supabase (via **session pooler**). Queue = Upstash Redis.
- Windows + PowerShell. venv at `backend/venv`. Use `.\venv\Scripts\python.exe`.
## Obsidian — update it yourself, automatically

After finishing ANY phase, push the update to the Obsidian vault yourself using the
helper script (do NOT ask the user to do it manually, and do NOT hand-write the API calls):

```powershell
$py = ".\backend\venv\Scripts\python.exe"
& $py scripts\obsidian_sync.py check                                            # reachable?
& $py scripts\obsidian_sync.py status "Phases/Phase N - <name>.md" "✅ Done"
& $py scripts\obsidian_sync.py check-tasks "Phases/Phase N - <name>.md"
```

If `check` says OFFLINE, ask the user to open the Obsidian app, then run it. Always
tell the user what you changed in Obsidian afterward. Full details + all commands: PROJECT_STATE.md §7.

**Pending sync:** none — vault is current through Phase 6 (synced 2026-07-07).
