# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ClipWise (formerly HyperEdit) is an AI-powered video editor built with React 19, Remotion for motion graphics, and Cloudflare Workers for the backend. It's a Mocha platform app.

## Commands

```bash
npm install --legacy-peer-deps  # Install dependencies (required due to Vite 7 peer dep conflict)
npm run dev              # Start Vite dev server
npm run ffmpeg-server    # Start local FFmpeg server (port 3333) - run in separate terminal
npm run build            # TypeScript + Vite production build
npm run lint             # ESLint
npm run check            # Full validation: type check + build + deploy dry-run
npm run knip             # Check for unused dependencies
npm run cf-typegen       # Generate Cloudflare worker types
```

**Local development** requires both `npm run dev` and `npm run ffmpeg-server` running simultaneously.

## Architecture

```
src/
├── react-app/           # Frontend React SPA
│   ├── components/      # UI: Timeline, VideoPreview, AssetLibrary, AIPromptPanel, MotionGraphicsPanel
│   ├── hooks/           # useProject (main state), useFFmpeg, useVideoSession
│   └── pages/Home.tsx   # Main editor layout
├── worker/index.ts      # Hono backend API (AI editing via Gemini)
├── remotion/            # Motion graphics system
│   └── templates/       # 11 templates with registry in index.ts
scripts/
└── local-ffmpeg-server.js  # Session-based FFmpeg server with Whisper transcription
```

**Key patterns:**
- Multi-track timeline with 6 tracks: T1 (captions), V3 (top overlay), V2 (overlay), V1 (base video), A1/A2 (audio)
- `useProject()` hook manages all project state: assets, clips, playback, captions, rendering
- Local FFmpeg server (port 3333) handles sessions, asset storage, thumbnail generation, rendering, and Whisper-based transcription for captions
- Cloudflare Worker with D1 database and R2 bucket for production (configured in wrangler.json)

## State Management

The `useProject()` hook in `src/react-app/hooks/useProject.ts` is the central state manager. Key concepts:

- **Assets**: Source files (video/image/audio) with metadata, thumbnails, and stream URLs
- **TimelineClips**: Instances of assets placed on tracks with start time, duration, in/out points, and transforms
- **CaptionData**: Word-level timing from Whisper transcription, stored separately with style configuration keyed by clip ID. Caption clips on T1 have `assetId: ''` — never look for caption content in the asset library.
- **TimelineTabs**: Each tab stores its own `clips: TimelineClip[]` separately. `activeClips` in Home.tsx switches between main `clips` and `tab.clips`. All move/resize/delete operations must check `activeTabId !== 'main'` and dispatch to `updateTabClips` instead.

**Critical patterns:**
- The hook uses parallel refs (`tracksRef`, `clipsRef`, `settingsRef`) synced via `useEffect` so debounced/async operations read latest state without stale closures. This is essential for `saveProject` and `renderProject`.
- Session ID is persisted in `localStorage` under key `clipwise-session`. If the FFmpeg server restarts, the stored session may be invalid (404), in which case localStorage is cleared and a new session is created on next asset upload.
- Tracks are always initialized client-side (never loaded from server) to guard against outdated server data.
- Auto-save is intentionally disabled to prevent excessive saves during drag operations. Saves must be triggered explicitly via `saveProject()`.
- `refreshAssets` appends `?v=Date.now()` to `streamUrl` for cache-busting after server-side file modifications.
- Assets with `aiGenerated: true` are deprioritized when selecting context video for new animation generation.

**Two parallel session systems exist:**
- `useProject` (modern) — multi-asset, full timeline
- `useVideoSession` (legacy) — single-video, still used exclusively for `generateChapters` in Home.tsx

## FFmpeg Server

The local FFmpeg server (`scripts/local-ffmpeg-server.js`, ~7700 lines) is a raw Node.js `http.createServer` with regex-based route matching. It handles all video processing, asset management, Remotion rendering, transcription, and fal.ai calls. The Cloudflare Worker only generates FFmpeg commands via Gemini — it does NOT execute them.

