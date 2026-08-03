import csv
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from build_simple_post_mfa_review_bundle import build_bundle  # noqa: E402
from pipeline_common import sha256_file  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402


class SimplePostMfaReviewBundleTests(unittest.TestCase):
    def make_db(self, path: Path) -> None:
        connection = sqlite3.connect(path)
        connection.executescript(
            """
            CREATE TABLE file(
                id INTEGER PRIMARY KEY, name TEXT, relative_path TEXT
            );
            CREATE TABLE sound_file(
                file_id INTEGER PRIMARY KEY, duration FLOAT,
                sound_file_path TEXT
            );
            CREATE TABLE utterance(
                id INTEGER PRIMARY KEY, file_id INTEGER, ignored BOOLEAN,
                normalized_text TEXT, alignment_score FLOAT
            );
            CREATE TABLE word(id INTEGER PRIMARY KEY, word TEXT);
            CREATE TABLE phone(
                id INTEGER PRIMARY KEY, phone TEXT, phone_type TEXT
            );
            CREATE TABLE word_interval(
                id INTEGER PRIMARY KEY, utterance_id INTEGER,
                begin FLOAT, end FLOAT, word_id INTEGER
            );
            CREATE TABLE phone_interval(
                id INTEGER PRIMARY KEY, utterance_id INTEGER,
                begin FLOAT, end FLOAT, phone_id INTEGER,
                word_interval_id INTEGER
            );
            """
        )
        connection.executemany(
            "INSERT INTO file VALUES(?, ?, ?)",
            [(1, "S1.1", "S1"), (2, "S1.2", "S1")],
        )
        connection.executemany(
            "INSERT INTO sound_file VALUES(?, ?, ?)",
            [(1, 1.0, "S1.1.wav"), (2, 1.0, "S1.2.wav")],
        )
        connection.executemany(
            "INSERT INTO utterance VALUES(?, ?, 0, ?, ?)",
            [(1, 1, "실패", None), (2, 2, "성공", -10.0)],
        )
        connection.execute("INSERT INTO word VALUES(1, '성공')")
        connection.execute("INSERT INTO phone VALUES(1, 'k', 'non_silence')")
        connection.execute("INSERT INTO word_interval VALUES(1, 2, 0.1, 0.9, 1)")
        connection.execute("INSERT INTO phone_interval VALUES(1, 2, 0.1, 0.9, 1, 1)")
        connection.commit()
        connection.close()

    def make_search(self, root: Path) -> None:
        path = root / "2020" / "S1.csv"
        path.parent.mkdir(parents=True)
        fields = [
            "utt_id",
            "year",
            "session_id",
            "speaker_id",
            "form",
            "original_form",
            "form_roman",
            "tagged",
            "n_eojeol",
            "pron_reference_form",
            "pron_reference_n_eojeol",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for utt_id, form in (("S1.1", "실패"), ("S1.2", "성공")):
                writer.writerow(
                    {
                        "utt_id": utt_id,
                        "year": "2020",
                        "session_id": "S1",
                        "speaker_id": "SP1",
                        "form": form,
                        "original_form": form,
                        "form_roman": "S I L P AE" if form == "실패" else "S EO NG G O NG",
                        "tagged": f"{form}/NNG",
                        "n_eojeol": "1",
                        "pron_reference_form": form,
                        "pron_reference_n_eojeol": "1",
                    }
                )

    def make_review(self, root: Path) -> Path:
        media = root / "media"
        media.mkdir()
        rows = []
        for order, utt_id, role, text in (
            (1, "S1.1", "missing", "실패"),
            (2, "S1.2", "aligned_control", "성공"),
        ):
            wav = media / f"{utt_id}.wav"
            lab = media / f"{utt_id}.lab"
            wav.write_bytes(b"RIFFfixture" + bytes([order]))
            lab.write_text(text, encoding="utf-8")
            rows.append(
                {
                    "review_order": order,
                    "sample_role": role,
                    "year": "2020",
                    "utt_id": utt_id,
                    "session_id": "S1",
                    "normalized_text": text,
                    "wav_path": str(wav),
                    "lab_path": str(lab),
                }
            )
        path = root / "review.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def make_acoustic(self, path: Path) -> None:
        meta = {"phones": ["k"], "phone_groups": {"0": ["k"]}}
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("acoustic/meta.json", json.dumps(meta))

    def test_builds_flat_numbered_bundle_without_modifying_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "2020.db"
            search = root / "search"
            acoustic = root / "acoustic.zip"
            output = root / "bundle"
            self.make_db(db)
            self.make_search(search)
            review = self.make_review(root)
            self.make_acoustic(acoustic)
            before = sha256_file(db)

            result = build_bundle(
                review_csv=review,
                db_path=db,
                search_master_root=search,
                acoustic_model=acoustic,
                output_root=output,
                prefill_match_orders={1},
            )

            self.assertEqual(sha256_file(db), before)
            self.assertEqual(result["review_count"], 2)
            self.assertEqual(result["missing_alignment_count"], 1)
            self.assertEqual(result["aligned_control_count"], 1)
            self.assertTrue((output / "01__S1.1__NO_CURRENT_TEXTGRID.txt").is_file())
            self.assertFalse((output / "01__S1.1__CURRENT_MFA_6TIER.TextGrid").exists())
            tg = output / "02__S1.2__CURRENT_MFA_6TIER.TextGrid"
            duration, tiers = parse_mfa_textgrid(tg)
            self.assertEqual(duration, 1.0)
            self.assertEqual(list(tiers), [
                "words",
                "phones_mfa",
                "phoneme_r_auto",
                "utterance",
                "utterance_orth_r",
                "morph_analysis_utt",
            ])
            with (output / "00_REVIEW.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["decision"], "match")
            self.assertEqual(rows[1]["decision"], "pending")
            self.assertEqual(rows[0]["search_csv_file"], "01__S1.1__SEARCH.csv")


if __name__ == "__main__":
    unittest.main()
