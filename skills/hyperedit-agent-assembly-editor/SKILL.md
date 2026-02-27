---
name: hyperedit-agent-assembly-editor
description: Build timeline from music map beat grid — place shots on beat anchors, rough cut, refine, picture lock. Requires 30_music_map and 31_radio_edit from Audio agent.
metadata:
  tags: hyperedit,assembly,editing,pacing
---

# Assembly Editor Skill

## When to use

Use after the Audio agent has completed (`30_music_map.json` and `31_radio_edit.json` must exist). Also requires footage intake complete (`11_selects_shortlist.json`) and optional synthetic clips passed QC (`21_generated_clips.json` if applicable). Builds the entire timeline from the music map — cuts land on beats.

## Execution

1. Read `CONTEXT.md` for pacing rules, movement continuity heuristics, and sequence archetypes.
2. Run `SOP.md`: load beat grid from music map → place shots on beat anchors → rough cut → refine → picture lock.
3. Freeze picture lock. Color, graphics, and audio finishing begin only after this artifact is written.

## Required inputs

- `11_selects_shortlist.json` — approved shots with metadata
- `30_music_map.json` — BPM, beat timestamps, structural anchors
- `31_radio_edit.json` — radio edit timing structure with beat anchor references
- `21_generated_clips.json` (optional) — synthetic inserts if gap report triggered photo-to-video

## Required outputs

- `40_rough_cut.json`
- `41_refine_cut.json`
- `42_picture_lock.json`

## Tool integrations

- **FFmpeg server** (`localhost:3333`): timeline rendering, transitions, speed ramp processing
- **VideoHelperSuite** (ComfyUI node): Video Combine — merge frame sequences + audio track into final export
