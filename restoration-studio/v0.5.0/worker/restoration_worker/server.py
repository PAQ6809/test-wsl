from __future__ import annotations

import json
import mimetypes
import os
import platform
import re
import shutil
import socket
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import __version__
from .cloud import CloudClient
from .config import WorkerConfig, load_config
from .pipeline import Cancelled, ffprobe, process_media, sha256_file
from .state import patch_state, read_json, write_json_atomic

CONFIG: WorkerConfig = load_config()
CLOUD = CloudClient(CONFIG)
WORKER_ID = f"{socket.gethostname()}-{uuid.uuid5(uuid.NAMESPACE_DNS, str(CONFIG.home)).hex[:10]}"
STOP = threading.Event()
THREADS: list[threading.Thread] = []
ACTIVE: set[str] = set()
ACTIVE_LOCK = threading.Lock()
DOWNLOAD_TOKENS: dict[str, tuple[str, float]] = {}
DOWNLOAD_LOCK = threading.Lock()


def safe_name(name: str) -> str:
    name = Path(name).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem).strip("._")[:100] or "media"
    return stem + Path(name).suffix.lower()


def job_dir(job_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-fA-F-]{32,36}", job_id):
        raise HTTPException(400, "不正確的工作編號")
    return CONFIG.jobs_dir / job_id


def check_pairing(value: str | None) -> None:
    if not value or not secrets_compare(value, CONFIG.pairing_secret):
        raise HTTPException(401, "本機 Worker 配對密碼不正確")


def secrets_compare(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a.encode(), b.encode())


def capabilities() -> dict[str, Any]:
    return {"ffmpeg": shutil.which("ffmpeg") is not None, "ffprobe": shutil.which("ffprobe") is not None,
            "platform": platform.platform(), "cpu_count": os.cpu_count(), "local_api": True,
            "cloud_relay": CLOUD.enabled, "segment_seconds": CONFIG.segment_seconds,
            "video2x": bool(CONFIG.external_commands.get("video2x")),
            "flashvsr": bool(CONFIG.external_commands.get("flashvsr")),
            "seedvr": bool(CONFIG.external_commands.get("seedvr"))}


def cloud_progress(job_id: str, stage: str, progress: float, status: str = "processing", result: dict[str, Any] | None = None) -> None:
    if CLOUD.enabled:
        CLOUD.progress(WORKER_ID, job_id, status=status, stage=stage, progress=progress, result_metadata=result or {})


def process_job(local_dir: Path) -> None:
    job_id = local_dir.name
    with ACTIVE_LOCK:
        if job_id in ACTIVE:
            return
        ACTIVE.add(job_id)
    try:
        state = read_json(local_dir / "state.json", {}) or {}
        src = local_dir / "source" / state["safe_name"]
        out_ext = ".jpg" if src.suffix.lower() in {".jpg", ".jpeg"} else (src.suffix.lower() if src.suffix.lower() in {".png", ".webp"} else ".mp4")
        out = local_dir / "output" / f"restored-{Path(state['safe_name']).stem}{out_ext}"
        out.parent.mkdir(parents=True, exist_ok=True)
        cancel_file = local_dir / "cancel.requested"
        patch_state(local_dir, status="processing", stage="準備處理", progress=max(10, float(state.get("progress", 0))))
        cloud_progress(job_id, "準備處理", 10)

        def progress(stage: str, value: float, segment: dict[str, Any] | None) -> None:
            patch_state(local_dir, status="processing", stage=stage, progress=round(value, 2))
            cloud_progress(job_id, stage, value)
            if segment and CLOUD.enabled:
                payload = dict(segment)
                payload.setdefault("status", "processing")
                CLOUD.segment(job_id, **payload)

        result = process_media(src, out, local_dir, CONFIG, state.get("preset", "balanced"), int(state.get("target_height", 1080)),
                               state.get("options", {}), progress, cancel_file.exists)
        report = {"version": __version__, "job_id": job_id, "completed_at": time.time(), "input": str(src),
                  "output": str(out), "input_sha256": sha256_file(src), "output_sha256": sha256_file(out), **result}
        write_json_atomic(local_dir / "report.json", report)
        patch_state(local_dir, status="completed", stage="完成", progress=100, output_path=str(out),
                    output_name=out.name, output_size=out.stat().st_size, output_sha256=report["output_sha256"], report=report)
        if CLOUD.enabled:
            CLOUD.complete_local(WORKER_ID, job_id, filename=out.name, size=out.stat().st_size,
                                 sha256=report["output_sha256"], mime=mimetypes.guess_type(out.name)[0] or "application/octet-stream",
                                 result_metadata=report)
    except Cancelled as exc:
        patch_state(local_dir, status="cancelled", stage="已安全停止", error=str(exc))
        if CLOUD.enabled:
            CLOUD.fail(WORKER_ID, job_id, str(exc), "CANCELLED", True)
    except Exception as exc:
        patch_state(local_dir, status="failed", stage="處理失敗", error=str(exc))
        if CLOUD.enabled:
            try:
                CLOUD.fail(WORKER_ID, job_id, str(exc))
            except Exception:
                pass
    finally:
        with ACTIVE_LOCK:
            ACTIVE.discard(job_id)


