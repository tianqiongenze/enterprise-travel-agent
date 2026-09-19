Param(
    [switch]$SkipInstall,
    [switch]$SkipK8s,
    [switch]$SkipLoadTest,
    [int]$LoadRequests = 500,
    [int]$LoadConcurrency = 50,
    [ValidateSet("online", "prepare", "offline")]
    [string]$PackageMode = $(if ($env:TRAVEL_PACKAGE_MODE) { $env:TRAVEL_PACKAGE_MODE } else { "online" }),
    [string]$OfflineBundleDir = $(if ($env:TRAVEL_OFFLINE_BUNDLE_DIR) { $env:TRAVEL_OFFLINE_BUNDLE_DIR } else { "platform/deploy/offline_bundle" }),
    [string]$ArtifactManifest = $(if ($env:TRAVEL_ARTIFACT_MANIFEST) { $env:TRAVEL_ARTIFACT_MANIFEST } else { "artifacts.manifest.json" }),
    [switch]$OfflineStrict,
    [string]$OfflineToolInstallDir = $(if ($env:TRAVEL_OFFLINE_TOOL_INSTALL_DIR) { $env:TRAVEL_OFFLINE_TOOL_INSTALL_DIR } else { "var/offline_tools/bin" }),
    [switch]$BundleSkipDockerImages,
    [switch]$BundleSkipTools,
    [string]$BundleToolTargets = $(if ($env:TRAVEL_BUNDLE_TOOL_TARGETS) { $env:TRAVEL_BUNDLE_TOOL_TARGETS } else { "windows-amd64,linux-amd64,darwin-amd64,darwin-arm64" }),
    [string]$BundleKubectlVersion = $(if ($env:TRAVEL_BUNDLE_KUBECTL_VERSION) { $env:TRAVEL_BUNDLE_KUBECTL_VERSION } else { "v1.31.1" }),
    [string]$BundleKindVersion = $(if ($env:TRAVEL_BUNDLE_KIND_VERSION) { $env:TRAVEL_BUNDLE_KIND_VERSION } else { "v0.29.0" }),
    [string]$BundleDockerInstallerWindows,
    [string]$BundleDockerInstallerLinux,
    [string]$BundleDockerInstallerMacos,
    [ValidateSet("kind", "rancher-desktop")]
    [string]$K8sProvider = $(if ($env:TRAVEL_K8S_PROVIDER) { $env:TRAVEL_K8S_PROVIDER } else { "kind" })
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$orchestrator = Join-Path $repoRoot "platform\deploy\scripts\one_click_stack.py"
$cmd = @(
    "python", "-u", $orchestrator,
    "--project-root", $repoRoot,
    "--load-requests", "$LoadRequests",
    "--load-concurrency", "$LoadConcurrency",
    "--package-mode", $PackageMode,
    "--offline-bundle-dir", $OfflineBundleDir,
    "--artifact-manifest", $ArtifactManifest,
    "--offline-tool-install-dir", $OfflineToolInstallDir,
    "--bundle-tool-targets", $BundleToolTargets,
    "--bundle-kubectl-version", $BundleKubectlVersion,
    "--bundle-kind-version", $BundleKindVersion,
    "--k8s-provider", $K8sProvider
)

if ($SkipInstall) { $cmd += "--skip-install" }
if ($SkipK8s) { $cmd += "--skip-k8s" }
if ($SkipLoadTest) { $cmd += "--skip-load-test" }
if ($OfflineStrict) { $cmd += "--offline-strict" }
if ($BundleSkipDockerImages) { $cmd += "--bundle-skip-docker-images" }
if ($BundleSkipTools) { $cmd += "--bundle-skip-tools" }
if ($BundleDockerInstallerWindows) { $cmd += @("--bundle-docker-installer-windows", $BundleDockerInstallerWindows) }
if ($BundleDockerInstallerLinux) { $cmd += @("--bundle-docker-installer-linux", $BundleDockerInstallerLinux) }
if ($BundleDockerInstallerMacos) { $cmd += @("--bundle-docker-installer-macos", $BundleDockerInstallerMacos) }

Write-Host "[run] $($cmd -join ' ')"
& $cmd[0] $cmd[1..($cmd.Length - 1)]
if ($LASTEXITCODE -ne 0) {
    throw "one-click orchestrator failed with code $LASTEXITCODE"
}

