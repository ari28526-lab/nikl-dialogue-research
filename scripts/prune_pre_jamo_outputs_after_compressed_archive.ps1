#Requires -Version 5.1
<#
검증된 E: pre-Jamo 압축 archive를 근거로 정확한 D: 구결과만 정리한다.

기본 실행은 검증 보고서만 만들며 삭제하지 않는다. 실제 삭제는 -Apply와
고정 ApprovalToken을 함께 줄 때만 가능하다. 삭제 전에 모든 archive SHA,
모든 D: 원본의 파일 수·총바이트와 DB SHA를 전수 재검증한다.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Z]:$')]
    [string]$ArchiveDrive = 'E:',

    [switch]$Apply,

    [string]$ApprovalToken = '',

    [string]$ReportPath = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $ReportPath = Join-Path $PSScriptRoot (
        '..\outputs\reports\' +
        'PRUNE_pre_jamo_after_compressed_archive_20260730.json'
    )
}

$requiredApprovalToken = 'DELETE_VERIFIED_PRE_JAMO_20260730'
$allowedSources = [ordered]@{
    textgrid_2020 = (
        'D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2020'
    )
    textgrid_2021 = (
        'D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2021'
    )
    mfa_temp_2021 = 'D:\mfa_tmp\2021'
    mfa_stale_temp = 'D:\mfa_eojeol\archive_stale_temp'
    failed_model_clone = (
        'D:\mfa_common_pron\models\' +
        'official_hf_korean_mfa_v3.3.0_20260728'
    )
}
$archiveNames = [ordered]@{
    textgrid_2020 = 'textgrid_baseline_pre_jamo_2020.7z'
    textgrid_2021 = 'textgrid_baseline_pre_jamo_2021.7z'
    mfa_temp_2021 = 'mfa_temp_baseline_pre_jamo_2021.7z'
    mfa_stale_temp = 'mfa_stale_temp_pre_jamo.7z'
    failed_model_clone = 'hf_clone_crlf_failure.7z'
}

