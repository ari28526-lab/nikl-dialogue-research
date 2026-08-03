#Requires -Version 5.1
<#
2021 새 전수 정렬 전에 활성 위치에 남은 구 실행 상태만 E:로 압축 보관한다.

보존 대상:
- 원본 WAV/CSV
- 기존 .lab 입력(다음 실행에서 다시 전수 검증)
- 2020 완성 TextGrid/DB/승인·Gate B 자료
- 공통발음사전과 morph_search_v3

정리 대상은 아래 exact allowlist의 2021 구 로그·완료표시·낡은 입력계약뿐이다.
기본은 dry-run이며, -Apply와 고정 ApprovalToken을 함께 줘야 실제 보관·정리한다.
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$ApprovalToken = '',
    [string]$ReportPath = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$requiredToken = 'ARCHIVE_PRE_2021_ACTIVE_STATE_20260803'
$projectRoot = [IO.Path]::GetFullPath(
    (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
)
if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $ReportPath = Join-Path $projectRoot (
        'outputs\reports\ARCHIVE_pre_2021_active_state_20260803.json'
    )
}

$stateRoot = 'D:\mfa_eojeol'
$archiveRoot = (
    'E:\READ_ONLY_ARCHIVE\2026_summer_research\' +
    'pre_2021_active_state_20260803'
)
$archivePath = Join-Path $archiveRoot 'pre_2021_active_state_20260803.7z'
$partialArchive = "$archivePath.partial"
$sevenZip = 'C:\Program Files\7-Zip\7z.exe'

$sourcePaths = [Collections.Generic.List[string]]::new()
foreach ($path in @(
    'D:\mfa_eojeol\done\2021.lab_input_done.json',
    'D:\mfa_eojeol\input_contracts\2021.json',
    'D:\mfa_eojeol\logs\direct_db_export_2021_eojeol_g2p_2021_20260727_082721.json',
    'D:\mfa_eojeol\logs\lab_2021_post_mfa_inventory_20260728_heartbeat.jsonl',
    'D:\mfa_eojeol\logs\lab_build_2021_ef22e9b38901_unresolved_symbols.csv',
    'D:\mfa_eojeol\logs\lab_build_2021_latest.json',
    'D:\mfa_eojeol\logs\mfa_2021_eojeol_g2p_2021_20260727_082721_heartbeat.jsonl',
    'D:\mfa_eojeol\logs\mfa_2021_stderr.log',
    'D:\mfa_eojeol\logs\mfa_2021_stderr.log.prev'
)) {
    $sourcePaths.Add($path)
}

$emptyPartialRoot = (
    'D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\_partial_direct_db'
)
$emptyPartialContract = Join-Path $emptyPartialRoot (
    'ef22e9b38901a3dd0797cd9664cd72c1d04f496e2ad775cbd9b5f3f99292c3fe'
)
$retainedLabRoot = 'D:\20_AUDIO\03_wav\individual\2021'
$protectedPaths = @(
    'D:\20_AUDIO\08_textgrid_research_v2_staging\2020',
    'D:\mfa_tmp\2020\2020.db',
    (Join-Path $projectRoot 'outputs\reports\GATE_B_2020_TO_2021.json')
)
$legacyMarkerPaths = @(
    'D:\mfa_eojeol\done\archive_stale\r2_transition_20260730_legacy_markers\2021.align_done',
    'D:\mfa_eojeol\done\archive_stale\r2_transition_20260730_legacy_markers\2021.merge_done'
)

function Save-Json([string]$Path, [object]$Payload) {
    $resolved = [IO.Path]::GetFullPath($Path)
    $parent = Split-Path -Parent $resolved
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $partial = "$resolved.$PID.partial"
    $Payload | ConvertTo-Json -Depth 12 |
        Set-Content -LiteralPath $partial -Encoding UTF8
    Move-Item -LiteralPath $partial -Destination $resolved -Force
}

