<# Single-purpose entrypoint: resume only 2020 morph_search.v3. #>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$verify = Join-Path $PSScriptRoot 'verify_production_source_contract.ps1'
$runner = Join-Path $PSScriptRoot 'run_morph_search_year_safe.ps1'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verify `
    -Year 2020 -Ensure
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $runner -Year 2020
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verify `
    -Year 2020 -RequireMorphYearSuccess
exit $LASTEXITCODE
