param(
    [switch]$ForceRecreateVenv
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonHome = Join-Path $ProjectRoot ".python312"
$PythonExe = Join-Path $PythonHome "python.exe"
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$TempDir = Join-Path $ProjectRoot ".tmp"

Set-Location $ProjectRoot
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
$env:TEMP = $TempDir
$env:TMP = $TempDir

if (-not (Test-Path $PythonExe)) {
    throw "Local Python was not found: $PythonExe. Ensure .python312 exists first."
}

if ($ForceRecreateVenv -and (Test-Path $VenvDir)) {
    Remove-Item $VenvDir -Recurse -Force
}

if (-not (Test-Path $VenvPython)) {
    & $PythonExe -m venv $VenvDir
}

$MissingOutput = & $VenvPython -c "import importlib.util; modules={'loguru':'loguru','numpy':'numpy','cv2':'opencv-python-headless','PIL':'pillow','yaml':'pyyaml'}; missing=[pkg for mod,pkg in modules.items() if importlib.util.find_spec(mod) is None]; print(' '.join(missing))"
$MissingPackages = @()
if ($MissingOutput) {
    $MissingPackages = $MissingOutput.Trim().Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)
}

if ($MissingPackages.Count -gt 0) {
    & $VenvPython -m pip install --disable-pip-version-check @MissingPackages
}

Write-Host ""
Write-Host "Environment is ready."
Write-Host "Python: $VenvPython"
Write-Host "Run command: .\run.ps1"
