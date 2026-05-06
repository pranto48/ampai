$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot/../../.."

$stage = "dist/windows/stage"
New-Item -ItemType Directory -Force -Path "$stage/runtime" | Out-Null
New-Item -ItemType Directory -Force -Path "$stage/config" | Out-Null

if (Test-Path "packaging/windows/runtime") {
  Copy-Item -Recurse -Force packaging/windows/runtime/* "$stage/runtime/"
}
if (Test-Path "packaging/windows/runtime/.env.desktop") {
  Copy-Item -Force packaging/windows/runtime/.env.desktop "$stage/config/.env"
}
