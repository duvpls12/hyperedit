# SOP: HyperEdit QC Gate

## Objective

Run applicable quality gate checks for a specific pipeline stage. Output a structured `_qc_result.json` with per-gate pass/warn/fail results. Block the pipeline on any `fail` result that has a non-retry resolution.

## Trigger

Invoked by `/hyperedit-qc-gate <stage>` where stage is one of:
`footage_intake | photo_to_video | audio | assembly | color | text_graphics | final`

## Inputs

- Stage name (argument)
- `state/agents/<project_id>/` — all artifacts written so far
- `skills/hyperedit-orchestrator/CONTEXT.md` — gate thresholds
- `state/intel/` — RAG-indexed rulebook (optional: query for heuristics)

## Prerequisites

- All artifacts for the specified stage must exist (written by the agent that just ran).
- `state/agents/<project_id>/00_project_brief.json` must exist (for project-level thresholds).

---

## Procedure

### Step 1: Load project brief and thresholds

Read `00_project_brief.json` to get:
- `quality_gates.hook_window_seconds` (default: 5)
- `quality_gates.rehook_interval_seconds` (default: 8)
- `quality_gates.directional_continuity_min` (default: 0.8)
- `quality_gates.audio_loudness_lufs` (default: -14)
- `caption_required` (for skip conditions)

### Step 2: Load relevant artifacts

Load artifacts for the specified stage (see stage-to-artifact mapping below).

### Step 3: Run gate checks

Execute the applicable gate checks (see gates below).

### Step 4: Write result

Write `state/agents/<project_id>/<stage>_qc_result.json`:

```json
{
  "status": "pass | warn | fail",
  "blocking_issues": [],
  "assumptions": [],
  "open_questions": [],
  "source_references": [
    {"type": "artifact", "path": "state/agents/<project_id>/<artifact>"}
  ],
  "project_id": "<project_id>",
  "stage": "<stage>",
  "created_at": "<ISO8601>",
  "overall": "pass | warn | fail",
  "gates": [
    {
      "gate_id": "<gate_id>",
      "gate_name": "<human readable>",
      "result": "pass | warn | fail",
      "actual_value": <measured value>,
      "threshold": <expected value>,
      "detail": "<explanation of result>"
    }
  ]
}
```

---

## Gate Definitions

### FOOTAGE INTAKE gates

**G-01: artifact_validity**
- Check: all three artifacts exist, are valid JSON, have `status != "fail"`, have `blocking_issues: []`
- Pass: all valid
- Warn: any warn-status artifact
- Fail: any fail-status or missing artifact

**G-02: selects_coverage**
- Check: `11_selects_shortlist.total_selected >= 8` (minimum shot pool for a 60-90s video)
- Pass: ≥ 8 selects
- Warn: 5-7 selects
- Fail: < 5 selects

### PHOTO-TO-VIDEO gates (conditional)

**G-10: realism_qc_pass**
- Check: `22_realism_qc.approved_clips` list is non-empty
- Pass: at least one approved clip per blocking gap
- Warn: some gaps still unfilled after generation
- Fail: no clips approved (realism failed for all)

**G-11: motion_artifacts**
- Check: no clips in `22_realism_qc.qc_checks` have `motion_artifacts: true`
- Pass: zero motion artifacts
- Warn: 1-2 clips with minor artifacts (still usable)
- Fail: > 2 clips with blocking artifacts

### AUDIO gates

**G-20: bpm_confidence**
- Check: `32_audio_qc.bpm_confidence >= 0.8`
- Pass: ≥ 0.8
- Warn: 0.6-0.8
- Fail: < 0.6

**G-21: beat_grid_alignment**
- Check: `32_audio_qc.beat_grid_alignment_score >= 0.9`
- Pass: ≥ 0.9
- Warn: 0.75-0.9
- Fail: < 0.75

**G-22: loudness**
- Check: `32_audio_qc.loudness_lufs` within ±2 dB of target from project brief
- Pass: within ±1 dB
- Warn: within ±2 dB
- Fail: outside ±3 dB or `clipping_detected: true`

**G-23: duration_match**
- Check: `32_audio_qc.duration_match == true`
- Pass: music covers target duration
- Warn: music is 10-20% shorter than target
- Fail: music is > 20% shorter

### ASSEMBLY gates

**G-30: hook_timing**
- Check: `42_picture_lock.hook_present == true`
- Measure: first high-energy clip in timeline should land in first `hook_window_seconds`
- Pass: hook present and within window
- Warn: hook present but past window by ≤ 2s
- Fail: no hook or hook more than 2s past window

