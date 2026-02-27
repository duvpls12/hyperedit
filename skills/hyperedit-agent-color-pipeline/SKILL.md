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

## Required outputs

- `50_base_corrections.json`
- `51_look_layers.json`
- `52_color_qc.json`