function Assert-SafeTemp([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $tempBase = [IO.Path]::GetFullPath(
        [IO.Path]::GetTempPath()
    ).TrimEnd('\')
    if (-not $resolved.StartsWith(
        "$tempBase\pre_2021_state_",
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "임시폴더 안전범위 불일치: $resolved"
    }
}

$fileRecords = [Collections.Generic.List[object]]::new()
$legacyRecords = [Collections.Generic.List[object]]::new()
$report = [ordered]@{
    schema_version = 'pre_2021_active_state_archive.v1'
    status = 'preflight'
    checked_at = (Get-Date).ToString('o')
    apply_requested = [bool]$Apply
    scope = 'legacy_active_state_for_2021_only'
    archive_root = $archiveRoot
    archive_path = $archivePath
    policy = [ordered]@{
        source_allowlist_count = $sourcePaths.Count
        raw_wav_modified = $false
        csv_modified = $false
        retained_lab_inputs_modified = $false
        common_pronunciation_modified = $false
        morph_search_v3_modified = $false
        production_2020_modified = $false
        legacy_2021_active_files_removed_after_verified_archive = [bool]$Apply
    }
    retained_lab_root = $retainedLabRoot
    protected_paths = $protectedPaths
    source_files = $fileRecords
    previously_archived_legacy_markers = $legacyRecords
    empty_partial_contract = [ordered]@{
        path = $emptyPartialContract
        exists = $false
        file_count = 0
        action = 'none'
    }
}

$stageRoot = Join-Path ([IO.Path]::GetTempPath()) (
    'pre_2021_state_' + [guid]::NewGuid().ToString('N')
)

try {
    if ($Apply -and $ApprovalToken -ne $requiredToken) {
        throw '실제 보관 ApprovalToken 불일치'
    }
    foreach ($driveLetter in @('D', 'E')) {
        $drive = [IO.DriveInfo]::new($driveLetter)
        if (-not $drive.IsReady) {
            throw "$driveLetter`: 드라이브가 준비되지 않음"
        }
    }
    if ([IO.DriveInfo]::new('D').VolumeLabel -ne 'DATA_SSD') {
        throw 'D: 메인 드라이브 안전 차단'
    }
    if (-not (Test-Path -LiteralPath $sevenZip -PathType Leaf)) {
        throw "7-Zip 실행파일 없음: $sevenZip"
    }
    foreach ($path in $protectedPaths) {
        if (-not (Test-Path -LiteralPath $path)) {
            throw "2020 보호 자산 없음: $path"
        }
    }
    if (-not (Test-Path -LiteralPath $retainedLabRoot -PathType Container)) {
        throw "2021 재사용 LAB root 없음: $retainedLabRoot"
    }
    foreach ($lock in @(
        'D:\mfa_eojeol\locks\pre_mfa_bulk.lock',
        'D:\mfa_eojeol\locks\eojeol_realign.lock',
        'D:\mfa_common_pron\locks\common_pron_mfa_r2_20260728.lock'
    )) {
        if (Test-Path -LiteralPath $lock) {
            throw "MFA/G2P lock 존재: $lock"
        }
    }
    if (
        Get-Process -ErrorAction SilentlyContinue |
            Where-Object { $_.ProcessName -match '^(mfa|python|conda)$' }
    ) {
        throw 'MFA/Python/conda 실행 중 — archive 금지'
    }

    foreach ($path in $sourcePaths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "allowlist source 없음: $path"
        }
        $item = Get-Item -LiteralPath $path
        $relative = $item.FullName.Substring($stateRoot.Length).TrimStart('\')
        $fileRecords.Add([pscustomobject][ordered]@{
            source = $item.FullName
            relative_path = "mfa_eojeol\$relative"
            bytes = [long]$item.Length
            mtime = $item.LastWriteTime.ToString('o')
            sha256 = (
                Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256
            ).Hash.ToLowerInvariant()
            action = $(if ($Apply) {
                'archive_then_remove_active_copy'
            } else {
                'planned_archive_then_remove_active_copy'
            })
        })
    }
    foreach ($path in $legacyMarkerPaths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "기존 legacy marker archive 없음: $path"
        }
        $item = Get-Item -LiteralPath $path
        $legacyRecords.Add([pscustomobject][ordered]@{
            path = $item.FullName
            bytes = [long]$item.Length
            sha256 = (
                Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256
            ).Hash.ToLowerInvariant()
            action = 'retain_existing_archive_in_place'
        })
    }

    if (Test-Path -LiteralPath $emptyPartialContract) {
        $partialFiles = @(
            Get-ChildItem -LiteralPath $emptyPartialContract -Recurse -File
        )
        if ($partialFiles.Count -ne 0) {
            throw "구 partial contract가 비어 있지 않음: $emptyPartialContract"
        }
        $report.empty_partial_contract.exists = $true
        $report.empty_partial_contract.action = $(if ($Apply) {
            'remove_empty_directory_after_archive'
        } else {
            'planned_remove_empty_directory_after_archive'
        })
    }
    $report.status = 'dry_run_passed'
    Save-Json $ReportPath $report
    if (-not $Apply) {
        Write-Host (
            '[OK] dry-run: files={0}, bytes={1}, 2020 protected, LAB retained' -f
            $fileRecords.Count,
            (($fileRecords | Measure-Object -Property bytes -Sum).Sum)
        )
        Write-Host "report: $ReportPath"
        exit 0
    }

    if (Test-Path -LiteralPath $archiveRoot) {
        throw "archive destination이 이미 존재함: $archiveRoot"
    }
    Assert-SafeTemp $stageRoot
    New-Item -ItemType Directory -Path $stageRoot | Out-Null
    foreach ($record in $fileRecords) {
        $destination = Join-Path $stageRoot ([string]$record.relative_path)
        New-Item -ItemType Directory -Force -Path (
            Split-Path -Parent $destination
        ) | Out-Null
        Copy-Item -LiteralPath ([string]$record.source) -Destination $destination
        $stagedHash = (
            Get-FileHash -LiteralPath $destination -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        if ($stagedHash -ne [string]$record.sha256) {
            throw "staging SHA 불일치: $destination"
        }
    }
    $embeddedManifest = Join-Path $stageRoot 'archive_inventory.json'
    $report.status = 'staged_verified'
    Save-Json $embeddedManifest $report

    New-Item -ItemType Directory -Path $archiveRoot | Out-Null
    & $sevenZip a -t7z -mx=9 -mmt=on -- $partialArchive "$stageRoot\*"
    if ($LASTEXITCODE -ne 0) {
        throw "7-Zip archive 실패(exit=$LASTEXITCODE)"
    }
    & $sevenZip t -- $partialArchive
    if ($LASTEXITCODE -ne 0) {
        throw "7-Zip test 실패(exit=$LASTEXITCODE)"
    }
    Move-Item -LiteralPath $partialArchive -Destination $archivePath
    $report.archive_bytes = (Get-Item -LiteralPath $archivePath).Length
    $report.archive_sha256 = (
        Get-FileHash -LiteralPath $archivePath -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    $report.archive_test = 'passed'

    foreach ($record in $fileRecords) {
        Remove-Item -LiteralPath ([string]$record.source)
        if (Test-Path -LiteralPath ([string]$record.source)) {
            throw "active source 정리 실패: $($record.source)"
        }
    }
    if ($report.empty_partial_contract.exists) {
        Remove-Item -LiteralPath $emptyPartialContract
        if (Test-Path -LiteralPath $emptyPartialContract) {
            throw "빈 partial contract 정리 실패: $emptyPartialContract"
        }
        if (
            (Test-Path -LiteralPath $emptyPartialRoot) -and
            @(Get-ChildItem -LiteralPath $emptyPartialRoot -Force).Count -eq 0
        ) {
            Remove-Item -LiteralPath $emptyPartialRoot
        }
    }
    foreach ($path in $protectedPaths) {
        if (-not (Test-Path -LiteralPath $path)) {
            throw "사후 2020 보호 자산 없음: $path"
        }
    }
    if (-not (Test-Path -LiteralPath $retainedLabRoot -PathType Container)) {
        throw '사후 2021 LAB root 없음'
    }
    $report.status = 'success'
    $report.completed_at = (Get-Date).ToString('o')
    $report.active_sources_remaining = @(
        $sourcePaths | Where-Object { Test-Path -LiteralPath $_ }
    ).Count
    $report.production_2020_rechecked = $true
    Save-Json (Join-Path $archiveRoot 'archive_manifest.json') $report
    Save-Json $ReportPath $report
    Write-Host (
        '[OK] 2021 구 활성상태 archive 완료: files={0}, archive={1}' -f
        $fileRecords.Count,
        $archivePath
    )
    Write-Host '[OK] 2020 완성본·원본 WAV/CSV·LAB·공통사전·검색표 변경 없음'
} catch {
    $report.status = 'failed'
    $report.failed_at = (Get-Date).ToString('o')
    $report.error = $_.Exception.Message
    Save-Json $ReportPath $report
    throw
} finally {
    if (Test-Path -LiteralPath $stageRoot) {
        Assert-SafeTemp $stageRoot
        Remove-Item -LiteralPath $stageRoot -Recurse -Force
    }
}
