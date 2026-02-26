---
name: hyperedit-remote-gpu-vastai
description: Use when running HyperEdit video analysis on a rented Vast.ai GPU instance using qwen2.5vl:32b via Ollama, librosa DSP audio, and yt-dlp/Vimeo scraping. Single model handles all passes — no model swapping. Upload via Jupyter REST API when SSH is unavailable.
---

# HyperEdit Remote GPU Pipeline (Vast.ai + qwen2.5vl:32b)

## Objective

Execute a fully deterministic analysis pipeline per video on a rented GPU instance:
1. Scrape source videos (YouTube / Vimeo) via yt-dlp
2. Vision Pass 1 — Per-frame temporal scan (5 fps, 720px, 6 concurrent workers)
3. Vision Pass 2 — Temporal synthesis (40 sampled frames, full narrative + movement analysis)
4. Audio DSP — librosa baseline (BPM, beats, onsets, energy, spectral)
5. Audio Semantic — qwen2.5vl:32b text-only interpretation of DSP features
6. Final Synthesis — structured Markdown report
7. Sync results back to local `state/final-analysis/`
8. Clean up workspace after each video

No vision model swapping. No separate audio LLM. One model: **qwen2.5vl:32b on Ollama**.

---

## Instance Profile

| Field | Value |
|---|---|
| Provider | Vast.ai |
| GPU | 4× NVIDIA RTX PRO 6000 Blackwell Server Edition |
| RAM | 256 GB |
| Vision model | `qwen2.5vl:32b` via Ollama |
| Disk cap | 31 GB (enforced in script) |
| Ollama port | `localhost:11434` |
| Results dir | `/workspace/results/` |
| Script | `/workspace/run_remote_scrape_infer.py` |

---

## Core Enforcement Rules

- **One model, all passes**: `qwen2.5vl:32b` handles pass1, pass2, and audio semantic. No swap.
- **Disk cap is hard**: refuse new downloads if `du /workspace` ≥ `DISK_CAP_GB`. Clean up after every video.
- **Deterministic output paths**: `<video_id>_vision_pass1.json`, `<video_id>_vision_pass2_temporal.json`, `<video_id>_final_synthesis.md`
- **num_ctx: 4096** always set in Ollama options.
- **Pass 1 num_predict: 250**. **Pass 2 num_predict: 1200**.
- Audio DSP is mandatory (librosa). Audio semantic is best-effort (LLM timeout 300s).
- Local-only commits unless explicitly instructed to push.

---

## Required Artifacts

### Per-video outputs (in `/workspace/results/<video_id>/`)
- `<video_id>_vision_pass1.json` — per-frame temporal scan
- `<video_id>_vision_pass2_temporal.json` — full narrative synthesis
- `<video_id>_audio_dsp.json` — librosa DSP baseline
- `<video_id>_audio_semantic.json` — LLM interpretation of DSP
- `<video_id>_final_synthesis.md` — structured report

### Synced locally (after run)
- `state/final-analysis/<video_id>_final_synthesis.md`
- `state/final-analysis/<video_id>_done.marker`

---

## Deployment: Upload Script to Instance

SSH on the assigned port may fail with `publickey`. Use Jupyter REST API instead.

### Step 1 — Get XSRF token from browser

Open the Jupyter terminal tab in Chrome, open DevTools console, run:

```js
document.cookie.match(/_xsrf=([^;]+)/)?.[1]
```

Copy the returned token string.

### Step 2 — Base64-encode the script locally

```bash
base64 -i /Users/davideby/hyperedit/state/video-analysis-single/run_remote_scrape_infer.py | tr -d '\n' > /tmp/script_b64.txt
```

### Step 3 — Upload via Jupyter contents API

In Chrome DevTools console (on the Jupyter tab):

```js
const token = "PASTE_XSRF_TOKEN_HERE";
const b64 = "PASTE_BASE64_CONTENT_HERE";

fetch("/api/contents/run_remote_scrape_infer.py", {
  method: "PUT",
  headers: {
    "Content-Type": "application/json",
    "X-XSRFToken": token
  },
  body: JSON.stringify({
    type: "file",
    format: "base64",
    content: b64
  })
}).then(r => r.json()).then(console.log);
```

### Step 4 — Run the pipeline

In the Jupyter terminal:

```bash
pip install -q librosa
python3 /workspace/run_remote_scrape_infer.py
```

---

## Pipeline Execution Sequence

### 0) Preflight
1. Check `qwen2.5vl:32b` is loaded in Ollama (`GET localhost:11434/api/tags`).
2. Check disk usage — abort individual video if near cap.
3. yt-dlp scrape target channels (default: `@arcoa_films`, `studio910pb`).

---

### 1) Vision Pass 1 — Per-Frame Temporal Scan (5 fps, 720px)

**Purpose:** Frame-level camera movement and scene type classification.

- Sample at 5 fps, max resolution 720px on longest edge.
- 6 concurrent workers (ThreadPoolExecutor).
- Each frame analyzed independently.

**Per-frame prompt extracts:**
- `camera_movement`: 30+ types including `gimbal_walk_forward`, `gimbal_walk_backward`, `drone_pullback`, `drone_push`, `drone_orbit`, `drone_rise`, `drone_descend`, `slider_left`, `slider_right`, `pan_left`, `pan_right`, `tilt_up`, `tilt_down`, `static_locked`, `handheld_subtle`, `jib_up`, `jib_down`, `whip_pan`, `speed_ramp`, `zoom_in`, `zoom_out`, `mixed`
- `movement_speed`: `slow_cinematic` | `medium` | `fast_dynamic`
- `scene_type`: `exterior_aerial`, `exterior_ground`, `interior_main_living`, `interior_kitchen`, `interior_bedroom`, `interior_bathroom`, `interior_detail`, `pool_area`, `garage`, `transition_card`
- `sequence_role`: `intro_hook` | `room_showcase` | `transition` | `detail_moment` | `outro`
- `composition`: `ultrawide` | `wide` | `medium` | `close` | `detail`
- `confidence`: 0.0–1.0

