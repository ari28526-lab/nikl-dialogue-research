import json
import sys
import tempfile
import unittest
from pathlib import Path


PYTHON_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(PYTHON_SCRIPTS))

from apply_mfa_r3_temp_cleanup import (  # noqa: E402
    apply_plan,
    build_plan,
    validate_approval_scope,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ApplyMfaR3TempCleanupTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        release = root / "release_test"
        temp_year = release / "temp" / "2020"
        temp_year.mkdir(parents=True)
        database = temp_year / "2020.db"
        database.write_bytes(b"database")
        candidate = temp_year / "2020" / "feats.ark"
        candidate.parent.mkdir()
        candidate.write_bytes(b"temporary-features")

        def record(path: Path, classification: str) -> dict:
            stat = path.stat()
            return {
                "relative_path": path.relative_to(temp_year).as_posix(),
                "path": str(path.resolve()),
                "bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "classification": classification,
                "reason": "test",
            }

        inventory_path = root / "inventory.json"
        write_json(
            inventory_path,
            {
                "schema_version": 1,
                "kind": "mfa_storage_inventory_and_cleanup_dry_run",
                "year": "2020",
                "status": "ready_for_user_review",
                "temp_year": str(temp_year.resolve()),
                "blockers": [],
                "unsafe_links": [],
                "active_transaction_files": [],
                "unclassified_files": [],
                "files": [
                    record(database, "retain_critical"),
                    record(candidate, "cleanup_candidate_after_qc"),
                ],
            },
        )
        summary_path = root / "summary.json"
        write_json(
            summary_path,
            {
                "schema_version": "mfa_r3_storage_cleanup_review.v1",
                "status": "ready_for_researcher_review",
                "release_id": release.name,
                "scope": {"years": ["2020"], "temp_only": True},
                "reports": [
                    {
                        "year": "2020",
                        "candidate_files": 1,
                        "candidate_bytes": candidate.stat().st_size,
                        "report_path": str(inventory_path.resolve()),
                    }
                ],
                "safety": {
                    "deletion_performed": False,
                    "move_performed": False,
                    "archive_performed": False,
                    "apply_supported": False,
                    "authorization_required_for_cleanup": True,
                    "databases_retained": True,
                    "final_6tier_retained": True,
                    "source_corpus_modified": False,
                },
            },
        )
        return summary_path, release, database, candidate

    def test_apply_deletes_only_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary, release, database, candidate = self.fixture(root)
            plan = build_plan(
                summary_path=summary,
                release_root=release,
                years=["2020"],
                expected_files=1,
                expected_bytes=candidate.stat().st_size,
            )
            self.assertEqual(plan["status"], "dry_run_passed")
            result = apply_plan(plan, root / "apply.json")
            self.assertEqual(result["status"], "passed")
            self.assertFalse(candidate.exists())
            self.assertTrue(database.is_file())

    def test_changed_candidate_blocks_apply_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary, release, _, candidate = self.fixture(root)
            expected_bytes = candidate.stat().st_size
            candidate.write_bytes(b"changed")
            plan = build_plan(
                summary_path=summary,
                release_root=release,
                years=["2020"],
                expected_files=1,
                expected_bytes=expected_bytes,
            )
            self.assertEqual(plan["status"], "blocked")
            self.assertTrue(
                any("file_changed_or_missing" in blocker for blocker in plan["blockers"])
            )

    def test_approval_token_is_bound_to_exact_scope(self) -> None:
        validate_approval_scope(
            approval_token="R3_TEMP_CLEANUP_2024_2025_ARI30_20260815",
            years=["2024", "2025"],
            expected_files=126,
            expected_bytes=38_640_655_415,
        )
        with self.assertRaises(RuntimeError):
            validate_approval_scope(
                approval_token="R3_TEMP_CLEANUP_2024_2025_ARI30_20260815",
                years=["2024"],
                expected_files=63,
                expected_bytes=20_533_860_560,
            )


if __name__ == "__main__":
    unittest.main()
