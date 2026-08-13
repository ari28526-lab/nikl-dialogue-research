<#
한 연도의 조합검색 CSV.gz를 shard checkpoint 방식으로 생성한다.

- 기존 pre-MFA search master는 읽기 전용이다.
- 성공 shard는 재실행 때 SHA-256 검증 후 재사용한다.
- 실패 partial은 자동 삭제하지 않는다.
- MFA·TextGrid·공통발음사전은 실행하거나 변경하지 않는다.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$RunId = 'morph_search_v3_20260801',
    [ValidateRange(1, 1000)]
    [int]$FilesPerShard = 100,
    [ValidateRange(0, 100000)]
    [int]$MaxShards = 0,
    [ValidateRange(10, 500)]
    [int]$MinimumFreeGiB = 50,
    [switch]$EmitOrthComponents,
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
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

function Write-JsonAtomic([string]$Path, $Payload) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $partial = "$Path.$PID.partial"
    $Payload | ConvertTo-Json -Depth 10 |
        Set-Content -LiteralPath $partial -Encoding UTF8
    Move-Item -LiteralPath $partial -Destination $Path -Force
}

$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
$inputBase = Resolve-ConfiguredPath ([string]$config.pre_mfa_search_master)
$outputBase = Resolve-ConfiguredPath ([string]$config.morph_search_v3_staging)
$inputRoot = Join-Path $inputBase $Year
$outputRoot = Join-Path (Join-Path $outputBase $RunId) $Year
$sourceMeta = Join-Path $inputBase '_build_meta.json'

foreach ($required in @($python, $sourceMeta)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "필수 파일 없음: $required"
    }
}
if (-not (Test-Path -LiteralPath $inputRoot -PathType Container)) {
    throw "연도 입력 root 없음: $inputRoot"
}
$meta = Get-Content -LiteralPath $sourceMeta -Raw -Encoding UTF8 |
    ConvertFrom-Json
if ([string]$meta.status -ne 'success') {
    throw "pre-MFA search master가 success 정본이 아님: $sourceMeta"
}

$driveName = ([IO.Path]::GetPathRoot($outputBase)).TrimEnd('\')
$drive = [IO.DriveInfo]::new($driveName + '\')
$freeGiB = [math]::Round($drive.AvailableFreeSpace / 1GB, 3)
if ($freeGiB -lt $MinimumFreeGiB) {
    throw "저장공간 부족: $driveName free=$freeGiB GiB, 최소=$MinimumFreeGiB GiB"
}

$lockPath = Join-Path $outputRoot 'RUNNING.lock.json'
if ($PreflightOnly) {
    if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
        $prior = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        $priorProcess = Get-Process -Id ([int]$prior.pid) -ErrorAction SilentlyContinue
        if ($null -ne $priorProcess) {
            throw "동일 연도 작업이 실행 중임: pid=$($prior.pid), lock=$lockPath"
        }
        Write-Warning "stale lock 발견; 실제 실행 때 archive: $lockPath"
    }
    $preservedPartials = @()
    if (Test-Path -LiteralPath $outputRoot -PathType Container) {
        $preservedPartials = @(
            Get-ChildItem -LiteralPath $outputRoot -Recurse -Force `
                -ErrorAction Stop |
                Where-Object {
                    $_.Name.EndsWith('.partial') -and
                    $_.FullName.IndexOf(
                        '\archive_failed\',
                        [StringComparison]::OrdinalIgnoreCase
                    ) -lt 0
                }
        )
    }
    if ($preservedPartials.Count -gt 0) {
        $examples = @(
            $preservedPartials |
                Select-Object -First 5 -ExpandProperty FullName
        ) -join '; '
        throw (
            "미완료 partial이 남아 있어 실제 실행 전 조사·archive 필요: " +
            $examples
        )
    }
    $inputFiles = @(
        Get-ChildItem -LiteralPath $inputRoot -File -Filter '*.csv'
    ).Count
    if ($inputFiles -le 0) { throw "연도 입력 CSV 없음: $inputRoot" }
    $totalShards = [math]::Ceiling($inputFiles / [double]$FilesPerShard)
    Write-Host (
        "[GO] 조합검색 preflight: year=$Year, input_files=$inputFiles, " +
        "shards=$totalShards, D free=$freeGiB GiB"
    ) -ForegroundColor Green
    Write-Host '출력·lock·MFA·TextGrid·공통발음사전을 만들거나 변경하지 않음.'
    exit 0
}

New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
    $prior = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $priorProcess = Get-Process -Id ([int]$prior.pid) -ErrorAction SilentlyContinue
    if ($null -ne $priorProcess) {
        throw "동일 연도 작업이 실행 중임: pid=$($prior.pid), lock=$lockPath"
    }
    $stale = Join-Path $outputRoot (
        'RUNNING.lock.stale.' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json'
    )
    Move-Item -LiteralPath $lockPath -Destination $stale
}

$lock = [ordered]@{
    schema_version = 'morph_search_year_lock.v1'
    pid = $PID
    started_at = (Get-Date).ToString('o')
    year = $Year
    run_id = $RunId
    input_root = $inputRoot
    output_root = $outputRoot
    files_per_shard = $FilesPerShard
    max_shards = $MaxShards
    emit_orth_components = [bool]$EmitOrthComponents
}
Write-JsonAtomic $lockPath $lock

Write-Host (
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 조합검색 $Year 시작: " +
    "shard=$FilesPerShard files, D free=$freeGiB GiB"
) -ForegroundColor Cyan
Write-Host "입력: $inputRoot"
Write-Host "출력: $outputRoot"
Write-Host 'MFA·TextGrid·공통발음사전은 변경하지 않는다.'

$args = @(
    (Join-Path $PSScriptRoot 'python\build_morph_search_year_sharded.py'),
    '--year', $Year,
    '--input-root', $inputRoot,
    '--output-root', $outputRoot,
    '--files-per-shard', ([string]$FilesPerShard)
)
if ($MaxShards -gt 0) {
    $args += @('--max-shards', ([string]$MaxShards))
}
if ($EmitOrthComponents) {
    $args += '--emit-orth-components'
}

try {
    & $python @args
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "조합검색 연도 build 실패: exit=$exitCode"
    }
} finally {
    if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
        $current = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        if ([int]$current.pid -eq $PID) {
            Remove-Item -LiteralPath $lockPath
        }
    }
}

Write-Host '[OK] 조합검색 연도 작업 종료' -ForegroundColor Green
Write-Host "상태: $(Join-Path $outputRoot 'YEAR_PROGRESS.json')"
