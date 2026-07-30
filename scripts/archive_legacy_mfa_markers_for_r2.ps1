#Requires -Version 5.1
<#
2020·2021 구 korean_mfa align/merge marker를 r2 전수 재실행 전에 보존
격리한다. lab_input marker는 발음모델과 독립적인 동결 CSV 입력 계약이므로
읽고 기록만 하며 이동하지 않는다.

기본은 dry-run이다. 실제 이동은 -Apply와 고정 ApprovalToken을 함께 줘야
한다. 원시 corpus, TextGrid, DB, lab은 대상이 아니다.
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$ApprovalToken = '',
    [string]$ReportPath = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$expectedMode = 'common_pron_mfa_r2_latest_jamo'
$requiredToken = 'ARCHIVE_LEGACY_MFA_MARKERS_R2_20260730'
$years = @('2020', '2021')
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root 'config\paths.json'
if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $ReportPath = Join-Path $root (
        'outputs\reports\' +
        'ARCHIVE_legacy_mfa_markers_for_r2_20260730.json'
    )
}

function Expand-CfgPath([object]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables(
            ([string]$Value).Replace('/', '\')
        )
    ).TrimEnd('\')
}

function Save-Json([string]$Path, [object]$Payload) {
    $resolved = [IO.Path]::GetFullPath($Path)
    $parent = Split-Path -Parent $resolved
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $partial = "$resolved.$PID.partial"
    $Payload | ConvertTo-Json -Depth 12 |
        Set-Content -LiteralPath $partial -Encoding UTF8
    Move-Item -LiteralPath $partial -Destination $resolved -Force
}

try {
    $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $stateRoot = Expand-CfgPath $cfg.mfa_state
} catch {
    throw "config/paths.json 해석 실패: $($_.Exception.Message)"
}
$expectedStateRoot = 'D:\mfa_eojeol'
if (-not $stateRoot.Equals(
    $expectedStateRoot, [StringComparison]::OrdinalIgnoreCase
)) {
    throw "mfa_state exact root 불일치: $stateRoot"
}
$doneRoot = Join-Path $stateRoot 'done'
$archiveRoot = Join-Path $doneRoot (
    'archive_stale\r2_transition_20260730_legacy_markers'
)

$report = [ordered]@{
    schema_version = 'legacy_mfa_marker_archive.v1'
    status = 'preflight'
    checked_at = (Get-Date).ToString('o')
    apply_requested = [bool]$Apply
    expected_pronunciation_mode = $expectedMode
    policy = [ordered]@{
        exact_done_root = $doneRoot
        exact_years = $years
        align_merge_only = $true
        lab_input_markers_moved = $false
        raw_corpus_modified = $false
        textgrids_modified = $false
        databases_modified = $false
        deletion_used = $false
    }
    marker_records = @()
    lab_input_records = @()
}
$resolvedReport = [IO.Path]::GetFullPath($ReportPath)
Save-Json $resolvedReport $report

try {
    if ($Apply -and $ApprovalToken -ne $requiredToken) {
        throw "실제 marker archive ApprovalToken 불일치"
    }
    $drive = [IO.DriveInfo]::new('D')
    if (-not $drive.IsReady -or $drive.VolumeLabel -ne 'DATA_SSD') {
        throw "D: 메인 드라이브 안전 차단"
    }
    if (-not (Test-Path -LiteralPath $doneRoot -PathType Container)) {
        throw "done root 없음: $doneRoot"
    }
    foreach ($lock in @(
        (Join-Path $stateRoot 'locks\pre_mfa_bulk.lock'),
        (Join-Path $stateRoot 'locks\eojeol_realign.lock'),
        'D:\mfa_common_pron\locks\common_pron_mfa_r2_20260728.lock',
        'D:\mfa_common_pron\locks\common_pron_mfa_difference_inventory.lock'
    )) {
        if (Test-Path -LiteralPath $lock) {
            throw "MFA/G2P lock 존재 — marker 이동 금지: $lock"
        }
    }
    if (
        Get-Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ProcessName -match '^(mfa|python|conda)$'
            }
    ) {
        throw "MFA/Python/conda 실행 중 — marker 이동 금지"
    }

    foreach ($year in $years) {
        $labPath = Join-Path $doneRoot "$year.lab_input_done.json"
        if (-not (Test-Path -LiteralPath $labPath -PathType Leaf)) {
            throw "lab input marker 없음: $labPath"
        }
        $lab = Get-Content -LiteralPath $labPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        if (
            [string]$lab.year -ne $year -or
            [string]$lab.status -ne 'passed' -or
            [string]$lab.lab_input_version -ne
                'eojeol_v3_pron_reference_form'
        ) {
            throw "lab input marker 계약 불일치: $labPath"
        }
        $report.lab_input_records += [ordered]@{
            year = $year
            path = $labPath
            sha256 = (
                Get-FileHash -LiteralPath $labPath -Algorithm SHA256
            ).Hash.ToLowerInvariant()
            action = 'retain_in_place'
        }

        foreach ($stage in @('align', 'merge')) {
            $path = Join-Path $doneRoot "$year.$stage`_done"
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
                throw "예상 legacy marker 없음: $path"
            }
            $marker = Get-Content -LiteralPath $path -Raw -Encoding UTF8 |
                ConvertFrom-Json
            $mode = [string]$marker.g2p_model
            if (
                [string]$marker.year -ne $year -or
                [string]$marker.stage -ne $stage -or
                [string]::IsNullOrWhiteSpace($mode)
            ) {
                throw "marker identity 손상: $path"
            }
            if ($mode -eq $expectedMode) {
                throw "r2 marker는 legacy archive 대상이 아님: $path"
            }
            if ($mode -ne 'korean_mfa') {
                throw "알 수 없는 legacy pronunciation mode: $mode"
            }
            $destination = Join-Path $archiveRoot (
                Split-Path -Leaf $path
            )
            $report.marker_records += [ordered]@{
                year = $year
                stage = $stage
                source = $path
                destination = $destination
                pronunciation_mode = $mode
                sha256 = (
                    Get-FileHash -LiteralPath $path -Algorithm SHA256
                ).Hash.ToLowerInvariant()
                action = $(if ($Apply) {
                    'archive_move'
                } else {
                    'planned_archive_move'
                })
                moved = $false
            }
        }
    }
    if ($report.marker_records.Count -ne 4) {
        throw "legacy marker 수 불일치: $($report.marker_records.Count)"
    }
    $report.status = if ($Apply) {
        'verified_ready_to_archive'
    } else {
        'dry_run_passed'
    }
    Save-Json $resolvedReport $report

    if (-not $Apply) {
        Write-Host "[OK] dry-run; marker move=0; report=$resolvedReport"
        exit 0
    }
    if (Test-Path -LiteralPath $archiveRoot) {
        throw "archive destination이 이미 존재함: $archiveRoot"
    }
    New-Item -ItemType Directory -Path $archiveRoot | Out-Null
    foreach ($record in $report.marker_records) {
        Move-Item -LiteralPath ([string]$record.source) `
            -Destination ([string]$record.destination)
        if (
            (Test-Path -LiteralPath ([string]$record.source)) -or
            -not (Test-Path -LiteralPath (
                [string]$record.destination
            ))
        ) {
            throw "marker archive 이동 검증 실패: $($record.source)"
        }
        $afterHash = (
            Get-FileHash -LiteralPath (
                [string]$record.destination
            ) -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        if ($afterHash -ne [string]$record.sha256) {
            throw "marker archive SHA 불일치: $($record.destination)"
        }
        $record.moved = $true
        $record.moved_at = (Get-Date).ToString('o')
        Save-Json $resolvedReport $report
    }
    $archiveManifest = Join-Path $archiveRoot 'archive_manifest.json'
    $report.status = 'success'
    $report.completed_at = (Get-Date).ToString('o')
    $report.archive_manifest = $archiveManifest
    Save-Json $archiveManifest $report
    Save-Json $resolvedReport $report
    Write-Host "[OK] legacy markers archived: $archiveRoot"
} catch {
    $report.status = 'failed'
    $report.failed_at = (Get-Date).ToString('o')
    $report.error = $_.Exception.Message
    Save-Json $resolvedReport $report
    throw
}
