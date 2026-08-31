from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = PROJECT_ROOT / "scripts" / "python"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from apply_mfa_temp_cleanup_exact import (  # noqa: E402
    apply_plan,
    build_plan,
    finalize_existing_apply,
)
from pipeline_common import sha256_file  # noqa: E402


class ExactTempCleanupTests(unittest.TestCase):
    def make_inventory(self, root: Path, report: Path) -> dict[str, object]:
        db = root / "2021.db"
        log = root / "2021.log"
        candidate = root / "2021" / "split4" / "final_features.1.ark"
        candidate.parent.mkdir(parents=True)
        db.write_bytes(b"database")
        log.write_text("retain", encoding="utf-8")
        candidate.write_bytes(b"candidate")
        rows = []
        for path, classification in (
            (db, "retain_critical"),
            (log, "retain_reproducibility"),
            (candidate, "cleanup_candidate_after_qc"),
        ):
            stat = path.stat()
            rows.append(
                {
                    "relative_path": path.relative_to(root).as_posix(),
                    "path": str(path.resolve()),
                    "bytes": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "classification": classification,
                    "reason": "test",
                }
            )
        inventory = {
            "kind": "mfa_storage_inventory_and_cleanup_dry_run",
            "status": "ready_for_user_review",
            "year": "2021",
            "temp_year": str(root.resolve()),
            "blockers": [],
            "unsafe_links": [],
            "active_transaction_files": [],
            "unclassified_files": [],
            "files": rows,
        }
        report.write_text(json.dumps(inventory), encoding="utf-8")
        return {
            "year": "2021",
            "temp_root": str(root.resolve()),
            "inventory_sha256": sha256_file(report),
            "candidate_files": 1,
            "candidate_bytes": candidate.stat().st_size,
            "retained_db_sha256": sha256_file(db),
        }

    def test_exact_candidate_deleted_and_retained_assets_preserved(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temporary:
            base = Path(temporary)
            root = base / "temp" / "2021"
            root.mkdir(parents=True)
            report = base / "inventory.json"
            scope = self.make_inventory(root, report)
            plan = build_plan(report, scope)
            self.assertEqual(plan["status"], "dry_run_passed")

            result = apply_plan(plan, base / "apply.json")

            self.assertEqual(result["status"], "passed")
            self.assertFalse(
                (root / "2021" / "split4" / "final_features.1.ark").exists()
            )
            self.assertTrue((root / "2021.db").is_file())
            self.assertTrue((root / "2021.log").is_file())

    def test_changed_candidate_blocks_before_deletion(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temporary:
            base = Path(temporary)
            root = base / "temp" / "2021"
            root.mkdir(parents=True)
            report = base / "inventory.json"
            scope = self.make_inventory(root, report)
            candidate = root / "2021" / "split4" / "final_features.1.ark"
            candidate.write_bytes(b"changed")

            plan = build_plan(report, scope)

            self.assertEqual(plan["status"], "blocked")
            self.assertTrue(
                any("file_changed_or_missing" in item for item in plan["blockers"])
            )
            self.assertTrue(candidate.is_file())

    def test_interrupted_postdelete_state_can_be_finalized(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temporary:
            base = Path(temporary)
            root = base / "temp" / "2021"
            root.mkdir(parents=True)
            report = base / "inventory.json"
            output = base / "apply.json"
            scope = self.make_inventory(root, report)
            plan = build_plan(report, scope)
            candidate = root / "2021" / "split4" / "final_features.1.ark"
            candidate_record = plan["candidates"][0]
            candidate.unlink()
            state = dict(plan)
            state.update(
                {
                    "status": "deletion_in_progress",
                    "drive_free_bytes_before": 0,
                    "deleted": [
                        {
                            "path": str(candidate_record["path"]),
                            "bytes": int(candidate_record["bytes"]),
                            "deleted_at": "test",
                        }
                    ],
                    "current_path": None,
                }
            )
            output.write_text(json.dumps(state), encoding="utf-8")

            result = finalize_existing_apply(report, scope, output)

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["deleted_files"], 1)
            self.assertTrue((root / "2021.db").is_file())


if __name__ == "__main__":
    unittest.main()
