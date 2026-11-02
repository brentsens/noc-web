#define AppName "SESAMI NOC Operations"
#define AppVersion "1.0.0"
[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
OutputBaseFilename=SESAMI-NOC-Operations-Setup
DefaultDirName={localappdata}\SESAMI NOC Operations
PrivilegesRequired=lowest
SetupIconFile=sesami-noc-operations.ico
OutputDir=..\..\dist\windows
DisableProgramGroupPage=yes
Uninstallable=no

[Files]
Source: "..\..\scripts\windows\bootstrap-install.ps1"; DestDir: "{app}\scripts\windows"
Source: "..\..\scripts\bootstrap\*.py"; DestDir: "{app}\scripts\bootstrap"
Source: "bootstrap-manifest.json"; DestDir: "{app}"
Source: "sesami-noc-operations.ico"; DestDir: "{app}"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{app}\scripts\windows\bootstrap-install.ps1"" {code:BootstrapParameters}"; Flags: waituntilterminated

[Code]
function BootstrapParameters(Param: String): String;
var
  Manifest: String;
begin
  Manifest := ExpandConstant('{app}\bootstrap-manifest.json');
  Result := '-Distribution Ubuntu -BootstrapManifest ' + AddQuotes(Manifest);

  if MsgBox(
      'Install or repair the verified NOC Web release in your WSL environment?',
      mbConfirmation, MB_YESNO) = IDYES then
  begin
    Result := Result + ' -ConfirmReplacement';
    if MsgBox(
        'Install the optional verified noc-tools release? You can choose this later.',
        mbConfirmation, MB_YESNO) = IDYES then
      Result := Result + ' -ConfirmNocTools';
  end;
end;
