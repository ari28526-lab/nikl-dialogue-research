#Requires -Version 5.1
<#
현재 2020--2025 r2 생산에 쓰지 않는 D: 산출물을 E:에 항목별 7z로 보존한다.

각 항목은 원본 파일 수/바이트, 모든 SQLite DB SHA-256, 7-Zip CRC 전수 검사,
archive 내부 파일 수/비압축 바이트, archive SHA-256을 통과해야 verified가 된다.
원본 정리는 -PruneAfterVerified와 고정 승인 토큰을 함께 준 경우에만, 그리고
해당 항목이 verified인 직후 exact allowlist 경로에 대해서만 수행한다.

현재 공통사전 r2, 원 WAV/CSV/search master, 2020 복구 코퍼스, 생산 상태·계약은
allowlist에 없으므로 이 스크립트가 건드릴 수 없다.
#>
[CmdletBinding()]
param(
    [ValidateSet('all', 'small', 'textgrid')]
    [string]$Only = 'all',

    [ValidatePattern('^[A-Z]:$')]
    [string]$ArchiveDrive = 'E:',

    [switch]$PruneAfterVerified,

    [switch]$PreflightOnly,

    [string]$ApprovalToken = '',

    [ValidateRange(100, 1000)]
    [int]$MinimumFreeGiB = 200
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class LegacyArchiveSleepGuard {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@

function Enable-LegacyArchiveSleepGuard {
    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED; 화면은 꺼져도 시스템 절전은 막는다.
    $result = [LegacyArchiveSleepGuard]::SetThreadExecutionState(
        [uint32]2147483649
    )
    if ($result -eq 0) {
        throw 'Windows 절전 억제 설정 실패'
    }
}

function Disable-LegacyArchiveSleepGuard {
    # ES_CONTINUOUS만 다시 설정해 정상 전원 정책으로 복원한다.
    [void][LegacyArchiveSleepGuard]::SetThreadExecutionState(
        [uint32]2147483648
    )
}

$requiredToken = 'ARCHIVE_AND_PRUNE_LEGACY_D_20260802'
if ($PruneAfterVerified -and $ApprovalToken -ne $requiredToken) {
    throw 'legacy D: 실제 정리 ApprovalToken 불일치'
}

function Resolve-ExactPath([string]$Path) {
    return [IO.Path]::GetFullPath($Path).TrimEnd('\')
}

function Assert-ExactSource([string]$Path, [string[]]$Allowed) {
    $resolved = Resolve-ExactPath $Path
    $matches = @($Allowed | Where-Object {
        (Resolve-ExactPath $_).Equals(
            $resolved, [StringComparison]::OrdinalIgnoreCase
        )
    })
    if ($matches.Count -ne 1 -or $resolved -in @('D:', 'D:\')) {
        throw "legacy archive 원본 allowlist 위반: $resolved"
    }
    return $resolved
}

function Assert-Child([string]$Path, [string]$Root) {
    $resolved = Resolve-ExactPath $Path
    $prefix = (Resolve-ExactPath $Root) + '\'
    if (-not $resolved.StartsWith(
        $prefix, [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "legacy archive 경로 경계 위반: $resolved"
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

function Get-DatabaseHashes([string]$Path) {
    $records = @()
    foreach ($database in @(
        Get-ChildItem -LiteralPath $Path -File -Recurse -Force `
            -Filter '*.db' -ErrorAction Stop | Sort-Object FullName
    )) {
        $records += [ordered]@{
            relative_path = $database.FullName.Substring(
                $Path.TrimEnd('\').Length + 1
            ).Replace('\', '/')
            bytes = [long]$database.Length
            sha256 = (Get-FileHash -LiteralPath $database.FullName `
                -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    return @($records)
}

function Comparable-Json([object]$Value) {
    return ($Value | ConvertTo-Json -Depth 12 -Compress)
}

function Save-Json([string]$Path, [object]$Value) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temp = "$Path.$PID.partial"
    $Value | ConvertTo-Json -Depth 16 |
        Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $Path -Force
}

function Test-SevenZip([string]$SevenZip, [string]$Archive) {
    $lines = @(& $SevenZip t -bb0 -- $Archive 2>&1)
    $code = $LASTEXITCODE
    $lines | ForEach-Object { Write-Host $_ }
    if ($code -ne 0 -or -not ($lines -match '^Everything is Ok$')) {
        throw "7z CRC 전수 검사 실패(exit=$code): $Archive"
    }
    $filesLine = @($lines | Where-Object { $_ -match '^Files:\s+\d+' })
    $sizeLine = @($lines | Where-Object { $_ -match '^Size:\s+\d+' })
    if ($filesLine.Count -ne 1 -or $sizeLine.Count -ne 1) {
        throw "7z 검사 요약 파싱 실패: $Archive"
    }
    return [ordered]@{
        files = [long]([regex]::Match([string]$filesLine[0], '\d+').Value)
        bytes = [long]([regex]::Match([string]$sizeLine[0], '\d+').Value)
        exit_code = $code
    }
}

$smallItems = @(
    [ordered]@{ key='common_pron_archive'; source='D:\mfa_common_pron\archive'; archive='common_pron_archive.7z'; hash_db=$true },
    [ordered]@{ key='common_pron_archive_obsolete'; source='D:\mfa_common_pron\archive_obsolete'; archive='common_pron_archive_obsolete.7z'; hash_db=$true },
    [ordered]@{ key='common_pron_r1'; source='D:\mfa_common_pron\releases\common_pron_mfa_r1_20260728'; archive='common_pron_mfa_r1_20260728.7z'; hash_db=$true },
    [ordered]@{ key='common_pron_full6y_pilot'; source='D:\mfa_common_pron\releases\common_pron_pilot_full6y_20260728'; archive='common_pron_pilot_full6y_20260728.7z'; hash_db=$true },
    [ordered]@{ key='common_pron_ab_review'; source='D:\mfa_common_pron\REVIEW_AB_6_20260728'; archive='common_pron_REVIEW_AB_6_20260728.7z'; hash_db=$true },
    [ordered]@{ key='mfa_legacy_pilot'; source='D:\mfa_eojeol\pilot'; archive='mfa_eojeol_legacy_pilot.7z'; hash_db=$true },
    [ordered]@{ key='mfa_legacy_pilots'; source='D:\mfa_eojeol\pilots'; archive='mfa_eojeol_legacy_pilots.7z'; hash_db=$true }
)
$textgridItems = @(
    foreach ($year in 2020..2021) {
        [ordered]@{
            key = "legacy_eojeol_$year"
            source = "D:\20_AUDIO\06_textgrid_eojeol\$year"
            archive = "legacy_06_textgrid_eojeol_$year.7z"
            hash_db = $false
        }
    }
    foreach ($year in 2020..2025) {
        [ordered]@{
            key = "legacy_merged_$year"
            source = "D:\20_AUDIO\06_textgrid_merged\$year"
            archive = "legacy_06_textgrid_merged_$year.7z"
            hash_db = $false
        }
    }
)
$allItems = @($smallItems) + @($textgridItems)
$items = switch ($Only) {
    'small' { @($smallItems) }
    'textgrid' { @($textgridItems) }
    default { @($allItems) }
}
$allowedSources = @($allItems | ForEach-Object { [string]$_.source })

$sourceDrive = [IO.DriveInfo]::new('D')
if (-not $sourceDrive.IsReady -or $sourceDrive.VolumeLabel -ne 'DATA_SSD') {
    throw 'D: 메인 드라이브 안전 차단'
}
$archiveInfo = [IO.DriveInfo]::new($ArchiveDrive)
if (-not $archiveInfo.IsReady -or $archiveInfo.DriveFormat -ne 'NTFS') {
    throw "$ArchiveDrive archive 드라이브 안전 차단"
}
$freeGiB = [math]::Round($archiveInfo.AvailableFreeSpace / 1GB, 3)
if ($freeGiB -lt $MinimumFreeGiB) {
    throw "$ArchiveDrive 공간 부족: ${freeGiB}GiB"
}
if (Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -match '^(mfa|python|conda|robocopy|7z|7zG)$'
}) {
    throw 'MFA/Python/conda/robocopy/7z 동시 실행 금지'
}

$sevenZip = @(
    'C:\Program Files\7-Zip\7z.exe',
    'C:\Program Files (x86)\7-Zip\7z.exe'
) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
if ([string]::IsNullOrWhiteSpace([string]$sevenZip)) {
    throw '7-Zip 실행 파일 없음'
}

$archiveRoot = Assert-Child (Join-Path $ArchiveDrive (
    'READ_ONLY_ARCHIVE\2026_summer_research\legacy_d_workspace_20260802'
)) ($ArchiveDrive + '\')
$manifestPath = Join-Path $archiveRoot 'archive_manifest.json'
$repoReport = Join-Path $PSScriptRoot (
    '..\outputs\reports\ARCHIVE_legacy_d_workspace_20260802.json'
)
if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    if ($manifest.schema_version -ne 'legacy_d_workspace_archive.v1') {
        throw '기존 legacy archive manifest schema 불일치'
    }
    if ($manifest.PSObject.Properties['error'] -and
        -not [string]::IsNullOrWhiteSpace([string]$manifest.error)) {
        $history = [Collections.Generic.List[object]]::new()
        if ($manifest.PSObject.Properties['failure_history']) {
            foreach ($oldFailure in @($manifest.failure_history)) {
                $history.Add($oldFailure)
            }
        }
        $history.Add([pscustomobject][ordered]@{
            failed_at = $manifest.failed_at
            error = $manifest.error
        })
        $manifest | Add-Member -NotePropertyName failure_history `
            -NotePropertyValue @($history) -Force
        foreach ($old in @($manifest.items)) {
            if ([string]$old.status -in @(
                'measuring_source','creating_archive','testing_crc'
            )) {
                $old.status = 'failed'
                $old | Add-Member -NotePropertyName failure_reason `
                    -NotePropertyValue ([string]$manifest.error) -Force
            }
        }
        $manifest | Add-Member -NotePropertyName error `
            -NotePropertyValue $null -Force
        $manifest | Add-Member -NotePropertyName failed_at `
            -NotePropertyValue $null -Force
    }
} else {
    $manifest = [pscustomobject][ordered]@{
        schema_version = 'legacy_d_workspace_archive.v1'
        status = 'running'
        started_at = (Get-Date).ToString('o')
        source_drive = 'D: DATA_SSD'
        archive_drive = $ArchiveDrive
        current_production_assets_targeted = $false
        prune_after_verified = [bool]$PruneAfterVerified
        items = @()
    }
}
$preflightRows = @($items | ForEach-Object {
    [pscustomobject][ordered]@{
        key = [string]$_.key
        source = [string]$_.source
        source_exists = Test-Path -LiteralPath ([string]$_.source) `
            -PathType Container
        archive = Join-Path $archiveRoot ([string]$_.archive)
    }
})
if ($PreflightOnly) {
    [pscustomobject][ordered]@{
        status = 'preflight_passed'
        windows_powershell_version = [string]$PSVersionTable.PSVersion
        selection = $Only
        prune_requested = [bool]$PruneAfterVerified
        approval_token_matched = (
            -not $PruneAfterVerified -or $ApprovalToken -eq $requiredToken
        )
        manifest_present = Test-Path -LiteralPath $manifestPath -PathType Leaf
        items = $preflightRows
    } | ConvertTo-Json -Depth 5
    exit 0
}
New-Item -ItemType Directory -Force -Path $archiveRoot | Out-Null
$manifest.status = 'running'
$manifest | Add-Member -NotePropertyName last_resumed_at `
    -NotePropertyValue (Get-Date).ToString('o') -Force
$manifest | Add-Member -NotePropertyName current_selection `
    -NotePropertyValue $Only -Force
Save-Json $manifestPath $manifest
Save-Json $repoReport $manifest

$sleepGuardEnabled = $false
try {
    Enable-LegacyArchiveSleepGuard
    $sleepGuardEnabled = $true
    Write-Host 'Windows system sleep guard: enabled' -ForegroundColor Cyan
    foreach ($item in $items) {
        $source = Assert-ExactSource ([string]$item.source) $allowedSources
        $archive = Assert-Child (Join-Path $archiveRoot ([string]$item.archive)) `
            $archiveRoot
        $prior = @($manifest.items | Where-Object {
            $_.key -eq $item.key -and $_.status -in @('verified','pruned')
        } | Select-Object -Last 1)
        if ($prior.Count -eq 1) {
            if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
                throw "검증 기록의 archive 실물 없음: $archive"
            }
            $hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($hash -ne [string]$prior[0].archive_sha256) {
                throw "검증 기록의 archive SHA 불일치: $archive"
            }
            if ($prior[0].status -eq 'verified' -and $PruneAfterVerified -and
                (Test-Path -LiteralPath $source -PathType Container)) {
                $measure = Get-TreeMeasure $source
                $dbHashes = if ([bool]$prior[0].database_hashing) {
                    Get-DatabaseHashes $source
                } else { @() }
                if ($measure.files -ne [long]$prior[0].source_files -or
                    $measure.bytes -ne [long]$prior[0].source_bytes -or
                    (Comparable-Json $dbHashes) -ne
                        (Comparable-Json @($prior[0].database_sha256))) {
                    throw "verified 이후 원본 변경으로 prune 차단: $source"
                }
                Remove-Item -LiteralPath $source -Recurse -Force
                if (Test-Path -LiteralPath $source) {
                    throw "검증 원본 정리 실패: $source"
                }
                $prior[0].status = 'pruned'
                $prior[0] | Add-Member -NotePropertyName pruned_at `
                    -NotePropertyValue (Get-Date).ToString('o') -Force
            }
            Save-Json $manifestPath $manifest
            Save-Json $repoReport $manifest
            Write-Host "[SKIP] 기존 검증 archive 재사용: $($item.key)"
            continue
        }
        if (-not (Test-Path -LiteralPath $source -PathType Container)) {
            $manifest.items += [pscustomobject][ordered]@{
                key = $item.key; source = $source; archive = $archive
                status = 'source_absent'; observed_at = (Get-Date).ToString('o')
            }
            Save-Json $manifestPath $manifest
            Save-Json $repoReport $manifest
            continue
        }
        $sourceItem = Get-Item -LiteralPath $source -Force
        if (($sourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "archive 원본 root reparse point 금지: $source"
        }
        if (Test-Path -LiteralPath $archive) {
            throw "manifest 없는 최종 archive 덮어쓰기 금지: $archive"
        }
        $partial = "$archive.partial"
        if (Test-Path -LiteralPath $partial) {
            Move-Item -LiteralPath $partial -Destination (
                "$partial.abandoned_" + (Get-Date -Format 'yyyyMMdd_HHmmss')
            )
        }
        $record = [pscustomobject][ordered]@{
            key = $item.key
            source = $source
            archive = $archive
            status = 'measuring_source'
            started_at = (Get-Date).ToString('o')
        }
        $manifest.items += $record
        Save-Json $manifestPath $manifest
        Save-Json $repoReport $manifest

        $before = Get-TreeMeasure $source
        $dbBefore = if ([bool]$item.hash_db) {
            Get-DatabaseHashes $source
        } else { @() }
        $record | Add-Member -NotePropertyName source_files `
            -NotePropertyValue $before.files -Force
        $record | Add-Member -NotePropertyName source_bytes `
            -NotePropertyValue $before.bytes -Force
        $record | Add-Member -NotePropertyName database_sha256 `
            -NotePropertyValue @($dbBefore) -Force
        $record | Add-Member -NotePropertyName database_hashing `
            -NotePropertyValue ([bool]$item.hash_db) -Force
        $record.status = 'creating_archive'
        Save-Json $manifestPath $manifest
        Save-Json $repoReport $manifest

        Push-Location $source
        try {
            & $sevenZip a -t7z -mx=1 -m0=LZMA2 -ms=256m -mmt=on -snl -bb0 -- `
                $partial '.\*'
            $createCode = $LASTEXITCODE
        } finally {
            Pop-Location
        }
        if ($createCode -ne 0) {
            throw "7z 생성 실패(exit=$createCode): $source"
        }
        $record.status = 'testing_crc'
        Save-Json $manifestPath $manifest
        Save-Json $repoReport $manifest
        $archiveMeasure = Test-SevenZip $sevenZip $partial
        if ($before.files -ne $archiveMeasure.files) {
            throw "archive 내부 파일 수 불일치: $source"
        }
        if ($before.bytes -ne $archiveMeasure.bytes) {
            $reparseEntries = @(
                Get-ChildItem -LiteralPath $source -Recurse -Force `
                    -ErrorAction Stop | Where-Object {
                        ($_.Attributes -band
                            [IO.FileAttributes]::ReparsePoint) -ne 0
                    }
            )
            if ($reparseEntries.Count -eq 0 -or
                $archiveMeasure.bytes -lt $before.bytes) {
                throw "archive 내부 바이트 불일치(링크 근거 없음): $source"
            }
            # 7-Zip 기본 동작은 파일 symlink의 대상을 archive 안에 일반 파일
            # 내용으로 보존한다. 따라서 파일 수는 같지만 symlink Length=0인
            # 원본 계수보다 비압축 바이트가 커질 수 있다. 링크 수와 차이를
            # 기록하고 CRC가 통과한 경우에만 허용한다.
            $record | Add-Member -NotePropertyName reparse_entries `
                -NotePropertyValue $reparseEntries.Count -Force
            $record | Add-Member -NotePropertyName symlink_followed_byte_delta `
                -NotePropertyValue (
                    [long]$archiveMeasure.bytes - [long]$before.bytes
                ) -Force
        }
        $archiveHash = (Get-FileHash -LiteralPath $partial `
            -Algorithm SHA256).Hash.ToLowerInvariant()
        Move-Item -LiteralPath $partial -Destination $archive
        $record | Add-Member -NotePropertyName archive_files `
            -NotePropertyValue $archiveMeasure.files -Force
        $record | Add-Member -NotePropertyName archive_uncompressed_bytes `
            -NotePropertyValue $archiveMeasure.bytes -Force
        $record | Add-Member -NotePropertyName archive_bytes `
            -NotePropertyValue ([long](Get-Item -LiteralPath $archive).Length) -Force
        $record | Add-Member -NotePropertyName archive_sha256 `
            -NotePropertyValue $archiveHash -Force
        $record.status = 'verified'
        $record | Add-Member -NotePropertyName verified_at `
            -NotePropertyValue (Get-Date).ToString('o') -Force
        Save-Json $manifestPath $manifest
        Save-Json $repoReport $manifest

        if ($PruneAfterVerified) {
            $source = Assert-ExactSource $source $allowedSources
            Remove-Item -LiteralPath $source -Recurse -Force
            if (Test-Path -LiteralPath $source) {
                throw "검증 원본 정리 실패: $source"
            }
            $record.status = 'pruned'
            $record | Add-Member -NotePropertyName pruned_at `
                -NotePropertyValue (Get-Date).ToString('o') -Force
            Save-Json $manifestPath $manifest
            Save-Json $repoReport $manifest
        }
        Write-Host "[OK] $($item.key): $($record.status)"
    }
    $manifest.status = 'selection_completed'
    $manifest | Add-Member -NotePropertyName last_completed_at `
        -NotePropertyValue (Get-Date).ToString('o') -Force
    Save-Json $manifestPath $manifest
    Save-Json $repoReport $manifest
    Write-Host "[OK] legacy archive selection 완료: $manifestPath"
} catch {
    $manifest.status = 'failed'
    $manifest | Add-Member -NotePropertyName failed_at `
        -NotePropertyValue (Get-Date).ToString('o') -Force
    $manifest | Add-Member -NotePropertyName error `
        -NotePropertyValue $_.Exception.Message -Force
    Save-Json $manifestPath $manifest
    Save-Json $repoReport $manifest
    throw
} finally {
    if ($sleepGuardEnabled) {
        Disable-LegacyArchiveSleepGuard
    }
}
