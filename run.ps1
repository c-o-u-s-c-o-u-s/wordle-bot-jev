# One command to install and play (Windows):
#   powershell -ExecutionPolicy Bypass -File run.ps1 [wordle-bot arguments]
# The first run creates .venv and installs torch, Laya and Selenium; later runs start straight away.
# Exit codes are checked by hand: with $ErrorActionPreference = "Stop", Windows PowerShell 5.1
# turns harmless pip warnings on stderr into fatal errors.
Set-Location $PSScriptRoot
$venvPy = ".venv\Scripts\python.exe"
$marker = ".venv\.installed"

function Find-Python {
    $candidates = @()
    if ($env:PYTHON) { $candidates += , @($env:PYTHON) }
    if (Get-Command py -ErrorAction SilentlyContinue) { $candidates += , @("py", "-3") }
    if (Get-Command python -ErrorAction SilentlyContinue) { $candidates += , @("python") }
    foreach ($c in $candidates) {
        $rest = @($c | Select-Object -Skip 1)
        & $c[0] @rest -c "import sys; sys.exit(sys.version_info < (3, 10))"
        if ($LASTEXITCODE -eq 0) { return , $c }
    }
    return $null
}

if (-not (Test-Path $venvPy)) {
    $py = Find-Python
    if (-not $py) {
        Write-Host "error: Python 3.10 or newer is required: https://www.python.org/downloads/" -ForegroundColor Red
        exit 1
    }
    Write-Host "Creating .venv..."
    $rest = @($py | Select-Object -Skip 1)
    & $py[0] @rest -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

$stale = (-not (Test-Path $marker)) -or ((Get-Item pyproject.toml).LastWriteTime -gt (Get-Item $marker).LastWriteTime)
if ($stale) {
    Write-Host "Installing dependencies (first run only; torch and Laya are large)..."
    & $venvPy -m pip install --quiet --upgrade pip
    if ($LASTEXITCODE -ne 0) { exit 1 }
    & $venvPy -m pip install -e .
    if ($LASTEXITCODE -ne 0) { exit 1 }
    New-Item -ItemType File -Force $marker | Out-Null
}

& $venvPy -m wordle_bot @args
exit $LASTEXITCODE
