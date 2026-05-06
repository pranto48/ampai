param(
  [string]$RepoRoot = (Resolve-Path "$PSScriptRoot/../../..").Path,
  [int]$BackendPort = 18000,
  [int]$PostgresPort = 15432,
  [int]$RedisPort = 16379
)

$ErrorActionPreference = "Stop"

$runtimeDir = Join-Path $RepoRoot "dist/windows/stage/runtime"
$configFile = Join-Path $RepoRoot "dist/windows/stage/config/.env"
$backendExe = Join-Path $RepoRoot "dist/windows/stage/backend/ampai-backend/main.exe"
$redisExe = Join-Path $runtimeDir "redis/redis-server.exe"
$redisConf = Join-Path $runtimeDir "redis/redis.windows.conf"
$pgCtl = Join-Path $runtimeDir "postgres/bin/pg_ctl.exe"
$pgData = Join-Path $runtimeDir "postgres/data"

function Start-Redis {
  if (Get-Process -Name redis-server -ErrorAction SilentlyContinue) { return }
  Start-Process -FilePath $redisExe -ArgumentList $redisConf -WindowStyle Hidden | Out-Null
}

function Start-Postgres {
  $status = & $pgCtl status -D $pgData 2>$null
  if ($LASTEXITCODE -eq 0) { return }
  & $pgCtl start -D $pgData -l (Join-Path $pgData "postgres.log") | Out-Null
}

function Start-Backend {
  if (Get-Process -Name main -ErrorAction SilentlyContinue) { return }
  Start-Process -FilePath $backendExe -WorkingDirectory (Split-Path $backendExe) -WindowStyle Hidden | Out-Null
}

function Wait-Health([string]$url, [int]$seconds = 60) {
  $deadline = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $resp = Invoke-WebRequest -Uri $url -TimeoutSec 3
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) { return $true }
    } catch {}
    Start-Sleep -Milliseconds 700
  }
  return $false
}

Start-Redis
Start-Postgres
$env:PORT = "$BackendPort"
$env:DATABASE_URL = "postgresql+psycopg2://ampai:ampai@127.0.0.1:$PostgresPort/ampai"
$env:REDIS_URL = "redis://127.0.0.1:$RedisPort/0"
if (Test-Path $configFile) {
  Get-Content $configFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $k, $v = $_ -split '=', 2
    [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), 'Process')
  }
}
Start-Backend
if (-not (Wait-Health "http://127.0.0.1:$BackendPort/" 75)) {
  throw "AmpAI backend failed health check on port $BackendPort"
}
Write-Host "AmpAI services started successfully on http://127.0.0.1:$BackendPort"
