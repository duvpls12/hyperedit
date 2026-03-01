---
name: hyperedit-agent-image-to-video
description: Generate synthetic inserts for blocking coverage gaps using start/end frame workflows and realism QC.
metadata:
  tags: hyperedit,img2video,ai,generation
---

# Image to Video Generation Skill

## When to use

Use only when footage sorting marks a blocking gap that cannot be solved with existing clips.

## Execution

1. Read `CONTEXT.md` for synthetic usage constraints.
2. Run `SOP.md` to create requests, prompts, and QC outputs.
3. Hand off only passed synthetic clips to assembly.

## Claude Code trigger

Invoke as `/hyperedit-photo-to-video` when the orchestrator detects `blocking` gaps in `12_gap_report.json` that can be filled from property stills. Skip entirely if no blocking gaps exist.

## Tools

- **ComfyUI** (Vast.ai GPU remote `:8188`): Dispatch generation workflows — heavy inference requires RTX PRO 6000 VRAM
- **LTXVideo (LTX-2 19B)** (`ComfyUI-LTXVideo` nodes): Image-to-video generation — `LTXVideo Image2Video` node takes start frame + optional end frame + text prompt
- **IC-LoRA** (`LTXVideo IC-LoRA` node): Camera motion control for `dolly_in`, `jib_up`, `pan_left`, depth and pose conditioning
- **ComfyUI VideoHelperSuite**: Final video export — `Video Combine` node merges frame sequence into MP4

## ComfyUI dispatch pattern

```
POST http://<vast-ai-host>:8188/prompt
{ "prompt": <workflow_json> }
→ poll GET /history/{prompt_id} until complete
→ download output from /view?filename=...
```

Fallback: if Vast.ai GPU unavailable, queue request and skip to non-GPU pipeline stages.

## State paths

- Reads: `state/agents/<project_id>/12_gap_report.json`, raw stills directory
- Writes: `state/agents/<project_id>/20_synthetic_plan.json`, `state/agents/<project_id>/21_generated_clips.json`, `state/agents/<project_id>/22_realism_qc.json`

## Required outputs

- `20_synthetic_plan.json`
- `21_generated_clips.json`
- `22_realism_qc.json`
