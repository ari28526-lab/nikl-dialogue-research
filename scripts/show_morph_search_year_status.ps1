[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$RunId = 'morph_search_v3_20260801'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) -Raw -Encoding UTF8 | ConvertFrom-Json
function Resolve-ConfiguredPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}

$base = Resolve-ConfiguredPath ([string]$config.morph_search_v3_staging)
$root = Join-Path (Join-Path $base $RunId) $Year
$progressPath = Join-Path $root 'YEAR_PROGRESS.json'
$contractPath = Join-Path $root 'RUN_CONTRACT.json'
$manifestPath = Join-Path $root 'annual_tables\YEAR_MANIFEST.json'
$lockPath = Join-Path $root 'RUNNING.lock.json'
$driveName = ([IO.Path]::GetPathRoot($base)).TrimEnd('\').TrimEnd(':')
$drive = Get-PSDrive -Name $driveName

Write-Host 'Morph combination-search year dashboard (read-only)'
Write-Host "Observed: $(Get-Date -Format o)"
Write-Host "Root:     $root"
Write-Host "D free:   $([math]::Round($drive.Free / 1GB, 3)) GiB"
Write-Host "Lock:     $(Test-Path -LiteralPath $lockPath -PathType Leaf)"
Write-Host ''

if (Test-Path -LiteralPath $contractPath -PathType Leaf) {
    $contract = Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    [pscustomobject]@{
        year = $contract.year
        input_files = $contract.input_files
        files_per_shard = $contract.files_per_shard
        total_shards = $contract.shards
        morph_schema = $contract.versions.morph_schema
        symbol_schema = $contract.versions.symbol_schema
    } | Format-List
}
if (Test-Path -LiteralPath $progressPath -PathType Leaf) {
    $progress = Get-Content -LiteralPath $progressPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $progress | Format-List
} else {
    Write-Host 'Progress: not started'
}
if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    Write-Host ''
    Write-Host 'Annual manifest: success'
    $manifest.tables.PSObject.Properties | ForEach-Object {
        [pscustomobject]@{
            table = $_.Name
            rows = $_.Value.rows
            bytes = $_.Value.bytes
            sha256 = $_.Value.sha256
        }
    } | Format-Table -AutoSize
}
