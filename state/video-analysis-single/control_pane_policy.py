#!/usr/bin/env python3
"""Deterministic control-pane policy for video analysis orchestration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Tuple

DEFAULT_STATUS: Dict[str, Any] = {
    "schema_version": 1,
    "timestamp": "1970-01-01T00:00:00Z",
    "queue_depth": 0,
    "queue_depth_min": 4,
    "queue_depth_target": 10,
    "below_threshold_consecutive": 0,
    "below_threshold_limit": 2,
    "lock_state": "none",
    "disk_free_root_gb": -1,
    "disk_free_charlie_gb": -1,
    "disk_threshold_root_gb": 5,
    "disk_threshold_charlie_gb": 25,
    "worker_active": False,
    "action_taken": "no_op",
    "action_reason": "initialized",
}


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "on"}:
            return True
        if v in {"0", "false", "no", "off"}:
            return False
    return default


def load_status(path: Path) -> Dict[str, Any]:
    raw: Dict[str, Any] = {}
    if path.exists():
        try:
            maybe = json.loads(path.read_text())
            if isinstance(maybe, dict):
                raw = maybe
        except json.JSONDecodeError:
            raw = {}

    status = dict(DEFAULT_STATUS)
    status.update(raw)

    status["schema_version"] = _as_int(status.get("schema_version"), 1)
    status["queue_depth"] = _as_int(status.get("queue_depth"), DEFAULT_STATUS["queue_depth"])
    status["queue_depth_min"] = _as_int(status.get("queue_depth_min"), DEFAULT_STATUS["queue_depth_min"])
    status["queue_depth_target"] = _as_int(status.get("queue_depth_target"), DEFAULT_STATUS["queue_depth_target"])
    status["below_threshold_consecutive"] = _as_int(
        status.get("below_threshold_consecutive"), DEFAULT_STATUS["below_threshold_consecutive"]
    )
    status["below_threshold_limit"] = _as_int(
        status.get("below_threshold_limit"), DEFAULT_STATUS["below_threshold_limit"]
    )
    status["disk_free_root_gb"] = _as_int(status.get("disk_free_root_gb"), DEFAULT_STATUS["disk_free_root_gb"])
    status["disk_free_charlie_gb"] = _as_int(
        status.get("disk_free_charlie_gb"), DEFAULT_STATUS["disk_free_charlie_gb"]
    )
    status["disk_threshold_root_gb"] = _as_int(
        status.get("disk_threshold_root_gb"), DEFAULT_STATUS["disk_threshold_root_gb"]
    )
    status["disk_threshold_charlie_gb"] = _as_int(
        status.get("disk_threshold_charlie_gb"), DEFAULT_STATUS["disk_threshold_charlie_gb"]
    )
    status["worker_active"] = _as_bool(status.get("worker_active"), DEFAULT_STATUS["worker_active"])
    status["lock_state"] = str(status.get("lock_state") or "none")
    status["timestamp"] = str(status.get("timestamp") or DEFAULT_STATUS["timestamp"])

    return status


def evaluate_policy(status: Dict[str, Any]) -> Tuple[str, str]:
    root_free = status["disk_free_root_gb"]
    root_min = status["disk_threshold_root_gb"]
    charlie_free = status["disk_free_charlie_gb"]
    charlie_min = status["disk_threshold_charlie_gb"]

    low_root = root_free >= 0 and root_free < root_min
    low_charlie = charlie_free >= 0 and charlie_free < charlie_min

    if low_root or low_charlie:
        if low_root and low_charlie:
            return "no_op", "disk_low_root_and_charlie"
        if low_root:
            return "no_op", "disk_low_root"
        return "no_op", "disk_low_charlie"

    lock_state = status["lock_state"]
    if lock_state.startswith("stale:"):
        return "clear_stale_lock", "stale_lock"

    queue_depth = status["queue_depth"]
    queue_depth_min = status["queue_depth_min"]
    below = status["below_threshold_consecutive"]
    below_limit = status["below_threshold_limit"]

    if queue_depth < queue_depth_min and below >= below_limit:
        return "restage_queue", "queue_below_threshold"

    worker_active = status["worker_active"]
    if not worker_active and not lock_state.startswith("live:"):
        return "ensure_worker", "worker_inactive"

    if lock_state.startswith("live:"):
        return "no_op", "live_lock_present"

    return "no_op", "worker_active"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate orchestrator control-pane policy.")
    parser.add_argument("--status", required=True, help="Path to status.json")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    status_path = Path(args.status)
    status = load_status(status_path)
    action, reason = evaluate_policy(status)

    if args.json:
        print(json.dumps({"action": action, "reason": reason}, separators=(",", ":")))
    else:
        print(f"{action}\t{reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
