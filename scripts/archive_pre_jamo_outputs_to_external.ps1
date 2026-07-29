#Requires -Version 5.1
<#
Jamo 최신 기준으로 재실행하기 전의 대용량 산출물을 외장 HDD에 보존한다.

D:는 메인 작업 드라이브다. E:는 이 스크립트가 만든 READ_ONLY_ARCHIVE의
구결과 보존에만 쓰며, 새 MFA 실행 입력·출력 경로로 사용하지 않는다.
기본 실행은 복사와 검증만 한다. -PruneAfterVerify는 각 대상의 robocopy
zero-diff, 파일 수, 총 바이트 검증을 모두 통과한 뒤에만 명시적 D: 원본을
삭제한다.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Z]:$')]
    [string]$ArchiveDrive = 'E:',

    [ValidateRange(100, 1000)]
    [int]$MinimumFreeGiB = 100,

    [switch]$PruneAfterVerify
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

throw (
    "사용 중단된 loose-file archive 스크립트입니다. 수백만 작은 " +
    "파일을 낱개 복사하지 말고 " +
    "scripts\archive_pre_jamo_outputs_compressed.ps1을 사용하십시오."
)

function Assert-ExactSource([string]$Path, [string[]]$Allowed) {
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $matches = @($Allowed | Where-Object {
        [IO.Path]::GetFullPath($_).TrimEnd('\').Equals(
            $resolved, [StringComparison]::OrdinalIgnoreCase
        )
    })
    if ($matches.Count -ne 1) {
        throw "archive 원본 allowlist 위반: $resolved"
    }
    return $resolved
}

