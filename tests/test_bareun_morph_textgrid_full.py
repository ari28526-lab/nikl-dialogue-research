from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = PROJECT_ROOT / "scripts" / "python"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from pipeline_common import sha256_file  # noqa: E402
from research_textgrid_v2 import BASE_TIERS, parse_mfa_textgrid, write_textgrid_exact  # noqa: E402
from run_bareun_morph_textgrid_full import (  # noqa: E402
    StorageSafetyStop,
    choose_storage,
    derive_atomic,
    init_database,
    pending_receipts_from_checkpoint,
    primary_control_reserve_bytes,
    process_receipt,
    same_intervals,
)
from audit_bareun_morph_textgrid_full import audit_one_shard  # noqa: E402


def write_gzip_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class StorageRoutingTests(unittest.TestCase):
    def test_primary_is_preferred(self) -> None:
        self.assertEqual(
            choose_storage(
                required_bytes=10,
                primary_free_bytes=100,
                primary_floor_bytes=50,
                spill_free_bytes=200,
                spill_floor_bytes=50,
            ),
            "external_d",
        )

    def test_spill_is_used_when_primary_would_cross_floor(self) -> None:
        self.assertEqual(
            choose_storage(
                required_bytes=30,
                primary_free_bytes=70,
                primary_floor_bytes=50,
                spill_free_bytes=100,
                spill_floor_bytes=50,
            ),
            "local_c",
        )

    def test_both_unsafe_stops_before_write(self) -> None:
        with self.assertRaises(StorageSafetyStop):
            choose_storage(
                required_bytes=30,
                primary_free_bytes=70,
                primary_floor_bytes=50,
                spill_free_bytes=70,
                spill_floor_bytes=50,
            )

    def test_spill_routing_is_sticky_after_it_starts(self) -> None:
        self.assertEqual(
            choose_storage(
                required_bytes=10,
                primary_free_bytes=100,
                primary_floor_bytes=50,
                spill_free_bytes=100,
                spill_floor_bytes=50,
                spill_started=True,
            ),
            "local_c",
        )

    def test_primary_control_reserve_is_conservative(self) -> None:
        self.assertEqual(primary_control_reserve_bytes(1), 1024**2)
        self.assertEqual(primary_control_reserve_bytes(2048), 2 * 1024**2)


