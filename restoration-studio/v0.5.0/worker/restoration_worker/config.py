from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_EDGE_URL = "https://goedzzhhvvnfczgnkqlv.supabase.co/functions/v1/restoration-worker-api"
DEFAULT_SITE = "https://restoration-studio-cloud.vercel.app"


def default_root() -> Path:
    override = os.getenv("RESTORATION_WORKER_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".restoration-studio"


@dataclass
class WorkerConfig:
    worker_token: str = ""
    pairing_secret: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    worker_name: str = "Personal Worker"
    edge_url: str = DEFAULT_EDGE_URL
    bind_host: str = "127.0.0.1"
    bind_port: int = 8787
    segment_seconds: int = 300
    segment_retries: int = 3
    ffmpeg_preset: str = "medium"
    max_upload_bytes: int = 100 * 1024**3
    min_free_disk_bytes: int = 5 * 1024**3
    poll_seconds: float = 3.0
    allowed_origins: list[str] = field(default_factory=lambda: [
        DEFAULT_SITE,
        "https://restoration-studio-cloud-pinranchen6809-9565s-projects.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])
    external_commands: dict[str, str] = field(default_factory=dict)

    @property
    def home(self) -> Path:
        return default_root()

    @property
    def jobs_dir(self) -> Path:
        return self.home / "jobs"

    @property
    def config_path(self) -> Path:
        return self.home / "config.json"

    def save(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        tmp = self.config_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.config_path)


def load_config() -> WorkerConfig:
    path = default_root() / "config.json"
    if not path.exists():
        cfg = WorkerConfig()
        cfg.save()
        return cfg
    raw = json.loads(path.read_text(encoding="utf-8"))
    allowed = {field.name for field in WorkerConfig.__dataclass_fields__.values()}
    cfg = WorkerConfig(**{k: v for k, v in raw.items() if k in allowed})
    if not cfg.pairing_secret:
        cfg.pairing_secret = secrets.token_urlsafe(32)
    cfg.save()
    return cfg
