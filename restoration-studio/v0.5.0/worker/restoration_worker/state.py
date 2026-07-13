from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

_LOCKS: dict[str, threading.RLock] = {}
_MASTER = threading.Lock()


def job_lock(job_id: str) -> threading.RLock:
    with _MASTER:
        return _LOCKS.setdefault(job_id, threading.RLock())


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    with tmp.open("rb") as handle:
        os.fsync(handle.fileno())
    tmp.replace(path)


def patch_state(job_dir: Path, **changes: Any) -> dict[str, Any]:
    job_id = job_dir.name
    with job_lock(job_id):
        path = job_dir / "state.json"
        current = read_json(path, {}) or {}
        current.update(changes)
        write_json_atomic(path, current)
        return current
