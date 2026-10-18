#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{D4B7A8E1-92F3-4C19-A832-7195E4F01A96}
AppName=Editor Matemático Accesible
AppVersion={#AppVersion}
AppPublisher=Roddy Agustin Romero Mero
DefaultDirName={autopf}\EditorMatematicoAccesible
DefaultGroupName=Editor Matemático Accesible
OutputBaseFilename=editor-matematico-accesible-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "build\exe.win-amd64-*\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Editor Matemático Accesible"; Filename: "{app}\editor-matematico-accesible.exe"
Name: "{commondesktop}\Editor Matemático Accesible"; Filename: "{app}\editor-matematico-accesible.exe"