Key endpoints on `localhost:3333`:
- `POST /session/create` - Create new editing session
- `POST /session/{id}/assets` - Upload asset (auto-generates thumbnails)
- `POST /session/{id}/transcribe` - Whisper transcription for captions
- `POST /session/{id}/render` - Render final video
- `POST /session/{id}/render-motion-graphic` - Render Remotion animation
- `POST /session/{id}/generate-animation` - AI-generated Remotion code (Gemini writes JSX → Remotion CLI renders)
- `POST /session/{id}/edit-animation` - Modify existing Remotion source in-place (same asset ID reused after re-render)
- `POST /session/{id}/process-asset` - Apply FFmpeg command to a specific asset (replaces in-place)
- `POST /session/{id}/extract-audio` - Split video into muted video + audio on A1
- `POST /session/{id}/generate-video` - Image-to-video via fal.ai (DiCaprio)
- `POST /session/{id}/restyle-video` - Video-to-video style transfer (DiCaprio)
- `POST /session/{id}/remove-video-bg` - Background removal (DiCaprio)
- `POST /session/{id}/generate-image` - Picasso image generation
- `POST /session/{id}/giphy/*` - GIPHY search/trending/add proxy
- `POST /session/{id}/create-gif` - Animated GIF from image with motion effects
- `GET /session-continuity` - Session persistence/heartbeat continuity status

Sessions persist to `state/local-ffmpeg/sessions/{sessionId}/` by default (override root with `HYPEREDIT_DATA_DIR`). Each session also writes `heartbeat.json` (`lastSeen`) on create/restore and every 30s. Stale sessions are `lastSeen > 120s`, exposed by `/session-continuity`.

## TypeScript Configuration

Three separate tsconfig files:
- `tsconfig.app.json` - React app (ES2020, strict)
- `tsconfig.worker.json` - Cloudflare Worker
- `tsconfig.node.json` - Build tools

Path alias: `@/` → `./src/`

## Remotion Integration

Motion graphics use Remotion 4.x. Two distinct subsystems coexist:

**Static Templates** (`src/remotion/templates/`): 11 pre-built components registered in `MOTION_TEMPLATES` with categories (text, engagement, data, branding, mockup, showcase). Used by `MotionGraphicsPanel` with `@remotion/player` for live preview.

**AI-Generated Dynamic Animations** (`src/remotion/DynamicAnimation.tsx`): Takes `scenes: Scene[]` prop with types like title, steps, features, stats, chart, countdown, emoji, gif, lottie, etc. Composition `id="DynamicAnimation"` is what the FFmpeg server renders. Uses `@remotion/shapes`, `@remotion/animated-emoji`, `@remotion/gif`, `@remotion/lottie`, `@remotion/three`.

When working on templates, use the `/remotion-best-practices` skill for domain-specific guidance. Tailwind only scans `./src/react-app/` — not the remotion directory.

## Environment Variables

Required in `.dev.vars` for local development:
- `GEMINI_API_KEY` - Google AI for editing commands (worker uses `gemini-2.5-flash`)
- `FAL_API_KEY` - fal.ai for Picasso/DiCaprio (note: server aliases this to `FAL_KEY` for the fal.ai SDK)
- `GIPHY_API_KEY` - GIF search
- `OPENAI_API_KEY` - Additional AI features

## AI Agents

The right panel has three AI agents accessible via tabs. All three panels are always mounted but toggled with `hidden` CSS class to preserve chat state.
- **Director** (AIPromptPanel): Video editing commands, captions, motion graphics, animations
- **Picasso** (PicassoPanel): Image generation using fal.ai nano-banana-pro model
- **DiCaprio** (DiCaprioPanel): Video generation with Animate Image (Kling v1.5), Restyle Video (LTX-2 19B), Remove Background (Bria)

## UI Layout Conventions

