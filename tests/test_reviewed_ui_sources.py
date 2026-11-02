#!/usr/bin/env python3
"""Offline guard tests; no network, branch write, or hardware access."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("promotion", ROOT / "tools/promote_reviewed_ui_sources.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class Guards(unittest.TestCase):
    def test_manifest_merge_preserves_final_hashes(self):
        preview = {"files": {name: {"sha256": value} for name, value in p.EXPECTED.items() if name not in ["webpage/schedule-timeline-view.js", "webpage/schedule-page-binding.js"]}}
        timeline = {"candidate_sha256": p.EXPECTED["webpage/schedule-timeline-view.js"]}
        actions = {"unchanged_renderer_sha256": timeline["candidate_sha256"], "files": {"webpage/schedule-page-binding.js": {"sha256": p.EXPECTED["webpage/schedule-page-binding.js"]}, "webpage/style.css": {"sha256": "intermediate"}}}
        self.assertEqual(p.manifest_hashes(preview, timeline, actions), p.EXPECTED)
        actions["unchanged_renderer_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            p.manifest_hashes(preview, timeline, actions)
        actions["unchanged_renderer_sha256"] = timeline["candidate_sha256"]
        preview["files"]["extra"] = {"sha256": "wrong"}
        with self.assertRaises(ValueError):
            p.manifest_hashes(preview, timeline, actions)

    def test_file_hash_and_symlink_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            file = root / "source"
            file.write_bytes(b"reviewed")
            expected = {"source": p.digest(file)}
            with patch.object(p, "EXPECTED", expected):
                p.verify_files(root)
                file.write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    p.verify_files(root)
                file.unlink()
                file.symlink_to(root / "missing")
                with self.assertRaises(ValueError):
                    p.verify_files(root)

    def test_event_ref_sha_target_guards(self):
        sha = "a" * 40
        env = {"GITHUB_REPOSITORY": p.REPO, "GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/" + p.SOURCE, "GITHUB_SHA": sha}
        with patch.dict(os.environ, env, clear=True):
            p.guard_context(sha, p.TARGET)
            with self.assertRaises(ValueError):
                p.guard_context(sha, "main")
            for name in env:
                with patch.dict(os.environ, {name: "wrong"}):
                    with self.assertRaises(ValueError):
                        p.guard_context(sha, p.TARGET)

    def test_authenticated_helper_accepts_env(self):
        with patch.dict(os.environ, {"GH_TOKEN": "test-only"}, clear=True):
            env = p.auth_env()
        self.assertNotIn("GH_TOKEN", env)
        self.assertEqual(env["GIT_CONFIG_COUNT"], "1")
        with patch.object(subprocess, "check_output", return_value="ok\n") as call:
            self.assertEqual(p.git(ROOT, ["status"], env), "ok")
            self.assertIs(call.call_args.kwargs["env"], env)

    def test_existing_target_ref_is_rejected_before_changes(self):
        sha = "a" * 40
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder)
            (bundle / "receipt.json").write_text(json.dumps(p.checkpoint(sha)))
            with patch.object(p, "EXPECTED", {}), patch.object(p, "guard_context"), patch.object(p, "clean_base"), patch.object(p, "auth_env", return_value={}):
                (bundle / "receipt.json").write_text(json.dumps(p.checkpoint(sha)))
                with patch.object(p, "git", side_effect=["https://github.com/" + p.REPO, "existing-ref"]) as call:
                    with self.assertRaisesRegex(ValueError, "Target branch exists"):
                        p.prepare(ROOT, sha, bundle, p.TARGET)
                    self.assertEqual(call.call_count, 2)

    def test_unreviewed_config_paths_and_sha_are_rejected(self):
        sha = "a" * 40
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            with patch.object(p, "git", side_effect=[sha, "", "webpage/style.css"]):
                with self.assertRaisesRegex(ValueError, "Unreviewed changes"):
                    p.clean_base(base, sha)
            with patch.object(p, "git", return_value="b" * 40):
                with self.assertRaisesRegex(ValueError, "Configuration checkout differs"):
                    p.clean_base(base, sha)
            with self.assertRaisesRegex(ValueError, "Invalid configuration SHA"):
                p.clean_base(base, "HEAD")

    def test_bundle_receipt_and_extra_paths_fail_before_network(self):
        sha = "a" * 40
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder)
            (bundle / "receipt.json").write_text("{}")
            with patch.object(p, "guard_context"), patch.object(p, "clean_base"), patch.object(p, "git") as call:
                with self.assertRaisesRegex(ValueError, "Bundle receipt differs"):
                    p.prepare(ROOT, sha, bundle, p.TARGET)
                call.assert_not_called()
                (bundle / "receipt.json").write_text(json.dumps(p.checkpoint(sha)))
                (bundle / "extra.txt").write_text("unapproved")
                with self.assertRaisesRegex(ValueError, "Unexpected bundle files"):
                    p.prepare(ROOT, sha, bundle, p.TARGET)
                call.assert_not_called()

    def test_workflow_permission_and_checkout_contract(self):
        text = (ROOT / ".github/workflows/prepare-reviewed-ui-promotion.yml").read_text()
        sections = text.split("\n  prepare:\n")
        self.assertEqual(len(sections), 2)
        verify, tail = sections
        prepare, validate = tail.split("\n  validate:\n")
        self.assertNotIn("contents: write", verify)
        self.assertEqual(prepare.count("contents: write"), 1)
        self.assertNotIn("contents: write", validate)
        self.assertIn("needs: verify", prepare)
        self.assertIn("needs: prepare", validate)
        self.assertIn("ref: ${{ needs.prepare.outputs.head }}", validate)
        for forbidden in ["actions: write", "workflow_dispatch", "pull-requests: write", "path: .github/workflows/ui-source-validation.yml"]:
            self.assertNotIn(forbidden, text)
        retired = (ROOT / ".github/workflows/prepare-reviewed-ui-branch.yml").read_text()
        self.assertIn("if: ${{ false }}", retired)
        self.assertNotIn("contents: write", retired)


if __name__ == "__main__":
    unittest.main()
