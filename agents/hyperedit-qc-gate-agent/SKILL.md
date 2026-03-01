---
name: hyperedit-qc-gate
description: Universal quality gate checker invoked between every pipeline stage. Validates hook timing, rehook cadence, directional continuity, music-edit alignment, color ordering, safe-area compliance, and audio loudness. Writes a per-gate pass/warn/fail result JSON.
metadata:
  tags: hyperedit,qc,validation,quality-gate
---

# HyperEdit QC Gate Skill

## When to use

Invoked by the orchestrator between every pipeline stage and at final QA. Also callable directly to check a specific stage's output.

## Claude Code trigger

Invoke as `/hyperedit-qc-gate` with the stage name as argument.

Example: `/hyperedit-qc-gate assembly`

## How to use

1. Read [SOP.md](SOP.md) for gate definitions and check procedures.
2. Read upstream artifacts for the specified stage.
3. Run each applicable gate check.
4. Write `<stage>_qc_result.json` to `state/agents/<project_id>/`.

## Stage-to-gate mapping

| Stage | Gates Applied |
|-------|---------------|
| footage_intake | artifact_validity, selects_coverage |
| photo_to_video | realism_qc, motion_artifacts |
| audio | bpm_confidence, beat_grid_alignment, loudness, duration_match |
| assembly | hook_timing, rehook_cadence, directional_continuity, beat_alignment |
| color | color_after_lock, cross_clip_consistency, clipping |
| text_graphics | safe_area, word_count, timing_alignment |
| final | all_gates (cross-stage rollup) |

## Outputs

- `state/agents/<project_id>/<stage>_qc_result.json`
  - Schema: `{ stage, overall: pass|warn|fail, gates: [{ gate_id, result, actual, threshold, detail }] }`

## Shared references

- Rulebook: `state/intel/` (RAG-indexed patterns and heuristics)
- Common schema: [schemas/_common.schema.json](../../schemas/_common.schema.json)
- Orchestrator thresholds: [skills/hyperedit-orchestrator/CONTEXT.md](../hyperedit-orchestrator/CONTEXT.md)
