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

import package_hf_korean_mfa_bundle as packager  # noqa: E402


def make_repository(root: Path, *, crlf_symbols: bool = False) -> None:
    (root / ".git" / "refs" / "heads").mkdir(parents=True)
    (root / ".git" / "HEAD").write_text(
        "ref: refs/heads/main\n", encoding="ascii"
    )
    (root / ".git" / "refs" / "heads" / "main").write_text(
        "a" * 40 + "\n", encoding="ascii"
    )
    acoustic = root / "acoustic"
    dictionary = root / "dictionary"
    g2p = root / "g2p" / "korean_mfa"
    acoustic.mkdir()
    dictionary.mkdir()
    g2p.mkdir(parents=True)
    for name in ("final.alimdl", "final.mdl", "lda.mat", "phones.txt", "tree"):
        (acoustic / name).write_bytes(f"{name}\n".encode())
    (acoustic / "meta.json").write_text(
        json.dumps({"version": "3.3.0", "phones": ["a", "k"]}),
        encoding="utf-8",
    )
    (dictionary / "korean_mfa.dict").write_text(
        "가\ta k\n", encoding="utf-8"
    )
    (dictionary / "rules.yaml").write_text("rules: []\n", encoding="utf-8")
    (g2p / "meta.json").write_text(
        json.dumps(
            {
                "version": "3.2.0",
                "phones": ["a", "k"],
                "graphemes": ["ᄀ", "ᅡ"],
                "unicode_decomposition": True,
            }
        ),
        encoding="utf-8",
    )
    newline = b"\r\n" if crlf_symbols else b"\n"
    (g2p / "phones.sym").write_bytes(b"a 1" + newline + b"k 2" + newline)
    (g2p / "graphemes.sym").write_bytes(
        "ᄀ 1".encode() + newline + "ᅡ 2".encode() + newline
    )
    (g2p / "model.fst").write_bytes(b"fst")


class PackageHfKoreanMfaBundleTests(unittest.TestCase):
    def test_builds_idempotent_phone_matched_jamo_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            output = root / "output"
            manifest = root / "manifest.json"
            make_repository(source)
            first = packager.build_bundle(
                hf_root=source,
                output_directory=output,
                manifest_path=manifest,
            )
            second = packager.build_bundle(
                hf_root=source,
                output_directory=output,
                manifest_path=manifest,
            )
            self.assertEqual(first["status"], "success")
            self.assertTrue(
                first["contract"]["acoustic_g2p_phone_inventory_equal"]
            )
            self.assertTrue(first["contract"]["unicode_decomposition"])
            self.assertEqual(
                first["outputs"]["g2p_model"]["sha256"],
                second["outputs"]["g2p_model"]["sha256"],
            )
            acoustic_path = Path(
                first["outputs"]["acoustic_model"]["path"]
            )
            with zipfile.ZipFile(acoustic_path) as archive:
                self.assertIn("korean_mfa/final.mdl", archive.namelist())
                self.assertIn("korean_mfa/rules.yaml", archive.namelist())

    def test_rejects_windows_crlf_symbol_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            make_repository(source, crlf_symbols=True)
            with self.assertRaisesRegex(RuntimeError, "CR/CRLF"):
                packager.build_bundle(
                    hf_root=source,
                    output_directory=root / "output",
                    manifest_path=root / "manifest.json",
                )

    def test_rejects_non_jamo_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            make_repository(source)
            meta_path = source / "g2p" / "korean_mfa" / "meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["unicode_decomposition"] = False
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Jamo"):
                packager.build_bundle(
                    hf_root=source,
                    output_directory=root / "output",
                    manifest_path=root / "manifest.json",
                )


if __name__ == "__main__":
    unittest.main()
