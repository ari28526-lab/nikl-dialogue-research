# MFA r2 infrastructure acceptance pilot.
# Scratch stays isolated on D:. Only a verified flat review bundle is promoted
# to one Dropbox folder. This pilot does not judge phonological realization.
# LAB source is the frozen search-master pron_reference_form.

param(
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string[]]$Years = @('2020','2021','2022','2023','2024','2025'),
    [ValidateRange(1,100)]
    [int]$UtterancesPerYear = 10,
    [ValidateRange(1,50)]
    [int]$SpeakersPerYear = 5,
    [ValidateRange(1,16)]
    [int]$NumJobs = 4,
    [string]$RunId = 'mfa_r2_infra_pilot_20260730',
    [string]$CommonPronManifest = (
        'D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\' +
        '00_contract\release_manifest.json'
    ),
    [string]$CommonPronAdoptionContract = (
        'D:\mfa_common_pron\releases\common_pron_mfa_r2_20260728\' +
        '00_contract\adoption_contract.json'
    ),
    [string]$ReviewRoot = (
        "$env:USERPROFILE\Dropbox\MFA_R2_INFRA_PILOT_20260730"
    )
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $projectRoot 'config\paths.json'
$cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 |
       ConvertFrom-Json
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

function Expand-ConfigPath([string]$Value) {
    return [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
    )
}
function Say([string]$Message) {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message)
}
function Write-Json([string]$Path, [object]$Value) {
    $temp = "$Path.$PID.partial"
    $Value | ConvertTo-Json -Depth 12 |
        Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $Path -Force
}
function Test-StageMarker(
    [string]$Path,
    [string]$Year,
    [string]$Stage,
    [string]$AlignmentContractId
) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    try {
        $data = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 |
                ConvertFrom-Json
        return (
            $data.run_id -eq $RunId -and
            $data.year -eq $Year -and
            $data.stage -eq $Stage -and
            $data.pronunciation_mode -eq
                'common_pron_mfa_r2_latest_jamo' -and
            $data.alignment_contract_id -eq $AlignmentContractId
        )
    } catch {
        return $false
    }
}