**Output schema (pass 1):**
```json
{
  "video_id": "string",
  "pass": "vision_pass_1_per_frame",
  "vision_model_used": "qwen2.5vl:32b",
  "fps_sampled": 5,
  "frames": [
    {
      "frame_idx": 0,
      "timestamp_s": 0.0,
      "camera_movement": "string",
      "movement_speed": "slow_cinematic|medium|fast_dynamic",
      "scene_type": "string",
      "sequence_role": "string",
      "composition": "string",
      "confidence": 0.0,
      "notes": "optional"
    }
  ]
}
```

---

### 2) Vision Pass 2 — Temporal Synthesis (40 sampled frames)

**Purpose:** Full narrative, movement arc, editorial blueprint from the video as a whole.

- 40 evenly sampled frames from the full video duration.
- Single LLM call with all frames.
- num_predict: 1200, timeout: 300s.

**Pass 2 prompt extracts:**
- `narrative_arc`: overall story structure
- `camera_movement_breakdown`: distribution of movement types across the video
- `movement_sequences`: temporal grouping of similar movements
- `signature_moves`: hero/standout shots
- `movement_speed_profile`: pacing distribution (% slow / medium / fast)
- `transition_types`: hard cut, dissolve, whip, speed ramp counts
- `pacing`: `slow_cinematic` | `mixed` | `fast_dynamic`
- `space_coverage`: which rooms/areas were shown
- `editorial_blueprint`: recommended edit structure
- `hook_candidates`: best frames for thumbnail/hook

**Output schema (pass 2):**
```json
{
  "video_id": "string",
  "pass": "vision_pass_2_temporal_synthesis",
  "vision_model_used": "qwen2.5vl:32b",
  "narrative_arc": "string",
  "camera_movement_breakdown": {},
  "movement_sequences": [],
  "signature_moves": [],
  "movement_speed_profile": { "slow_pct": 0, "medium_pct": 0, "fast_pct": 0 },
  "transition_types": {},
  "pacing": "string",
  "space_coverage": [],
  "editorial_blueprint": "string",
  "hook_candidates": []
}
```

---

### 3) Audio DSP — librosa Baseline (Mandatory)

- Extract audio track from downloaded video (ffmpeg).
- librosa analysis:
  - BPM (tempo)
  - Beat frames → timestamps
  - Onset frames → timestamps
  - RMS energy curve (per-second)
  - Spectral centroid / brightness (per-second)
- Persist as `<video_id>_audio_dsp.json`.

**Output schema (DSP):**
```json
{
  "video_id": "string",
  "bpm": 0.0,
  "beats": [0.0],
  "onsets": [0.0],
  "energy_curve": [{ "t": 0.0, "rms": 0.0 }],
  "spectral_brightness": [{ "t": 0.0, "centroid_hz": 0.0 }]
}
```

---

### 4) Audio Semantic — qwen2.5vl:32b Text-Only Pass (Best-Effort)

- Feed DSP features as structured text to `qwen2.5vl:32b`.
- No audio file sent to LLM — text-only prompt.
- Timeout: 300s. If timeout, set `audio_semantic_fallback: true` and continue.

**Extracts:**
- `energy_character`: e.g., "high-energy throughout with drops at 30s, 90s"
- `beat_density_interpretation`: e.g., "fast-paced, 128 BPM, dance-forward"
- `music_fit_suggestions`: ranked list of music styles
- `sound_design_notes`: key moments to accent
- `pacing_alignment`: how audio pacing matches visual pacing

---

### 5) Final Synthesis

Combine pass 1 frame data + pass 2 synthesis + audio DSP + audio semantic into a structured Markdown report.

**Report sections:**
- Video overview (duration, shot count, pacing)
- Movement arc (distribution, signature moves, speed profile)
- Space coverage (rooms shown, aerial vs ground ratio)
- Cinematic grammar (transition types, composition patterns)
- Audio profile (BPM, energy, beat density)
- Sound design opportunities
- Music fit recommendations
- Editorial blueprint (recommended cut structure)
- Hook candidates

Write to `<video_id>_final_synthesis.md`.

---

### 6) Result Sync (After Run)

```bash
rsync -avz -e "ssh -p 19691" root@ssh8.vast.ai:/workspace/results/ \
  /Users/davideby/hyperedit/state/final-analysis/
```

If SSH fails, use Jupyter file browser download or API `GET /api/contents/results/`.

---

### 7) Cleanup (After Each Video)

Remove extracted frames, audio temp files, and source video from workspace to stay under disk cap. Keep only JSON + Markdown outputs in `/workspace/results/`.

---

## Source Channels

Default scrape targets:
- `https://www.youtube.com/@arcoa_films`
- `https://vimeo.com/studio910pb`

Override via `CHANNELS` list in script.

---

## Failure Handling

| Failure | Action |
|---|---|
| Disk cap hit | Skip video, log, continue |
| Ollama timeout (pass 1 frame) | Skip frame, mark `confidence: 0.0` |
| Ollama timeout (pass 2) | Write partial, mark `synthesis_complete: false` |
| Audio DSP fails | Skip audio, set `audio_dsp_available: false` |
| Audio semantic timeout | Set `audio_semantic_fallback: true`, persist DSP only |
| yt-dlp fails | Log error, skip video |

---

## Completion Contract

Return:
- `DONE`
- Files written per video
- Disk usage before cleanup
- rsync status
- Local commit hash (if applicable)
