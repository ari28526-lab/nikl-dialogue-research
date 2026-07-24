"""경로 단일 관리 로더. 사용: from paths import P; P("layers") -> Path

폴더를 옮기거나 다른 기계에서 작업할 때 config/paths.json만 수정하면
모든 스크립트가 따라온다. 신규 스크립트는 반드시 이걸 쓸 것.
"""
import json
import os
from pathlib import Path

_CONFIG = Path(__file__).resolve().parents[2] / "config" / "paths.json"
_cache = None


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(_CONFIG.read_text(encoding="utf-8"))
    return _cache


def P(key: str) -> Path:
    d = _load()
    if key not in d or key.startswith("_"):
        raise KeyError(f"paths.json에 '{key}' 없음. 사용 가능: "
                       + ", ".join(k for k in d if not k.startswith("_")))
    value = os.path.expandvars(os.path.expanduser(str(d[key])))
    return Path(value)


def config_path() -> Path:
    """실제로 읽은 설정 파일 경로."""
    return _CONFIG


def path_values() -> dict[str, Path]:
    """주석 키를 제외하고 환경변수를 확장한 전체 경로."""
    return {key: P(key) for key in _load() if not key.startswith("_")}
