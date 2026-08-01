# 2020-2025 r2 전수 MFA 무인 큐 시작 전 최종 GO/NO-GO 검사.
# MFA·WAV 이동·승인·승격은 수행하지 않고 JSON 보고서만 쓴다.

[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$QueueId = 'mfa_r2_full6y_20260801',
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SearchMasterRunId = 'pre_mfa_v1_20260725',
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string[]]$Years = @('2020','2021','2022','2023','2024','2025'),
    [Parameter(Mandatory=$true)]
    [string]$CommonPronManifest,
    [Parameter(Mandatory=$true)]
    [string]$CommonPronAdoptionContract,
    [Parameter(Mandatory=$true)]
    [string]$ApprovedExclusionsRoot,
    [string]$Output = '',
    [switch]$RunRepositoryTests
)

$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) -Raw -Encoding UTF8 | ConvertFrom-Json
function Resolve-ConfiguredPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}
function Find-Approval([string]$Root, [string]$Year) {
    foreach ($candidate in @(
        (Join-Path $Root "$Year\approved_exclusions.json"),
        (Join-Path $Root "approved_exclusions_${Year}.json")
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return [IO.Path]::GetFullPath($candidate)
        }
    }
    return $null
}

$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
$stateRoot = Resolve-ConfiguredPath ([string]$config.mfa_state)
$layersRoot = Resolve-ConfiguredPath ([string]$config.layers)
$searchMasterRoot = Join-Path $layersRoot (
    "05_search_master_pre_mfa_staging\$SearchMasterRunId"
)
$CommonPronManifest = [IO.Path]::GetFullPath($CommonPronManifest)
$CommonPronAdoptionContract = [IO.Path]::GetFullPath(
    $CommonPronAdoptionContract
)
$ApprovedExclusionsRoot = [IO.Path]::GetFullPath(
    $ApprovedExclusionsRoot
)
if ([string]::IsNullOrWhiteSpace($Output)) {
    $Output = Join-Path $projectRoot (
        "outputs\reports\PREFLIGHT_mfa_year_queue_${QueueId}.json"
    )
}
$Output = [IO.Path]::GetFullPath($Output)
$outputParent = Split-Path -Parent $Output
New-Item -ItemType Directory -Force -Path $outputParent | Out-Null
$checks = New-Object System.Collections.Generic.List[object]
function Add-Check([string]$Name, [bool]$Passed, [string]$Detail,
                   [string]$Severity = 'hard') {
    $checks.Add([ordered]@{
        name = $Name
        status = $(if ($Passed) { 'passed' } elseif ($Severity -eq 'warn') {
            'warning'
        } else { 'failed' })
        severity = $Severity
        detail = $Detail
    })
}

Add-Check 'pipeline_python_exists' (
    Test-Path -LiteralPath $python -PathType Leaf
) $python
Add-Check 'common_manifest_exists' (
    Test-Path -LiteralPath $CommonPronManifest -PathType Leaf
) $CommonPronManifest
Add-Check 'common_adoption_exists' (
    Test-Path -LiteralPath $CommonPronAdoptionContract -PathType Leaf
) $CommonPronAdoptionContract
Add-Check 'search_master_success_meta' (
    Test-Path -LiteralPath (
        Join-Path $searchMasterRoot '_build_meta.json'
    ) -PathType Leaf
) $searchMasterRoot

