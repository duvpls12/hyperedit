---
name: hyperedit-two-pass-vision-audio
description: Use when running HyperEdit with a deterministic two-pass vision plus audio workflow, enforcing exactly one vision model instance, strict JSON artifacts, and local-only commits.
---

# HyperEdit Deterministic Two-Pass Vision + Audio Pipeline

## Objective
Execute one fully deterministic analysis pipeline per video:
1. Vision Pass 1 — Temporal segmentation (low-res, 5 fps)
2. Vision Pass 2 — High-res semantic deep read (1 frame per shot)
3. Optional Pass 2.5 — 11B refinement on selected shots
4. Vision fusion (canonical merge)
5. **Generate 720p proxy** for editing
6. Unload vision model
7. Load audio models
8. Audio DSP + semantic pass
9. Final synthesis
10. Move source video to `/done`

No parallelism. No model overlap. No schema drift.

## Proxy-First Workflow

After classification, generate a **720p H.264 proxy** for each clip. All downstream editing (assembly, review, QC) uses proxies. Full-resolution footage is only re-encoded during the final conform + grade stage after picture lock.

```
Classify (GPU) → Sort (bins/) → Proxy (proxies/) → Edit with proxies → Conform + Grade (graded/)
```

**Proxy spec:** 720p longest edge, H.264 CRF 23, ultrafast preset, AAC 128k audio.

**Why:** Not all clips make the final cut. Grading is expensive (4K HEVC → H.264 at ~62x realtime). By deferring grade to post-picture-lock, we only process the 20-40 clips in the final edit rather than all 160+ raw clips.

---

## Core Enforcement Rules
- Exactly **one vision model instance** may be loaded at any time.
- Vision fallback ladder is hard-coded:
  **11B → 8B → 4B**
- On failure:
  - Demote model.
  - Restart the current pass from checkpoint.
- Audio pass is mandatory unless explicitly waived.
- All file paths must be deterministic.
- All JSON keys must match schema exactly.
- Every vision JSON must include:
  - `vision_model_used`
  - `vision_fallback_chain`
- Local-only commits unless explicitly instructed to push.

---

## Required Artifacts

### Vision
- `state/video-analysis-single/<video_id>_vision_pass1.json`
- `state/video-analysis-single/<video_id>_vision_pass2_semantic.json`
- `state/video-analysis-single/<video_id>_vision_pass2_5_hq11b.json` (optional)
- `state/video-analysis-single/<video_id>_vision_fusion_canonical.json`

### Audio
- `state/audio-analysis/<video_id>_audio_pass.json`

### Final
- `state/final-analysis/<video_id>_final_synthesis.md`
- `state/final-analysis/<video_id>_done.marker`
- `state/final-analysis/<video_id>_failed.json` (if all models fail)

---

## GPU Infrastructure

### Vast.ai RTX PRO 6000 Blackwell (96GB VRAM)
- **SSH:** `ssh -p 29449 root@154.59.156.10 -L 8080:localhost:8080`
- **SSH Key:** `~/.ssh/id_ed25519` (passphrase-protected, must be loaded via `ssh-add`)
- **Ollama:** Runs on remote port 11434, tunneled to `localhost:8080`
- **Vision model:** `qwen2.5vl:7b` (Q4_K_M, 6GB, ~0.4s/frame warm)
- **Pipeline script:** `node scripts/run-pipeline-local.js <project-path>`

### Setup Sequence
```bash
# 1. Load SSH key (passphrase required)
ssh-add ~/.ssh/id_ed25519

# 2. Start SSH tunnel
ssh -p 29449 root@154.59.156.10 -N -f -L 8080:localhost:8080

# 3. Verify Ollama
curl http://localhost:8080/api/tags

# 4a. Run pipeline (local decode, remote classify via tunnel)
node scripts/run-pipeline-local.js /Volumes/Charlie/hyperedit-studio/projects/<project_id> --classify-only

# 4b. Run pipeline (remote decode + classify, local proxies) — PREFERRED
node scripts/run-pipeline-remote.js /Volumes/Charlie/hyperedit-studio/projects/<project_id>
```

### Model Loading on Fresh Instance
```bash
ssh -p 29449 root@154.59.156.10 "nohup ollama serve > /tmp/ollama.log 2>&1 &"
ssh -p 29449 root@154.59.156.10 "ollama pull qwen2.5vl:7b"
```

### Pipeline Scripts

| Script | Mode | Description |
|--------|------|-------------|
| `scripts/run-pipeline-remote.js` | Remote GPU | SCP clips to Vast.ai, classify server-side via `gpu-classify.py`, generate 720p proxies locally. **Fastest — eliminates Mac CPU bottleneck.** |
| `scripts/run-pipeline-local.js --classify-only` | Local + tunnel | FFmpeg decode locally, classify via Ollama tunnel (localhost:8080). Skip grading. |
| `scripts/run-pipeline-local.js --grade-only` | Local only | Read existing `shot-catalog.json`, apply LUTs to raw clips. Run after picture lock for conform. |
| `scripts/gpu-classify.py` | Server-side | Runs on Vast.ai instance. Extracts frames + classifies via local Ollama. Called by `run-pipeline-remote.js` via SSH. |