if ($UtterancesPerYear % $SpeakersPerYear -ne 0) {
    throw 'UtterancesPerYear must be a multiple of SpeakersPerYear.'
}
if ($RunId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
    throw "Unsafe RunId: $RunId"
}
$dLabel = ([IO.DriveInfo]::new('D:\')).VolumeLabel
if ($dLabel -ne 'DATA_SSD') {
    throw "D: volume label must be DATA_SSD (actual=$dLabel)."
}

$scratchBase = 'D:\mfa_eojeol\pilots\r2_infrastructure'
$runRoot = [IO.Path]::GetFullPath((Join-Path $scratchBase $RunId))
$allowedScratch = [IO.Path]::GetFullPath($scratchBase).TrimEnd('\') + '\'
if (-not $runRoot.StartsWith(
    $allowedScratch, [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Scratch boundary violation: $runRoot"
}
$dropboxRoot = [IO.Path]::GetFullPath("$env:USERPROFILE\Dropbox").TrimEnd('\')
$reviewFull = [IO.Path]::GetFullPath($ReviewRoot).TrimEnd('\')
if (
    [IO.Path]::GetDirectoryName($reviewFull) -ne $dropboxRoot -or
    $reviewFull -eq $dropboxRoot
) {
    throw "ReviewRoot must be one direct child folder of Dropbox: $reviewFull"
}
if (Test-Path -LiteralPath $reviewFull) {
    throw "Review folder already exists; no overwrite: $reviewFull"
}

$py = Expand-ConfigPath ([string]$cfg.pipeline_python)
$envRoot = Join-Path $env:USERPROFILE 'miniforge3\envs\mfa'
$mfa = Join-Path $envRoot 'Scripts\mfa.exe'
$env:Path = (
    "$envRoot;$envRoot\Library\bin;$envRoot\Scripts;$envRoot\bin;" +
    $env:Path
)
$pydir = Join-Path $PSScriptRoot 'python'
$required = @(
    $py,
    $mfa,
    $CommonPronManifest,
    $CommonPronAdoptionContract,
    (Join-Path $pydir 'validate_mfa_r2_adoption.py'),
    (Join-Path $pydir 'verify_mfa_install.py'),
    (Join-Path $pydir 'build_stratified_mfa_pilot.py'),
    (Join-Path $pydir 'build_mfa_alignment_contract.py'),
    (Join-Path $pydir 'export_mfa_db_4tier.py'),
    (Join-Path $pydir 'audit_mfa_4tier_year.py'),
    (Join-Path $pydir 'verify_mfa_db_4tier_sample.py'),
    (Join-Path $pydir 'build_mfa_year_phone_inventory.py'),
    (Join-Path $pydir 'audit_mfa_cross_year_contracts.py'),
    (Join-Path $pydir 'package_mfa_r2_pilot_review.py')
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required file missing: $path"
    }
}

New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
$lockPath = Join-Path $runRoot '.pilot.lock'
try {
    $lock = [IO.File]::Open(
        $lockPath,
        [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,
        [IO.FileShare]::None
    )
    $lock.Dispose()
} catch {
    throw "Pilot lock already present: $lockPath"
}

try {
    $stateDir = Join-Path $runRoot 'state'
    $logsDir = Join-Path $runRoot 'logs'
    $contractsDir = Join-Path $runRoot 'contracts'
    $phoneDir = Join-Path $runRoot 'phone_inventory'
    $tempRoot = Join-Path $runRoot 'temp'
    $textgridRoot = Join-Path $runRoot 'textgrid_4tier'
    foreach ($path in @(
        $stateDir, $logsDir, $contractsDir, $phoneDir, $tempRoot
    )) {
        New-Item -ItemType Directory -Force -Path $path | Out-Null
    }

    $adoptionValidation = Join-Path $stateDir 'r2_adoption_validation.json'
    & $py (Join-Path $pydir 'validate_mfa_r2_adoption.py') `
        --manifest $CommonPronManifest `
        --adoption-contract $CommonPronAdoptionContract `
        --output $adoptionValidation
    if ($LASTEXITCODE -ne 0) {
        throw 'MFA r2 adoption validation failed.'
    }
    $r2 = Get-Content -LiteralPath $adoptionValidation -Raw -Encoding UTF8 |
          ConvertFrom-Json
    $dictionary = [string]$r2.dictionary.path
    $acoustic = [string]$r2.acoustic_model.path
    $g2pReference = [string]$r2.g2p_model_reference_only.path
    $frozenBundle = [string]$r2.frozen_model_bundle_contract.path

    $installReport = Join-Path $stateDir 'mfa_install_validation.json'
    & $py (Join-Path $pydir 'verify_mfa_install.py') `
        --json-output $installReport
    if ($LASTEXITCODE -ne 0) {
        throw 'MFA local safety patch validation failed.'
    }

    $buildArgs = @(
        (Join-Path $pydir 'build_stratified_mfa_pilot.py'),
        '--run-root', $runRoot,
        '--utterances-per-year', "$UtterancesPerYear",
        '--speakers-per-year', "$SpeakersPerYear",
        '--seed', 'mfa_r2_infrastructure_pilot_v1',
        '--search-root', (
            Expand-ConfigPath ([string]$cfg.pre_mfa_search_master)
        ),
        '--years'
    ) + $Years
    & $py @buildArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Pilot sample and frozen CSV build failed.'
    }
    $sessionHashes = Get-Content -LiteralPath (
        Join-Path $runRoot 'search_master\_session_hashes.json'
    ) -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($sessionHashes.status -ne 'success') {
        throw 'Frozen pilot search-master hashes are not successful.'
    }
    $labInputContractId = [string]$sessionHashes.aggregate_sha256

    foreach ($year in $Years) {
        Say "START year=$year"
        $contractPath = Join-Path $contractsDir "$year.json"
        & $py (Join-Path $pydir 'build_mfa_alignment_contract.py') `
            --year $year `
            --lab-input-contract-id $labInputContractId `
            --acoustic-model-path $acoustic `
            --dictionary-model-path $dictionary `
            --g2p-model-path $g2pReference `
            --acoustic-model-name 'korean_mfa_acoustic_v3.3.0' `
            --dictionary-model-name 'common_pron_mfa_r2' `
            --g2p-model-name 'korean_mfa_jamo_g2p_v3.2.0_reference_only' `
            --frozen-bundle-contract $frozenBundle `
            --common-pron-manifest $CommonPronManifest `
            --common-pron-adoption-contract $CommonPronAdoptionContract `
            --output $contractPath
        if ($LASTEXITCODE -ne 0) {
            throw "$year alignment contract failed."
        }
        $contract = Get-Content -LiteralPath $contractPath -Raw `
                    -Encoding UTF8 | ConvertFrom-Json
        $contractId = [string]$contract.alignment_contract_id
        $markerPath = Join-Path $stateDir "$year.machine_done.json"
        if (Test-StageMarker $markerPath $year 'machine_qc' $contractId) {
            Say "REUSE year=$year verified marker"
            continue
        }
        if (Test-Path -LiteralPath $markerPath) {
            throw "$year stale or mismatched machine marker: $markerPath"
        }

        $corpus = Join-Path $runRoot "corpus\$year"
        $labCount = (
            Get-ChildItem -LiteralPath $corpus -Recurse -File -Filter '*.lab' |
            Measure-Object
        ).Count
        $sessionCount = (
            Get-ChildItem -LiteralPath $corpus -Directory |
            Measure-Object
        ).Count
        if (
            $labCount -ne $UtterancesPerYear -or
            $sessionCount -ne $SpeakersPerYear
        ) {
            throw (
                "$year pilot balance failed: labs=$labCount " +
                "sessions=$sessionCount"
            )
        }

        $rawSink = Join-Path $runRoot "mfa_raw_suppressed\$year"
        $alignLog = Join-Path $logsDir "$year.align.log"
        $dbPath = Join-Path $tempRoot "$year\$year.db"
        $alignMarkerPath = Join-Path $stateDir "$year.align_done.json"
        if (
            (Test-StageMarker $alignMarkerPath $year 'align' $contractId) -and
            (Test-Path -LiteralPath $dbPath)
        ) {
            Say "REUSE year=$year completed MFA DB"
        } else {
            if (Test-Path -LiteralPath $alignMarkerPath) {
                throw (
                    "$year stale or mismatched align marker: " +
                    $alignMarkerPath
                )
            }
            $alignArgs = @(
                'align',
                $corpus,
                $dictionary,
                $acoustic,
                $rawSink,
                '--no_tokenization',
                '--temporary_directory', $tempRoot,
                '--num_jobs', "$NumJobs",
                '--output_format', 'long_textgrid',
                '--clean'
            )
            $priorSkip = $env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT
            $priorErrorAction = $ErrorActionPreference
            $env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT = '1'
            # PowerShell 5.1 wraps every native stderr INFO line in
            # NativeCommandError when ErrorActionPreference is Stop. MFA writes
            # normal progress to stderr, so only this call uses Continue;
            # the real process exit code remains the acceptance gate.
            $ErrorActionPreference = 'Continue'
            try {
                & $mfa @alignArgs 2>&1 |
                    Tee-Object -FilePath $alignLog |
                    ForEach-Object { Write-Host $_ }
                $alignExit = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $priorErrorAction
                if ($null -eq $priorSkip) {
                    Remove-Item Env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT `
                        -ErrorAction SilentlyContinue
                } else {
                    $env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT = $priorSkip
                }
            }
            if ($alignExit -ne 0) {
                throw "$year MFA align failed(exit=$alignExit): $alignLog"
            }
            if (-not (Test-Path -LiteralPath $dbPath)) {
                throw "$year MFA DB missing after exit 0: $dbPath"
            }
            Write-Json $alignMarkerPath ([ordered]@{
                run_id = $RunId
                year = $year
                stage = 'align'
                status = 'passed'
                pronunciation_mode = (
                    'common_pron_mfa_r2_latest_jamo'
                )
                inline_g2p_used = $false
                alignment_contract_id = $contractId
                lab_input_contract_id = $labInputContractId
                database = $dbPath
                log = $alignLog
                built_in_textgrid_export_skipped = $true
                completed_at = (Get-Date).ToString('o')
            })
        }

        $exportReport = Join-Path $logsDir "$year.direct_export.json"
        & $py (Join-Path $pydir 'export_mfa_db_4tier.py') `
            --db $dbPath --year $year `
            --search-master-root (Join-Path $runRoot 'search_master') `
            --output-root $textgridRoot --workers $NumJobs `
            --report $exportReport
        if ($LASTEXITCODE -ne 0) {
            throw "$year direct DB export failed: $exportReport"
        }
        $export = Get-Content -LiteralPath $exportReport -Raw `
                  -Encoding UTF8 | ConvertFrom-Json
        $textgridCount = [int64]$export.counts.created +
                         [int64]$export.counts.validated_existing
        if (
            $export.status -ne 'success' -or
            $textgridCount -ne $UtterancesPerYear -or
            [int64]$export.counts.spn_intervals -ne 0
        ) {
            throw "$year export coverage/SPN gate failed."
        }

        $auditReport = Join-Path $logsDir "$year.4tier_audit.json"
        $missingCsv = Join-Path $logsDir "$year.4tier_missing.csv"
        & $py (Join-Path $pydir 'audit_mfa_4tier_year.py') `
            --year $year `
            --lab-root (Join-Path $runRoot "corpus\$year") `
            --textgrid-root (Join-Path $textgridRoot $year) `
            --report $auditReport --missing-csv $missingCsv `
            --input-contract-id $labInputContractId `
            --workers $NumJobs --minimum-coverage-pct 100
        if ($LASTEXITCODE -ne 0) {
            throw "$year 4-tier/boundary audit failed: $auditReport"
        }

        $sampleRoot = Join-Path $runRoot "db_reexport_sample\$year"
        $sampleReport = Join-Path $logsDir "$year.db_tg_sample.json"
        $sampleCsv = Join-Path $logsDir "$year.db_tg_sample.csv"
        & $py (Join-Path $pydir 'verify_mfa_db_4tier_sample.py') `
            --db $dbPath --year $year `
            --search-master-root (Join-Path $runRoot 'search_master') `
            --final-root $textgridRoot --scratch-root $sampleRoot `
            --report $sampleReport --sample-csv $sampleCsv `
            --sample-size $SpeakersPerYear `
            --input-contract-id $labInputContractId
        if ($LASTEXITCODE -ne 0) {
            throw "$year DB-to-TextGrid sample equivalence failed."
        }

        $phoneReport = Join-Path $phoneDir "$year.json"
        & $py (Join-Path $pydir 'build_mfa_year_phone_inventory.py') `
            --db $dbPath --year $year `
            --common-pron-manifest $CommonPronManifest `
            --alignment-contract $contractPath `
            --output $phoneReport
        if ($LASTEXITCODE -ne 0) {
            throw "$year phone inventory gate failed."
        }

        Write-Json $markerPath ([ordered]@{
            run_id = $RunId
            year = $year
            stage = 'machine_qc'
            status = 'passed'
            pronunciation_mode = 'common_pron_mfa_r2_latest_jamo'
            inline_g2p_used = $false
            alignment_contract_id = $contractId
            lab_input_contract_id = $labInputContractId
            textgrids = $textgridCount
            tier_provenance = $export.tier_provenance
            database = $dbPath
            export_report = $exportReport
            boundary_audit_report = $auditReport
            db_textgrid_sample_report = $sampleReport
            phone_inventory_report = $phoneReport
            researcher_review_status = 'pending'
            realization_judgment_performed = $false
            completed_at = (Get-Date).ToString('o')
        })
        Say "PASS year=$year machine QC"
    }

    $yearKey = (@($Years | Sort-Object -Unique) -join ',')
    if ($yearKey -eq '2020,2021,2022,2023,2024,2025') {
        $crossYearReport = Join-Path $logsDir 'cross_year_method_audit.json'
        & $py (Join-Path $pydir 'audit_mfa_cross_year_contracts.py') `
            --contracts-directory $contractsDir `
            --phone-inventory-directory $phoneDir `
            --output $crossYearReport
        if ($LASTEXITCODE -ne 0) {
            throw 'Cross-year method/phone standard audit failed.'
        }
    }

    & $py (Join-Path $pydir 'package_mfa_r2_pilot_review.py') `
        --run-root $runRoot --output-root $reviewFull
    if ($LASTEXITCODE -ne 0) {
        throw 'Flat Dropbox review bundle packaging failed.'
    }
    $reviewCsv = Join-Path $reviewFull 'REVIEW.csv'
    $reviewXlsx = Join-Path $reviewFull 'REVIEW.xlsx'
    $bundleManifest = Join-Path $reviewFull 'BUNDLE_MANIFEST.json'
    & $py (Join-Path $pydir 'create_mfa_r2_review_workbook.py') `
        --input-csv $reviewCsv --output-xlsx $reviewXlsx `
        --bundle-manifest $bundleManifest
    if ($LASTEXITCODE -ne 0) {
        throw 'REVIEW.xlsx generation/verification failed.'
    }
    $deliveryAudit = Join-Path $logsDir 'review_delivery_audit.json'
    & $py (Join-Path $pydir 'audit_mfa_r2_pilot_review_delivery.py') `
        --review-root $reviewFull --report $deliveryAudit
    if ($LASTEXITCODE -ne 0) {
        throw 'Final Dropbox review delivery audit failed.'
    }
    Say "MACHINE PASS; RESEARCHER INFRASTRUCTURE REVIEW PENDING"
    Say "Flat Dropbox folder: $reviewFull"
    Say "Delivery audit: $deliveryAudit"
} finally {
    if (Test-Path -LiteralPath $lockPath) {
        Remove-Item -LiteralPath $lockPath -Force
    }
}
