---
name: hyperedit-two-pass-vision-audio
description: Use when running HyperEdit end-to-end in two vision passes plus audio pass with strict two-instance Qwen limits, deterministic JSON artifacts, and final full-dataset synthesis.
---

# HyperEdit Two-Pass Vision + Audio Skill

## Goal
Run one deterministic pipeline:
1) Vision pass 1 JSON,
2) Vision pass 2 JSON (posthoc temporal/shot-aware),
3) unload Qwen,
4) load audio LLM + run audio JSON,
5) final full-dataset synthesis.

## Hard Rules
- Never exceed **2 loaded `qwen/qwen3-vl-8b` instances**.
- If two instances already exist, do not load another.
- If user is manually unloading, do not issue additional unloads unless explicitly asked.
- Audio pass is mandatory: do not skip it.
- Explicitly load the requested audio LLM before audio semantic analysis.
- Use deterministic file paths + deterministic JSON schema.
- Local-only changes/commits unless explicitly asked to push.

## Required Artifacts
- `state/video-analysis-single/<video_id>_vision_pass1.json`
- `state/video-analysis-single/<video_id>_vision_pass2_temporal.json`
- `state/audio-analysis/<video_id>_audio_pass.json`
- `state/final-analysis/<video_id>_final_synthesis.md`

## Runtime Sequence

### 0) Preflight instance guard
1. Query loaded models.
2. Count `qwen/qwen3-vl-8b*` instances.
3. If count < 2, load until count == 2.
4. If count == 2, proceed.
5. If count > 2, stop and request cleanup confirmation.

### 1) Vision Pass 1 (semantic baseline)
- Run frame analysis with the two pinned Qwen instances.
- Save deterministic baseline JSON.

### 2) Vision Pass 2 (posthoc temporal refinement)
- Use existing frames + pass1 JSON.
- Detect shot boundaries.
- Compute inter-frame/global motion.
- Classify movement per shot.
- Interpolate movement across frame timeline.
- Save temporal/refined JSON.

### 3) Switch models (required)
- Unload the two Qwen vision instances.
- Load the configured audio model via LM Studio model API before analysis.

Default audio model id:
- `qwen2-audio-7b`

Model API sequence:
1. `POST /api/v1/models/unload` for each active vision instance.
2. `POST /api/v1/models/load` with `{ "model": "qwen2-audio-7b" }` (or configured override).
3. Verify load by checking model list and ensuring audio model is active.

### 4) Audio pass (required)
Use DSP + audio LLM together.

DSP baseline (must run):
- `librosa`: BPM/tempo, beat map, onset map, RMS/energy, spectral centroid/brightness.
- `essentia` optional when available; do not block run if unavailable.

Audio LLM semantic pass (must run after load):
- scene-level sound design interpretation,
- music/ambience/voice segmentation labels,
- recommended sound-design event placements,
- music-fit guidance.

Save deterministic audio JSON including both DSP and LLM sections.
Do not mark run complete if audio LLM step was skipped unless explicitly instructed by user.

### 5) Final synthesis
Combine pass1 + pass2 + audio JSON into a full report:
- flow/pacing,
- shot sequence + movement logic,
- composition/amenity coverage,
- sound design/music recommendations,
- edit blueprint.

## Deterministic JSON Keys (minimum)

### Vision pass 1
- `video`
- `fps`
- `frames_total`
- `per_frame[]`

### Vision pass 2 temporal
- `shot_boundaries[]`
- `shots[]` (`start_frame`, `end_frame`, `duration_sec`, `movement_type`, `confidence`)
- `interpolated_motion[]`
- `movement_counts`

### Audio pass
- `audio_model_id`
- `audio_model_loaded` (bool)
- `bpm`
- `beats[]`
- `onsets[]`
- `energy_curve[]`
- `spectral_brightness[]`
- `segments[]` (`music|ambience|voice`)
- `sound_design_events[]`
- `audio_semantic_summary`

## Failure Handling
- 400/500 from model endpoint: retry bounded attempts with jitter.
- Context overflow risk: chunk and compact payloads; never send full raw timeline in one prompt.
- If audio LLM fails, keep DSP-only fallback and mark `audio_semantic_fallback=true`.

## Completion Contract
Return:
- DONE
- files changed
- verification outputs
- local commit hash
