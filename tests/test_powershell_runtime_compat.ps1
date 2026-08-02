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
    foreach ($error in @($errors)) {
        $failures.Add("PS5 구문 오류 $($script.Name): $($error.Message)")
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

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}
Write-Host "Windows PowerShell 5.1 runtime compatibility PASS ($($scripts.Count) scripts)"
