$ErrorActionPreference = "Stop"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "請先安裝 Python 3.11 以上版本" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Warning "找不到 FFmpeg。請先執行 winget install Gyan.FFmpeg" }
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .
Write-Host "安裝完成。執行 .\configure.ps1 後再執行 .\run.ps1"
