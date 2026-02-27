---
name: hyperedit-agent-footage-intake-sort
description: Ingest and sort footage into sequence-ready selects with continuity and gap reporting.
metadata:
  tags: hyperedit,footage,sorting,editing
---

# Footage Intake and Sorting Skill

## When to use

Use this skill at the start of every project before assembly editing.

## Use this workflow

1. Read `CONTEXT.md` to apply tutorial based selection heuristics.
2. Run `SOP.md` to produce catalogs, selects, and gap report.
3. Hand off outputs to assembly agent and optional image-to-video agent.

## Claude Code trigger

Invoke as `/hyperedit-footage-intake` or when the orchestrator dispatches this stage at pipeline start.

## Tools

- **FFmpeg server** (`localhost:3333`): Upload clips via `POST /session/{id}/assets` for metadata extraction and thumbnail generation
- **ComfyUI VideoHelperSuite** (local `:8188`): Extract frames per clip for vision analysis (`Load Video (Upload)` node)
- **video2x** (optional): AI upscale low-res clips before assembly — `video2x -i clip.mp4 -o out.mp4 --scale-factor 2`
- **LM Studio vision model** (local): Shot class tagging — submit extracted frame, receive `shot_class`, `room_zone`, `direction` labels

## State paths

- Reads: `state/agents/<project_id>/00_project_brief.json`, raw footage directory
- Writes: `state/agents/<project_id>/10_footage_catalog.json`, `state/agents/<project_id>/11_selects_shortlist.json`, `state/agents/<project_id>/12_gap_report.json`

## Required outputs

- `10_footage_catalog.json`
- `11_selects_shortlist.json`
- `12_gap_report.json`
