# SOP: Fallback & Escalation

## Objective

Define the retry policy, fallback ladder, and escalation path for every failure mode across the pipeline. Every agent must consult this SOP when a stage fails, before marking it `blocked`.

## Trigger

Invoked when any stage agent encounters a failure, timeout, or quality gate violation that cannot be resolved on the first pass.

## Inputs

| Input | Source |
|-------|--------|
| Failed stage artifact | `state/agents/<project_id>/<stage_artifact>.json` |
| Blocking issue description | Artifact `blocking_issues[]` field |
| Run-ledger current state | `state/run-ledger/<project_id>.json` |
| Stage name | Run-ledger `current_stage` |

## Prerequisites

- Stage has attempted execution at least once.
- Blocking issue is documented in artifact `blocking_issues[]`.

---

## Fallback Ladders

### Vision Model Fallback (Footage Intake, Photo-to-Video)

| Priority | Model | Use When |
|----------|-------|----------|
| 1 (preferred) | 11B vision model | Available and stable |
| 2 | 8B vision model | 11B load failure or inference error |
| 3 | 4B vision model | 8B failure |
| 4 | `unclassified` tag | All models fail |

Policy:
1. Try 11B first.
2. On 11B failure: unload, demote to 8B, restart current clip pass.
3. On 8B failure: unload, demote to 4B, restart current clip pass.
4. On 4B failure: write `<clip_id>_unclassified.json`, continue batch without that clip.
5. Every artifact must include `vision_model_used` and `vision_fallback_chain` fields.

### GPU (ComfyUI/LTXVideo) Fallback

| Priority | Action |
|----------|--------|
| 1 | Dispatch to Vast.ai GPU endpoint |
| 2 | Queue in run-ledger as `gpu_pending`, continue non-GPU stages |
| 3 | Defer generation; assemble without synthetic clips (skip photo-to-video) |

Policy:
1. Attempt Vast.ai endpoint.
2. If unreachable: mark `gpu_pending`, set stage `status: "waiting"` in run-ledger.
3. Continue pipeline: audio, assembly (with existing real clips), color, text/graphics, QA proceed without generated clips.
4. When GPU becomes available: resume photo-to-video stage, re-dispatch assembly if synthetic clips were needed for blocking gaps.
5. If no GPU available within project deadline: skip photo-to-video, mark blocking gaps as `accepted_warn` in assembly.

### Audio BPM Extraction Fallback

| Priority | Action |
|----------|--------|
| 1 | FFmpeg audio analysis on source file (primary) |
| 2 | Re-extract from WAV source if MP3 BPM detection fails (compressed MP3 with heavy low-end can confuse detection) |
| 3 | Retry FFmpeg analysis with alternate flags (e.g., `silencedetect`, `ebur128`) |
| 4 | Manual BPM tap from structural markers |
| 5 | Default BPM grid (120 BPM) with documented assumption |

Policy: If MP3 BPM confidence < 0.6 on first attempt, always try WAV source before manual estimation.

### Transcription Fallback (Text/Graphics)

| Priority | Tool | Use When |
|----------|------|----------|
| 1 | Local Whisper (CPU, `base` model) | Primary |
| 2 | Gemini API transcription | Local Whisper unavailable |
| 3 | Manual caption entry | Gemini struggles with long audio |

Note: Gemini fallback may produce lower accuracy on long audio. Document as `warn`.

### ComfyUI Node Fallback (Color Grading)

| Priority | Tool |
|----------|------|
| 1 | ComfyUI + EasyColorCorrector (local :8188) |
| 2 | color-matcher CLI: `color-matcher -s ./frames/ -r reference.png` |
| 3 | FFmpeg LUT application: `ffmpeg -i input.mp4 -vf lut3d=<lut_path> output.mp4` |

### Export / Render Fallback (Assembly, Delivery)

| Priority | Tool |
|----------|------|
| 1 | ComfyUI VideoHelperSuite (Video Combine) |
| 2 | FFmpeg server `POST /session/{id}/render` |
| 3 | Direct FFmpeg CLI command |

---

## Retry Policy

**Universal retry rules:**
- Max **2 retries** per stage before escalating.
- Always document the failure reason and retry attempt in the artifact's `blocking_issues[]`.
- Only retry with a different approach — identical retry is not allowed.
- Do not reopen upstream stages unless the failure root cause is definitively upstream.
- Rework only the failed stage and its direct downstream dependents.

