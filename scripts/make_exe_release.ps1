$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$DistRoot = Join-Path $Root "dist"
$BuildRoot = Join-Path $Root "build\pyinstaller"
$VersionFile = Join-Path $Root "src\version.py"
$VersionMatch = Select-String -Path $VersionFile -Pattern '^__version__\s*=\s*"([^"]+)"' | Select-Object -First 1
if (-not $VersionMatch) {
    throw "Cannot read version from src\version.py"
}

$Version = $VersionMatch.Matches[0].Groups[1].Value
$PackageName = "forza-painter-fh6-v$Version-onefile"
$PackageDir = Join-Path $DistRoot $PackageName
$ZipPath = Join-Path $DistRoot "$PackageName.zip"
$VersionedExePath = Join-Path $DistRoot "forza-painter-fh6-v$Version.exe"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $Python)) {
    throw "Missing .venv Python. Run start_app.bat or install_dependencies.bat first."
}

cmd /c "`"$Python`" -m pip show pyinstaller >nul 2>nul"
if ($LASTEXITCODE -ne 0) {
    & $Python -m pip install pyinstaller
}

& $Python -m pip install -r (Join-Path $Root "requirements.txt")
& $Python -m pip install -r (Join-Path $Root "requirements-preview.txt")

if (Test-Path $BuildRoot) {
    Remove-Item -LiteralPath $BuildRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $BuildRoot | Out-Null

$common = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--paths", (Join-Path $Root "src"),
    "--workpath", $BuildRoot,
    "--specpath", $BuildRoot,
    "--distpath", $BuildRoot,
    "--hidden-import", "win32timezone",
    "--hidden-import", "cv2",
    "--hidden-import", "numpy",
    "--hidden-import", "PIL",
    "--hidden-import", "PIL.Image",
    "--hidden-import", "PIL.ImageDraw",
    "--hidden-import", "preprocess.luma"
)

$appArgs = $common + @(
    "--windowed",
    "--name", "forza-painter-fh6",
    "--add-data", "$(Join-Path $Root 'config');config",
    "--add-data", "$(Join-Path $Root 'bin');bin",
    "--add-data", "$(Join-Path $Root 'assets');assets",
    "--add-data", "$(Join-Path $Root 'docs');docs",
    (Join-Path $Root "src\app.py")
)
& $Python -m PyInstaller @appArgs

if (Test-Path $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir | Out-Null

Copy-Item -LiteralPath (Join-Path $BuildRoot "forza-painter-fh6.exe") -Destination $PackageDir
Copy-Item -LiteralPath (Join-Path $BuildRoot "forza-painter-fh6.exe") -Destination $VersionedExePath

if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath
Write-Host "One-file EXE written to $VersionedExePath"
Write-Host "One-file EXE package written to $ZipPath"
