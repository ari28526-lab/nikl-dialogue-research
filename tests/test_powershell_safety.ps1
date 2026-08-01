# PowerShell 실행기 정적 안전성 회귀 검사. 실제 MFA·데이터 작업은 실행하지 않는다.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$files = @(
    (Join-Path $root 'scripts\preflight_eojeol_realign.ps1'),
    (Join-Path $root 'scripts\run_eojeol_realign.ps1'),
    (Join-Path $root 'scripts\run_pre_mfa_bulk_safe.ps1'),
    (Join-Path $root 'scripts\run_mfa_year_queue_safe.ps1'),
    (Join-Path $root 'scripts\show_mfa_year_queue_status.ps1'),
    (Join-Path $root 'scripts\preflight_mfa_year_queue.ps1'),
    (Join-Path $root 'scripts\prepare_full_mfa_approval_reviews.ps1'),
    (Join-Path $root 'scripts\start_full_mfa_after_review.ps1'),
    (Join-Path $root 'scripts\prepare_mfa_year_exclusion_review.ps1'),
    (Join-Path $root 'scripts\run_stratified_mfa_pilot.ps1'),
    (Join-Path $root 'scripts\run_search_master.ps1'),
    (Join-Path $root 'scripts\initialize_common_pron_pilot.ps1'),
    (Join-Path $root 'scripts\run_common_pron_ab_pilot.ps1'),
    (Join-Path $root 'scripts\run_common_pron_mfa_r1.ps1'),
    (Join-Path $root 'scripts\run_common_pron_mfa_r2.ps1'),
    (Join-Path $root 'scripts\run_common_pron_difference_inventory.ps1'),
    (Join-Path $root 'scripts\show_common_pron_mfa_status.ps1'),
    (Join-Path $root 'scripts\archive_pre_jamo_outputs_to_external.ps1'),
    (Join-Path $root 'scripts\archive_pre_jamo_outputs_compressed.ps1'),
    (Join-Path $root 'scripts\archive_legacy_mfa_markers_for_r2.ps1'),
    (Join-Path $root 'scripts\run_mfa_r2_infrastructure_pilot.ps1'),
    (Join-Path $root (
        'scripts\prune_pre_jamo_outputs_after_compressed_archive.ps1'
    ))
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
            'export_mfa_db_research_6tier.py',
            'inspect_mfa_db_checkpoint.py',
            'direct_db_ready',
            'MFA DB 계산 체크포인트 재검증',
            'direct_db_ready count 불일치',
            'legacy 4-tier 병합으로 폴백하지 않음',
            'textgrid_research_v2_staging',
            'direct_db_research_6tier_v1',
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
            '[string]$CommonPronManifest',
            '[string]$CommonPronAdoptionContract',
            '[string]$CommonPronEquivalenceReport',
            '[string]$ApprovedExclusionsContract',
            '[switch]$ForceVerifyLabInput',
            'mfa_exclusion_contract.py',
            '--approved-exclusions-contract',
            'exact_id_reconciliation',
            '[switch]$AllowBaselineCommonPronRerun',
            '[switch]$AllowLegacyInlineG2p',
            '[switch]$AllowFullCleanRetry',
            'if ($AllowFullCleanRetry) { $tries += $true }',
            'explicit_full_clean_retry_after_resume_failure',
            '연도 전체 자동 재계산 금지',
            '[int]$BulkWrapperPid = 0',
            "owner_mode = 'direct_runner'",
            "owner_mode -ne 'bulk_wrapper'",
            '공통 G2P/r2 생성과 MFA 동시 실행 금지',
            '$ownsDirectLock',
            '2020·2021은 전수 동등성 baseline으로 보존함',
            'common_pron_mfa_adoption.v3',
            'latest_jamo_common_dictionary_required',
            'allow_yearly_mfa',
            'verify_frozen_mfa_bundle.py',
            'korean_mfa_latest_jamo_bundle_20260728.json',
            '$useInlineG2p = $false',
            "'-ExpectedPronunciationMode', `$pronunciationMode",
            'tier_provenance = [ordered]@{',
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
            "direct DB align marker",
            'marker 삭제·재정렬 금지',
            '$directFinalPresent',
            'final staging은 있으나 완료 marker가 전무함'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("MFA preflight 복구 안전장치 누락: $required")
            }
        }
        foreach ($required in @(
            '[string]$Year',
            'textgrid_eojeol_staging',
            'textgrid_research_v2_staging',
            'inspect_mfa_db_checkpoint.py',
            '[switch]$PreferD',
            'PreferD: D:',
            '[string]$ExpectedPronunciationMode',
            '$ExpectedPronunciationMode',
            '러너는 D:를 우선'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("MFA preflight 연도/staging 가드 누락: $required")
            }
        }
    }
    if (
        (Split-Path $path -Leaf) -eq
        'run_mfa_r2_infrastructure_pilot.ps1'
    ) {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            'common_pron_mfa_r2_latest_jamo',
            'validate_mfa_r2_adoption.py',
            'MFA_PROJECT_SKIP_TEXTGRID_EXPORT',
            'export_mfa_db_4tier.py',
            'audit_mfa_4tier_year.py',
            'verify_mfa_db_4tier_sample.py',
            'build_mfa_year_phone_inventory.py',
            'audit_mfa_cross_year_contracts.py',
            'package_mfa_r2_pilot_review.py',
            'pron_reference_form',
            'inline_g2p_used = $false',
            "researcher_review_status = 'pending'",
            'realization_judgment_performed = $false',
            'ReviewRoot must be one direct child folder of Dropbox',
            'Review folder already exists; no overwrite',
            'D: volume label must be DATA_SSD'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("MFA r2 pilot safety token missing: $required")
            }
        }
        if ($text.Contains("'--g2p_model_path'")) {
            $failures.Add(
                'MFA r2 pilot must not use inline --g2p_model_path'
            )
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
            '[string]$CommonPronManifest',
            '[string]$CommonPronAdoptionContract',
            '[string]$CommonPronEquivalenceReport',
            '[switch]$AllowBaselineCommonPronRerun',
            '[switch]$AllowLegacyInlineG2p',
            '[switch]$AllowFullCleanRetry',
            "'-AllowFullCleanRetry'",
            'allow_full_clean_retry = [bool]$AllowFullCleanRetry',
            "'-CommonPronManifest'",
            "'-CommonPronAdoptionContract'",
            "'-AllowBaselineCommonPronRerun'",
            "'-BulkWrapperPid'",
            "owner_mode = 'bulk_wrapper'",
            'if ($PreferD)',
            "'-PreferD'",
            'prefer_d = [bool]$PreferD',
            'run_eojeol_realign.ps1',
            '[string]$PauseAfterYear',
            '[Parameter(Mandatory=$true)]',
            '$Years.Count -ne 1',
            '-Years는 한 연도만 허용함',
            '$Years[0] -notin @(''2020'', ''2021'')',
            'allow_baseline_common_pron_rerun = [bool]$AllowBaselineCommonPronRerun',
            "status = 'paused'",
            'paused_after_year',
            '$yearExitCode -eq 75'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("pre-MFA 안전 wrapper D 우선 가드 누락: $required")
            }
        }
    }
    if ((Split-Path $path -Leaf) -eq 'run_mfa_year_queue_safe.ps1') {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            'mfa_r2_unattended_year_queue.v1',
            'no_automatic_full_clean_retry = $true',
            '연구자 승인 제외 계약이 없으면 후보표만 만들고',
            '연구자 인프라 검토와 정본 승격은 자동 수행하지 않는다',
            'prepare_mfa_year_exclusion_review.ps1',
            'run_pre_mfa_bulk_safe.ps1',
            'audit_mfa_research_6tier_year.py',
            'verify_mfa_db_research_6tier_sample.py',
            'mfa_failed_checkpoint_preserved',
            'machine_qc_failed_outputs_preserved',
            'machine_qc_passed_human_review_pending',
            '의도적으로 -AllowFullCleanRetry를 전달하지 않는다',
            'canonical_promotion_automatic = $false',
            'researcher_approval_automatic = $false',
            'Write-JsonAtomic',
            'mfa_year_queue.lock'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("연도 무인 큐 안전장치 누락: $required")
            }
        }
        if ($text -match '\$runArgs\s*\+=\s*''-AllowFullCleanRetry''') {
            $failures.Add('연도 무인 큐가 full clean retry를 전달함')
        }
    }
    if ((Split-Path $path -Leaf) -eq 'show_mfa_year_queue_status.ps1') {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            'read-only dashboard',
            'mfa_year_queue.lock',
            'queue_state.json',
            'machine_qc_passed_human_review_pending',
            '이 상태판은 파일이나 프로세스를 변경하지 않음'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("연도 큐 상태판 안전장치 누락: $required")
            }
        }
        if ($text -match (
            '(?im)^\s*(Remove-Item|Move-Item|Rename-Item|Stop-Process|' +
            'Start-Process|Set-Content|Add-Content|Out-File|Tee-Object)\b'
        )) {
            $failures.Add('연도 큐 상태판에 상태 변경 명령이 포함됨')
        }
    }
    if ((Split-Path $path -Leaf) -eq 'preflight_mfa_year_queue.ps1') {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            'mfa_r2_full_year_queue_preflight.v1',
            'validate_mfa_r2_adoption.py',
            'preflight_eojeol_realign.ps1',
            'mfa_exclusion_contract.py',
            'test_powershell_safety.ps1',
            'python_full_test_suite',
            'tracked_code_committed',
            "`$env:PYTHONUTF8 = '1'",
            "`$finalStatus = if (`$failed.Count -eq 0) { 'GO' } else { 'NO_GO' }",
            'status = $finalStatus',
            '$checkRows = @($checks | ForEach-Object { $_ })',
            'starts_mfa = $false',
            'approves_exclusions = $false',
            'promotes_canonical_outputs = $false'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("연도 큐 최종 preflight 누락: $required")
            }
        }
        if ($text -match '(?im)^\s*(Start-Process|Stop-Process)\b') {
            $failures.Add('연도 큐 최종 preflight가 MFA 프로세스를 시작/중단함')
        }
    }
    if (
        (Split-Path $path -Leaf) -eq
        'prepare_full_mfa_approval_reviews.ps1'
    ) {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            'prepare_mfa_year_exclusion_review.ps1',
            'existing_review_preserved',
            '자동 덮어쓰기 금지',
            'starts_mfa = $false',
            'moves_wav = $false',
            'approves_exclusions = $false',
            'promotes_canonical_outputs = $false'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("전수 승인자료 준비 가드 누락: $required")
            }
        }
        if ($text.Contains('run_mfa_year_queue_safe.ps1')) {
            $failures.Add('승인자료 준비기가 MFA 연도 큐를 호출함')
        }
    }
    if (
        (Split-Path $path -Leaf) -eq
        'start_full_mfa_after_review.ps1'
    ) {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            'mfa_exclusion_contract.py',
            'preflight_mfa_year_queue.ps1',
            "[string]`$preflight.status -ne 'GO'",
            '[bool]$preflight.starts_mfa -ne $false',
            'run_mfa_year_queue_safe.ps1',
            '-RunRepositoryTests',
            '의도적으로 -AllowFullCleanRetry와 -PrepareMissingReviews를 전달하지 않는다',
            '연도 전체 자동 clean 재계산·자동 정본 승격은 금지'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("승인 후 전수 시작 가드 누락: $required")
            }
        }
        if ($text -match "`$queueArgs\s*\+=.*AllowFullCleanRetry") {
            $failures.Add('승인 후 전수 시작기가 full clean retry를 전달함')
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
            '$previousErrorActionPreference',
            "`$ErrorActionPreference = 'Continue'",
            '$mfaExitCode = $LASTEXITCODE',
            'mfa_3_4_optional_probability_columns_v1',
            "PSObject.Properties[",
            'registry_before_dictionary_probability_fix',
            'comparison_done.json',
            '아직 정책을 채택하지 않음',
            '기존 2020/2021 결과와 canonical CSV/TextGrid는 수정하지 않음'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("공통 발음 A/B 러너 안전장치 누락: $required")
            }
        }
    }
    if ((Split-Path $path -Leaf) -eq 'run_common_pron_mfa_r1.ps1') {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        if ($text -notmatch '(?s)\$incomplete\s*=\s*@\(\s*@\(') {
            $failures.Add(
                '공통 MFA r1의 빈 incomplete 목록이 StrictMode에서 ' +
                '$null.Count로 실패할 수 있음'
            )
        }
        foreach ($required in @(
            "D:\mfa_common_pron",
            "VolumeLabel -ne 'DATA_SSD'",
            'pre_mfa_bulk.lock',
            '정책: 기본사전 보존 + 동일 G2P 1-best만',
            '--num_pronunciations',
            "'1'",
            '--strict_graphemes',
            'attested_dictionary_variants_added',
            'phone_outside_acoustic_inventory',
            'audit_common_pron_mfa_equivalence.py',
            '2020 TextGrid 866,196개 + 2021 완성 DB',
            'no_phone_standard_change',
            'requires_2020_pass',
            'requires_2020_partial_db_auxiliary_pass',
            'requires_2021_pass',
            'allow_common_dictionary_for_2022',
            'Archive-Incomplete'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("공통 MFA 사전 r1 안전장치 누락: $required")
            }
        }
    }
    if ((Split-Path $path -Leaf) -eq 'run_common_pron_mfa_r2.ps1') {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            "D:\mfa_common_pron",
            "VolumeLabel -ne 'DATA_SSD'",
            'pre_mfa_bulk.lock',
            'verify_frozen_mfa_bundle.py',
            'korean_mfa_latest_jamo_bundle_20260728.json',
            'acoustic v3.3.0 + Jamo G2P v3.2.0',
            '--strict_graphemes',
            'g2p_unsupported_other_words',
            'g2p_jamo_ls_rewrite_words',
            'U+11B3 정확히 4어절',
            'restore-jamo-ls',
            'jamo_ls_researcher_review.csv',
            'common_pron_no_path_review.py',
            'finalize_common_pron_no_path_method.py',
            'g2p_no_path_researcher_review.csv',
            'partial 보존·승인 대기',
            '다음 shard로 계속',
            '전체 shard 계산은 계속했지만 final은 보류',
            'no-path 방법론 supplement 실패',
            'g2p_existing_model_pronunciations_replaced',
            '미등록 누락어',
            '기존 모델 출력은 대체하지 않는다',
            'r2 사전 실물은 아직 없음',
            '연도별 MFA 사용 승인은 아님',
            'Acquire-Lock',
            'Release-Lock',
            'MFA/G2P/archive 동시 실행 금지',
            'exit 76'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("공통 MFA 사전 r2 안전장치 누락: $required")
            }
        }
    }
    if (
        (Split-Path $path -Leaf) -eq
            'run_common_pron_difference_inventory.ps1'
    ) {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            "D:\mfa_common_pron",
            "VolumeLabel -ne 'DATA_SSD'",
            'pre_mfa_bulk.lock',
            'common_pron_mfa_difference_inventory.lock',
            '--checkpoint-2020',
            '--checkpoint-every-batches',
            'checkpoint는 보존됨',
            'SetThreadExecutionState',
            'Enable-SleepGuard',
            'Disable-SleepGuard',
            'difference_inventory_complete',
            'common_release.manifest.sha256',
            'allow_yearly_mfa -ne $false',
            '기존 차이 inventory 재검증',
            '아직 adoption·연도별 MFA 승인이 아님',
            'Acquire-Lock',
            'Release-Lock'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add(
                    "공통 발음 차이감사 안전장치 누락: $required"
                )
            }
        }
    }
    if ((Split-Path $path -Leaf) -eq 'show_common_pron_mfa_status.ps1') {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            'Read-only status dashboard',
            '[IO.FileShare]::ReadWrite',
            "status -eq 'success'",
            'missing',
            'extras',
            'spn_words',
            'phone_outside_acoustic_inventory',
            '[IO.DriveInfo]::new',
            'lock_process_alive',
            'allow_yearly_mfa',
            'jamo_ls_candidate_words',
            '$sessionVerifiedWords',
            '$sessionVerifiedWords = [int64]0',
            'foreach ($record in @($verifiedReportRecords))',
            'unverified_output_words',
            'approval_pending_shards',
            'approval_pending_words',
            'unknown_missing_shards',
            'unknown_missing_words',
            'g2p_review_blocked_not_running',
            'difference_inventory_status',
            'difference_inventory_running',
            'difference_inventory_interrupted_resumable',
            'difference_checkpoint_status',
            'difference_lock_process_alive'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("공통 MFA 상태판 안전장치 누락: $required")
            }
        }
        if ($text -match (
            '(?im)^\s*(Remove-Item|Move-Item|Rename-Item|Stop-Process|' +
            'Start-Process|Set-Content|Add-Content|Out-File|Tee-Object)\b'
        )) {
            $failures.Add('공통 MFA 상태판에 쓰기·제어 명령이 포함됨')
        }
    }
    if (
        (Split-Path $path -Leaf) -eq
            'archive_pre_jamo_outputs_to_external.ps1'
    ) {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            "D:는 메인 작업 드라이브",
            'READ_ONLY_ARCHIVE',
            'Assert-ExactSource',
            'archive 원본 allowlist 위반',
            'robocopy zero-diff plus file-count and byte-count',
            'if ($diffCode -ne 0)',
            '2021.db SHA256 불일치',
            '[switch]$PruneAfterVerify',
            'Remove-Item -LiteralPath $confirmed -Recurse -Force'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add("외장 archive 안전장치 누락: $required")
            }
        }
    }
    if (
        (Split-Path $path -Leaf) -eq
            'archive_pre_jamo_outputs_compressed.ps1'
    ) {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            'D:는 메인 작업 드라이브',
            'compressed archive 원본 allowlist 위반',
            '7z CRC 전수 검사 실패',
            'Get-AllDatabaseHashes',
            'source_pruning_supported = $false',
            'archive_sha256',
            'manifest 없는 최종 archive 덮어쓰기 금지'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add(
                    "압축 외장 archive 안전장치 누락: $required"
                )
            }
        }
        if ($text -match '(?im)^\s*Remove-Item\b') {
            $failures.Add('압축 외장 archive에 삭제 명령이 포함됨')
        }
    }

    if (
        (Split-Path $path -Leaf) -eq
        'archive_legacy_mfa_markers_for_r2.ps1'
    ) {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            '[switch]$Apply',
            'ARCHIVE_LEGACY_MFA_MARKERS_R2_20260730',
            'r2_transition_20260730_legacy_markers',
            "align_merge_only = `$true",
            "lab_input_markers_moved = `$false",
            "action = 'retain_in_place'",
            "Move-Item -LiteralPath",
            "deletion_used = `$false",
            "raw_corpus_modified = `$false"
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add(
                    "legacy MFA marker archive 안전 계약 누락: $required"
                )
            }
        }
        if ($text -match 'Remove-Item') {
            $failures.Add(
                'legacy MFA marker archive에 삭제 명령이 포함됨'
            )
        }
    }

    if (
        (Split-Path $path -Leaf) -eq
        'prune_pre_jamo_outputs_after_compressed_archive.ps1'
    ) {
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        foreach ($required in @(
            '[switch]$Apply',
            'DELETE_VERIFIED_PRE_JAMO_20260730',
            'exact_source_allowlist_only',
            'all_archives_rehashed_before_delete',
            'all_sources_remeasured_before_delete',
            'all_database_hashes_rechecked_before_delete',
            'Assert-ExactSource',
            'Remove-Item -LiteralPath $source -Recurse -Force'
        )) {
            if (-not $text.Contains($required)) {
                $failures.Add(
                    "pre-Jamo prune 안전 계약 누락: $required"
                )
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
