# 1044 Waterbury — Reference Grading Rubric (v1)

- Project: `1044_waterbury_20260228`
- Source: `/Volumes/Charlie/deliverables/Jacob Guthrie/1044 Waterbury Lane/1044 Waterbury Lane.mp4`
- Generated: `2026-03-01T04:47:44+00:00`
- Grade: **C** (weighted score `79.9`)

## Evidence
- Duration: 44.23s
- Resolution: 2160x3840
- FPS: 30/1
- Estimated cuts: 76 (103.09/min)
- Loudness: -12.99 LUFS
- Sampling policy manifest: `/Users/davideby/hyperedit/state/baseline/1044-waterbury/fps_sampling_manifest.json`

## Weights
{
  "hook": 0.18,
  "rehook_density": 0.14,
  "motion_continuity": 0.17,
  "tension_waveform": 0.16,
  "audio_immersion": 0.12,
  "music_property_match": 0.13,
  "viral_readiness": 0.1
}

## Target thresholds
{
  "hook_window_sec": 3.0,
  "rehook_interval_sec": 10.0,
  "ideal_median_shot_sec_min": 0.9,
  "ideal_median_shot_sec_max": 2.5,
  "title_window_max_sec": 4.0,
  "min_beats_for_cuemap": 8
}

## Dimension scores
{
  "hook": 90,
  "rehook_density": 88,
  "motion_continuity": 78,
  "tension_waveform": 82,
  "audio_immersion": 85,
  "music_property_match": 80,
  "viral_readiness": 84
}

## Penalties
[
  {
    "rule": "semantic_room_labels_missing",
    "points": -4,
    "source": "baseline semantic LM Studio failures"
  }
]

## Recreation directives
- Hit first hook by <=3.0s with high-energy exterior or amenity shot
- Maintain rehook cadence <=10s intervals; preferred 5-8s for this pacing profile
- Preserve high cut density (~103 cuts/min estimate) while avoiding directional whiplash
- Target integrated loudness near -14 LUFS with true peak < -1 dBTP
- Rerun semantic pass (8B primary, 4B fallback) to recover room/amenity labeling before final recreation grading

## Degraded labels
- semantic pass degraded due LM Studio model load failures
