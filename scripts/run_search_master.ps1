# 검색 마스터 CSV 안전 실행기.
# 모호한 PATH의 python을 쓰지 않고 config/paths.json의 pipeline_python을 사용한다.
# 기본은 preflight 통과 후 전량. 파일럿: -Year 2020 -Pilot 3 -OutputRoot <격리경로>
param(
    [string]$Year = "",
    [int]$Pilot = 0,
    [string]$OutputRoot = "",
    [switch]$Overwrite,
    [switch]$AllowMissingJson,
    [switch]$SkipPreflight
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root 'config\paths.json'
$pythonDir = Join-Path $PSScriptRoot 'python'

if (-not (Test-Path -LiteralPath $configPath)) {
    Write-Error "설정 파일 없음: $configPath"
    exit 1
}

try {
    $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 |
              ConvertFrom-Json
    $pyText = [Environment]::ExpandEnvironmentVariables(
        ([string]$config.pipeline_python).Replace('/', '\')
    )
    $py = [IO.Path]::GetFullPath($pyText)
} catch {
    Write-Error "pipeline_python 설정 해석 실패: $($_.Exception.Message)"
    exit 1
}

if (-not (Test-Path -LiteralPath $py)) {
    Write-Error "pipeline_python 없음: $py"
    exit 1
}

if (-not $SkipPreflight) {
    & $py (Join-Path $pythonDir 'preflight_search_master.py')
    if ($LASTEXITCODE -ne 0) {
        Write-Error "검색 마스터 preflight 실패(exit $LASTEXITCODE). logs\preflight_report.txt 확인."
        exit 1
    }
}

$buildArgs = @((Join-Path $pythonDir 'build_search_master.py'))
if ($Year) { $buildArgs += @('--year', $Year) }
if ($Pilot -gt 0) { $buildArgs += @('--pilot', "$Pilot") }
if ($OutputRoot) { $buildArgs += @('--output-root', $OutputRoot) }
if ($Overwrite) { $buildArgs += '--overwrite' }
if ($AllowMissingJson) { $buildArgs += '--allow-missing-json' }

& $py @buildArgs
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Error "검색 마스터 빌드 실패(exit $code). logs의 build/crash 보고서 확인."
    exit $code
}
exit 0
