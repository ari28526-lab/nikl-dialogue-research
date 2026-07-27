# 어절(語節) 전량 재정렬 배치 — 목적 B: 4-tier TextGrid. ★실시간 출력판★
#   words(어절)+phones(G2P 사전으로 정렬한 대략적 라벨·시간)+morphemes(형태소 경계)+utterance
# lab은 wav 옆에 제자리 생성(하드링크 없음). 기존 06_textgrid_merged는 읽기전용 보존.
# 신규 결과: D:\20_AUDIO\07_textgrid_eojeol_g2p_staging
# 기존 D:\20_AUDIO\06_textgrid_eojeol은 검증·archive·승격 전까지 그대로 보존.
# ★lab·병합 단계는 화면 실시간. MFA 단계는 stderr를 파일로 캡처(실패 traceback 보존)
#   + 1분 하트비트로 진행바 요약 표시 (2026-07-18: 7/17 실패 원인 유실 사고 후 전환).
# 실행: powershell -ExecutionPolicy Bypass -File <리포>\scripts\run_eojeol_realign.ps1
# 주의: 도는 동안 D:를 읽는 다른 작업 금지(경합).
# ★전제(2026-07-19): wav 코퍼스는 세션 하위폴더 구조여야 함(세션=화자). 평면이면
#   MFA가 연도 전체를 화자 1명으로 오인 → 가드가 중단시킴. restructure_wav_sessions.py 먼저.
#   기기 이식: miniforge는 %USERPROFILE%\miniforge3, 데이터는 D: 문자 기준 — 새 기기에서
#   SSD에 D: 부여하면 무수정 실행. num_jobs·작업드라이브는 자동 선택.

param(
    [ValidateSet('2020','2021','2022','2023','2024','2025')]
    [string]$Year,
    [string]$SearchMasterRoot = "",
    [switch]$PreferD,
    [switch]$UseDirectDbExport,
    [switch]$CleanupDirectDbAfterMerge,
    [switch]$CleanupMfaOutput,
    [switch]$SkipPreflight
)

if ($CleanupDirectDbAfterMerge -and -not $UseDirectDbExport) {
    Write-Error "-CleanupDirectDbAfterMerge는 -UseDirectDbExport와 함께만 사용할 수 있음"
    exit 1
}
if ($UseDirectDbExport -and $CleanupMfaOutput) {
    Write-Error (
        "-UseDirectDbExport는 QC용 alignment DB 보존 정책을 사용함. " +
        "정리가 필요하면 -CleanupDirectDbAfterMerge를 명시할 것"
    )
    exit 1
}

# 주의: $ErrorActionPreference는 Stop 안 씀(네이티브 exe stderr가 오류로 오인되는 것 방지).
$root = Split-Path -Parent $PSScriptRoot

