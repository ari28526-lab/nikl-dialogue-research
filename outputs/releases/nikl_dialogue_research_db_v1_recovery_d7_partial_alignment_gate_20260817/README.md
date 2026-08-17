# DB v1 recovery D7 partial-alignment preservation gate

연구자가 검토한 D5 진단 TextGrid 11건을 본체 정렬 성공에서는 제외하고, 원인과 향후 사용 가능성을 exact-ID로 보존한다. 6건은 `partial_alignment_available`, 3건은 `noise_hold`, 2건은 전사 회수·수정 후보다. WAV·LAB·TextGrid는 D6 검토 root에 그대로 있으며 삭제하거나 r3 본체·6-tier·DB v1에 병합하지 않았다.

Dropbox CSV는 `RESEARCHER_REVIEW_SOURCE.csv`에 바이트 그대로 보존했고, 권위 구조화 결정은 JSON과 별도 SQLite다.
