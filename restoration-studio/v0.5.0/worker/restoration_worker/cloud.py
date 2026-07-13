from __future__ import annotations

from typing import Any

import httpx

from .config import WorkerConfig


class CloudError(RuntimeError):
    pass


class CloudClient:
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.client = httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0), follow_redirects=True)

    @property
    def enabled(self) -> bool:
        return bool(self.config.worker_token and self.config.edge_url)

    def _request(self, method: str, action: str, **kwargs: Any) -> dict[str, Any]:
        if not self.enabled:
            raise CloudError("Worker token 尚未設定")
        headers = dict(kwargs.pop("headers", {}))
        headers["x-worker-token"] = self.config.worker_token
        response = self.client.request(method, f"{self.config.edge_url.rstrip('/')}/{action}", headers=headers, **kwargs)
        if response.status_code >= 400:
            raise CloudError(f"Cloud API {response.status_code}: {response.text[:1000]}")
        return response.json()

    def health(self) -> dict[str, Any]:
        response = self.client.get(f"{self.config.edge_url.rstrip('/')}/health")
        response.raise_for_status()
        return response.json()

    def register(self, worker_id: str, capabilities: dict[str, Any], version: str) -> dict[str, Any]:
        return self._request("POST", "register", json={"worker_id": worker_id, "name": self.config.worker_name,
            "capabilities": capabilities, "version": version})

    def heartbeat(self, worker_id: str, status: str, current_job_id: str | None, capabilities: dict[str, Any], version: str) -> dict[str, Any]:
        return self._request("POST", "heartbeat", json={"worker_id": worker_id, "status": status,
            "current_job_id": current_job_id, "capabilities": capabilities, "version": version})

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        return self._request("POST", "claim", json={"worker_id": worker_id}).get("job")

    def next_part(self, job_id: str) -> dict[str, Any] | None:
        return self._request("GET", "next-part", params={"job_id": job_id}).get("part")

    def consume_part(self, job_id: str, part_number: int) -> None:
        self._request("POST", "consume-part", json={"job_id": job_id, "part_number": part_number})

    def progress(self, worker_id: str, job_id: str, **values: Any) -> dict[str, Any]:
        payload = {"worker_id": worker_id, "job_id": job_id, **values}
        return self._request("POST", "progress", json=payload).get("job", {})

    def segment(self, job_id: str, **values: Any) -> None:
        self._request("POST", "segment", json={"job_id": job_id, **values})

    def complete_local(self, worker_id: str, job_id: str, **values: Any) -> dict[str, Any]:
        return self._request("POST", "complete-local", json={"worker_id": worker_id, "job_id": job_id, **values}).get("job", {})

    def fail(self, worker_id: str, job_id: str, error: str, failure_code: str = "WORKER_FAILURE", cancelled: bool = False) -> None:
        self._request("POST", "fail", json={"worker_id": worker_id, "job_id": job_id, "error": error,
            "failure_code": failure_code, "cancelled": cancelled})
