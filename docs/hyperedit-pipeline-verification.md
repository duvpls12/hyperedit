# HyperEdit Pipeline Verification Procedure

## Purpose

Step-by-step checklist to verify the complete HyperEdit MCP + agent pipeline is functional before running production projects. Run this procedure whenever:
- The MCP server is updated
- Claude Desktop is reconfigured
- A new machine or environment is set up
- After a major dependency upgrade

---

## Prerequisites

- [ ] Charlie drive mounted at `/Volumes/Charlie/`
- [ ] Claude Desktop installed and running
- [ ] MCP server config present in Claude Desktop settings
- [ ] Node.js ≥ 18 available
- [ ] Test project created: `/Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline/`

---

## Step 1: MCP Server Health

**Goal:** Confirm the `hyperedit` MCP server is registered and tools are available.

```bash
# Start the MCP server (from repo root)
node mcp/server.js

# Expected: Server prints "HyperEdit MCP server listening on stdio"
```

**Claude Desktop verification:**
1. Open Claude Desktop → Settings → MCP Servers
2. Confirm `hyperedit` appears in the list with status "Connected"
3. In a new conversation, call `list_available_luts` with no arguments
4. Expected response: JSON array of available LUT filenames

**Pass criteria:** `list_available_luts` returns at least one LUT entry without error.

---

## Step 2: Frame Extraction

**Goal:** Verify `extract_frame` produces a valid JPEG from a video file.

**Setup:** Place any `.mp4` or `.mov` test clip in:
`/Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline/footage/`

**Call:**
```json
{
  "tool": "extract_frame",
  "arguments": {
    "video_path": "/Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline/footage/test_clip.mp4",
    "position": "middle"
  }
}
```

**Pass criteria:**
- Returns a file path ending in `.jpg`
- File exists on disk and is a valid JPEG (non-zero size)
- No FFmpeg error in response

---

## Step 3: Camera Model Detection

**Goal:** Verify `get_file_metadata` correctly parses camera make/model from various filename patterns and EXIF data.

**Test cases:**

| Input File Pattern | Expected Camera Model |
|-------------------|----------------------|
| `DJI_0042.MP4` | DJI (from filename prefix) |
| `A7IV_clip.mp4` | Sony A7 IV |
| `GH6_footage.mp4` | Panasonic GH6 |
| `clip_with_exif.mp4` | Read from EXIF MakerNote |

**Call:**
```json
{
  "tool": "get_file_metadata",
  "arguments": {
    "file_path": "/path/to/test_clip.mp4"
  }
}
```

**Pass criteria:**
- Returns `camera_model` field (string, not null)
- Returns `color_profile` field (string or "unknown")
- Returns `duration_seconds`, `width`, `height`, `fps`

---

## Step 4: Shot Classification

**Goal:** Verify all primary and sub-classification labels are recognized by `classify_shot`.

**Test each primary tag:**

```json
{
  "tool": "classify_shot",
  "arguments": {
    "frame_path": "/tmp/test_frame.jpg",
    "hint": "aerial drone shot of full property"
  }
}
```

**Expected primary tags:** `wide`, `tight`, `detail`, `drone`, `agent-on-camera`

**Verification:** For each primary tag, confirm at least one sub-classification from the taxonomy is returned. See `docs/shot-classification-taxonomy.md` for full label list.

**Pass criteria:**
- `primary_tag` is one of the 5 valid primaries
- `sub_tag` is a valid sub-classification for that primary
- `confidence` is a float between 0.0 and 1.0

---

## Step 5: Bin Sorting (Symlink Creation)

**Goal:** Verify `sort_to_bin` creates the correct symlink.

**Call:**
```json
{
  "tool": "sort_to_bin",
  "arguments": {
    "project_id": "20260227_Test_Pipeline",
    "filename": "test_clip.mp4",
    "primary_tag": "drone"
  }
}
```

**Verify:**
```bash
ls -la /Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline/bins/drone/
# Expected: test_clip.mp4 -> ../../footage/test_clip.mp4
```

**Pass criteria:**
- `bins/drone/test_clip.mp4` exists
- It is a symlink (`l` in `ls -la` output)
- Symlink target resolves to the original in `footage/`

---

## Step 6: LUT Application

**Goal:** Verify `apply_lut` produces a graded output file.