# 실행 중인 다년 배치를 연도 경계에서 안전하게 멈추기 위한 run별 요청.
# 이미 시작한 연도에는 영향을 주지 않고, 바깥 wrapper가 다음 연도의 이
# 스크립트를 새 프로세스로 호출할 때만 검사한다. 요청 파일은 run ID에
# 묶여 있어 다른 실행에는 적용되지 않는다.
if (-not [string]::IsNullOrWhiteSpace($SearchMasterRoot)) {
    $runIdHint = Split-Path -Leaf $SearchMasterRoot
    $pauseRequestPath = Join-Path $root (
        "work\control\pause_after_year_{0}.json" -f $runIdHint
    )
    if (Test-Path -LiteralPath $pauseRequestPath) {
        try {
            $pauseRequest = Get-Content -LiteralPath $pauseRequestPath -Raw `
                -Encoding UTF8 | ConvertFrom-Json
            if ([string]$pauseRequest.run_id -ne $runIdHint) {
                throw "run_id 불일치(request=$($pauseRequest.run_id), current=$runIdHint)"
            }
            $pauseAfterYear = [int]$pauseRequest.pause_after_year
            if ($pauseAfterYear -notin @(2020, 2021, 2022, 2023, 2024, 2025)) {
                throw "pause_after_year 허용 범위 위반: $pauseAfterYear"
            }
        } catch {
            Write-Error "연도 경계 일시정지 요청 해석 실패: $($_.Exception.Message)"
            exit 74
        }
        if ([int]$Year -gt $pauseAfterYear) {
            Write-Host (
                "요청에 따라 $pauseAfterYear 완료 뒤 일시정지: " +
                "$Year 작업은 시작하지 않음 ($pauseRequestPath)"
            ) -ForegroundColor Yellow
            exit 75
        }
    }
}

$configPath = Join-Path $root "config\paths.json"
try {
    $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    function Expand-CfgPath($value) {
        return [IO.Path]::GetFullPath(
            [Environment]::ExpandEnvironmentVariables(
                ([string]$value).Replace('/', '\')
            )
        )
    }
    $py = Expand-CfgPath $cfg.pipeline_python
    $wavRoot = Join-Path (Expand-CfgPath $cfg.wav) "individual"
    $layersRoot = Expand-CfgPath $cfg.layers
    $stateRoot = Expand-CfgPath $cfg.mfa_state
    $tmpPrimary = Expand-CfgPath $cfg.mfa_temp_primary
    $tmpSecondary = Expand-CfgPath $cfg.mfa_temp_secondary
    $outPrimary = Expand-CfgPath $cfg.mfa_output_primary
    $outSecondary = Expand-CfgPath $cfg.mfa_output_secondary
    $g2pStage = Expand-CfgPath $cfg.textgrid_eojeol_staging
    $morphTextGridRoot = Expand-CfgPath $cfg.textgrid_merged
    $sourcePcmCheck = Join-Path $layersRoot "05_audio_index\source_pcm_check.csv"
    if ([string]::IsNullOrWhiteSpace($SearchMasterRoot)) {
        $searchMasterRoot = Expand-CfgPath $cfg.search_master
    } else {
        $searchMasterRoot = [IO.Path]::GetFullPath($SearchMasterRoot)
    }
} catch {
    Write-Error "config/paths.json 해석 실패: $($_.Exception.Message)"
    exit 1
}
# ★ conda run 대신 mfa.exe 직접 호출 (2026-07-17): conda run은 출력을 버퍼링해
#   진행바가 안 보이고, MFA 에러 시 래퍼가 안 죽고 매달리는 사고 확인됨(파일럿).
#   단 OpenFST 등 서드파티 실행파일(fstcompile)을 PATH에서 찾으므로 env 경로를 얹는다.
# ★ 기기 이식성 (2026-07-19): 경로를 사용자 홈 기준으로 — 새 노트북에서도 무수정 실행.
$envRoot = Join-Path $env:USERPROFILE "miniforge3\envs\mfa"
$mfa   = Join-Path $envRoot "Scripts\mfa.exe"
$env:Path = "$envRoot;$envRoot\Library\bin;$envRoot\Scripts;$envRoot\bin;" + $env:Path
$pydir = Join-Path $PSScriptRoot "python"
$mfaModelRoot = Join-Path $env:USERPROFILE "Documents\MFA\pretrained_models"
$acousticModelPath = Join-Path $mfaModelRoot "acoustic\korean_mfa.zip"
$dictionaryModelPath = Join-Path $mfaModelRoot "dictionary\korean_mfa.dict"
$g2pModelPath = Join-Path $mfaModelRoot "g2p\korean_mfa.zip"
if (-not (Test-Path -LiteralPath $py)) {
    Write-Error "pipeline_python 없음: $py"
    exit 1
}
if (-not (Test-Path -LiteralPath $mfa)) {
    Write-Error "mfa.exe 없음: $mfa"
    exit 1
}
foreach ($modelPath in @(
    $acousticModelPath, $dictionaryModelPath, $g2pModelPath
)) {
    if (-not (Test-Path -LiteralPath $modelPath)) {
        Write-Error "MFA alignment contract 모델 파일 없음: $modelPath"
        exit 1
    }
}
# ★ 병렬 자동 (2026-07-19): 논리코어 12+(i5-1240P=16) → 8job, 그 외(N200=4) → 4job.
#   세션=화자 재구성 후에야 유효 — 1화자면 MFA가 어차피 1job으로 강등함.
$numJobs = if ([Environment]::ProcessorCount -ge 12) { 8 } else { 4 }
# ★ 작업 드라이브 자동 — 연도별 재평가 (2026-07-19 도입, 2026-07-22 연도별로 전환):
#   원래 스크립트 시작 시 1회만 정했으나, 연도별 규모 격차가 커서(2021이 2020의
#   1.63배) 실행 도중 C: 여유가 40GB 밑으로 떨어지는 사례 발생 → 전역 1회 결정이면
#   그 뒤 연도부터 자동으로 D:로 넘어가되, **이미 특정 드라이브에 만들어진 temp가
#   있으면(중단 후 재개) 그 드라이브를 최우선 사용** — 안 그러면 완주한 정렬 계산
#   (연도당 최대 3시간+)이 든 temp를 못 찾고 새로 --clean 시작해버림(2021 실측 사고).
#   판정 순서: ① 검증된 temp가 있는 드라이브 ② 신규 연도는 연도별 예상 peak를
#   감당할 때만 C:, 아니면 D:. 최대 연도 2021은 C: 55GB, 나머지는 45GB를 요구.
function Get-WorkPaths($year) {
    $required = if ($year -eq '2021') { 55 } else { 45 }
    # 무인 대량 작업에서는 OS/Dropbox가 함께 쓰는 C:의 2~3GB 잔여 여유를
    # 감수하지 않는다. -PreferD면 신규 연도는 D:에서 시작한다. 단, 동일한
    # 입력계약으로 검증된 resume temp가 이미 있으면 수시간 계산을 버리지 않도록
    # 그 temp의 원래 드라이브를 유지한다(계약 불일치 temp는 아래에서 먼저 archive).
    if ($PreferD) {
        if (Test-Path (Join-Path $tmpSecondary $year)) {
            return @{ TempRoot = $tmpSecondary; OutRoot = $outSecondary; MinFreeGB = 10 }
        }
        if (Test-Path (Join-Path $tmpPrimary $year)) {
            return @{ TempRoot = $tmpPrimary; OutRoot = $outPrimary; MinFreeGB = 10 }
        }
        return @{
            TempRoot = $tmpSecondary
            OutRoot = $outSecondary
            MinFreeGB = $required
        }
    }
    if (Test-Path (Join-Path $tmpPrimary $year)) {
        return @{ TempRoot = $tmpPrimary; OutRoot = $outPrimary; MinFreeGB = 10 }
    }
    if (Test-Path (Join-Path $tmpSecondary $year)) {
        return @{ TempRoot = $tmpSecondary; OutRoot = $outSecondary; MinFreeGB = 10 }
    }
    $primaryDrive = Split-Path -Qualifier $tmpPrimary
    $primaryFree = ([IO.DriveInfo]::new($primaryDrive)).AvailableFreeSpace
    if ($primaryFree / 1GB -ge $required) {
        return @{
            TempRoot = $tmpPrimary
            OutRoot = $outPrimary
            MinFreeGB = $required
        }
    }
    return @{ TempRoot = $tmpSecondary; OutRoot = $outSecondary; MinFreeGB = $required }
}

# MFA의 실제 자식·손자 프로세스만 집계한다. 이전 구현은 컴퓨터에서 실행 중인
# 모든 mfa/python CPU를 합쳐, 별도 분석 작업이 있으면 교착을 정상 진행으로
# 오판할 수 있었다. 관리자 권한이 필요한 CIM 대신 Windows Toolhelp snapshot을
# 사용한다. 스냅샷 조회가 일시 실패하면 기존 전역 집계로 폴백하되
# metrics_scope에 이를 명시해 사후에 판별 가능하게 한다.
function Get-ProcessTreeMetrics {
    param([Parameter(Mandatory=$true)][int]$RootProcessId)

    try {
        if (-not ('ProjectProcessSnapshot' -as [type])) {
            $snapshotSource = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public sealed class ProjectProcessParentInfo {
    public int ProcessId { get; set; }
    public int ParentProcessId { get; set; }
    public string Name { get; set; }
}

public static class ProjectProcessSnapshot {
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Auto)]
    private struct PROCESSENTRY32 {
        public uint dwSize;
        public uint cntUsage;
        public uint th32ProcessID;
        public IntPtr th32DefaultHeapID;
        public uint th32ModuleID;
        public uint cntThreads;
        public uint th32ParentProcessID;
        public int pcPriClassBase;
        public uint dwFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=260)]
        public string szExeFile;
    }

    [DllImport("kernel32.dll", SetLastError=true)]
    private static extern IntPtr CreateToolhelp32Snapshot(
        uint flags, uint processId
    );
    [DllImport("kernel32.dll", CharSet=CharSet.Auto, SetLastError=true)]
    private static extern bool Process32First(
        IntPtr snapshot, ref PROCESSENTRY32 entry
    );
    [DllImport("kernel32.dll", CharSet=CharSet.Auto, SetLastError=true)]
    private static extern bool Process32Next(
        IntPtr snapshot, ref PROCESSENTRY32 entry
    );
    [DllImport("kernel32.dll", SetLastError=true)]
    private static extern bool CloseHandle(IntPtr handle);

    public static ProjectProcessParentInfo[] GetProcesses() {
        var result = new List<ProjectProcessParentInfo>();
        IntPtr snapshot = CreateToolhelp32Snapshot(2, 0);
        if (snapshot == new IntPtr(-1)) {
            throw new System.ComponentModel.Win32Exception(
                Marshal.GetLastWin32Error()
            );
        }
        try {
            var entry = new PROCESSENTRY32();
            entry.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));
            if (Process32First(snapshot, ref entry)) {
                do {
                    result.Add(new ProjectProcessParentInfo {
                        ProcessId = (int)entry.th32ProcessID,
                        ParentProcessId = (int)entry.th32ParentProcessID,
                        Name = entry.szExeFile
                    });
                    entry.dwSize = (
                        uint
                    )Marshal.SizeOf(typeof(PROCESSENTRY32));
                } while (Process32Next(snapshot, ref entry));
            }
        } finally {
            CloseHandle(snapshot);
        }
        return result.ToArray();
    }
}
'@
            Add-Type -TypeDefinition $snapshotSource -ErrorAction Stop
        }
        $inventory = @([ProjectProcessSnapshot]::GetProcesses())
        $treeIdSet = @{}
        $treeIdSet[$RootProcessId] = $true
        $added = $true
        while ($added) {
            $added = $false
            foreach ($item in $inventory) {
                $itemId = [int]$item.ProcessId
                $parentId = [int]$item.ParentProcessId
                if ($itemId -gt 0 -and $treeIdSet.ContainsKey($parentId) -and
                    -not $treeIdSet.ContainsKey($itemId)) {
                    $treeIdSet[$itemId] = $true
                    $added = $true
                }
            }
        }
        $processIds = @($treeIdSet.Keys | Sort-Object)
        $live = @(
            Get-Process -Id $processIds -ErrorAction SilentlyContinue
        )
        $cpuSeconds = 0.0
        [int64]$workingSetBytes = 0
        [int64]$privateMemoryBytes = 0
        [int64]$threadCount = 0
        $cpuByPid = @{}
        foreach ($item in $live) {
            if ($null -ne $item.CPU) {
                $itemCpu = [double]$item.CPU
                $cpuSeconds += $itemCpu
                $cpuByPid[[string]$item.Id] = $itemCpu
            }
            $workingSetBytes += [int64]$item.WorkingSet64
            $privateMemoryBytes += [int64]$item.PrivateMemorySize64
            try {
                $threadCount += @($item.Threads).Count
            } catch {}
        }
        return [PSCustomObject][ordered]@{
            Scope = 'descendant_tree'
            ProcessCount = $live.Count
            PythonProcessCount = @(
                $live | Where-Object { $_.ProcessName -match '^python' }
            ).Count
            ThreadCount = $threadCount
            CpuSeconds = $cpuSeconds
            CpuByPid = $cpuByPid
            WorkingSetBytes = $workingSetBytes
            PrivateMemoryBytes = $privateMemoryBytes
            ProcessIds = $processIds
        }
    } catch {
        $live = @(Get-Process mfa,python -ErrorAction SilentlyContinue)
        $cpuSeconds = 0.0
        [int64]$workingSetBytes = 0
        [int64]$privateMemoryBytes = 0
        [int64]$threadCount = 0
        $cpuByPid = @{}
        foreach ($item in $live) {
            if ($null -ne $item.CPU) {
                $itemCpu = [double]$item.CPU
                $cpuSeconds += $itemCpu
                $cpuByPid[[string]$item.Id] = $itemCpu
            }
            $workingSetBytes += [int64]$item.WorkingSet64
            $privateMemoryBytes += [int64]$item.PrivateMemorySize64
            try {
                $threadCount += @($item.Threads).Count
            } catch {}
        }
        return [PSCustomObject][ordered]@{
            Scope = 'global_fallback'
            ProcessCount = $live.Count
            PythonProcessCount = @(
                $live | Where-Object { $_.ProcessName -match '^python' }
            ).Count
            ThreadCount = $threadCount
            CpuSeconds = $cpuSeconds
            CpuByPid = $cpuByPid
            WorkingSetBytes = $workingSetBytes
            PrivateMemoryBytes = $privateMemoryBytes
            ProcessIds = @($live.Id | Sort-Object)
        }
    }
}

function Get-SystemMemoryMetrics {
    if (-not ('ProjectSystemMemory' -as [type])) {
        $memorySource = @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public sealed class ProjectSystemMemorySnapshot {
    public long AvailablePhysicalBytes { get; set; }
    public long CommitUsedBytes { get; set; }
    public long CommitLimitBytes { get; set; }
}

public static class ProjectSystemMemory {
    [StructLayout(LayoutKind.Sequential)]
    private struct PERFORMANCE_INFORMATION {
        public uint cb;
        public UIntPtr CommitTotal;
        public UIntPtr CommitLimit;
        public UIntPtr CommitPeak;
        public UIntPtr PhysicalTotal;
        public UIntPtr PhysicalAvailable;
        public UIntPtr SystemCache;
        public UIntPtr KernelTotal;
        public UIntPtr KernelPaged;
        public UIntPtr KernelNonpaged;
        public UIntPtr PageSize;
        public uint HandleCount;
        public uint ProcessCount;
        public uint ThreadCount;
    }

    [DllImport("psapi.dll", SetLastError=true)]
    private static extern bool GetPerformanceInfo(
        out PERFORMANCE_INFORMATION information,
        uint size
    );

    private static long ToBytes(UIntPtr pages, UIntPtr pageSize) {
        checked {
            return (long)(pages.ToUInt64() * pageSize.ToUInt64());
        }
    }

    public static ProjectSystemMemorySnapshot GetSnapshot() {
        var information = new PERFORMANCE_INFORMATION();
        information.cb = (uint)Marshal.SizeOf(
            typeof(PERFORMANCE_INFORMATION)
        );
        if (!GetPerformanceInfo(out information, information.cb)) {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        return new ProjectSystemMemorySnapshot {
            AvailablePhysicalBytes = ToBytes(
                information.PhysicalAvailable,
                information.PageSize
            ),
            CommitUsedBytes = ToBytes(
                information.CommitTotal,
                information.PageSize
            ),
            CommitLimitBytes = ToBytes(
                information.CommitLimit,
                information.PageSize
            )
        };
    }
}
'@
        Add-Type -TypeDefinition $memorySource -ErrorAction Stop
    }

    try {
        $snapshot = [ProjectSystemMemory]::GetSnapshot()
        $commitPercent = $null
        if ([int64]$snapshot.CommitLimitBytes -gt 0) {
            $commitPercent = [math]::Round(
                100.0 * [int64]$snapshot.CommitUsedBytes /
                [int64]$snapshot.CommitLimitBytes,
                1
            )
        }
        return [PSCustomObject][ordered]@{
            AvailableMemoryMB = [math]::Round(
                [int64]$snapshot.AvailablePhysicalBytes / 1MB, 1
            )
            CommitUsedGB = [math]::Round(
                [int64]$snapshot.CommitUsedBytes / 1GB, 2
            )
            CommitLimitGB = [math]::Round(
                [int64]$snapshot.CommitLimitBytes / 1GB, 2
            )
            CommitPercent = $commitPercent
            PressureWarning = (
                [int64]$snapshot.AvailablePhysicalBytes -lt 1GB -or
                ($null -ne $commitPercent -and $commitPercent -ge 90)
            )
            Available = $true
        }
    } catch {
        return [PSCustomObject][ordered]@{
            AvailableMemoryMB = $null
            CommitUsedGB = $null
            CommitLimitGB = $null
            CommitPercent = $null
            PressureWarning = $null
            Available = $false
        }
    }
}

function Update-ProcessTreeCpuAccumulator {
    param(
        [hashtable]$PreviousCpuByPid = @{},
        [hashtable]$CurrentCpuByPid = @{},
        [double]$RetiredCpuSeconds = 0.0
    )

    $nextRetiredCpuSeconds = $RetiredCpuSeconds
    $nextCpuByPid = @{}
    [double]$liveCpuSeconds = 0.0

    foreach ($entry in $CurrentCpuByPid.GetEnumerator()) {
        $pidKey = [string]$entry.Key
        $pidCpu = [double]$entry.Value
        if ($PreviousCpuByPid.ContainsKey($pidKey) -and
            $pidCpu -lt [double]$PreviousCpuByPid[$pidKey]) {
            # 같은 PID의 CPU가 감소했다면 heartbeat 사이 PID가 재사용된
            # 것으로 보고, 이전 process instance의 마지막 CPU를 보존한다.
            $nextRetiredCpuSeconds += [double]$PreviousCpuByPid[$pidKey]
        }
        $nextCpuByPid[$pidKey] = $pidCpu
        $liveCpuSeconds += $pidCpu
    }
    foreach ($pidKey in @($PreviousCpuByPid.Keys)) {
        if (-not $nextCpuByPid.ContainsKey([string]$pidKey)) {
            # 종료된 worker가 live 합계에서 사라져도 마지막 CPU를 잃지 않는다.
            $nextRetiredCpuSeconds += [double]$PreviousCpuByPid[$pidKey]
        }
    }

    return [PSCustomObject][ordered]@{
        RetiredCpuSeconds = $nextRetiredCpuSeconds
        LiveCpuSeconds = $liveCpuSeconds
        TotalCpuSeconds = $nextRetiredCpuSeconds + $liveCpuSeconds
        CpuByPid = $nextCpuByPid
    }
}

# lattice 후처리에는 stderr 진행 카운터가 없으므로 MFA가 쓰는 두 interval CSV의
# 증분 행 수와 byte 크기를 관측한다. byte 단위 줄바꿈 스캔이라 CSV 내용을
# 파싱하거나 잠그지 않으며, 쓰는 중인 마지막 행은 다음 heartbeat에서 센다.
# 이 값 역시 생존·병목 진단용이며 성공 gate는 DB/direct export/QC로 분리한다.
function Update-IntervalCsvProgress {
    param(
        [Parameter(Mandatory=$true)][string]$AlignmentDirectory,
        [hashtable]$PreviousState = @{}
    )

    if (-not ('ProjectNewlineScanner' -as [type])) {
        $newlineScannerSource = @'
using System;
using System.IO;

public sealed class ProjectNewlineDelta {
    public long NewOffset { get; set; }
    public string Carry { get; set; }
    public long Newlines { get; set; }
    public string LastUtteranceId { get; set; }
    public long UtteranceTransitions { get; set; }
}

public static class ProjectNewlineScanner {
    private static string WordUtteranceId(string line) {
        int start = 0;
        for (int field = 0; field < 3; field++) {
            int comma = line.IndexOf(',', start);
            if (comma < 0) {
                return null;
            }
            start = comma + 1;
        }
        int end = line.IndexOf(',', start);
        if (end < 0 || end <= start) {
            return null;
        }
        string value = line.Substring(start, end - start);
        long parsed;
        return long.TryParse(value, out parsed) ? value : null;
    }

    public static ProjectNewlineDelta Scan(
        string path,
        long offset,
        string carry,
        string lastUtteranceId,
        bool trackWordUtterances
    ) {
        long newOffset = offset;
        long newlines = 0;
        long utteranceTransitions = 0;
        string pending = carry ?? "";
        string lastId = lastUtteranceId;
        byte[] buffer = new byte[65536];
        using (var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.ReadWrite | FileShare.Delete
        )) {
            stream.Seek(offset, SeekOrigin.Begin);
            while (true) {
                int read = stream.Read(buffer, 0, buffer.Length);
                if (read <= 0) {
                    break;
                }
                newOffset += read;
                string text = pending +
                    System.Text.Encoding.UTF8.GetString(buffer, 0, read);
                int start = 0;
                while (true) {
                    int newline = text.IndexOf('\n', start);
                    if (newline < 0) {
                        break;
                    }
                    int length = newline - start;
                    if (length > 0 && text[newline - 1] == '\r') {
                        length -= 1;
                    }
                    if (trackWordUtterances) {
                        string utteranceId = WordUtteranceId(
                            text.Substring(start, length)
                        );
                        if (utteranceId != null &&
                            !String.Equals(
                                utteranceId,
                                lastId,
                                StringComparison.Ordinal
                            )) {
                            utteranceTransitions += 1;
                            lastId = utteranceId;
                        }
                    }
                    newlines += 1;
                    start = newline + 1;
                }
                pending = start < text.Length
                    ? text.Substring(start)
                    : "";
            }
        }
        return new ProjectNewlineDelta {
            NewOffset = newOffset,
            Carry = pending,
            Newlines = newlines,
            LastUtteranceId = lastId,
            UtteranceTransitions = utteranceTransitions
        };
    }
}
'@
        Add-Type -TypeDefinition $newlineScannerSource -ErrorAction Stop
    }

    $nextState = @{}
    $metrics = @{
        'phone_intervals.csv' = @{ Rows = 0L; Bytes = 0L }
        'word_intervals.csv' = @{
            Rows = 0L
            Bytes = 0L
            Utterances = 0L
        }
    }
    $latestWriteUtc = $null
    foreach ($name in @('phone_intervals.csv', 'word_intervals.csv')) {
        $path = Join-Path $AlignmentDirectory $name
        [int64]$offset = 0
        [int64]$newlines = 0
        [int64]$utterances = 0
        [string]$carry = ''
        [string]$lastUtteranceId = ''
        if ($PreviousState.ContainsKey($name)) {
            $offset = [int64]$PreviousState[$name].Offset
            $newlines = [int64]$PreviousState[$name].Newlines
            $carry = [string]$PreviousState[$name].Carry
            $lastUtteranceId = [string](
                $PreviousState[$name].LastUtteranceId
            )
            $utterances = [int64]$PreviousState[$name].Utterances
        }
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }
        $file = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
        if ($null -eq $file) {
            continue
        }
        if ([int64]$file.Length -lt $offset) {
            $offset = 0
            $newlines = 0
            $utterances = 0
            $carry = ''
            $lastUtteranceId = ''
        }
        [int64]$newOffset = $offset
        try {
            $delta = [ProjectNewlineScanner]::Scan(
                $path,
                $offset,
                $carry,
                $lastUtteranceId,
                ($name -eq 'word_intervals.csv')
            )
            $newOffset = [int64]$delta.NewOffset
            $carry = [string]$delta.Carry
            $newlines += [int64]$delta.Newlines
            $utterances += [int64]$delta.UtteranceTransitions
            $lastUtteranceId = [string]$delta.LastUtteranceId
        } catch {
            # 공유 읽기가 순간 실패하면 이전 offset부터 다음 heartbeat에 재시도한다.
        }
        $nextState[$name] = [PSCustomObject][ordered]@{
            Offset = $newOffset
            Carry = $carry
            Newlines = $newlines
            LastUtteranceId = $lastUtteranceId
            Utterances = $utterances
        }
        $metrics[$name] = @{
            Rows = [math]::Max(0L, $newlines - 1L)
            Bytes = [int64]$file.Length
            Utterances = $utterances
        }
        if ($null -eq $latestWriteUtc -or
            $file.LastWriteTimeUtc -gt $latestWriteUtc) {
            $latestWriteUtc = $file.LastWriteTimeUtc
        }
    }

    return [PSCustomObject][ordered]@{
        State = $nextState
        PhoneRows = [int64]$metrics['phone_intervals.csv'].Rows
        WordRows = [int64]$metrics['word_intervals.csv'].Rows
        WordUtterances = [int64](
            $metrics['word_intervals.csv'].Utterances
        )
        PhoneBytes = [int64]$metrics['phone_intervals.csv'].Bytes
        WordBytes = [int64]$metrics['word_intervals.csv'].Bytes
        LatestWriteUtc = $(if ($null -ne $latestWriteUtc) {
            $latestWriteUtc.ToString('o')
        } else { $null })
    }
}

# stderr 진행바가 없는 first-pass/final alignment에서도 실제 발화 처리량을
# 관측한다. 각 로그를 매번 처음부터 세지 않고, 파일별 마지막 byte offset
# 이후에 추가된 내용만 읽는다. 끝의 미완성 행은 Carry에 보존해 다음
# heartbeat에서 이어 붙이므로 쓰는 중인 행을 중복/누락 집계하지 않는다.
# 이 값은 생존·진행 진단용이며 MFA 성공 판정은 exit/DB/direct QC로 분리한다.
function Update-AlignmentLogProgress {
    param(
        [Parameter(Mandatory=$true)][string]$LogDirectory,
        [hashtable]$PreviousState = @{}
    )

    if (-not ('ProjectAlignmentLogScanner' -as [type])) {
        $alignmentScannerSource = @'
using System;
using System.IO;
using System.Text;

public sealed class ProjectAlignmentLogDelta {
    public long NewOffset { get; set; }
    public string Carry { get; set; }
    public long Processed { get; set; }
    public long Retried { get; set; }
    public long ErrorSignals { get; set; }
}

public static class ProjectAlignmentLogScanner {
    private static void CountLine(
        string line,
        ref long processed,
        ref long retried,
        ref long errorSignals
    ) {
        if (line.IndexOf(
                " - DEBUG - Processing ",
                StringComparison.Ordinal
            ) >= 0) {
            processed += 1;
        } else if (line.IndexOf(
                " - DEBUG - Retried ",
                StringComparison.Ordinal
            ) >= 0) {
            retried += 1;
        }
        if (line.IndexOf(
                "Traceback",
                StringComparison.OrdinalIgnoreCase
            ) >= 0 ||
            line.IndexOf(
                " - ERROR - ",
                StringComparison.OrdinalIgnoreCase
            ) >= 0 ||
            line.IndexOf(
                " - CRITICAL - ",
                StringComparison.OrdinalIgnoreCase
            ) >= 0) {
            errorSignals += 1;
        }
    }

    public static ProjectAlignmentLogDelta Scan(
        string path,
        long offset,
        string carry
    ) {
        long processed = 0;
        long retried = 0;
        long errorSignals = 0;
        string pending = carry ?? "";
        long newOffset = offset;
        byte[] buffer = new byte[65536];

        using (var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.ReadWrite | FileShare.Delete
        )) {
            stream.Seek(offset, SeekOrigin.Begin);
            while (true) {
                int read = stream.Read(buffer, 0, buffer.Length);
                if (read <= 0) {
                    break;
                }
                newOffset += read;
                string text = pending +
                    Encoding.UTF8.GetString(buffer, 0, read);
                int start = 0;
                while (true) {
                    int newline = text.IndexOf('\n', start);
                    if (newline < 0) {
                        break;
                    }
                    int length = newline - start;
                    if (length > 0 && text[newline - 1] == '\r') {
                        length -= 1;
                    }
                    CountLine(
                        text.Substring(start, length),
                        ref processed,
                        ref retried,
                        ref errorSignals
                    );
                    start = newline + 1;
                }
                pending = start < text.Length
                    ? text.Substring(start)
                    : "";
            }
        }

        return new ProjectAlignmentLogDelta {
            NewOffset = newOffset,
            Carry = pending,
            Processed = processed,
            Retried = retried,
            ErrorSignals = errorSignals
        };
    }
}
'@
        Add-Type -TypeDefinition $alignmentScannerSource -ErrorAction Stop
    }

    $nextState = @{}
    if (-not (Test-Path -LiteralPath $LogDirectory)) {
        return [PSCustomObject][ordered]@{
            State = $nextState
            FileCount = 0
            LogBytes = 0
            Processed = 0
            Retried = 0
            ErrorSignals = 0
            JobProcessed = @{}
            LatestWriteUtc = $null
        }
    }

    [int64]$totalBytes = 0
    [int64]$totalProcessed = 0
    [int64]$totalRetried = 0
    [int64]$totalErrorSignals = 0
    $jobProcessed = @{}
    $latestWriteUtc = $null
    $files = @(
        Get-ChildItem -LiteralPath $LogDirectory -File `
            -Filter 'align.*.log' -ErrorAction SilentlyContinue |
            Sort-Object Name
    )
    foreach ($file in $files) {
        $key = [string]$file.Name
        $prior = $null
        if ($PreviousState.ContainsKey($key)) {
            $prior = $PreviousState[$key]
        }
        [int64]$offset = 0
        [int64]$processed = 0
        [int64]$retried = 0
        [int64]$errorSignals = 0
        [string]$carry = ''
        if ($null -ne $prior) {
            $offset = [int64]$prior.Offset
            $processed = [int64]$prior.Processed
            $retried = [int64]$prior.Retried
            $errorSignals = [int64]$prior.ErrorSignals
            $carry = [string]$prior.Carry
        }

        # --clean/retry 등으로 로그가 교체·축소됐다면 이 파일만 0부터 센다.
        if ([int64]$file.Length -lt $offset) {
            $offset = 0
            $processed = 0
            $retried = 0
            $errorSignals = 0
            $carry = ''
        }

        [int64]$newOffset = $offset
        try {
            $delta = [ProjectAlignmentLogScanner]::Scan(
                $file.FullName, $offset, $carry
            )
            $newOffset = [int64]$delta.NewOffset
            $carry = [string]$delta.Carry
            $processed += [int64]$delta.Processed
            $retried += [int64]$delta.Retried
            $errorSignals += [int64]$delta.ErrorSignals
        } catch {
            # 읽기 공유가 순간 실패해도 이전 누적값을 보존하고 다음 heartbeat에
            # 같은 offset부터 재시도한다.
        }

        $nextState[$key] = [PSCustomObject][ordered]@{
            Offset = $newOffset
            Carry = $carry
            Processed = $processed
            Retried = $retried
            ErrorSignals = $errorSignals
        }
        $jobProcessed[$key] = $processed
        $totalProcessed += $processed
        $totalRetried += $retried
        $totalErrorSignals += $errorSignals
        $totalBytes += [int64]$file.Length
        if ($null -eq $latestWriteUtc -or
            $file.LastWriteTimeUtc -gt $latestWriteUtc) {
            $latestWriteUtc = $file.LastWriteTimeUtc
        }
    }

    return [PSCustomObject][ordered]@{
        State = $nextState
        FileCount = $files.Count
        LogBytes = $totalBytes
        Processed = $totalProcessed
        Retried = $totalRetried
        ErrorSignals = $totalErrorSignals
        JobProcessed = $jobProcessed
        LatestWriteUtc = $(if ($null -ne $latestWriteUtc) {
            $latestWriteUtc.ToString('o')
        } else { $null })
    }
}

# 어떤 D: 경로도 만들기 전에 SSD 정본 라벨부터 검증한다.
$expectLabel = 'DATA_SSD'
$dLabel = $null
if (Get-Command Get-Volume -ErrorAction SilentlyContinue) {
    $dLabel = (Get-Volume -DriveLetter D -ErrorAction SilentlyContinue).FileSystemLabel
}
if ([string]::IsNullOrEmpty($dLabel)) {
    $dLabel = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='D:'" -ErrorAction SilentlyContinue).VolumeName
}
if ([string]::IsNullOrEmpty($dLabel)) {
    try { $dLabel = ([IO.DriveInfo]::new('D:\')).VolumeLabel } catch {}
}
if ($dLabel -ne $expectLabel) {
    Write-Error "D: 볼륨 라벨이 '$expectLabel'이 아님(현재 '$dLabel') — 어떤 파일도 만들지 않고 중단"
    exit 1
}
if (-not $SkipPreflight) {
    $preflightArgs = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        (Join-Path $PSScriptRoot 'preflight_eojeol_realign.ps1')
    )
    if ($Year) { $preflightArgs += @('-Year', $Year) }
    $preflightArgs += @('-SearchMasterRoot', $searchMasterRoot)
    if ($PreferD) { $preflightArgs += '-PreferD' }
    & powershell.exe @preflightArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Error "MFA preflight 실패(exit $LASTEXITCODE). 리포 logs의 최신 preflight 보고서 확인."
        exit 1
    }
}
$doneDir = Join-Path $stateRoot "done"
New-Item -ItemType Directory -Force $doneDir | Out-Null
# temp: MFA는 정렬 반복 중 wav이 아니라 temp의 특징값(MFCC)·DB를 계속 읽음.
# 연도당 temp ~15-35GB(2021 실측 33GB). Get-WorkPaths가 신규 연도별 peak
# 문턱을 적용하고, 검증된 resume temp는 남은 10GB를 하한으로 둔다.
$logDir  = Join-Path $stateRoot "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("eojeol_realign_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")

function Say($m) { $l = "[$(Get-Date -Format 'MM-dd HH:mm:ss')] $m"; Write-Host $l -ForegroundColor Cyan; Add-Content $log $l -Encoding UTF8 }
function Read-DoneMarker(
    $path, $year, $stage, $inputContractId = "",
    $alignmentContractId = ""
) {
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    try {
        $data = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
        $valid = ($data.year -eq $year -and $data.stage -eq $stage -and
                  $data.g2p_model -eq 'korean_mfa')
        if ($valid -and -not [string]::IsNullOrWhiteSpace($inputContractId)) {
            $valid = (
                [string]$data.details.input_contract_id -eq
                [string]$inputContractId -and
                [IO.Path]::GetFullPath(
                    [string]$data.details.search_master_root
                ).TrimEnd('\') -eq
                [IO.Path]::GetFullPath($searchMasterRoot).TrimEnd('\')
            )
        }
        if ($valid -and -not [string]::IsNullOrWhiteSpace(
            $alignmentContractId
        )) {
            $valid = (
                [string]$data.details.alignment_contract_id -eq
                [string]$alignmentContractId
            )
        }
        if ($valid -and $stage -eq 'merge') {
            $recordedStage = [string]$data.details.staging_output_root
            $valid = (
                -not [string]::IsNullOrWhiteSpace($recordedStage) -and
                [IO.Path]::GetFullPath($recordedStage).TrimEnd('\') -eq
                [IO.Path]::GetFullPath($g2pStage).TrimEnd('\')
            )
        }
        return $valid
    } catch { return $false }
}
function Archive-StaleTemp($path, $allowedRoot, $year, $reason) {
    $resolved = [IO.Path]::GetFullPath($path).TrimEnd('\')
    $allowed = [IO.Path]::GetFullPath($allowedRoot).TrimEnd('\')
    if ((Split-Path -Parent $resolved) -ne $allowed) {
        throw "stale temp 보존 경계 위반: $resolved (허용 부모 $allowed)"
    }
    if (-not (Test-Path -LiteralPath $resolved)) { return $null }
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $driveTag = (Split-Path -Qualifier $resolved).Substring(0, 1)
    $archiveDir = Join-Path $stateRoot (
        "archive_stale_temp\$stamp\$driveTag"
    )
    New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null
    $destination = Join-Path $archiveDir $year
    if (Test-Path -LiteralPath $destination) {
        throw "stale temp archive 충돌: $destination"
    }
    Say "$year 입력 계약 불일치 temp를 삭제하지 않고 보존 이동: $resolved -> $destination"
    Move-Item -LiteralPath $resolved -Destination $destination
    $record = [ordered]@{
        year = $year
        source = $resolved
        archived = $destination
        reason = $reason
        archived_at = (Get-Date).ToString('o')
    }
    $record | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath (Join-Path $archiveDir "$year.reason.json") -Encoding UTF8
    return $destination
}
function Write-TempContract(
    $path, $year, $inputContractId, $alignmentContract,
    $tempYear, $status
) {
    $dir = Split-Path -Parent $path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $partial = "$path.$PID.partial"
    [ordered]@{
        year = $year
        input_contract_id = $inputContractId
        lab_input_contract_id = $inputContractId
        alignment_contract_id = $alignmentContract.alignment_contract_id
        mfa_runtime = $alignmentContract.runtime
        mfa_models = $alignmentContract.models
        search_master_root = $searchMasterRoot
        temp_year = $tempYear
        status = $status
        updated_at = (Get-Date).ToString('o')
    } | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $partial -Encoding UTF8
    Move-Item -LiteralPath $partial -Destination $path -Force
}
function Write-DoneMarker(
    $path, $year, $stage, $details, $inputContractId,
    $alignmentContract
) {
    $tmpMarker = "$path.$PID.partial"
    $details.input_contract_id = $inputContractId
    $details.lab_input_contract_id = $inputContractId
    $details.alignment_contract_id = (
        $alignmentContract.alignment_contract_id
    )
    $details.mfa_runtime = $alignmentContract.runtime
    $details.mfa_models = $alignmentContract.models
    $payload = [ordered]@{
        year = $year
        stage = $stage
        g2p_model = 'korean_mfa'
        completed_at = (Get-Date).ToString('o')
        git_commit = (& git -C $root rev-parse HEAD 2>$null)
        details = $details
    }
    $payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $tmpMarker -Encoding UTF8
    Move-Item -LiteralPath $tmpMarker -Destination $path -Force
}
function Write-JsonLine($path, $payload) {
    $parent = Split-Path -Parent $path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $payload | ConvertTo-Json -Depth 6 -Compress |
        Add-Content -LiteralPath $path -Encoding UTF8
}
function Remove-SafeYearPath($path, $allowedRoot) {
    $resolved = [IO.Path]::GetFullPath($path).TrimEnd('\')
    $allowed = [IO.Path]::GetFullPath($allowedRoot).TrimEnd('\')
    if ((Split-Path -Parent $resolved) -ne $allowed) {
        throw "삭제 경계 위반: $resolved (허용 부모 $allowed)"
    }
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

$years = if ($Year) { @($Year) } else {
    @('2020','2021','2022','2023','2024','2025')
}
$runId = "eojeol_g2p_" + ($years -join '-') + "_" + `
         (Get-Date -Format "yyyyMMdd_HHmmss")

Say "어절 재정렬 시작 (대상: $($years -join ', '), run_id=$runId)"
Say "신규 G2P 4-tier는 기존본을 건드리지 않고 staging에 기록: $g2pStage"
Say "pre-MFA search master 입력: $searchMasterRoot"
Say ("TextGrid 생성 경로: " + $(if ($UseDirectDbExport) {
    "MFA DB -> 4-tier 직접(검증된 고속 경로, raw 2-tier 중복 생성 안 함)"
} else {
    "MFA built-in raw export -> 4-tier 병합(보수적 fallback)"
}))
Say ("작업 드라이브 정책: " + $(if ($PreferD) {
    "D: 우선(신규 temp/output); 검증된 resume temp만 원래 드라이브 유지"
} else {
    "자동(C: 여유 문턱 충족 시 C:, 아니면 D:)"
}))

foreach ($y in $years) {
    Say "===== $y 시작 ====="

    # 1) 검증된 pre-MFA search master의 reference form으로 lab을 만들고
    #    입력 계약 ID를 얻는다. 계약 marker가 같으면 재실행은 즉시 반환한다.
    Say "$y [1/3] pre-MFA 입력계약 확인 + lab 생성/내용검증..."
    $labHeartbeatFile = Join-Path $logDir (
        "lab_{0}_{1}_heartbeat.jsonl" -f $y, $runId
    )
    & $py (Join-Path $pydir "realign_eojeol_build_corpus.py") `
        --year $y --search-master-root $searchMasterRoot `
        --progress-jsonl $labHeartbeatFile
    if ($LASTEXITCODE -ne 0) { Say "!! $y lab 실패 (exit $LASTEXITCODE) — 중단"; exit 1 }
    $labReportPath = Join-Path $logDir "lab_build_${y}_latest.json"
    try {
        $labReport = Get-Content -LiteralPath $labReportPath -Raw -Encoding UTF8 |
                     ConvertFrom-Json
        $inputContractId = [string]$labReport.input_contract_id
        if ($labReport.status -ne 'passed' -or
            [string]::IsNullOrWhiteSpace($inputContractId)) {
            throw "status/input_contract_id 누락"
        }
    } catch {
        Say "!! $y lab 입력계약 보고서 손상: $labReportPath"
        exit 1
    }
    Say "$y 입력 계약: $($inputContractId.Substring(0,12)) / $searchMasterRoot"
    # lab/CSV 계약과 별도로 모델 파일 내용·MFA/Pynini 판본을 고정한다.
    # 같은 이름의 korean_mfa 파일이 바뀌면 alignment_contract_id가 달라져
    # 기존 temp·marker를 재사용하지 않는다.
    $alignmentContractPath = Join-Path $stateRoot (
        "alignment_contracts\{0}.json" -f $y
    )
    & $py (Join-Path $pydir "build_mfa_alignment_contract.py") `
        --year $y --lab-input-contract-id $inputContractId `
        --acoustic-model-path $acousticModelPath `
        --dictionary-model-path $dictionaryModelPath `
        --g2p-model-path $g2pModelPath `
        --output $alignmentContractPath
    if ($LASTEXITCODE -ne 0) {
        Say "!! $y MFA alignment contract 생성 실패"
        exit 1
    }
    try {
        $alignmentContract = Get-Content -LiteralPath `
            $alignmentContractPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $alignmentContractId = [string](
            $alignmentContract.alignment_contract_id
        )
        if (
            $alignmentContract.status -ne 'passed' -or
            [string]$alignmentContract.year -ne $y -or
            [string]$alignmentContract.lab_input_contract_id -ne
                $inputContractId -or
            [string]::IsNullOrWhiteSpace($alignmentContractId)
        ) {
            throw "alignment contract identity/status 불일치"
        }
    } catch {
        Say (
            "!! $y MFA alignment contract 손상: " +
            "$alignmentContractPath ($($_.Exception.Message))"
        )
        exit 1
    }
    Say (
        "$y 정렬 계약: $($alignmentContractId.Substring(0,12)) / " +
        "acoustic=$($alignmentContract.models.acoustic.sha256.Substring(0,12)) " +
        "dictionary=$($alignmentContract.models.dictionary.sha256.Substring(0,12)) " +
        "g2p=$($alignmentContract.models.g2p.sha256.Substring(0,12))"
    )
    $existingAlignDone = Read-DoneMarker (
        Join-Path $doneDir "$y.align_done"
    ) $y 'align' $inputContractId $alignmentContractId
    $existingMergeDone = Read-DoneMarker (
        Join-Path $doneDir "$y.merge_done"
    ) $y 'merge' $inputContractId $alignmentContractId
    if ($existingAlignDone -and $existingMergeDone) {
        Say "$y 같은 입력·정렬 계약으로 이미 전부 완료 — 즉시 건너뜀"
        continue
    }

    # 신규 계산에는 analysis-ready를 요구하되, 같은 계약의 수시간짜리 temp를
    # 재개할 때는 이미 계산된 DB를 버리지 않도록 execution gate를 적용한다.
    # 후자의 분석 제외·복구 판정은 final 독립 QC에서 다시 강제한다.
    $tempContractPath = Join-Path $stateRoot "input_contracts\$y.json"
    $tempContract = $null
    if (Test-Path -LiteralPath $tempContractPath) {
        try {
            $tempContract = Get-Content -LiteralPath $tempContractPath -Raw `
                -Encoding UTF8 | ConvertFrom-Json
        } catch {
            $tempContract = $null
        }
    }
    $trustedResumeTemp = $false
    foreach ($candidate in @(
        @{ Path = (Join-Path $tmpPrimary $y); Root = $tmpPrimary },
        @{ Path = (Join-Path $tmpSecondary $y); Root = $tmpSecondary }
    )) {
        if (-not (Test-Path -LiteralPath $candidate.Path)) { continue }
        if (
            $null -ne $tempContract -and
            [string]$tempContract.input_contract_id -eq $inputContractId -and
            [string]$tempContract.alignment_contract_id -eq
                $alignmentContractId -and
            [IO.Path]::GetFullPath(
                [string]$tempContract.temp_year
            ).TrimEnd('\') -eq
                [IO.Path]::GetFullPath($candidate.Path).TrimEnd('\')
        ) {
            $trustedResumeTemp = $true
        }
    }
    $integrityGateProfile = if ($trustedResumeTemp) {
        'execution'
    } else {
        'analysis'
    }
    # MFA 시작 전에 F29형 CSV–WAV 발화 번호 밀림과 형태소 원천 누락을
    # 전수 검사한다. 신규 계산은 물리적 전사–구간 불일치와 원음 정상 회수
    # 후보까지 차단하고, 검증된 resume은 분류 완결성과 실행 무결성을 강제한다.
    $inputIntegrityReport = Join-Path $root (
        "outputs\reports\PREFLIGHT_mfa_input_integrity_{0}_{1}.json" -f
        $y, $runId
    )
    & $py (Join-Path $pydir "audit_mfa_year_readiness.py") `
        --years $y --search-master-root $searchMasterRoot `
        --wav-root $wavRoot `
        --morph-textgrid-root $morphTextGridRoot `
        --source-pcm-check $sourcePcmCheck `
        --gate-profile $integrityGateProfile --output $inputIntegrityReport
    if ($LASTEXITCODE -ne 0) {
        Say (
            "!! $y MFA 입력 무결성 gate 실패 — 정렬 시작 금지: " +
            $inputIntegrityReport
        )
        exit 1
    }
    try {
        $inputIntegrityData = Get-Content -LiteralPath `
            $inputIntegrityReport -Raw -Encoding UTF8 | ConvertFrom-Json
        $integrityYear = @(
            $inputIntegrityData.years |
            Where-Object { [string]$_.year -eq $y }
        )
        $integrityPassProperty = if (
            $integrityGateProfile -eq 'analysis'
        ) {
            'analysis_ready_gates_pass'
        } else {
            'execution_gates_pass'
        }
        if (
            $inputIntegrityData.gate_profile -ne $integrityGateProfile -or
            -not [bool]$inputIntegrityData.all_years_pass -or
            $integrityYear.Count -ne 1 -or
            -not [bool]$integrityYear[0].$integrityPassProperty
        ) {
            throw "$integrityGateProfile gate identity/result 불일치"
        }
    } catch {
        Say (
            "!! $y MFA 입력 무결성 보고서 손상: " +
            "$inputIntegrityReport ($($_.Exception.Message))"
        )
        exit 1
    }
    Say (
        "$y MFA 입력 무결성 통과(profile=$integrityGateProfile): " +
        "duration failed sessions=" +
        "$($integrityYear[0].counts.duration_sessions_failed), " +
        "text-duration impossible=" +
        "$($integrityYear[0].counts.source_segment_text_duration_impossible), " +
        "morph missing=$($integrityYear[0].counts.morph_source_missing), " +
        "unclassified=$($integrityYear[0].counts.morph_source_unclassified)"
    )
    $directPartialRoot = Join-Path $g2pStage (
        "_partial_direct_db\" + $alignmentContractId
    )
    $directPartialYear = Join-Path $directPartialRoot $y
    $finalStageYear = Join-Path $g2pStage $y

    # 기존 temp는 같은 입력계약임이 증명될 때만 재사용한다. 계약이 없거나 다르면
    # 삭제하지 않고 D:\mfa_eojeol\archive_stale_temp 아래로 보존 이동한다.
    foreach ($candidate in @(
        @{ Path = (Join-Path $tmpPrimary $y); Root = $tmpPrimary },
        @{ Path = (Join-Path $tmpSecondary $y); Root = $tmpSecondary }
    )) {
        if (-not (Test-Path -LiteralPath $candidate.Path)) { continue }
        $trusted = (
            $null -ne $tempContract -and
            [string]$tempContract.input_contract_id -eq $inputContractId -and
            [string]$tempContract.alignment_contract_id -eq
                $alignmentContractId -and
            [IO.Path]::GetFullPath([string]$tempContract.temp_year).TrimEnd('\') -eq
            [IO.Path]::GetFullPath($candidate.Path).TrimEnd('\')
        )
        if (-not $trusted) {
            try {
                Archive-StaleTemp $candidate.Path $candidate.Root $y `
                    "missing_or_mismatched_input_contract"
            } catch {
                Say "!! $y stale temp 보존 실패: $($_.Exception.Message)"
                exit 1
            }
        }
    }

    # 연도별 작업 드라이브 결정(기존 temp 우선 — 위 Get-WorkDrive 참조). align이
    # 이미 끝난 연도라도 아래 병합(3/3) 단계에 $out이 필요하므로 if/else 밖에서 계산.
    $workPaths = Get-WorkPaths $y
    $out = $workPaths.OutRoot
    $tmp = $workPaths.TempRoot
    $minStartFreeGB = [double]$workPaths.MinFreeGB
    $workDrive = (Split-Path -Qualifier $tmp).TrimEnd('\')
    $tmpYear = Join-Path $tmp $y
    $outYear = Join-Path $out $y
    New-Item -ItemType Directory -Force $out | Out-Null

    # 2) MFA 정렬 — 완료 마커 있으면 건너뜀. 진행바가 화면에 실시간.
    $doneMark = Join-Path $doneDir "$y.align_done"
    if (Read-DoneMarker $doneMark $y 'align' $inputContractId `
            $alignmentContractId) {
        Say "$y [2/3] MFA 이미 완료(.done) — 건너뜀"
    } else {
        if ((Test-Path -LiteralPath $doneMark) -and
            -not (Read-DoneMarker $doneMark $y 'align' $inputContractId `
                $alignmentContractId)) {
            Say "!! $y align_done이 현재 입력계약과 불일치 — 자동 재사용 금지: $doneMark"
            exit 1
        }
        if ((Test-Path -LiteralPath $outYear) -and
            -not (Test-Path -LiteralPath $tmpYear)) {
            Say "!! $y 마커·temp 없이 MFA 원출력만 존재 — stale/부분 출력 판별 전 실행 금지: $outYear"
            exit 1
        }
        # 작업 드라이브 여유 가드 — temp가 도중에 차면 연도 전체 재작업이라 미리 중단
        $freeGB = [math]::Round(
            ([IO.DriveInfo]::new($workDrive)).AvailableFreeSpace / 1GB, 1
        )
        if ($freeGB -lt $minStartFreeGB) {
            Say "!! $workDrive 여유 ${freeGB}GB < ${minStartFreeGB}GB — temp($tmp) 부족 위험, 중단. 정리 후 재실행."
            exit 1
        }

        # ★ 평면 구조 가드 (2026-07-19, 1화자 사고 재발 방지): 연도 루트에 wav가 바로
        #   있으면 = 세션 재구성 안 됨 → MFA가 연도 전체를 화자 1명으로 오인(품질·병렬
        #   붕괴). 지연 열거라 세션 구조면 즉시 통과, 평면이면 첫 파일에서 걸림.
        $flatWav = [IO.Directory]::EnumerateFiles((Join-Path $wavRoot $y), "*.wav") |
                   Select-Object -First 1
        if ($flatWav) {
            Say "!! $y 코퍼스가 평면 구조(예: $(Split-Path $flatWav -Leaf)) — 1화자 오인 위험."
            Say "   먼저 실행: python scripts\python\restructure_wav_sessions.py --root $wavRoot --year $y --apply"
            exit 1
        }
        # 1.5) 깨진 wav 격리 (2026-07-18): 0바이트 wav 1개가 MFA 로딩 '말미'에 전체를
        #   실패시킴(7/17·7/18 두 차례, 각 5h+ 손실). 연도당 ~5분 보험.
        Say "$y [1.5/3] 깨진 wav 스캔·격리 (0바이트 등)..."
        & $py (Join-Path $pydir "quarantine_bad_wavs.py") --year $y --apply
        if ($LASTEXITCODE -ne 0) { Say "!! $y wav 스캔 실패 (exit $LASTEXITCODE) — 중단"; exit 1 }

        # ★ stderr를 파일로 캡처 (2026-07-18): MFA는 진행바·traceback을 전부 stderr로 쓰고,
        #   에러 traceback은 자기 로그 파일이 닫힌 '뒤' 출력되는 구조라 콘솔이 닫히면 유실됨
        #   (7/17 2020 실패 원인 유실 사고). 파일로 받되, 1분마다 파일 끝(=현재 진행바)을
        #   요약해 콘솔에 하트비트로 찍음 — 실시간성 유지 + 실패 원인 영구 보존.
        # ★ 이어가기 (2026-07-18): 같은 연도 재시도 시 temp DB가 남아 있으면 1차는
        #   --clean 없이 실행 → MFA가 끝난 단계(코퍼스 로딩 5.5h, MFCC 등)를 재사용.
        #   실패하면 temp 비우고 --clean 전체 재실행(2차 폴백 — 어중간한 DB 방어).
        #   lab을 바꾼 적 없는 동일-연도 재시도에만 안전(연도 첫 시도는 항상 --clean).
            $errFile = Join-Path $logDir "mfa_${y}_stderr.log"
            $heartbeatFile = Join-Path $logDir (
                "mfa_{0}_{1}_heartbeat.jsonl" -f $y, $runId
            )
            $tries = @(); if (Test-Path $tmpYear) { $tries += $false }; $tries += $true
        $ok = $false
        foreach ($doClean in $tries) {
            $mode = if ($doClean) { "--clean 전체" } else { "이어가기(temp 재사용)" }
            Say "$y [2/3] MFA 정렬 — $mode (num_jobs $numJobs, temp=$tmp 여유 ${freeGB}GB, 진행=1분 하트비트)..."
            if (Test-Path $errFile) { Move-Item $errFile "$errFile.prev" -Force }
            # G2P 추가 (2026-07-23): korean_mfa 사전에 없는 활용형(것을·다니는 등)이
            #   phones에서 spn으로 버려지던 문제 해결 — 파일럿 spn 27.5->0%, 것을=[거슬] 확인.
            #   사전·음향모델과 동일 버전 g2p 모델. align.py em-dash 패치(export 직전 crash)도 수정 완료.
            #   완료 마커는 G2P 모델·연도·단계·staging 경로까지 검증하므로
            #   와일드카드로 직접 삭제하지 않는다.
            $aArgs = @('align', (Join-Path $wavRoot $y),
                       $dictionaryModelPath, $acousticModelPath,
                       (Join-Path $out $y), '--num_jobs', "$numJobs", '--no_tokenization',
                       '--g2p_model_path', $g2pModelPath,
                       '--temporary_directory', $tmp, '--output_format', 'long_textgrid')
            if ($doClean) { $aArgs += '--clean' }
            Write-TempContract $tempContractPath $y $inputContractId `
                $alignmentContract $tmpYear "mfa_running"
            $priorSkipExport = $env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT
            if ($UseDirectDbExport) {
                $env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT = '1'
            } else {
                Remove-Item Env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT `
                    -ErrorAction SilentlyContinue
            }
            try {
                $p = Start-Process -FilePath $mfa -ArgumentList $aArgs `
                     -NoNewWindow -PassThru -RedirectStandardError $errFile
            } finally {
                if ($null -eq $priorSkipExport) {
                    Remove-Item Env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT `
                        -ErrorAction SilentlyContinue
                } else {
                    $env:MFA_PROJECT_SKIP_TEXTGRID_EXPORT = $priorSkipExport
                }
            }
            $null = $p.Handle   # PS5.1 함정: 핸들 미참조 시 ExitCode가 빈 값이 됨(성공을 실패로 오판)
            # ★ 교착(hang) 자동 감지·복구 (2026-07-21 도입, 2026-07-22 오판 수정):
            #   stderr 텍스트 무변화만으론 판단 불가(정상 단계도 몇 분씩 새 줄 없음 — 실측
            #   오판 사례). 1차로 "CPU 완전 무변화"를 썼으나 이것도 실패: 2021에서 export
            #   워커 스레드가 예외로 죽어 메인 스레드가 영원히 대기하는 진짜 교착인데도,
            #   다른 스레드의 미세한 폴링 활동 때문에 60초마다 CPU가 1~2초씩 계속 늘어
            #   "무변화" 조건이 한 번도 안 걸리고 4.5시간 그대로 방치됨(실측).
            #   → **누적 증가량 기준**으로 교체: 최근 $stallMinutes분 동안 늘어난 CPU
            #   시간이 ${stallMinCpuSec}초 미만이면 교착으로 판정(정상 작업은 스레드
            #   여러 개가 몇 분 새 최소 이 정도는 반드시 씀 — 노이즈 수준을 크게 웃돎).
            # ★ 교착 감지 재설계 (2026-07-23): CPU 증가량 단독 기준이 g2p 추가로 새로 생긴
            #   저CPU 프리루드('Generating pronunciations'->'Generating MFCCs')를 교착으로
            #   오판(실측: 완주 중 MFA를 죽이고 --clean 루프). MFA 자체 진행카운터(N/M) +
            #   단계 인지로 교체 — 카운터가 조금이라도 늘면 안 죽이고, 저CPU 셋업단계는 봐준다.
            $stallMinutes = 30
            $stallMinCpuSec = 10
            $setupStallMin = 45
            $cpuHistory = New-Object System.Collections.Generic.List[object]
            $setupRe = 'Setting up|Loading corpus|Found \d+ speakers|Initializing multiprocessing|Normalizing text|Generating pronunciations|Generating MFCCs|Compiling training graphs'
            $alignRe = 'Generating alignments|Collecting|Exporting|Performing.*lignment|Analyzing'
                $phase = 'setup'
                $lastCount = -1
                $lastCountChange = Get-Date
                $watchdogKilled = $false
                $mfaReportedDone = $false
                # 종료된 worker의 CPU가 live 합계에서 빠져 watchdog 누적치가
                # 역행하지 않도록 마지막 값을 retired 합계에 보존한다.
                $retiredTreeCpuSeconds = 0.0
                $lastTreeCpuByPid = @{}
                $alignmentLogState = @{}
                $alignmentProgress = $null
                $intervalCsvState = @{}
                $intervalProgress = $null
                $systemMemory = $null
                Write-JsonLine $heartbeatFile ([ordered]@{
                    event = 'mfa_process_started'
                    recorded_at = (Get-Date).ToString('o')
                    run_id = $runId
                    year = $y
                    pid = $p.Id
                    mode = $mode
                    temp_year = $tmpYear
                    output_year = $outYear
                })
                while (-not $p.HasExited) {
                Start-Sleep -Seconds 60
                $tail = ""
                $seg = @()
                try {
                    $fs = [IO.File]::Open($errFile, 'Open', 'Read', 'ReadWrite')
                    $n = [Math]::Min(3000, $fs.Length)
                    if ($n -gt 0) {
                        [void]$fs.Seek(-$n, 'End')
                        $buf = New-Object byte[] $n
                        [void]$fs.Read($buf, 0, $n)
                        $seg = [Text.Encoding]::UTF8.GetString($buf) -split "[`r`n]" |
                               ForEach-Object { ($_ -replace '\e\[[0-9;]*m', '').Trim() } |
                               Where-Object { $_ -match '\S' }
                        if ($seg) { $tail = $seg[-1] }
                    }
                    $fs.Close()
                } catch {}
                Write-Host ("[{0}] {1} MFA 진행: {2}" -f (Get-Date -Format 'HH:mm:ss'), $y, $tail)
                $now = Get-Date
                $processMetrics = Get-ProcessTreeMetrics `
                    -RootProcessId $p.Id
                $systemMemory = Get-SystemMemoryMetrics
                $cpuState = Update-ProcessTreeCpuAccumulator `
                    -PreviousCpuByPid $lastTreeCpuByPid `
                    -CurrentCpuByPid $processMetrics.CpuByPid `
                    -RetiredCpuSeconds $retiredTreeCpuSeconds
                $retiredTreeCpuSeconds = `
                    [double]$cpuState.RetiredCpuSeconds
                $lastTreeCpuByPid = $cpuState.CpuByPid
                $curCpu = [double]$cpuState.TotalCpuSeconds
                $cpuHistory.Add([PSCustomObject]@{ Time = $now; Cpu = $curCpu })
                while ($cpuHistory.Count -gt 0 -and ($now - $cpuHistory[0].Time).TotalMinutes -gt ($stallMinutes + 2)) {
                    $cpuHistory.RemoveAt(0)
                }
                $old = $cpuHistory | Where-Object { ($now - $_.Time).TotalMinutes -ge $stallMinutes } | Select-Object -First 1
                # 단계 갱신: 정렬 신호를 먼저 확인해 프리루드->정렬 전이를 확실히 잡음(한 번 align이면 유지)
                $segText = ($seg -join "`n")
                if ($segText -match $alignRe) { $phase = 'align' }
                elseif ($segText -match $setupRe) { $phase = 'setup' }
                if ($phase -eq 'align') {
                    $alignmentProgress = Update-AlignmentLogProgress `
                        -LogDirectory (
                            Join-Path $tmpYear 'alignment\log'
                        ) `
                        -PreviousState $alignmentLogState
                    $alignmentLogState = $alignmentProgress.State
                    $intervalProgress = Update-IntervalCsvProgress `
                        -AlignmentDirectory (
                            Join-Path $tmpYear 'alignment'
                        ) `
                        -PreviousState $intervalCsvState
                    $intervalCsvState = $intervalProgress.State
                }
                # MFA 진행카운터(N/M) 파싱 — 값이 바뀌면 살아있는 것
                    if ($tail -match '([\d,]+)\s*/\s*[\d,]+') {
                        $c = [int64](($matches[1]) -replace ',', '')
                        if ($c -ne $lastCount) { $lastCount = $c; $lastCountChange = $now }
                    }
                $hasCounter = ($tail -match '[\d,]+\s*/\s*[\d,]+')
                $frozenMin = [math]::Round(($now - $lastCountChange).TotalMinutes, 1)
                # ★ 완주 직후 오살 방지 (2026-07-23 실사고): MFA가 "Done!"까지 찍고 막판
                #   정리(파일 flush·DB 종료 등) 중 CPU가 잠깐 낮아진 순간을 교착으로
                #   오판해 강제종료 — 2021 137만 건 전량 정상 export 완료 직후였음
                #   (temp만 날아감, 실제 출력은 무사했지만 위험한 우연). "Done!"류
                #   완주 신호가 보이면 죽이지 않고 자연 종료를 더 기다림.
                # ★ G2P 오살 방지 (2026-07-23): 'Generating pronunciations'는 사전·
                #   FST 빌드/헬퍼 단계라 mfa·python CPU가 거의 안 오름 → 교착으로 오판돼
                #   완주 중인 정렬을 죽이고 --clean 루프에 빠지는 사고 확인. 이 단계에선
                #   죽이지 않고 자연 진행을 기다림(g2p 추가 후 새로 생긴 구간).
                    if ($segText -match 'Done!|Everything took') {
                        $mfaReportedDone = $true
                    }
                    if ($mfaReportedDone) { $phase = 'finalizing' }
                    $kill = $false
                if (-not $mfaReportedDone -and $phase -eq 'align') {
                    # 정렬/내보내기: 카운터가 $stallMinutes분간 정지 = 교착(2021 export형).
                    #   바가 아예 없는 구간(예: 일부 export)은 CPU 무증가로 폴백 판정.
                    if ($hasCounter) {
                        if ($frozenMin -ge $stallMinutes) { $kill = $true }
                    } elseif ($old -and ($curCpu - $old.Cpu) -lt $stallMinCpuSec) { $kill = $true }
                } elseif (-not $mfaReportedDone) {
                    # 셋업/프리루드(코퍼스로딩 최대 5.5h·정규화·g2p·MFCC·그래프): 저CPU가 정상 → 안 죽임.
                    #   단 카운터가 $setupStallMin분간 같은 값에 붙박이면 진짜 실패로 보고 중단.
                        if ($hasCounter -and $frozenMin -ge $setupStallMin) { $kill = $true }
                    }
                    $freeNowGB = $null
                    try {
                        $freeNowGB = [math]::Round(
                            ([IO.DriveInfo]::new($workDrive)).AvailableFreeSpace /
                            1GB, 2
                        )
                    } catch {}
                    Write-JsonLine $heartbeatFile ([ordered]@{
                        event = 'heartbeat'
                        recorded_at = $now.ToString('o')
                        run_id = $runId
                        year = $y
                        pid = $p.Id
                        phase = $phase
                        counter_current = $(if ($lastCount -ge 0) {
                            $lastCount
                        } else { $null })
                        counter_frozen_minutes = $frozenMin
                        cpu_seconds = $curCpu
                        tree_cpu_seconds = $curCpu
                        tree_live_cpu_seconds = `
                            $cpuState.LiveCpuSeconds
                        tree_retired_cpu_seconds = `
                            $retiredTreeCpuSeconds
                        metrics_scope = $processMetrics.Scope
                        tree_process_count = $processMetrics.ProcessCount
                        tree_python_process_count = `
                            $processMetrics.PythonProcessCount
                        tree_thread_count = $processMetrics.ThreadCount
                        tree_working_set_mb = [math]::Round(
                            $processMetrics.WorkingSetBytes / 1MB, 1
                        )
                        tree_private_memory_mb = [math]::Round(
                            $processMetrics.PrivateMemoryBytes / 1MB, 1
                        )
                        tree_process_ids = @($processMetrics.ProcessIds)
                        system_memory_available_mb = $(if (
                            $null -ne $systemMemory
                        ) {
                            $systemMemory.AvailableMemoryMB
                        } else { $null })
                        system_commit_used_gb = $(if (
                            $null -ne $systemMemory
                        ) {
                            $systemMemory.CommitUsedGB
                        } else { $null })
                        system_commit_limit_gb = $(if (
                            $null -ne $systemMemory
                        ) {
                            $systemMemory.CommitLimitGB
                        } else { $null })
                        system_commit_percent = $(if (
                            $null -ne $systemMemory
                        ) {
                            $systemMemory.CommitPercent
                        } else { $null })
                        memory_pressure_warning = $(if (
                            $null -ne $systemMemory
                        ) {
                            $systemMemory.PressureWarning
                        } else { $null })
                        alignment_processed = $(if (
                            $null -ne $alignmentProgress
                        ) {
                            $alignmentProgress.Processed
                        } else { $null })
                        alignment_retried = $(if (
                            $null -ne $alignmentProgress
                        ) {
                            $alignmentProgress.Retried
                        } else { $null })
                        alignment_error_signals = $(if (
                            $null -ne $alignmentProgress
                        ) {
                            $alignmentProgress.ErrorSignals
                        } else { $null })
                        alignment_log_file_count = $(if (
                            $null -ne $alignmentProgress
                        ) {
                            $alignmentProgress.FileCount
                        } else { 0 })
                        alignment_log_bytes = $(if (
                            $null -ne $alignmentProgress
                        ) {
                            $alignmentProgress.LogBytes
                        } else { 0 })
                        alignment_job_processed = $(if (
                            $null -ne $alignmentProgress
                        ) {
                            $alignmentProgress.JobProcessed
                        } else { @{} })
                        alignment_log_latest_write_utc = $(if (
                            $null -ne $alignmentProgress
                        ) {
                            $alignmentProgress.LatestWriteUtc
                        } else { $null })
                        interval_phone_rows = $(if (
                            $null -ne $intervalProgress
                        ) {
                            $intervalProgress.PhoneRows
                        } else { 0 })
                        interval_word_rows = $(if (
                            $null -ne $intervalProgress
                        ) {
                            $intervalProgress.WordRows
                        } else { 0 })
                        interval_word_utterances = $(if (
                            $null -ne $intervalProgress
                        ) {
                            $intervalProgress.WordUtterances
                        } else { 0 })
                        interval_word_utterance_pct = $(if (
                            $null -ne $intervalProgress -and
                            $null -ne $alignmentProgress -and
                            [int64]$alignmentProgress.Processed -gt 0
                        ) {
                            [math]::Round(
                                100.0 *
                                [int64]$intervalProgress.WordUtterances /
                                [int64]$alignmentProgress.Processed,
                                2
                            )
                        } else { $null })
                        interval_phone_bytes = $(if (
                            $null -ne $intervalProgress
                        ) {
                            $intervalProgress.PhoneBytes
                        } else { 0 })
                        interval_word_bytes = $(if (
                            $null -ne $intervalProgress
                        ) {
                            $intervalProgress.WordBytes
                        } else { 0 })
                        interval_latest_write_utc = $(if (
                            $null -ne $intervalProgress
                        ) {
                            $intervalProgress.LatestWriteUtc
                        } else { $null })
                        work_drive_free_gb = $freeNowGB
                        watchdog_will_kill = $kill
                        stderr_tail = $tail
                    })
                    if ($kill) {
                    Say "!! $y MFA 교착 추정(단계=$phase, 카운터 ${frozenMin}분 정지, 마지막='$tail') — 강제종료 후 자동 재시도"
                    try { $p.Kill() } catch {}
                    $watchdogKilled = $true
                }
            }
            $p.WaitForExit()
            Write-JsonLine $heartbeatFile ([ordered]@{
                event = 'mfa_process_exited'
                recorded_at = (Get-Date).ToString('o')
                run_id = $runId
                year = $y
                pid = $p.Id
                exit_code = $p.ExitCode
                watchdog_killed = $watchdogKilled
                alignment_processed = $(if (
                    $null -ne $alignmentProgress
                ) {
                    $alignmentProgress.Processed
                } else { $null })
                alignment_retried = $(if (
                    $null -ne $alignmentProgress
                ) {
                    $alignmentProgress.Retried
                } else { $null })
                alignment_error_signals = $(if (
                    $null -ne $alignmentProgress
                ) {
                    $alignmentProgress.ErrorSignals
                } else { $null })
                interval_phone_rows = $(if (
                    $null -ne $intervalProgress
                ) {
                    $intervalProgress.PhoneRows
                } else { 0 })
                interval_word_rows = $(if (
                    $null -ne $intervalProgress
                ) {
                    $intervalProgress.WordRows
                } else { 0 })
                interval_word_utterances = $(if (
                    $null -ne $intervalProgress
                ) {
                    $intervalProgress.WordUtterances
                } else { 0 })
                memory_pressure_warning = $(if (
                    $null -ne $systemMemory
                ) {
                    $systemMemory.PressureWarning
                } else { $null })
            })
            # ★ 거짓 성공 방지 (2026-07-22): MFA는 export 단계에서 배치 전체가 실패해도
            # (output_errors.txt로만 기록) exit 0을 반환함 — 2021 실측(too many SQL
            # variables로 137만 건 전부 실패했는데 exit 0이라 "성공"으로 오판, temp
            # 삭제로 3.26h짜리 완주 정렬까지 날아감). exit 0이어도 실제 TextGrid가
            # 하나도 없으면 성공으로 인정하지 않음(temp 보존 → 재시도 시 이어가기 가능).
            if (-not $watchdogKilled -and $p.ExitCode -eq 0) {
                if ($UseDirectDbExport) {
                    $ok = $true
                    break
                }
                $anyTg = [IO.Directory]::EnumerateFiles((Join-Path $out $y), "*.TextGrid",
                         [IO.SearchOption]::AllDirectories) | Select-Object -First 1
                if ($anyTg) { $ok = $true; break }
                # ★ 거짓 성공 처리 수정 (2026-07-24): 종전엔 이 아래 공통 경로가 temp를 지우고
                #   --clean 재시도 — 로그 문구("temp 보존")와 달리 실제로는 보존되지 않았음.
                #   거짓 성공 = 정렬은 완주, export 단계 버그이므로 clean 재시도로는 안 고쳐지고
                #   수 시간 재계산만 낭비(2021 실측). temp 보존한 채 즉시 중단, 사람 확인.
                Say "!! $y MFA exit 0이나 TextGrid 출력 0건 — 거짓 성공(export 실패)으로 판단"
                Say "!! $y temp($tmpYear) 보존한 채 중단 — 원인: $errFile 확인. 조치 후 재실행하면 이어가기됨."
                exit 1
            } elseif ($watchdogKilled) {
                Say "!! $y MFA 교착으로 강제종료됨 — traceback 없음(정상, hang은 예외를 안 남김)"
            } else {
                Say "!! $y MFA 실패 (exit $($p.ExitCode)) — 원인 traceback: $errFile"
            }
            if (-not $doClean) {
                Say "$y 이어가기 실패 → temp 비우고 --clean 전체로 재시도"
                try { Remove-SafeYearPath $tmpYear $tmp }
                catch { Say "!! temp 안전 삭제 실패: $($_.Exception.Message)"; exit 1 }
            }
        }
        if (-not $ok) {
            # ★ 최종 실패에도 temp 보존 (2026-07-24, "무조건 이어가기"): 종전(7-21)엔 여기서
            #   temp를 지워 다음 실행이 코퍼스 로딩(최대 5.5h)부터 재시작했음. 보존해도
            #   다음 실행이 temp-우선 Get-WorkDrive로 같은 드라이브를 잡고, 이어가기 실패
            #   시 그때 비우고 --clean 폴백($tries 로직)하므로 어중간한 DB도 방어됨.
            #   7-21 삭제 도입 사유(찌꺼기→드라이브 선택 흔들림)는 7-22 temp-우선 규칙이
            #   이미 해소. 남는 건 실패 연도 1개분(15~35GB)뿐이고 preflight가 리포트함.
            Say "!! $y MFA 최종 실패(이어가기+clean 모두 실패) — temp($tmpYear) 보존한 채 중단, 사람 확인 필요"
            exit 1
        }
        if ($UseDirectDbExport) {
            # Built-in raw TextGrid 수백만 개를 쓴 뒤 다시 읽는 이중 I/O를 피한다.
            # align()은 word/phone interval을 이미 SQLite에 수집했다. 동일 writer로
            # 4-tier를 partial staging에 만들고, 전수 검증 뒤 연도 디렉터리 하나를
            # 원자적으로 최종 staging 위치로 이동한다.
            $dbPath = Join-Path $tmpYear "$y.db"
            if (-not (Test-Path -LiteralPath $dbPath)) {
                Say "!! $y direct-DB용 MFA DB 없음: $dbPath"
                exit 1
            }
            if (Test-Path -LiteralPath $finalStageYear) {
                Say "!! $y 최종 staging이 marker 없이 이미 존재 — 자동 덮어쓰기 금지: $finalStageYear"
                exit 1
            }
            New-Item -ItemType Directory -Force -Path $directPartialRoot |
                Out-Null
            $directReport = Join-Path $logDir (
                "direct_db_export_{0}_{1}.json" -f $y, $runId
            )
            Say "$y [3/3-direct] MFA DB -> partial 4-tier staging..."
            & $py (Join-Path $pydir "export_mfa_db_4tier.py") `
                --db $dbPath --year $y `
                --search-master-root $searchMasterRoot `
                --output-root $directPartialRoot --report $directReport
            if ($LASTEXITCODE -ne 0) {
                Say "!! $y direct-DB 4-tier 실패 — DB와 partial 보존: $directReport"
                exit 1
            }
            try {
                $directData = Get-Content -LiteralPath $directReport -Raw `
                    -Encoding UTF8 | ConvertFrom-Json
                if ($directData.status -ne 'success') {
                    throw "status=$($directData.status)"
                }
                $tgN = [int64]$directData.counts.created +
                       [int64]$directData.counts.validated_existing
                $labN = ([IO.Directory]::EnumerateFiles(
                    (Join-Path $wavRoot $y), "*.lab",
                    [IO.SearchOption]::AllDirectories
                ) | Measure-Object).Count
                $pct = if ($labN -gt 0) {
                    [math]::Round(100 * $tgN / $labN, 2)
                } else { 0 }
                if ($labN -le 0 -or $tgN -le 0 -or $pct -lt 99) {
                    throw "coverage gate 실패: TextGrid=$tgN lab=$labN pct=$pct"
                }
                if (-not (Test-Path -LiteralPath $directPartialYear)) {
                    throw "partial 연도 디렉터리 없음: $directPartialYear"
                }
                Move-Item -LiteralPath $directPartialYear `
                    -Destination $finalStageYear
            } catch {
                Say "!! $y direct-DB 최종 gate/승격 실패 — DB·partial 보존: $($_.Exception.Message)"
                exit 1
            }
            Write-DoneMarker $doneMark $y 'align' @{
                textgrids = $tgN
                labs = $labN
                coverage_pct = $pct
                export_mode = 'direct_db_4tier'
                alignment_db = $dbPath
                input_contract_id = $inputContractId
                search_master_root = $searchMasterRoot
                input_integrity_report = $inputIntegrityReport
                input_integrity_gate_profile = $integrityGateProfile
                input_integrity_execution_gates_pass = $true
                input_integrity_analysis_ready_gates_pass = (
                    [bool]$integrityYear[0].analysis_ready_gates_pass
                )
                morph_source_missing = (
                    [int64]$integrityYear[0].counts.morph_source_missing
                )
                morph_source_unclassified = (
                    [int64]$integrityYear[0].counts.morph_source_unclassified
                )
            } $inputContractId $alignmentContract
            $mergeMark = Join-Path $doneDir "$y.merge_done"
            Write-DoneMarker $mergeMark $y 'merge' @{
                export_mode = 'direct_db_4tier'
                direct_export_report = $directReport
                staging_output_root = $g2pStage
                existing_final_root = (Expand-CfgPath $cfg.textgrid_eojeol)
                promotion_required = $true
                raw_mfa_textgrid_duplicated = $false
                alignment_db_retained = (-not [bool]$CleanupDirectDbAfterMerge)
                input_contract_id = $inputContractId
                search_master_root = $searchMasterRoot
                input_integrity_report = $inputIntegrityReport
                input_integrity_gate_profile = $integrityGateProfile
                input_integrity_execution_gates_pass = $true
                input_integrity_analysis_ready_gates_pass = (
                    [bool]$integrityYear[0].analysis_ready_gates_pass
                )
                morph_source_missing = (
                    [int64]$integrityYear[0].counts.morph_source_missing
                )
                morph_source_unclassified = (
                    [int64]$integrityYear[0].counts.morph_source_unclassified
                )
            } $inputContractId $alignmentContract
            if ($CleanupDirectDbAfterMerge) {
                try { Remove-SafeYearPath $tmpYear $tmp }
                catch {
                    Say "!! direct-DB 완료 후 temp 정리 실패(4-tier·marker 보존): $($_.Exception.Message)"
                }
                Write-TempContract $tempContractPath $y $inputContractId `
                    $alignmentContract $tmpYear `
                    "direct_merge_completed_temp_removed"
                Say "===== $y direct-DB 완료 (temp 정리, 4-tier $tgN/$labN) ====="
            } else {
                Write-TempContract $tempContractPath $y $inputContractId `
                    $alignmentContract $tmpYear `
                    "direct_merge_completed_temp_retained_for_qc"
                Say "===== $y direct-DB 완료 (QC 전 DB 보존: $dbPath, 4-tier $tgN/$labN) ====="
            }
            continue
        }
        # ★ 정렬 산출 수량 검증: 기존 2020·2021 실측 성공률은 99.9%대다.
        #   99% 미만은 통상적 난정렬 범위를 넘어 부분 export·stale 출력 가능성이
        #   크므로 완료 마커를 만들지 않는다.
        try {
            $tgN  = ([IO.Directory]::EnumerateFiles((Join-Path $out $y), "*.TextGrid",
                     [IO.SearchOption]::AllDirectories) | Measure-Object).Count
            $labN = ([IO.Directory]::EnumerateFiles((Join-Path $wavRoot $y), "*.lab",
                     [IO.SearchOption]::AllDirectories) | Measure-Object).Count
            $pct = if ($labN -gt 0) { [math]::Round(100 * $tgN / $labN, 2) } else { 0 }
            Say "$y 정렬 산출 관측: TextGrid $tgN / lab $labN ($pct%)"
            if ($labN -le 0) {
                Say "!! $y lab 0건 — 완료 마커 생성 금지"
                exit 1
            }
            if ($pct -lt 99) {
                Say "!! $y 산출 비율 $pct% < 99% — 부분 누락 가능, 완료 마커 생성 금지"
                exit 1
            }
        } catch {
            Say "!! $y 산출 수량 검증 실패 — 완료 마커 생성 금지: $($_.Exception.Message)"
            exit 1
        }
        Write-DoneMarker $doneMark $y 'align' @{
            textgrids = $tgN
            labs = $labN
            coverage_pct = $pct
            output_root = $out
            input_contract_id = $inputContractId
            search_master_root = $searchMasterRoot
            input_integrity_report = $inputIntegrityReport
            input_integrity_execution_gates_pass = $true
            morph_source_missing = (
                [int64]$integrityYear[0].counts.morph_source_missing
            )
            morph_source_unclassified = (
                [int64]$integrityYear[0].counts.morph_source_unclassified
            )
        } $inputContractId $alignmentContract
        Write-TempContract $tempContractPath $y $inputContractId `
            $alignmentContract $tmpYear `
            "align_completed_temp_retained_until_merge"
        Say "$y MFA 정렬 완료 (병합·QC 전까지 temp $tmpYear 보존)"
    }

    # 3) 4-tier 병합 — 진행줄 실시간. MFA 원출력은 선택된 작업 드라이브에 있음.
    #    완료 마커가 있으면 건너뜀(완료 연도는 해당 원출력이 이미 삭제돼 있음).
    $mergeMark = Join-Path $doneDir "$y.merge_done"
    if (Read-DoneMarker $mergeMark $y 'merge' $inputContractId `
            $alignmentContractId) {
        Say "$y [3/3] 병합 이미 완료 — 건너뜀"; Say "===== $y 완료 ====="; continue
    }
    if ((Test-Path -LiteralPath $mergeMark) -and
        -not (Read-DoneMarker $mergeMark $y 'merge' $inputContractId `
            $alignmentContractId)) {
        Say "!! $y merge_done이 현재 입력계약과 불일치 — 자동 재사용 금지: $mergeMark"
        exit 1
    }
    # ★ 병합 원출력 드라이브 폴백 (2026-07-24): align 완료 후에는 temp가 지워져 있어,
    #   그 상태에서 재시작하면 Get-WorkDrive가 여유공간 기준으로 새로 정한 드라이브가
    #   MFA 원출력(mfa_eojeol_out)이 실제로 있는 드라이브와 어긋날 수 있음(병합만 남은
    #   재개 시나리오). $out\<연도>가 없으면 반대 드라이브를 확인해 자동 전환.
    if (-not (Test-Path (Join-Path $out $y))) {
        $altOut = if ($out -eq $outPrimary) { $outSecondary } else { $outPrimary }
        if (Test-Path (Join-Path $altOut $y)) {
            Say "$y 병합 원출력을 $altOut 에서 발견 — 드라이브 자동 전환(원래 추정: $out)"
            $out = $altOut
            $outYear = Join-Path $out $y
        }
    }
    Say "$y [3/3] 4-tier 병합 -> G2P staging (아래 진행줄 실시간)..."
    & $py (Join-Path $pydir "realign_eojeol_merge_output.py") `
        --year $y --mfa-out $out --output-root $g2pStage --run-id $runId
    if ($LASTEXITCODE -ne 0) { Say "!! $y 병합 실패 (exit $LASTEXITCODE) — 중단"; exit 1 }

    # 4) 검증 성공 마커를 먼저 기록한 뒤 MFA 원출력을 정리한다.
    Write-DoneMarker $mergeMark $y 'merge' @{
        mfa_output_root = $out
        mfa_output_retained = (-not [bool]$CleanupMfaOutput)
        staging_output_root = $g2pStage
        existing_final_root = (Expand-CfgPath $cfg.textgrid_eojeol)
        promotion_required = $true
        input_contract_id = $inputContractId
        search_master_root = $searchMasterRoot
        input_integrity_report = $inputIntegrityReport
        input_integrity_execution_gates_pass = $true
        morph_source_missing = (
            [int64]$integrityYear[0].counts.morph_source_missing
        )
        morph_source_unclassified = (
            [int64]$integrityYear[0].counts.morph_source_unclassified
        )
    } $inputContractId $alignmentContract
    # temp DB는 raw MFA 출력과 4-tier 병합이 모두 검증된 뒤에만 정리한다.
    # 병합 실패 시 위에서 exit 1이므로 이 지점에 오지 않고 temp가 보존된다.
    try { Remove-SafeYearPath $tmpYear $tmp }
    catch { Say "!! 병합 후 temp 안전 삭제 실패(산출·마커는 보존): $($_.Exception.Message)" }
    Write-TempContract $tempContractPath $y $inputContractId `
        $alignmentContract $tmpYear "merge_completed_temp_removed"
    if ($CleanupMfaOutput) {
        try { Remove-SafeYearPath $outYear $out }
        catch { Say "!! 병합 후 MFA 원출력 정리 실패(마커·4-tier는 보존): $($_.Exception.Message)" }
        Say "===== $y 완료 (요청에 따라 raw MFA 원출력 정리됨) ====="
    } else {
        Say "===== $y 완료 (raw MFA 원출력 보존: $outYear) ====="
    }
}
Say "선택 연도 정렬·병합 완료 - $g2pStage"
Say "기존 06_textgrid_eojeol은 보존됨. 전수 검증과 archive 계획 확인 전 자동 승격하지 않음."
exit 0
