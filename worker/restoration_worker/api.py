from __future__ import annotations
import time
from pathlib import Path
from typing import Any
import httpx
from .config import settings

class WorkerAPI:
    def __init__(self) -> None:
        self.url = f"{settings.supabase_url}/functions/v1/restoration-worker"
        self.headers = {
            "Authorization": f"Worker {settings.worker_token}",
            "apikey": settings.publishable_key,
            "Content-Type": "application/json",
            "User-Agent": "restoration-worker/1.0.0",
        }
        self.client = httpx.Client(timeout=httpx.Timeout(60, connect=20), follow_redirects=True)

    def call(self, action: str, **payload: Any) -> dict[str, Any]:
        body = {"action": action, "worker_id": settings.worker_id, **payload}
        last: Exception | None = None
        for attempt in range(5):
            try:
                response = self.client.post(self.url, headers=self.headers, json=body)
                data = response.json()
                if response.status_code >= 400 or not data.get("ok", False):
                    raise RuntimeError(data.get("error") or f"HTTP {response.status_code}")
                return data
            except Exception as exc:
                last = exc
                if attempt == 4:
                    break
                time.sleep(min(10, 0.7 * (2**attempt)))
        raise RuntimeError(f"Worker API失敗：{last}")

    def download(self, url: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".download")
        with self.client.stream("GET", url, timeout=None) as response:
            response.raise_for_status()
            with temp.open("wb") as fh:
                for chunk in response.iter_bytes(1024 * 1024):
                    fh.write(chunk)
                fh.flush()
        temp.replace(target)

    def upload_signed(self, signed_url: str, token: str, source: Path, content_type: str) -> None:
        headers = {"Content-Type": content_type, "x-upsert": "true"}
        params = {} if "token=" in signed_url else {"token": token}
        with source.open("rb") as fh:
            response = self.client.put(signed_url, headers=headers, params=params, content=fh, timeout=None)
        if response.status_code >= 400:
            raise RuntimeError(f"成品分段上傳失敗 HTTP {response.status_code}: {response.text[:300]}")
