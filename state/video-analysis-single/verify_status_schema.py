#!/usr/bin/env python3
"""Tiny schema verifier for control-pane status.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

STATUS_PATH = Path("state/video-analysis-single/status.json")

REQUIRED: Dict[str, type] = {
    "schema_version": int,
    "timestamp": str,
    "queue_depth": int,
    "queue_depth_min": int,
    "queue_depth_target": int,
    "below_threshold_consecutive": int,
    "below_threshold_limit": int,
    "lock_state": str,
    "disk_free_root_gb": int,
    "disk_free_charlie_gb": int,
    "disk_threshold_root_gb": int,
    "disk_threshold_charlie_gb": int,
    "worker_active": bool,
    "action_taken": str,
    "action_reason": str,
}

ACTIONS = {"ensure_worker", "restage_queue", "clear_stale_lock", "no_op"}
LOCK_RE = re.compile(r"^(none|live:\d+|stale:[^\s]+)$")


def fail(errors: List[str]) -> int:
    print("FAIL")
    for err in errors:
        print(f"- {err}")
    return 1


def main() -> int:
    if not STATUS_PATH.exists():
        return fail([f"missing file: {STATUS_PATH}"])

    try:
        data: Any = json.loads(STATUS_PATH.read_text())
    except json.JSONDecodeError as exc:
        return fail([f"invalid JSON: {exc}"])

    if not isinstance(data, dict):
        return fail(["top-level value must be an object"])

    errors: List[str] = []

    for key, typ in REQUIRED.items():
        if key not in data:
            errors.append(f"missing field: {key}")
            continue
        if typ is bool:
            if not isinstance(data[key], bool):
                errors.append(f"field {key} must be boolean")
        elif not isinstance(data[key], typ):
            errors.append(f"field {key} must be {typ.__name__}")

    if "lock_state" in data and isinstance(data["lock_state"], str):
        if not LOCK_RE.match(data["lock_state"]):
            errors.append("field lock_state must match none|live:<pid>|stale:<reason>")

    if "action_taken" in data and isinstance(data["action_taken"], str):
        if data["action_taken"] not in ACTIONS:
            errors.append(f"field action_taken must be one of {sorted(ACTIONS)}")

    for int_key in [
        "queue_depth",
        "queue_depth_min",
        "queue_depth_target",
        "below_threshold_consecutive",
        "below_threshold_limit",
    ]:
        if int_key in data and isinstance(data[int_key], int) and data[int_key] < 0:
            errors.append(f"field {int_key} must be >= 0")

    if errors:
        return fail(errors)

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
