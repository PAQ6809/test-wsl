# Restoration Studio Personal Worker

The worker performs long-running FFmpeg/OpenCV restoration on the user's own computer. It binds only to `127.0.0.1`, requires a pairing secret for browser-to-worker calls, and uses a revocable worker token for cloud job coordination.

## Windows

```powershell
winget install Gyan.FFmpeg
./install.ps1
./configure.ps1 -WorkerToken "TOKEN_FROM_WEBSITE"
./run.ps1
```

The worker stores checkpoints and outputs under `%USERPROFILE%/.restoration-studio/jobs`.

## Linux / macOS

```bash
./install.sh
.venv/bin/restoration-worker configure --token "TOKEN_FROM_WEBSITE"
./run.sh
```

The public website is https://restoration-studio-cloud.vercel.app . This worker is only for media owned by the user or used with authorization; it is not a forensic de-redaction tool.