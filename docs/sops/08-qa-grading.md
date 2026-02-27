# SOP: QA & Grading

## Objective

Cross-stage validation of the complete pipeline output: verify all artifacts pass quality gates, score the edit against the QC rulebook, produce a letter grade with specific deficiency callouts, and make a publish/rework decision.

## Trigger

Dispatched by Orchestrator after all active pipeline stages complete:
- `42_picture_lock.json` exists with `locked: true`.
- `52_color_qc.json` exists (color applied).
- `62_graphics_qc.json` exists OR `text-graphics` stage was skipped.
- All stage artifacts present in `state/agents/<project_id>/`.

## Inputs

| Input | Source | Schema |
|-------|--------|--------|
| All numbered artifacts (00–62) | `state/agents/<project_id>/` | Per-stage schemas |
| Final video (captioned or graded) | `state/agents/<project_id>/` | — |
| Orchestration plan + gates | `state/agents/<project_id>/01_orchestration_plan.json` | `schemas/01_orchestration_plan.schema.json` |
| Music map | `state/agents/<project_id>/30_music_map.json` | `schemas/30_music_map.schema.json` |
| QC rulebook | `state/intel/perfect_video_blueprint.md` | — |

## Prerequisites

- All upstream stage artifacts present (00–62 series, skipped optional stages excluded).
- `42_picture_lock.json` with `locked: true`.
- Color applied: `52_color_qc.json` exists.
- `skills/hyperedit-qc-gate/` installed and callable.

## Procedure

1. **Collect all stage artifacts.**
   - Scan `state/agents/<project_id>/` — confirm all required numbered artifacts present.
   - Build artifact manifest: list all found files vs. expected files per pipeline variant.
   - Expected output: manifest with `found`, `missing`, `skipped_optional`.

2. **Run hook and rehook timing check.**
   - Parse `42_picture_lock.json → clips[0].cut_out_beat` — confirm first hook within 3–5s.
   - Parse all cut timestamps — confirm rehook within 5–10s intervals for social formats.
   - Expected output: `hook_timing_result` (pass/warn/fail) + specific timestamps.

3. **Run directional continuity check.**
   - Re-validate final cut sequence from `42_picture_lock.json` directional tags.
   - Continuity score ≥ 0.8 required.
   - Identify any remaining direction reversals without reset.
   - Expected output: `continuity_result` with score and violation list.

4. **Verify color-applied-after-lock.**
   - Confirm `50_base_corrections.json.created_at > 42_picture_lock.json.locked_at`.
   - No color work should predate picture lock.
   - Expected output: timestamp sequence check result.

5. **Run caption safe area check (if applicable).**
   - Parse `62_graphics_qc.json` — verify all captions within 8% padding safe area (mobile-first, 9:16 viewport).
   - Confirm no caption collision with face or key property feature.
   - Expected output: `captions_safe_area_result`.

6. **Run audio loudness and beat-alignment check.**
   - Verify cuts in `42_picture_lock.json` land on beat markers from `31_radio_edit.json` — ≥ 90% within 1 beat.
   - Check `32_audio_qc.json` for hook timing and rehook compliance.
   - Expected output: `audio_alignment_result`.

7. **Run every speed ramp validation.**
   - Confirm each speed ramp in `42_picture_lock.json` has matching audio accent in `30_music_map.json`.
   - Confirm sufficient footage on each side (≥ 1s).
   - Expected output: `speed_ramp_result`.

8. **Cross-stage blocking issues sweep.**
   - Collect all `blocking_issues` arrays from every artifact.
   - Categorize: unresolved (still blocking), resolved (addressed in later stage), accepted_warn.
   - Expected output: `blocking_issues_summary`.

9. **Invoke hyperedit-qc-gate skill.**
   - Pass all collected check results to `skills/hyperedit-qc-gate/` for unified scoring.
   - QC gate applies rulebook from `state/intel/perfect_video_blueprint.md`.
   - Expected output: per-gate pass/warn/fail with weighted score.

10. **Produce letter grade.**
    - Score each dimension 0–10: `hook_strength`, `pacing`, `directional_continuity`, `color_consistency`, `audio_quality`, `caption_readability` (if applicable).
    - Map overall score to grade: A = publish ready, B = publish with minor notes, C = review needed, D = rework needed, FAIL = blocked.
    - Include specific deficiency callouts (dimension, observation, severity) for each non-passing gate.
    - Expected output: `71_grade_card.json` with dimension scores, overall grade, and callouts.

11. **Publish decision.**
    - A/B: Publish (B with noted warnings).
    - C: Rework — identify top 2 failing dimensions, dispatch targeted rework to affected stage only.
    - D/FAIL: Full rework — surface all deficiencies to user, await direction.
    - Write `72_publish_checklist.json` with all delivery checklist items and `publish_ready` boolean.
    - Expected output: `70_final_qc_report.json`, `71_grade_card.json`, `72_publish_checklist.json`.

12. **Write outputs and validate.**
    - Run schema validation: `scripts/validate-artifact.js` on all three final artifacts.
    - Expected output: all 3 artifacts with `status: "pass"`.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| Hook in first 3–5 seconds | ≤ 5s | 5–7s | > 7s |
| Rehook every 5–10s (social) | All intervals | 1 interval > 10s | >1 interval missed |
| Directional continuity score | ≥ 0.8 | 0.7–0.79 | < 0.7 |
| Color applied after picture lock | Timestamp verified | — | Color predates lock |
| Caption safe area (if applicable) | 100% compliant | — | Any violation |
| Beat-aligned cuts ≥ 90% | ≥ 90% | 80–89% | < 80% |
| Speed ramp has audio accent | 100% | — | Any missing |
| No unresolved blocking issues | 0 unresolved | Accepted warns only | Any unresolved |
| All required artifacts present | All present | — | Any missing |

## Outputs

| Artifact | Path | Schema |
|----------|------|--------|
| Final QC report | `state/agents/<project_id>/70_final_qc_report.json` | `schemas/70_final_qc_report.schema.json` |
| Grade card | `state/agents/<project_id>/71_grade_card.json` | `schemas/71_grade_card.schema.json` |
| Publish checklist | `state/agents/<project_id>/72_publish_checklist.json` | `schemas/72_publish_checklist.schema.json` |

## Failure Handling

- **C grade**: Rework failed stage only and downstream dependents. Do not reopen upstream stages unless root cause is upstream. Max 2 retries before escalating to user.
- **D grade**: Surface full deficiency list to user with specific gate failures. Await explicit direction before rework.
- **Missing required artifact**: Return `BLOCKED: missing artifacts [list]`. Do not proceed to grade.
- **QC gate skill error**: Run manual checks using procedure steps 2–8. Document as `warn`.
- **Retry policy**: Max 2 rework cycles per stage. On persistent failure, escalate to `13-fallback-escalation.md`.
- **Escalation**: See `13-fallback-escalation.md` for full escalation ladder.

## Downstream Dependencies

Completing this SOP:
- **A/B grade**: Unblocks `12-client-delivery.md` (reads `72_publish_checklist.json`).
- **C/D grade**: Dispatches targeted rework to appropriate upstream stage.

## Skill Cross-Reference

- Skill (dispatch): `skills/hyperedit-orchestrator/SKILL.md` (QA phase)
- Skill (gates): `skills/hyperedit-qc-gate/SKILL.md`
- Procedure matches: `skills/hyperedit-agent-master-orchestrator/SOP.md` Step 10 + quality gates
- Context: `skills/hyperedit-agent-master-orchestrator/CONTEXT.md`
- Rulebook: `state/intel/perfect_video_blueprint.md`
