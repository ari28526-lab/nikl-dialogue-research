#Requires -Version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$manifestPath = (
    'E:\READ_ONLY_ARCHIVE\2026_summer_research\' +
    'legacy_d_workspace_20260802\archive_manifest.json'
)
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    Write-Host 'legacy D: archive manifest가 아직 없습니다.'
    exit 0
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$items = @($manifest.items)
$latest = @{}
foreach ($item in $items) { $latest[[string]$item.key] = $item }
$rows = foreach ($key in @($latest.Keys | Sort-Object)) {
    $item = $latest[$key]
    [pscustomobject]@{
        key = $key
        status = [string]$item.status
        source_gib = if ($item.PSObject.Properties['source_bytes']) {
            [math]::Round([long]$item.source_bytes / 1GB, 3)
        } else { $null }
        archive_gib = if ($item.PSObject.Properties['archive_bytes']) {
            [math]::Round([long]$item.archive_bytes / 1GB, 3)
        } else { $null }
        source = [string]$item.source
    }
}
Write-Host 'Legacy D: workspace archive - read-only dashboard'
Write-Host "Observed: $(Get-Date -Format o)"
Write-Host "Manifest: $($manifest.status) / selection=$($manifest.current_selection)"
$rows | Format-Table -AutoSize
[pscustomobject]@{
    d_free_gib = [math]::Round(
        [IO.DriveInfo]::new('D').AvailableFreeSpace / 1GB, 3
    )
    e_free_gib = [math]::Round(
        [IO.DriveInfo]::new('E').AvailableFreeSpace / 1GB, 3
    )
} | Format-List
