from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

class AtomicState:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"last_part": 0, "source_bytes": 0, "segments": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict[str, Any]) -> None:
        temp = self.path.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        temp.replace(self.path)
