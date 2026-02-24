---
name: cinematic-training-and-qa
description: Use when running HyperEdit end-to-end in two vision passes plus audio pass with strict two-instance Qwen limits, deterministic JSON artifacts, and final full-dataset synthesis.
---

# Cinematic Training and QA Skill

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
- `state/final-analysis/<video_id>_done.marker`

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
- Load the configured audio model(s) via LM Studio model API before analysis.

Default audio model ids:
- `qwen2-audio-7b` (audio semantics)
- `gemma-music-recommender` (music fit/recommendation scoring)

Model API sequence:
1. `POST /api/v1/models/unload` for each active vision instance.
2. `POST /api/v1/models/load` with `{ "model": "qwen2-audio-7b" }` (or configured override).
3. `POST /api/v1/models/load` with `{ "model": "gemma-music-recommender" }` (or configured override).
4. Verify load by checking model list and ensuring required audio models are active.

### 4) Audio pass (required)
Use DSP + audio LLM together.

DSP baseline (must run):
- `librosa`: BPM/tempo, beat map, onset map, RMS/energy, spectral centroid/brightness.
- `essentia` optional when available; do not block run if unavailable.

Audio LLM semantic pass (must run after load):
- `qwen2-audio-7b`: scene-level sound design interpretation, music/ambience/voice segmentation labels, sound-design event placements.
- `gemma-music-recommender`: music-fit scoring and ranked music recommendations aligned to pacing/energy profile.

Save deterministic audio JSON including both DSP and LLM sections.
Do not mark run complete if either required audio model step was skipped unless explicitly instructed by user.

### 5) Final synthesis
Combine pass1 + pass2 + audio JSON into a full report:
- flow/pacing,
- shot sequence + movement logic,
- composition/amenity coverage,
- sound design/music recommendations,
- edit blueprint.

### 6) Done-folder workflow (required)
After a video completes all passes:
1. Write done marker artifact.
2. Move source video from `.../all_files/` to `.../done/`.
3. Immediately continue with the next pending video.
4. Default batch target: process 10 videos per run unless overridden.

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
- `audio_models[]` (e.g., `qwen2-audio-7b`, `gemma-music-recommender`)
- `audio_models_loaded` (bool)
- `bpm`
- `beats[]`
- `onsets[]`
- `energy_curve[]`
- `spectral_brightness[]`
- `segments[]` (`music|ambience|voice`)
- `sound_design_events[]`
- `audio_semantic_summary`
- `music_fit_score`
- `music_recommendations[]`

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