**Stage-specific retry behaviors:**

| Stage | Retry Approach |
|-------|----------------|
| Footage Intake (vision tagging) | Retry failed clips with next vision model in fallback ladder |
| Photo-to-Video (generation) | Generate 2–3 variants; select best. If all fail: retry with alternate source still |
| Audio (BPM extraction) | Retry with alternate FFmpeg flags; fallback to manual estimation |
| Assembly (continuity) | Swap direction-violating clips, add `straight_reset`, re-validate |
| Color (consistency) | Run second color-matcher pass on outlier clips only |
| Text/Graphics (collision) | Move caption to alternate position zone; reduce size |
| QA (grade C) | Rework top 2 failing gates in their origin stage, re-run QA |

---

## Escalation Path

### Level 1: Auto-Retry (Agent handles)
- Retry within fallback ladder (max 2 attempts).
- Document each attempt in artifact `blocking_issues[]`.
- Continue if partial success is acceptable (`warn` status).

### Level 2: Stage Blocked (Orchestrator handles)
- Agent marks stage `status: "blocked"` in run-ledger.
- Agent writes specific blocker list to artifact.
- Orchestrator evaluates: can pipeline continue without this stage?
  - If yes: mark stage `skipped_with_warn`, continue downstream.
  - If no: halt pipeline, surface to user.

### Level 3: User Escalation
- Triggered by: any Level 2 block that cannot be bypassed.
- Surface to user:
  - Project ID.
  - Stage that blocked.
  - Specific `blocking_issues` list.
  - Recommended resolution (e.g., "provide alternate music track", "check GPU endpoint").
  - Template: use `docs/sops/templates/agent-run-report.md`.

### Level 4: Full Pipeline Halt
- Triggered by: missing required footage, corrupt run-ledger, infrastructure failure.
- Halt all stages immediately.
- Write incident report to `state/intel/incident_status.md`.
- Surface to user with full state dump.

---

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| Failure documented in blocking_issues | Documented | — | Undocumented failure |
| Retry attempted with different approach | New approach used | — | Identical retry |
| Max retry count respected | ≤ 2 retries | — | > 2 retries |
| Escalation reached user before pipeline halt | User notified | — | Silent halt |

## Outputs

Each failure handling produces updates to:
- Stage artifact: `blocking_issues[]`, `retry_log[]`.
- Run-ledger: stage `status`, `retry_count`, `blocked_reason`.
- If Level 3: `docs/sops/templates/agent-run-report.md` filled and surfaced.
- If Level 4: `state/intel/incident_status.md` updated.

## Per-Stage Fallback Quick Reference

| Stage | Primary Failure | Fallback | Escalates If |
|-------|----------------|----------|--------------|
| 01 Kickoff | Missing brief fields | Request user to complete template | Fields still missing |
| 02 Footage Ingest | Vision model fails | 11B→8B→4B→unclassified | All models fail on >10% clips |
| 03 Photo-to-Video | GPU unavailable | Queue as gpu_pending | GPU unavailable past deadline |
| 04 Audio | BPM extraction fails | Manual estimation | No viable music track |
| 05 Assembly | Continuity < 0.7 | Swap clips + reset | Runtime > 10% off after 2 passes |
| 06 Color | EasyColorCorrector fails | color-matcher CLI → FFmpeg LUT | ΔE > 8 after 2 passes |
| 07 Text/Graphics | Caption collision | Move position zone | Collision persists after 2 passes |
| 08 QA/Grading | Grade C | Targeted rework of top 2 gates | Grade D after 2 rework cycles |
| 09 ComfyUI Setup | Node missing | Install missing node, restart | ComfyUI won't start |
| 10 RAG Commit | Qdrant unreachable | Queue to pending file | Non-blocking — never hard escalation |
| 11 Session Restore | Run-ledger corrupt | Reconstruct from artifacts | Cannot determine resume point |
| 12 Delivery | Export fails | Retry with lower bitrate | File unrenderable |

## Skill Cross-Reference

- Referenced by: all stage skills.
- Failure reporting template: `docs/sops/templates/agent-run-report.md`.
- Incident log: `state/intel/incident_status.md`.
- Vision model fallback: `docs/plans/2026-02-25-hyperedit-fallback-sop.md`.
