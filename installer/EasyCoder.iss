; Instalator Windows (Inno Setup 6). Budowa: iscc /DAppVersion=1.0.0 installer\EasyCoder.iss
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6E2B7C1A-4C3E-4B8D-9E55-EC0DE5EC0DE5}
AppName=EASY CODER
AppVersion={#AppVersion}
AppPublisher=EASY CODER
DefaultDirName={autopf}\EasyCoder
DefaultGroupName=EASY CODER
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=EasyCoder-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\EasyCoder.exe
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\EasyCoder-win\EasyCoder.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\EasyCoder-win\bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion

[Icons]
Name: "{group}\EASY CODER"; Filename: "{app}\EasyCoder.exe"
Name: "{group}\{cm:UninstallProgram,EASY CODER}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\EASY CODER"; Filename: "{app}\EasyCoder.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\EasyCoder.exe"; Description: "{cm:LaunchProgram,EASY CODER}"; Flags: nowait postinstall skipifsilent
