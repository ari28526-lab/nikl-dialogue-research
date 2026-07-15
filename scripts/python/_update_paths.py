# -*- coding: utf-8 -*-
"""이행에 따른 경로 일괄 치환 (1회용). finish_migration.py는 제외."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SCRIPTS = Path(__file__).parent
REPL = [
    (r"D:\00_NIKL_DIALOGUE_2020-2025_json", r"D:\00_RAW\dialogue_json"),
    (r"D:\05_NIKL_DIALOGUE_bareun_2020-2025", r"D:\10_LAYERS"),
    (r"D:\DATA_2026", r"D:\00_RAW\reference"),
    (r"D:\04_00_NIKL_DIALOGUE_MFA\00_source", r"D:\00_RAW\dialogue_audio"),
    (r"D:\04_00_NIKL_DIALOGUE_MFA\06_textgrid_merged",
     r"D:\20_AUDIO\06_textgrid_merged"),
    (r"D:\04_00_NIKL_DIALOGUE_MFA\03_wav", r"D:\20_AUDIO\03_wav"),
    # 슬래시 표기 (paths.json)
    ("D:/00_NIKL_DIALOGUE_2020-2025_json", "D:/00_RAW/dialogue_json"),
    ("D:/05_NIKL_DIALOGUE_bareun_2020-2025", "D:/10_LAYERS"),
    ("D:/DATA_2026", "D:/00_RAW/reference"),
    ("D:/04_00_NIKL_DIALOGUE_MFA/03_wav", "D:/20_AUDIO/03_wav"),
    ("D:/04_00_NIKL_DIALOGUE_MFA/06_textgrid_merged",
     "D:/20_AUDIO/06_textgrid_merged"),
    ("D:/04_00_NIKL_DIALOGUE_MFA", "D:/20_AUDIO"),
]
targets = [p for p in SCRIPTS.glob("*.py")
           if p.name not in ("finish_migration.py", "_update_paths.py")]
targets.append(SCRIPTS.parent.parent / "config" / "paths.json")
for fp in targets:
    if not fp.exists():
        continue
    text = orig = fp.read_text(encoding="utf-8")
    for old, new in REPL:
        text = text.replace(old, new)
    if text != orig:
        fp.write_text(text, encoding="utf-8")
        print(f"갱신: {fp.name}")
print("완료")
