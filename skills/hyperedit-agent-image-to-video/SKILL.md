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

## Required outputs

- `20_synthetic_plan.json`
- `21_generated_clips.json`
- `22_realism_qc.json`
