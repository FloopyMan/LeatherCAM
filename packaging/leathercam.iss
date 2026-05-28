; Inno Setup script for LeatherCAM (Windows).
;
; Prerequisites:
;   1. Run PyInstaller first:    python -m PyInstaller packaging\leathercam.spec
;   2. Install Inno Setup 6:     https://jrsoftware.org/isdl.php
;   3. Compile this script:      iscc packaging\leathercam.iss
;
; Output: packaging\dist\LeatherCAM-Setup-x86_64.exe

#define MyAppName "LeatherCAM"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "leathercam"
#define MyAppExeName "leathercam.exe"

[Setup]
AppId={{B6D62C8E-4E58-4C7E-AC1F-7E0B6E1A12F3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist
OutputBaseFilename=LeatherCAM-Setup-x86_64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать иконку на рабочем столе"; GroupDescription: "Дополнительно:"

[Files]
Source: "..\dist\leathercam\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent
