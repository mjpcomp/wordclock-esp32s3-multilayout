#!/usr/bin/env python3
"""Offline activation promotion guards and local-Git preparation; no network."""
import copy
import hashlib
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
spec = importlib.util.spec_from_file_location("promotion", ROOT / "tools/prepare_reviewed_preview_activation.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def init_repo(root):
    subprocess.run(["git", "init", "--initial-branch=fixture", str(root)], check=True, capture_output=True)
    p.storage.git(root, ["config", "user.name", "Fixture"])
    p.storage.git(root, ["config", "user.email", "fixture@example.invalid"])
    for name in p.HASHES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("original")
    p.storage.git(root, ["add", "--", *sorted(p.HASHES)])
    p.storage.git(root, ["commit", "-m", "fixture base"])
    base = p.storage.git(root, ["rev-parse", "HEAD"])
    (root / "tools").mkdir(exist_ok=True)
    name = sorted(p.CONFIG)[0]
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("configuration")
    p.storage.git(root, ["add", "--", name])
    p.storage.git(root, ["commit", "-m", "fixture configuration"])
    return base, p.storage.git(root, ["rev-parse", "HEAD"])


class PromotionGuards(unittest.TestCase):
    def test_review_identity_and_complete_gate_set(self):
        review = {"repository": p.REPO, "source_branch": p.SOURCE, "source_sha": p.REVIEWED, "run_id": p.RUN, "attempt": "1", "status": "PASS", "errors": [], "checks": dict.fromkeys(p.CHECKS, True)}
        review.update(dict.fromkeys(["candidate_result", "build_result", "checks_result", "upload_result", "download_result"], "success"))
        manifest = {"files": {name: {"base_sha256": p.activation.EXPECTED[name], "candidate_sha256": value} for name, value in p.HASHES.items()}}
        text = "fixture diff"
        diff = {"format": "unified-diff", "sha256": p.digest(text.encode()), "text": text}
        with patch.object(p, "DIFF_SHA", diff["sha256"]):
            p.verify_evidence(review, manifest, diff)
            for key in ["source_sha", "run_id", "status", "candidate_result"]:
                with self.assertRaises(ValueError):
                    p.verify_evidence({**review, key: "wrong"}, manifest, diff)
            changed = copy.deepcopy(review)
            changed["checks"].pop(next(iter(p.CHECKS)))
            with self.assertRaises(ValueError):
                p.verify_evidence(changed, manifest, diff)
            with self.assertRaises(ValueError):
                p.verify_evidence(review, {"files": {}}, diff)
            with self.assertRaises(ValueError):
                p.verify_evidence(review, manifest, {**diff, "text": "tampered"})

    def test_source_hash_and_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "value"
            target.write_bytes(b"approved")
            with patch.object(p, "HASHES", {"value": p.digest(b"approved")}):
                p.verify_files(root)
                target.write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    p.verify_files(root)
                target.unlink()
                target.symlink_to(root / "missing")
                with self.assertRaises(ValueError):
                    p.verify_files(root)

    def test_context_and_target(self):
        sha = "a" * 40
        env = {"GITHUB_REPOSITORY": p.REPO, "GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/" + p.SOURCE, "GITHUB_SHA": sha}
        with patch.dict(os.environ, env, clear=True):
            p.guard_context(sha, p.TARGET)
            with self.assertRaises(ValueError):
                p.guard_context(sha, "main")
            for key in env:
                with patch.dict(os.environ, {key: "wrong"}):
                    with self.assertRaises(ValueError):
                        p.guard_context(sha, p.TARGET)

    def test_clean_config_with_real_local_git(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base, sha = init_repo(root)
            with patch.object(p, "REVIEWED", base):
                p.clean_config(root, sha)
                (root / "webpage/script.js").write_text("unreviewed")
                p.storage.git(root, ["add", "--", "webpage/script.js"])
                p.storage.git(root, ["commit", "-m", "unreviewed fixture change"])
                current = p.storage.git(root, ["rev-parse", "HEAD"])
                with self.assertRaisesRegex(ValueError, "outside reviewed"):
                    p.clean_config(root, current)

    def test_bundle_tampering_before_remote(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder)
            (bundle / "receipt.json").write_text("{}")
            with patch.object(p, "guard_context"), patch.object(p, "clean_config"), patch.object(p.storage, "git") as git:
                with self.assertRaisesRegex(ValueError, "receipt differs"):
                    p.prepare(ROOT, "a" * 40, bundle, p.TARGET)
                git.assert_not_called()
                (bundle / "receipt.json").write_text(json.dumps(p.receipt("a" * 40)))
                (bundle / "extra").write_text("unreviewed")
                with self.assertRaisesRegex(ValueError, "bundle paths"):
                    p.prepare(ROOT, "a" * 40, bundle, p.TARGET)
                git.assert_not_called()

    def test_existing_target_branch_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder)
            with patch.object(p, "HASHES", {}), patch.object(p, "guard_context"), patch.object(p, "clean_config"), patch.object(p, "auth_env", return_value={}):
                (bundle / "receipt.json").write_text(json.dumps(p.receipt("a" * 40)))
                with patch.object(p.storage, "git", side_effect=["https://github.com/" + p.REPO, "existing-target"]) as git:
                    with self.assertRaisesRegex(ValueError, "branch exists"):
                        p.prepare(ROOT, "a" * 40, bundle, p.TARGET)
                    self.assertEqual(git.call_count, 2)

    def test_workflow_permissions_and_gate(self):
        text = (ROOT / ".github/workflows/prepare-reviewed-preview-activation.yml").read_text()
        verifier, writer = text.split("\n  prepare:\n")
        self.assertIn("permissions:\n  contents: read", verifier)
        self.assertNotIn("contents: write", verifier)
        self.assertEqual(writer.count("contents: write"), 1)
        self.assertIn("needs: verify", writer)
        self.assertIn("--target " + p.TARGET, writer)
        self.assertNotIn("pull-requests: write", text)
        self.assertNotIn("actions: write", text)

    def test_preparation_exact_local_commits_and_create_only_push(self):
        with tempfile.TemporaryDirectory() as checkout, tempfile.TemporaryDirectory() as artifact:
            root, bundle = Path(checkout), Path(artifact)
            base, sha = init_repo(root)
            p.storage.git(root, ["remote", "add", "origin", "https://github.com/" + p.REPO])
            values = {name: ("approved " + name).encode() for name in p.HASHES}
            hashes = {name: p.digest(value) for name, value in values.items()}
            for name, value in values.items():
                target = bundle / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(value)
            original_git = p.storage.git
            pushes = []
            def local_git(folder, args, env=None):
                if args[0] == "ls-remote":
                    return sha + "\trefs/heads/" + p.SOURCE if args[-1] == "refs/heads/" + p.SOURCE else ""
                if args[0] == "push":
                    pushes.append(args)
                    return ""
                return original_git(folder, args, env)
            with patch.object(p, "REVIEWED", base), patch.object(p, "HASHES", hashes), patch.object(p, "guard_context"), patch.object(p, "auth_env", return_value={}), patch.object(p.storage, "git", side_effect=local_git):
                (bundle / "receipt.json").write_text(json.dumps(p.receipt(sha)))
                result = p.prepare(root, sha, bundle, p.TARGET)
                self.assertEqual(result["status"], "PREPARED_NOT_MERGED")
                self.assertEqual(original_git(root, ["rev-list", "--count", sha + "..HEAD"]), "4")
                self.assertEqual(set(original_git(root, ["diff", "--name-only", sha, "HEAD"]).splitlines()), set(values) | {p.MARKER})
                self.assertEqual(pushes, [["push", "--force-with-lease=refs/heads/" + p.TARGET + ":", "origin", "HEAD:refs/heads/" + p.TARGET]])


if __name__ == "__main__":
    unittest.main()
