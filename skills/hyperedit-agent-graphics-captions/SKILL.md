---
name: hyperedit-agent-graphics-captions
description: Add captions and graphics with mobile-safe readability and tracked text where useful.
metadata:
  tags: hyperedit,captions,graphics,text
---

# Graphics and Captions Skill

## When to use

Use after picture lock and primary color pass.

## Execution

1. Read `CONTEXT.md` for typography and timing heuristics.
2. Run `SOP.md` for caption script, layout pass, and QC.
3. Export graphics plans and optional alpha outputs.

## Claude Code trigger

Invoke as `/hyperedit-text-graphics` when the orchestrator confirms color pass is complete. This agent is conditional — skip if the project brief specifies no captions or graphics.

## Tools

- **FFmpeg server** (`localhost:3333`): Whisper transcription via `POST /session/{id}/transcribe` — returns word-level timestamps
- **Remotion** (local CLI): Caption rendering, lower thirds, motion graphics — renders templates from `src/remotion/templates/` via `POST /session/{id}/render-motion-graphic`

## Caption chunking rules

- Max **5 words per chunk** OR split on a **0.7s pause** between words (whichever comes first).
- Mobile safe area: center-bottom zone, 9:16 viewport with **8% padding** on all sides.
- No caption collisions with faces or key property features.

## State paths

- Reads: `state/agents/<project_id>/42_picture_lock.json`
- Writes: `state/agents/<project_id>/60_caption_script.json`, `state/agents/<project_id>/61_graphics_layout.json`, `state/agents/<project_id>/62_graphics_qc.json`

## Required outputs

- `60_caption_script.json`
- `61_graphics_layout.json`
- `62_graphics_qc.json`
