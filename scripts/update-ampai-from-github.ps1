param(
    [string]$RepoUrl = "https://github.com/pranto48/ampai.git",
    [string]$Branch = "main",
    [string]$InstallDir = "D:\ampai",
    [switch]$BuildDesktop
)

$ErrorActionPreference = "Stop"

function Run($Command, $WorkingDirectory) {
    Write-Host ">> $Command" -ForegroundColor Cyan
    Push-Location $WorkingDirectory
    try {
        cmd.exe /c $Command
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$parent = Split-Path -Parent $InstallDir
$backupDir = Join-Path $parent "ampai-backup-$stamp"
$stagingDir = Join-Path $parent "ampai-update-$stamp"

Write-Host "Cloning $RepoUrl ($Branch) to $stagingDir"
Run "git clone --branch $Branch --depth 1 $RepoUrl `"$stagingDir`"" $parent

Write-Host "Stopping current Docker stack"
Run "docker compose down" $InstallDir

Write-Host "Backing up current install to $backupDir"
Move-Item -LiteralPath $InstallDir -Destination $backupDir
Move-Item -LiteralPath $stagingDir -Destination $InstallDir

Write-Host "Starting updated Docker stack"
Run "docker compose up -d --build" $InstallDir

if ($BuildDesktop) {
    $desktopDir = Join-Path $InstallDir "desktop"
    if (Test-Path $desktopDir) {
        $vsDevCmd = "C:\Program Files\Microsoft Visual Studio\18\Community\Common7\Tools\VsDevCmd.bat"
        if (-not (Test-Path $vsDevCmd)) {
            throw "Visual Studio 2026 developer prompt not found at $vsDevCmd"
        }
        Run "npm install" $desktopDir
        Run "`"$vsDevCmd`" -arch=amd64 -host_arch=amd64 && npm run tauri:build" $desktopDir
    } else {
        Write-Warning "No desktop folder found in updated repository."
    }
}

Write-Host "Update complete. Backup kept at $backupDir" -ForegroundColor Green
