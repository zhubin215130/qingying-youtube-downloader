Unicode true
!include "MUI2.nsh"

!define APP_NAME "清影"
!define APP_VERSION "1.0.0"

Name "${APP_NAME} YouTube 下载器"
OutFile "dist\Qingying-Setup-1.0.0.exe"
InstallDir "$LOCALAPPDATA\Programs\Qingying"
InstallDirRegKey HKCU "Software\Qingying" "Install_Dir"
RequestExecutionLevel user
SetCompressor zlib
Icon "assets\icon.ico"
UninstallIcon "assets\icon.ico"
BrandingText "清影 YouTube 下载器"
VIProductVersion "1.0.0.0"
VIAddVersionKey /LANG=2052 "ProductName" "清影 YouTube 下载器"
VIAddVersionKey /LANG=2052 "FileDescription" "清影安装程序"
VIAddVersionKey /LANG=2052 "FileVersion" "1.0.0"
VIAddVersionKey /LANG=2052 "LegalCopyright" "Copyright 2026 Qingying contributors"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "安装" SecMain
    SetOutPath "$INSTDIR"
    SetOverwrite on
    File /r "dist\Qingying\*"
    File "USER_GUIDE.txt"
    SetOutPath "$INSTDIR\licenses"
    File /r "licenses\*"
    File "THIRD_PARTY.txt"
    SetOutPath "$INSTDIR"
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    CreateDirectory "$SMPROGRAMS\清影"
    CreateShortcut "$SMPROGRAMS\清影\清影.lnk" "$INSTDIR\Qingying.exe"
    WriteRegStr HKCU "Software\Qingying" "Install_Dir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Qingying" "DisplayName" "清影 YouTube 下载器"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Qingying" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Qingying" "DisplayIcon" "$INSTDIR\Qingying.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Qingying" "DisplayVersion" "${APP_VERSION}"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Qingying" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Qingying" "NoRepair" 1
SectionEnd

Section "Uninstall"
    Delete "$SMPROGRAMS\清影\清影.lnk"
    RMDir "$SMPROGRAMS\清影"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir /r "$INSTDIR"
    DeleteRegKey HKCU "Software\Qingying"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Qingying"
SectionEnd
