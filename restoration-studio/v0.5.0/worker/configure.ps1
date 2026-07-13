param([Parameter(Mandatory=$true)][string]$WorkerToken, [string]$Name="Personal Worker")
$ErrorActionPreference = "Stop"
& .\.venv\Scripts\restoration-worker.exe configure --token $WorkerToken --name $Name
