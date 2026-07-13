from __future__ import annotations
import os
import platform
import shutil
import socket
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    supabase_url: str = os.getenv("SUPABASE_URL", "").rstrip("/")
    publishable_key: str = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    worker_token: str = os.getenv("WORKER_TOKEN", "")
    worker_name: str = os.getenv("WORKER_NAME", f"{socket.gethostname()} Worker")
    data_dir: Path = Path(os.getenv("WORKER_DATA_DIR", "./worker-data")).resolve()
    poll_seconds: float = float(os.getenv("WORKER_POLL_SECONDS", "5"))
    keep_days: int = int(os.getenv("WORKER_KEEP_DAYS", "7"))
    output_part_bytes: int = int(os.getenv("WORKER_OUTPUT_PART_MB", "32")) * 1024 * 1024
    segment_seconds: int = 300

    def validate(self) -> None:
        missing = [name for name, value in {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_PUBLISHABLE_KEY": self.publishable_key,
            "WORKER_TOKEN": self.worker_token,
        }.items() if not value]
        if missing:
            raise RuntimeError("缺少環境變數：" + ", ".join(missing))
        if not self.worker_token.startswith("rst_"):
            raise RuntimeError("WORKER_TOKEN格式錯誤")
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise RuntimeError("找不到FFmpeg／FFprobe，請先安裝並加入PATH")

    @property
    def worker_id(self) -> str:
        raw = f"{socket.gethostname()}-{platform.system()}-{platform.machine()}"
        return "".join(c for c in raw if c.isalnum() or c in "._-")[:100]

settings = Settings()
