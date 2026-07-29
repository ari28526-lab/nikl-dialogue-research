#Requires -Version 5.1
<#
2020 TextGrid·부분 DB와 2021 완성 DB를 공통발음사전 r2와 전수 비교한다.

- 모든 baseline은 읽기 전용이다.
- 2020 TextGrid는 batch마다 checkpoint를 남겨 중단 후 재개한다.
- 차이를 숨기지 않고 분류 inventory로 기록한다.
- 이 스크립트는 adoption이나 연도별 MFA를 자동 승인하지 않는다.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^common_pron_mfa_r2_[0-9]{8}$')]
    [string]$ReleaseId = 'common_pron_mfa_r2_20260728',

    [ValidatePattern('^common_pron_pilot_[a-z0-9_]+_[0-9]{8}$')]
    [string]$SourceReleaseId = 'common_pron_pilot_full6y_20260728',

    [ValidateRange(1, 16)]
    [int]$Workers = 4,

    [ValidateRange(100, 10000)]
    [int]$BatchSize = 2000,

    [ValidateRange(10, 500)]
    [int]$MinimumFreeGiB = 30
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (
    Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')
).Path
$config = Get-Content -Raw -Encoding UTF8 `
    -LiteralPath (Join-Path $projectRoot 'config\paths.json') |
    ConvertFrom-Json

function Expand-CfgPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables(
            $Value.Replace('/', '\')
        )
    )
}

function Say([string]$Message) {
    Write-Host (
        '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    ) -ForegroundColor Cyan
}

function Assert-Child([string]$Path, [string]$Root) {
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $allowed = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith(
        $allowed, [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "경로 경계 위반: $resolved (root=$Root)"
    }
}

function Acquire-Lock([string]$LockPath, [string]$CommonRoot) {
    Assert-Child $LockPath $CommonRoot
    New-Item -ItemType Directory -Force `
        -Path (Split-Path -Parent $LockPath) | Out-Null
    if (Test-Path -LiteralPath $LockPath) {
        $live = $false
        try {
            $old = Get-Content -Raw -Encoding UTF8 `
                -LiteralPath $LockPath | ConvertFrom-Json
            $live = [int]$old.pid -gt 0 -and $null -ne (
                Get-Process -Id ([int]$old.pid) `
                    -ErrorAction SilentlyContinue
            )
        } catch {}
        if ($live) {
            throw "차이 inventory lock 사용 중: $LockPath"
        }
        $archive = Join-Path $CommonRoot (
            'archive_stale_locks\{0}_difference_inventory.json' -f
            (Get-Date -Format 'yyyyMMdd_HHmmss')
        )
        Assert-Child $archive $CommonRoot
        New-Item -ItemType Directory -Force `
            -Path (Split-Path -Parent $archive) | Out-Null
        Move-Item -LiteralPath $LockPath -Destination $archive
        Say "종료된 차이감사 lock 보존: $archive"
    }
    $temp = "$LockPath.$PID.partial"
    [ordered]@{
        schema_version = 1
        release_id = $ReleaseId
        pipeline = 'common_pron_difference_inventory'
        pid = $PID
        host = $env:COMPUTERNAME
        acquired_at = (Get-Date).ToString('o')
    } | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $LockPath
}

function Release-Lock([string]$LockPath) {
    if (-not (Test-Path -LiteralPath $LockPath)) { return }
    try {
        $lock = Get-Content -Raw -Encoding UTF8 `
            -LiteralPath $LockPath | ConvertFrom-Json
        if (
            [int]$lock.pid -eq $PID -and
            [string]$lock.release_id -eq $ReleaseId
        ) {
            Remove-Item -LiteralPath $LockPath -Force
        }
    } catch {
        Write-Warning "차이감사 lock 해제 실패: $LockPath"
    }
}

