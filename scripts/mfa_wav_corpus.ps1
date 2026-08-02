# Resolve the year-specific WAV corpus and fail closed on a configured recovery.

function Resolve-MfaWavCorpusForYear {
    param(
        [Parameter(Mandatory=$true)]$Config,
        [Parameter(Mandatory=$true)]
        [ValidateSet('2020','2021','2022','2023','2024','2025')]
        [string]$Year
    )
    function Expand-MfaCorpusPath([string]$Value) {
        return [IO.Path]::GetFullPath(
            [Environment]::ExpandEnvironmentVariables($Value.Replace('/', '\'))
        )
    }
    $defaultRoot = Join-Path (Expand-MfaCorpusPath ([string]$Config.wav)) `
        'individual'
    if ($Year -ne '2020') {
        return [pscustomobject]@{
            WavRoot = $defaultRoot
            ContractPath = $null
            CorpusContractId = 'source_identity'
            Recovered = $false
        }
    }
    $rootProperty = $Config.PSObject.Properties['mfa_wav_corpus_2020']
    $contractProperty = $Config.PSObject.Properties[
        'mfa_wav_corpus_contract_2020'
    ]
    if ($null -eq $rootProperty -or $null -eq $contractProperty) {
        throw '2020 복구 WAV corpus/contract config 누락'
    }
    $wavRoot = Expand-MfaCorpusPath ([string]$rootProperty.Value)
    $contractPath = Expand-MfaCorpusPath ([string]$contractProperty.Value)
    if (-not (Test-Path -LiteralPath $contractPath -PathType Leaf)) {
        throw "2020 복구 WAV corpus contract 없음: $contractPath"
    }
    try {
        $contract = Get-Content -LiteralPath $contractPath -Raw `
            -Encoding UTF8 | ConvertFrom-Json
    } catch {
        throw "2020 복구 WAV corpus contract 손상: $contractPath"
    }
    $expectedYear = [IO.Path]::GetFullPath((Join-Path $wavRoot '2020')).TrimEnd('\')
    $actualYear = [IO.Path]::GetFullPath(
        [string]$contract.output_year
    ).TrimEnd('\')
    if (
        $contract.status -ne 'passed' -or
        [string]$contract.year -ne '2020' -or
        -not [bool]$contract.source_wav_tree_untouched -or
        [string]::IsNullOrWhiteSpace(
            [string]$contract.corpus_contract_id
        ) -or
        $actualYear -ne $expectedYear -or
        -not (Test-Path -LiteralPath $expectedYear -PathType Container)
    ) {
        throw "2020 복구 WAV corpus identity/status 불일치: $contractPath"
    }
    return [pscustomobject]@{
        WavRoot = $wavRoot
        ContractPath = $contractPath
        CorpusContractId = [string]$contract.corpus_contract_id
        Recovered = $true
    }
}
