param([string]$Out = "runs/reproduction")
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$ProjetDupire = Split-Path -Parent $PSScriptRoot
Push-Location $ProjetDupire
try {
    $PythonDupire = Join-Path $ProjetDupire ".venv312\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $PythonDupire)) {
        & py -3.12 -m venv .venv312
        if ($LASTEXITCODE -ne 0) { throw "Creation de .venv312 impossible." }
    }
    & $PythonDupire -c "import sys; assert sys.version_info[:2] == (3, 12), 'Python 3.12 requis'"
    if ($LASTEXITCODE -ne 0) { throw "Version Python incorrecte." }
    & $PythonDupire -m pip install -r requirements-lock.txt
    if ($LASTEXITCODE -ne 0) { throw "Installation des dependances interrompue." }
    & $PythonDupire -m pip install --no-build-isolation --no-deps -e .
    if ($LASTEXITCODE -ne 0) { throw "Installation du moteur interrompue." }
    & $PythonDupire scripts/download_data.py frozen
    if ($LASTEXITCODE -ne 0) { throw "Donnees figees non verifiees." }
    & $PythonDupire scripts/reproduce.py --profile core --out $Out
    if ($LASTEXITCODE -ne 0) { throw "Reproduction interrompue. Consulter les journaux." }
}
finally { Pop-Location }
