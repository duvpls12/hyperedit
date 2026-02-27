# SOP: Session Continuity & Restore

## Objective

Detect interrupted pipeline runs, restore agent state from the run-ledger, and resume execution from the last completed stage without re-running successful work or losing committed artifacts.

## Trigger

Invoked when:
- User invokes `/hyperedit-session-restore <project_id>`.
- Orchestrator detects an in-progress run-ledger on startup.
- FFmpeg server `/session-continuity` endpoint returns `stale` or `interrupted` sessions.
- Agent process exited unexpectedly mid-stage.

## Inputs

| Input | Source | Schema |
|-------|--------|--------|
| Project ID | User input or auto-detected from latest run-ledger | — |
| Run-ledger | `state/run-ledger/<project_id>.json` | `schemas/run_ledger.schema.json` |
| Existing artifacts | `state/agents/<project_id>/` | Per-stage schemas |
| FFmpeg session state | `state/local-ffmpeg/sessions/{sessionId}/` | — |
| FFmpeg heartbeat | `state/local-ffmpeg/sessions/{sessionId}/heartbeat.json` | — |

## Prerequisites

- `state/run-ledger/<project_id>.json` exists.
- `state/agents/<project_id>/` directory exists with at least `00_project_brief.json`.
- FFmpeg server running on `localhost:3333`.

## Procedure

1. **Load run-ledger.**
   - Read `state/run-ledger/<project_id>.json`.
   - Identify `current_stage` and each stage's `status`: `pending`, `in_progress`, `done`, `blocked`, `gpu_pending`.
   - Expected output: run state map.

2. **Audit existing artifacts.**
   - For each stage with `status: "done"`: verify its artifacts exist on disk and pass schema validation.
   - `scripts/validate-artifact.js --project <project_id> --stage <stage>`.
   - Expected output: per-stage artifact audit results — `valid`, `corrupt`, `missing`.

3. **Restore FFmpeg session.**
   - Read `state/local-ffmpeg/sessions/{sessionId}/heartbeat.json` → `lastSeen`.
   - If `lastSeen` within 120s: session is live, reconnect.
   - If `lastSeen` > 120s (stale): session is invalid.
     - Clear `localStorage` session reference (if applicable).
     - Create new FFmpeg session: `POST /session/create`.
     - Re-upload assets from `state/agents/<project_id>/` to new session.
   - Expected output: active session_id.

4. **Determine resume point.**
   - Stages with `status: "done"` and valid artifacts: **skip** — do not re-run.
   - Stages with `status: "in_progress"` and partial artifacts: **restart from beginning of that stage** — partial work is not trusted.
   - Stages with `status: "pending"`: run in dependency order.
   - Stages with `status: "gpu_pending"`: check GPU endpoint availability. If available, dispatch now.
   - Expected output: resume_from_stage and stage_skip_list.

5. **Re-initialize run-ledger for resume.**
   - For interrupted stage: reset `status: "in_progress"` → `"pending"`.
   - Keep all `"done"` stages as-is.
   - Record `resumed_at` timestamp in run-ledger.
   - Expected output: run-ledger updated for clean resume.

6. **Resume pipeline from resume point.**
   - Dispatch `skills/hyperedit-orchestrator/` with `resume_mode: true`, `skip_stages: [list]`.
   - Orchestrator re-dispatches from `resume_from_stage` forward.
   - Expected output: pipeline continues from correct stage.

7. **Report restore status.**
   - Write restore report: stages skipped, stages restarted, artifacts recovered.
   - Expected output: `state/agents/<project_id>/restore_report.json`.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| Run-ledger readable and valid | Valid JSON | Minor format issues | Corrupt / unreadable |
| Done-stage artifacts valid | All valid | 1 artifact warn | Any corrupt / missing |
| FFmpeg session restored | Active session | Stale session recovered | Session lost (re-upload needed) |
| Resume point identified | Clear resume point | — | Ambiguous state |
| No duplicate stage execution | 0 re-runs of done stages | — | Any done stage re-run |

## Outputs

| Artifact | Path |
|----------|------|
| Restore report | `state/agents/<project_id>/restore_report.json` |
| Updated run-ledger | `state/run-ledger/<project_id>.json` |

## Failure Handling

- **Run-ledger corrupt or missing**: Cannot restore. Start fresh run OR attempt to reconstruct from existing artifacts in `state/agents/<project_id>/`. Prompt user for direction.
- **Done-stage artifact corrupt**: Re-run that stage and all downstream dependents. Do not skip corrupt data.
- **FFmpeg session assets lost**: Re-upload from `state/agents/<project_id>/` source files. If source footage also lost, surface as `BLOCKED`.
- **GPU queue stale**: Re-queue GPU tasks. Check Vast.ai instance status. If GPU unavailable, see `13-fallback-escalation.md`.
- **Retry policy**: Session restore is attempted once. On failure, surface specific error to user.
- **Escalation**: If resume is impossible, surface full project state to user and request direction (restart vs. continue).

## Downstream Dependencies

- Completing this SOP enables: full pipeline to resume from interruption point.
- Related: `10-rag-commit.md` — any pending RAG commits from interrupted stages are committed on resume.

## Skill Cross-Reference

- Skill: `skills/hyperedit-session-restore/SKILL.md`
- Run-ledger schema: `schemas/run_ledger.schema.json`
- FFmpeg session state: `state/local-ffmpeg/sessions/`
- FFmpeg endpoint: `GET /session-continuity` (heartbeat + stale session detection)
- Session persistence: `localStorage` key `clipwise-session` (see CLAUDE.md)
