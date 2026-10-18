$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$python = Join-Path $project '.venv\Scripts\python.exe'
$nsis = Join-Path $project 'nsis\makensis.exe'

foreach ($required in @($python, $nsis, (Join-Path $project 'bin\node.exe'), (Join-Path $project 'bin\ffmpeg.exe'))) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing build dependency: $required" }
}

Push-Location $project
try {
    & $python -m PyInstaller --noconfirm --clean --log-level ERROR --onedir --windowed `
        --name Qingying `
        --icon 'assets\icon.ico' `
        --distpath 'dist' `
        --workpath 'build-cache' `
        --specpath '.' `
        --collect-all yt_dlp `
        --collect-all yt_dlp_ejs `
        --add-binary 'bin\node.exe;bin' `
        --add-binary 'bin\ffmpeg.exe;bin' `
        --add-data 'assets\NotoSansSC.ttf;assets' `
        --add-data 'assets\OFL.txt;assets' `
        --add-data 'assets\icon.ico;assets' `
        'src\main.py'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    # PyInstaller may pick up an ICU build whose exports conflict with Windows Qt.
    # Windows 10/11 supplies the compatible unversioned ICU DLLs.
    foreach ($relative in @('icuuc.dll', 'icudt78.dll', 'PySide6\icuuc.dll', 'PySide6\icudt78.dll')) {
        $bundledIcu = Join-Path $project (Join-Path 'dist\Qingying\_internal' $relative)
        if (Test-Path -LiteralPath $bundledIcu) { Remove-Item -LiteralPath $bundledIcu -Force }
    }
    & $nsis /V2 /INPUTCHARSET UTF8 'installer.nsi'
    if ($LASTEXITCODE -ne 0) { throw 'NSIS installer build failed.' }
}
finally {
    Pop-Location
}
