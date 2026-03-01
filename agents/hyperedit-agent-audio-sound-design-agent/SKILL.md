---
name: hyperedit-agent-audio-sound-design
description: Select music, detect BPM and beat grid via FFmpeg server, and produce the radio edit structure that drives all timeline cut timing. Runs BEFORE assembly.
metadata:
  tags: hyperedit,audio,sound-design,mix
---

# Audio and Sound Design Skill

## When to use

Use BEFORE assembly — music drives the edit rhythm. Run after footage shortlist is ready.

## Execution

1. Read `CONTEXT.md` for layering and level heuristics.
2. Run `SOP.md` for music selection, BPM analysis, radio edit structure, and QC.
3. Deliver music map and radio edit that assembly uses to drive cuts.

## Required outputs

- `30_music_map.json`
- `31_radio_edit.json`
- `32_audio_qc.json`
