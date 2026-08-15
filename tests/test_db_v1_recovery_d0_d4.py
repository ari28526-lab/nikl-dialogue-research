import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "python" / "build_db_v1_recovery_d0_d4.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("build_db_v1_recovery_d0_d4", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RecoveryD0D4Tests(unittest.TestCase):
    def test_reason_routing_separates_technical_and_pronunciation(self):
        post = MODULE.route_fields(
            "post_mfa_technical_exclusion", ["mfa_feature_generation_failed"], "2024"
        )
        self.assertEqual(post["recovery_family"], "post_mfa_feature")
        self.assertEqual(post["recovery_priority"], "P0")
        audio = MODULE.route_fields(
            "pre_mfa_technical_exclusion", ["audio_pairing_unresolved"], "2023"
        )
        self.assertEqual(audio["recovery_family"], "audio_identity_topology")
        policy = MODULE.route_fields(
            "pronunciation_followup",
            ["pronunciation_policy_token", "routing_class:policy"],
            "2022",
        )
        self.assertEqual(policy["recovery_family"], "pronunciation_policy")
        self.assertEqual(policy["recovery_eligibility"], "linguistic_evidence_review")

    def test_technical_classification_does_not_accept_filename_as_identity(self):
        klass, action = MODULE.classify_technical(
            "pre_mfa_technical_exclusion", ["audio_pairing_unresolved"], True, False, False
        )
        self.assertEqual(klass, "requires_audio_identity_review")
        self.assertIn("not_filename_only", action)
        klass, _ = MODULE.classify_technical(
            "post_mfa_technical_exclusion", ["mfa_alignment_missing"], True, True, True
        )
        self.assertEqual(klass, "ready_for_alignment_diagnostic")

    def test_pronunciation_evidence_never_becomes_realization_decision(self):
        selected = {
            "release_selected_variant_count": "1",
            "planning_candidate_variant_count": "1",
            "dictionary_pron_hangul_json": '["가"]',
        }
        self.assertEqual(
            MODULE.pronunciation_review_class("hold", selected),
            "routing_consistency_review",
        )
        self.assertEqual(
            MODULE.pronunciation_review_class("policy", selected),
            "policy_decision_required",
        )
        self.assertEqual(
            MODULE.pronunciation_review_class("unknown", None),
            "token_inventory_investigation",
        )

    def test_first_shard_is_all_feature_plus_five_sessions_per_year(self):
        rows = []
        for index in range(25):
            year = MODULE.YEARS[index % len(MODULE.YEARS)]
            rows.append(self._row(year, f"F{index:03d}", f"FS{index:03d}", "mfa_feature_generation_failed", "ready_for_feature_failure_diagnostic"))
        for year in MODULE.YEARS:
            for index in range(7):
                rows.append(self._row(year, f"A{year}{index}", f"S{year}{index}", "mfa_alignment_missing", "ready_for_alignment_diagnostic"))
        selected = MODULE.choose_first_shard(rows)
        self.assertEqual(len(selected), 55)
        self.assertEqual(sum(row["reason_code"] == "mfa_feature_generation_failed" for row in selected), 25)
        for year in MODULE.YEARS:
            sessions = {
                row["session_id"] for row in selected
                if row["year"] == year and row["reason_code"] == "mfa_alignment_missing"
            }
            self.assertEqual(len(sessions), 5)

    @staticmethod
    def _row(year, utt, session, reason, klass):
        return {
            "year": year, "utt_id": utt, "session_id": session,
            "reason_code": reason, "recoverability_class": klass,
            "form": "가", "original_form": "가",
            "r3_corpus_wav_path": "x.wav", "r3_corpus_wav_bytes": "10",
            "r3_corpus_lab_path": "x.lab", "r3_corpus_lab_bytes": "2",
        }


if __name__ == "__main__":
    unittest.main()
