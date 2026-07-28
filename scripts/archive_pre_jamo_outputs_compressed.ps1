#Requires -Version 5.1
<#
구 MFA 산출물을 E:에 항목별 7z archive로 보존한다.

D:는 메인 작업 드라이브이며 원본은 읽기 전용이다. 이 스크립트는 원본
삭제 기능을 제공하지 않는다. 7-Zip CRC 전수 검사, 원본/압축본 파일 수와
비압축 바이트 합계, 트리 내 모든 *.db의 실행 전후 SHA256, 완성 archive
SHA256을 통과한 항목만 verified로 기록한다.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Z]:$')]
    [string]$ArchiveDrive = 'E:',

    [ValidateRange(100, 1000)]
    [int]$MinimumFreeGiB = 100,

    [ValidateSet(
        'all',
        'textgrid_2020',
        'textgrid_2021',
        'mfa_temp_2021',
        'mfa_stale_temp',
        'failed_model_clone'
    )]
    [string]$Only = 'all'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-ExactSource([string]$Path, [string[]]$Allowed) {
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $matches = @($Allowed | Where-Object {
        [IO.Path]::GetFullPath($_).TrimEnd('\').Equals(
            $resolved, [StringComparison]::OrdinalIgnoreCase
        )
    })
    if ($matches.Count -ne 1) {
        throw "compressed archive 원본 allowlist 위반: $resolved"
    }
    return $resolved
}

function Assert-Child([string]$Path, [string]$Root) {
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith(
        $prefix, [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "compressed archive 경로 경계 위반: $resolved"
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

function Save-Manifest([string]$Path, $Payload) {
    $temp = "$Path.$PID.partial"
    $Payload | ConvertTo-Json -Depth 12 |
        Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $Path -Force
}

function Test-SevenZipArchive(
    [string]$SevenZip,
    [string]$ArchivePath
) {
    $lines = @(& $SevenZip t -bb0 -- $ArchivePath 2>&1)
    $code = $LASTEXITCODE
    $lines | ForEach-Object { Write-Host $_ }
    if ($code -ne 0 -or -not ($lines -match '^Everything is Ok$')) {
        throw "7z CRC 전수 검사 실패(exit=$code): $ArchivePath"
    }
    $filesLine = @($lines | Where-Object { $_ -match '^Files:\s+\d+' })
    $sizeLine = @($lines | Where-Object { $_ -match '^Size:\s+\d+' })
    if ($filesLine.Count -ne 1 -or $sizeLine.Count -ne 1) {
        throw "7z 검사 요약 파싱 실패: $ArchivePath"
    }
    return [ordered]@{
        files = [long]([regex]::Match(
            [string]$filesLine[0], '\d+'
        ).Value)
        bytes = [long]([regex]::Match(
            [string]$sizeLine[0], '\d+'
        ).Value)
        exit_code = $code
    }
}

$sourceDrive = [IO.DriveInfo]::new('D')
if (-not $sourceDrive.IsReady -or $sourceDrive.VolumeLabel -ne 'DATA_SSD') {
    throw "D: 메인 드라이브 안전 차단"
}
$archiveInfo = [IO.DriveInfo]::new($ArchiveDrive)
if (-not $archiveInfo.IsReady -or $archiveInfo.DriveFormat -ne 'NTFS') {
    throw "$ArchiveDrive archive 드라이브 안전 차단"
}
$freeGiB = [math]::Round($archiveInfo.AvailableFreeSpace / 1GB, 3)
if ($freeGiB -lt $MinimumFreeGiB) {
    throw "$ArchiveDrive 공간 부족: ${freeGiB}GiB"
}
if (
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessName -match '^(mfa|python|conda|robocopy|7z)$'
        }
) {
    throw "MFA/Python/conda/robocopy/7z 동시 실행 금지"
}

$sevenZip = @(
    'C:\Program Files\7-Zip\7z.exe',
    'C:\Program Files (x86)\7-Zip\7z.exe'
) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
if ([string]::IsNullOrWhiteSpace([string]$sevenZip)) {
    throw "7-Zip 실행 파일 없음"
}
$version = [string](
    & $sevenZip i |
        Where-Object { $_ -match '^7-Zip [0-9.]+' } |
        Select-Object -First 1
)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($version)) {
    throw "7-Zip 버전 확인 실패"
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
        key = 'textgrid_2020'
        source = $allowedSources[0]
        archive_name = 'textgrid_baseline_pre_jamo_2020.7z'
    },
    [ordered]@{
        key = 'textgrid_2021'
        source = $allowedSources[1]
        archive_name = 'textgrid_baseline_pre_jamo_2021.7z'
    },
    [ordered]@{
        key = 'mfa_temp_2021'
        source = $allowedSources[2]
        archive_name = 'mfa_temp_baseline_pre_jamo_2021.7z'
    },
    [ordered]@{
        key = 'mfa_stale_temp'
        source = $allowedSources[3]
        archive_name = 'mfa_stale_temp_pre_jamo.7z'
    },
    [ordered]@{
        key = 'failed_model_clone'
        source = $allowedSources[4]
        archive_name = 'hf_clone_crlf_failure.7z'
    }
)
if ($Only -ne 'all') {
    $items = @($items | Where-Object { $_.key -eq $Only })
}

