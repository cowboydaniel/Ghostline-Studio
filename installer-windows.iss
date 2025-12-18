; Inno Setup Script for Ghostline Studio
; This creates a Windows installer that installs the program to Program Files
; and creates Start Menu shortcuts

#define MyAppName "Ghostline Studio"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Cowboy Daniel"
#define MyAppURL "https://github.com/cowboydaniel/Ghostline-Studio"
#define MyAppExeName "ghostline-studio.exe"

[Setup]
; Application information
AppId={{7B8F9A2C-3D4E-4F5A-8B6C-1E2F3A4B5C6D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; LicenseFile=LICENSE
OutputDir=dist
OutputBaseFilename=ghostline-studio-setup-{#MyAppVersion}-windows-x86_64
; SetupIconFile=ghostline\resources\icons\app-icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; The main executable
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Documentation
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
; Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu shortcuts
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; Desktop shortcut (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Quick Launch shortcut (optional, for older Windows)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; Option to launch the application after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up user configuration on uninstall (optional)
Type: filesandordirs; Name: "{userappdata}\ghostline"
