# 검증된 pre-MFA 언어층을 버전 고정한 뒤 연도별 MFA를 순차 실행한다.
#
# 안전 원칙:
# - 기존 05_search_master와 06_textgrid_eojeol을 덮어쓰지 않는다.
# - 새 search master는 versioned staging에 생성·검증한다.
# - pron_reference_form으로 lab을 만들고 기존 lab 내용도 전수 비교한다.
# - 다른 입력으로 만든 MFA temp는 삭제하지 않고 archive_stale_temp로 이동한다.
# - 한 연도가 실패하면 다음 연도로 넘어가지 않는다.
# - KOINA·stitch_session은 후보 추출 뒤 별도 산출물에서 수행한다.

param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$RunId = 'pre_mfa_v1_20260725',
    [Parameter(Mandatory=$true)]
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string[]]$Years,
    [switch]$PreferD,
    [switch]$UseDirectDbExport,
    [switch]$CleanupDirectDbAfterMerge,
    [switch]$SkipSearchMasterBuild,
    [string]$CommonPronManifest = '',
    [string]$CommonPronAdoptionContract = '',
    [string]$ApprovedExclusionsContract = '',
    [string]$CommonPronEquivalenceReport = '',
    [switch]$ForceVerifyLabInput,
    [switch]$AllowBaselineCommonPronRerun,
    [switch]$AllowLegacyInlineG2p,
    [switch]$AllowFullCleanRetry,
    [ValidateSet('','2020','2021','2022','2023','2024','2025')]
    [string]$PauseAfterYear = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root 'config\paths.json'
$pythonDir = Join-Path $PSScriptRoot 'python'

if ($Years.Count -ne 1) {
    Write-Error (
        "-Years는 한 연도만 허용함. 직전 연도 독립 QC와 누락 분류를 " +
        "확인한 뒤 다음 연도를 별도 실행할 것: requested=" +
        ($Years -join ',')
    )
    exit 1
}

if ($PauseAfterYear -and -not ($Years -contains $PauseAfterYear)) {
    Write-Error "-PauseAfterYear $PauseAfterYear 이 -Years 목록에 없음"
    exit 1
}
if ($CleanupDirectDbAfterMerge -and -not $UseDirectDbExport) {
    Write-Error "-CleanupDirectDbAfterMerge는 -UseDirectDbExport와 함께만 사용할 수 있음"
    exit 1
}
if (
    -not [string]::IsNullOrWhiteSpace($CommonPronManifest) -and
    -not $UseDirectDbExport
) {
    Write-Error (
        "r2 공통사전 전수 실행에는 연구 6-tier+동반표 direct export가 " +
        "필수임: -UseDirectDbExport를 지정할 것"
    )
    exit 1
}
if (
    -not [string]::IsNullOrWhiteSpace($CommonPronManifest) -and
    [string]::IsNullOrWhiteSpace($ApprovedExclusionsContract)
) {
    Write-Error (
        "r2 전수 실행에는 연구자 승인 제외 계약이 필수임: " +
        "-ApprovedExclusionsContract"
    )
    exit 1
}
if (
    -not [string]::IsNullOrWhiteSpace($CommonPronEquivalenceReport)
) {
    Write-Error (
        "-CommonPronEquivalenceReport는 r1 폐기 gate임. " +
        "-CommonPronAdoptionContract를 사용할 것"
    )
    exit 1
}
if (
    [string]::IsNullOrWhiteSpace($CommonPronManifest) -ne
    [string]::IsNullOrWhiteSpace($CommonPronAdoptionContract)
) {
    Write-Error (
        "-CommonPronManifest와 -CommonPronAdoptionContract는 " +
        "둘 다 지정하거나 둘 다 생략해야 함"
    )
    exit 1
}
if (
    [string]::IsNullOrWhiteSpace($CommonPronManifest) -and
    -not $AllowLegacyInlineG2p
) {
    Write-Error (
        "검증·승인된 공통사전 r2 manifest가 기본 필수임. r2 실물이 " +
        "아직 없으면 대량 MFA를 시작하지 말 것. 과거 진단만 " +
        "-AllowLegacyInlineG2p로 명시할 수 있음"
    )
    exit 1
}
if (
    $AllowLegacyInlineG2p -and
    -not [string]::IsNullOrWhiteSpace($CommonPronManifest)
) {
    Write-Error (
        "-AllowLegacyInlineG2p와 -CommonPronManifest는 함께 사용할 수 없음"
    )
    exit 1
}
if (
    $AllowBaselineCommonPronRerun -and
    [string]::IsNullOrWhiteSpace($CommonPronManifest)
) {
    Write-Error (
        "-AllowBaselineCommonPronRerun은 검증된 공통사전 r2 manifest와 " +
        "함께만 사용할 수 있음"
    )
    exit 1
}
if (
    $AllowBaselineCommonPronRerun -and
    $Years[0] -notin @('2020', '2021')
) {
    Write-Error (
        "-AllowBaselineCommonPronRerun은 2020·2021 전수 재실행에만 " +
        "사용할 수 있음: requested=$($Years[0])"
    )
    exit 1
}
if (
    -not [string]::IsNullOrWhiteSpace($CommonPronManifest) -and
    $Years[0] -in @('2020', '2021') -and
    -not $AllowBaselineCommonPronRerun
) {
    Write-Error (
        "2020·2021 r2 전수 재실행 결정은 명시적이어야 함. " +
        "-AllowBaselineCommonPronRerun을 지정할 것"
    )
    exit 1
}

