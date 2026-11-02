#!/usr/bin/env python3
"""Offline checks for one-shot pinned activation patches; no network or git writes."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("activation", ROOT / "tools/prepare_preview_simulation_activation.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ActivationGuards(unittest.TestCase):
    def test_replace_requires_unique_anchor(self):
        self.assertEqual(p.replace_once("a:b", ":", "!"), "a!b")
        for value in ["absent", "::"]:
            with self.assertRaises(ValueError):
                p.replace_once(value, ":", "!")

    def test_hash_failure_does_not_change_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "webpage").mkdir()
            for name in p.EXPECTED:
                (root / name).write_text("unreviewed")
            before = {name: (root / name).read_bytes() for name in p.EXPECTED}
            with self.assertRaisesRegex(ValueError, "Pinned activation base differs"):
                p.apply(root)
            self.assertEqual(before, {name: (root / name).read_bytes() for name in p.EXPECTED})

    def test_fixture_patch_and_double_application(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "webpage").mkdir()
            data = {"webpage/script.js": p.OLD_INIT, "webpage/index.html": p.SCRIPT_ANCHOR + "\n", "webpage/style.css": "/* fixture */\n"}
            expected = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in data.items()}
            for name, text in data.items():
                (root / name).write_text(text)
            with patch.object(p, "EXPECTED", expected):
                manifest = p.apply(root)
                self.assertEqual(set(manifest["files"]), set(expected))
                self.assertEqual((root / "webpage/script.js").read_text(), p.NEW_INIT)
                self.assertIn("mirc0-preview-playback.js", (root / "webpage/index.html").read_text())
                self.assertTrue((root / "webpage/style.css").read_text().endswith(p.CSS))
                with self.assertRaises(ValueError):
                    p.apply(root)

    def test_missing_anchor_does_not_partially_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "webpage").mkdir()
            data = {"webpage/script.js": p.OLD_INIT, "webpage/index.html": "missing", "webpage/style.css": "/* fixture */\n"}
            expected = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in data.items()}
            for name, text in data.items():
                (root / name).write_text(text)
            with patch.object(p, "EXPECTED", expected):
                with self.assertRaises(ValueError):
                    p.apply(root)
            self.assertEqual({name: (root / name).read_text() for name in data}, data)


if __name__ == "__main__":
    unittest.main()
