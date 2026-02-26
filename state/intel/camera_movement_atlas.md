# Camera Movement Atlas

> Derived from **7,430 frames** across **14 videos** (qwen2.5vl:7b, 5 fps, 720px)
> Generated: 2026-02-26

## Summary

| Movement Category | Frames | % |
|---|---|---|
| static / locked | 5,230 | 70.4% |
| horizontal pan | 1,827 | 24.6% |
| drone / aerial | 368 | 5.0% |
| gimbal walk | 3 | 0.0% |
| tilt | 2 | 0.0% |

## Key Insight

**Static/locked shots dominate at ~70%** (static + stationary + still + none combined).
Horizontal panning (pan + panning + horizontal) accounts for ~25% of movement.
Drone/aerial appears in ~5% of frames — reserved for establishing shots and exterior reveals.

## Raw Label Breakdown

| Label (raw) | Frames | % |
|---|---|---|
| `static` | 4,047 | 54.5% |
| `horizontal` | 1,035 | 13.9% |
| `none` | 969 | 13.0% |
| `pan` | 411 | 5.5% |
| `drone_flyover` | 368 | 5.0% |
| `panning` | 294 | 4.0% |
| `stationary` | 173 | 2.3% |
| `horizontal pan` | 87 | 1.2% |
| `still` | 37 | 0.5% |

## Editorial Rules Derived

1. **Default to static** — majority of shots are locked. Movement is an accent, not a default.
2. **Pan = the workhorse** — when movement appears, it's almost always a slow horizontal pan.
3. **Drone for openers and exteriors only** — aerial > 5fps is exceptional; treat as a premium cut.
4. **Gimbal walk is rare** (<0.1%) — used sparingly for immersive interior walkthroughs.
5. **No whip pans, speed ramps, or push/pull** detected in corpus — these would read as stylistically aggressive for this market.