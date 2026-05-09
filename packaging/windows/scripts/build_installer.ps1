$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot/../../.."

$innoCandidates = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)
$inno = $innoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $inno) { throw "Inno Setup ISCC.exe not found" }

& $inno "packaging/windows/installer/AmpAI.iss"