def start_processing(local_dir: Path) -> None:
    thread = threading.Thread(target=process_job, args=(local_dir,), daemon=True, name=f"job-{local_dir.name[:8]}")
    thread.start()
    THREADS.append(thread)


def _hash_slice(path: Path, offset: int, size: int) -> str:
    import hashlib
    digest = hashlib.sha256()
    remaining = size
    with path.open("rb") as handle:
        handle.seek(offset)
        while remaining:
            block = handle.read(min(1024 * 1024, remaining))
            if not block:
                break
            digest.update(block)
            remaining -= len(block)
    if remaining:
        raise RuntimeError("本機中繼片段長度不足")
    return digest.hexdigest()


def _reconcile_ingest(src: Path, log_path: Path) -> dict[str, Any]:
    """Recover the narrow crash window between fsync and cloud acknowledgement."""
    log = read_json(log_path, {"parts": {}, "pending": None}) or {"parts": {}, "pending": None}
    log.setdefault("parts", {})
    pending = log.get("pending")
    if not pending:
        return log
    offset = int(pending["offset"])
    size = int(pending["size"])
    expected_end = offset + size
    current = src.stat().st_size if src.exists() else 0
    if current == expected_end and _hash_slice(src, offset, size) == pending["sha256"]:
        log["parts"][str(pending["part_number"])] = {
            "size": size, "sha256": pending["sha256"], "end_offset": expected_end,
        }
        log["pending"] = None
        write_json_atomic(log_path, log)
        return log
    if current != offset:
        with src.open("r+b") as handle:
            handle.truncate(offset)
            handle.flush()
            os.fsync(handle.fileno())
    log["pending"] = None
    write_json_atomic(log_path, log)
    return log


def ingest_cloud_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    local_dir = CONFIG.jobs_dir / job_id
    source_dir = local_dir / "source"
    incoming_dir = local_dir / "incoming"
    source_dir.mkdir(parents=True, exist_ok=True)
    incoming_dir.mkdir(parents=True, exist_ok=True)
    name = safe_name(job.get("safe_name") or job.get("filename") or f"input{job.get('extension') or '.bin'}")
    src = source_dir / name
    src.touch(exist_ok=True)
    ingest_log_path = local_dir / "ingest.json"
    ingest_log = _reconcile_ingest(src, ingest_log_path)
    state = read_json(local_dir / "state.json", {}) or {}
    if not state:
        state = {"job_id": job_id, "filename": job.get("filename"), "safe_name": name, "size": int(job.get("file_size") or 0),
                 "mime": job.get("media_type"), "preset": job.get("preset", "balanced"),
                 "target_height": int(job.get("target_height") or 1080), "options": job.get("options") or {},
                 "status": "ingesting", "stage": "接收雲端分段", "progress": float(job.get("progress") or 0),
                 "received": src.stat().st_size}
        write_json_atomic(local_dir / "state.json", state)

    while not STOP.is_set():
        part = CLOUD.next_part(job_id)
        if not part:
            latest = CLOUD.progress(WORKER_ID, job_id, status="ingesting", stage="等待後續上傳分段",
                                    progress=min(9.5, (src.stat().st_size / max(1, int(job.get('file_size') or 1))) * 9.5))
            if latest.get("cancel_requested"):
                raise Cancelled("使用者取消")
            if latest.get("upload_complete"):
                break
            time.sleep(2)
            continue

        part_number = int(part["part_number"])
        key = str(part_number)
        completed = ingest_log["parts"].get(key)
        if completed:
            if int(completed["size"]) != int(part["size"]) or completed["sha256"] != part["sha256"]:
                raise RuntimeError(f"第 {part_number} 段雲端中繼資料與本機日誌不一致")
            CLOUD.consume_part(job_id, part_number)
            continue

        temp = incoming_dir / f"part-{part_number:06d}.download"
        digest = __import__("hashlib").sha256()
        count = 0
        with temp.open("wb") as download:
            with httpx.stream("GET", part["signed_url"], timeout=120, follow_redirects=True) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes(1024 * 1024):
                    download.write(chunk)
                    digest.update(chunk)
                    count += len(chunk)
            download.flush()
            os.fsync(download.fileno())
        if count != int(part["size"]) or digest.hexdigest() != part["sha256"]:
            temp.unlink(missing_ok=True)
            raise RuntimeError(f"第 {part_number} 段雜湊或大小不符")

        offset = src.stat().st_size
        ingest_log["pending"] = {"part_number": part_number, "offset": offset, "size": count, "sha256": digest.hexdigest()}
        write_json_atomic(ingest_log_path, ingest_log)
        with src.open("ab") as handle, temp.open("rb") as download:
            shutil.copyfileobj(download, handle, length=1024 * 1024)
            handle.flush()
            os.fsync(handle.fileno())
        ingest_log["parts"][key] = {"size": count, "sha256": digest.hexdigest(), "end_offset": offset + count}
        ingest_log["pending"] = None
        write_json_atomic(ingest_log_path, ingest_log)
        CLOUD.consume_part(job_id, part_number)
        temp.unlink(missing_ok=True)
        patch_state(local_dir, received=src.stat().st_size, stage=f"已安全接收第 {part_number} 段")

    if src.stat().st_size != int(job.get("file_size") or 0):
        raise RuntimeError(f"重組檔案大小不符: {src.stat().st_size} / {job.get('file_size')}")
    expected = job.get("input_sha256")
    if expected and sha256_file(src) != expected:
        raise RuntimeError("重組後整體 SHA-256 不符")
    try:
        ffprobe(src)
    except Exception as exc:
        raise RuntimeError(f"重組後媒體驗證失敗: {exc}") from exc
    patch_state(local_dir, status="processing", stage="雲端分段重組完成", received=src.stat().st_size, progress=10)
    process_job(local_dir)