$dLabel = $null
$dFree = $null
try {
    $drive = [IO.DriveInfo]::new('D:\')
    $dLabel = $drive.VolumeLabel
    $dFree = [math]::Round($drive.AvailableFreeSpace / 1GB, 2)
} catch {}
Add-Check 'D_volume_label_DATA_SSD' ($dLabel -eq 'DATA_SSD') (
    "label=$dLabel"
)
Add-Check 'D_free_space_at_least_55GiB' (
    $null -ne $dFree -and [double]$dFree -ge 55
) "free_gib=$dFree"

$liveLocks = New-Object System.Collections.Generic.List[string]
$staleLocks = New-Object System.Collections.Generic.List[string]
$lockCandidates = @(
    (Join-Path $stateRoot 'locks\pre_mfa_bulk.lock'),
    (Join-Path $stateRoot 'locks\mfa_year_queue.lock')
)
$commonHome = Resolve-ConfiguredPath ([string]$config.common_pron_home)
if (Test-Path -LiteralPath (Join-Path $commonHome 'locks')) {
    $lockCandidates += @(
        Get-ChildItem -LiteralPath (Join-Path $commonHome 'locks') `
            -Filter *.lock -File -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName }
    )
}
foreach ($lockPath in $lockCandidates) {
    if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) { continue }
    $alive = $false
    try {
        $lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        if ($lock.pid) {
            $alive = $null -ne (
                Get-Process -Id ([int]$lock.pid) -ErrorAction SilentlyContinue
            )
        }
    } catch {}
    if ($alive) { $liveLocks.Add($lockPath) }
    else { $staleLocks.Add($lockPath) }
}
Add-Check 'no_live_conflicting_lock' ($liveLocks.Count -eq 0) (
    $liveLocks -join '; '
)
Add-Check 'stale_lock_inventory' ($staleLocks.Count -eq 0) (
    $staleLocks -join '; '
) 'warn'

$adoptionReport = Join-Path $outputParent (
    "PREFLIGHT_mfa_adoption_${QueueId}.json"
)
if (
    (Test-Path -LiteralPath $python -PathType Leaf) -and
    (Test-Path -LiteralPath $CommonPronManifest -PathType Leaf) -and
    (Test-Path -LiteralPath $CommonPronAdoptionContract -PathType Leaf)
) {
    & $python (Join-Path $PSScriptRoot (
        'python\validate_mfa_r2_adoption.py'
    )) --manifest $CommonPronManifest `
        --adoption-contract $CommonPronAdoptionContract `
        --output $adoptionReport | Out-Host
    Add-Check 'common_pron_adoption_runtime_validation' (
        $LASTEXITCODE -eq 0
    ) $adoptionReport
} else {
    Add-Check 'common_pron_adoption_runtime_validation' $false (
        '필수 파일이 없어 실행하지 못함'
    )
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
    Join-Path $PSScriptRoot 'preflight_eojeol_realign.ps1'
) -SearchMasterRoot $searchMasterRoot `
    -ExpectedPronunciationMode 'common_pron_mfa_r2_latest_jamo' `
    -PreferD
Add-Check 'existing_eojeol_preflight_all_years' (
    $LASTEXITCODE -eq 0
) 'scripts/preflight_eojeol_realign.ps1'

foreach ($year in $Years) {
    $labReport = Join-Path $stateRoot "logs\lab_build_${year}_latest.json"
    if (-not (Test-Path -LiteralPath $labReport -PathType Leaf)) {
        Add-Check "${year}_lab_input_contract" $false (
            "lab report 없음: $labReport"
        )
        Add-Check "${year}_approved_exclusions" $false (
            'lab 입력계약이 없어 승인 계약 검증 불가'
        )
        continue
    }
    $inputId = $null
    try {
        $lab = Get-Content -LiteralPath $labReport -Raw -Encoding UTF8 |
            ConvertFrom-Json
        if ($lab.status -eq 'passed') {
            $inputId = [string]$lab.input_contract_id
        }
    } catch {}
    Add-Check "${year}_lab_input_contract" (
        -not [string]::IsNullOrWhiteSpace($inputId)
    ) "report=$labReport input_contract_id=$inputId"
    $approval = Find-Approval $ApprovedExclusionsRoot $year
    if ($null -eq $approval) {
        Add-Check "${year}_approved_exclusions" $false (
            "승인 계약 없음: $ApprovedExclusionsRoot"
        )
        continue
    }
    if ([string]::IsNullOrWhiteSpace($inputId)) {
        Add-Check "${year}_approved_exclusions" $false (
            "입력 계약 ID 없음: $approval"
        )
        continue
    }
    & $python (Join-Path $PSScriptRoot (
        'python\mfa_exclusion_contract.py'
    )) validate --contract $approval --year $year `
        --input-contract-id $inputId | Out-Host
    Add-Check "${year}_approved_exclusions" (
        $LASTEXITCODE -eq 0
    ) $approval
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (
    Join-Path $projectRoot 'tests\test_powershell_safety.ps1'
) | Out-Host
Add-Check 'powershell_static_safety' ($LASTEXITCODE -eq 0) (
    'tests/test_powershell_safety.ps1'
)
if ($RunRepositoryTests) {
    & $python -m unittest discover -s (Join-Path $projectRoot 'tests') |
        Out-Host
    Add-Check 'python_full_test_suite' ($LASTEXITCODE -eq 0) (
        'python -m unittest discover -s tests'
    )
}

& git -C $projectRoot diff --quiet
$trackedClean = $LASTEXITCODE -eq 0
& git -C $projectRoot diff --cached --quiet
$stagedClean = $LASTEXITCODE -eq 0
Add-Check 'tracked_code_committed' ($trackedClean -and $stagedClean) (
    "working_diff_clean=$trackedClean staged_diff_clean=$stagedClean"
)

$failed = @($checks | Where-Object { $_.status -eq 'failed' })
$warnings = @($checks | Where-Object { $_.status -eq 'warning' })
$finalStatus = if ($failed.Count -eq 0) { 'GO' } else { 'NO_GO' }
$checkRows = @($checks | ForEach-Object { $_ })
$failedNames = @($failed | ForEach-Object { $_.name })
$warningNames = @($warnings | ForEach-Object { $_.name })
$report = [ordered]@{
    schema_version = 'mfa_r2_full_year_queue_preflight.v1'
    status = $finalStatus
    checked_at = (Get-Date).ToString('o')
    queue_id = $QueueId
    search_master_run_id = $SearchMasterRunId
    years = @($Years)
    checks = $checkRows
    failed_checks = $failedNames
    warning_checks = $warningNames
    d_drive = [ordered]@{ label = $dLabel; free_gib = $dFree }
    output = $Output
    starts_mfa = $false
    approves_exclusions = $false
    promotes_canonical_outputs = $false
}
$partial = "$Output.$PID.partial"
$report | ConvertTo-Json -Depth 10 |
    Set-Content -LiteralPath $partial -Encoding UTF8
Move-Item -LiteralPath $partial -Destination $Output -Force
Write-Host "최종 preflight: $($report.status)" -ForegroundColor $(if (
    $report.status -eq 'GO'
) { 'Green' } else { 'Red' })
Write-Host "보고서: $Output"
if ($report.status -eq 'GO') { exit 0 }
exit 1
