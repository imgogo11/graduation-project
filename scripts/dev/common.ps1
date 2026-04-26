Set-StrictMode -Version Latest

$script:ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Get-ProjectRoot {
    return $script:ProjectRoot
}

function Resolve-ProjectPath {
    param(
        [Parameter(Mandatory)]
        [string]$RelativePath
    )

    return Join-Path $script:ProjectRoot $RelativePath
}

function Ensure-FileFromTemplate {
    param(
        [Parameter(Mandatory)]
        [string]$TargetPath,
        [Parameter(Mandatory)]
        [string]$TemplatePath
    )

    if (Test-Path -LiteralPath $TargetPath) {
        return
    }

    Copy-Item -LiteralPath $TemplatePath -Destination $TargetPath
    Write-Host "Created $TargetPath from template."
}

function Ensure-ProjectEnvironmentFiles {
    Ensure-FileFromTemplate -TargetPath (Resolve-ProjectPath ".env") -TemplatePath (Resolve-ProjectPath ".env.template")
}

function Import-DotEnvFile {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [switch]$Override
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding utf8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }

        $name = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1)

        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        $currentValue = [Environment]::GetEnvironmentVariable($name, "Process")
        if ($Override -or [string]::IsNullOrEmpty($currentValue)) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Import-ProjectEnvironment {
    Import-DotEnvFile -Path (Resolve-ProjectPath ".env")
}

function Get-EnvValue {
    param(
        [Parameter(Mandatory)]
        [string]$Name,
        [string]$Default = ""
    )

    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }

    return $value.Trim()
}

function Get-IntEnvValue {
    param(
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [int]$Default
    )

    $rawValue = Get-EnvValue -Name $Name
    if ([string]::IsNullOrWhiteSpace($rawValue)) {
        return $Default
    }

    $parsedValue = 0
    if (-not [int]::TryParse($rawValue, [ref]$parsedValue)) {
        throw "Environment variable $Name must be an integer, but got '$rawValue'."
    }

    return $parsedValue
}

function Get-VenvExecutable {
    param(
        [Parameter(Mandatory)]
        [string]$RelativePath,
        [Parameter(Mandatory)]
        [string]$DisplayName
    )

    $fullPath = Resolve-ProjectPath $RelativePath
    if (-not (Test-Path -LiteralPath $fullPath)) {
        throw "$DisplayName was not found at $fullPath. Run .\scripts\dev\full-start.ps1 first."
    }

    return (Resolve-Path -LiteralPath $fullPath).Path
}

function Invoke-InProjectRoot {
    param(
        [Parameter(Mandatory)]
        [scriptblock]$ScriptBlock
    )

    Push-Location $script:ProjectRoot
    try {
        & $ScriptBlock
    }
    finally {
        Pop-Location
    }
}

function Get-CachedCMakeGeneratorArgs {
    param(
        [Parameter(Mandatory)]
        [string]$BuildDirectoryRelativePath
    )

    $cachePath = Resolve-ProjectPath (Join-Path $BuildDirectoryRelativePath "CMakeCache.txt")
    if (-not (Test-Path -LiteralPath $cachePath)) {
        return $null
    }

    $generator = $null
    $platform = $null
    $toolset = $null

    foreach ($line in Get-Content -LiteralPath $cachePath -Encoding utf8) {
        if ($line -match '^CMAKE_GENERATOR:INTERNAL=(.+)$') {
            $generator = $matches[1].Trim()
            continue
        }
        if ($line -match '^CMAKE_GENERATOR_PLATFORM:INTERNAL=(.*)$') {
            $platform = $matches[1].Trim()
            continue
        }
        if ($line -match '^CMAKE_GENERATOR_TOOLSET:INTERNAL=(.*)$') {
            $toolset = $matches[1].Trim()
            continue
        }
    }

    if ([string]::IsNullOrWhiteSpace($generator)) {
        return $null
    }

    $args = @("-G", $generator)
    if (-not [string]::IsNullOrWhiteSpace($platform)) {
        $args += @("-A", $platform)
    }
    if (-not [string]::IsNullOrWhiteSpace($toolset)) {
        $args += @("-T", $toolset)
    }

    return $args
}

function Get-CMakeGeneratorArgs {
    param(
        [string]$BuildDirectoryRelativePath = "algo-module/build"
    )

    $mingwMake = Get-Command mingw32-make -ErrorAction SilentlyContinue
    $gxx = Get-Command g++ -ErrorAction SilentlyContinue
    if ($mingwMake -and $gxx) {
        return @("-G", "MinGW Makefiles")
    }

    throw @"
MinGW toolchain was not detected for CMake.
This project is configured to use MinGW Makefiles.
Please make sure both commands are available in PowerShell and reopen the terminal:
1) g++
2) mingw32-make
"@
}

function Test-VisualStudioGenerator {
    param(
        [Parameter(Mandatory)]
        [string[]]$GeneratorArgs
    )

    return (
        $GeneratorArgs.Count -ge 2 -and
        $GeneratorArgs[0] -eq "-G" -and
        $GeneratorArgs[1] -eq "Visual Studio 17 2022"
    )
}

function Test-CMakeGeneratorArgsEqual {
    param(
        [Parameter(Mandatory)]
        [string[]]$Left,
        [Parameter(Mandatory)]
        [string[]]$Right
    )

    if ($Left.Count -ne $Right.Count) {
        return $false
    }

    for ($index = 0; $index -lt $Left.Count; $index += 1) {
        if ($Left[$index] -ne $Right[$index]) {
            return $false
        }
    }

    return $true
}

function Start-PostgresContainer {
    Invoke-InProjectRoot {
        docker compose -f deploy/docker-compose.yml up -d postgres
    }
}
