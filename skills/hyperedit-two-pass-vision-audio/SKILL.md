---
name: hyperedit-two-pass-vision-audio
description: Use when running HyperEdit with a deterministic two-pass vision plus audio workflow, enforcing exactly one vision model instance, strict JSON artifacts, and local-only commits.
---

# HyperEdit Two-Pass Vision + Audio SOP

## Goal
Run one deterministic pipeline per video:
1) Vision Pass 1 (low-res temporal segmentation),
2) Vision Pass 2 (high-res semantic deep read),
3) Unload vision model,
4) Load audio models + run audio JSON,
5) Final synthesis,
6) Move processed video to done.

## Hard Rules
- Keep vision instance to **one always**.
- Never run more than **1 loaded `qwen/qwen3-vl-8b` instance**.
- If one instance already exists, do not load another.
- If more than one exists, stop and request cleanup confirmation.
- Audio pass is mandatory unless user explicitly waives it.
- Use deterministic file paths and deterministic JSON schema keys.
- Local-only changes/commits unless explicitly instructed to push.

## Required Artifacts
- `state/video-analysis-single/<video_id>_vision_pass1.json`
- `state/video-analysis-single/<video_id>_vision_pass2_semantic.json`
- `state/video-analysis-single/<video_id>_vision_fusion_canonical.json`
- `state/audio-analysis/<video_id>_audio_pass.json`
- `state/final-analysis/<video_id>_final_synthesis.md`
- `state/final-analysis/<video_id>_done.marker`

## Runtime Sequence

### 0) Preflight guard (vision instance policy)
1. Query loaded models.
2. Count `qwen/qwen3-vl-8b*` instances.
3. If count == 0, load one instance.
4. If count == 1, proceed.
5. If count > 1, stop and request cleanup confirmation.

### 1) Vision Pass 1 (low-res temporal @ 5 fps)
- Sample at 5 fps.
- Use low resolution for temporal structure.
- Detect shot boundaries, transitions, camera motion states.
- Produce pass1 JSON and shot list.

### 2) Vision Pass 2 (high-res semantic @ 1 frame per shot)
- Use Pass 1 shot list as timeline truth.
- Analyze one full-resolution keyframe per shot (optionally 2 for long shots).
- Extract granular scene/object/composition/camera details.
- Produce pass2 semantic JSON.

### 3) Vision fusion (required)
- Merge pass1 + pass2 strictly by `shot_id`.
- Never alter pass1 boundaries during merge.
- Preserve missing semantic entries as null with flags.
- Produce canonical fused JSON.

### 4) Switch models (required)
- Unload vision instance.
- Load audio model(s) before audio semantic analysis.

Default audio models:
- `qwen2-audio-7b`
- `gemma-music-recommender`

Model API sequence:
1. `POST /api/v1/models/unload` for active vision instance.
2. `POST /api/v1/models/load` with `{ "model": "qwen2-audio-7b" }` (or override).
3. `POST /api/v1/models/load` with `{ "model": "gemma-music-recommender" }` (or override).
4. Verify required audio models are active.

### 5) Audio pass (required)
DSP baseline (must run):
- `librosa`: BPM/tempo, beat map, onset map, RMS/energy, spectral centroid/brightness.
- `essentia` optional when available.

Audio LLM semantic pass:
- `qwen2-audio-7b`: scene-level interpretation + segmentation labels + event placements.
- `gemma-music-recommender`: music-fit scoring + ranked recommendations.

Save deterministic audio JSON.

### 6) Final synthesis
Combine fusion JSON + audio JSON into report:
- flow/pacing,
- shot sequence and movement logic,
- composition and amenity coverage,
- sound design and music recommendations,
- editing blueprint.

### 7) Done-folder workflow
After completion:
1. Write done marker.
2. Move source video from `.../all_files/` to `.../done/`.
3. Continue to next pending video.
4. Default batch target: 10 videos/run unless overridden.

## Prompt SOP (deterministic)

### Prompt A — Vision Pass 1 (Low-Res Temporal Segmentation @ 5 fps)
```text
You are Vision Pass 1 for real-estate video analysis.

MISSION
Detect shot boundaries and temporal structure with high recall.
This pass is low-resolution and timeline-focused (not deep object semantics).

INPUT
- video_id: {{video_id}}
- fps_sampled: 5
- frame_resolution: low
- frames: ordered with timestamps
- optional_audio_signals: beat/onset/energy (if provided)

OUTPUT RULES
- Return STRICT JSON only (no markdown, no commentary).
- Use timestamps in seconds with 3 decimals.
- Prefer over-segmentation to under-segmentation when uncertain.
- Include confidence scores 0..1.

TASKS
1) Identify shot boundaries:
   - hard cuts
   - soft transitions/dissolves
   - whip/blur transitions
2) Group frames into shots with:
   - start_s
   - end_s
   - duration_s
3) For each shot, estimate:
   - camera_motion: static|pan|tilt|dolly|push|pull|orbit|handheld|mixed
   - motion_intensity: low|medium|high
   - composition_scale: extreme_wide|wide|medium|close|extreme_close
   - scene_change_strength: 0..1
4) Flag uncertain boundaries for review.

JSON SCHEMA
{
  "video_id": "string",
  "pass": "vision_pass_1_lowres_temporal",
  "fps_sampled": 5,
  "shots": [
    {
      "shot_id": "S001",
      "start_s": 0.000,
      "end_s": 2.400,
      "duration_s": 2.400,
      "boundary_in": { "type": "hard_cut|soft|whip|start_of_video", "confidence": 0.0 },
      "boundary_out": { "type": "hard_cut|soft|whip|end_of_video", "confidence": 0.0 },
      "camera_motion": "static|pan|tilt|dolly|push|pull|orbit|handheld|mixed",
      "motion_intensity": "low|medium|high",
      "composition_scale": "extreme_wide|wide|medium|close|extreme_close",
      "scene_change_strength": 0.0,
      "needs_review": false,
      "notes": "short optional note"
    }
  ],
  "global_quality": {
    "segmentation_confidence": 0.0,
    "uncertain_boundary_count": 0
  }
}
```

