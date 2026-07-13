#!/usr/bin/env bash
set -euo pipefail
ROOT="${HOME}/RestorationStudioWorker"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
command -v python3 >/dev/null || { echo '需要 Python 3.11+'; exit 1; }
command -v ffmpeg >/dev/null || { echo '需要 FFmpeg / FFprobe'; exit 1; }
curl -fsSL https://github.com/PAQ6809/test-wsl/archive/refs/heads/main.tar.gz | tar -xz -C "$TMP"
rm -rf "$ROOT"
mkdir -p "$ROOT"
cp -R "$TMP"/*/worker/. "$ROOT"/
cd "$ROOT"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
echo "安裝完成：$ROOT"
echo "請編輯 $ROOT/.env，填入網站產生的 WORKER_TOKEN。"
echo "啟動：$ROOT/.venv/bin/python $ROOT/run.py"