**G-31: rehook_cadence**
- Check: `42_picture_lock.rehook_count >= floor(total_duration / rehook_interval_seconds) - 1`
- Pass: adequate rehooks
- Warn: 1 fewer rehook than expected
- Fail: 2+ fewer rehooks than expected

**G-32: directional_continuity**
- Check: `42_picture_lock.directional_continuity_score >= directional_continuity_min`
- Pass: ≥ 0.8
- Warn: 0.6-0.8
- Fail: < 0.6

**G-33: beat_alignment**
- Check: inspect timeline entries in `42_picture_lock.timeline` — count cuts with `beat_anchor_seconds` set
- Pass: ≥ 80% of cuts have a beat anchor assigned
- Warn: 60-80% have beat anchors
- Fail: < 60% have beat anchors

### COLOR gates

**G-40: color_after_lock**
- Check: `52_color_qc.color_applied_after_lock == true`
- Pass: true
- Fail: false (pipeline order violation — critical)

**G-41: cross_clip_consistency**
- Check: `52_color_qc.cross_clip_consistency_score >= 0.75`
- Pass: ≥ 0.75
- Warn: 0.5-0.75
- Fail: < 0.5

**G-42: no_clipping**
- Check: `52_color_qc.clipping_detected == false`
- Pass: no clipping
- Fail: clipping detected

### TEXT & GRAPHICS gates (conditional)

**G-50: safe_area_compliance**
- Check: `62_graphics_qc.all_safe_area_compliant == true`
- Pass: all elements compliant
- Fail: any element outside safe area

**G-51: word_count**
- Check: `62_graphics_qc.max_words_per_chunk <= 5`
- Pass: ≤ 5 words per chunk
- Fail: any chunk > 5 words

**G-52: timing_alignment**
- Check: `62_graphics_qc.timing_aligned_to_audio == true`
- Pass: captions sync to transcript timing
- Warn: minor drift (< 0.3s)
- Fail: misaligned

### FINAL gates (cross-stage rollup)

**G-99: all_artifacts_written**
- Check: all expected artifacts for run stages exist and are valid JSON
- Pass: all present
- Fail: any missing

**G-100: no_blocking_issues**
- Check: no artifact has non-empty `blocking_issues`
- Pass: all `blocking_issues: []`
- Fail: any artifact has blocking issues

**G-101: overall_grade**
- Check: counts of fail/warn/pass across all stage gate results
- A: zero fails, ≤ 2 warns
- B: zero fails, > 2 warns
- C: one fail (non-pipeline-order)
- D: two fails
- FAIL: any pipeline-order fail OR three+ fails

---

## Output example

```json
{
  "status": "pass",
  "blocking_issues": [],
  "assumptions": [],
  "open_questions": [],
  "source_references": [
    {"type": "artifact", "path": "state/agents/3213_cliff_drive_20260227/42_picture_lock.json"}
  ],
  "project_id": "3213_cliff_drive_20260227",
  "stage": "assembly",
  "created_at": "2026-02-27T14:30:00Z",
  "overall": "pass",
  "gates": [
    { "gate_id": "G-30", "gate_name": "hook_timing", "result": "pass", "actual_value": 3.2, "threshold": 5, "detail": "Hook clip at 0.0-3.2s — well within 5s window" },
    { "gate_id": "G-31", "gate_name": "rehook_cadence", "result": "pass", "actual_value": 8, "threshold": 7, "detail": "8 rehooks for 90s video — adequate" },
    { "gate_id": "G-32", "gate_name": "directional_continuity", "result": "pass", "actual_value": 0.87, "threshold": 0.8, "detail": "0.87 continuity score" },
    { "gate_id": "G-33", "gate_name": "beat_alignment", "result": "warn", "actual_value": 0.71, "threshold": 0.8, "detail": "71% cuts have beat anchors — 10 of 14 cuts aligned" }
  ]
}
```

## Failure Handling

- **Gate fail with retry resolution**: Report BLOCKED to orchestrator with gate details. Orchestrator retries the failed stage.
- **Gate fail with no retry**: For pipeline-order violations (G-40 color_after_lock), report FAIL — do not retry.
- **Missing artifact**: Report BLOCKED — stage did not complete fully.
- **Unreadable artifact (invalid JSON)**: Report BLOCKED — artifact is corrupt.

## Downstream Dependencies

- Orchestrator reads QC gate result before advancing to next stage.
- Final QA reads all stage gate results to compute overall grade card.