$commonRoot = Expand-CfgPath ([string]$config.common_pron_home)
$expectedRoot = [IO.Path]::GetFullPath('D:\mfa_common_pron')
if ($commonRoot.TrimEnd('\') -ne $expectedRoot.TrimEnd('\')) {
    throw "공통 발음 root 안전 차단: $commonRoot"
}
$drive = [IO.DriveInfo]::new('D')
if (-not $drive.IsReady -or $drive.VolumeLabel -ne 'DATA_SSD') {
    throw "D: DATA_SSD 안전 차단"
}
$freeGiB = [math]::Round($drive.AvailableFreeSpace / 1GB, 3)
if ($freeGiB -lt $MinimumFreeGiB) {
    throw "D: 공간 부족: ${freeGiB}GiB < ${MinimumFreeGiB}GiB"
}

$releaseRoot = Join-Path (
    Join-Path $commonRoot 'releases'
) $ReleaseId
$sourceRoot = Join-Path (
    Join-Path $commonRoot 'releases'
) $SourceReleaseId
Assert-Child $releaseRoot $commonRoot
Assert-Child $sourceRoot $commonRoot

$python = Expand-CfgPath ([string]$config.pipeline_python)
$driver = Join-Path (
    Join-Path $projectRoot 'scripts\python'
) 'audit_common_pron_mfa_equivalence.py'
$commonManifest = Join-Path (
    Join-Path $releaseRoot '00_contract'
) 'release_manifest.json'
$vocabulary = Join-Path (
    Join-Path $sourceRoot '01_vocabulary'
) 'common_vocabulary_2020_2025.csv'
$textgrid2020 = Join-Path (
    Expand-CfgPath ([string]$config.textgrid_eojeol_staging)
) '2020'
$partialDatabase2020 = (
    'D:\mfa_eojeol\archive_stale_temp\20260725_141701\' +
    'C\2020\2020.db'
)
$database2021 = Join-Path (
    Expand-CfgPath ([string]$config.mfa_temp_secondary)
) '2021\2021.db'
$qc2020 = Join-Path (
    Join-Path $projectRoot 'outputs\reports'
) 'AUDIT_mfa_4tier_2020_pre_mfa_v1_20260728.json'
$integrity2021 = Join-Path (
    Join-Path $projectRoot 'outputs\reports'
) 'SQLITE_integrity_2021_pre_mfa_v1_20260728.json'

foreach ($path in @(
    $python, $driver, $commonManifest, $vocabulary, $textgrid2020,
    $partialDatabase2020, $database2021, $qc2020, $integrity2021
)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "차이 inventory 필수 입력 없음: $path"
    }
}

