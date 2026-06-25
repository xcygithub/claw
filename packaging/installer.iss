; Inno Setup 脚本: 把 PyInstaller 产物打成 LegalClaw-0.2.0-Setup.exe
; 用法: 用 Inno Setup Compiler 打开本文件并编译, 或:
;   iscc packaging\installer.iss
; 前置: 已执行 pyinstaller packaging/LegalClaw.spec, 产物在 dist\LegalClaw\

#define AppName "LegalClaw"
#define AppVersion "0.2.0"
#define AppPublisher "LegalClaw"
#define AppExeName "LegalClaw.exe"

[Setup]
AppId={{B5E3A2C1-9F4D-4C7A-8E21-LEGALCLAW0200}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename={#AppName}-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"

[Files]
; 打包整个 one-folder 产物
Source: "..\dist\LegalClaw\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent

; --- WebView2 运行时检测 ---
; Win11 内置 WebView2; 部分 Win10 缺失。下面在安装后检测注册表,
; 缺失则提示用户安装 Evergreen Bootstrapper(可改为静默下载安装)。
[Code]
function WebView2Installed(): Boolean;
var
  v: String;
begin
  Result :=
    RegQueryStringValue(HKLM,
      'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
      'pv', v) or
    RegQueryStringValue(HKCU,
      'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
      'pv', v);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not WebView2Installed()) then
  begin
    MsgBox('未检测到 Microsoft Edge WebView2 运行时, LegalClaw 需要它才能显示界面。' + #13#10 +
           '请前往 https://developer.microsoft.com/microsoft-edge/webview2/ 下载安装 Evergreen Bootstrapper。',
           mbInformation, MB_OK);
  end;
end;
