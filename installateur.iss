; Installateur Windows de MecaStruct RdM (Inno Setup 6). Lancé par construire_bureau.py :
;   iscc /DVersion=1.0.0 /DRacine=<dossier du dépôt> installateur.iss
; Installation pour l'utilisateur seul (aucun droit d'administrateur), icône du Bureau, menu Démarrer, désinstallation.

#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Racine
  #define Racine "."
#endif

[Setup]
AppId={{6F1E2B4A-3C5D-4E7F-9A1B-2C3D4E5F6A7B}
AppName=MecaStruct RdM
AppVersion={#Version}
AppVerName=MecaStruct RdM {#Version}
AppPublisher=Théo Brun
AppPublisherURL=https://github.com/theo33-oss/MecaStruct
AppSupportURL=https://github.com/theo33-oss/MecaStruct/issues
AppUpdatesURL=https://github.com/theo33-oss/MecaStruct/releases
DefaultDirName={localappdata}\Programs\MecaStruct
DefaultGroupName=MecaStruct RdM
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#Racine}\dist
OutputBaseFilename=MecaStruct_Installation_{#Version}
SetupIconFile={#Racine}\build\icone.ico
UninstallDisplayIcon={app}\MecaStruct.exe
LicenseFile={#Racine}\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "bureau"; Description: "Créer une icône sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "{#Racine}\dist\MecaStruct\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MecaStruct RdM"; Filename: "{app}\MecaStruct.exe"
Name: "{group}\Limites connues"; Filename: "{app}\LIMITES.md"
Name: "{group}\Désinstaller MecaStruct RdM"; Filename: "{uninstallexe}"
Name: "{userdesktop}\MecaStruct RdM"; Filename: "{app}\MecaStruct.exe"; Tasks: bureau

[Run]
Filename: "{app}\MecaStruct.exe"; Description: "Ouvrir MecaStruct RdM"; Flags: nowait postinstall skipifsilent