$final = Get-Content -Raw -Encoding UTF8 `
    -LiteralPath $commonManifest | ConvertFrom-Json
$commonManifestHash = (
    Get-FileHash -Algorithm SHA256 -LiteralPath $commonManifest
).Hash.ToLowerInvariant()
if (
    $final.status -ne 'success' -or
    [int]$final.counts.g2p_missing -ne 0 -or
    [int]$final.counts.g2p_spn_words -ne 0 -or
    [int]$final.counts.phone_outside_acoustic_inventory -ne 0 -or
    [int]$final.counts.observed_oov_coverage_missing -ne 0
) {
    throw "r2 최종사전 hard gate 실패"
}

$g2pLock = Join-Path $commonRoot "locks\$ReleaseId.lock"
$bulkLock = 'D:\mfa_eojeol\locks\pre_mfa_bulk.lock'
foreach ($path in @($g2pLock, $bulkLock)) {
    if (Test-Path -LiteralPath $path) {
        throw "동시 대량작업 금지 lock 존재: $path"
    }
}

$equivalenceRoot = Join-Path $releaseRoot '03_equivalence'
$outputJson = Join-Path (
    $equivalenceRoot
) 'common_pron_mfa_difference_inventory_2020_2021.json'
$outputCsv = Join-Path (
    $equivalenceRoot
) 'common_pron_mfa_difference_inventory_2020_2021.csv'
$checkpoint = Join-Path (
    $equivalenceRoot
) 'common_pron_mfa_difference_inventory_2020.checkpoint.json'
foreach ($path in @($outputJson, $outputCsv, $checkpoint)) {
    Assert-Child $path $releaseRoot
}
New-Item -ItemType Directory -Force -Path $equivalenceRoot | Out-Null

if (
    (Test-Path -LiteralPath $outputJson) -xor
    (Test-Path -LiteralPath $outputCsv)
) {
    throw (
        "차이 inventory 최종 산출물이 한쪽만 존재함. 덮어쓰지 않음: " +
        "$outputJson / $outputCsv"
    )
}
if (
    (Test-Path -LiteralPath $outputJson) -and
    (Test-Path -LiteralPath $outputCsv)
) {
    $existing = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $outputJson | ConvertFrom-Json
    $csvHash = (
        Get-FileHash -Algorithm SHA256 -LiteralPath $outputCsv
    ).Hash.ToLowerInvariant()
    if (
        $existing.schema_version -ne
            'common_pron_mfa_difference_inventory.v2' -or
        $existing.status -ne 'differences_inventoried' -or
        $existing.gate.difference_inventory_complete -ne $true -or
        [string]$existing.common_release.manifest.sha256 -ne
            $commonManifestHash -or
        [string]$existing.mismatches.csv.sha256 -ne $csvHash
    ) {
        throw "기존 차이 inventory 재검증 실패"
    }
    Say "기존 차이 inventory 완성본 재검증 통과: $outputJson"
    exit 0
}

$lockPath = Join-Path (
    Join-Path $commonRoot 'locks'
) 'common_pron_mfa_difference_inventory.lock'
Acquire-Lock $lockPath $commonRoot
try {
    $logRoot = Join-Path $releaseRoot 'logs'
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
    $logPath = Join-Path $logRoot (
        'difference_inventory_{0}.log' -f
        (Get-Date -Format 'yyyyMMdd_HHmmss')
    )
    Assert-Child $logPath $releaseRoot

    Say (
        "2020·2021 전수 차이 inventory 시작: workers=$Workers, " +
        "batch=$BatchSize, D free=${freeGiB}GiB"
    )
    if (Test-Path -LiteralPath $checkpoint) {
        $saved = Get-Content -Raw -Encoding UTF8 `
            -LiteralPath $checkpoint | ConvertFrom-Json
        Say (
            "checkpoint 발견: status=$($saved.status), " +
            "files=$($saved.counts.textgrid_files)"
        )
    } else {
        Say "새 checkpoint 시작: $checkpoint"
    }

    $env:PYTHONUTF8 = '1'
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $python $driver `
            --common-manifest $commonManifest `
            --vocabulary $vocabulary `
            --textgrid-2020-root $textgrid2020 `
            --qc-2020-report $qc2020 `
            --partial-database-2020 $partialDatabase2020 `
            --database-2021 $database2021 `
            --integrity-2021-report $integrity2021 `
            --output-json $outputJson `
            --output-csv $outputCsv `
            --checkpoint-2020 $checkpoint `
            --workers $Workers `
            --batch-size $BatchSize `
            --mode difference-inventory 2>&1 |
            Tee-Object -FilePath $logPath |
            ForEach-Object { Write-Host $_ }
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0) {
        throw (
            "차이 inventory 실패(exit=$exitCode). checkpoint는 보존됨: " +
            "$checkpoint; log=$logPath"
        )
    }

    $report = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $outputJson | ConvertFrom-Json
    $checkpointReport = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $checkpoint | ConvertFrom-Json
    $csvHash = (
        Get-FileHash -Algorithm SHA256 -LiteralPath $outputCsv
    ).Hash.ToLowerInvariant()
    if (
        $report.schema_version -ne
            'common_pron_mfa_difference_inventory.v2' -or
        $report.status -ne 'differences_inventoried' -or
        $report.gate.difference_inventory_complete -ne $true -or
        $report.gate.allow_yearly_mfa -ne $false -or
        [string]$report.common_release.manifest.sha256 -ne
            $commonManifestHash -or
        [string]$report.mismatches.csv.sha256 -ne $csvHash -or
        $checkpointReport.status -ne 'completed'
    ) {
        throw "차이 inventory 최종 gate 실패"
    }
    Say (
        "차이 inventory 완료: mismatch rows=" +
        "$($report.mismatches.rows); $outputJson"
    )
    Say (
        "아직 adoption·연도별 MFA 승인이 아님. 분류 결과의 연구자 " +
        "검토가 다음 단계"
    )
} finally {
    Release-Lock $lockPath
}
