# SOP - Image to Video Generation

## Objective

Produce minimal, high fidelity synthetic inserts that bridge missing story coverage without breaking realism.

## Inputs

- `12_gap_report.json` — only process entries where `gap_type: "blocking"` and stills are available.
- Raw property stills directory (JPEGs/PNGs at full resolution).
- Existing color baseline and style intent from footage agent notes.

## Procedure

1. Confirm each generation request is `blocking` in `12_gap_report.json`. Skip non-blocking gaps.
2. Write `20_synthetic_plan.json` with one entry per gap: `gap_id`, `still_path`, `intended_shot_class`, `target_duration_s`, `camera_motion`, `adjacent_clip_direction`.
3. Export start/end frames at full resolution after base color normalization (use FFmpeg server `POST /session/{id}/assets` to normalize if needed).
4. Build LTXVideo prompt for each gap with strict constraints:
   - Keep architecture geometry stable.
   - Preserve lens perspective.
   - Match movement direction and speed from adjacent real clips.
   - Camera motion: choose from `dolly_in`, `dolly_out`, `jib_up`, `jib_down`, `pan_left`, `pan_right`, `static`.
   - Avoid object hallucinations and temporal warping.
   - Duration: 2-5 seconds; prefer conservative motion to reduce artifacts.
5. Dispatch to ComfyUI on Vast.ai GPU:
   - Workflow: `Load Image` (start frame) → `LTXVideo Image2Video` (text prompt + optional end frame) → `LTXVideo IC-LoRA` (camera motion conditioning) → `Video Combine` (output MP4).
   - Submit workflow JSON via `POST http://<vast-ai-host>:8188/prompt`.
   - Poll `GET /history/{prompt_id}` every 10s until `status: "success"`.
   - Download output via `GET /view?filename=<output_file>`.
6. Generate 2-3 variants per gap (vary seed; keep prompt constant).
7. Run QC pass on each variant:
   - Geometry consistency (no morphing walls/windows).
   - Motion plausibility (no impossible camera moves).
   - Lighting continuity with adjacent real shots.
   - Compression/artifact check (no block artifacts or flicker).
8. Select best variant; record rejection reason for others in `22_realism_qc.json`.
9. Write `21_generated_clips.json` with: `gap_id`, `clip_path`, `tool: "LTXVideo-2-19B"`, `prompt`, `seed`, `model_version`, `variant_selected`, `variants_rejected`.

## Quality gates

- Synthetic clips should usually remain below 20% of final timeline duration.
- No clip with visible warping, flicker, or impossible camera motion may pass.
- Synthetic inserts must blend with adjacent real shots in color and motion.

## Outputs

- `20_synthetic_plan.json` — one entry per blocking gap with generation parameters.
- `21_generated_clips.json` — selected clip paths with full provenance (tool, prompt, seed, model).
- `22_realism_qc.json` — pass/warn/fail per clip with geometry/motion/lighting/artifact scores and rejection reasons for unused variants.
