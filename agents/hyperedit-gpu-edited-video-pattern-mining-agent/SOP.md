# SOP - Edited-Video Pattern Mining

## Inputs

- Edited video file.
- Optional transcript/captions.

## Procedure

1. Detect shot boundaries and segment timeline.
2. Compute per-shot features:
- Duration.
- Apparent movement class.
- Transition type.
- Composition class (wide/medium/detail estimate).
3. Extract pacing map:
- Cut density by 5-second windows.
- Fast/slow rhythm regions.
4. Detect structural markers:
- Hook window (0-5s).
- Rehook candidates (5-10s intervals).
- Payoff window near outro.
5. Extract audio signals:
- BPM estimate.
- Beat/onset maps.
- Energy curve and accent density.
6. Generate rule candidates with confidence scores.
7. Persist outputs and QC.

## Outputs

- `<video_id>_segment_map.json`
- `<video_id>_pacing_map.json`
- `<video_id>_hook_rehook_map.json`
- `<video_id>_audio_structure.json`
- `<video_id>_rule_candidates.json`
