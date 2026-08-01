<#
Create or verify the frozen source identity shared by morph search and MFA.
This script never edits the frozen source data.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$MorphRunId = 'morph_search_v3_20260801',
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SearchMasterRunId = 'pre_mfa_v1_20260725',
    [switch]$Ensure,
    [switch]$RequireMorphYearSuccess,
    [string]$Output = ''
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
function Same-Path([string]$Left, [string]$Right) {
    return [string]::Equals(
        [IO.Path]::GetFullPath($Left).TrimEnd('\'),
        [IO.Path]::GetFullPath($Right).TrimEnd('\'),
        [StringComparison]::OrdinalIgnoreCase
    )
}
function Write-JsonAtomic([string]$Path, $Payload) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $partial = "$Path.$PID.partial"
    $Payload | ConvertTo-Json -Depth 12 |
        Set-Content -LiteralPath $partial -Encoding UTF8
    Move-Item -LiteralPath $partial -Destination $Path -Force
}

$sourceRoot = Resolve-ConfiguredPath ([string]$config.pre_mfa_search_master)
$morphBase = Resolve-ConfiguredPath ([string]$config.morph_search_v3_staging)
$sourceMeta = Join-Path $sourceRoot '_build_meta.json'
$inputRoot = Join-Path $sourceRoot $Year
$outputRoot = Join-Path (Join-Path $morphBase $MorphRunId) $Year
$contractPath = Join-Path $outputRoot 'SOURCE_CONTRACT.json'
$yearManifestPath = Join-Path $outputRoot 'annual_tables\YEAR_MANIFEST.json'
if ([string]::IsNullOrWhiteSpace($Output)) {
    $Output = Join-Path $projectRoot (
        "outputs\reports\SOURCE_CONTRACT_${MorphRunId}_${Year}.json"
    )
}
$Output = [IO.Path]::GetFullPath($Output)

$checks = New-Object System.Collections.Generic.List[object]
function Add-Check([string]$Name, [bool]$Passed, [string]$Detail) {
    $checks.Add([ordered]@{
        name = $Name
        status = if ($Passed) { 'passed' } else { 'failed' }
        detail = $Detail
    })
}

$sourceExists = Test-Path -LiteralPath $sourceMeta -PathType Leaf
Add-Check 'source_meta_exists' $sourceExists $sourceMeta
$inputExists = Test-Path -LiteralPath $inputRoot -PathType Container
Add-Check 'year_input_exists' $inputExists $inputRoot
if (-not $sourceExists -or -not $inputExists) {
    $failedEarly = [ordered]@{
        schema_version = 'production_source_contract_check.v1'
        status = 'failed'
        checked_at = (Get-Date).ToString('o')
        year = $Year
        checks = @($checks | ForEach-Object { $_ })
    }
    Write-JsonAtomic $Output $failedEarly
    Write-Error "Frozen source is missing. Report: $Output"
    exit 1
}

$meta = Get-Content -LiteralPath $sourceMeta -Raw -Encoding UTF8 |
    ConvertFrom-Json
$sourceSha = (Get-FileHash -LiteralPath $sourceMeta -Algorithm SHA256).Hash.ToLowerInvariant()
Add-Check 'source_meta_success' ([string]$meta.status -eq 'success') (
    "status=$($meta.status)"
)
Add-Check 'search_master_run_id' (
    [string]$meta.run_id -eq $SearchMasterRunId
) "actual=$($meta.run_id), expected=$SearchMasterRunId"

if (-not (Test-Path -LiteralPath $contractPath -PathType Leaf) -and $Ensure) {
    $contract = [ordered]@{
        schema_version = 'production_frozen_source_contract.v1'
        status = 'frozen'
        created_at = (Get-Date).ToString('o')
        year = $Year
        morph_run_id = $MorphRunId
        search_master_run_id = $SearchMasterRunId
        source_meta = [ordered]@{
            path = $sourceMeta
            sha256 = $sourceSha
            status = [string]$meta.status
        }
        input_root = $inputRoot
        output_root = $outputRoot
        raw_source_modified = $false
    }
    Write-JsonAtomic $contractPath $contract
}

$contractExists = Test-Path -LiteralPath $contractPath -PathType Leaf
Add-Check 'source_contract_exists' $contractExists $contractPath
if ($contractExists) {
    $contract = Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    Add-Check 'source_contract_schema' (
        [string]$contract.schema_version -eq 'production_frozen_source_contract.v1'
    ) "schema=$($contract.schema_version)"
    Add-Check 'source_contract_year' (
        [string]$contract.year -eq $Year
    ) "actual=$($contract.year), expected=$Year"
    Add-Check 'source_contract_run_ids' (
        [string]$contract.morph_run_id -eq $MorphRunId -and
        [string]$contract.search_master_run_id -eq $SearchMasterRunId
    ) "morph=$($contract.morph_run_id), search=$($contract.search_master_run_id)"
    Add-Check 'source_contract_sha256' (
        [string]$contract.source_meta.sha256 -eq $sourceSha
    ) "actual=$($contract.source_meta.sha256), expected=$sourceSha"
    Add-Check 'source_contract_paths' (
        (Same-Path ([string]$contract.source_meta.path) $sourceMeta) -and
        (Same-Path ([string]$contract.input_root) $inputRoot) -and
        (Same-Path ([string]$contract.output_root) $outputRoot)
    ) 'source/input/output path identity'
}

if ($RequireMorphYearSuccess) {
    $manifestExists = Test-Path -LiteralPath $yearManifestPath -PathType Leaf
    Add-Check 'morph_year_manifest_exists' $manifestExists $yearManifestPath
    if ($manifestExists) {
        $yearManifest = Get-Content -LiteralPath $yearManifestPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        Add-Check 'morph_year_manifest_success' (
            [string]$yearManifest.status -eq 'success' -and
            [string]$yearManifest.year -eq $Year
        ) "status=$($yearManifest.status), year=$($yearManifest.year)"
    }
}

$checkRows = @($checks | ForEach-Object { $_ })
$failed = @($checkRows | Where-Object { $_.status -eq 'failed' })
$report = [ordered]@{
    schema_version = 'production_source_contract_check.v1'
    status = if ($failed.Count -eq 0) { 'passed' } else { 'failed' }
    checked_at = (Get-Date).ToString('o')
    year = $Year
    morph_run_id = $MorphRunId
    search_master_run_id = $SearchMasterRunId
    source_meta_sha256 = $sourceSha
    source_contract = $contractPath
    year_manifest = $yearManifestPath
    checks = $checkRows
    failed_checks = @($failed | ForEach-Object { $_.name })
    modifies_frozen_source = $false
}
Write-JsonAtomic $Output $report
Write-Host "source contract status=$($report.status)"
Write-Host "report=$Output"
if ($report.status -ne 'passed') { exit 1 }
