"""연구용 TextGrid 발화 검색 label의 단일 생성·파싱 계약."""

from __future__ import annotations

import re
from collections import OrderedDict
from typing import Mapping

from morph_schema import canonicalize_tagged, tagged_roman_v2

SEARCH_LABEL_SCHEMA_VERSION = "utterance_search.v1"
TARGET_TIERS = [
    "words",
    "phones_mfa",
    "utterance",
    "utterance_search",
]
FIELD_ORDER = ("UTT", "ORTH_R", "MORPH", "MORPH_R", "NOTE")
MARKER_RE = re.compile(r"(?<!\\)\[([A-Z_]+)\] ")


class SearchLabelError(ValueError):
    pass


def escape_field_value(value: object) -> str:
    """한 줄 label에서 field marker와 제어문자를 무손실 escape한다."""

    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def unescape_field_value(value: str) -> str:
    out: list[str] = []
    index = 0
    escapes = {
        "\\": "\\",
        "[": "[",
        "]": "]",
        "r": "\r",
        "n": "\n",
        "t": "\t",
    }
    while index < len(value):
        if value[index] != "\\":
            out.append(value[index])
            index += 1
            continue
        if index + 1 >= len(value):
            raise SearchLabelError("field value 끝의 단독 backslash")
        code = value[index + 1]
        if code not in escapes:
            raise SearchLabelError(f"알 수 없는 escape: \\{code}")
        out.append(escapes[code])
        index += 2
    return "".join(out)


def build_search_fields(row: Mapping[str, object]) -> OrderedDict[str, str]:
    required = ("utt_id", "form_roman", "tagged")
    missing = [field for field in required if not str(row.get(field, "")).strip()]
    if missing:
        raise SearchLabelError(f"검색 label 필수값 누락: {missing}")
    fields: OrderedDict[str, str] = OrderedDict(
        (
            ("UTT", str(row["utt_id"]).strip()),
            ("ORTH_R", str(row["form_roman"]).strip()),
            ("MORPH", canonicalize_tagged(str(row["tagged"]))),
            ("MORPH_R", tagged_roman_v2(str(row["tagged"]))),
        )
    )
    notes: list[str] = []
    align_warn = str(row.get("align_warn", "") or "").strip()
    if align_warn:
        notes.append(f"align_warn={align_warn}")
    if notes:
        fields["NOTE"] = "; ".join(notes)
    return fields


def utterance_search_label(row: Mapping[str, object]) -> str:
    fields = build_search_fields(row)
    label = " ".join(
        f"[{name}] {escape_field_value(value)}"
        for name, value in fields.items()
    )
    reparsed = parse_search_label(label)
    if reparsed != fields:
        raise SearchLabelError(
            f"검색 label 왕복 실패: expected={fields!r} actual={reparsed!r}"
        )
    return label


def parse_search_label(label: str) -> OrderedDict[str, str]:
    matches = list(MARKER_RE.finditer(label))
    if not matches or matches[0].start() != 0:
        raise SearchLabelError("검색 label이 field marker로 시작하지 않음")
    fields: OrderedDict[str, str] = OrderedDict()
    for index, match in enumerate(matches):
        name = match.group(1)
        if name in fields:
            raise SearchLabelError(f"중복 field marker: {name}")
        if name not in FIELD_ORDER:
            raise SearchLabelError(f"허용하지 않은 field marker: {name}")
        end = matches[index + 1].start() - 1 if index + 1 < len(matches) else len(label)
        raw_value = label[match.end():end]
        fields[name] = unescape_field_value(raw_value)
    expected = [name for name in FIELD_ORDER if name in fields]
    if list(fields) != expected:
        raise SearchLabelError(
            f"field 순서 불일치: expected={expected} actual={list(fields)}"
        )
    required = {"UTT", "ORTH_R", "MORPH", "MORPH_R"}
    missing = required - set(fields)
    if missing:
        raise SearchLabelError(f"필수 field marker 누락: {sorted(missing)}")
    return fields
