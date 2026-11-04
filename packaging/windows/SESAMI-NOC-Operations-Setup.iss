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

function ReadBootstrapResultValue(const Content, Name: AnsiString): AnsiString;
var
  StartPosition: Integer;
  EndPosition: Integer;
  Prefix: String;
begin
  Result := '';
  Prefix := Name + '=';
  StartPosition := Pos(Prefix, Content);
  if StartPosition = 0 then
    Exit;
  StartPosition := StartPosition + Length(Prefix);
  EndPosition := Pos(#13#10, Copy(Content, StartPosition, MaxInt));
  if EndPosition = 0 then
    Result := Copy(Content, StartPosition, MaxInt)
  else
    Result := Copy(Content, StartPosition, EndPosition - 1);
end;

procedure FailBootstrap(const Detail: String);
begin
  MsgBox(
      'SESAMI NOC Operations bootstrap failed before application setup. ' +
      Detail + ' No application runtime or shortcut was created.',
      mbError, MB_OK);
  RaiseException('Bootstrap failed.');
end;

procedure RunBootstrap;
var
  ResultCode: Integer;
  Parameters: String;
  PowerShell: String;
  ResultFile: String;
  ResultContent: AnsiString;
  Action: AnsiString;
  Command: AnsiString;
  Reason: AnsiString;
  Category: AnsiString;
  Stage: AnsiString;
begin
  ResultFile := ExpandConstant('{tmp}\sesami-bootstrap-prerequisite-result.txt');
  DeleteFile(ResultFile);
  Parameters := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ' +
      AddQuotes(ExpandConstant('{app}\scripts\windows\bootstrap-install.ps1')) +
      ' ' + BootstrapParameters('') + ' -PrerequisiteResultPath ' + AddQuotes(ResultFile);
  PowerShell := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  if not Exec(PowerShell, Parameters, '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then
    FailBootstrap('The bootstrap process could not start.');
  if ResultCode = 0 then
    Exit;

  ResultContent := '';
  if LoadStringFromFile(ResultFile, ResultContent) then
  begin
    Action := ReadBootstrapResultValue(ResultContent, 'ACTION');
    Command := ReadBootstrapResultValue(ResultContent, 'COMMAND');
    Reason := ReadBootstrapResultValue(ResultContent, 'REASON');
    Category := ReadBootstrapResultValue(ResultContent, 'CATEGORY');
    Stage := ReadBootstrapResultValue(ResultContent, 'STAGE');
    if (Action = 'GITHUB_CLI') and (Command <> '') then
    begin
      if MsgBox(
          'GitHub CLI attestation support is required before trusted release acquisition. ' +
          'The following approved action will run in WSL:'#13#10#13#10 + Command + #13#10#13#10 +
          'It configures the official GitHub CLI package source, then runs apt-get update and apt-get install --yes gh.',
          mbConfirmation, MB_YESNO) <> IDYES then
        FailBootstrap('GitHub CLI setup was declined (RUNTIME_SETUP_REQUIRED).');
      DeleteFile(ResultFile);
      if not Exec(PowerShell, Parameters + ' -GitHubCliApproved', '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then
        FailBootstrap('The approved GitHub CLI action could not start.');
      if ResultCode = 0 then
        Exit;
      ResultContent := '';
      LoadStringFromFile(ResultFile, ResultContent);
      Reason := ReadBootstrapResultValue(ResultContent, 'REASON');
      if Reason = 'attestation-unavailable' then
        FailBootstrap('GitHub CLI was provisioned but gh attestation verify remains unavailable. Verify WSL setup and rerun.');
      FailBootstrap('The approved GitHub CLI action failed. Verify WSL network access and sudo authorization, then rerun.');
    end;
    if (Category <> '') and (Stage <> '') then
      FailBootstrap('Bootstrap failed during stage ' + Stage + ' (' + Category + '). Review the prerequisite guidance and rerun setup.');
    if Category <> '' then
      FailBootstrap('Bootstrap failed (' + Category + '). Review the prerequisite guidance and rerun setup.');
  end;
  FailBootstrap('Review the prerequisite guidance and rerun setup.');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RunBootstrap;
end;