function Resolve-ExactPath([string]$Path) {
    return [IO.Path]::GetFullPath($Path).TrimEnd('\')
}

function Assert-ExactSource([string]$Path, [string]$Expected) {
    $resolved = Resolve-ExactPath $Path
    $allowed = Resolve-ExactPath $Expected
    if (-not $resolved.Equals(
        $allowed, [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "정리 원본 allowlist 위반: $resolved"
    }
    if ($resolved -in @('D:', 'D:\')) {
        throw "드라이브 루트 정리 금지"
    }
    return $resolved
}

function Assert-ExactArchive(
    [string]$Path,
    [string]$Expected,
    [string]$Root
) {
    $resolved = Resolve-ExactPath $Path
    $allowed = Resolve-ExactPath $Expected
    $rootPrefix = (Resolve-ExactPath $Root) + '\'
    if (
        -not $resolved.Equals(
            $allowed, [StringComparison]::OrdinalIgnoreCase
        ) -or
        -not $resolved.StartsWith(
            $rootPrefix, [StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw "archive allowlist 위반: $resolved"
    }
    return $resolved
}

function Get-TreeMeasure([string]$Path) {
    $measure = Get-ChildItem -LiteralPath $Path -File -Recurse -Force `
        -ErrorAction Stop | Measure-Object -Property Length -Sum
    return [ordered]@{
        files = [long]$measure.Count
        bytes = [long]$measure.Sum
    }
}

function Get-AllDatabaseHashes([string]$Path) {
    $records = @()
    foreach ($database in @(
        Get-ChildItem -LiteralPath $Path -File -Recurse -Force `
            -Filter '*.db' -ErrorAction Stop |
            Sort-Object FullName
    )) {
        $records += [ordered]@{
            relative_path = $database.FullName.Substring(
                $Path.TrimEnd('\').Length + 1
            ).Replace('\', '/')
            bytes = [long]$database.Length
            sha256 = (
                Get-FileHash -LiteralPath $database.FullName `
                    -Algorithm SHA256
            ).Hash.ToLowerInvariant()
        }
    }
    return @($records)
}

function Convert-ComparableJson([object]$Value) {
    return ($Value | ConvertTo-Json -Depth 12 -Compress)
}

function Save-Report([string]$Path, [object]$Payload) {
    $resolved = [IO.Path]::GetFullPath($Path)
    $parent = Split-Path -Parent $resolved
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temp = "$resolved.$PID.partial"
    $Payload | ConvertTo-Json -Depth 16 |
        Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $resolved -Force
}

$report = [ordered]@{
    schema_version = 'pre_jamo_compressed_prune.v1'
    status = 'preflight'
    started_at = (Get-Date).ToString('o')
    apply_requested = [bool]$Apply
    deletion_performed = $false
    approval = [ordered]@{
        explicit_user_approval_recorded_at = '2026-07-30'
        required_token_matched = (
            $Apply -and $ApprovalToken -eq $requiredApprovalToken
        )
    }
    policy = [ordered]@{
        archive_must_be_success = $true
        all_archives_rehashed_before_delete = $true
        all_sources_remeasured_before_delete = $true
        all_database_hashes_rechecked_before_delete = $true
        exact_source_allowlist_only = $true
        raw_corpus_targeted = $false
    }
    items = @()
}
$resolvedReportPath = [IO.Path]::GetFullPath($ReportPath)
Save-Report $resolvedReportPath $report

try {
    if ($Apply -and $ApprovalToken -ne $requiredApprovalToken) {
        throw "실제 정리 ApprovalToken 불일치"
    }
    $sourceDrive = [IO.DriveInfo]::new('D')
    if (
        -not $sourceDrive.IsReady -or
        $sourceDrive.VolumeLabel -ne 'DATA_SSD'
    ) {
        throw "D: 메인 드라이브 안전 차단"
    }
    $archiveInfo = [IO.DriveInfo]::new($ArchiveDrive)
    if (
        -not $archiveInfo.IsReady -or
        $archiveInfo.DriveFormat -ne 'NTFS'
    ) {
        throw "$ArchiveDrive archive 드라이브 안전 차단"
    }
    if (
        Get-Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ProcessName -match (
                    '^(mfa|python|conda|robocopy|7z)$'
                )
            }
    ) {
        throw "MFA/Python/conda/robocopy/7z 동시 실행 금지"
    }

    $archiveRoot = Resolve-ExactPath (
        Join-Path $ArchiveDrive (
            'READ_ONLY_ARCHIVE\2026_summer_research\' +
            'pre_jamo_compressed_20260728'
        )
    )
    $manifestPath = Join-Path $archiveRoot 'archive_manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "compressed archive manifest 없음"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw `
        -Encoding UTF8 | ConvertFrom-Json
    if (
        $manifest.schema_version -ne
            'pre_jamo_compressed_external_archive.v1' -or
        $manifest.status -ne 'success'
    ) {
        throw "compressed archive manifest 성공 gate 실패"
    }

    $verifiedItems = @()
    foreach ($key in $allowedSources.Keys) {
        $expectedSource = [string]$allowedSources[$key]
        $expectedArchive = Join-Path $archiveRoot (
            [string]$archiveNames[$key]
        )
        $matches = @($manifest.items | Where-Object {
            $_.key -eq $key -and $_.status -eq 'verified'
        })
        if ($matches.Count -ne 1) {
            throw "verified archive 레코드 수 불일치: $key"
        }
        $manifestItem = $matches[0]
        $source = Assert-ExactSource (
            [string]$manifestItem.source
        ) $expectedSource
        $archive = Assert-ExactArchive (
            [string]$manifestItem.archive
        ) $expectedArchive $archiveRoot
        if (-not (Test-Path -LiteralPath $source -PathType Container)) {
            throw "정리 원본 없음: $source"
        }
        $sourceItem = Get-Item -LiteralPath $source -Force
        if (
            ($sourceItem.Attributes -band
                [IO.FileAttributes]::ReparsePoint) -ne 0
        ) {
            throw "정리 원본 reparse point 금지: $source"
        }
        if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
            throw "검증 archive 실물 없음: $archive"
        }

        Write-Host "[VERIFY] archive SHA: $key"
        $archiveHash = (
            Get-FileHash -LiteralPath $archive -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        if ($archiveHash -ne [string]$manifestItem.archive_sha256) {
            throw "archive SHA256 불일치: $archive"
        }

        Write-Host "[VERIFY] source count/bytes: $key"
        $measure = Get-TreeMeasure $source
        if (
            $measure.files -ne [long]$manifestItem.source_files -or
            $measure.bytes -ne [long]$manifestItem.source_bytes
        ) {
            throw "archive 이후 D: 원본 수량/바이트 변경: $source"
        }
        Write-Host "[VERIFY] source DB SHA: $key"
        $databaseHashes = Get-AllDatabaseHashes $source
        $manifestDatabaseHashes = @()
        if ($manifestItem.PSObject.Properties['database_sha256']) {
            $manifestDatabaseHashes = @(
                $manifestItem.database_sha256
            )
        }
        if (
            (Convert-ComparableJson $databaseHashes) -ne
            (Convert-ComparableJson $manifestDatabaseHashes)
        ) {
            throw "archive 이후 D: DB SHA 변경: $source"
        }

        $record = [ordered]@{
            key = $key
            source = $source
            archive = $archive
            source_files = $measure.files
            source_bytes = $measure.bytes
            archive_bytes = [long](Get-Item -LiteralPath $archive).Length
            archive_sha256 = $archiveHash
            database_sha256 = $databaseHashes
            pre_delete_verified = $true
            removed = $false
        }
        $report.items += $record
        $verifiedItems += $record
        Save-Report $resolvedReportPath $report
    }

    $totalFiles = [long](
        $verifiedItems |
            ForEach-Object { [long]$_['source_files'] } |
            Measure-Object -Sum
    ).Sum
    $totalBytes = [long](
        $verifiedItems |
            ForEach-Object { [long]$_['source_bytes'] } |
            Measure-Object -Sum
    ).Sum
    $report.status = if ($Apply) {
        'all_items_verified_ready_to_prune'
    } else {
        'ready_for_explicit_apply'
    }
    $report.summary = [ordered]@{
        items = $verifiedItems.Count
        files = $totalFiles
        bytes = $totalBytes
        expected_reclaim_gib = [math]::Round(
            $totalBytes / 1GB,
            3
        )
    }
    Save-Report $resolvedReportPath $report

    if (-not $Apply) {
        Write-Host (
            "[OK] dry-run only; deletion=0; report=$resolvedReportPath"
        )
        exit 0
    }

    foreach ($record in $verifiedItems) {
        $source = Assert-ExactSource (
            [string]$record.source
        ) ([string]$allowedSources[$record.key])
        Write-Host "[DELETE] verified pre-Jamo source: $source"
        Remove-Item -LiteralPath $source -Recurse -Force
        if (Test-Path -LiteralPath $source) {
            throw "검증된 D: 원본 삭제 실패: $source"
        }
        $record.removed = $true
        $record.removed_at = (Get-Date).ToString('o')
        $report.deletion_performed = $true
        Save-Report $resolvedReportPath $report
    }

    $report.status = 'success'
    $report.completed_at = (Get-Date).ToString('o')
    $report.drive_free_bytes_after = [long](
        [IO.DriveInfo]::new('D').AvailableFreeSpace
    )
    Save-Report $resolvedReportPath $report
    Write-Host "[OK] verified pre-Jamo D: prune: $resolvedReportPath"
} catch {
    $report.status = 'failed'
    $report.failed_at = (Get-Date).ToString('o')
    $report.error = $_.Exception.Message
    Save-Report $resolvedReportPath $report
    throw
}
