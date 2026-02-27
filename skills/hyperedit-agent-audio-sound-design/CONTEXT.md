# Context - Audio Agent (Music Selection, BPM Analysis, Radio Edit)

## Role in pipeline

Audio runs BEFORE assembly. The music map and radio edit produced here are the structural backbone that the Assembly agent uses to place every cut. Do not skip this agent or use placeholder BPM values — bad beat alignment creates flat edits regardless of shot quality.

## Music selection heuristics

- Match track energy arc to the property tier: luxury cinematic = slower builds, wide dynamic range; social reel = fast drop, early energy peak
- Prefer tracks with a clear intro/drop/outro — editor needs structural anchors for hook and payoff placement
- Avoid tracks where the strongest beat lands before second 3 — wastes the hook window
- For 30s–60s reels: select a chorus or drop segment, not the intro; radio edit should land on peak energy early
- When brief specifies no music preference, default to mid-tempo instrumental (100–120 BPM) with percussive attack

## BPM detection rules

- Always use FFmpeg server for BPM detection — do not estimate by ear
- If BPM result confidence < 0.8, try a second extraction method before flagging WARN
- Common failure: tracks with variable tempo (live recordings, cinematic scores) — flag in QC and use average BPM
- Beat grid gaps > 5s usually indicate silence sections (intro/outro) — pad with estimated beats, note as assumption

## Beat grid and anchor mapping

- Strong beats = kick/snare downbeats, prefer bar boundaries for cut points
- Structural anchors must be confirmed against audio waveform, not assumed from track title
- `chorus_start` and `drop_start` are highest-priority anchors — assembly agent uses these for major visual transitions
- Mark all anchors to the nearest beat (within 50ms tolerance)

## Radio edit rules

- Edit in/out points must land on beats, never mid-bar
- When splicing a shorter segment from a longer track, prefer crossfade at a low-energy moment (bridge, breakdown)
- Total radio edit duration should match target video duration within ±5s — flag as WARN if drift is 5–10s, FAIL if > 10s
- Include `beat_anchors_used[]` in `31_radio_edit.json` so assembly can reference by name rather than timestamp

## Failure modes

- BPM detection on compressed mp3 with loud low-end distortion → use WAV source if available
- Structural anchor placed in wrong section because silence was misread as section boundary → verify with waveform
- Radio edit duration off by > 10s → causes assembly to pad with dead air or hard-cut mid-beat
- Delivering `30_music_map.json` with empty `beat_timestamps[]` → blocks assembly completely
