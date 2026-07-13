$ErrorActionPreference = "Stop"
Write-Host "Restoration Studio Worker installer" -ForegroundColor Cyan

$Repo = "https://github.com/PAQ6809/test-wsl/archive/refs/heads/main.zip"
$Root = Join-Path $HOME "RestorationStudioWorker"
$Zip = Join-Path $env:TEMP "restoration-studio-worker.zip"
$Extract = Join-Path $env:TEMP "restoration-studio-worker-source"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "請先安裝 Python 3.11+" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host "找不到 FFmpeg。可先執行：winget install Gyan.FFmpeg" -ForegroundColor Yellow
  throw "安裝 FFmpeg 後重新執行此腳本"
}

Remove-Item $Extract -Recurse -Force -ErrorAction SilentlyContinue
Invoke-WebRequest $Repo -OutFile $Zip
Expand-Archive $Zip -DestinationPath $Extract -Force
$Source = Get-ChildItem $Extract -Directory | Select-Object -First 1
if (-not $Source) { throw "無法解壓縮Worker原始碼" }
Remove-Item $Root -Recurse -Force -ErrorAction SilentlyContinue
New-Item $Root -ItemType Directory | Out-Null
Copy-Item (Join-Path $Source.FullName "worker\*") $Root -Recurse -Force
Set-Location $Root
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host "安裝完成：$Root" -ForegroundColor Green
Write-Host "請編輯 $Root\.env，填入網站產生的 WORKER_TOKEN。" -ForegroundColor Yellow
Write-Host "啟動：$Root\.venv\Scripts\python.exe $Root\run.py" -ForegroundColor Cyan
