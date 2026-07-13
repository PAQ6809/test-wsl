#!/usr/bin/env bash
set -euo pipefail
command -v python3 >/dev/null || { echo 'Python 3.11+ is required'; exit 1; }
command -v ffmpeg >/dev/null || echo 'Warning: install ffmpeg before processing media.'
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
echo 'Installed. Run: .venv/bin/restoration-worker configure --token YOUR_TOKEN && .venv/bin/restoration-worker run'
