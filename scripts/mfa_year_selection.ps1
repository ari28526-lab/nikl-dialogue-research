#Requires -Version 5.1
<# Windows PowerShell -File 경계를 안전하게 넘는 MFA 연도 선택 정규화. #>

function Resolve-MfaYearSelection {
    [CmdletBinding()]
    param(
        [string[]]$Years = @(),
        [string]$YearsCsv = ''
    )

    $allowed = @('2020','2021','2022','2023','2024','2025')
    $resolved = if ([string]::IsNullOrWhiteSpace($YearsCsv)) {
        @($Years)
    } else {
        @(
            $YearsCsv.Split(',') |
                ForEach-Object { $_.Trim() } |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        )
    }
    if ($resolved.Count -eq 0) {
        throw 'MFA 연도 선택이 비어 있음'
    }
    $invalid = @($resolved | Where-Object { $_ -notin $allowed })
    if ($invalid.Count -gt 0) {
        throw "허용되지 않은 MFA 연도: $($invalid -join ',')"
    }
    $duplicates = @(
        $resolved | Group-Object | Where-Object { $_.Count -gt 1 }
    )
    if ($duplicates.Count -gt 0) {
        throw (
            '중복 MFA 연도: ' +
            (@($duplicates | ForEach-Object { $_.Name }) -join ',')
        )
    }
    return [string[]]$resolved
}
