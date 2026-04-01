Param(
    [string]$DriveLetter = "X"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$gatewayDir = Join-Path $repoRoot "services\techgroup-enterprise-travel-gateway"
$drive = ($DriveLetter.TrimEnd(':') + ":")
$mapped = $false

try {
    # protobuf-maven-plugin on Windows can fail on non-ASCII absolute paths.
    & subst.exe $drive $repoRoot | Out-Null
    $mapped = $true
    if (-not (Test-Path "$drive\")) {
        throw "failed to map $drive to $repoRoot"
    }
    Push-Location ("$drive\services\techgroup-enterprise-travel-gateway")
    mvn -q generate-sources
    Pop-Location
    Write-Host "[grpc-java] generated: services/techgroup-enterprise-travel-gateway/target/generated-sources/protobuf"
}
finally {
    if ($mapped) {
        & subst.exe $drive /D | Out-Null
    }
}

