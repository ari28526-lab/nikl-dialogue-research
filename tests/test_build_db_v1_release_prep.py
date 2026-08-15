from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))
MODULE_PATH = ROOT / "scripts" / "python" / "build_db_v1_release_prep.py"
SPEC = importlib.util.spec_from_file_location("build_db_v1_release_prep", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_gz(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fixture_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    base_fields = ["year", "utt_id", "session_id", "source_csv"]
    safe = tmp_path / "safe.csv.gz"
    expected = tmp_path / "expected.csv.gz"
    followup = tmp_path / "followup.csv.gz"
    rows = [
        {"year": "2020", "utt_id": "u1", "session_id": "s1", "source_csv": "a.csv"},
        {"year": "2020", "utt_id": "u2", "session_id": "s1", "source_csv": "a.csv"},
        {"year": "2020", "utt_id": "u3", "session_id": "s2", "source_csv": "b.csv"},
    ]
    write_gz(safe, base_fields, rows)
    write_gz(expected, base_fields, [rows[0], rows[2]])
    follow_fields = base_fields + ["routing_class", "hold_tokens_json", "policy_tokens_json", "unknown_tokens_json"]
    write_gz(
        followup,
        follow_fields,
        [
            {
                **{"year": "2020", "utt_id": "u4", "session_id": "s2", "source_csv": "b.csv"},
                "routing_class": "hold",
                "hold_tokens_json": json.dumps(["x"]),
                "policy_tokens_json": "[]",
                "unknown_tokens_json": "[]",
            }
        ],
    )
    return safe, expected, followup


class DbV1ReleasePrepTests(unittest.TestCase):
    def test_export_discovery_uses_qc_bound_sha_not_first_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reports = root / "outputs" / "reports"
            reports.mkdir(parents=True)
            failed = reports / "EXPORT_mfa_r3_research_6tier_2024_first.json"
            recovered = reports / "EXPORT_RECOVERED_mfa_r3_research_6tier_2024_final.json"
            failed.write_text('{"status":"failed"}', encoding="utf-8")
            recovered.write_text('{"status":"success"}', encoding="utf-8")
            selected = MODULE.discover_export_report(root, "2024", MODULE.sha256(recovered))
            self.assertEqual(selected, recovered)

    def test_year_ledger_is_exhaustive_and_disjoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            safe, expected, followup = fixture_files(Path(temp))
            counters: Counter[str] = Counter()
            rows = list(
                MODULE.year_ledger_rows(
                    year="2020",
                    safe_path=safe,
                    followup_path=followup,
                    expected_path=expected,
                    pre_reasons={"u2": ["audio_pairing_unresolved"]},
                    post_reasons={"u3": ["mfa_alignment_missing"]},
                    year_input_contract_id="input",
                    alignment_contract_id="alignment",
                    counters=counters,
                )
            )
            self.assertEqual(
                [row["primary_status"] for row in rows],
                [
                    "aligned_safe_body",
                    "pre_mfa_technical_exclusion",
                    "post_mfa_technical_exclusion",
                    "pronunciation_followup",
                ],
            )
            self.assertEqual(counters["source_total"], 4)
            self.assertEqual(len({row["utt_id"] for row in rows}), 4)
            self.assertEqual(rows[0]["textgrid_available"], "true")
            self.assertEqual(rows[1]["followup_required"], "true")

    def test_year_ledger_rejects_safe_followup_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            safe, expected, followup = fixture_files(Path(temp))
            follow_fields = ["year", "utt_id", "session_id", "source_csv", "routing_class", "hold_tokens_json", "policy_tokens_json", "unknown_tokens_json"]
            write_gz(
                followup,
                follow_fields,
                [{"year": "2020", "utt_id": "u1", "session_id": "s1", "source_csv": "a.csv", "routing_class": "hold", "hold_tokens_json": "[]", "policy_tokens_json": "[]", "unknown_tokens_json": "[]"}],
            )
            rows = MODULE.year_ledger_rows(
                year="2020",
                safe_path=safe,
                followup_path=followup,
                expected_path=expected,
                pre_reasons={"u2": ["audio_pairing_unresolved"]},
                post_reasons={"u3": ["mfa_alignment_missing"]},
                year_input_contract_id="input",
                alignment_contract_id="alignment",
                counters=Counter(),
            )
            with self.assertRaisesRegex(RuntimeError, "overlap"):
                list(rows)


if __name__ == "__main__":
    unittest.main()