def cloud_loop() -> None:
    if not CLOUD.enabled:
        return
    caps = capabilities()
    try:
        CLOUD.register(WORKER_ID, caps, __version__)
    except Exception:
        pass
    current: str | None = None
    last_heartbeat = 0.0
    while not STOP.wait(0.5):
        try:
            if time.time() - last_heartbeat > 15:
                CLOUD.heartbeat(WORKER_ID, "busy" if current else "idle", current, caps, __version__)
                last_heartbeat = time.time()
            job = CLOUD.claim(WORKER_ID)
            if not job:
                STOP.wait(CONFIG.poll_seconds)
                continue
            current = str(job["id"])
            ingest_cloud_job(job)
            current = None
        except Exception as exc:
            if current:
                try:
                    CLOUD.fail(WORKER_ID, current, str(exc), "INGEST_FAILURE")
                except Exception:
                    pass
            current = None
            STOP.wait(min(15, CONFIG.poll_seconds * 2))


@asynccontextmanager
async def lifespan(_: FastAPI):
    CONFIG.jobs_dir.mkdir(parents=True, exist_ok=True)
    STOP.clear()
    if CLOUD.enabled:
        thread = threading.Thread(target=cloud_loop, daemon=True, name="cloud-poller")
        thread.start(); THREADS.append(thread)
    yield
    STOP.set()
    for thread in THREADS:
        thread.join(timeout=3)


app = FastAPI(title="Restoration Studio Personal Worker", version=__version__, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CONFIG.allowed_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                   allow_headers=["Content-Type", "X-Restoration-Pairing"])


class JobInit(BaseModel):
    job_id: str
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)
    mime: str = "application/octet-stream"
    preset: str = "balanced"
    target_height: int = 1080
    options: dict[str, Any] = Field(default_factory=dict)


@app.get("/v1/health")
def health() -> dict[str, Any]:
    return {"ok": shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None,
            "version": __version__, "worker_id": WORKER_ID, "worker_name": CONFIG.worker_name,
            "cloud_connected": CLOUD.enabled, "capabilities": capabilities(),
            "free_disk_bytes": shutil.disk_usage(CONFIG.home).free}


@app.post("/v1/jobs")
def create_job(payload: JobInit, x_restoration_pairing: str | None = Header(default=None)) -> dict[str, Any]:
    check_pairing(x_restoration_pairing)
    if payload.size > CONFIG.max_upload_bytes:
        raise HTTPException(413, "檔案超過 Worker 上限")
    local_dir = job_dir(payload.job_id)
    local_dir.mkdir(parents=True, exist_ok=True)
    source = local_dir / "source"; source.mkdir(exist_ok=True)
    name = safe_name(payload.filename)
    part = source / f"{name}.part"
    if not part.exists(): part.touch()
    state = {"job_id": payload.job_id, "filename": payload.filename, "safe_name": name, "size": payload.size,
             "mime": payload.mime, "preset": payload.preset, "target_height": payload.target_height,
             "options": payload.options, "status": "uploading", "stage": "本機可續傳上傳", "progress": 0,
             "received": part.stat().st_size, "created_at": time.time()}
    write_json_atomic(local_dir / "state.json", state)
    return state


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str, x_restoration_pairing: str | None = Header(default=None)) -> dict[str, Any]:
    check_pairing(x_restoration_pairing)
    state = read_json(job_dir(job_id) / "state.json")
    if not state: raise HTTPException(404, "找不到工作")
    return state


