param(
    [string]$CameraUrl = $env:CHESS_CAMERA_URL,
    [int]$Port = 8765
)

$dashboard = Join-Path $PSScriptRoot 'Visual Studio\program\vision_dashboard.py'
$workspaceDeps = Join-Path (Split-Path $PSScriptRoot -Parent) '.deps'
if (Test-Path -LiteralPath $workspaceDeps) {
    $env:PYTHONPATH = if ($env:PYTHONPATH) { "$workspaceDeps;$env:PYTHONPATH" } else { $workspaceDeps }
    $localStockfish = Join-Path $workspaceDeps 'bin\stockfish.exe'
    if (-not $env:STOCKFISH_PATH -and (Test-Path -LiteralPath $localStockfish)) {
        $env:STOCKFISH_PATH = $localStockfish
    }
}

$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pythonExe = if (Test-Path -LiteralPath $bundledPython) { $bundledPython } else { (Get-Command python -ErrorAction Stop).Source }
$arguments = @($dashboard, '--port', $Port)
if ($CameraUrl) { $arguments += @('--camera', $CameraUrl) }

Write-Host "Apri http://127.0.0.1:$Port/ nel browser. Premi Ctrl+C per fermare il feed."
& $pythonExe @arguments
exit $LASTEXITCODE
