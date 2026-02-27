---
name: hyperedit-agent-color-pipeline
description: Apply correction and grading using layered LUT workflow after picture lock.
metadata:
  tags: hyperedit,color,grading,correction
---

# Color Pipeline Skill

## When to use

Use only after assembly is picture locked.

## Execution

1. Read `CONTEXT.md` for grading principles and failure cases.
2. Run `SOP.md` to execute correction and look passes.
3. Deliver QC report and handoff to graphics/audio.

## Claude Code trigger

Invoke as `/hyperedit-color` when the orchestrator confirms `42_picture_lock.json` status is `done`. Never run before picture lock is final — wasted grading on cuts that change.

## Tools

- **ComfyUI + EasyColorCorrector** (local `:8188`): AI-assisted correction via `EasyColorCorrect` node — modes: `Auto`, `Preset` (30+ looks including film emulation), `Manual`
- **color-matcher** (CLI): Batch cross-clip color consistency — `color-matcher -s './frames/' -r reference_frame.png -m 'mkl'` — matches color distribution of all clips to a single reference
- **FFmpeg server** (`localhost:3333`): LUT application — `POST /session/{id}/process-asset` with FFmpeg filter `lut3d=<lut_file.cube>`

## ComfyUI workflow (local)

```
Load Video (Upload) → extract frames
→ EasyColorCorrect (Auto mode: balance exposure/WB)
→ EasyColorCorrect (Preset mode: apply look at 40-60% intensity)
→ Video Combine → export graded MP4
```

Local ComfyUI handles EasyColorCorrector (low VRAM). Route to Vast.ai only if video2x detail enhancement is needed post-grade.

## State paths

- Reads: `state/agents/<project_id>/42_picture_lock.json`
- Writes: `state/agents/<project_id>/50_base_corrections.json`, `state/agents/<project_id>/51_look_layers.json`, `state/agents/<project_id>/52_color_qc.json`

## Required outputs

- `50_base_corrections.json`
- `51_look_layers.json`
- `52_color_qc.json`