### Cost Optimization
- **Instance cost:** $1.076/hr (RTX PRO 6000 Blackwell)
- **Classification speed:** ~37s/clip (remote), ~50s/clip (local tunnel)
- **160 clips → ~1.5 hrs classify-only = ~$1.60 total**
- **Stop instance immediately after classification completes**
- **Grading happens locally after picture lock — no GPU needed**

### First Pipeline Run Results (2026-02-27)
- **160 clips** classified in ~2.5 hrs on RTX PRO 6000 Blackwell
- **Bins produced:** wide (75), detail (64), drone (19), walk-through (2)
- **Total GPU cost:** ~$2.70 ($1.076/hr x ~2.5 hrs)
- **Average classification time:** ~37s/clip (remote mode)
- **All 160 proxies** generated locally via `scripts/generate-proxies.js` (~5s/clip)

### Camera-Aware Drone Override Rule

Only filenames prefixed with `DJI_` can classify as `drone`. If a non-DJI clip is classified as drone by the vision model, it is reclassified to `wide`. This rule is enforced in `run-pipeline-local.js`, `run-pipeline-remote.js`, `gpu-classify.py`, `hyperedit-mcp-server.js`, and `bridge-catalog.js`.

---

## Runtime Execution Sequence

### 0) Preflight + Model Resolution
1. Query loaded models.
2. Enforce exactly one managed vision instance.
3. Attempt vision load in order:
   - `VISION_MODEL_11B`
     - Default: `mlx-community/Llama-3.2-11B-Vision-Instruct-8bit`
   - `VISION_MODEL_8B`
     - Default: `qwen/qwen3-vl-8b`
   - `VISION_MODEL_4B`
     - Default: `qwen/qwen2.5-vl-4b-instruct`
   - **Vast.ai Ollama (preferred for batch):**
     - `qwen2.5vl:7b` via `localhost:8080` (SSH tunnel to Vast.ai)
4. On failure:
   - Unload.
   - Demote.
   - Retry current pass.
5. If all fail:
   - Write `<video_id>_failed.json`
   - Continue to next video.

---

### 1) Vision Pass 1 — Low-Res Temporal (5 fps)
**Purpose:** Structural segmentation, high recall.
- Sample at 5 fps.
- Low resolution.
- Detect:
  - Shot boundaries
  - Transitions
  - Camera motion state
- Over-segment when uncertain.

**Output:**
- Strict JSON.
- Include:
  - `vision_model_used`
  - `vision_fallback_chain`

---

### 2) Vision Pass 2 — High-Res Semantic
**Purpose:** Deep semantic understanding per shot.
- Use Pass 1 shot list as timeline authority.
- Analyze exactly 1 keyframe per shot (2 only if long duration).
- Extract:
  - Environment
  - Objects
  - Spatial layering
  - Cinematic grammar
  - Editorial flags

Do not alter shot boundaries.

---

### 2.5) Optional 11B Refinement
Apply only to:
- Hero shots
- Low-confidence shots
- Ambiguous scenes

**Rules:**
- Unload current model before loading 11B.
- If 11B fails, skip refinement.
- Do not restart full pipeline for refinement failure.

---

### 3) Vision Fusion
Merge Pass 1 + Pass 2 by `shot_id`.

**Rules:**
- Pass 1 boundaries are authoritative.
- Never remove a shot.
- If semantic missing → set null + flag.
- Preserve all shot IDs.

**Output:**
- Canonical fused JSON.
- Include summary metrics.

---

### 4) Vision → Audio Model Switch
Before audio:
1. `POST /api/v1/models/unload` active vision model
2. Load:
   - `qwen2-audio-7b`
   - `gemma-music-recommender`
3. Verify both active.

No overlapping vision/audio memory.

---

### 5) Audio Pass

#### DSP Baseline (Mandatory)
- BPM / tempo
- Beat map
- Onset map
- RMS energy
- Spectral centroid / brightness
- Optional: Essentia enhancements

#### LLM Semantic Pass
- Scene-level interpretation
- Segmentation labels
- Event placement
- Music-fit scoring
- Ranked recommendations

Persist deterministic audio JSON.

---

### 6) Final Synthesis
Combine:
- Vision fusion
- Audio JSON

Generate structured report covering:
- Pacing logic
- Motion distribution
- Composition patterns
- Amenity coverage
- Sound design notes
- Editing blueprint
- Music fit assessment

---

### 7) Done Folder Workflow
After completion:
1. Write `<video_id>_done.marker`
2. Move source video from `/all_files/` → `/done/`
3. Continue to next pending video
4. Default batch size: 10 videos per run unless overridden

---

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
  "vision_model_used": "string",
  "vision_fallback_chain": ["string"],
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
  "vision_model_used": "string",
  "vision_fallback_chain": ["string"],
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

---

## Deterministic JSON Keys (minimum)

### Vision pass 1
- `video_id`, `pass`, `vision_model_used`, `vision_fallback_chain`, `fps_sampled`, `shots[]`, `global_quality`

### Vision pass 2
- `video_id`, `pass`, `vision_model_used`, `vision_fallback_chain`, `shots[]`

### Vision fusion
- `video_id`, `pass`, `shots[]`, `summary`

### Audio pass
- `audio_models[]`, `audio_models_loaded`, `bpm`, `beats[]`, `onsets[]`
- `energy_curve[]`, `spectral_brightness[]`, `segments[]`, `sound_design_events[]`
- `audio_semantic_summary`, `music_fit_score`, `music_recommendations[]`

---

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