$archiveRoot = Join-Path $ArchiveDrive (
    'READ_ONLY_ARCHIVE\2026_summer_research\pre_jamo_compressed_20260728'
)
$archiveRoot = Assert-Child $archiveRoot ($ArchiveDrive + '\')
New-Item -ItemType Directory -Force -Path $archiveRoot | Out-Null
$manifestPath = Join-Path $archiveRoot 'archive_manifest.json'
if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    if (
        $manifest.schema_version -ne
            'pre_jamo_compressed_external_archive.v1'
    ) {
        throw "기존 compressed manifest schema 불일치"
    }
    if (
        $manifest.PSObject.Properties['error'] -and
        -not [string]::IsNullOrWhiteSpace([string]$manifest.error)
    ) {
        $history = @()
        if ($manifest.PSObject.Properties['failure_history']) {
            $history = @($manifest.failure_history)
        }
        $history += [ordered]@{
            failed_at = $manifest.failed_at
            error = $manifest.error
        }
        $manifest | Add-Member -NotePropertyName failure_history `
            -NotePropertyValue $history -Force
        $manifest | Add-Member -NotePropertyName failed_at `
            -NotePropertyValue $null -Force
        $manifest | Add-Member -NotePropertyName error `
            -NotePropertyValue $null -Force
        foreach ($priorItem in @($manifest.items)) {
            if (
                [string]$priorItem.status -in @(
                    'measuring_source',
                    'creating_archive',
                    'testing_crc'
                )
            ) {
                $priorItem.status = 'failed'
                $priorItem | Add-Member `
                    -NotePropertyName failure_reason `
                    -NotePropertyValue $history[-1].error -Force
            }
        }
    }
    $manifest.status = 'running'
    $manifest | Add-Member -NotePropertyName resumed_at `
        -NotePropertyValue (Get-Date).ToString('o') -Force
} else {
    $manifest = [ordered]@{
        schema_version = 'pre_jamo_compressed_external_archive.v1'
        status = 'running'
        started_at = (Get-Date).ToString('o')
        source_drive = 'D: DATA_SSD'
        archive_drive = $ArchiveDrive
        source_read_only = $true
        source_pruning_supported = $false
        tool = $version.Trim()
        verification = (
            '7-Zip CRC full test plus file-count/byte-count, all DB ' +
            'SHA256 before/after, and archive SHA256'
        )
        items = @()
    }
}
Save-Manifest $manifestPath $manifest

try {
    foreach ($item in $items) {
        $source = Assert-ExactSource ([string]$item.source) $allowedSources
        if (-not (Test-Path -LiteralPath $source -PathType Container)) {
            $manifest.items += [ordered]@{
                key = $item.key
                source = $source
                status = 'source_absent'
            }
            Save-Manifest $manifestPath $manifest
            continue
        }
        $archivePath = Assert-Child (
            Join-Path $archiveRoot ([string]$item.archive_name)
        ) $archiveRoot
        $verified = @($manifest.items | Where-Object {
            $_.key -eq $item.key -and $_.status -eq 'verified'
        })
        if ($verified.Count -gt 0) {
            if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
                throw "verified archive 실물 없음: $archivePath"
            }
            $actualHash = (
                Get-FileHash -LiteralPath $archivePath -Algorithm SHA256
            ).Hash.ToLowerInvariant()
            if ($actualHash -ne [string]$verified[-1].archive_sha256) {
                throw "verified archive SHA256 불일치: $archivePath"
            }
            Write-Host "[SKIP] 검증된 기존 archive: $($item.key)"
            continue
        }
        if (Test-Path -LiteralPath $archivePath) {
            throw "manifest 없는 최종 archive 덮어쓰기 금지: $archivePath"
        }
        $partialPath = "$archivePath.partial"
        if (Test-Path -LiteralPath $partialPath) {
            Move-Item -LiteralPath $partialPath -Destination (
                "$partialPath.abandoned_" +
                (Get-Date -Format 'yyyyMMdd_HHmmss')
            )
        }

        $record = [ordered]@{
            key = $item.key
            source = $source
            archive = $archivePath
            status = 'measuring_source'
            started_at = (Get-Date).ToString('o')
        }
        $manifest.items += $record
        Save-Manifest $manifestPath $manifest
        $before = Get-TreeMeasure $source
        $dbBefore = Get-AllDatabaseHashes $source
        $record.source_files = $before.files
        $record.source_bytes = $before.bytes
        $record.database_sha256 = $dbBefore
        $record.status = 'creating_archive'
        Save-Manifest $manifestPath $manifest

        Push-Location $source
        try {
            & $sevenZip a -t7z -mx=1 -m0=LZMA2 -ms=256m `
                -mmt=on -bb0 -- $partialPath '.\*'
            $createCode = $LASTEXITCODE
        } finally {
            Pop-Location
        }
        if ($createCode -ne 0) {
            throw "7z 생성 실패(exit=$createCode): $source"
        }
        $record.status = 'testing_crc'
        Save-Manifest $manifestPath $manifest
        $archiveMeasure = Test-SevenZipArchive $sevenZip $partialPath
        $after = Get-TreeMeasure $source
        $dbAfter = Get-AllDatabaseHashes $source
        if (
            $before.files -ne $after.files -or
            $before.bytes -ne $after.bytes -or
            $before.files -ne $archiveMeasure.files -or
            $before.bytes -ne $archiveMeasure.bytes -or
            (ConvertTo-Json $dbBefore -Compress) -ne
                (ConvertTo-Json $dbAfter -Compress)
        ) {
            throw "archive 생성 중 원본 또는 파일 수/바이트 불일치"
        }
        $archiveHash = (
            Get-FileHash -LiteralPath $partialPath -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        Move-Item -LiteralPath $partialPath -Destination $archivePath
        $record.archive_files = $archiveMeasure.files
        $record.archive_uncompressed_bytes = $archiveMeasure.bytes
        $record.archive_bytes = [long](
            Get-Item -LiteralPath $archivePath
        ).Length
        $record.archive_sha256 = $archiveHash
        $record.create_exit = $createCode
        $record.crc_test_exit = $archiveMeasure.exit_code
        $record.status = 'verified'
        $record.verified_at = (Get-Date).ToString('o')
        Save-Manifest $manifestPath $manifest
    }
    $manifest.status = 'success'
    $manifest | Add-Member -NotePropertyName completed_at `
        -NotePropertyValue (Get-Date).ToString('o') -Force
    Save-Manifest $manifestPath $manifest
    Write-Host "[OK] compressed archive: $manifestPath"
} catch {
    $manifest.status = 'failed'
    $manifest | Add-Member -NotePropertyName failed_at `
        -NotePropertyValue (Get-Date).ToString('o') -Force
    $manifest | Add-Member -NotePropertyName error `
        -NotePropertyValue $_.Exception.Message -Force
    foreach ($failedItem in @($manifest.items)) {
        if (
            [string]$failedItem.status -in @(
                'measuring_source',
                'creating_archive',
                'testing_crc'
            )
        ) {
            $failedItem.status = 'failed'
            $failedItem | Add-Member -NotePropertyName failure_reason `
                -NotePropertyValue $_.Exception.Message -Force
        }
    }
    Save-Manifest $manifestPath $manifest
    throw
}
