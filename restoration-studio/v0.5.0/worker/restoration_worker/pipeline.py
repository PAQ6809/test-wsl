from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from .config import WorkerConfig
from .state import read_json, write_json_atomic

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".ts", ".mts", ".m2ts"}


class Cancelled(RuntimeError):
    pass


def sha256_file(path: Path, chunk: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while data := handle.read(chunk):
            digest.update(data)
    return digest.hexdigest()


def ffprobe(path: Path) -> dict[str, Any]:
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFprobe 失敗: {proc.stderr[-2000:]}")
    return json.loads(proc.stdout)


def duration_of(meta: dict[str, Any]) -> float:
    try:
        return float(meta.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        return 0.0


def segment_plan(duration: float, segment_seconds: int) -> list[dict[str, Any]]:
    if duration <= 0:
        return [{"segment_index": 0, "start_seconds": 0.0, "duration_seconds": 0.0}]
    count = max(1, math.ceil(duration / segment_seconds))
    return [{"segment_index": i, "start_seconds": i * segment_seconds,
             "duration_seconds": min(segment_seconds, max(0.001, duration - i * segment_seconds))}
            for i in range(count)]


def ensure_disk(config: WorkerConfig, needed: int) -> None:
    free = shutil.disk_usage(config.home).free
    requirement = max(config.min_free_disk_bytes, needed)
    if free < requirement:
        raise RuntimeError(f"磁碟空間不足，需要至少 {requirement / 1024**3:.1f} GB，可用 {free / 1024**3:.1f} GB")


def enhance_image(src: Path, out: Path, preset: str, target_height: int) -> dict[str, Any]:
    raw = np.fromfile(src, dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("圖片無法解碼")
    before_h, before_w = image.shape[:2]
    strengths = {"light": (3, 0.35), "balanced": (5, 0.55), "strong": (7, 0.75)}
    denoise, sharp = strengths.get(preset, strengths["balanced"])
    restored = cv2.fastNlMeansDenoisingColored(image, None, denoise, denoise, 7, 21)
    if target_height > restored.shape[0]:
        scale = target_height / restored.shape[0]
        restored = cv2.resize(restored, (int(round(restored.shape[1] * scale)), target_height), interpolation=cv2.INTER_LANCZOS4)
    blurred = cv2.GaussianBlur(restored, (0, 0), 1.2)
    restored = cv2.addWeighted(restored, 1 + sharp, blurred, -sharp, 0)
    ext = out.suffix.lower()
    params = [cv2.IMWRITE_JPEG_QUALITY, 95] if ext in {".jpg", ".jpeg"} else []
    ok, encoded = cv2.imencode(ext if ext in IMAGE_EXTS else ".png", restored, params)
    if not ok:
        raise RuntimeError("圖片輸出編碼失敗")
    temp = out.with_suffix(out.suffix + ".part")
    encoded.tofile(temp)
    temp.replace(out)
    return {"kind": "image", "input_resolution": [before_w, before_h],
            "output_resolution": [restored.shape[1], restored.shape[0]], "preset": preset,
            "truth_note": "改善壓縮、雜訊與觀看清晰度；不宣稱找回已被刪除或遮蔽的原始像素。"}


def build_filters(meta: dict[str, Any], preset: str, target_height: int, options: dict[str, Any]) -> str:
    stream = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), {})
    filters: list[str] = []
    field = str(stream.get("field_order", "progressive"))
    if options.get("deinterlace", True) and field not in {"progressive", "unknown", ""}:
        filters.append("bwdif=mode=send_frame:parity=auto:deint=all")
    if options.get("deblock", True):
        value = {"light": "filter=weak:block=8:alpha=0.07:beta=0.035:gamma=0.04:delta=0.04",
                 "balanced": "filter=weak:block=8:alpha=0.09:beta=0.045:gamma=0.05:delta=0.05",
                 "strong": "filter=strong:block=8:alpha=0.11:beta=0.065:gamma=0.055:delta=0.055"}.get(preset)
        filters.append(f"deblock={value}")
    if options.get("denoise", True):
        filters.append({"light": "hqdn3d=0.8:0.8:2.5:2.5", "balanced": "hqdn3d=1.3:1.2:4.2:4.0",
                        "strong": "hqdn3d=2.2:2.0:6.0:5.0"}.get(preset, "hqdn3d=1.3:1.2:4.2:4.0"))
    if options.get("deband", True):
        t = {"light": "0.012", "balanced": "0.016", "strong": "0.022"}.get(preset, "0.016")
        filters.append(f"deband=1thr={t}:2thr={t}:3thr={t}:range=16:blur=1:coupling=1")
    if options.get("sharpen", True):
        s = {"light": "0.22", "balanced": "0.36", "strong": "0.50"}.get(preset, "0.36")
        filters.append(f"unsharp=5:5:{s}:5:5:0")
    src_h = int(stream.get("height") or 0)
    if target_height > src_h:
        filters.append(f"scale=-2:{target_height}:flags=lanczos")
    filters.append("format=yuv420p")
    return ",".join(filters)


def run_ffmpeg(cmd: list[str], duration: float, progress: Callable[[float], None], cancelled: Callable[[], bool]) -> None:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    assert proc.stdout is not None
    tail: list[str] = []
    try:
        for line in proc.stdout:
            if cancelled():
                raise Cancelled("使用者取消")
            text = line.strip()
            tail.append(text)
            tail = tail[-80:]
            if text.startswith("out_time_us=") and duration > 0:
                try:
                    progress(min(1.0, int(text.split("=", 1)[1]) / 1_000_000 / duration))
                except ValueError:
                    pass
        code = proc.wait()
        if code:
            raise RuntimeError("FFmpeg 處理失敗:\n" + "\n".join(tail[-20:]))
    except Exception:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(8)
            except subprocess.TimeoutExpired:
                proc.kill()
        raise


def process_video(src: Path, out: Path, job_dir: Path, config: WorkerConfig, preset: str, target_height: int,
                  options: dict[str, Any], progress_cb: Callable[[str, float, dict[str, Any] | None], None],
                  cancelled: Callable[[], bool]) -> dict[str, Any]:
    meta = ffprobe(src)
    duration = duration_of(meta)
    if duration <= 0:
        raise RuntimeError("無法取得影片長度")
    stream = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), None)
    if not stream:
        raise RuntimeError("檔案沒有視訊串流")
    plan = segment_plan(duration, config.segment_seconds)
    segments_dir = job_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    manifest_state = read_json(job_dir / "checkpoints.json", {"segments": {}}) or {"segments": {}}
    filters = build_filters(meta, preset, target_height, options)
    paths: list[Path] = []
    for pos, segment in enumerate(plan):
        idx = segment["segment_index"]
        seg = segments_dir / f"segment-{idx:05d}.mp4"
        checkpoint = manifest_state["segments"].get(str(idx))
        if checkpoint and checkpoint.get("status") == "completed" and seg.exists():
            try:
                ffprobe(seg)
                paths.append(seg)
                progress_cb(f"沿用第 {idx + 1}/{len(plan)} 段檢查點", 15 + 75 * ((pos + 1) / len(plan)), segment)
                continue
            except Exception:
                seg.unlink(missing_ok=True)
        last = ""
        for attempt in range(1, config.segment_retries + 1):
            if cancelled():
                raise Cancelled("使用者取消")
            temp = seg.with_suffix(".part.mp4")
            temp.unlink(missing_ok=True)
            cmd = ["ffmpeg", "-y", "-v", "error"]
            if segment["start_seconds"] > 0:
                cmd += ["-ss", f"{segment['start_seconds']:.6f}"]
            cmd += ["-i", str(src), "-t", f"{segment['duration_seconds']:.6f}", "-map", "0:v:0", "-map", "0:a?",
                    "-vf", filters, "-c:v", "libx264", "-preset", config.ffmpeg_preset,
                    "-crf", str(max(12, min(22, int(options.get("crf", 16))))), "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-avoid_negative_ts", "make_zero", "-reset_timestamps", "1",
                    "-progress", "pipe:1", "-nostats", str(temp)]
            try:
                run_ffmpeg(cmd, segment["duration_seconds"],
                    lambda ratio: progress_cb(f"處理第 {idx + 1}/{len(plan)} 段", 15 + 75 * ((pos + ratio) / len(plan)), segment),
                    cancelled)
                ffprobe(temp)
                temp.replace(seg)
                checksum = sha256_file(seg)
                manifest_state["segments"][str(idx)] = {"status": "completed", "attempts": attempt, "sha256": checksum}
                write_json_atomic(job_dir / "checkpoints.json", manifest_state)
                progress_cb(f"第 {idx + 1} 段完成", 15 + 75 * ((pos + 1) / len(plan)), {**segment, "status": "completed", "attempts": attempt, "checksum": checksum})
                paths.append(seg)
                break
            except Cancelled:
                raise
            except Exception as exc:
                last = str(exc)
                manifest_state["segments"][str(idx)] = {"status": "queued", "attempts": attempt, "error": last}
                write_json_atomic(job_dir / "checkpoints.json", manifest_state)
                if attempt < config.segment_retries:
                    time.sleep(min(10, 2**attempt))
        else:
            raise RuntimeError(f"第 {idx + 1} 段重試後仍失敗: {last}")
    concat = job_dir / "concat.txt"
    concat.write_text("\n".join(f"file '{p.as_posix().replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'" for p in paths), encoding="utf-8")
    temp_out = out.with_suffix(".part.mp4")
    temp_out.unlink(missing_ok=True)
    progress_cb("合併片段並重建索引", 93, None)
    proc = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
                           "-c", "copy", "-movflags", "+faststart", str(temp_out)], capture_output=True, text=True)
    if proc.returncode:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
                        "-c:v", "libx264", "-preset", config.ffmpeg_preset, "-crf", "16", "-c:a", "aac",
                        "-b:a", "192k", "-movflags", "+faststart", str(temp_out)], check=True)
    output_meta = ffprobe(temp_out)
    out_duration = duration_of(output_meta)
    if abs(out_duration - duration) > max(3.0, duration * 0.01):
        raise RuntimeError(f"輸出長度驗證失敗: input={duration:.3f}s output={out_duration:.3f}s")
    temp_out.replace(out)
    out_stream = next((s for s in output_meta.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"kind": "video", "input_duration": duration, "output_duration": out_duration,
            "input_resolution": [int(stream.get("width") or 0), int(stream.get("height") or 0)],
            "output_resolution": [int(out_stream.get("width") or 0), int(out_stream.get("height") or 0)],
            "segments": len(plan), "checkpoint_seconds": config.segment_seconds, "preset": preset,
            "truth_note": "輸出改善壓縮、雜訊與觀看清晰度；不宣稱找回已被刪除或遮蔽的原始像素。"}


def process_media(src: Path, out: Path, job_dir: Path, config: WorkerConfig, preset: str, target_height: int,
                  options: dict[str, Any], progress_cb: Callable[[str, float, dict[str, Any] | None], None],
                  cancelled: Callable[[], bool]) -> dict[str, Any]:
    ensure_disk(config, max(src.stat().st_size * 3, 2 * 1024**3))
    if src.suffix.lower() in IMAGE_EXTS:
        progress_cb("分析並修復圖片", 25, None)
        result = enhance_image(src, out, preset, target_height)
        progress_cb("圖片驗證完成", 96, None)
        return result
    if src.suffix.lower() in VIDEO_EXTS:
        return process_video(src, out, job_dir, config, preset, target_height, options, progress_cb, cancelled)
    raise RuntimeError("不支援的媒體格式")
