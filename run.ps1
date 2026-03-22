$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$TempDir = Join-Path $ProjectRoot ".tmp"

Set-Location $ProjectRoot
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
$env:TEMP = $TempDir
$env:TMP = $TempDir

if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment was not found. Run .\setup.ps1 first."
}

& $VenvPython ".\src\main.py"
