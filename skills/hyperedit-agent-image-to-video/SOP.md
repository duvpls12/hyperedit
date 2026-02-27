# SOP - Image to Video Generation

## Objective

Produce minimal, high fidelity synthetic inserts that bridge missing story coverage without breaking realism.

## Inputs

- `12_gap_report.json` from footage agent.
- Approved start/end frame pairs.
- Existing color baseline and style intent.

## Procedure

1. Confirm each generation request is `blocking`.
2. Export start/end frames at full quality after base color normalization.
3. Build prompt with strict constraints:
- Keep architecture geometry stable.
- Preserve lens perspective.
- Match movement direction and speed profile.
- Avoid object hallucinations and temporal warping.
4. If needed, annotate end frame for intent clarity (for example lot outlines for development reveal).
5. Generate 2-3 variants per request.
6. Run QC pass:
- Geometry consistency.
- Motion plausibility.
- Lighting continuity.
- Compression/artifact check.
7. Select best variant and record rejection reasons for others.
8. Deliver clip and metadata to assembly stage.

## Quality gates

- Synthetic clips should usually remain below 20% of final timeline duration.
- No clip with visible warping, flicker, or impossible camera motion may pass.
- Synthetic inserts must blend with adjacent real shots in color and motion.

## Outputs

- `20_img2video_requests.json`
- `21_img2video_outputs.json`
- `22_img2video_qc.json`
