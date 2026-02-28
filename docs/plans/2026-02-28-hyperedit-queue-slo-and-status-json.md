# HyperEdit Queue SLO + status.json (2026-02-28)

## What was added

- Queue SLO enforcement in `state/video-analysis-single/run_100_video_assessment_loop.sh`:
  - `queue_depth_min = 4`
  - If queue depth is below threshold for 2 consecutive checks, the loop auto-restages to target depth 10.
- Machine-readable preflight artifact:
  - `state/video-analysis-single/status.json`

## status.json fields

- `timestamp`
- `queue_depth`
- `queue_depth_min`
- `below_threshold_consecutive`
- `lock_state` (`none`, `stale`, `live:<pid>`)
- `disk_free_root_gb`
- `disk_free_charlie_gb`
- `worker_active`
- `action_taken` (`none` or `restage`)

## Lock handling

- The loop now clears only stale `.batch10.lock` files.
- Live locks are respected.
- Batch runner lock acquisition now validates PID ownership and self-heals stale lock files.

## Variant fallback

- Batch runner resolves missing variant filenames (`.f137/.f247/.f399`) to canonical `.mp4` candidates when available.
