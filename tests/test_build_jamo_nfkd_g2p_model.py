import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import build_jamo_nfkd_g2p_model as builder  # noqa: E402


def write_source(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "jamo/meta.json",
            json.dumps(
                {
                    "architecture": "phonetisaurus",
                    "unicode_decomposition": None,
                    "phones": ["a", "k"],
                    "graphemes": ["ᄀ", "ᅡ"],
                }
            ),
        )
        archive.writestr("jamo/model.fst", b"fst-bytes")
        archive.writestr("jamo/phones.sym", b"a 1\nk 2\n")


class BuildJamoNfkdG2pModelTests(unittest.TestCase):
    def test_changes_only_unicode_decomposition_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.zip"
            derived = root / "derived.zip"
            manifest = root / "manifest.json"
            write_source(source)
            source_before = source.read_bytes()

            first = builder.build_derived_model(
                source_model=source,
                derived_model=derived,
                manifest_path=manifest,
            )
            self.assertEqual(first["status"], "success")
            self.assertEqual(source.read_bytes(), source_before)
            self.assertEqual(
                first["change_contract"]["unchanged_member_count"], 2
            )
            with zipfile.ZipFile(derived) as archive:
                meta = json.loads(archive.read("jamo/meta.json"))
                self.assertIs(meta["unicode_decomposition"], True)
                self.assertEqual(
                    archive.read("jamo/model.fst"), b"fst-bytes"
                )
                self.assertEqual(
                    archive.read("jamo/phones.sym"), b"a 1\nk 2\n"
                )

            second = builder.build_derived_model(
                source_model=source,
                derived_model=derived,
                manifest_path=manifest,
            )
            self.assertEqual(
                first["derived_model"]["sha256"],
                second["derived_model"]["sha256"],
            )

    def test_refuses_same_source_and_output_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.zip"
            write_source(source)
            with self.assertRaisesRegex(ValueError, "경로가 같음"):
                builder.build_derived_model(
                    source_model=source,
                    derived_model=source,
                    manifest_path=root / "manifest.json",
                )


if __name__ == "__main__":
    unittest.main()
