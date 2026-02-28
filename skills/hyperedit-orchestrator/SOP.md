# SOP: HyperEdit Orchestrator

## Objective

Deliver a publish-ready real estate video by coordinating 7 pipeline stages (6 specialist agents + QA) with deterministic handoffs, quality gates, schema validation, and durable execution state via the run-ledger.

## Trigger

User provides a client brief (JSON file path or inline) and invokes `/hyperedit-orchestrator` or `/hyperedit-run`.

## Inputs

- Client brief (property address, footage directory, target duration, delivery format, music style, caption flag)
- Optional: existing `state/run-ledger/<project_id>.json` for resume

## Prerequisites

- Raw footage directory exists and is readable
- `scripts/validate-artifact.js` is present
- `schemas/` directory contains all 24 artifact schemas
- FFmpeg server is running on port 3333 (for footage intake and assembly stages)

---

## Procedure

### Phase 0: Initialize

**Step 1 — Parse brief and generate project_id**

```
project_id = <property_slug>_<YYYYMMDD>  e.g. 3213_cliff_drive_20260227
artifacts_dir = state/agents/<project_id>/
```

Create `artifacts_dir` if it does not exist.

**Step 2 — Check for existing run-ledger (resume)**

- If `state/run-ledger/<project_id>.json` exists:
  - Read it. Find the first stage with `status != "done"` and `status != "skipped"`.
  - Resume from that stage (skip completed stages).
  - Log: `RESUMING from stage: <stage_name>`
- If no run-ledger exists:
  - Proceed with full pipeline initialization.

**Step 3 — Write `00_project_brief.json`**

Write to `state/agents/<project_id>/00_project_brief.json`:
```json
{
  "status": "pass",
  "blocking_issues": [],
  "assumptions": [],
  "open_questions": [],
  "source_references": [],
  "project_id": "<project_id>",
  "property_address": "<from brief>",
  "footage_directory": "<from brief>",
  "target_duration_seconds": <from brief>,
  "delivery_format": { "aspect_ratio": "16:9", "resolution": "1920x1080", "fps": 30 },
  "music_style": "<from brief or default: 'uplifting modern, 120-130 BPM'>",
  "caption_required": <from brief or false>,
  "quality_gates": {
    "hook_window_seconds": 5,
    "rehook_interval_seconds": 8,
    "directional_continuity_min": 0.8,
    "audio_loudness_lufs": -14
  }
}
```

Validate: `node scripts/validate-artifact.js state/agents/<project_id>/00_project_brief.json`

**Step 4 — Initialize run-ledger**

Write `state/run-ledger/<project_id>.json` with all 8 stages as `pending`:

```json
{
  "project_id": "<project_id>",
  "created_at": "<ISO8601>",
  "updated_at": "<ISO8601>",
  "current_stage": "orchestrator_init",
  "client_brief_path": "state/agents/<project_id>/00_project_brief.json",
  "artifacts_dir": "state/agents/<project_id>/",
  "stages": [
    { "name": "orchestrator_init", "status": "done", "artifacts": [...], "blockers": [] },
    { "name": "footage_intake", "status": "pending", "artifacts": [], "blockers": [] },
    { "name": "photo_to_video", "status": "pending", "artifacts": [], "blockers": [] },
    { "name": "audio", "status": "pending", "artifacts": [], "blockers": [] },
    { "name": "assembly", "status": "pending", "artifacts": [], "blockers": [] },
    { "name": "color", "status": "pending", "artifacts": [], "blockers": [] },
    { "name": "text_graphics", "status": "pending", "artifacts": [], "blockers": [] },
    { "name": "orchestrator_qc", "status": "pending", "artifacts": [], "blockers": [] }
  ]
}
```

**Step 5 — Write `01_orchestration_plan.json`**

Include stage sequence, conditional flags, and quality gate definitions. Reference `00_project_brief.json`.

---

### Phase 1: Footage Intake

**Step 6 — Dispatch `/hyperedit-footage-intake`**