function Assert-Child([string]$Path, [string]$Root) {
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $allowed = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith(
        $allowed, [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "archive 경로 경계 위반: $resolved (root=$Root)"
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

function Save-Manifest([string]$Path, [hashtable]$Payload) {
    $temp = "$Path.$PID.partial"
    $Payload | ConvertTo-Json -Depth 12 |
        Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $Path -Force
}

$sourceDrive = [IO.DriveInfo]::new('D')
if (-not $sourceDrive.IsReady -or $sourceDrive.VolumeLabel -ne 'DATA_SSD') {
    throw (
        "D: 메인 드라이브 안전 차단: ready=$($sourceDrive.IsReady), " +
        "label=$($sourceDrive.VolumeLabel)"
    )
}
$archiveInfo = [IO.DriveInfo]::new($ArchiveDrive)
if (-not $archiveInfo.IsReady -or $archiveInfo.DriveFormat -ne 'NTFS') {
    throw (
        "$ArchiveDrive archive 안전 차단: ready=$($archiveInfo.IsReady), " +
        "format=$($archiveInfo.DriveFormat)"
    )
}
$freeGiB = [math]::Round($archiveInfo.AvailableFreeSpace / 1GB, 3)
if ($freeGiB -lt $MinimumFreeGiB) {
    throw "$ArchiveDrive 공간 부족: ${freeGiB}GiB < ${MinimumFreeGiB}GiB"
}
if (
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessName -match '^(mfa|python|conda)$' }
) {
    throw "MFA/Python/conda 실행 중 — archive·prune 동시 실행 금지"
}

$allowedSources = @(
    'D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2020',
    'D:\20_AUDIO\07_textgrid_eojeol_g2p_staging\2021',
    'D:\mfa_tmp\2021',
    'D:\mfa_eojeol\archive_stale_temp',
    'D:\mfa_common_pron\models\official_hf_korean_mfa_v3.3.0_20260728'
)
$items = @(
    [ordered]@{
        source = $allowedSources[0]
        relative_destination = 'textgrid_baseline_pre_jamo\2020'
        reason = '2020 old acoustic/syllable-G2P baseline'
    },
    [ordered]@{
        source = $allowedSources[1]
        relative_destination = 'textgrid_baseline_pre_jamo\2021'
        reason = '2021 old acoustic/syllable-G2P baseline'
    },
    [ordered]@{
        source = $allowedSources[2]
        relative_destination = 'mfa_temp_baseline_pre_jamo\2021'
        reason = '2021 DB and reproducibility cache'
    },
    [ordered]@{
        source = $allowedSources[3]
        relative_destination = 'mfa_stale_temp_pre_jamo'
        reason = 'preserved stale MFA temp evidence'
    },
    [ordered]@{
        source = $allowedSources[4]
        relative_destination = 'model_failures\hf_clone_crlf_failure'
        reason = 'first latest-model clone rejected by OpenFST due CRLF'
    }
)

$archiveRoot = Join-Path $ArchiveDrive (
    'READ_ONLY_ARCHIVE\2026_summer_research\pre_jamo_20260728'
)
$archiveRoot = Assert-Child $archiveRoot ($ArchiveDrive + '\')
New-Item -ItemType Directory -Force -Path $archiveRoot | Out-Null
$logPath = Join-Path $archiveRoot 'robocopy.log'
$manifestPath = Join-Path $archiveRoot 'archive_manifest.json'
$readmePath = Join-Path $archiveRoot 'ARCHIVE_README.txt'
@"
This directory preserves pre-Jamo MFA outputs and failed setup evidence.
D:\ remains the only main working drive.
Do not use this E:\ archive as an MFA input or output root.
See archive_manifest.json for source paths and verification results.
"@ | Set-Content -LiteralPath $readmePath -Encoding UTF8

$manifest = [ordered]@{
    schema_version = 'pre_jamo_external_archive.v1'
    status = 'running'
    started_at = (Get-Date).ToString('o')
    source_drive = [ordered]@{
        name = $sourceDrive.Name
        label = $sourceDrive.VolumeLabel
    }
    archive_drive = [ordered]@{
        name = $archiveInfo.Name
        label = $archiveInfo.VolumeLabel
        total_bytes = [long]$archiveInfo.TotalSize
        free_bytes_before = [long]$archiveInfo.AvailableFreeSpace
    }
    policy = [ordered]@{
        d_is_main = $true
        archive_is_not_execution_root = $true
        prune_requested = [bool]$PruneAfterVerify
        verification = 'robocopy zero-diff plus file-count and byte-count'
    }
    items = @()
}
Save-Manifest $manifestPath $manifest

foreach ($item in $items) {
    $source = Assert-ExactSource ([string]$item.source) $allowedSources
    if (-not (Test-Path -LiteralPath $source -PathType Container)) {
        $manifest.items += [ordered]@{
            source = $source
            status = 'source_absent'
            reason = $item.reason
        }
        Save-Manifest $manifestPath $manifest
        continue
    }
    $destination = Join-Path $archiveRoot (
        [string]$item.relative_destination
    )
    $destination = Assert-Child $destination $archiveRoot
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    $before = Get-TreeMeasure $source

    & robocopy.exe $source $destination /E /COPY:DAT /DCOPY:DAT /R:2 /W:2 `
        /MT:16 /XJ /NP /TEE "/LOG+:$logPath"
    $copyCode = $LASTEXITCODE
    if ($copyCode -ge 8) {
        throw "robocopy 실패(exit=$copyCode): $source"
    }

    $after = Get-TreeMeasure $destination
    if (
        $before.files -ne $after.files -or
        $before.bytes -ne $after.bytes
    ) {
        throw "archive count/byte 불일치: $source -> $destination"
    }
    & robocopy.exe $source $destination /E /L /COPY:DAT /DCOPY:DAT `
        /R:0 /W:0 /XJ /NJH /NJS /NP
    $diffCode = $LASTEXITCODE
    if ($diffCode -ne 0) {
        throw "archive zero-diff 실패(exit=$diffCode): $source"
    }

    $dbSource = Join-Path $source '2021.db'
    $dbDestination = Join-Path $destination '2021.db'
    $dbHash = $null
    if (Test-Path -LiteralPath $dbSource -PathType Leaf) {
        $sourceHash = (
            Get-FileHash -LiteralPath $dbSource -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        $destinationHash = (
            Get-FileHash -LiteralPath $dbDestination -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        if ($sourceHash -ne $destinationHash) {
            throw "2021.db SHA256 불일치"
        }
        $dbHash = $sourceHash
    }

    $record = [ordered]@{
        source = $source
        destination = $destination
        reason = $item.reason
        source_files = $before.files
        source_bytes = $before.bytes
        destination_files = $after.files
        destination_bytes = $after.bytes
        robocopy_copy_exit = $copyCode
        robocopy_zero_diff_exit = $diffCode
        database_sha256 = $dbHash
        verified_at = (Get-Date).ToString('o')
        source_removed = $false
        status = 'verified'
    }
    if ($PruneAfterVerify) {
        $confirmed = Assert-ExactSource $source $allowedSources
        Remove-Item -LiteralPath $confirmed -Recurse -Force
        if (Test-Path -LiteralPath $confirmed) {
            throw "검증 후 D: 원본 제거 실패: $confirmed"
        }
        $record.source_removed = $true
        $record.status = 'verified_and_pruned'
    }
    $manifest.items += $record
    Save-Manifest $manifestPath $manifest
}

$manifest.status = 'success'
$manifest.completed_at = (Get-Date).ToString('o')
$manifest.archive_drive.free_bytes_after = [long](
    [IO.DriveInfo]::new($ArchiveDrive).AvailableFreeSpace
)
Save-Manifest $manifestPath $manifest
Write-Host "[OK] pre-Jamo external archive: $manifestPath"
