# SOP: Color Correction & Grading

## Objective

Apply technical correction and creative grading to the picture-locked edit: convert log footage, correct exposure and white balance, shape contrast, apply creative look, match cross-clip consistency, and deliver a fully graded timeline ready for graphics and audio finishing.

## Trigger

Dispatched by Orchestrator after `42_picture_lock.json` is written with `locked: true`. **Must not run before picture lock is confirmed** — grading wasted on cut changes is a known failure mode.

## Inputs

| Input | Source | Schema |
|-------|--------|--------|
| Picture lock | `state/agents/<project_id>/42_picture_lock.json` | `schemas/42_picture_lock.schema.json` |
| Picture lock video | `state/agents/<project_id>/picture_lock.mp4` | — |
| Camera profiles / footage metadata | From `10_footage_catalog.json` | `schemas/10_footage_catalog.schema.json` |
| Look references | `brief.look_references[]` | Image files or LUT paths |
| Style intent | `brief.style_intent` | `cinematic` \| `warm_natural` \| `cool_editorial` \| `flat_neutral` |

## Prerequisites

- `42_picture_lock.json` exists with `locked: true` and `status: "pass"` or accepted `"warn"`.
- ComfyUI running on `localhost:8188`.
- EasyColorCorrector nodes installed in ComfyUI.
- color-matcher CLI installed (`color-matcher --version`).
- Picture lock video file exists at expected path.

## Procedure

1. **Extract frames from picture lock.**
   - Use ComfyUI VideoHelperSuite: Load Video → extract frames at native resolution.
   - Group frames by clip (using cut points from `42_picture_lock.json`).
   - Expected output: frame sequences per clip in temp directory.

2. **Apply log-to-display conversion (if applicable).**
   - If camera profile is log (S-Log, Log-C, V-Log): apply conversion LUT as base layer.
   - Load appropriate conversion LUT — do not apply creative look at this step.
   - Expected output: log footage linearized.

3. **Base exposure and white balance correction (per clip).**
   - Use ComfyUI EasyColorCorrector in `auto` mode for initial pass.
   - Manually review: exposure midpoints, shadow lift, highlight protection.
   - Correct white balance: remove magenta/green casts, match neutral whites.
   - Expected output: exposure and white balance corrected per clip.

4. **Contrast shaping.**
   - Apply mild S-curve: lift shadows slightly, add presence to mids, protect highlights.
   - Use waveform to verify: no clipped highlights (unless artistically intentional), no crushed blacks.
   - Expected output: contrast shaped, scope-verified.

5. **Apply creative look LUT.**
   - Select look from `brief.look_references` or `EasyColorCorrector` preset library (30 looks).
   - Apply at reduced intensity (30–60% opacity) — never full strength unless explicitly requested.
   - For film emulation: use FilmEmulation preset within EasyColorCorrector.
   - Expected output: creative look applied to all clips.

6. **Cross-clip color consistency pass.**
   - Run color-matcher CLI for batch consistency: `color-matcher -s ./frames/ -r reference_frame.png`.
   - Reference frame: the highest-quality clip from the selects.
   - Verify: no visible white balance jumps between adjacent clips, no tint shifts between room transitions.
   - Expected output: `50_base_corrections.json` with per-clip correction data + consistency score.

7. **Handle special cases.**
   - **Window recovery**: apply highlight control + midtone lift for interior window scenes.
   - **Drone footage**: selective exposure balancing for sky/foreground split.
   - **Skin tones** (if talent on screen): isolate with luma key, preserve warmth.
   - **Day-to-night transitions**: only add glow/atmosphere if narratively motivated and documented.
   - Expected output: special case handling documented in `50_base_corrections.json → special_cases`.

8. **Build look layers record.**
   - Document per clip: conversion LUT used, base correction params, creative look + intensity, any special case treatment.
   - Expected output: `51_look_layers.json`.

9. **Run scope-based QC.**
   - Waveform: confirm no clipping above 100 IRE, no crush below 0 IRE (unless documented).
   - Vectorscope: verify skin tone line alignment (if applicable).
   - Check white balance continuity across adjacent cuts.
   - Run ComfyUI workflow for final color output: `skills/comfyui-workflows/color-correct.json`.
   - Expected output: `52_color_qc.json` with per-check pass/warn/fail.

10. **Write outputs and validate.**
    - Write `50_base_corrections.json`, `51_look_layers.json`, `52_color_qc.json`.
    - Run schema validation: `scripts/validate-artifact.js`.
    - Expected output: all 3 artifacts with `status: "pass"` or `"warn"`.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| No clipped highlights (unless documented) | 0 clips | 1 clip with documented justification | Any unintentional clip |
| No crushed blacks | 0 clips | 1 clip with documented justification | Any unintentional crush |
| White balance continuity across adjacent cuts | All consistent | 1–2 minor shifts | Visible jumps |
| Creative LUT intensity | 30–60% | > 60% with justification | > 80% undocumented |
| Cross-clip consistency score | ΔE < 5 avg | ΔE 5–8 avg | ΔE > 8 avg |
| Conversion LUT applied (log footage) | All log clips converted | — | Any log clip not converted |
| Skin tones preserved (if applicable) | Believable warmth | Slight shift | Unnatural/green/magenta |

## Outputs

| Artifact | Path | Schema |
|----------|------|--------|
| Base corrections data | `state/agents/<project_id>/50_base_corrections.json` | `schemas/50_base_corrections.schema.json` |
| Look layers record | `state/agents/<project_id>/51_look_layers.json` | `schemas/51_look_layers.schema.json` |
| Color QC report | `state/agents/<project_id>/52_color_qc.json` | `schemas/52_color_qc.schema.json` |
| Graded video | `state/agents/<project_id>/graded.mp4` | — |

## Failure Handling

- **EasyColorCorrector node error**: Check ComfyUI custom node installation at `hyperedit-deps/ComfyUI-EasyColorCorrector/`. Fallback to FFmpeg LUT application: `ffmpeg -i input.mp4 -vf lut3d=<lut_path> output.mp4`.
- **color-matcher CLI fails**: Use EasyColorCorrector manual mode for cross-clip matching.
- **Consistency score ΔE > 8**: Run a second matching pass on the outlier clips. If still failing, document `warn` with specific clip list.
- **Skin tone isolation issues**: Remove skin tone isolation and grade globally. Document as `warn`.
- **Retry policy**: Max 2 color correction passes before escalation. Heavy denoise/sharpen is deferred to final render, not grading pass.
- **Escalation**: Orchestrator may accept `warn` grade for delivery under time constraint.

## Downstream Dependencies

Completing this SOP unblocks:
- `07-text-graphics-captions.md` (runs after color is applied)
- `08-qa-grading.md` (Orchestrator final QC reads graded output)

## Skill Cross-Reference

- Skill: `skills/hyperedit-agent-color-pipeline/SKILL.md`
- Procedure matches: `skills/hyperedit-agent-color-pipeline/SOP.md` Steps 1–9
- Context: `skills/hyperedit-agent-color-pipeline/CONTEXT.md`
- ComfyUI workflow: `skills/comfyui-workflows/color-correct.json`
- Tools: ComfyUI + EasyColorCorrector (local :8188), color-matcher CLI, FFmpeg LUT application
