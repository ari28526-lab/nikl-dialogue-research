# PowerShell 실행기 정적 안전성 회귀 검사. 실제 MFA·데이터 작업은 실행하지 않는다.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$files = @(
    (Join-Path $root 'scripts\preflight_eojeol_realign.ps1'),
    (Join-Path $root 'scripts\run_eojeol_realign.ps1'),
    (Join-Path $root 'scripts\run_pre_mfa_bulk_safe.ps1'),
    (Join-Path $root 'scripts\run_stratified_mfa_pilot.ps1'),
    (Join-Path $root 'scripts\run_search_master.ps1'),
    (Join-Path $root 'scripts\initialize_common_pron_pilot.ps1'),
    (Join-Path $root 'scripts\run_common_pron_ab_pilot.ps1')
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
            '$mfaReportedDone',
            "'finalizing'",
            'tree_cpu_seconds',
            'tree_live_cpu_seconds',
            'tree_retired_cpu_seconds',
            'metrics_scope',
            'tree_python_process_count',
            'tree_thread_count',
            'tree_working_set_mb',
            'tree_private_memory_mb',
            'Get-SystemMemoryMetrics',
            'system_memory_available_mb',
            'system_commit_used_gb',
            'system_commit_limit_gb',
            'system_commit_percent',
            'memory_pressure_warning',
            'Update-AlignmentLogProgress',
            'alignment_processed',
            'alignment_retried',
            'alignment_error_signals',
            'alignment_job_processed',
            'alignment_log_latest_write_utc',
            'Update-IntervalCsvProgress',
            'interval_phone_rows',
            'interval_word_rows',
            'interval_word_utterances',
            'interval_word_utterance_pct',
            'interval_phone_bytes',
            'interval_word_bytes',
            'interval_latest_write_utc',
            'MFA_PROJECT_SKIP_TEXTGRID_EXPORT',
            'export_mfa_db_4tier.py',
            '_partial_direct_db',
            'direct_merge_completed_temp_retained_for_qc',
            'build_mfa_alignment_contract.py',
            '$dictionaryModelPath, $acousticModelPath',
            "'--g2p_model_path', `$g2pModelPath",
            'alignment_contract_id',
            'lab_input_contract_id',
            'mfa_models',
            'audit_mfa_year_readiness.py',
            '--gate-profile',
            '$trustedResumeTemp',
            "'analysis_ready_gates_pass'",
            'input_integrity_execution_gates_pass',
            'input_integrity_analysis_ready_gates_pass',
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
            '$alignExportMode',
            "direct_db_4tier align marker",
            'marker 삭제·재정렬 금지'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("MFA preflight 복구 안전장치 누락: $required")
            }
        }
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
            '[Parameter(Mandatory=$true)]',
            '$Years.Count -ne 1',
            '-Years는 한 연도만 허용함',
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
    if ((Split-Path $path -Leaf) -eq 'initialize_common_pron_pilot.ps1') {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            '[CmdletBinding(SupportsShouldProcess)]',
            'common_pron_home',
            "D:\mfa_common_pron",
            "VolumeLabel -ne 'DATA_SSD'",
            'MinimumFreeGiB',
            'pre_mfa_bulk.lock',
            '기존 release를 덮어쓰지 않음',
            'raw_corpus_read_only',
            'baseline_2020_2021_read_only',
            'no_automatic_cleanup',
            'vocabulary_and_registry_use_all_six_years',
            "'would_initialize'"
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("공통 발음 파일럿 초기화 안전장치 누락: $required")
            }
        }
    }
    if ((Split-Path $path -Leaf) -eq 'run_common_pron_ab_pilot.ps1') {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            "D:\mfa_common_pron",
            "VolumeLabel -ne 'DATA_SSD'",
            'pre_mfa_bulk.lock',
            'verify_mfa_install.py',
            'common_pron_ab_pilot.py',
            '--num_pronunciations',
            "'1'",
            '--strict_graphemes',
            '--no_tokenization',
            'policy_A_baseline_cache.dict',
            'policy_B_attested_variants.dict',
            'Archive-Incomplete',
            'comparison_done.json',
            '아직 정책을 채택하지 않음',
            '기존 2020/2021 결과와 canonical CSV/TextGrid는 수정하지 않음'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("공통 발음 A/B 러너 안전장치 누락: $required")
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
    $accumulatorFunction = $runnerAst.Find({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Update-ProcessTreeCpuAccumulator'
    }, $true)
    if ($null -eq $accumulatorFunction) {
        throw 'Update-ProcessTreeCpuAccumulator AST 없음'
    }
    $alignmentProgressFunction = $runnerAst.Find({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Update-AlignmentLogProgress'
    }, $true)
    if ($null -eq $alignmentProgressFunction) {
        throw 'Update-AlignmentLogProgress AST 없음'
    }
    $memoryMetricsFunction = $runnerAst.Find({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Get-SystemMemoryMetrics'
    }, $true)
    if ($null -eq $memoryMetricsFunction) {
        throw 'Get-SystemMemoryMetrics AST 없음'
    }
    $intervalProgressFunction = $runnerAst.Find({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Update-IntervalCsvProgress'
    }, $true)
    if ($null -eq $intervalProgressFunction) {
        throw 'Update-IntervalCsvProgress AST 없음'
    }
    Invoke-Expression $metricsFunction.Extent.Text
    Invoke-Expression $accumulatorFunction.Extent.Text
    Invoke-Expression $alignmentProgressFunction.Extent.Text
    Invoke-Expression $memoryMetricsFunction.Extent.Text
    Invoke-Expression $intervalProgressFunction.Extent.Text
    $treeMetrics = Get-ProcessTreeMetrics -RootProcessId $PID
    if ($treeMetrics.Scope -ne 'descendant_tree') {
        throw "프로세스 트리 조회가 폴백됨: $($treeMetrics.Scope)"
    }
    if ($treeMetrics.ProcessCount -lt 1 -or
        $PID -notin @($treeMetrics.ProcessIds)) {
        throw "현재 PowerShell PID가 트리 집계에서 누락됨: $PID"
    }
    if (-not $treeMetrics.CpuByPid.ContainsKey([string]$PID)) {
        throw "현재 PowerShell PID별 CPU가 집계에서 누락됨: $PID"
    }
    if ($treeMetrics.CpuSeconds -lt 0 -or
        $treeMetrics.WorkingSetBytes -le 0 -or
        $treeMetrics.PrivateMemoryBytes -le 0 -or
        $treeMetrics.ThreadCount -lt 1) {
        throw '프로세스 트리 CPU/RAM 집계값이 유효하지 않음'
    }
    $systemMemory = Get-SystemMemoryMetrics
    if (-not $systemMemory.Available -or
        $systemMemory.AvailableMemoryMB -le 0 -or
        $systemMemory.CommitUsedGB -le 0 -or
        $systemMemory.CommitLimitGB -le $systemMemory.CommitUsedGB -or
        $systemMemory.CommitPercent -le 0 -or
        $systemMemory.CommitPercent -ge 100) {
        throw '시스템 물리/commit 메모리 집계값이 유효하지 않음'
    }

    $cpuState1 = Update-ProcessTreeCpuAccumulator `
        -CurrentCpuByPid @{'1'=10.0; '2'=20.0}
    $cpuState2 = Update-ProcessTreeCpuAccumulator `
        -PreviousCpuByPid $cpuState1.CpuByPid `
        -CurrentCpuByPid @{'1'=15.0} `
        -RetiredCpuSeconds $cpuState1.RetiredCpuSeconds
    $cpuState3 = Update-ProcessTreeCpuAccumulator `
        -PreviousCpuByPid $cpuState2.CpuByPid `
        -CurrentCpuByPid @{'1'=2.0} `
        -RetiredCpuSeconds $cpuState2.RetiredCpuSeconds
    $cpuState4 = Update-ProcessTreeCpuAccumulator `
        -PreviousCpuByPid $cpuState3.CpuByPid `
        -CurrentCpuByPid @{} `
        -RetiredCpuSeconds $cpuState3.RetiredCpuSeconds
    if ($cpuState1.TotalCpuSeconds -ne 30.0 -or
        $cpuState2.TotalCpuSeconds -ne 35.0 -or
        $cpuState2.RetiredCpuSeconds -ne 20.0 -or
        $cpuState3.TotalCpuSeconds -ne 37.0 -or
        $cpuState3.RetiredCpuSeconds -ne 35.0 -or
        $cpuState4.TotalCpuSeconds -ne 37.0) {
        throw '종료/PID 재사용 뒤 프로세스 트리 CPU 누적치가 단조 증가하지 않음'
    }

    $logTestRoot = Join-Path ([IO.Path]::GetTempPath()) (
        'mfa_alignment_progress_' + [Guid]::NewGuid().ToString('N')
    )
    try {
        [void](New-Item -ItemType Directory -Path $logTestRoot)
        $utf8NoBom = New-Object Text.UTF8Encoding($false)
        $align1 = Join-Path $logTestRoot 'align.1.log'
        $align2 = Join-Path $logTestRoot 'align.2.log'
        [IO.File]::WriteAllText(
            $align1,
            (
                "t - DEBUG - Processing a`r`n" +
                "t - DEBUG - Retried a`r`n" +
                "t - DEBUG - Pro"
            ),
            $utf8NoBom
        )
        $alignProgress1 = Update-AlignmentLogProgress `
            -LogDirectory $logTestRoot
        if ($alignProgress1.Processed -ne 1 -or
            $alignProgress1.Retried -ne 1 -or
            $alignProgress1.ErrorSignals -ne 0 -or
            $alignProgress1.State['align.1.log'].Carry -ne
                't - DEBUG - Pro') {
            throw '정렬 로그 첫 증분/미완성 행 집계 실패'
        }

        [IO.File]::AppendAllText(
            $align1,
            "cessing b`r`nt - ERROR - synthetic`r`n",
            $utf8NoBom
        )
        [IO.File]::WriteAllText(
            $align2,
            "t - DEBUG - Processing c`r`n",
            $utf8NoBom
        )
        $alignProgress2 = Update-AlignmentLogProgress `
            -LogDirectory $logTestRoot `
            -PreviousState $alignProgress1.State
        if ($alignProgress2.Processed -ne 3 -or
            $alignProgress2.Retried -ne 1 -or
            $alignProgress2.ErrorSignals -ne 1 -or
            $alignProgress2.JobProcessed['align.1.log'] -ne 2 -or
            $alignProgress2.JobProcessed['align.2.log'] -ne 1) {
            throw '정렬 로그 증분·job별 집계 실패'
        }

        # --clean/retry로 한 로그가 짧아진 경우 해당 파일 누적만 리셋한다.
        [IO.File]::WriteAllText(
            $align1,
            "t - DEBUG - Processing replacement`r`n",
            $utf8NoBom
        )
        $alignProgress3 = Update-AlignmentLogProgress `
            -LogDirectory $logTestRoot `
            -PreviousState $alignProgress2.State
        if ($alignProgress3.Processed -ne 2 -or
            $alignProgress3.Retried -ne 0 -or
            $alignProgress3.ErrorSignals -ne 0) {
            throw '정렬 로그 교체 뒤 파일별 누적 리셋 실패'
        }

        $phoneCsv = Join-Path $logTestRoot 'phone_intervals.csv'
        $wordCsv = Join-Path $logTestRoot 'word_intervals.csv'
        [IO.File]::WriteAllText(
            $phoneCsv,
            "id,value`r`n1,a`r`n2,b",
            $utf8NoBom
        )
        [IO.File]::WriteAllText(
            $wordCsv,
            (
                "id,begin,end,utterance_id,word_id,pronunciation_id`r`n" +
                "1,0,1,77,2,3`r`n"
            ),
            $utf8NoBom
        )
        $intervalProgress1 = Update-IntervalCsvProgress `
            -AlignmentDirectory $logTestRoot
        if ($intervalProgress1.PhoneRows -ne 1 -or
            $intervalProgress1.WordRows -ne 1 -or
            $intervalProgress1.WordUtterances -ne 1 -or
            $intervalProgress1.PhoneBytes -le 0 -or
            $intervalProgress1.WordBytes -le 0 -or
            $null -eq $intervalProgress1.LatestWriteUtc) {
            throw 'interval CSV 첫 증분·부분행 집계 실패'
        }

        [IO.File]::AppendAllText(
            $phoneCsv,
            "`r`n3,c`r`n",
            $utf8NoBom
        )
        $intervalProgress2 = Update-IntervalCsvProgress `
            -AlignmentDirectory $logTestRoot `
            -PreviousState $intervalProgress1.State
        if ($intervalProgress2.PhoneRows -ne 3 -or
            $intervalProgress2.WordRows -ne 1 -or
            $intervalProgress2.WordUtterances -ne 1) {
            throw 'interval CSV 후속 증분 집계 실패'
        }

        [IO.File]::WriteAllText(
            $phoneCsv,
            "id,value`r`n9,z`r`n",
            $utf8NoBom
        )
        $intervalProgress3 = Update-IntervalCsvProgress `
            -AlignmentDirectory $logTestRoot `
            -PreviousState $intervalProgress2.State
        if ($intervalProgress3.PhoneRows -ne 1 -or
            $intervalProgress3.WordRows -ne 1 -or
            $intervalProgress3.WordUtterances -ne 1) {
            throw 'interval CSV 교체 뒤 파일별 누적 리셋 실패'
        }
    } finally {
        if (Test-Path -LiteralPath $logTestRoot) {
            Remove-Item -LiteralPath $logTestRoot -Recurse -Force
        }
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
