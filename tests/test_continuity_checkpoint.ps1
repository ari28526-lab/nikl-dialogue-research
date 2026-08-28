#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $root 'scripts\write_continuity_checkpoint.ps1'
$testName = 'continuity_checkpoint_test_' + [guid]::NewGuid().ToString('N')
$relativeLog = "work\$testName.jsonl"
$testLog = Join-Path $root $relativeLog

try {
    $preflight = & $scriptPath `
        -Summary 'synthetic preflight' `
        -NextStep 'do not write' `
        -Status 'in_progress' `
        -LogPath $relativeLog `
        -PreflightOnly | ConvertFrom-Json
    if ($preflight.status -ne 'preflight_passed') {
        throw 'preflight 상태 오류'
    }
    if (Test-Path -LiteralPath $testLog) {
        throw 'preflight가 파일을 생성함'
    }

    $written = & $scriptPath `
        -Summary 'synthetic checkpoint' `
        -NextStep 'remove synthetic checkpoint' `
        -Status 'paused' `
        -DecisionNeeded @('decision one', 'decision two') `
        -Actor 'test' `
        -LogPath $relativeLog | ConvertFrom-Json
    if ($written.status -ne 'checkpoint_appended') {
        throw 'append 상태 오류'
    }

    $rows = @(Get-Content -LiteralPath $testLog -Encoding UTF8)
    if ($rows.Count -ne 1) { throw '첫 append 행 수 오류' }
    $record = $rows[0] | ConvertFrom-Json
    if ($record.schema_version -ne 'project_continuity_checkpoint.v1') {
        throw 'schema_version 오류'
    }
    if ($record.summary -ne 'synthetic checkpoint') {
        throw 'summary 보존 오류'
    }
    if (@($record.decision_needed).Count -ne 2) {
        throw 'decision_needed 배열 보존 오류'
    }
    $expectedBranch = [string]@(& git -C $root rev-parse --abbrev-ref HEAD)[0]
    $expectedHead = [string]@(& git -C $root rev-parse HEAD)[0]
    if ($record.git.branch -ne $expectedBranch) {
        throw "git branch 보존 오류: $($record.git.branch) != $expectedBranch"
    }
    if ($record.git.head -ne $expectedHead) {
        throw "git HEAD 보존 오류: $($record.git.head) != $expectedHead"
    }
    if ($record.safety.automatic_commit -ne $false -or
        $record.safety.automatic_push -ne $false) {
        throw '자동 Git 변경 금지값 오류'
    }

    & $scriptPath `
        -Summary 'second synthetic checkpoint' `
        -NextStep 'verify append only' `
        -Status 'completed' `
        -Actor 'test' `
        -LogPath $relativeLog | Out-Null
    $rows = @(Get-Content -LiteralPath $testLog -Encoding UTF8)
    if ($rows.Count -ne 2) { throw 'append-only 두 번째 행 수 오류' }

    Write-Host 'continuity checkpoint test PASS'
} finally {
    if (Test-Path -LiteralPath $testLog -PathType Leaf) {
        $resolvedLog = [IO.Path]::GetFullPath($testLog)
        $resolvedWork = [IO.Path]::GetFullPath((Join-Path $root 'work')).TrimEnd('\') + '\'
        if ($resolvedLog.StartsWith(
            $resolvedWork, [StringComparison]::OrdinalIgnoreCase
        )) {
            Remove-Item -LiteralPath $resolvedLog -Force
        }
    }
}
