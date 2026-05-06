#define MyAppName "AmpAI"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "AmpAI"
#define MyAppExeName "AmpAI Desktop.exe"

[Setup]
AppId={{A8F0E71D-0A4F-4A35-9A4B-AMP-AI-DESKTOP}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\AmpAI
DefaultGroupName=AmpAI
OutputDir=dist\windows
OutputBaseFilename=AmpAI-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "startup"; Description: "Run AmpAI on Windows startup"; GroupDescription: "Additional options:"

[Files]
Source: "dist\windows\stage\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AmpAI"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\AmpAI"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch AmpAI"; Flags: nowait postinstall skipifsilent


[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AmpAI"; ValueData: ""{app}\{#MyAppExeName}""; Tasks: startup

[UninstallDelete]
; Keep user data by default under %APPDATA%\AmpAI (not deleted)
Type: filesandordirs; Name: "{app}"
