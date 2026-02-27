# Cowork Scheduled Task: HyperEdit Auto-Sort Pipeline

## Overview

This document contains the exact prompt to register as a scheduled Cowork task in Claude Desktop. When active, Cowork will poll the projects folder every 30 minutes and automatically kick off the intake + sort + grade pipeline for any new project that has a `brief.json` but no `run-ledger.json`.

---

## How to Register

1. Open Claude Desktop
2. In any conversation, type `/schedule`
3. Paste the prompt below into the task field
4. Set interval to **every 30 minutes**
5. Confirm prerequisites (see below) are met

---

## The Prompt (paste exactly as-is)

```
Check /Volumes/Charlie/hyperedit-studio/projects/ for any folders containing brief.json that haven't been processed yet (no run-ledger.json). For each new project:
1. Read the brief.json (get_project_brief)
2. List all files in footage/ (list_project_footage)
3. For each video clip:
   a. Extract middle frame (extract_frame)
   b. Read file metadata (get_file_metadata) → detect camera model
   c. Analyze frame visually → determine shot type + sub-classification
   d. Classify shot (classify_shot) → store tags
   e. Detect color profile (detect_color_profile)
   f. Sort into bin (sort_to_bin) → symlink into bins/{type}/
4. For each still photo:
   a. Read file metadata
   b. Analyze visually → shot type
   c. Classify and sort into both bins/{type}/ AND bins/photos/
5. For each classified clip:
   a. Find matching LUT (list_available_luts) based on camera + profile
   b. Apply LUT (apply_lut) → output to graded/
6. Initialize run-ledger.json for orchestrator
7. Send notification (notify) with summary of what was processed
```

---

## Schedule

**Interval:** Every 30 minutes

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Charlie drive mounted | `/Volumes/Charlie/` is accessible |
| Claude Desktop open | App is running and active |
| MCP server registered | `hyperedit` tools visible in Claude Desktop tool list |
| `hyperedit-studio/projects/` exists | Base folder present on Charlie |

---

## MCP Tools Called

| Tool | Purpose |
|------|---------|
| `get_project_brief` | Read and parse `brief.json` |
| `list_project_footage` | Enumerate files in `footage/` |
| `extract_frame` | Pull middle frame from video for visual analysis |
| `get_file_metadata` | Read EXIF/container metadata → detect camera model |
| `classify_shot` | Tag clip with primary + secondary shot classification |
| `detect_color_profile` | Identify log/LUT profile from metadata or frame analysis |
| `sort_to_bin` | Create symlink in `bins/{type}/` |
| `list_available_luts` | Return LUT catalog filtered by camera + profile |
| `apply_lut` | Apply matched LUT → write output to `graded/` |
| `notify` | Send summary notification with processed clip count |

---

## Detection Logic: "Unprocessed" Project

A folder is considered **unprocessed** when:
- It contains `brief.json`
- It does **not** contain `run-ledger.json`

A folder is considered **in-progress or done** when:
- `run-ledger.json` exists (regardless of `current_stage`)

---

## Output Structure Per Project

```
/Volumes/Charlie/hyperedit-studio/projects/{project_id}/
├── brief.json                  ← input: project parameters
├── run-ledger.json             ← written at end of this task
├── footage/                    ← raw clips and stills (read-only)
├── bins/
│   ├── wide/                   ← symlinks to wide shots
│   ├── tight/                  ← symlinks to tight shots
│   ├── detail/                 ← symlinks to detail shots
│   ├── drone/                  ← symlinks to drone shots
│   ├── agent-on-camera/        ← symlinks to agent shots
│   └── photos/                 ← symlinks to all stills
└── graded/                     ← LUT-applied output files
```

---

## Notes

- The task is **idempotent**: running it again on an already-processed project is a no-op (run-ledger.json check).
- Videos are sorted by **primary shot type** only into `bins/`. Stills go into both `bins/{type}/` AND `bins/photos/`.
- LUT matching uses camera model + detected color profile. If no match is found, clip is flagged in `run-ledger.json` under `blocking_issues`.
- After this task completes, the project is ready for the full orchestrator pipeline (`/hyperedit-orchestrator`).
