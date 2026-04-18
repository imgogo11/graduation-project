$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "common.ps1")

Ensure-ProjectEnvironmentFiles
Import-ProjectEnvironment

$pythonExePath = Resolve-ProjectPath ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExePath)) {
    Invoke-InProjectRoot {
        uv venv .venv --python 3.13
    }
}

Invoke-InProjectRoot {
    uv sync
}

$pythonExe = Get-VenvExecutable -RelativePath ".venv\Scripts\python.exe" -DisplayName "Python virtual environment"
$pybind11CMakeDir = Invoke-InProjectRoot {
    & $pythonExe -m pybind11 --cmakedir
}
$pybind11CMakeDir = "$pybind11CMakeDir".Trim()

$webDirectory = Resolve-ProjectPath "web"
Push-Location $webDirectory
try {
    npm install
}
finally {
    Pop-Location
}

Invoke-InProjectRoot {
    cmake -S algo-module -B algo-module/build "-DPython_EXECUTABLE=$pythonExe" "-Dpybind11_DIR=$pybind11CMakeDir"
}

Invoke-InProjectRoot {
    cmake --build algo-module/build
}

Start-PostgresContainer

Invoke-InProjectRoot {
    & $pythonExe -m alembic -c backend/alembic.ini upgrade head
}

Invoke-InProjectRoot {
    & $pythonExe backend/scripts/init_admin.py
}

Invoke-InProjectRoot {
    & $pythonExe backend/scripts/import_data.py
}

$frontendHost = Get-EnvValue -Name "VITE_DEV_HOST" -Default "127.0.0.1"
$frontendPort = Get-IntEnvValue -Name "VITE_DEV_PORT" -Default 4173

Write-Host ""
Write-Host "Initial setup completed."
Write-Host "Use these commands for daily startup:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\dev\demo-start.ps1 backend"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\dev\demo-start.ps1 frontend"
Write-Host "Open http://$frontendHost`:$frontendPort/ after both services are running."
