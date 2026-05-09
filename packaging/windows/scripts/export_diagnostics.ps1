param(
  [string]$AppDataRoot = "$env:APPDATA\\AmpAI",
  [string]$OutputDir = "$env:USERPROFILE\\Desktop"
)

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bundleRoot = Join-Path $OutputDir "ampai-diagnostics-$timestamp"
New-Item -ItemType Directory -Force -Path $bundleRoot | Out-Null

$logsDir = Join-Path $AppDataRoot "logs"
if (Test-Path $logsDir) {
  Copy-Item -Recurse -Force $logsDir (Join-Path $bundleRoot "logs")
}

$meta = @{
  generated_at = (Get-Date).ToString("o")
  appdata_root = $AppDataRoot
  machine = $env:COMPUTERNAME
  user = $env:USERNAME
}
$meta | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $bundleRoot "metadata.json") -Encoding UTF8

$zipPath = "$bundleRoot.zip"
Compress-Archive -Path "$bundleRoot/*" -DestinationPath $zipPath -Force
Write-Host "Diagnostics exported: $zipPath"
