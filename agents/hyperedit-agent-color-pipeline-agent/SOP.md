# SOP - Color Correction and Grading

## Objective

Produce consistent, natural, cinematic color while preserving detail and continuity across cuts.

## Inputs

- `42_picture_lock.json` — clip list with paths, in/out points, and track assignments.
- Camera profiles and footage metadata (log profile, color space).
- Desired look references (optional reference frame or mood board).

## Procedure

1. Extract frames for correction using ComfyUI VideoHelperSuite on local `:8188`: `Load Video (Upload)` → extract every Nth frame at working resolution.
2. Apply conversion LUT when source is log footage (S-Log2/3, Log-C, etc.) — apply via FFmpeg server `POST /session/{id}/process-asset` with filter `lut3d=<conversion.cube>`.
3. Run base correction pass via ComfyUI EasyColorCorrector (`Auto` mode):
   - `EasyColorCorrect` node with `mode: "Auto"` → AI balances exposure and white balance per clip.
   - Record per-clip correction values in `50_base_corrections.json`.
4. Under correction, fine-tune manually where auto results are unsatisfactory:
   - Correct clip-level exposure and white balance.
   - Balance contrast using wheels (shadows, mids, highs).
   - Fine tune with curves (mild S curve).
5. Apply cross-clip consistency pass via color-matcher CLI:
   - Select the best-corrected clip as reference frame: `reference_frame.png`.
   - Run: `color-matcher -s './frames/' -r reference_frame.png -m 'mkl'`
   - This batch-matches all clips to the reference palette.
6. Apply creative look via ComfyUI EasyColorCorrector (`Preset` mode):
   - Select look preset (film emulation recommended: `Kodak Portra`, `Fuji Velvia`, etc.).
   - Set intensity to 30-60% (`blend_strength` parameter).
   - Record look name and intensity in `51_look_layers.json`.
7. Handle special cases:
   - Window recovery: add highlight roll-off via EasyColorCorrector `Manual` mode curves.
   - Skin tone isolation when talent is on screen — use masks if available.
   - Day to night transitions: grade each segment independently, blend at cut point.
8. Run scope-based QC (waveform and vectorscope checks via FFmpeg `scale=128:72,waveform` filter).
9. Mark heavy denoise/sharpen tasks for final render stage only — do not apply pre-export.

## Quality gates

- No clipped highlights unless artistically intentional and documented.
- No crushed blacks that remove room detail.
- White balance continuity across adjacent clips.
- Creative LUT intensity stays subtle unless project style demands otherwise.

## Outputs

- `50_base_corrections.json` — per-clip correction values (exposure delta, WB shift, contrast params).
- `51_look_layers.json` — look preset applied, blend intensity, any per-clip overrides.
- `52_color_qc.json` — pass/warn/fail per clip: clipping, white balance continuity, LUT intensity check.
