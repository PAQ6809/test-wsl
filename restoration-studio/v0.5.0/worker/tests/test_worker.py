from pathlib import Path
import hashlib

from restoration_worker.pipeline import segment_plan
from restoration_worker.server import _reconcile_ingest, safe_name
from restoration_worker.state import write_json_atomic


def test_segment_plan_two_hours():
    plan = segment_plan(7200, 300)
    assert len(plan) == 24
    assert plan[-1]["start_seconds"] == 6900
    assert plan[-1]["duration_seconds"] == 300


def test_safe_name_blocks_traversal():
    assert safe_name("../../private movie.MP4") == "private_movie.mp4"


def test_reconcile_ingest_recovers_fsynced_part(tmp_path: Path):
    src = tmp_path / "source.bin"
    prefix = b"prefix"
    payload = b"cloud-part" * 1024
    src.write_bytes(prefix + payload)
    log_path = tmp_path / "ingest.json"
    write_json_atomic(log_path, {"parts": {}, "pending": {
        "part_number": 2, "offset": len(prefix), "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }})
    log = _reconcile_ingest(src, log_path)
    assert log["pending"] is None
    assert log["parts"]["2"]["end_offset"] == len(prefix) + len(payload)
    assert src.read_bytes() == prefix + payload


def test_reconcile_ingest_truncates_partial_append(tmp_path: Path):
    src = tmp_path / "source.bin"
    prefix = b"prefix"
    payload = b"cloud-part" * 1024
    src.write_bytes(prefix + payload[:100])
    log_path = tmp_path / "ingest.json"
    write_json_atomic(log_path, {"parts": {}, "pending": {
        "part_number": 2, "offset": len(prefix), "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }})
    log = _reconcile_ingest(src, log_path)
    assert log["pending"] is None
    assert src.read_bytes() == prefix
