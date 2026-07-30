import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import build_common_pron_researcher_approval as approval  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


class ResearcherApprovalTests(unittest.TestCase):
    def fixture(self, root: Path) -> dict[str, Path]:
        filled = root / "filled.xlsx"
        filled.write_bytes(b"filled")
        correction = root / "correction.csv"
        correction.write_text("token\nfixture\n", encoding="utf-8")
        jamo = root / "jamo.csv"
        rows = []
        phones = []
        for index, word in enumerate(
            sorted(approval.REQUIRED_JAMO_LS_WORDS), 1
        ):
            phone = f"k p{index}"
            phones.extend(phone.split())
            rows.append(
                {
                    "token": word,
                    "model_input": word,
                    "pron_phones_mfa": "k",
                    "approved_pron_phones_mfa": phone,
                    "decision": "approved",
                    "evidence_source": "fixture",
                    "notes": "explicit approval",
                }
            )
        with jamo.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=approval.JAMO_FIELDS,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)

        common = root / "common.json"
        common.write_text(
            json.dumps(
                {
                    "schema_version": approval.LEXICON_SCHEMA_VERSION,
                    "status": "success",
                    "release_id": "common_pron_mfa_r2_fixture",
                    "dictionary_contract": {
                        "jamo_ls_researcher_review": file_fingerprint(
                            jamo, with_sha256=True
                        )
                    },
                }
            ),
            encoding="utf-8",
        )
        difference = root / "difference.json"
        difference.write_text(
            json.dumps(
                {
                    "schema_version": approval.DIFFERENCE_SCHEMA_VERSION,
                    "status": "differences_inventoried",
                    "gate": {
                        "difference_inventory_complete": True,
                        "allow_yearly_mfa": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        application = root / "application.json"
        application.write_text(
            json.dumps(
                {
                    "schema_version": (
                        approval.APPLICATION_SCHEMA_VERSION
                    ),
                    "status": "applied",
                    "gates": approval.REQUIRED_APPLICATION_GATES,
                    "phone_inventory_contract": {
                        "phones": sorted(set(phones))
                    },
                    "outputs": {
                        "correction_registry": file_fingerprint(
                            correction, with_sha256=True
                        )
                    },
                    "archives": {
                        "decision_evidence": {
                            "filled_workbook": file_fingerprint(
                                filled, with_sha256=True
                            )
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        decision = root / "decision.md"
        decision.write_text(
            "상태: 확정\n"
            "2020–2025 여섯 연도 전부 다시 정렬\n"
            "difference inventory는 구결과 재사용 여부를 결정하는 "
            "검사가 아니다.\n",
            encoding="utf-8",
        )
        return {
            "common": common,
            "difference": difference,
            "application": application,
            "decision": decision,
            "jamo": jamo,
        }

    def build(self, paths: dict[str, Path]) -> dict:
        return approval.build_researcher_approval(
            common_manifest_path=paths["common"],
            difference_inventory_path=paths["difference"],
            decision_application_path=paths["application"],
            decision_record_path=paths["decision"],
        )

    def test_builds_from_prior_explicit_decision_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.build(self.fixture(Path(temp)))
        self.assertTrue(result["approved"])
        self.assertTrue(result["scope"]["realign_all_six_years"])
        self.assertEqual(
            set(result["jamo_ls"]["reviewed_words"]),
            approval.REQUIRED_JAMO_LS_WORDS,
        )

    def test_pending_jamo_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            text = paths["jamo"].read_text(encoding="utf-8-sig")
            paths["jamo"].write_text(
                text.replace(",approved,fixture", ",pending,fixture", 1),
                encoding="utf-8-sig",
            )
            common = json.loads(
                paths["common"].read_text(encoding="utf-8")
            )
            common["dictionary_contract"][
                "jamo_ls_researcher_review"
            ] = file_fingerprint(paths["jamo"], with_sha256=True)
            paths["common"].write_text(
                json.dumps(common), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                RuntimeError, "approval rows invalid"
            ):
                self.build(paths)


if __name__ == "__main__":
    unittest.main()
