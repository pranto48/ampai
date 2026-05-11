# AmpAI Update System

## Current Windows App Update Flow

The desktop app includes a GitHub update check for:

`https://github.com/pranto48/ampai`

It checks the latest GitHub release first. If the repo has no release, it shows the latest `main` commit. This is a safe notification flow, not an automatic installer.

## Recommended Release Flow

1. Build the Windows app:

   ```powershell
   cd D:\ampai\desktop
   npm run tauri:build
   ```

2. Upload these files to a GitHub Release:

   - `desktop\src-tauri\target\release\bundle\nsis\AmpAI_0.1.1_x64-setup.exe`
   - `desktop\src-tauri\target\release\bundle\msi\AmpAI_0.1.1_x64_en-US.msi`

3. Users install the latest setup file from the release.

## Server Update From GitHub

Use the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File D:\ampai\scripts\update-ampai-from-github.ps1
```

To rebuild the desktop app after pulling the GitHub repo:

```powershell
powershell -ExecutionPolicy Bypass -File D:\ampai\scripts\update-ampai-from-github.ps1 -BuildDesktop
```

## Full Auto-Update Option

Tauri supports signed automatic updates, but it needs a signing private key and a release endpoint that publishes signed metadata. The correct production path is:

- Enable Tauri updater plugin.
- Generate updater signing keys.
- Keep the private key only on the build machine or CI.
- Publish signed update metadata and installers in GitHub Releases.
- Configure the app to check the GitHub release metadata endpoint.
