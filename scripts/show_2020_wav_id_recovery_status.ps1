# Read-only status dashboard for the 2020 WAV-ID recovery corpus build.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $projectRoot 'config\paths.json'
) -Raw -Encoding UTF8 | ConvertFrom-Json
function Resolve-ConfiguredPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}
$outputRoot = Resolve-ConfiguredPath ([string]$config.mfa_wav_corpus_2020)
$contractPath = Resolve-ConfiguredPath (
    [string]$config.mfa_wav_corpus_contract_2020
)
$progress = Join-Path $projectRoot (
    'logs\wav_recovery_2020_20260802_progress.jsonl'
)
$report = Join-Path $projectRoot (
    'outputs\reports\PREFLIGHT_2020_wav_recovery_corpus_20260802.json'
)
$lock = Join-Path (Split-Path -Parent $outputRoot) (
    'locks\wav_recovery_2020.lock'
)
$preflight = $null
if (Test-Path -LiteralPath $report -PathType Leaf) {
    $preflight = Get-Content -LiteralPath $report -Raw -Encoding UTF8 |
        ConvertFrom-Json
}
$latest = $null
if (
    $null -ne $preflight -and
    (Test-Path -LiteralPath $progress -PathType Leaf)
) {
    $expectedContractId = [string]$preflight.contract.corpus_contract_id
    $records = @(Get-Content -LiteralPath $progress -Encoding UTF8 | ForEach-Object {
        if (-not [string]::IsNullOrWhiteSpace($_)) {
            try { $_ | ConvertFrom-Json } catch {}
        }
    })
    $latest = $records | Where-Object {
        [string]$_.corpus_contract_id -eq $expectedContractId
    } | Select-Object -Last 1
}
$contract = $null
if (Test-Path -LiteralPath $contractPath -PathType Leaf) {
    $contract = Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
}
$lockData = $null
if (Test-Path -LiteralPath $lock -PathType Leaf) {
    try {
        $lockData = Get-Content -LiteralPath $lock -Raw -Encoding UTF8 |
            ConvertFrom-Json
    } catch {}
}
[pscustomobject]@{
    observed_at = (Get-Date).ToString('o')
    phase = if ($null -ne $contract -and $contract.status -eq 'passed') {
        'complete'
    } elseif ($null -ne $latest) {
        [string]$latest.event
    } elseif ($null -ne $preflight) {
        [string]$preflight.status
    } else {
        'not_started'
    }
    dry_run_status = if ($null -ne $preflight) {$preflight.status} else {$null}
    corpus_contract_id = if ($null -ne $contract -and $contract.status -eq 'passed') {
        $contract.corpus_contract_id
    } elseif ($null -ne $preflight) {
        $preflight.contract.corpus_contract_id
    } else {$null}
    preflight_contract_id = if ($null -ne $preflight) {
        $preflight.contract.corpus_contract_id
    } else {$null}
    expected_corpus_wavs = if ($null -ne $preflight) {
        $preflight.scan.corpus_entries
    } else {$null}
    omitted_for_review = if ($null -ne $preflight) {
        $preflight.scan.omitted_for_review
    } else {$null}
    progress_current = if ($null -ne $latest) {$latest.current} else {$null}
    progress_total = if ($null -ne $latest) {$latest.total} else {$null}
    progress_wav_files = if ($null -ne $latest) {$latest.wav_files} else {$null}
    lock_present = Test-Path -LiteralPath $lock
    lock_pid = if ($null -ne $lockData) {$lockData.pid} else {$null}
    final_contract_status = if ($null -ne $contract) {$contract.status} else {'pending'}
    final_corpus_wavs = if ($null -ne $contract) {$contract.wav_files} else {$null}
    source_wav_tree_untouched = if ($null -ne $contract) {
        $contract.source_wav_tree_untouched
    } else {$null}
    output_root = $outputRoot
    contract_path = $contractPath
} | Format-List