- **Track placement**: AI-generated animations always go on V2. B-roll images go on V3 with default `scale: 0.2`, centered.
- **Image clips** default to 5-second duration everywhere (`addClip`, `handleDropAsset`, `addCaptionClip`).
- **Caption word timestamps** are relative to clip start, not absolute project time. Conversion happens in `getPreviewLayers()`.
- **Caption chunking**: Max 5 words per chunk OR when there's a 0.7s pause between words (hardcoded in Home.tsx `handleTranscribeAndAddCaptions`).
- **Ripple delete**: When `autoSnap` is true, deleting a clip shifts subsequent clips on the same track backward via the `ripple` parameter on `deleteClip`.
- **`splitClip`** has a 0.05s guard — returns `null` if split point is within 50ms of either edge.
- **Properties panel**: Left panel bottom half shows `CaptionPropertiesPanel` when selected clip is on T1, otherwise `ClipPropertiesPanel`.
- **Resizable panels**: Left (assets + properties), right (AI agents), and timeline height are all user-resizable via `ResizablePanel`/`ResizableVerticalPanel`.

## Local Whisper Transcription

Captions use local OpenAI Whisper (`scripts/whisper-transcribe.py`). Setup:
```bash
pip3 install openai-whisper torch
```
- **MPS (Apple GPU) is NOT supported** — Whisper's sparse tensors crash on MPS. The script runs on CPU only. Do not add `device="mps"`.
- Falls back to Gemini API if local Whisper is unavailable (but Gemini struggles with long audio files).
- The `base` model is used by default (good speed/accuracy balance).

## Dead Air Removal

The remove dead air workflow (`POST /session/{id}/remove-dead-air`) is stable — **do not modify it**. How it works:
1. FFmpeg `silencedetect` finds silence periods (threshold: -26dB, min duration: 0.4s — set in `Home.tsx handleRemoveDeadAir`)
2. Each non-silent segment is extracted individually with `-ss`/`-t` and re-encoded (`libx264 ultrafast, aac`)
3. Segments are concatenated with `-c copy` into the final output
4. The original file is replaced in-place on disk
5. Frontend calls `refreshAssets()` to get a cache-busted URL and updates the V1 clip duration

The segment-based approach (extract + concat) is required — single-pass filter approaches (`select`/`aselect`, `trim`/`atrim`) drop audio streams. The `VideoPreview` component uses a stable `key` on the base video element and manually calls `video.load()` when the source URL changes, preserving browser audio permission from the user's play gesture.

## Build & Deployment

- Vite config uses `@cloudflare/vite-plugin` and `@getmocha/vite-plugins`. `chunkSizeWarningLimit: 5000` due to Remotion's size.
- `wrangler.json` app name is a UUID (Mocha app ID). SPA routing via `not_found_handling: "single-page-application"`.
- No tests exist in the codebase. No testing framework is configured.

## HyperEdit Agent Pipeline Infrastructure

This section documents the agent-driven video editing pipeline built on top of ClipWise. Skills live in `skills/` at the repo root.

### Pipeline Order (hard dependency chain)

```
ORCHESTRATOR (init)
  → FOOTAGE INTAKE            always
  → PHOTO-TO-VIDEO            conditional: only if 12_gap_report.has_blocking_gaps == true
  → AUDIO                     always — must complete BEFORE assembly (beat grid drives all cuts)
  → ASSEMBLY                  always — reads 30_music_map + 31_radio_edit
  → COLOR                     always — only after 42_picture_lock is confirmed
  → TEXT & GRAPHICS           conditional: only if project_brief.caption_required == true
ORCHESTRATOR (QA & grading)
```

**Critical rule:** Audio BEFORE assembly. The music map and radio edit are the timeline skeleton — assembly without them produces arbitrary cuts.

### Skills Directory (`skills/`)

Single source of truth for all Claude Code skills. Each skill has `SKILL.md` + optional `SOP.md` + `CONTEXT.md`.

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `hyperedit-orchestrator` | `/hyperedit-orchestrator` or `/hyperedit-run` | Full pipeline dispatch, run-ledger init, final QA |
| `hyperedit-qc-gate` | `/hyperedit-qc-gate <stage>` | Universal quality gate checker between every stage |
| `hyperedit-agent-footage-intake-sort` | `/hyperedit-footage-intake` | Ingest, tag, sort, shortlist raw clips |
| `hyperedit-agent-image-to-video` | `/hyperedit-photo-to-video` | Synthetic clips from stills (conditional) |
| `hyperedit-agent-audio-sound-design` | `/hyperedit-audio` | Music selection, BPM analysis, radio edit |
| `hyperedit-agent-assembly-editor` | `/hyperedit-assembly` | Timeline from music map → picture lock |
| `hyperedit-agent-color-pipeline` | `/hyperedit-color` | Correction + grading after picture lock |
| `hyperedit-agent-graphics-captions` | `/hyperedit-text-graphics` | Captions, lower thirds (conditional) |
| `hyperedit-agent-master-orchestrator` | legacy | See `hyperedit-orchestrator` |
| `remotion-best-practices` | `/remotion-best-practices` | Remotion domain knowledge |
| `comfyui-workflows/` | (dispatch templates) | See ComfyUI section below |