@app.put("/v1/jobs/{job_id}/chunk")
async def upload_chunk(job_id: str, request: Request, offset: int,
                       x_restoration_pairing: str | None = Header(default=None)) -> dict[str, Any]:
    check_pairing(x_restoration_pairing)
    local_dir = job_dir(job_id)
    state = read_json(local_dir / "state.json")
    if not state: raise HTTPException(404, "找不到工作")
    part = local_dir / "source" / f"{state['safe_name']}.part"
    current = part.stat().st_size if part.exists() else 0
    if offset != current: raise HTTPException(409, detail={"expected_offset": current})
    data = await request.body()
    if not data or len(data) > 16 * 1024 * 1024: raise HTTPException(400, "分段大小不正確")
    if current + len(data) > int(state["size"]): raise HTTPException(400, "分段超過檔案大小")
    with part.open("ab") as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())
    received = part.stat().st_size
    patch_state(local_dir, received=received, progress=received / int(state["size"]) * 10,
                stage=f"本機上傳 {received / int(state['size']) * 100:.1f}%")
    return {"received": received, "size": state["size"]}


@app.post("/v1/jobs/{job_id}/complete")
def complete_upload(job_id: str, x_restoration_pairing: str | None = Header(default=None)) -> dict[str, Any]:
    check_pairing(x_restoration_pairing)
    local_dir = job_dir(job_id); state = read_json(local_dir / "state.json")
    if not state: raise HTTPException(404, "找不到工作")
    part = local_dir / "source" / f"{state['safe_name']}.part"
    if not part.exists() or part.stat().st_size != int(state["size"]):
        raise HTTPException(409, "檔案尚未完整上傳")
    final = local_dir / "source" / state["safe_name"]
    part.replace(final)
    try: ffprobe(final)
    except Exception as exc:
        final.unlink(missing_ok=True); raise HTTPException(415, f"媒體驗證失敗: {exc}") from exc
    patch_state(local_dir, status="queued", stage="來源驗證完成", progress=10, received=final.stat().st_size)
    start_processing(local_dir)
    return read_json(local_dir / "state.json")


@app.post("/v1/jobs/{job_id}/cancel")
def cancel(job_id: str, x_restoration_pairing: str | None = Header(default=None)) -> dict[str, bool]:
    check_pairing(x_restoration_pairing)
    local_dir = job_dir(job_id)
    if not local_dir.exists(): raise HTTPException(404, "找不到工作")
    (local_dir / "cancel.requested").touch()
    patch_state(local_dir, stage="正在安全停止")
    return {"cancel_requested": True}


@app.post("/v1/jobs/{job_id}/download-token")
def create_download_token(job_id: str, x_restoration_pairing: str | None = Header(default=None)) -> dict[str, str | int]:
    check_pairing(x_restoration_pairing)
    state = read_json(job_dir(job_id) / "state.json")
    if not state or state.get("status") != "completed": raise HTTPException(404, "成品尚未完成")
    import secrets
    token = secrets.token_urlsafe(32)
    with DOWNLOAD_LOCK:
        DOWNLOAD_TOKENS[token] = (job_id, time.time() + 90)
    return {"token": token, "expires_in": 90}


@app.get("/v1/jobs/{job_id}/download")
def download(job_id: str, token: str | None = None, x_restoration_pairing: str | None = Header(default=None)):
    authorized = False
    if x_restoration_pairing:
        check_pairing(x_restoration_pairing); authorized = True
    elif token:
        with DOWNLOAD_LOCK:
            item = DOWNLOAD_TOKENS.pop(token, None)
        authorized = bool(item and item[0] == job_id and item[1] >= time.time())
    if not authorized: raise HTTPException(401, "下載授權已失效")
    state = read_json(job_dir(job_id) / "state.json")
    if not state or state.get("status") != "completed": raise HTTPException(404, "成品尚未完成")
    path = Path(state["output_path"])
    if not path.exists(): raise HTTPException(404, "成品不存在")
    return FileResponse(path, filename=state.get("output_name") or path.name)


@app.get("/v1/jobs/{job_id}/report")
def report(job_id: str, x_restoration_pairing: str | None = Header(default=None)):
    check_pairing(x_restoration_pairing)
    path = job_dir(job_id) / "report.json"
    if not path.exists(): raise HTTPException(404, "報告尚未完成")
    return FileResponse(path, media_type="application/json", filename=f"{job_id}-truth-report.json")
