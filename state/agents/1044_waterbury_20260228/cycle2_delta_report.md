# Cycle 2 Delta Report — 1044 Waterbury Lane

- Generated: 2026-03-01T04:20:56.167282+00:00
- Video: /Volumes/Charlie/deliverables/Jacob Guthrie/1044 Waterbury Lane/1044 Waterbury Lane.mp4
- Cycle 2 objective: real DSP + LM Studio semantic path + QC recompute

## New artifacts
- `/Users/davideby/hyperedit/state/baseline/1044-waterbury/audio_dsp_real.json`
- `/Users/davideby/hyperedit/state/baseline/1044-waterbury/semantic_tags_lmstudio.json`
- `/Users/davideby/hyperedit/state/agents/1044_waterbury_20260228/32_audio_qc.json`
- `/Users/davideby/hyperedit/state/agents/1044_waterbury_20260228/audio_qc_result.json`
- `/Users/davideby/hyperedit/state/agents/1044_waterbury_20260228/assembly_qc_result.json`
- `/Users/davideby/hyperedit/state/baseline/1044-waterbury/cycle2_recreate_spec.json`

## Gate deltas vs Cycle 1

| Gate | Cycle1 | Cycle2 | Delta |
|---|---|---|---|
| G-20 | warn | pass | improved |
| G-21 | warn | warn | no-change |
| G-22 | warn | pass | improved |
| G-23 | pass | pass | no-change |
| G-30 | pass | pass | no-change |
| G-31 | pass | pass | no-change |
| G-32 | warn | warn | no-change |
| G-33 | pass | pass | no-change |

## Summary
- Improved gates: **2**
- Regressed gates: **0**
- Unchanged gates: **6**
- Audio overall: **warn**
- Assembly overall: **warn**

## Notes
- Real beat/onset extraction completed with librosa (non-proxy).
- Semantic tagging executed through LM Studio OpenAI-compatible endpoint (non-Ollama path).
- Limitation: 10 LM Studio frame(s) failed strict JSON parse; those frames excluded from aggregate tags.


## Project-stage sync (2026-03-01T04:47:44+00:00)
- Synced from baseline to project artifact path for deterministic stage reporting.
- Degraded labels retained for missing semantic/color/text passes.
