#define AppName "SESAMI NOC Operations"
#define AppVersion "0.1.0"
[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
OutputBaseFilename=SESAMI-NOC-Operations-Setup
DefaultDirName={autopf}\SESAMI NOC Operations
DisableProgramGroupPage=yes
Uninstallable=no

[Files]
Source: "..\..\scripts\windows\bootstrap-install.ps1"; DestDir: "{app}\scripts\windows"
Source: "..\..\scripts\bootstrap\*"; DestDir: "{app}\scripts\bootstrap"; Flags: recursesubdirs
Source: "bootstrap-manifest.json"; DestDir: "{app}"
Source: "release-public-key.txt"; DestDir: "{app}"; Flags: skipifsourcedoesntexist
Source: "sesami-noc-operations.ico"; DestDir: "{app}"; Flags: skipifsourcedoesntexist

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\windows\bootstrap-install.ps1"" -Distribution Ubuntu -InstallRoot /home/{username}/noc-web -ConfirmReplacement"; Flags: waituntilterminated