**Call:**
```json
{
  "tool": "apply_lut",
  "arguments": {
    "input_path": "/Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline/footage/test_clip.mp4",
    "lut_name": "DJI_Mavic3Pro_DLogM_to_Rec709.cube",
    "output_path": "/Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline/graded/test_clip_graded.mp4"
  }
}
```

**Verify:**
```bash
ls -lh /Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline/graded/
# Expected: test_clip_graded.mp4 present, non-zero size
```

**Pass criteria:**
- Output file exists in `graded/`
- File size > 0 bytes
- Response includes `lut_applied` field matching the LUT name used

---

## Step 7: Full Pipeline (End-to-End)

**Goal:** Run the complete intake → classify → sort → grade flow on the test project.

**Setup:** Ensure `run-ledger.json` does NOT exist in the test project directory.

**Trigger:** Run `/hyperedit-footage-intake` skill on `20260227_Test_Pipeline`.

**Expected sequence:**
1. `get_project_brief` → reads `brief.json` → validates against schema
2. `list_project_footage` → returns file list from `footage/`
3. For each clip: `extract_frame` → `get_file_metadata` → `classify_shot` → `detect_color_profile` → `sort_to_bin`
4. For each classified clip: `list_available_luts` → `apply_lut`
5. `run-ledger.json` written to project root
6. `notify` called with summary

**Pass criteria:**
- `10_footage_catalog.json` written to `state/agents/20260227_Test_Pipeline/`
- All clips present in appropriate `bins/` subdirectories
- All clips present in `graded/` (or flagged in `blocking_issues` if LUT not found)
- `run-ledger.json` exists with `current_stage: "footage_intake"` and `status: "done"` or `"warn"`

---

## Step 8: UI Asset Bins

**Goal:** Verify the `AssetBinBrowser` component displays the sorted bins correctly.

**Steps:**
1. Start dev server: `npm run dev`
2. Open `http://localhost:5173`
3. Load the test project
4. Open the Asset Library panel
5. Verify bin tree appears: `wide/`, `tight/`, `detail/`, `drone/`, `agent-on-camera/`, `photos/`
6. Test drag-and-drop from `bins/drone/` to the timeline
7. Verify badge counts update after sorting

**Pass criteria:**
- Bin tree renders without errors
- Drag-and-drop adds clip to timeline
- Clip count badges match actual file counts in `bins/`

---

## Step 9: RAG Query

**Goal:** Verify the RAG endpoint returns relevant chunks.

```bash
curl -X POST http://localhost:3333/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "how to sort drone footage", "project_id": "20260227_Test_Pipeline"}'
```

**Expected response:**
```json
{
  "chunks": [
    {
      "text": "...",
      "source": "...",
      "score": 0.87
    }
  ]
}
```

**Pass criteria:**
- HTTP 200 response
- `chunks` array is non-empty
- Each chunk has `text`, `source`, and `score` fields

---

## Step 10: Folder Watcher

**Goal:** Verify `watch-projects.sh` detects new `brief.json` files and triggers processing.

```bash
# Start the watcher
bash scripts/watch-projects.sh &

# Create a new test project to trigger detection
mkdir -p /Volumes/Charlie/hyperedit-studio/projects/20260227_Watcher_Test/footage
cp /Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline/brief.json \
   /Volumes/Charlie/hyperedit-studio/projects/20260227_Watcher_Test/brief.json
```

**Expected:** Within 5 seconds, watcher logs detection of `20260227_Watcher_Test` and initiates pipeline.

**Pass criteria:**
- Watcher log shows "Detected new project: 20260227_Watcher_Test"
- Pipeline kickoff is initiated (e.g., `run-ledger.json` created)
- No errors in watcher output

---

## Verification Summary Checklist

| # | Check | Status |
|---|-------|--------|
| 1 | MCP server starts + tools visible in Claude Desktop | ⬜ |
| 2 | `extract_frame` returns valid JPEG | ⬜ |
| 3 | `get_file_metadata` detects camera model | ⬜ |
| 4 | `classify_shot` returns valid taxonomy labels | ⬜ |
| 5 | `sort_to_bin` creates correct symlink | ⬜ |
| 6 | `apply_lut` writes graded output file | ⬜ |
| 7 | Full pipeline: brief.json → run-ledger.json | ⬜ |
| 8 | UI bins: tree renders + drag-drop works | ⬜ |
| 9 | RAG query returns relevant chunks | ⬜ |
| 10 | Folder watcher detects new brief.json | ⬜ |

**All 10 checks pass = pipeline is production-ready.**
