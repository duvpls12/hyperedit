# HyperEdit Vision Fallback SOP (11B → 8B → 4B)

## Decision
Adopt a hard-coded vision fallback ladder with strict single-instance policy.

## Runtime Policy
1. Enforce exactly one managed vision instance.
2. Try 11B first for highest quality.
3. On 11B load/inference failure, unload + demote to 8B and restart current video pass.
4. On 8B failure, unload + demote to 4B and restart current video pass.
5. On 4B failure, write `<video_id>_failed.json` and continue batch.

## Determinism + Auditability
- Every pass output must include:
  - `vision_model_used`
  - `vision_fallback_chain`
- Keep deterministic JSON schemas and deterministic file paths.

## Quality Mode
- 8B remains production core for stability.
- 11B is used as preferred model when available and stable.
- Optional 11B refinement can be run selectively on hero/low-confidence shots.
