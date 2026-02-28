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

## Proxy-First Editing

Assembly works exclusively with **720p proxy files** from `<project>/proxies/`. This keeps timeline operations fast and avoids processing 4K/HEVC footage during the creative editing phase. The `11_selects_shortlist.json` includes `proxy_path` for each clip.

After picture lock is frozen, the Color agent handles **conform** — replacing proxy references with full-resolution source files and applying LUT grading. Assembly never touches the raw footage directly.

## Required inputs

- `11_selects_shortlist.json` — approved shots with metadata + proxy_path references
- `30_music_map.json` — BPM, beat timestamps, structural anchors
- `31_radio_edit.json` — radio edit timing structure with beat anchor references
- `21_generated_clips.json` (optional) — synthetic inserts if gap report triggered photo-to-video
- `<project>/proxies/` — 720p H.264 proxy files for all shortlisted clips

## Required outputs

- `40_rough_cut.json` — includes both `proxy_path` and `source_path` per clip
- `41_refine_cut.json`
- `42_picture_lock.json` — frozen cut with proxy→source mapping for conform

## Live Editing via FFmpeg Server

The assembly agent can edit the timeline live through the FFmpeg server, allowing the user to watch edits in real time at the dev server (`npm run dev`):

1. **Create session:** `POST /session/create` → receive `session_id`
2. **Import proxies:** `POST /session/{id}/import-project` — reads `shot-catalog.json`, symlinks proxies into session, creates bins, registers assets
3. **Place clips on timeline:** `PUT /session/{id}/project` — saves clips/tracks/settings to `project.json`. The frontend `useProject` hook loads from server session and updates in real time.
4. **Render final output:** `POST /session/{id}/render` — renders the timeline to video

The user can watch the assembly being built at `localhost:5173` (Vite dev server) while the agent places clips.

## Tool integrations

- **FFmpeg server** (`localhost:3333`): timeline rendering, transitions, speed ramp processing (operates on proxy files), live project save via `PUT /session/{id}/project`
- **VideoHelperSuite** (ComfyUI node): Video Combine — merge frame sequences + audio track into final export
