# EASY CODER - budowa dla Windows (plik celowo w ASCII: PowerShell 5.1 nie czyta UTF-8 bez BOM).
#   powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 [-FfmpegDir C:\ffmpeg\bin] [-Python python]
# Wynik:
#   dist\EasyCoder-win\EasyCoder.exe + bin\ffmpeg.exe, bin\ffprobe.exe
#   dist\EasyCoder-win-x64.zip
#   dist\EasyCoder-Setup.exe   (jesli zainstalowany jest Inno Setup - iscc.exe)
param(
    [string]$FfmpegDir = "",
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Version = & $Python -c "import easycoder; print(easycoder.__version__)"
Write-Host "== EASY CODER $Version (Windows) =="

# 1. FFmpeg do bin\
New-Item -ItemType Directory -Force bin | Out-Null
if ($FfmpegDir) {
    Copy-Item (Join-Path $FfmpegDir "ffmpeg.exe"), (Join-Path $FfmpegDir "ffprobe.exe") bin -Force
} elseif (-not (Test-Path bin\ffmpeg.exe)) {
    & $Python scripts\fetch_ffmpeg.py
    if ($LASTEXITCODE -ne 0) { throw "FFmpeg download failed" }
}

# 2. Ikony (jesli brak)
if (-not (Test-Path assets\icon.ico)) { & $Python scripts\make_icons.py }

# 3. Testy
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }

# 4. PyInstaller -> dist\EasyCoder.exe (jeden plik)
& $Python -m PyInstaller EasyCoder.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# 5. Uklad dystrybucji: EasyCoder.exe + bin\
$Out = "dist\EasyCoder-win"
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force "$Out\bin" | Out-Null
Move-Item dist\EasyCoder.exe "$Out\EasyCoder.exe" -Force
Copy-Item bin\ffmpeg.exe, bin\ffprobe.exe "$Out\bin" -Force
Compress-Archive -Path "$Out\*" -DestinationPath "dist\EasyCoder-win-x64.zip" -Force
Write-Host "OK: $Out\EasyCoder.exe and dist\EasyCoder-win-x64.zip"

# 6. Instalator (opcjonalnie)
$Iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $Iscc) {
    foreach ($p in "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") {
        if (Test-Path $p) { $Iscc = $p }
    }
}
if ($Iscc) {
    & $Iscc "/DAppVersion=$Version" installer\EasyCoder.iss
    Write-Host "Installer: dist\EasyCoder-Setup.exe"
} else {
    Write-Host "Inno Setup not found - skipping installer (https://jrsoftware.org/isinfo.php)."
}