Update run-ledger: `stages[footage_intake].status = "in_progress"`.

Provide context:
- `00_project_brief.json` path
- Footage directory
- FFmpeg server endpoint: `http://localhost:3333`
- LM Studio vision endpoint (if configured)

**Step 7 — Validate outputs**

On completion, validate all three artifacts:
```
node scripts/validate-artifact.js state/agents/<project_id>/10_footage_catalog.json
node scripts/validate-artifact.js state/agents/<project_id>/11_selects_shortlist.json
node scripts/validate-artifact.js state/agents/<project_id>/12_gap_report.json
```

If any artifact has `status: "fail"` or validation fails:
- Try retry (max 2 attempts).
- On second failure: mark `stages[footage_intake].status = "blocked"`, add blockers, STOP and report.

Update run-ledger: `stages[footage_intake].status = "done"`.

---

### Phase 2: Photo-to-Video (Conditional)

**Step 8 — Check gap report**

Read `12_gap_report.json`. Check `has_blocking_gaps` field.

- If `false`: mark `stages[photo_to_video].status = "skipped"`, `skip_reason = "No blocking gaps"`. Continue to audio.
- If `true`: dispatch `/hyperedit-photo-to-video`.

**Step 9 — Dispatch and validate (if running)**

Validate:
```
node scripts/validate-artifact.js state/agents/<project_id>/20_synthetic_plan.json
node scripts/validate-artifact.js state/agents/<project_id>/21_generated_clips.json
node scripts/validate-artifact.js state/agents/<project_id>/22_realism_qc.json
```

---

### Phase 3: Audio

**Step 10 — Dispatch `/hyperedit-audio`**

⚠️ CRITICAL: Audio MUST complete before assembly. The radio edit drives all cut timing.

Provide context:
- `11_selects_shortlist.json` (for duration/pacing reference)
- Music library path
- Target duration from `00_project_brief.json`
- FFmpeg server endpoint for BPM detection

**Step 11 — Validate outputs**

```
node scripts/validate-artifact.js state/agents/<project_id>/30_music_map.json
node scripts/validate-artifact.js state/agents/<project_id>/31_radio_edit.json
node scripts/validate-artifact.js state/agents/<project_id>/32_audio_qc.json
```

Invoke `/hyperedit-qc-gate` for audio stage. If gate fails: retry or escalate.

---

### Phase 4: Assembly

**Step 12 — Dispatch `/hyperedit-assembly`**

Provide ALL required inputs:
- `11_selects_shortlist.json`
- `21_generated_clips.json` (only if photo-to-video ran and has approved clips)
- `30_music_map.json` — beat grid + phrase anchors
- `31_radio_edit.json` — segment timing + beat anchors

**Step 13 — Validate outputs**

```
node scripts/validate-artifact.js state/agents/<project_id>/40_rough_cut.json
node scripts/validate-artifact.js state/agents/<project_id>/41_refine_cut.json
node scripts/validate-artifact.js state/agents/<project_id>/42_picture_lock.json
```

Invoke `/hyperedit-qc-gate` for assembly stage.

Key gate: `directional_continuity_score >= 0.8` in `42_picture_lock.json`.

---

### Phase 5: Conform + Color

**Step 14 — Confirm picture lock**

Verify `42_picture_lock.json` exists and `status == "pass"`. DO NOT dispatch color before picture lock is confirmed.

The picture lock was built from 720p proxy files. This step replaces proxies with full-resolution graded footage — **only for clips in the final cut**.

**Step 15 — Dispatch `/hyperedit-color`**

Provide:
- `42_picture_lock.json` (contains proxy→source mapping + clip list with in/out points)
- `<project>/shot-catalog.json` (camera, color profile, LUT path per clip)
- Raw footage paths (resolved from proxy→source mapping)
- LUT library: `/Volumes/Charlie/hyperedit-studio/assets/luts/`
- ComfyUI local endpoint: `http://localhost:8188`
- color-matcher CLI path

