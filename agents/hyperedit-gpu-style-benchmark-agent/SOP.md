# SOP - Style Benchmark

## Inputs

- Mined per-video feature artifacts.
- Optional performance metrics (watch time, shares, saves).

## Procedure

1. Normalize feature vectors across videos.
2. Cluster videos by:
- pacing profile
- transition density
- movement continuity
- audio energy profile
- hook/rehook structure
3. Build archetype profiles:
- `luxury_cinematic`
- `family_friendly_mls`
- `signature_reel`
- `ai_lot_transform`
4. Rank top-performing archetypes by available metrics.
5. Produce anti-pattern set for low-performing clusters.
6. Export practical rule cards for agent training.

## Outputs

- `style_clusters.json`
- `archetype_profiles.json`
- `anti_patterns.json`
- `benchmark_report.md`
