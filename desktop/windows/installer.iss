#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef SourceRoot
  #error SourceRoot is required
#endif
#ifndef BundleDir
  #error BundleDir is required
#endif
#ifndef ReleaseDir
  #error ReleaseDir is required
#endif

[Setup]
AppId={{CB390738-D1E4-4BE0-ABCB-36A3B833BE73}
AppName=draft-kit
AppVersion={#AppVersion}
AppPublisher=draft-kit contributors
DefaultDirName={localappdata}\Programs\draft-kit
DefaultGroupName=draft-kit
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#ReleaseDir}
OutputBaseFilename=draft-kit-{#AppVersion}-windows-x64-setup-unsigned-beta
SetupIconFile={#SourceRoot}\build\windows\draft-kit.ico
UninstallDisplayIcon={app}\draft-kit.exe
LicenseFile={#SourceRoot}\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
AppMutex=Local\draft-kit-desktop
CloseApplications=no
RestartApplications=no
Uninstallable=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\draft-kit"; Filename: "{app}\draft-kit.exe"
Name: "{autodesktop}\draft-kit"; Filename: "{app}\draft-kit.exe"; Tasks: desktopicon

[Registry]
; Open at login is opt-in from the tray. Uninstall removes only our Run value.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "draft-kit"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\draft-kit.exe"; Description: "Open draft-kit"; Flags: nowait postinstall skipifsilent
