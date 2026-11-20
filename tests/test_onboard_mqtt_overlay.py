#!/usr/bin/env python3
"""Host-only overlay transformation tests; no SDK, downloads or firmware runs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mqtt_overlay", ROOT / "tools/onboard_mqtt_overlay.py")
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)

FIXTURE = ('/* fixture: not a complete MQTT library */\n'
           '#include "PubSubClient.h"\n#include "Arduino.h"\n' +
           ''.join(anchor + '}\n' for anchor, _ in overlay.PATCHES))

class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "installed" / "PubSubClient.cpp"
        self.source.parent.mkdir()
        self.source.write_text(FIXTURE, encoding="utf-8")
        (self.source.parent / "PubSubClient.h").write_text("// fixture header\n", encoding="utf-8")
        self.build = self.root / "build"

    def generate_fixture(self, profile="YD_ESP32S3_N16R8_BOARD_ONLY"):
        with patch.object(overlay, "EXPECTED_BLOB", overlay.git_blob(self.source.read_bytes())):
            return overlay.prepare(self.source, self.build, profile)

    def test_production_reference_is_fixed(self):
        self.assertEqual(overlay.EXPECTED_BLOB, "2b48d2b6b8ff28f5be7ad46a06c2e4f3f389aeae")
        with self.assertRaisesRegex(ValueError, "Unverified"):
            overlay.prepare(self.source, self.build, "YD_ESP32S3_N16R8_BOARD_ONLY")
        self.assertFalse(self.build.exists())

    def test_normal_profiles_do_not_read_or_write(self):
        for profile in ("ESP8266", "ESP32", "ESP32C3", "YD_ESP32S3_N16R8"):
            missing = self.root / "missing.cpp"
            self.assertEqual(overlay.prepare(missing, self.build, profile), missing)
        self.assertFalse(self.build.exists())

    def test_two_isolated_profiles_and_exact_guard_positions(self):
        original = self.source.read_bytes()
        for profile in sorted(overlay.PROFILES):
            target = self.generate_fixture(profile)
            text = target.read_text(encoding="utf-8")
            self.assertEqual(sum(line.strip() == overlay.HOOK for line in text.splitlines()), 3)
            for anchor, addition in overlay.PATCHES:
                self.assertIn(anchor + addition, text)
            self.assertTrue(text.startswith('extern "C" void wordclockDiagnosticBeforeNetworkWork();'))
            self.assertIn('/* fixture: not a complete MQTT library */', text)
            header = (self.source.parent / "PubSubClient.h").as_posix()
            self.assertIn('#include "' + header + '"', text)
            manifest = json.loads((target.parent / "manifest.json").read_text())
            self.assertEqual(manifest["profile"], profile)
            self.assertEqual(manifest["guard_insertions"], 3)
            self.assertEqual(manifest["source_git_blob"], overlay.git_blob(original))
            self.assertEqual(self.source.read_bytes(), original)

    def test_repeated_generation_is_deterministic_not_double_patched(self):
        first = self.generate_fixture().read_bytes()
        self.assertEqual(self.generate_fixture().read_bytes(), first)
        self.assertEqual(sum(line.strip() == overlay.HOOK for line in first.decode().splitlines()), 3)

    def test_missing_and_duplicate_anchors_rejected(self):
        for anchor, _ in overlay.PATCHES:
            for text in (FIXTURE.replace(anchor, ""), FIXTURE + anchor):
                self.source.write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "exactly once"):
                    self.generate_fixture()
        self.assertFalse(self.build.exists())

    def test_include_errors_rejected(self):
        self.source.write_text(FIXTURE.replace('#include "PubSubClient.h"', ''), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "include"):
            self.generate_fixture()
        self.assertFalse(self.build.exists())

    def test_installed_tree_is_not_output_directory(self):
        for directory in (self.source.parent, self.root):
            with patch.object(overlay, "EXPECTED_BLOB", overlay.git_blob(self.source.read_bytes())):
                with self.assertRaisesRegex(ValueError, "installed source"):
                    overlay.prepare(self.source, directory, "YD_ESP32S3_N16R8_BOARD_ONLY")

if __name__ == "__main__":
    unittest.main()
