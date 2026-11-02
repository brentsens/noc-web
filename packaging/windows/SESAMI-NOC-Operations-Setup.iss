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
Source: "..\..\scripts\bootstrap\check_runtime_prerequisites.sh"; DestDir: "{app}\scripts\bootstrap"
Source: "..\..\scripts\bootstrap\provision_github_cli.sh"; DestDir: "{app}\scripts\bootstrap"
Source: "bootstrap-manifest.json"; DestDir: "{app}"
Source: "sesami-noc-operations.ico"; DestDir: "{app}"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{app}\scripts\windows\bootstrap-install.ps1"" {code:BootstrapParameters}"; Flags: waituntilterminated

[Code]
var
  DistributionPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  DistributionPage := CreateInputQueryPage(
      wpWelcome,
      'WSL distribution',
      'Select the WSL distribution to use',
      'Ubuntu supports automatic prerequisite provisioning. Other WSL2 distributions may continue when they meet the runtime capability checks.');
  DistributionPage.Add('WSL distribution:', False);
  DistributionPage.Values[0] := 'Ubuntu';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = DistributionPage.ID) and (Trim(DistributionPage.Values[0]) = '') then
  begin
    MsgBox('Enter the WSL distribution to use.', mbError, MB_OK);
    Result := False;
  end;
end;

function BootstrapParameters(Param: String): String;
var
  Manifest: String;
  Distribution: String;
begin
  Manifest := ExpandConstant('{app}\bootstrap-manifest.json');
  Distribution := DistributionPage.Values[0];
  Result := '-Distribution ' + AddQuotes(Distribution) + ' -BootstrapManifest ' + AddQuotes(Manifest);

  if MsgBox(
      'If missing, install only the approved Ubuntu runtime prerequisites ' +
      '(python3, python3-venv, and ca-certificates) with sudo apt-get? ' +
      'The installer will show the exact missing-package command before it runs.',
      mbConfirmation, MB_YESNO) = IDYES then
    Result := Result + ' -ConfirmPrerequisites';

  if MsgBox(
      'If needed, install or update GitHub CLI from GitHub''s official Ubuntu package source? ' +
      'The installer will show the exact action before it runs.',
      mbConfirmation, MB_YESNO) = IDYES then
    Result := Result + ' -ConfirmGitHubCli';

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
