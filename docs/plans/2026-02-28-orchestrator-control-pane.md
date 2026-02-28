# Orchestrator Control Pane (2026-02-28)

## Goal

Create a single control-plane artifact at `state/video-analysis-single/status.json` and make both orchestration loops use one deterministic policy engine.

## Source of truth

Path: `state/video-analysis-single/status.json`

This file now carries queue health, lock health, disk headroom, worker state, and last policy action.

## Policy table

`state/video-analysis-single/control_pane_policy.py` evaluates `status.json` in this priority order:

| Priority | Condition | Action |
|---|---|---|
| 1 | `disk_free_root_gb < disk_threshold_root_gb` OR `disk_free_charlie_gb < disk_threshold_charlie_gb` | `no_op` |
| 2 | `lock_state` starts with `stale:` | `clear_stale_lock` |
| 3 | `queue_depth < queue_depth_min` AND `below_threshold_consecutive >= below_threshold_limit` | `restage_queue` |
| 4 | `worker_active == false` AND `lock_state` is not `live:<pid>` | `ensure_worker` |
| 5 | Otherwise | `no_op` |

## status.json fields

| Field | Type | Description |
|---|---|---|
| `schema_version` | int | Schema/version marker for control-pane shape. |
| `timestamp` | string | Last status update time in ISO-8601. |
| `queue_depth` | int | Current number of queued video files. |
| `queue_depth_min` | int | Minimum acceptable queue depth. |
| `queue_depth_target` | int | Restage target queue depth. |
| `below_threshold_consecutive` | int | Consecutive checks where queue depth is below minimum. |
| `below_threshold_limit` | int | Consecutive-breach count required before restaging. |
| `lock_state` | string | `none`, `live:<pid>`, or `stale:<reason>`. |
| `disk_free_root_gb` | int | Free GB on root volume (`/Users/...`). |
| `disk_free_charlie_gb` | int | Free GB on `/Volumes/Charlie`. |
| `disk_threshold_root_gb` | int | Minimum safe free GB for root volume. |
| `disk_threshold_charlie_gb` | int | Minimum safe free GB for Charlie volume. |
| `worker_active` | bool | Whether the batch worker process is running. |
| `action_taken` | string | Last policy action (`ensure_worker`, `restage_queue`, `clear_stale_lock`, `no_op`). |
| `action_reason` | string | Short deterministic reason for `action_taken`. |

## Logging

Control actions are appended to:

- `state/video-analysis-single/logs/control-pane.log`

Format is one line per action with timestamp, source (`loop` or `watchdog`), action, reason, queue/lock/worker, and disk metrics.

## Verifier

Schema verifier:

- `state/video-analysis-single/verify_status_schema.py`

Usage:

```bash
python3 state/video-analysis-single/verify_status_schema.py
```

Outputs `PASS` or `FAIL` and exits non-zero on failure.
