---
name: hyperedit-agent-color-pipeline
description: Conform proxies to full-res, apply correction and grading using layered LUT workflow after picture lock. Only grades clips in the final cut.
metadata:
  tags: hyperedit,color,grading,correction,conform
---

# Color Pipeline Skill

## When to use

Use only after assembly is picture locked. This is where proxies get replaced with full-resolution graded footage.

## Proxy Conform + Grade Workflow

The assembly agent works with 720p proxies. The color pipeline is the first and only stage that touches raw footage. This means:

1. **Only clips in the final cut get graded** — massive time/cost savings since most raw footage doesn't make the edit
2. **Conform first** — read `42_picture_lock.json` to get the exact clip list with proxy→source mapping
3. **Grade only final selects** — apply LUT + correction to the full-res source files referenced in the picture lock
4. **Replace proxies** — output graded full-res files to `<project>/graded/`, update timeline references

### Conform Flow
```
42_picture_lock.json
  → For each clip in the locked timeline:
    1. Read source_path (raw 4K/HEVC) from proxy→source mapping
    2. Detect camera + color profile from shot-catalog.json
    3. Find matching LUT from /Volumes/Charlie/hyperedit-studio/assets/luts/
    4. Apply LUT + correction → graded/<clip_id>_graded.mp4
    5. Update timeline reference from proxy → graded
```

## Execution

1. Read `CONTEXT.md` for grading principles and failure cases.
2. Run `SOP.md` to execute conform + correction + look passes.
3. Deliver QC report and handoff to graphics/audio.

## Claude Code trigger

Invoke as `/hyperedit-color` when the orchestrator confirms `42_picture_lock.json` status is `done`. Never run before picture lock is final — wasted grading on cuts that change.

## Tools

- **FFmpeg** (local): LUT application + full-res encode — `ffmpeg -i <raw> -vf "lut3d=<lut.cube>" -c:v libx264 -crf 18 -c:a copy <graded>`
- **ComfyUI + EasyColorCorrector** (local `:8188`): AI-assisted correction via `EasyColorCorrect` node — modes: `Auto`, `Preset` (30+ looks including film emulation), `Manual`
- **color-matcher** (CLI): Batch cross-clip color consistency — `color-matcher -s './frames/' -r reference_frame.png -m 'mkl'` — matches color distribution of all clips to a single reference
- **FFmpeg server** (`localhost:3333`): LUT application — `POST /session/{id}/process-asset` with FFmpeg filter `lut3d=<lut_file.cube>`
- **shot-catalog.json**: Camera + color profile metadata per clip (written by footage intake)

### Pipeline Scripts

| Script | Purpose | When to use |
|--------|---------|-------------|
| `scripts/run-pipeline-local.js --grade-only` | Batch-grade from existing shot-catalog.json | Grade all classified clips (or specific subset) |

## ComfyUI workflow (local)

```
Load Video (Upload) → extract frames
→ EasyColorCorrect (Auto mode: balance exposure/WB)
→ EasyColorCorrect (Preset mode: apply look at 40-60% intensity)
→ Video Combine → export graded MP4
```

Local ComfyUI handles EasyColorCorrector (low VRAM). Route to Vast.ai only if video2x detail enhancement is needed post-grade.

## State paths

- Reads: `state/agents/<project_id>/42_picture_lock.json`, `<project>/shot-catalog.json`
- Writes: `state/agents/<project_id>/50_base_corrections.json`, `state/agents/<project_id>/51_look_layers.json`, `state/agents/<project_id>/52_color_qc.json`

## Project folder outputs

- `graded/` — Full-resolution graded files (only clips from the final cut)

## Required outputs

- `50_base_corrections.json`
- `51_look_layers.json`
- `52_color_qc.json`