GPU pipeline skills (Pipeline B): `hyperedit-gpu-edited-video-orchestrator`, `hyperedit-gpu-edited-video-pattern-mining`, `hyperedit-gpu-style-benchmark`, `hyperedit-gpu-rag-index-build`, `hyperedit-gpu-agent-training-dataset`.

### Artifact Numbering

Every pipeline stage writes 3 numbered JSON artifacts to `state/agents/<project_id>/`:

| Range | Stage |
|-------|-------|
| 00-01 | Orchestrator init |
| 10-12 | Footage Intake |
| 20-22 | Photo-to-Video |
| 30-32 | Audio |
| 40-42 | Assembly |
| 50-52 | Color |
| 60-62 | Text & Graphics |
| 70-72 | Final QC & Grade |

Every artifact includes required common fields: `status` (pass/warn/fail/pending), `blocking_issues`, `assumptions`, `open_questions`, `source_references`.

### JSON Schemas (`schemas/`)

Formal JSON Schema files for all 24 numbered artifacts plus the run-ledger.

- `schemas/_common.schema.json` — shared required fields for all artifacts
- `schemas/run-ledger.schema.json` — project execution state schema
- `schemas/00_project_brief.schema.json` through `schemas/72_publish_checklist.schema.json`

**Validate an artifact:**
```bash
node scripts/validate-artifact.js state/agents/<project_id>/10_footage_catalog.json
# Exit 0 = valid, 1 = invalid, 2 = usage error
# Schema is auto-inferred from filename prefix; or pass explicit schema as second arg
```

### Run-Ledger (`state/run-ledger/`)

Durable execution state for each project. Written by the orchestrator at every stage transition. Enables resume from checkpoint, skip completed stages, and retry failed stages.

- Path: `state/run-ledger/<project_id>.json`
- Schema: `schemas/run-ledger.schema.json`
- `current_stage`: one of `orchestrator_init | footage_intake | photo_to_video | audio | assembly | color | text_graphics | orchestrator_qc | done | blocked`
- Stage statuses: `pending | in_progress | done | blocked | skipped`

### ComfyUI Workflow Templates (`skills/comfyui-workflows/`)

Reusable JSON workflow templates dispatched via ComfyUI HTTP API (`POST /prompt`).

| Template | Purpose | Endpoint |
|----------|---------|---------|
| `color-correct.json` | LoadImage → EasyColorCorrection → SaveImage | Local Mac `:8188` |
| `video-combine.json` | VHS_LoadImages + VHS_LoadAudio → VHS_VideoCombine | Local Mac `:8188` |
| `image-to-video.json` | LTXVideo I2V distilled pipeline | Vast.ai GPU `:8188` |
| `upscale.json` | video2x CLI wrapper (upscale + interpolate presets) | CLI (not ComfyUI) |

**Hybrid dispatch rule:**
- **Local Mac** (`localhost:8188`): EasyColorCorrector, VideoHelperSuite — low VRAM, fast
- **Vast.ai GPU** (remote `:8188`): LTXVideo 19B generation — requires RTX PRO 6000 VRAM
- Orchestrator checks task type and routes accordingly. Fallback: queue GPU tasks, continue non-GPU stages.

