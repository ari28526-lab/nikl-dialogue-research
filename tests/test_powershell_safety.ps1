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
            'if ($PreferD)',
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
            'if ($PreferD)',
            "'-PreferD'",
            'prefer_d = [bool]$PreferD',
            'run_eojeol_realign.ps1'
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

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}
Write-Output "PowerShell safety checks PASS ($($files.Count) files)"
exit 0
