[Setup]
AppName=Bang Dieu Khien Audio
AppVersion=1.0
DefaultDirName={autopf}\BangDieuKhienAudio
DefaultGroupName=BangDieuKhienAudio
UninstallDisplayIcon={app}\BangDieuKhienAudio.exe
Compression=lzma2
SolidCompression=yes
OutputDir=.
OutputBaseFilename=BangDieuKhienAudio_Setup

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Update the source path to match your latest build folder in dist\
Source: "dist\BangDieuKhienAudio_v*\**"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Bang Dieu Khien Audio"; Filename: "{app}\BangDieuKhienAudio_v*.exe"
Name: "{commondesktop}\Bang Dieu Khien Audio"; Filename: "{app}\BangDieuKhienAudio_v*.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BangDieuKhienAudio_v*.exe"; Description: "{cm:LaunchProgram,Bang Dieu Khien Audio}"; Flags: nowait postinstall skipifsilent
