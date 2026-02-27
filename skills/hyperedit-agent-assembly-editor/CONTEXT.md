# Context - Assembly Editor

## Role in pipeline

Assembly runs AFTER Audio agent. Never attempt assembly without `30_music_map.json` and `31_radio_edit.json` — timing by visual feel alone produces flat edits. Every cut must have a beat justification.

## Source patterns from tutorials

- Music dictates pace and structure for most successful edits.
- Hook, promise, and payoff pattern outperforms random montage.
- Rehooks prevent attention decay after initial hook.
- Use movement matching across cuts for smooth perception.
- Alternate detail and wide shots for rhythm and space clarity.

## Movement continuity heuristics

- Keep consistent lateral direction through mini sequences.
- Use straight push clips as neutral reset before switching direction.
- Pre stabilize clips before speed ramping to avoid broken tracks.
- Maintain enough pre and post motion "meat" around ramp anchors.

## Sequence archetypes

- MLS: ordered room progression with clear orientation.
- Luxury cinematic: suspense driven detail reveals before wide payoff.
- Signature reel: stronger script and personality beats with stylized transitions.
- AI lot: build with timing placeholders, then replace with generated inserts.

## Tool integration

- **FFmpeg server** (`localhost:3333`): use `POST /session/{id}/render` to render timeline from clip JSON; use `POST /session/{id}/process-asset` for speed ramp encoding
- **VideoHelperSuite** (ComfyUI node): use Video Combine to merge frame sequences + audio track into final output file; prefer local Mac ComfyUI (:8188) for this step (low VRAM requirement)

## Failure modes

- Over editing transitions that hide property value.
- Repetitive shot rhythm causing flat watch curve.
- Timing purely by visual taste without beat references.
- Assembling before `30_music_map.json` exists — produces timeline with no beat anchors.
- Speed ramp anchor placed without checking pre/post motion buffer — causes broken stabilization track.
- Using wrong output artifact names (30_music_map, 31_rough_cut_plan) — Assembly produces 40/41/42 only.