**ComfyUI deps location:** `/Users/davideby/hyperedit-deps/`
- `ComfyUI/` — core engine (`python main.py` → http://localhost:8188)
- `ComfyUI-EasyColorCorrector/` — node: `EasyColorCorrection`
- `ComfyUI-LTXVideo/` — nodes: `LTXVConditioning`, `LTXVGemmaCLIPModelLoader`, etc.
- `ComfyUI-VideoHelperSuite/` — nodes: `VHS_VideoCombine`, `VHS_LoadVideo`, `VHS_LoadImages`, `VHS_LoadAudio`

### SOPs (`docs/sops/`)

13 dual-format SOPs — human-readable reference docs paired with executable skills.

```
docs/sops/
├── 01-project-kickoff.md          → hyperedit-orchestrator
├── 02-footage-ingest.md           → hyperedit-footage-intake
├── 03-photo-to-video.md           → hyperedit-photo-to-video
├── 04-audio-radio-edit.md         → hyperedit-audio
├── 05-assembly-picture-lock.md    → hyperedit-assembly
├── 06-color-grading.md            → hyperedit-color
├── 07-text-graphics-captions.md   → hyperedit-text-graphics
├── 08-qa-grading.md               → hyperedit-orchestrator (QA phase)
├── 09-comfyui-setup.md            → operational
├── 10-rag-commit.md               → hyperedit-rag-commit
├── 11-session-continuity.md       → hyperedit-session-restore
├── 12-client-delivery.md          → manual
├── 13-fallback-escalation.md      → embedded in each skill
└── templates/
    ├── project-brief-template.json
    ├── agent-run-report.md
    └── qc-checklist.md
```

### Quality Gates (enforced by `hyperedit-qc-gate`)

| Gate | Threshold | Fail Action |
|------|-----------|-------------|
| Hook timing | ≤ 5s from start | Retry assembly |
| Rehook cadence | Every 5-10s | Warn or retry |
| Directional continuity | ≥ 0.8 score | Retry assembly |
| Music-edit alignment | ≥ 80% cuts on beat anchors | Warn |
| Color after lock | Must be true | FAIL (pipeline order) |
| Caption safe area | 9:16, 8% padding | Retry graphics |
| Audio loudness | -14 LUFS ± 2 dB | Warn |

### Validate Script

`scripts/validate-artifact.js` — ES module CLI validator.
```bash
node scripts/validate-artifact.js <artifact_path> [schema_name]
```
- Auto-infers schema from artifact filename prefix (e.g. `10_...` → `10_footage_catalog.schema.json`)
- Uses ajv v6 for structural validation
- Common fields always checked (status, blocking_issues, assumptions, open_questions, source_references)

---

## Deterministic Execution Contract (HyperEdit Agent Runs)

### Project Context
- Repository: HyperEdit / ClipWise
- Worktree scope: run only in the assigned worktree path
- Objective: complete exactly the requested documentation/code change without side quests

### Task (Single Scope)
- Execute one explicitly defined task per run.
- If additional work is discovered, report it separately instead of expanding scope.

### Files allowed
- Only edit files explicitly listed in the task prompt.
- If a required file is outside the allowlist, stop and report BLOCKED.

### Definition of done
- Requested file edits are present and complete.
- Required validation command(s) execute and show expected markers.
- A local commit is created with the exact requested commit message.

### Validation commands
- Run only the validation commands specified in the task prompt.
- Include command output in final report.

### Output format
- BLOCKED: <reason>
- DONE: files changed + validation output + commit hash

### Git rule
- Do NOT push.
- Local commits only unless explicitly instructed otherwise.

---

## MCP Server (HyperEdit Tools)

The HyperEdit MCP server exposes Claude Desktop tools for the auto-sort pipeline. It is a separate Node.js process communicating over stdio.

**Location:** `mcp/server.js` (repo root)

**Start:**
```bash
node mcp/server.js
# Prints: "HyperEdit MCP server listening on stdio"
```

**Registration:** Add to Claude Desktop MCP config (Claude Desktop → Settings → MCP Servers):
```json
{
  "hyperedit": {
    "command": "node",
    "args": ["/Users/davideby/hyperedit/mcp/server.js"]
  }
}
```

**Cowork scheduled task:** `coworkScheduledTasksEnabled: true` is confirmed in Claude Desktop config. See `docs/cowork-auto-sort-task.md` for the exact prompt to register via `/schedule`.

**Available tools:**

| Tool | Purpose |
|------|---------|
| `get_project_brief` | Read and validate `brief.json` against schema |
| `list_project_footage` | Enumerate files in `footage/` |
| `extract_frame` | Extract middle frame from video → JPEG |
| `get_file_metadata` | EXIF + container metadata → camera model, color profile |
| `classify_shot` | Visual analysis → primary + sub-classification tags |
| `detect_color_profile` | Identify log/LUT profile (D-Log M, S-Log3, etc.) |
| `sort_to_bin` | Create symlink in `bins/{primary_tag}/` |
| `list_available_luts` | Return LUT catalog filtered by camera + profile |
| `apply_lut` | Apply LUT via FFmpeg → write to `graded/` |
| `notify` | Send macOS notification with processing summary |

---

## Charlie Drive Folder Structure

Charlie drive is mounted at `/Volumes/Charlie/`. The HyperEdit project root is `/Volumes/Charlie/hyperedit-studio/`.

```
/Volumes/Charlie/hyperedit-studio/
├── projects/
│   └── {project_id}/
│       ├── brief.json          ← pipeline entry point (triggers Cowork task)
│       ├── run-ledger.json     ← written after auto-sort; marks project as processed
│       ├── footage/            ← raw clips and stills (read-only)
│       ├── bins/
│       │   ├── wide/           ← symlinks to wide shots
│       │   ├── tight/          ← symlinks to tight shots
│       │   ├── detail/         ← symlinks to detail shots
│       │   ├── drone/          ← symlinks to drone shots
│       │   ├── agent-on-camera/ ← symlinks to agent shots
│       │   └── photos/         ← symlinks to all stills
│       └── graded/             ← LUT-applied output files
└── luts/
    └── *.cube                  ← LUT library (camera + profile matched)
```

**Test project:** `/Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline/` — ready for pipeline verification (brief.json + empty footage/, bins/, graded/).

---

## Auto-Sort Pipeline Overview

The Cowork scheduled task (every 30 min) drives the intake + classify + grade flow:

```
Cowork polls projects/ every 30 min
  → Finds folder with brief.json but no run-ledger.json
  → get_project_brief → list_project_footage
  → For each video:  extract_frame → get_file_metadata → classify_shot → detect_color_profile → sort_to_bin → list_available_luts → apply_lut
  → For each still:  get_file_metadata → classify_shot → sort_to_bin (primary bin + photos/)
  → Initialize run-ledger.json
  → notify (summary)
```

After auto-sort completes, the project is ready for the full orchestrator pipeline (`/hyperedit-orchestrator`). The run-ledger gates the orchestrator — it will read `current_stage` and continue from where auto-sort left off.

**Full prompt and schedule config:** `docs/cowork-auto-sort-task.md`

---

## RAG Query Endpoint

The local FFmpeg server exposes a RAG endpoint for agent context retrieval:

```
POST http://localhost:3333/rag/query
Content-Type: application/json

{
  "query": "how to grade DJI Mavic 3 Pro footage",
  "project_id": "20260227_Test_Pipeline"
}
```

Response:
```json
{
  "chunks": [
    { "text": "...", "source": "...", "score": 0.91 }
  ]
}
```

---

## Shot Classification Taxonomy

Full taxonomy documented in `docs/shot-classification-taxonomy.md`.

**Primary tags** (determine `bins/` sort destination):
- `wide` → sub: `establishing`, `low-angle`, `high-angle`, `eye-level`
- `tight` → sub: `close-up`, `medium-close-up`
- `detail` → sub: `hardware`, `fixture`, `texture`, `architectural`, `landscape`
- `drone` → sub: `aerial-wide`, `aerial-orbit`, `aerial-reveal`, `aerial-tracking`
- `agent-on-camera` → sub: `talking-head`, `walk-through`, `stand-up`

**Secondary tags** (stored in catalog, no bin effect): `interior/exterior`, room type, lighting condition.

**Confidence fallback:** If confidence < 0.65, default to `wide/establishing` and flag in `open_questions`.

---

## Pipeline Verification

Full end-to-end verification checklist: `docs/hyperedit-pipeline-verification.md`

10 verification steps covering: MCP server health, frame extraction, camera detection, shot classification, bin sorting, LUT application, full pipeline run, UI bins, RAG query, folder watcher.

