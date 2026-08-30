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

# `python -m venv` does not copy the Tcl/Tk data directory on Windows, so tkinter
# cannot start inside the venv. PyInstaller then only warns ("tkinter installation
# is broken") and drops tkinter, producing an EXE that dies with
# "No module named 'tkinter'". Point Tcl/Tk at the base installation first.
if (-not $env:TCL_LIBRARY) {
    $BasePrefix = (& $Python -c "import sys; print(sys.base_prefix)").Trim()
    $TclRoot = Join-Path $BasePrefix "tcl"
    if (Test-Path $TclRoot) {
        $TclDir = Get-ChildItem -Path $TclRoot -Directory | Where-Object { $_.Name -match '^tcl\d+\.\d+$' } | Select-Object -First 1
        $TkDir = Get-ChildItem -Path $TclRoot -Directory | Where-Object { $_.Name -match '^tk\d+\.\d+$' } | Select-Object -First 1
        if ($TclDir -and $TkDir) {
            $env:TCL_LIBRARY = $TclDir.FullName
            $env:TK_LIBRARY = $TkDir.FullName
            Write-Host "Using Tcl/Tk from $($TclDir.FullName)"
        }
    }
}

cmd /c "`"$Python`" -c `"import tkinter; tkinter.Tk().destroy()`" >nul 2>nul"
if ($LASTEXITCODE -ne 0) {
    throw "tkinter cannot start under $Python. PyInstaller would silently build an EXE without tkinter. Copy the 'tcl' folder from the base Python into .venv, or set TCL_LIBRARY/TK_LIBRARY, then retry."
}

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
    "--hidden-import", "fh6_vinyl_resources",
    "--hidden-import", "fh6_typecode_probe",
    "--hidden-import", "fh6_typecode_export",
    "--hidden-import", "fh6_typecode_import",
    "--hidden-import", "fh6_typecode_trim",
    "--hidden-import", "preprocess.luma"
)

$appArgs = $common + @(
    "--windowed",
    "--name", "forza-painter-fh6",
    "--add-data", "$(Join-Path $Root 'config');config",
    "--add-data", "$(Join-Path $Root 'bin');bin",
    "--add-data", "$(Join-Path $Root 'assets');assets",
    "--add-data", "$(Join-Path $Root 'docs');docs",
    "--add-data", "$(Join-Path $Root 'src\data');data",
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
