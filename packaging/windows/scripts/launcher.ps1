param(
  [string]$RepoRoot = (Resolve-Path "$PSScriptRoot/../../..").Path,
  [int]$BackendPort = 18000,
  [int]$PostgresPort = 15432,
  [int]$RedisPort = 16379,
  [switch]$OpenUi = $true
)

$ErrorActionPreference = "Stop"
$started = @{}

$runtimeDir = Join-Path $RepoRoot "dist/windows/stage/runtime"
$configFile = Join-Path $RepoRoot "dist/windows/stage/config/.env"
$backendExe = Join-Path $RepoRoot "dist/windows/stage/backend/ampai-backend/main.exe"
$redisExe = Join-Path $runtimeDir "redis/redis-server.exe"
$redisConf = Join-Path $runtimeDir "redis/redis.windows.conf"
$pgCtl = Join-Path $runtimeDir "postgres/bin/pg_ctl.exe"
$pgData = Join-Path $runtimeDir "postgres/data"

function Test-PortFree([int]$Port) {
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  return -not $conn
}

function Assert-PortReady([int]$Port, [string]$Name) {
  if (-not (Test-PortFree $Port)) {
    Write-Host "$Name already listening on port $Port (reusing existing service)."
    return
  }
  Write-Host "$Name port $Port is free."
}

function Start-Redis {
  $existing = Get-Process -Name redis-server -ErrorAction SilentlyContinue
  if ($existing) { return }
  $proc = Start-Process -FilePath $redisExe -ArgumentList $redisConf -WindowStyle Hidden -PassThru
  $started["redis"] = $proc.Id
}

function Start-Postgres {
  & $pgCtl status -D $pgData 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { return }
  & $pgCtl start -D $pgData -l (Join-Path $pgData "postgres.log") | Out-Null
  $started["postgres"] = 1
}

function Run-Migrations {
  # Startup migration hook. Replace with alembic/explicit migration command if needed.
  Write-Host "Running DB migrations check..."
  if (Test-Path (Join-Path $RepoRoot "backend/migrations")) {
    Write-Host "Migration directory found: backend/migrations"
  }
}

function Start-Backend {
  $existing = Get-Process -Name main -ErrorAction SilentlyContinue
  if ($existing) { return $existing }
  $proc = Start-Process -FilePath $backendExe -WorkingDirectory (Split-Path $backendExe) -WindowStyle Hidden -PassThru
  $started["backend"] = $proc.Id
  return $proc
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

function Open-Ui([int]$Port) {
  if ($OpenUi) {
    Start-Process "http://127.0.0.1:$Port"
  }
}

function Stop-StartedServices {
  if ($started.ContainsKey("backend")) {
    Stop-Process -Id $started["backend"] -Force -ErrorAction SilentlyContinue
  }
  if ($started.ContainsKey("redis")) {
    Stop-Process -Id $started["redis"] -Force -ErrorAction SilentlyContinue
  }
  if ($started.ContainsKey("postgres")) {
    & $pgCtl stop -D $pgData -m fast | Out-Null
  }
}

try {
  Assert-PortReady -Port $BackendPort -Name "Backend"
  Assert-PortReady -Port $PostgresPort -Name "Postgres"
  Assert-PortReady -Port $RedisPort -Name "Redis"

  Start-Redis
  Start-Postgres

  $env:HOST = "127.0.0.1"
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

  Run-Migrations

  $backendProc = Start-Backend
  if (-not (Wait-Health "http://127.0.0.1:$BackendPort/" 75)) {
    throw "AmpAI backend failed health check on port $BackendPort"
  }

  Open-Ui -Port $BackendPort
  Write-Host "AmpAI services started successfully on http://127.0.0.1:$BackendPort"

  while ($true) {
    Start-Sleep -Seconds 3
    if ($backendProc -and $backendProc.HasExited) {
      Write-Host "Backend crashed. Restarting..."
      $backendProc = Start-Backend
      Start-Sleep -Seconds 2
    }
  }
}
finally {
  Stop-StartedServices
}