function Expand-CfgPath($value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables(
            ([string]$value).Replace('/', '\')
        )
    )
}

try {
    $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 |
           ConvertFrom-Json
    $py = Expand-CfgPath $cfg.pipeline_python
    $layers = Expand-CfgPath $cfg.layers
    $stateRoot = Expand-CfgPath $cfg.mfa_state
} catch {
    Write-Error "config/paths.json 해석 실패: $($_.Exception.Message)"
    exit 1
}
if (-not (Test-Path -LiteralPath $py)) {
    Write-Error "pipeline_python 없음: $py"
    exit 1
}

$preMfaBase = Join-Path $layers '05_search_master_pre_mfa_staging'
$preMfaRoot = Join-Path $preMfaBase $RunId
$resolvedBase = [IO.Path]::GetFullPath($preMfaBase).TrimEnd('\')
$resolvedOutput = [IO.Path]::GetFullPath($preMfaRoot).TrimEnd('\')
if ((Split-Path -Parent $resolvedOutput) -ne $resolvedBase) {
    Write-Error "pre-MFA staging 경계 위반: $resolvedOutput"
    exit 1
}

$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$transcript = Join-Path $logDir "pre_mfa_bulk_${RunId}_${stamp}.log"
$summaryPath = Join-Path $logDir "pre_mfa_bulk_${RunId}_latest.json"

$lockDir = Join-Path $stateRoot 'locks'
New-Item -ItemType Directory -Force -Path $lockDir | Out-Null
$lockPath = Join-Path $lockDir 'pre_mfa_bulk.lock'
if (Test-Path -LiteralPath $lockPath) {
    $live = $false
    try {
        $oldLock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 |
                   ConvertFrom-Json
        if ($oldLock.pid) {
            $live = $null -ne (
                Get-Process -Id ([int]$oldLock.pid) -ErrorAction SilentlyContinue
            )
        }
    } catch {
        $live = $false
    }
    if ($live) {
        Write-Error "다른 pre-MFA/MFA 배치가 실행 중(pid=$($oldLock.pid)): $lockPath"
        exit 1
    }
    $archiveLockDir = Join-Path $lockDir 'archive_stale'
    New-Item -ItemType Directory -Force -Path $archiveLockDir | Out-Null
    Move-Item -LiteralPath $lockPath -Destination (
        Join-Path $archiveLockDir "pre_mfa_bulk_${stamp}.lock"
    )
}
[ordered]@{
    pid = $PID
    owner_mode = 'bulk_wrapper'
    run_id = $RunId
    years = $Years
    prefer_d = [bool]$PreferD
    direct_db_export = [bool]$UseDirectDbExport
    common_pron_manifest = $CommonPronManifest
    common_pron_adoption_contract = $CommonPronAdoptionContract
    approved_exclusions_contract = $ApprovedExclusionsContract
    legacy_common_pron_equivalence_report = $CommonPronEquivalenceReport
    force_verify_lab_input = [bool]$ForceVerifyLabInput
    allow_baseline_common_pron_rerun = [bool]$AllowBaselineCommonPronRerun
    allow_full_clean_retry = [bool]$AllowFullCleanRetry
    started_at = (Get-Date).ToString('o')
    pre_mfa_root = $preMfaRoot
} | ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath $lockPath -Encoding UTF8

$completed = New-Object System.Collections.Generic.List[string]
$status = 'running'
$failure = $null
$exitCode = 1
$pausedAfterYear = $null
$pausedBeforeYear = $null
Start-Transcript -LiteralPath $transcript -Force | Out-Null
try {
    Write-Host "pre-MFA/MFA 안전 배치 시작: $RunId" -ForegroundColor Cyan
    Write-Host "연도: $($Years -join ', ')"
    Write-Host "새 pre-MFA CSV: $preMfaRoot"
    Write-Host "기존 정본 CSV/TextGrid는 덮어쓰지 않음"
    Write-Host ("작업 드라이브: " + $(if ($PreferD) {
        "D: 우선(신규 MFA temp/output)"
    } else {
        "자동 선택"
    }))

    $metaPath = Join-Path $preMfaRoot '_build_meta.json'
    $reuseFrozenMaster = $false
    if (Test-Path -LiteralPath $metaPath) {
        try {
            $existingMeta = Get-Content -LiteralPath $metaPath -Raw -Encoding UTF8 |
                            ConvertFrom-Json
            $reuseFrozenMaster = $existingMeta.status -eq 'success'
        } catch {
            $reuseFrozenMaster = $false
        }
    }
    if ($reuseFrozenMaster) {
        Write-Host "동결된 pre-MFA build meta 확인 — CSV를 다시 쓰지 않음: $metaPath"
    } elseif (-not $SkipSearchMasterBuild) {
        & $py (Join-Path $pythonDir 'preflight_search_master.py')
        if ($LASTEXITCODE -ne 0) {
            throw "search master preflight 실패(exit $LASTEXITCODE)"
        }
        & $py (Join-Path $pythonDir 'build_search_master.py') `
            --output-root $preMfaRoot --run-id $RunId
        if ($LASTEXITCODE -ne 0) {
            throw "pre-MFA search master 빌드 실패(exit $LASTEXITCODE)"
        }
    } else {
        throw "-SkipSearchMasterBuild를 지정했지만 통과한 build meta가 없음: $metaPath"
    }

    if (-not (Test-Path -LiteralPath $metaPath)) {
        throw "pre-MFA build meta 없음: $metaPath"
    }
    $meta = Get-Content -LiteralPath $metaPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
    if ($meta.status -ne 'success') {
        throw "pre-MFA build 미통과(status=$($meta.status)): $metaPath"
    }

    foreach ($year in $Years) {
        Write-Host "===== $year MFA 게이트 시작 =====" -ForegroundColor Cyan
        $realignArgs = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            (Join-Path $PSScriptRoot 'run_eojeol_realign.ps1'),
            '-Year', $year,
            '-SearchMasterRoot', $preMfaRoot,
            '-BulkWrapperPid', [string]$PID
        )
        # r2 신규 실행은 D: 고정이다. -PreferD는 과거 호출과의 호환을
        # 위해 남기되 wrapper에서는 항상 하위 러너에 전달한다.
        $realignArgs += '-PreferD'
        if ($UseDirectDbExport) { $realignArgs += '-UseDirectDbExport' }
        if ($ForceVerifyLabInput) { $realignArgs += '-ForceVerifyLabInput' }
        if ($AllowFullCleanRetry) { $realignArgs += '-AllowFullCleanRetry' }
        if ($CleanupDirectDbAfterMerge) {
            $realignArgs += '-CleanupDirectDbAfterMerge'
        }
        if (-not [string]::IsNullOrWhiteSpace($CommonPronManifest)) {
            $realignArgs += @(
                '-CommonPronManifest', $CommonPronManifest,
                '-CommonPronAdoptionContract',
                $CommonPronAdoptionContract,
                '-ApprovedExclusionsContract',
                $ApprovedExclusionsContract
            )
            if ($AllowBaselineCommonPronRerun) {
                $realignArgs += '-AllowBaselineCommonPronRerun'
            }
        } elseif ($AllowLegacyInlineG2p) {
            $realignArgs += '-AllowLegacyInlineG2p'
        }
        & powershell.exe @realignArgs
        $yearExitCode = $LASTEXITCODE
        if ($yearExitCode -eq 75) {
            $pausedBeforeYear = $year
            if ($completed.Count -gt 0) {
                $pausedAfterYear = $completed[$completed.Count - 1]
            }
            $status = 'paused'
            $exitCode = 0
            Write-Host (
                "===== 의도적 일시정지: $pausedAfterYear 완료, " +
                "$pausedBeforeYear 미시작 ====="
            ) -ForegroundColor Yellow
            break
        }
        if ($yearExitCode -ne 0) {
            throw "$year MFA/병합 실패(exit $yearExitCode); 다음 연도는 실행하지 않음"
        }
        $completed.Add($year)
        if ($PauseAfterYear -and $year -eq $PauseAfterYear) {
            $pausedAfterYear = $year
            $status = 'paused'
            $exitCode = 0
            Write-Host "===== $year 완료 뒤 요청에 따라 일시정지 =====" `
                -ForegroundColor Yellow
            break
        }
    }
    if ($status -eq 'running') {
        $status = 'passed'
        $exitCode = 0
    }
} catch {
    $status = 'failed'
    $failure = $_.Exception.Message
    Write-Host "!! 안전 배치 중단: $failure" -ForegroundColor Red
} finally {
    [ordered]@{
        run_id = $RunId
        status = $status
        years_requested = $Years
        years_completed = @($completed)
        prefer_d = [bool]$PreferD
        direct_db_export = [bool]$UseDirectDbExport
        cleanup_direct_db_after_merge = [bool]$CleanupDirectDbAfterMerge
        common_pron_manifest = $CommonPronManifest
        common_pron_adoption_contract = $CommonPronAdoptionContract
        approved_exclusions_contract = $ApprovedExclusionsContract
        legacy_common_pron_equivalence_report = $CommonPronEquivalenceReport
        force_verify_lab_input = [bool]$ForceVerifyLabInput
        allow_baseline_common_pron_rerun = [bool]$AllowBaselineCommonPronRerun
        allow_full_clean_retry = [bool]$AllowFullCleanRetry
        pause_after_year_requested = $PauseAfterYear
        paused_after_year = $pausedAfterYear
        paused_before_year = $pausedBeforeYear
        failed_reason = $failure
        pre_mfa_root = $preMfaRoot
        transcript = $transcript
        finished_at = (Get-Date).ToString('o')
        next_action = if ($status -eq 'passed') {
            '전수 QC 후에만 정본 승격; 자동 승격 금지'
        } elseif ($status -eq 'paused') {
            '완료 연도 QC·병목 개선 뒤 남은 연도만 명시해 재개'
        } else {
            'transcript와 D:\mfa_eojeol\logs의 해당 연도 로그 확인'
        }
    } | ConvertTo-Json -Depth 5 |
        Set-Content -LiteralPath $summaryPath -Encoding UTF8
    if (Test-Path -LiteralPath $lockPath) {
        Remove-Item -LiteralPath $lockPath -Force
    }
    Stop-Transcript | Out-Null
}
exit $exitCode
