#!/usr/bin/env python3
"""Offline bundle and local Git publication guards; no GitHub/network operations."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("publisher", ROOT / "tools/publish_preview_activation_evidence.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def fixture(root):
    meta = {"source_sha": "a" * 40, "run_id": "12", "attempt": "1", "run_url": "fixture://run/12", "artifact_name": p.identity("a" * 40, "12", "1"), "candidate_result": "success", "build_result": "success", "checks_result": "success", "upload_result": "success", "download_result": "success"}
    proof = ({"scope": "fixture only", "files": {"webpage/script.js": {"candidate_sha256": "b" * 64}}}, "--- a/webpage/script.js\n+++ b/webpage/script.js\n@@ -1 +1 @@\n-old\n+new\n")
    values = {"activation-source.json": proof[0], "simulation-browser.json": {"status": "PASS", "errors": [], "blocked": [], "mutations": [], "sessions": [{"width": width, "overflow": False, "logicalCells": 114, "peerConnections": 1, "schedulerActions": ["get"]} for width in [320, 480, 768, 1024, 1440]]}, "layout.json": {"status": "PASS_DIAGNOSTICS_ONLY", "measurements": [{"documentScroll": 320, "documentClient": 320} for _ in range(45)]}, "preview.json": {"status": "PASS"}}
    for name, value in values.items():
        target = root / p.REPORTS[name]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value))
    (root / "preview-activation-evidence/activation.diff").write_text(proof[1])
    return meta, proof


class EvidenceGuards(unittest.TestCase):
    def test_complete_bundle_and_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            meta, proof = fixture(root)
            (root / "secret.txt").write_text("must not publish")
            bundle = p.build_bundle(root, meta, proof)
            self.assertEqual(bundle["review.json"]["status"], "PASS")
            self.assertEqual(set(bundle), p.NAMES)
            self.assertNotIn("secret.txt", json.dumps(bundle))
            self.assertEqual(bundle["activation-diff.json"]["text"], proof[1])

    def test_every_metadata_gate_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            meta, proof = fixture(root)
            for key in ["artifact_name", "candidate_result", "build_result", "checks_result", "upload_result", "download_result"]:
                changed = {**meta, key: "wrong"}
                self.assertEqual(p.build_bundle(root, changed, proof)["review.json"]["status"], "NOT_VERIFIED", key)

    def test_missing_and_altered_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            meta, proof = fixture(root)
            target = root / p.REPORTS["activation-source.json"]
            target.write_text("{}")
            self.assertFalse(p.build_bundle(root, meta, proof)["review.json"]["checks"]["source_manifest"])
            fixture(root)
            (root / "preview-activation-evidence/activation.diff").write_text("different")
            self.assertEqual(p.build_bundle(root, meta, proof)["review.json"]["status"], "NOT_VERIFIED")
            fixture(root)
            (root / p.REPORTS["simulation-browser.json"]).unlink()
            self.assertEqual(p.build_bundle(root, meta, proof)["review.json"]["status"], "NOT_VERIFIED")

    def test_simulation_failures_and_malformed_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            meta, proof = fixture(root)
            target = root / p.REPORTS["simulation-browser.json"]
            initial = json.loads(target.read_text())
            values = [{**initial, "mutations": ["unexpected write"]}, {**initial, "sessions": []}, {**initial, "errors": ["browser failure"]}, {**initial, "sessions": [{"width": []}] * 5}]
            for value in values:
                target.write_text(json.dumps(value))
                self.assertEqual(p.build_bundle(root, meta, proof)["review.json"]["status"], "NOT_VERIFIED")

    def test_identity_and_input_guards(self):
        for sha, run_id, attempt in [("HEAD", "12", "1"), ("a" * 40, "../12", "1"), ("a" * 40, "12", "0")]:
            with self.assertRaises(ValueError):
                p.identity(sha, run_id, attempt)
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as outside:
            root = Path(folder)
            (Path(outside) / "value").write_text("secret")
            (root / "escape").symlink_to(Path(outside) / "value")
            with self.assertRaises(ValueError):
                p.read_text(root, "escape")
            (root / "large").write_text("x" * 2_000_001)
            with self.assertRaises(ValueError):
                p.read_text(root, "large")

    def test_local_git_namespaces_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as evidence, tempfile.TemporaryDirectory() as inputs:
            folder = Path(evidence)
            subprocess.run(["git", "init", "--initial-branch=ci-evidence", str(folder)], check=True, capture_output=True)
            p.storage.git(folder, ["config", "user.name", "Fixture"])
            p.storage.git(folder, ["config", "user.email", "fixture@example.invalid"])
            p.storage.commit_json(folder, "latest.json", {"old": "unchanged"}, "fixture")
            meta, proof = fixture(Path(inputs))
            bundle = p.build_bundle(Path(inputs), meta, proof)
            commits = p.write_bundle(folder, bundle, meta, True)
            self.assertEqual(set(commits), p.NAMES)
            self.assertEqual(json.loads((folder / "latest.json").read_text()), {"old": "unchanged"})
            pointer = json.loads((folder / "activation-latest.json").read_text())
            self.assertEqual(pointer["file_commits"], commits)
            self.assertTrue(all(len(value) == 40 for value in commits.values()))
            paths = p.storage.git(folder, ["ls-files"]).splitlines()
            self.assertTrue(all(name == "latest.json" or name == "activation-latest.json" or name.startswith("activation-runs/12-1/") for name in paths))
            with self.assertRaises(ValueError):
                p.write_bundle(folder, bundle, meta, True)
            with self.assertRaises(ValueError):
                p.write_bundle(folder, {**bundle, "../bad.json": {}}, meta, False)

    def test_symlink_destination_rejected(self):
        with tempfile.TemporaryDirectory() as evidence, tempfile.TemporaryDirectory() as outside:
            folder = Path(evidence)
            (folder / "activation-runs").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                p.safe_target(folder, "activation-runs/12-1/review.json")

    def test_wrong_publication_context_before_git(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "wrong"}, clear=True), patch.object(sys, "argv", ["publisher", "--input", "missing"]), patch.object(p.storage, "git") as git:
            with self.assertRaises(ValueError):
                p.main()
            git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
