param(
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year = '2020',
    [switch]$CatalogOnly,
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\ari30\miniforge3\envs\mfa\python.exe'
$config = Join-Path $projectRoot 'config\mfa_r3_research_database_v1.json'
$builder = Join-Path $PSScriptRoot 'python\build_mfa_r3_research_database.py'
$auditor = Join-Path $PSScriptRoot 'python\audit_mfa_r3_research_database.py'
$outputRoot = 'D:\mfa_common_pron\releases\common_pron_mfa_r3_20260809\05_research_database'
$lockPath = Join-Path $outputRoot 'RESEARCH_DATABASE_BUILD.lock'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "pipeline Python 없음: $python"
}
if ([string]([IO.DriveInfo]::new('D:\')).VolumeLabel -ne 'DATA_SSD') {
    throw 'D: volume label이 DATA_SSD가 아님; 잘못된 드라이브 방지'
}
$freeGiB = [math]::Round(
    ([IO.DriveInfo]::new('D:\')).AvailableFreeSpace / 1GB, 3
)
if ($freeGiB -lt 5) {
    throw "D: 여유 공간이 5 GiB 미만: $freeGiB GiB"
}

$preflightArgs = [System.Collections.Generic.List[string]]::new()
$preflightArgs.Add($builder)
$preflightArgs.Add('--config')
$preflightArgs.Add($config)
if ($CatalogOnly) {
    $preflightArgs.Add('--catalog-only')
} else {
    $preflightArgs.Add('--year')
    $preflightArgs.Add($Year)
}
$preflightArgs.Add('--preflight-only')
& $python @preflightArgs
if ($LASTEXITCODE -ne 0) { throw 'r3 research DB preflight 실패' }
if ($PreflightOnly) {
    Write-Host '[GO] PreflightOnly: 출력·lock·MFA·TextGrid를 만들지 않음.' -ForegroundColor Green
    exit 0
}

New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
$lockStream = $null
try {
    try {
        $lockStream = [IO.File]::Open(
            $lockPath,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::Read
        )
    } catch [IO.IOException] {
        throw "research DB lock이 이미 존재함: $lockPath"
    }
    $lockText = @{
        schema_version = 'mfa_r3_research_database_lock.v1'
        pid = $PID
        year = $(if ($CatalogOnly) { '' } else { $Year })
        started_at = (Get-Date).ToString('o')
    } | ConvertTo-Json -Compress
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($lockText)
    $lockStream.Write($bytes, 0, $bytes.Length)
    $lockStream.Flush($true)

    $buildArgs = [System.Collections.Generic.List[string]]::new()
    $buildArgs.Add($builder)
    $buildArgs.Add('--config')
    $buildArgs.Add($config)
    if ($CatalogOnly) {
        $buildArgs.Add('--catalog-only')
    } else {
        $buildArgs.Add('--year')
        $buildArgs.Add($Year)
    }
    & $python @buildArgs
    if ($LASTEXITCODE -ne 0) { throw 'r3 research DB 생성 실패' }

    if (-not $CatalogOnly) {
        & $python $auditor '--config' $config '--year' $Year
        if ($LASTEXITCODE -ne 0) { throw 'r3 research DB 독립 감사 실패' }
        Write-Host "[PASS] $Year DB 연결 Gate 준비 완료. MFA는 아직 시작하지 않음." -ForegroundColor Green
    }
} finally {
    if ($null -ne $lockStream) {
        $lockStream.Dispose()
        if (Test-Path -LiteralPath $lockPath) {
            Remove-Item -LiteralPath $lockPath -Force
        }
    }
}
