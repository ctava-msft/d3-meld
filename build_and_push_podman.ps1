<#
.SYNOPSIS
    Build and push the MELD MPI container image to Azure Container Registry using Podman.

.DESCRIPTION
    Automates:
      1. (Optional) Podman machine init/start (if on Windows/macOS and requested)
      2. Azure login validation
      3. ACR login (direct or token fallback)
      4. Image build from Dockerfile.mpi
      5. Push to ACR
      6. (Optional) Emit image digest for pinning

.PARAMETER AcrName
    Name of the Azure Container Registry (no domain). Example: myacr

.PARAMETER Image
    Repository/image name within ACR. Default: d3-meld-mpi

.PARAMETER Tag
    Image tag to build/push. Default: latest

.PARAMETER Dockerfile
    Path to Dockerfile (default Dockerfile.mpi)

.PARAMETER Context
    Build context directory. Default: current directory

.PARAMETER UseTokenLogin
    Force token-based login instead of az acr login

.PARAMETER EmitDigest
    Output the repo@digest string at the end

.PARAMETER InitMachine
    Run 'podman machine init' and 'podman machine start' if not already created (ignored on Linux)

.EXAMPLE
    ./build_and_push_podman.ps1 -AcrName d3acr1 -Image d3-meld-mpi -Tag test1 -EmitDigest

.EXAMPLE
    ./build_and_push_podman.ps1 -AcrName d3acr1 -UseTokenLogin -InitMachine

.NOTES
    Requires: Azure CLI, Podman
#>
[CmdletBinding()] param(
    [Parameter(Mandatory=$true)] [string]$AcrName,
    [string]$Image = 'd3-meld-mpi',
    [string]$Tag = 'latest',
    [string]$Dockerfile = 'Dockerfile.mpi',
    [string]$Context = '.',
    [switch]$UseTokenLogin,
    [switch]$EmitDigest,
    [switch]$InitMachine
)

function Write-Info { param([string]$Msg) Write-Host "[INFO ] $Msg" -ForegroundColor Cyan }
function Write-Warn { param([string]$Msg) Write-Host "[WARN ] $Msg" -ForegroundColor Yellow }
function Write-Err  { param([string]$Msg) Write-Host "[ERROR] $Msg" -ForegroundColor Red }

# 1. Podman machine (Windows/macOS scenario)
if ($InitMachine) {
    if ($env:OS -and $env:OS -match 'Windows') {
        Write-Info 'Ensuring Podman machine exists...'
        $machines = podman machine list --format json 2>$null | ConvertFrom-Json 2>$null
        if (-not $machines) {
            Write-Info 'No machine found. Initializing.'
            podman machine init | Out-Null
        }
        Write-Info 'Starting Podman machine'
        podman machine start | Out-Null
        Write-Info 'Podman machine started.'
    } else {
        Write-Warn 'InitMachine specified but not on Windows; skipping.'
    }
}

# 2. Azure login check
Write-Info 'Validating Azure CLI session'
try {
    $account = az account show -o json | ConvertFrom-Json
    if (-not $account) { throw 'Not logged in' }
    Write-Info "Azure subscription: $($account.name)"
} catch {
    Write-Err 'Azure CLI not logged in. Run: az login'
    exit 1
}

# 3. ACR login
$registryFqdn = "$AcrName.azurecr.io"
Write-Info "Logging into ACR: $registryFqdn"
$loginSuccess = $false
if (-not $UseTokenLogin) {
    try {
        az acr login --name $AcrName 2>$null | Out-Null
        $loginSuccess = $true
        Write-Info 'Logged in via az acr login.'
    } catch {
        Write-Warn 'az acr login failed, will attempt token fallback.'
    }
}
if (-not $loginSuccess) {
    try {
        $token = az acr login --name $AcrName --expose-token --query accessToken -o tsv
        if (-not $token) { throw 'Token empty' }
        podman login $registryFqdn -u 00000000-0000-0000-0000-000000000000 -p $token | Out-Null
        Write-Info 'Logged in with token fallback.'
        $loginSuccess = $true
    } catch {
        Write-Err 'ACR token login failed.'
        exit 1
    }
}

# 4. Build image
if (-not (Test-Path $Dockerfile)) {
    Write-Err "Dockerfile not found: $Dockerfile"
    exit 1
}

$fullTag = "${registryFqdn}/${Image}:$Tag"
Write-Info "Building image $fullTag"
$buildArgs = @('-f', $Dockerfile, '-t', $fullTag, $Context)
podman build @buildArgs
if ($LASTEXITCODE -ne 0) {
    Write-Err 'Image build failed.'
    exit $LASTEXITCODE
}
Write-Info 'Build complete.'

# 5. Push image
Write-Info 'Pushing image to ACR'
podman push $fullTag
if ($LASTEXITCODE -ne 0) {
    Write-Err 'Image push failed.'
    exit $LASTEXITCODE
}
Write-Info 'Push complete.'

# 6. Emit digest
if ($EmitDigest) {
    Write-Info 'Retrieving digest'
    $inspect = podman inspect $fullTag --format '{{.Digest}}'
    if ($LASTEXITCODE -eq 0 -and $inspect) {
        $digestRef = "$registryFqdn/$Image@$inspect"
        Write-Host "DIGEST_REFERENCE=$digestRef" -ForegroundColor Green
    } else {
        Write-Warn 'Could not retrieve digest.'
    }
}

Write-Info 'Done.'
