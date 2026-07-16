"""사회변수 통합 화자표: 연도별 _speakers.csv -> speakers_normalized.csv.

비파괴적 정규화(원본 컬럼 보존 + *_norm 파생). 규칙은 docs/decisions/사회변수_코드북.md.
정규화 = "같은 개념을 같은 라벨로"만. 재코딩(계층/방언권)·시도 묶기는 하지 않음.
  - 지역 3필드: NA/빈칸 -> 미상 (라벨 vocabulary는 이미 3필드 동일, 17시도 유지)
  - 직업: '기술자 종자사(...)'(2021 오타) -> '기술자 종사자(...)'. 무직·군인 등은 그대로(원 분류 보존)
  - 학력: NA/빈칸 -> 미상 (순서 정보는 별도 education_ord)
  - 연령: 60대(2020) -> 60대 이상 (연도 정합)

출력: D:/10_LAYERS/04_metadata_index/speakers_normalized.csv
실행: python build_speakers_normalized.py
"""
import csv
import os
import sys
from pathlib import Path

BASE = Path(r"D:\10_LAYERS\01_bareun_raw")
OUT = Path(r"D:\10_LAYERS\04_metadata_index\speakers_normalized.csv")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MISSING = ("", "NA")
OCC_TYPO = {
    "기술자 종자사(장치/기계 조작 및 조립 종사자)":
        "기술자 종사자(장치/기계 조작 및 조립 종사자)",
}
EDU_ORD = {"초졸 이하": 1, "중졸": 2, "고졸": 3, "대재": 4,
           "대졸": 5, "대학원 이상": 6}


def miss(v):
    v = (v or "").strip()
    return "미상" if v in MISSING else v


def norm_occupation(v):
    v = (v or "").strip()
    if v in MISSING:
        return "미상"
    return OCC_TYPO.get(v, v)      # 오타만 교정, 나머지는 원 분류 보존


def norm_age(v):
    v = (v or "").strip()
    if v in MISSING:
        return "미상"
    return "60대 이상" if v == "60대" else v


def main() -> int:
    rows = []
    for yd in sorted(BASE.iterdir()):
        fp = yd / "_speakers.csv"
        if not fp.exists():
            continue
        year = "".join(c for c in yd.name if c.isdigit())[:4]
        with open(fp, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                edu = (r.get("education") or "").strip()
                rows.append({
                    "year": year,
                    "id": r.get("id", ""),
                    # 원본 보존
                    "sex": r.get("sex", ""), "age": r.get("age", ""),
                    "occupation": r.get("occupation", ""),
                    "education": r.get("education", ""),
                    "birthplace": r.get("birthplace", ""),
                    "principal_residence": r.get("principal_residence", ""),
                    "current_residence": r.get("current_residence", ""),
                    # 정규화 파생
                    "sex_norm": miss(r.get("sex")),
                    "age_norm": norm_age(r.get("age")),
                    "occupation_norm": norm_occupation(r.get("occupation")),
                    "education_norm": miss(r.get("education")),
                    "education_ord": EDU_ORD.get(edu, ""),
                    "birthplace_norm": miss(r.get("birthplace")),
                    "principal_residence_norm": miss(r.get("principal_residence")),
                    "current_residence_norm": miss(r.get("current_residence")),
                })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = ["year", "id", "sex", "age", "occupation", "education",
              "birthplace", "principal_residence", "current_residence",
              "sex_norm", "age_norm", "occupation_norm", "education_norm",
              "education_ord", "birthplace_norm", "principal_residence_norm",
              "current_residence_norm"]
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # 요약: 정규화로 바뀐 건수
    n_age = sum(1 for r in rows if r["age"].strip() == "60대")
    n_occ = sum(1 for r in rows
                if r["occupation"].strip() in OCC_TYPO)
    n_edu = sum(1 for r in rows if (r["education"] or "").strip() in MISSING)
    n_loc = sum(1 for r in rows for c in
                ("birthplace", "principal_residence", "current_residence")
                if (r[c] or "").strip() in MISSING)
    print(f"완료: 화자행 {len(rows):,} -> {OUT}")
    print(f"정규화 반영: age 60대->60대이상 {n_age} / 직업오타 교정 {n_occ} / "
          f"학력결측->미상 {n_edu} / 지역결측->미상 {n_loc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
