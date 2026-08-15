#Requires -Version 5.1
<# Windows PowerShell 5.1에서 실제로 발생하는 인코딩·배열 unrolling 회귀 검사. #>
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
$failures = [Collections.Generic.List[string]]::new()
$scripts = @(Get-ChildItem -LiteralPath (Join-Path $root 'scripts') `
    -Filter '*.ps1' -File)

foreach ($script in $scripts) {
    $bytes = [IO.File]::ReadAllBytes($script.FullName)
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and
        $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    if (-not $hasBom) {
        $failures.Add("UTF-8 BOM 없음: $($script.FullName)")
    }
    $tokens = $null
    $errors = $null
    [Management.Automation.Language.Parser]::ParseFile(
        $script.FullName, [ref]$tokens, [ref]$errors
    ) | Out-Null
    foreach ($parseError in @($errors)) {
        $failures.Add("PS5 구문 오류 $($script.Name): $($parseError.Message)")
    }
}

# ConvertFrom-Json이 1개 항목을 scalar PSCustomObject로 푸는 PS5 동작을 재현한다.
$single = '{"failure_history":{"failed_at":"t1","error":"e1"}}' |
    ConvertFrom-Json
$history = [Collections.Generic.List[object]]::new()
foreach ($item in @($single.failure_history)) { $history.Add($item) }
$history.Add([pscustomobject]@{ failed_at = 't2'; error = 'e2' })
if ($history.Count -ne 2) {
    $failures.Add('PSCustomObject 단일/배열 정규화 회귀')
}

$archiveScript = Get-Content -LiteralPath (Join-Path $root `
    'scripts\archive_legacy_d_workspace_20260802.ps1') -Raw -Encoding UTF8
foreach ($required in @(
    '[switch]$PreflightOnly',
    '[Collections.Generic.List[object]]::new()',
    "-snl",
    "status = 'preflight_passed'"
)) {
    if (-not $archiveScript.Contains($required)) {
        $failures.Add("archive PS5 호환 토큰 누락: $required")
    }
}
if ($archiveScript -match '\$history\s*\+=') {
    $failures.Add('archive failure_history에 PS5 scalar += 사용 금지')
}

# M1 회귀: 명시적 full-clean 재시도의 보존 이동 함수를 합성 temp에서
# 실제 호출한다. D: 자료나 MFA 산출물에는 접근하지 않는다.
$legacyRunnerPath = Join-Path $root 'scripts\run_eojeol_realign.ps1'
$legacyTokens = $null
$legacyErrors = $null
$legacyAst = [Management.Automation.Language.Parser]::ParseFile(
    $legacyRunnerPath, [ref]$legacyTokens, [ref]$legacyErrors
)
$archiveFunction = $legacyAst.Find({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Archive-StaleTemp'
}, $true)
$legacyText = Get-Content -LiteralPath $legacyRunnerPath -Raw -Encoding UTF8
if ($null -eq $archiveFunction) {
    $failures.Add('Archive-StaleTemp 함수 AST를 찾지 못함')
} elseif (-not $legacyText.Contains(
    'Archive-StaleTemp $tmpYear $tmp $y'
)) {
    $failures.Add('명시적 full-clean 재시도 호출의 allowedRoot 인자 누락')
} else {
    $archiveTestRoot = Join-Path ([IO.Path]::GetTempPath()) (
        'mfa_archive_stale_test_' + [guid]::NewGuid().ToString('N')
    )
    try {
        $allowedRoot = Join-Path $archiveTestRoot 'allowed'
        $sourceYear = Join-Path $allowedRoot '2020'
        $stateRoot = Join-Path $archiveTestRoot 'state'
        New-Item -ItemType Directory -Force -Path $sourceYear | Out-Null
        Set-Content -LiteralPath (Join-Path $sourceYear 'checkpoint.txt') `
            -Value 'preserve-me' -Encoding UTF8
        function Say { param([string]$Message) }
        Invoke-Expression $archiveFunction.Extent.Text
        $archived = Archive-StaleTemp $sourceYear $allowedRoot '2020' `
            'synthetic_actual_invocation'
        if (Test-Path -LiteralPath $sourceYear) {
            $failures.Add('Archive-StaleTemp 실제 호출 후 원 temp가 남음')
        }
        if (-not (Test-Path -LiteralPath (
            Join-Path $archived 'checkpoint.txt'
        ) -PathType Leaf)) {
            $failures.Add('Archive-StaleTemp 실제 호출이 checkpoint를 보존하지 못함')
        }
    } catch {
        $failures.Add("Archive-StaleTemp 실제 호출 실패: $($_.Exception.Message)")
    } finally {
        $resolvedTestRoot = [IO.Path]::GetFullPath($archiveTestRoot)
        $resolvedSystemTemp = [IO.Path]::GetFullPath(
            [IO.Path]::GetTempPath()
        )
        if ($resolvedTestRoot.StartsWith(
            $resolvedSystemTemp, [StringComparison]::OrdinalIgnoreCase
        )) {
            Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force `
                -ErrorAction SilentlyContinue
        }
    }
}

. (Join-Path $root 'scripts\mfa_year_selection.ps1')
$csvYears = @(
    Resolve-MfaYearSelection -YearsCsv '2021,2022,2023,2024,2025'
)
if (($csvYears -join ',') -ne '2021,2022,2023,2024,2025') {
    $failures.Add('YearsCsv PS5 연도 배열 복원 회귀')
}
$arrayYears = @(
    Resolve-MfaYearSelection -Years @('2021','2022')
)
if (($arrayYears -join ',') -ne '2021,2022') {
    $failures.Add('직접 Years 배열 정규화 회귀')
}
$duplicateRejected = $false
try {
    $null = Resolve-MfaYearSelection -YearsCsv '2021,2021'
} catch {
    $duplicateRejected = $true
}
if (-not $duplicateRejected) {
    $failures.Add('YearsCsv 중복 연도 차단 회귀')
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}
Write-Host "Windows PowerShell 5.1 runtime compatibility PASS ($($scripts.Count) scripts)"
