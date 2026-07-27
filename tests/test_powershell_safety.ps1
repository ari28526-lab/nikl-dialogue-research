# PowerShell 실행기 정적 안전성 회귀 검사. 실제 MFA·데이터 작업은 실행하지 않는다.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$files = @(
    (Join-Path $root 'scripts\preflight_eojeol_realign.ps1'),
    (Join-Path $root 'scripts\run_eojeol_realign.ps1'),
    (Join-Path $root 'scripts\run_pre_mfa_bulk_safe.ps1'),
    (Join-Path $root 'scripts\run_stratified_mfa_pilot.ps1'),
    (Join-Path $root 'scripts\run_search_master.ps1')
)
$failures = New-Object System.Collections.Generic.List[string]

foreach ($path in $files) {
    $bytes = [IO.File]::ReadAllBytes($path)
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and
               $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    if (-not $hasBom) { $failures.Add("UTF-8 BOM 없음: $path") }

    $tokens = $null
    $errors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile(
        $path, [ref]$tokens, [ref]$errors
    )
    foreach ($error in $errors) {
        $failures.Add("구문 오류 ${path}: $($error.Message)")
    }

    if ((Split-Path $path -Leaf) -eq 'run_eojeol_realign.ps1') {
        $returns = $ast.FindAll({
            param($node)
            $node -is [Management.Automation.Language.ReturnStatementAst]
        }, $true)
        foreach ($returnAst in $returns) {
            $parent = $returnAst.Parent
            $insideFunction = $false
            while ($null -ne $parent) {
                if ($parent -is [Management.Automation.Language.FunctionDefinitionAst]) {
                    $insideFunction = $true
                    break
                }
                $parent = $parent.Parent
            }
            if (-not $insideFunction) {
                $failures.Add(
                    "러너 최상위 return은 실패를 exit 0으로 숨길 수 있음: " +
                    $returnAst.Extent.Text
                )
            }
        }
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            'Write-DoneMarker',
            'Read-DoneMarker',
            'Remove-SafeYearPath',
            '산출 비율 $pct% < 99%',
            '[string]$Year',
            'textgrid_eojeol_staging',
            '--output-root',
            'promotion_required',
            '[switch]$PreferD',
            '[switch]$CleanupMfaOutput',
            '[switch]$UseDirectDbExport',
            '[switch]$CleanupDirectDbAfterMerge',
            'if ($PreferD)',
            'mfa_output_retained',
            'align_completed_temp_retained_until_merge',
            'heartbeat.jsonl',
            '--progress-jsonl',
            'lab_{0}_{1}_heartbeat.jsonl',
            'Get-ProcessTreeMetrics',
            'tree_cpu_seconds',
            'metrics_scope',
            'tree_python_process_count',
            'tree_working_set_mb',
            'MFA_PROJECT_SKIP_TEXTGRID_EXPORT',
            'export_mfa_db_4tier.py',
            '_partial_direct_db',
            'direct_merge_completed_temp_retained_for_qc',
            '$CleanupDirectDbAfterMerge -and -not $UseDirectDbExport',
            '$UseDirectDbExport -and $CleanupMfaOutput',
            'pause_after_year_',
            'exit 75',
            'exit 1'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("MFA 러너 필수 안전장치 누락: $required")
            }
        }
    }
    if ((Split-Path $path -Leaf) -eq 'preflight_eojeol_realign.ps1') {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            '[string]$Year',
            'textgrid_eojeol_staging',
            '[switch]$PreferD',
            'PreferD: D:'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("MFA preflight 연도/staging 가드 누락: $required")
            }
        }
    }
    if ((Split-Path $path -Leaf) -eq 'run_pre_mfa_bulk_safe.ps1') {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            '[switch]$PreferD',
            '[switch]$UseDirectDbExport',
            '[switch]$CleanupDirectDbAfterMerge',
            "'-UseDirectDbExport'",
            "'-CleanupDirectDbAfterMerge'",
            'direct_db_export = [bool]$UseDirectDbExport',
            '$CleanupDirectDbAfterMerge -and -not $UseDirectDbExport',
            'if ($PreferD)',
            "'-PreferD'",
            'prefer_d = [bool]$PreferD',
            'run_eojeol_realign.ps1',
            '[string]$PauseAfterYear',
            "status = 'paused'",
            'paused_after_year',
            '$yearExitCode -eq 75'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("pre-MFA 안전 wrapper D 우선 가드 누락: $required")
            }
        }
    }
    if ((Split-Path $path -Leaf) -eq 'run_stratified_mfa_pilot.ps1') {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            'speaker5',
            'speaker_id',
            'DATA_SSD',
            'verify_mfa_install.py',
            '--g2p_model_path',
            'Archive-PartialDirectory',
            'align_default_partial',
            '--retry_beam',
            'selection_manifest.csv',
            'textgrid_4tier',
            'exit 1'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("층화 MFA 파일럿 안전장치 누락: $required")
            }
        }
    }
}

# runner를 실행하지 않고 해당 함수 AST만 로드해, 관리자 권한 없는 현재
# PowerShell 프로세스가 실제 descendant tree로 집계되는지 동적 확인한다.
try {
    $runnerPath = Join-Path $root 'scripts\run_eojeol_realign.ps1'
    $runnerTokens = $null
    $runnerErrors = $null
    $runnerAst = [Management.Automation.Language.Parser]::ParseFile(
        $runnerPath, [ref]$runnerTokens, [ref]$runnerErrors
    )
    $metricsFunction = $runnerAst.Find({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Get-ProcessTreeMetrics'
    }, $true)
    if ($null -eq $metricsFunction) {
        throw 'Get-ProcessTreeMetrics AST 없음'
    }
    Invoke-Expression $metricsFunction.Extent.Text
    $treeMetrics = Get-ProcessTreeMetrics -RootProcessId $PID
    if ($treeMetrics.Scope -ne 'descendant_tree') {
        throw "프로세스 트리 조회가 폴백됨: $($treeMetrics.Scope)"
    }
    if ($treeMetrics.ProcessCount -lt 1 -or
        $PID -notin @($treeMetrics.ProcessIds)) {
        throw "현재 PowerShell PID가 트리 집계에서 누락됨: $PID"
    }
    if ($treeMetrics.CpuSeconds -lt 0 -or
        $treeMetrics.WorkingSetBytes -le 0) {
        throw '프로세스 트리 CPU/RAM 집계값이 유효하지 않음'
    }
} catch {
    $failures.Add(
        "MFA 프로세스 트리 동적 검사 실패: $($_.Exception.Message)"
    )
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}
Write-Output "PowerShell safety checks PASS ($($files.Count) files)"
exit 0
