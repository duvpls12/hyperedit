# SOP - Master Orchestrator

## Objective

Deliver a complete, publish ready real estate video by coordinating six specialist agents with minimal rework.

## Inputs

- Project brief and target platform.
- Source footage manifest.
- Script and dialogue assets.
- Brand constraints.
- Deadlines and runtime targets.

## Procedure

1. Create project skeleton in `state/agents/<project_id>/`.
2. Write `00_project_brief.json` with format target (`reel`, `mls`, `signature`).
3. Define quality gates in `02_quality_gates.json`.
4. Dispatch Footage Intake and Sorting.
5. If gaps exist, dispatch Image to Video Generation for only blocking gaps.
6. Dispatch Assembly Editor using approved shot pool.
7. Dispatch Color Pipeline after assembly lock.
8. Dispatch Graphics and Captions after picture lock.
9. Dispatch Audio and Sound Design after picture lock; allow minor recut only if audio sync demands it.
10. Run final cross stage QC and output `70_final_qc_report.json`.

## Mandatory quality gates

- Hook appears in first 3-5 seconds.
- At least one rehook every 5-10 seconds for social formats.
- Movement continuity score >= 0.8 (direction and motion logic).
- Wide/detail alternation present; avoid long run of same shot type.
- No unresolved color mismatch warnings between adjacent clips.
- Every speed ramp has matching audio accent.
- Captions safe area and legibility pass on 9:16 mobile viewport.
- Final loudness and speech intelligibility meet platform target.

## Retry policy

- If gate fails, rework only failed stage and downstream dependents.
- Do not reopen upstream stages unless failure root cause is upstream.
- Max two retries per stage before escalating with explicit blockers.

## Outputs

- `01_orchestration_plan.json`
- `70_final_qc_report.json`
- `71_publish_checklist.md`
