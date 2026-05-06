$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot/../../.."

npm ci
npm run build

New-Item -ItemType Directory -Force -Path dist/windows/stage/frontend | Out-Null
if (Test-Path frontend/build) { Copy-Item -Recurse -Force frontend/build/* dist/windows/stage/frontend/ }
if (Test-Path frontend/index.html) { Copy-Item -Force frontend/index.html dist/windows/stage/frontend/ }
if (Test-Path frontend/style.css) { Copy-Item -Force frontend/style.css dist/windows/stage/frontend/ }
