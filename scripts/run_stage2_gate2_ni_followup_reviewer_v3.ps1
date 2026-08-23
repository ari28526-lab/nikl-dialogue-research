[CmdletBinding()]
param(
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pipelinePython = 'C:\Users\ari30\miniforge3\envs\mfa\python.exe'
$builder = Join-Path $projectRoot 'scripts\python\build_stage2_gate2_ni_followup_reviewer_v3.py'
$auditor = Join-Path $projectRoot 'scripts\python\audit_stage2_gate2_ni_followup_reviewer_v3.py'
$outputDirectory = Join-Path $projectRoot 'outputs\pilots\stage2_gate2_ni_followup_reviewer_v3_20260823'

if (-not (Test-Path -LiteralPath $pipelinePython -PathType Leaf)) {
    throw "Pipeline Python을 찾지 못했습니다: $pipelinePython"
}
if (-not (Test-Path -LiteralPath $builder -PathType Leaf)) {
    throw "Builder를 찾지 못했습니다: $builder"
}
if (-not (Test-Path -LiteralPath $auditor -PathType Leaf)) {
    throw "감사기를 찾지 못했습니다: $auditor"
}

if ($PreflightOnly) {
    & $pipelinePython $builder --preflight-only
    if ($LASTEXITCODE -ne 0) {
        throw "Gate 2 preflight가 실패했습니다. exit=$LASTEXITCODE"
    }
    Write-Host '[PASS] Gate 2 preflight only. 출력과 연구 기록은 생성하지 않았습니다.'
    exit 0
}

if (Test-Path -LiteralPath $outputDirectory) {
    throw "기존 출력은 덮어쓰지 않습니다: $outputDirectory"
}

& $pipelinePython $builder
if ($LASTEXITCODE -ne 0) {
    throw "Gate 2 builder가 실패했습니다. exit=$LASTEXITCODE"
}

& $pipelinePython $auditor --write-audit
if ($LASTEXITCODE -ne 0) {
    throw "Gate 2 독립 감사가 실패했습니다. exit=$LASTEXITCODE"
}

Write-Host "[PASS] Gate 2 reviewer 생성·감사 완료: $outputDirectory"
Write-Host '실제 청취·저장·Gate 3는 연구자가 별도로 시작합니다.'
