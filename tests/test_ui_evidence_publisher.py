#!/usr/bin/env python3
"""Evidence summary and local-Git tests. No GitHub token or network is used."""
from pathlib import Path
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publisher", ROOT / "tools/publish_ui_evidence.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def main():
    meta = {"source_sha": "a" * 40, "run_id": "123", "attempt": "1", "run_url": "fixture", "candidate_result": "success", "final_checks": "success", "final_build": "success", "download_result": "success"}
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        empty = publisher.build_bundle(root, meta)
        assert empty["review.json"]["status"] == "NOT_VERIFIED"
        assert all(r["status"] == "missing" for r in empty["review.json"]["reports"].values())
        (root / "broken.json").write_text("{")
        assert publisher.read_json(root, "broken.json")["status"] == "invalid"
        evidence = root / "compact-layout-evidence"
        evidence.mkdir()
        manifest = {"files": {}}
        for number, name in enumerate(publisher.SOURCE_FILES):
            artifact = "preview-" + Path(name).name
            data = (name + str(number)).encode()
            (evidence / artifact).write_bytes(data)
            manifest["files"][name] = {"artifact": artifact, "sha256": publisher.digest(data)}
        (evidence / "preview-source.json").write_text(json.dumps(manifest))
        for name, path in publisher.REPORTS.items():
            target = root / path
            target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps({"status": "PASS_DIAGNOSTICS_ONLY" if name == "layout" else "PASS", "measurements": [{}]}))
        good = publisher.build_bundle(root, meta)
        assert good["review.json"]["status"] == "PASS"
        assert all(name.endswith(".json") for name in good)
        failed = publisher.build_bundle(root, {**meta, "candidate_result": "failure"})
        assert failed["review.json"]["status"] == "NOT_VERIFIED"
        (evidence / "preview-style.css").write_text("tampered")
        assert publisher.build_bundle(root, meta)["review.json"]["status"] == "NOT_VERIFIED"
        repo = root / "repo"
        repo.mkdir()
        publisher.git(repo, ["init", "--initial-branch=ci-evidence"])
        publisher.git(repo, ["config", "user.name", "Fixture"])
        publisher.git(repo, ["config", "user.email", "fixture@example.invalid"])
        commits = publisher.write_bundle(repo, good, meta, True)
        index = json.loads((repo / "latest.json").read_text())
        assert index["review_commit"] == commits["review.json"]
        restored = json.loads(publisher.git(repo, ["show", index["review_commit"] + ":" + index["review_path"]]))
        assert restored["source_sha"] == "a" * 40 and restored["status"] == "PASS"
        assert publisher.git(repo, ["show", "--format=", "--name-only", "HEAD"]) == "latest.json"
        publisher.write_bundle(repo, good, {**meta, "run_id": "124"}, False)
        assert json.loads((repo / "latest.json").read_text())["run_id"] == "123"
    print(json.dumps({"status": "PASS", "scope": "summary completeness, failure/missing evidence, hashes and local-Git diff retrieval"}))


if __name__ == "__main__":
    main()
