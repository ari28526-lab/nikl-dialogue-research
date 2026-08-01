# 연도 MFA 시작 전: 입력을 전수 감사하고 승인 제외 후보표만 만든다.
# 이 스크립트는 WAV를 이동하거나 후보를 자동 승인하지 않는다.

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year,
    [Parameter(Mandatory=$true)]
    [string]$SearchMasterRoot,
    [string]$OutputRoot = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (Join-Path $projectRoot 'config\paths.json') `
    -Raw -Encoding UTF8 | ConvertFrom-Json
function Resolve-ConfiguredPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}
$python = Resolve-ConfiguredPath ([string]$config.pipeline_python)
$wavRoot = Join-Path (Resolve-ConfiguredPath ([string]$config.wav)) 'individual'
$morphRoot = Resolve-ConfiguredPath ([string]$config.textgrid_merged)
$layers = Resolve-ConfiguredPath ([string]$config.layers)
$stateRoot = Resolve-ConfiguredPath ([string]$config.mfa_state)
$sourcePcm = Join-Path $layers '05_audio_index\source_pcm_check.csv'
$pythonDir = Join-Path $PSScriptRoot 'python'
$SearchMasterRoot = [IO.Path]::GetFullPath($SearchMasterRoot)
if (-not (Test-Path -LiteralPath $python)) { throw "pipeline Python 없음: $python" }
if (-not (Test-Path -LiteralPath $SearchMasterRoot)) {
    throw "search master 없음: $SearchMasterRoot"
}

# 같은 입력 계약의 기존 lab까지 전수 내용 검증한다. 원 corpus는 수정하지 않는다.
& $python (Join-Path $pythonDir 'realign_eojeol_build_corpus.py') `
    --year $Year --search-master-root $SearchMasterRoot --force-verify
if ($LASTEXITCODE -ne 0) { throw "lab 입력 전수 검증 실패" }
$labReport = Join-Path $stateRoot "logs\lab_build_${Year}_latest.json"
$labData = Get-Content -LiteralPath $labReport -Raw -Encoding UTF8 |
    ConvertFrom-Json
if ($labData.status -ne 'passed') { throw "lab report status 불통과" }
$inputContractId = [string]$labData.input_contract_id
if ([string]::IsNullOrWhiteSpace($inputContractId)) {
    throw "lab report input_contract_id 누락"
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $projectRoot (
        'outputs\reviews\mfa_exclusions_{0}_{1}' -f
        $Year, $inputContractId.Substring(0, 12)
    )
}
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$auditReport = Join-Path $OutputRoot '01_input_audit_unapproved.json'
$wavInventory = Join-Path $OutputRoot '02_bad_wav_candidates.csv'
$reviewCsv = Join-Path $OutputRoot '03_RESEARCHER_REVIEW.csv'
$reviewReport = Join-Path $OutputRoot '03_RESEARCHER_REVIEW_MANIFEST.json'

# 후보 발견 단계이므로 --no-strict. 실패를 숨기는 것이 아니라 issue_inventory를
# 연구자 검토표로 변환하기 위한 명시적 1차 감사다.
& $python (Join-Path $pythonDir 'audit_mfa_year_readiness.py') `
    --years $Year --search-master-root $SearchMasterRoot `
    --wav-root $wavRoot --morph-textgrid-root $morphRoot `
    --source-pcm-check $sourcePcm --gate-profile analysis --no-strict `
    --output $auditReport
if ($LASTEXITCODE -ne 0) { throw "입력 후보 감사 실행 실패" }
& $python (Join-Path $pythonDir 'quarantine_bad_wavs.py') `
    --year $Year --inventory-csv $wavInventory
if ($LASTEXITCODE -ne 0) { throw "불량 WAV dry-run inventory 실패" }
& $python (Join-Path $pythonDir 'prepare_mfa_exclusion_review.py') `
    --audit-report $auditReport --year $Year `
    --search-master-root $SearchMasterRoot `
    --input-contract-id $inputContractId `
    --quarantine-log $wavInventory `
    --output-csv $reviewCsv --output-report $reviewReport
if ($LASTEXITCODE -ne 0) { throw "연구자 검토표 생성 실패" }

Write-Host "[OK] 승인 전 후보표 생성(자동 승인 없음)" -ForegroundColor Green
Write-Host "검토 파일: $reviewCsv"
Write-Host "input_contract_id: $inputContractId"
Write-Host (
    "다음 단계: 각 행을 확인해 decision=pending을 approved로 바꾼 뒤 " +
    "mfa_exclusion_contract.py build 실행. 후보 0건이어도 빈 표를 명시 승인."
)
