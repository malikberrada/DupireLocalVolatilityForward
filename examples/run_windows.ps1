param(
    [ValidateSet("auto", "cpu", "cuda")][string]$Device = "auto",
    [int]$Threads = 10,
    [string]$Output = ".\runs\demo"
)
$ErrorActionPreference = "Stop"
# Run from the extracted project directory. Keep an already working PyTorch CUDA installation.
python -m pip install --only-binary=:all: .\dist\dupire_joint-0.1.1-py3-none-any.whl
if ($LASTEXITCODE -ne 0) { throw "pip installation failed" }
python -m dupire_joint doctor --device $Device --out ($Output + "_doctor")
if ($LASTEXITCODE -ne 0) { throw "Environment check failed" }
python -m dupire_joint demo --device $Device --threads $Threads --levels 0,1,2 --relax --out $Output
if ($LASTEXITCODE -ne 0) { throw "Demo failed; inspect status.json" }

