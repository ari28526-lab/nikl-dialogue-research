import csv
import gzip
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from export_mfa_db_research_6tier import (  # noqa: E402
    _db_inventory,
    _session_intervals,
    load_session_rows,
    open_readonly,
)
from phoneme_roman import (  # noqa: E402
    classify_phone,
    load_acoustic_meta,
    model_group_lookup,
)
from repair_mfa_textgrid_phone_only_silence_words import repair  # noqa: E402
from research_textgrid_v2 import write_base_textgrid_from_intervals  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402
from tests.test_export_mfa_db_research_6tier import (  # noqa: E402
    ExportMfaDbResearch6TierTests,
)


class RepairPhoneOnlySilenceWordTests(unittest.TestCase):
    def test_archives_and_blanks_only_phone_only_trailing_word(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            helper = ExportMfaDbResearch6TierTests()
            db = root / "2021.db"
            acoustic = root / "acoustic.zip"
            contract = root / "alignment.json"
            search = root / "search"
            output = root / "output"
            archive = root / "archive"
            partial = root / "utterance.partial.gz"
            manifest = root / "repair.json"
            helper.make_db(db)
            helper.make_acoustic(acoustic)
            helper.make_contract(contract)
            helper.make_search(search)
            connection = sqlite3.connect(db)
            connection.execute("UPDATE word_interval SET word_id=1 WHERE id=3")
            connection.commit()
            connection.close()

            connection = open_readonly(db)
            try:
                word_labels, phone_labels = _db_inventory(connection)
                words, phones = _session_intervals(
                    connection,
                    [1],
                    word_labels,
                    phone_labels,
                    normalize_phone_only_silence_words=False,
                )
            finally:
                connection.close()
            row = load_session_rows(search, "2021", "S1")["S1.1"]
            groups = model_group_lookup(load_acoustic_meta(acoustic))
            destination = output / "2021" / "S1" / "S1.1.TextGrid"
            write_base_textgrid_from_intervals(
                destination,
                duration=1.0,
                words=[(value[1], value[2], value[3]) for value in words[1]],
                phones=[(value[1], value[2], value[3]) for value in phones[1]],
                row=row,
                phone_mapper=lambda phone: classify_phone(
                    phone, groups
                ).phone_class_r_auto,
            )
            with gzip.open(
                partial, "wt", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "utt_id",
                        "n_lab_words_expected",
                        "n_mfa_words_aligned",
                        "lab_word_count_match",
                        "word_label_sequence_match",
                    ],
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": "S1.1",
                        "n_lab_words_expected": "1",
                        "n_mfa_words_aligned": "2",
                        "lab_word_count_match": "false",
                        "word_label_sequence_match": "false",
                    }
                )

            ready = repair(
                year="2021",
                db_path=db,
                search_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=contract,
                utterance_table_partial=partial,
                archive_root=archive,
                manifest_path=manifest,
                apply=False,
            )
            self.assertEqual(ready["status"], "ready")
            applied = repair(
                year="2021",
                db_path=db,
                search_root=search,
                output_root=output,
                acoustic_model=acoustic,
                alignment_contract=contract,
                utterance_table_partial=partial,
                archive_root=archive,
                manifest_path=manifest,
                apply=True,
            )
            self.assertEqual(applied["status"], "success")
            _duration, tiers = parse_mfa_textgrid(destination)
            self.assertEqual(tiers["words"][-1][2], "")
            archived = archive / "2021" / "S1" / "S1.1.TextGrid"
            _old_duration, old_tiers = parse_mfa_textgrid(archived)
            self.assertNotEqual(old_tiers["words"][-1][2], "")
            self.assertEqual(tiers["phones_mfa"], old_tiers["phones_mfa"])


if __name__ == "__main__":
    unittest.main()