The Color agent will:
1. **Conform** — resolve proxy→source mapping, verify all raw files accessible
2. **Grade** — apply log conversion LUT + correction + creative look to full-res source clips
3. **Export** — write graded clips to `<project>/graded/`

**Step 16 — Validate outputs**

```
node scripts/validate-artifact.js state/agents/<project_id>/50_base_corrections.json
node scripts/validate-artifact.js state/agents/<project_id>/51_look_layers.json
node scripts/validate-artifact.js state/agents/<project_id>/52_color_qc.json
```

Verify `<project>/graded/` contains graded files for all clips in the picture lock.

Invoke `/hyperedit-qc-gate` for color stage.

---

### Phase 6: Text & Graphics (Conditional)

**Step 17 — Check brief**

Read `00_project_brief.json`. Check `caption_required` field.

- If `false`: mark `stages[text_graphics].status = "skipped"`, `skip_reason = "Captions not required per brief"`. Continue to QC.
- If `true`: dispatch `/hyperedit-text-graphics`.

**Step 18 — Validate outputs (if running)**

```
node scripts/validate-artifact.js state/agents/<project_id>/60_caption_script.json
node scripts/validate-artifact.js state/agents/<project_id>/61_graphics_layout.json
node scripts/validate-artifact.js state/agents/<project_id>/62_graphics_qc.json
```

Invoke `/hyperedit-qc-gate` for graphics stage.

---

### Phase 7: Final QA & Grading

**Step 19 — Invoke `/hyperedit-qc-gate` (final pass)**

Run the universal QC gate across ALL artifact results from all stages.

**Step 20 — Write `70_final_qc_report.json`**

Cross-stage validation: check all mandatory quality gates (see Quality Gates below).

**Step 21 — Write `71_grade_card.json`**

Score all dimensions: hook_strength, pacing, directional_continuity, color_consistency, audio_quality, caption_readability (if applicable).

**Step 22 — Write `72_publish_checklist.json`**

All checklist items must be checked. If any fail, set `publish_ready: false` and list blockers.

**Step 23 — Update run-ledger**

Mark `stages[orchestrator_qc].status = "done"` and `current_stage = "done"`.

---

## Quality Gates (enforced by orchestrator + `/hyperedit-qc-gate`)

| Gate | Check | Fail Action |
|------|-------|-------------|
| Hook timing | Compelling shot in first 3-5s | Retry assembly |
| Rehook cadence | Rehook every 5-10s | Warn or retry assembly |
| Directional continuity | Score >= 0.8 | Retry assembly |
| Music-edit alignment | Cuts land on beat anchors | Warn or retry assembly |
| Color after lock | `color_applied_after_lock: true` in 52_color_qc | FAIL if false |
| Safe area compliance | All captions within 9:16 safe area | Retry graphics |
| Audio loudness | -14 LUFS target (±2 dB) | Warn |
| No blocking issues | Every artifact `blocking_issues: []` | FAIL |

---

## Retry Policy

- Max **2 retries per stage** before escalating.
- On retry: re-dispatch only the failed stage and its downstream dependents.
- Do NOT reopen upstream stages unless root cause is confirmed upstream.
- On escalation: write blocker to run-ledger and report `BLOCKED: <reason>` to user.

## Failure Handling

- **Artifact validation failure**: Re-run stage with specific error context.
- **QC gate failure**: Retry stage or accept as warn if non-blocking.
- **ComfyUI unavailable**: Queue GPU tasks, continue with non-GPU stages.
- **FFmpeg server down**: BLOCKED — cannot proceed without FFmpeg server.
- **Catastrophic**: Save run-ledger state, report `BLOCKED` with full context for manual recovery.

## Downstream Dependencies

None — this is the top-level orchestrator. Output is delivered to client.

## Outputs

- `state/run-ledger/<project_id>.json` — complete execution record
- `state/agents/<project_id>/00_project_brief.json` → `72_publish_checklist.json` — all 24 numbered artifacts
- Final video export (written by assembly agent via FFmpeg server)
