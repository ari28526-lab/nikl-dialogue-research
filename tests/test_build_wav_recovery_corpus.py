from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_wav_recovery_corpus import apply_recovery, dry_run, scan_corpus  # noqa: E402
from pipeline_common import sha256_file  # noqa: E402


def write_wav(path: Path, frames: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(1000)
        stream.writeframes(b"\x00\x00" * frames)


class WavRecoveryCorpusDryRunTests(unittest.TestCase):
    def test_scan_rejects_source_reused_by_identity_and_remap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            source = root / "source"
            year = "2023"
            session = "S"
            (search / year).mkdir(parents=True)
            with (search / year / f"{session}.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=["utt_id", "form"])
                writer.writeheader()
                writer.writerow({"utt_id": "S.1", "form": "하나"})
                writer.writerow({"utt_id": "S.2", "form": "둘"})
            write_wav(source / year / session / "S.1.wav", 100)
            write_wav(source / year / session / "S.2.wav", 200)
            plan = {
                "year": year,
                "session": session,
                "target_utt_id": "S.2",
                "source_utt_id": "S.1",
                "status": "remap_high_confidence",
                "block_length": "3",
                "target_duration_seconds": "0.1",
                "source_duration_seconds": "0.1",
                "duration_residual_seconds": "0",
                "source_wav": str(source / year / session / "S.1.wav"),
            }
            with self.assertRaisesRegex(RuntimeError, "둘 이상의 target"):
                scan_corpus(
                    year=year,
                    search_master_root=search,
                    source_wav_root=source,
                    plan_rows=[plan],
                    plan_by_target={"S.2": plan},
                )

    def test_reviewed_plan_builds_fail_closed_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search"
            source = root / "source"
            output = root / "output"
            archive = root / "archive"
            session = "S1"
            unaffected_session = "S2"
            missing_session = "S3"
            year = "2020"
            (search / year).mkdir(parents=True)
            (search / "_build_meta.json").write_text(
                json.dumps({"status": "success"}), encoding="utf-8"
            )
            ids = [f"{session}.1.1.{index}" for index in range(1, 15)]
            with (search / year / f"{session}.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=["utt_id", "form"])
                writer.writeheader()
                for utt_id in ids:
                    writer.writerow({"utt_id": utt_id, "form": utt_id})
            for index, utt_id in enumerate(ids, 1):
                write_wav(source / year / session / f"{utt_id}.wav", 100 + index)
            unaffected_ids = [
                f"{unaffected_session}.1.1.1",
                f"{unaffected_session}.1.1.2",
            ]
            with (search / year / f"{unaffected_session}.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=["utt_id", "form"])
                writer.writeheader()
                for utt_id in unaffected_ids:
                    writer.writerow({"utt_id": utt_id, "form": utt_id})
            for index, utt_id in enumerate(unaffected_ids, 1):
                write_wav(
                    source / year / unaffected_session / f"{utt_id}.wav",
                    200 + index,
                )
            missing_ids = [
                f"{missing_session}.1.1.1",
                f"{missing_session}.1.1.2",
            ]
            with (search / year / f"{missing_session}.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=["utt_id", "form"])
                writer.writeheader()
                for utt_id in missing_ids:
                    writer.writerow({"utt_id": utt_id, "form": utt_id})

            plan = root / "plan.csv"
            fields = [
                "year", "session", "target_utt_id", "source_utt_id",
                "status", "block_length", "target_duration_seconds",
                "source_duration_seconds", "duration_residual_seconds", "source_wav",
            ]
            plan_rows = []
            for index, target in enumerate(ids):
                source_id = ids[(index + 1) % len(ids)]
                plan_rows.append(
                    {
                        "year": year,
                        "session": session,
                        "target_utt_id": target,
                        "source_utt_id": source_id,
                        "status": "remap_high_confidence",
                        "block_length": "12",
                        "target_duration_seconds": "0.1",
                        "source_duration_seconds": "0.11",
                        "duration_residual_seconds": "0",
                        "source_wav": str(source / year / session / f"{source_id}.wav"),
                    }
                )
            plan_rows[-2]["status"] = "ambiguous_short_match"
            plan_rows[-1]["status"] = "target_unresolved"
            plan_rows[-1]["source_utt_id"] = ""
            plan_rows[-1]["source_wav"] = ""
            for target in missing_ids:
                plan_rows.append(
                    {
                        "year": year,
                        "session": missing_session,
                        "target_utt_id": target,
                        "source_utt_id": "",
                        "status": "target_unresolved",
                        "block_length": "0",
                        "target_duration_seconds": "0.1",
                        "source_duration_seconds": "",
                        "duration_residual_seconds": "",
                        "source_wav": "",
                    }
                )
            with plan.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(plan_rows)

            review_manifest = root / "review_manifest.json"
            review_decisions = root / "review_decisions.json"
            review_ids = ids[:12]
            review_manifest.write_text(
                json.dumps(
                    {
                        "plan_csv_sha256": sha256_file(plan),
                        "review_rows": [
                            {"target_utt_id": utt_id} for utt_id in review_ids
                        ],
                    }
                ),
                encoding="utf-8",
            )
            review_decisions.write_text(
                json.dumps(
                    {
                        "decisions": [
                            {
                                "target_utt_id": utt_id,
                                "decision": "A_MATCHES_TARGET",
                            }
                            for utt_id in review_ids
                        ]
                    }
                ),
                encoding="utf-8",
            )

            source_hashes = {
                str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (source / year).rglob("*.wav")
            }
            report = dry_run(
                year=year,
                plan_path=plan,
                search_master_root=search,
                source_wav_root=source,
                output_wav_root=output,
                archive_base=archive,
                review_manifest_path=review_manifest,
                review_decisions_path=review_decisions,
            )

            self.assertEqual(report["status"], "dry_run_passed")
            self.assertEqual(report["scan"]["search_utterances"], 18)
            self.assertEqual(report["scan"]["corpus_entries"], 14)
            self.assertEqual(report["scan"]["omitted_for_review"], 4)
            self.assertEqual(
                report["scan"]["mapping_counts"]["remap_high_confidence"], 12
            )
            self.assertFalse(output.exists())
            self.assertFalse(archive.exists())
            self.assertEqual(
                source_hashes,
                {
                    str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (source / year).rglob("*.wav")
                },
            )

            applied = apply_recovery(
                preflight=report,
                year=year,
                plan_path=plan,
                search_master_root=search,
                source_wav_root=source,
                output_wav_root=output,
                archive_base=archive,
                approved_by="test_researcher",
                require_independent_archive=False,
            )
            self.assertEqual(applied["status"], "passed")
            self.assertEqual(applied["wav_files"], 14)
            remapped = output / year / session / f"{ids[0]}.wav"
            proposed = source / year / session / f"{ids[1]}.wav"
            self.assertEqual(sha256_file(remapped), sha256_file(proposed))
            self.assertFalse(os.path.samefile(remapped, proposed))
            unaffected_output = (
                output / year / unaffected_session / f"{unaffected_ids[0]}.wav"
            )
            unaffected_source = (
                source / year / unaffected_session / f"{unaffected_ids[0]}.wav"
            )
            self.assertTrue(os.path.samefile(unaffected_output, unaffected_source))
            self.assertFalse((output / year / session / f"{ids[-1]}.wav").exists())
            self.assertTrue((output / year / missing_session).is_dir())
            self.assertEqual(
                list((output / year / missing_session).glob("*.wav")), []
            )
            with zipfile.ZipFile(
                Path(applied["archive_root"]) / "sessions" / f"{session}.zip"
            ) as archived:
                self.assertEqual(len(archived.namelist()), 14)
            missing_manifest = json.loads(
                (
                    Path(applied["archive_root"])
                    / "session_manifests"
                    / f"{missing_session}.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(missing_manifest["status"], "verified_absent")
            self.assertEqual(missing_manifest["file_count"], 0)
            self.assertFalse(
                (
                    Path(applied["archive_root"])
                    / "sessions"
                    / f"{missing_session}.zip"
                ).exists()
            )
            reused = apply_recovery(
                preflight=report,
                year=year,
                plan_path=plan,
                search_master_root=search,
                source_wav_root=source,
                output_wav_root=output,
                archive_base=archive,
                approved_by="test_researcher",
                require_independent_archive=False,
            )
            self.assertTrue(reused["reused"])
            self.assertEqual(
                source_hashes,
                {
                    str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (source / year).rglob("*.wav")
                },
            )

    def test_rejects_nonmatching_review_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.csv"
            plan.write_text(
                "year,session,target_utt_id,source_utt_id,status,block_length,"
                "target_duration_seconds,source_duration_seconds,"
                "duration_residual_seconds,source_wav\n",
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            decisions = root / "decisions.json"
            review_rows = [{"target_utt_id": f"U{i}"} for i in range(12)]
            manifest.write_text(
                json.dumps(
                    {"plan_csv_sha256": sha256_file(plan), "review_rows": review_rows}
                ),
                encoding="utf-8",
            )
            decisions.write_text(
                json.dumps(
                    {
                        "decisions": [
                            {
                                "target_utt_id": f"U{i}",
                                "decision": "A_MATCHES_TARGET" if i else "pending",
                            }
                            for i in range(12)
                        ]
                    }
                ),
                encoding="utf-8",
            )
            from build_wav_recovery_corpus import validate_review

            with self.assertRaisesRegex(RuntimeError, "미완료"):
                validate_review(
                    plan_path=plan,
                    review_manifest_path=manifest,
                    review_decisions_path=decisions,
                )


if __name__ == "__main__":
    unittest.main()
