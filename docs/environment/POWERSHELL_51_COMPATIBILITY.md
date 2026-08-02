# Windows PowerShell 5.1 호환성 규칙

결정일: 2026-08-02 KST

## 재발 원인

장시간 archive 스크립트의 첫 실행은 BOM 없는 UTF-8 한글을 Windows PowerShell
5.1이 잘못 해석해 파싱 전에 실패했다. 재개 실행은 `ConvertFrom-Json`의 단일
`PSCustomObject`를 배열로 가정하고 `+=`를 사용해 실패했다. 기존 안전검사는
경로·삭제·필수 token 중심의 정적 검사여서 실제 PS5 런타임 동작을 잡지 못했다.

## 강제 규칙

1. 모든 `.ps1`은 UTF-8 BOM과 CRLF로 저장한다. `.editorconfig`가 이를 선언한다.
2. JSON·pipeline 결과의 0/1/N개 값은 scalar로 풀릴 수 있다고 가정한다.
   누적에는 `+=` 대신 `List[object]`와 `foreach (@(...))`를 사용한다.
3. 장시간·대용량·파괴 가능 실행기는 실제 Windows PowerShell 5.1에서
   `-PreflightOnly`를 통과한 뒤에만 사용자 명령으로 제공한다.
4. `tests/test_powershell_safety.ps1`과
   `tests/test_powershell_runtime_compat.ps1`을 모두 PS5로 실행한다.
5. AST parse 성공만으로 실행 호환성을 선언하지 않는다. resume용 기존 manifest의
   단일/복수/실패 이력 형태를 런타임 시험한다.

## 표준 확인 명령

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File ".\tests\test_powershell_safety.ps1"

& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File ".\tests\test_powershell_runtime_compat.ps1"
```

archive처럼 외장 드라이브를 쓰는 스크립트는 이어서 같은 PS5 실행기로
`-PreflightOnly`를 호출한다. preflight는 archive 생성·prune을 수행하지 않는다.