class TextGridContractTests(unittest.TestCase):
    def test_only_morph_label_changes(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temporary:
            root = Path(temporary)
            source = root / "source.TextGrid"
            derived = root / "derived.TextGrid"
            tier_data = [
                ("words", [(0.0, 1.0, "가"), (1.0, 2.0, "나")]),
                ("phones_mfa", [(0.0, 2.0, "k a n a")]),
                ("phoneme_r_auto", [(0.0, 2.0, "k a n a")]),
                ("utterance", [(0.0, 2.0, "가 나")]),
                ("utterance_orth_r", [(0.0, 2.0, "가 나")]),
                ("morph_analysis_utt", [(0.0, 2.0, "옛/NNG")]),
            ]
            write_textgrid_exact(source, duration=2.0, tier_data=tier_data)
            source_sha = sha256_file(source)
            derive_atomic(source, derived, "가/NNG | 나/NNG")
            self.assertEqual(sha256_file(source), source_sha)
            _, source_tiers = parse_mfa_textgrid(source)
            _, derived_tiers = parse_mfa_textgrid(derived)
            self.assertEqual(list(derived_tiers), BASE_TIERS)
            for name in BASE_TIERS[:5]:
                self.assertTrue(same_intervals(source_tiers[name], derived_tiers[name]))
            self.assertEqual(
                [label for _, _, label in derived_tiers["morph_analysis_utt"] if label],
                ["가/NNG | 나/NNG"],
            )
            with self.assertRaises(FileExistsError):
                derive_atomic(source, derived, "다른/NNG")

    def test_deep_spill_path_uses_short_staging_name(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temporary:
            root = Path(temporary)
            source = root / "source.TextGrid"
            deep_parent = root / ("a" * 40) / ("b" * 40)
            derived = deep_parent / "SDRW2400000227.1.1.1.TextGrid"
            tier_data = [
                ("words", [(0.0, 1.0, "가")]),
                ("phones_mfa", [(0.0, 1.0, "k a")]),
                ("phoneme_r_auto", [(0.0, 1.0, "k a")]),
                ("utterance", [(0.0, 1.0, "가")]),
                ("utterance_orth_r", [(0.0, 1.0, "가")]),
                ("morph_analysis_utt", [(0.0, 1.0, "옛/NNG")]),
            ]
            write_textgrid_exact(source, duration=1.0, tier_data=tier_data)

            derive_atomic(source, derived, "새/NNG")

            self.assertTrue(derived.is_file())
            self.assertEqual(list(deep_parent.glob("*.partial")), [])
            _, tiers = parse_mfa_textgrid(derived)
            self.assertEqual(
                [label for _, _, label in tiers["morph_analysis_utt"] if label],
                ["새/NNG"],
            )


class TinyReceiptResumeTests(unittest.TestCase):
    def test_resume_uses_checkpoint_without_rehashing_completed_receipts(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temporary:
            connection = init_database(Path(temporary) / "CHECKPOINT.sqlite")
            try:
                inventory = [
                    ("files/a/RECEIPT.json", "a" * 64),
                    ("files/b/RECEIPT.json", "b" * 64),
                    ("files/c/RECEIPT.json", "c" * 64),
                ]
                connection.executemany(
                    """INSERT INTO shards
                    (source_file, receipt_relative, receipt_sha256, storage_id,
                     status, estimated_bytes, aligned_expected,
                     shard_receipt_relative)
                    VALUES (?, ?, ?, 'external_d', ?, 1, 1, ?)""",
                    [
                        (
                            "source-a",
                            inventory[0][0],
                            inventory[0][1],
                            "completed",
                            "shards/a/SHARD_RECEIPT.json",
                        ),
                        (
                            "source-b",
                            inventory[1][0],
                            inventory[1][1],
                            "processing",
                            None,
                        ),
                    ],
                )
                connection.commit()

                pending, completed = pending_receipts_from_checkpoint(
                    connection, inventory
                )

                self.assertEqual(completed, 1)
                self.assertEqual(
                    pending,
                    [
                        (2, inventory[1][0], inventory[1][1]),
                        (3, inventory[2][0], inventory[2][1]),
                    ],
                )
            finally:
                connection.close()

    def test_resume_checkpoint_sha_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temporary:
            connection = init_database(Path(temporary) / "CHECKPOINT.sqlite")
            try:
                connection.execute(
                    """INSERT INTO shards
                    (source_file, receipt_relative, receipt_sha256, storage_id,
                     status, estimated_bytes, aligned_expected,
                     shard_receipt_relative)
                    VALUES ('source-a', 'files/a/RECEIPT.json', ?,
                            'external_d', 'completed', 1, 1,
                            'shards/a/SHARD_RECEIPT.json')""",
                    ("b" * 64,),
                )
                connection.commit()
                with self.assertRaisesRegex(RuntimeError, "SHA mismatch"):
                    pending_receipts_from_checkpoint(
                        connection,
                        [("files/a/RECEIPT.json", "a" * 64)],
                    )
            finally:
                connection.close()

    def test_receipt_build_and_verified_resume(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "work") as temporary:
            root = Path(temporary)
            final_root = root / "bareun"
            source_root = root / "source"
            primary = root / "primary"
            spill = root / "spill"
            primary.mkdir()
            spill.mkdir()
            source_file = "NIKL_DIALOGUE_2020_v1.4/SESSION.csv"
            receipt_relative = "files/NIKL_DIALOGUE_2020_v1.4/SESSION/RECEIPT.json"
            receipt_path = final_root / receipt_relative
            parent = receipt_path.parent
            utterance_path = parent / "utterances.csv.gz"
            morpheme_path = parent / "morphemes.csv.gz"
            utterances = [
                {
                    "source_row_index": 0,
                    "utt_id": "utt_aligned",
                    "response_token_count": 2,
                },
                {
                    "source_row_index": 1,
                    "utt_id": "utt_no_mfa",
                    "response_token_count": 1,
                },
            ]
            morphemes = [
                {"utt_id": "utt_aligned", "token_index": 0, "morph_index": 0, "morph_surface": "가", "pos": "NNG"},
                {"utt_id": "utt_aligned", "token_index": 1, "morph_index": 1, "morph_surface": "나", "pos": "NNG"},
                {"utt_id": "utt_no_mfa", "token_index": 0, "morph_index": 0, "morph_surface": "다", "pos": "NNG"},
            ]
            write_gzip_csv(
                utterance_path,
                ["source_row_index", "utt_id", "response_token_count"],
                utterances,
            )
            write_gzip_csv(
                morpheme_path,
                ["utt_id", "token_index", "morph_index", "morph_surface", "pos"],
                morphemes,
            )
            receipt_path.write_text(
                json.dumps(
                    {
                        "source_file": source_file,
                        "outputs": {
                            "utterances.csv.gz": {
                                "bytes": utterance_path.stat().st_size,
                                "sha256": sha256_file(utterance_path),
                            },
                            "morphemes.csv.gz": {
                                "bytes": morpheme_path.stat().st_size,
                                "sha256": sha256_file(morpheme_path),
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            receipt_sha = sha256_file(receipt_path)
            source = source_root / "2020" / "SESSION" / "utt_aligned.TextGrid"
            source.parent.mkdir(parents=True)
            write_textgrid_exact(
                source,
                duration=2.0,
                tier_data=[
                    ("words", [(0.0, 1.0, "가"), (1.0, 2.0, "나")]),
                    ("phones_mfa", [(0.0, 2.0, "k a n a")]),
                    ("phoneme_r_auto", [(0.0, 2.0, "k a n a")]),
                    ("utterance", [(0.0, 2.0, "가 나")]),
                    ("utterance_orth_r", [(0.0, 2.0, "가 나")]),
                    ("morph_analysis_utt", [(0.0, 2.0, "이전/NNG")]),
                ],
            )
            config = {
                "storage": {
                    "primary_id": "external_d",
                    "spill_id": "local_c",
                    "primary_minimum_free_gib": 0,
                    "spill_minimum_free_gib": 0,
                    "shard_estimate_multiplier": 1.1,
                    "shard_estimate_fixed_bytes_per_file": 512,
                }
            }
            connection = init_database(primary / "CHECKPOINT.sqlite")
            try:
                result = process_receipt(
                    config=config,
                    primary_root=primary,
                    roots={"external_d": primary, "local_c": spill},
                    connection=connection,
                    final_root=final_root,
                    source_root=source_root,
                    receipt_relative=receipt_relative,
                    receipt_sha=receipt_sha,
                    commit_every=1,
                )
                self.assertEqual(result["status"], "completed")
                counts = connection.execute(
                    "SELECT status, COUNT(*) FROM outputs GROUP BY status ORDER BY status"
                ).fetchall()
                self.assertEqual(counts, [("derived", 1), ("no_mfa_alignment", 1)])
                shard_row = connection.execute(
                    "SELECT storage_id, shard_receipt_relative FROM shards "
                    "WHERE source_file=?",
                    (source_file,),
                ).fetchone()
                shard_path = primary / str(shard_row[1])
                audited = audit_one_shard(
                    final_root=final_root,
                    source_root=source_root,
                    roots={"external_d": primary, "local_c": spill},
                    primary_root=primary,
                    receipt_relative=receipt_relative,
                    bareun_receipt_sha=receipt_sha,
                    storage_id=str(shard_row[0]),
                    shard_receipt_relative=str(shard_row[1]),
                    shard_receipt_sha=sha256_file(shard_path),
                )
                self.assertEqual(audited["derived"], 1)
                self.assertEqual(audited["no_mfa_alignment"], 1)
                resumed = process_receipt(
                    config=config,
                    primary_root=primary,
                    roots={"external_d": primary, "local_c": spill},
                    connection=connection,
                    final_root=final_root,
                    source_root=source_root,
                    receipt_relative=receipt_relative,
                    receipt_sha=receipt_sha,
                    commit_every=1,
                )
                self.assertEqual(resumed["status"], "skipped_verified")
            finally:
                connection.close()


class StaticContractTests(unittest.TestCase):
    def test_config_and_powershell_contract(self) -> None:
        config = json.loads(
            (PROJECT_ROOT / "config" / "bareun_morph_textgrid_full_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(config["input"]["expected_aligned_textgrids"], 4_286_046)
        self.assertEqual(config["storage"]["primary_minimum_free_gib"], 18.0)
        self.assertEqual(config["storage"]["spill_minimum_free_gib"], 20.0)
        self.assertFalse(config["output"]["promotion_during_build"])
        wrapper = (PROJECT_ROOT / "run_bareun_morph_textgrid_full.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("BAREUN_MORPH_TEXTGRID_FULL_20260829", wrapper)
        self.assertIn("[Convert]::ToUInt32('80000000', 16)", wrapper)
        self.assertIn("--preflight-only", wrapper)
        self.assertIn("audit_bareun_morph_textgrid_full.py", wrapper)


if __name__ == "__main__":
    unittest.main()