### Prompt B — Vision Pass 2 (High-Res Deep Semantic, 1 frame per shot)
```text
You are Vision Pass 2 for real-estate video analysis.

MISSION
Perform granular semantic analysis on one high-resolution keyframe per shot
(using shot boundaries from Pass 1 as timeline truth).

INPUT
- video_id: {{video_id}}
- pass1_shots: authoritative shot list with shot_id/start/end
- keyframes: exactly one high-res frame per shot (optionally two for long shots)
- frame_resolution: full/native

OUTPUT RULES
- Return STRICT JSON only.
- One record per shot_id from pass1_shots.
- Do not alter shot boundaries; enrich semantics only.
- Include confidence 0..1 for major inferred attributes.

TASKS PER SHOT
1) Environment & space
   - indoor_or_outdoor
   - space_type (kitchen, living_room, bedroom, bathroom, exterior_front, backyard, aerial, etc.)
   - lighting (natural, mixed, artificial; bright/neutral/dim)
2) Objects & features
   - primary_objects[]
   - secondary_objects[]
   - premium_features[] (pool, island, fireplace, vaulted ceilings, etc.)
3) Spatial layering
   - foreground_elements[]
   - midground_elements[]
   - background_elements[]
4) Cinematic grammar
   - shot_type (establishing, hero, detail, insert, walkthrough, reveal, etc.)
   - camera_angle (eye_level, low_angle, high_angle, overhead, drone_oblique)
   - focal_length_estimate (ultrawide, wide, normal, telephoto)
   - composition_features[] (leading_lines, symmetry, frame_within_frame, depth_layers, etc.)
   - subject_emphasis (what viewer attention is pulled to)
5) Quality/utility flags
   - technical_flags[] (blur, blown_highlights, noise, skew, rolling_shutter, etc.)
   - editorial_tags[] (hook_candidate, transition_friendly, broll_strong, social_thumb_candidate, etc.)

JSON SCHEMA
{
  "video_id": "string",
  "pass": "vision_pass_2_highres_semantic",
  "shots": [
    {
      "shot_id": "S001",
      "environment": {
        "indoor_or_outdoor": "indoor|outdoor|mixed",
        "space_type": "string",
        "lighting_type": "natural|artificial|mixed",
        "lighting_level": "bright|neutral|dim",
        "confidence": 0.0
      },
      "objects": {
        "primary_objects": ["string"],
        "secondary_objects": ["string"],
        "premium_features": ["string"]
      },
      "spatial_layers": {
        "foreground_elements": ["string"],
        "midground_elements": ["string"],
        "background_elements": ["string"]
      },
      "cinematography": {
        "shot_type": "string",
        "camera_angle": "string",
        "focal_length_estimate": "ultrawide|wide|normal|telephoto",
        "composition_features": ["string"],
        "subject_emphasis": "string",
        "confidence": 0.0
      },
      "quality_and_editing": {
        "technical_flags": ["string"],
        "editorial_tags": ["string"],
        "confidence": 0.0
      },
      "notes": "optional concise note"
    }
  ]
}
```

### Prompt C — Fusion (Pass 1 + Pass 2)
```text
You are the fusion step for two-pass vision analysis.

MISSION
Merge temporal shot structure (Pass 1) with high-res semantics (Pass 2)
into a single shot-aware canonical output.

RULES
- Pass 1 boundaries are authoritative.
- Join strictly by shot_id.
- Never drop a shot from Pass 1.
- If Pass 2 is missing for a shot, keep shot with null semantic fields + flag.
- Return STRICT JSON.

OUTPUT
{
  "video_id": "string",
  "pass": "vision_fusion_canonical",
  "shots": [
    {
      "shot_id": "S001",
      "start_s": 0.000,
      "end_s": 2.400,
      "duration_s": 2.400,
      "temporal": { "from_pass1": true },
      "semantic": { "from_pass2": true },
      "fusion_flags": ["semantic_missing|low_confidence|boundary_uncertain"]
    }
  ],
  "summary": {
    "shot_count": 0,
    "semantic_coverage_pct": 0.0,
    "low_confidence_shots": 0
  }
}
```

## Deterministic JSON Keys (minimum)

### Vision pass 1
- `video_id`
- `pass`
- `fps_sampled`
- `shots[]`
- `global_quality`

### Vision pass 2
- `video_id`
- `pass`
- `shots[]`

### Vision fusion
- `video_id`
- `pass`
- `shots[]`
- `summary`

### Audio pass
- `audio_models[]`
- `audio_models_loaded`
- `bpm`
- `beats[]`
- `onsets[]`
- `energy_curve[]`
- `spectral_brightness[]`
- `segments[]`
- `sound_design_events[]`
- `audio_semantic_summary`
- `music_fit_score`
- `music_recommendations[]`

## Failure Handling
- 400/500 from model endpoint: retry with bounded attempts + jitter.
- Context pressure: chunk requests; never send full raw timeline in one call.
- If audio LLM fails, persist DSP fallback and set `audio_semantic_fallback=true`.

## Completion Contract
Return:
- DONE
- files changed
- verification outputs
- local commit hash
