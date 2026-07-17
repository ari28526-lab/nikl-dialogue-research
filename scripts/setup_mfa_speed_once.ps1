# MFA 배치 가속 1회 설정 (2026-07-17) — ★관리자 PowerShell에서 실행★
#   (시작 → "PowerShell" 우클릭 → 관리자 권한으로 실행 → 이 파일 실행)
# 1) Windows Defender 실시간 검사 제외: 수백만 개 소형 파일(.wav/.lab/TextGrid)마다
#    검사가 걸리면 USB I/O가 배로 느려짐. 데이터·temp·MFA env만 제외 (시스템 전체 아님).
# 2) 절전 해제: 밤샘 배치 중 대기모드·디스크 꺼짐 방지.
# 실행: powershell -ExecutionPolicy Bypass -File scripts\setup_mfa_speed_once.ps1

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Host "!! 관리자 PowerShell에서 실행하세요." -ForegroundColor Red; return }

# 1) Defender 제외 (데이터 경로 + MFA temp + miniforge)
$paths = @(
    "D:\20_AUDIO",
    "D:\10_LAYERS",
    "D:\mfa_eojeol",
    "C:\mfa_tmp",
    "C:\mfa_eojeol_out",
    "C:\Users\ari30\miniforge3"
)
foreach ($p in $paths) {
    Add-MpPreference -ExclusionPath $p
    Write-Host "Defender 제외 추가: $p"
}
Write-Host "`n현재 제외 목록:" -ForegroundColor Cyan
(Get-MpPreference).ExclusionPath

# 2) 절전 해제 (AC 전원 기준: 대기·최대절전·디스크 끄기 안 함)
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change disk-timeout-ac 0
Write-Host "`n절전 해제 완료 (standby/hibernate/disk = 사용 안 함, AC 기준)" -ForegroundColor Cyan
Write-Host "추가 권장: 설정 > 시스템 > 전원 > 전원 모드 = '최고의 성능'으로 (수동)."
Write-Host "배치 끝난 뒤 되돌리려면: powercfg /change standby-timeout-ac 30 등으로 복원."
