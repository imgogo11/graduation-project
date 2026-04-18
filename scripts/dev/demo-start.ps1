param(
    [Parameter(Position = 0)]
    [ValidateSet("backend", "frontend")]
    [string]$Target = "backend"
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "common.ps1")

Ensure-ProjectEnvironmentFiles
Import-ProjectEnvironment

switch ($Target) {
    "backend" {
        $uvicornExe = Get-VenvExecutable -RelativePath ".venv\Scripts\uvicorn.exe" -DisplayName "uvicorn"
        $backendHost = Get-EnvValue -Name "BACKEND_HOST" -Default "127.0.0.1"
        $backendPort = Get-IntEnvValue -Name "BACKEND_PORT" -Default 8200

        Start-PostgresContainer

        Invoke-InProjectRoot {
            & $uvicornExe app.main:app --app-dir backend --host $backendHost --port $backendPort --reload
        }
    }
    "frontend" {
        $webDirectory = Resolve-ProjectPath "web"
        if (-not (Test-Path -LiteralPath (Join-Path $webDirectory "node_modules"))) {
            throw "web\node_modules was not found. Run .\scripts\dev\full-start.ps1 first."
        }

        Push-Location $webDirectory
        try {
            npm run dev
        }
        finally {
            Pop-Location
        }
    }
}
