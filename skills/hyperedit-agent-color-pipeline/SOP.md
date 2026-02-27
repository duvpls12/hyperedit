# SOP - Color Correction and Grading

## Objective

Produce consistent, natural, cinematic color while preserving detail and continuity across cuts.

## Inputs

- Picture locked edit.
- Camera profiles and footage metadata.
- Desired look references.

## Procedure

1. Apply conversion LUT layer when source is log footage.
2. Under conversion, correct clip level exposure and white balance.
3. Balance contrast using wheels (shadows, mids, highs).
4. Fine tune with curves (mild S curve).
5. Apply creative look LUT on top at reduced intensity (typically 30-60%).
6. Match adjacent clips and room transitions.
7. Handle special cases:
- Window recovery and highlight control.
- Skin tone isolation when talent is on screen.
- Day to night transitions and glow effects only if motivated.
8. Run scope based QC (waveform and clipping checks).
9. Mark heavy denoise/sharpen tasks for final render stage only.

## Quality gates

- No clipped highlights unless artistically intentional and documented.
- No crushed blacks that remove room detail.
- White balance continuity across adjacent clips.
- Creative LUT intensity stays subtle unless project style demands otherwise.

## Outputs

- `40_base_corrections.json`
- `41_look_layers.json`
- `42_color_qc.json`
