#!/usr/bin/env python3
"""Prepare only the fixed activation branch from immutable reviewed evidence."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re

import prepare_preview_simulation_activation as activation
import publish_ui_evidence as storage

REPO = "mjpcomp/wordclock-esp32s3-multilayout"
SOURCE = "feature/optional-status-prefix"
TARGET = "promotion/preview-simulation-fb0e5359"
REVIEWED = "fb0e53599535b4a4ed6788de2c139d1e010a906b"
RUN = "41524704833"
MARKER = "tools/preview-simulation-checkpoint.json"
HASHES = {
    "webpage/script.js": "1a26301f3802c783aa66871ab0f6251717d6aa7b7ca170708472838813f90b6c",
    "webpage/index.html": "0655e3d2533d41ab5b66c59dfd30829e56ac6b7777eb904ddb6e9d58e7467369",
    "webpage/style.css": "db173399bda9e27a3f596c5bf201c12a0e05726742367df7d5fe77f1c9b8a03c",
}
EVIDENCE = {
    "review": ("8ec46b80144ed070aeeb48f2c604b84fece30f01", "review.json"),
    "manifest": ("f70b4c2f1bcba0d23ce3988fcce2f64915b969ec", "activation-source.json"),
    "diff": ("904b398adf0178294de62dc79144b6075b46e69b", "activation-diff.json"),
}
DIFF_SHA = "1bf0a006c60fa00e755d93d86a0eabafdb0ca21b316a59a6449e9341a2aa291b"
CHECKS = {"artifact_identity", "candidate", "build", "browser_step", "upload", "download", "source_manifest", "diff", "simulation", "layout", "preview"}
CONFIG = {"tools/prepare_reviewed_preview_activation.py", "tests/test_reviewed_preview_activation.py", ".github/workflows/prepare-reviewed-preview-activation.yml"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_files(root):
    for name, expected in HASHES.items():
        path = root / name
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), "Unsafe source: " + name)
        require(digest(path.read_bytes()) == expected, "Reviewed source differs: " + name)


def receipt(config_sha):
    return {"schema": 1, "reviewed_source": REVIEWED, "configuration_sha": config_sha, "review_run": RUN, "review_commit": EVIDENCE["review"][0], "files": HASHES, "scope": "Exact UI activation sources; no firmware or hardware readiness", "visual_review": "Not established by automated evidence"}


def verify_evidence(review, manifest, diff):
    require(review.get("repository") == REPO and review.get("source_branch") == SOURCE and review.get("source_sha") == REVIEWED and review.get("run_id") == RUN and review.get("attempt") == "1", "Review identity differs")
    require(review.get("status") == "PASS" and review.get("errors") == [] and set(review.get("checks", {})) == CHECKS and all(value is True for value in review["checks"].values()), "Review gates incomplete")
    require(all(review.get(key) == "success" for key in ["candidate_result", "build_result", "checks_result", "upload_result", "download_result"]), "Review outcomes incomplete")
    expected = {name: {"base_sha256": activation.EXPECTED[name], "candidate_sha256": value} for name, value in HASHES.items()}
    require(manifest.get("files") == expected, "Reviewed manifest differs")
    require(diff.get("format") == "unified-diff" and diff.get("sha256") == DIFF_SHA and isinstance(diff.get("text"), str) and digest(diff["text"].encode()) == DIFF_SHA, "Reviewed diff differs")


def clean_config(root, config_sha):
    require(re.fullmatch(r"[0-9a-f]{40}", config_sha) is not None, "Invalid configuration SHA")
    require(storage.git(root, ["rev-parse", "HEAD"]) == config_sha, "Configuration checkout differs")
    require(not storage.git(root, ["status", "--porcelain", "--untracked-files=no"]), "Tracked checkout dirty")
    require(not (root / MARKER).exists(), "Activation checkpoint already exists")
    require(set(storage.git(root, ["diff", "--name-only", REVIEWED, config_sha]).splitlines()) <= CONFIG, "Changes outside reviewed preparation configuration")


def auth_env():
    env = dict(os.environ)
    token = env.pop("GH_TOKEN")
    env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader", GIT_CONFIG_VALUE_0="AUTHORIZATION: basic " + base64.b64encode(("x-access-token:" + token).encode()).decode())
    return env


def verify(root, config_sha, bundle):
    clean_config(root, config_sha)
    storage.git(root, ["fetch", "--no-tags", "origin", "ci-evidence"], auth_env())
    evidence = {key: json.loads(storage.git(root, ["show", commit + ":activation-runs/" + RUN + "-1/" + name])) for key, (commit, name) in EVIDENCE.items()}
    verify_evidence(evidence["review"], evidence["manifest"], evidence["diff"])
    manifest = activation.apply(root)
    require(manifest["files"] == evidence["manifest"]["files"], "Reproduced manifest differs")
    require(digest((root / "preview-activation-evidence/activation.diff").read_bytes()) == DIFF_SHA, "Reproduced diff differs")
    verify_files(root)
    require(set(storage.git(root, ["diff", "--name-only"]).splitlines()) == set(HASHES), "Unexpected activation paths")
    require(not bundle.exists(), "Bundle exists")
    bundle.mkdir(parents=True)
    for name in HASHES:
        target = bundle / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / name).read_bytes())
    (bundle / "receipt.json").write_text(json.dumps(receipt(config_sha), sort_keys=True) + "\n")
    return {"status": "EXACT_REVIEWED_SOURCES_VERIFIED", "files": len(HASHES), "configuration_sha": config_sha}


def guard_context(config_sha, target):
    require(target == TARGET, "Unexpected promotion target")
    require(os.environ.get("GITHUB_REPOSITORY") == REPO and os.environ.get("GITHUB_EVENT_NAME") == "push" and os.environ.get("GITHUB_REF") == "refs/heads/" + SOURCE and os.environ.get("GITHUB_SHA") == config_sha, "Unexpected preparation context")


def prepare(root, config_sha, bundle, target):
    guard_context(config_sha, target)
    clean_config(root, config_sha)
    require(json.loads((bundle / "receipt.json").read_text()) == receipt(config_sha), "Bundle receipt differs")
    require({str(path.relative_to(bundle)) for path in bundle.rglob("*") if path.is_file()} == set(HASHES) | {"receipt.json"}, "Unexpected bundle paths")
    verify_files(bundle)
    origin = storage.git(root, ["remote", "get-url", "origin"])
    require(origin in ["https://github.com/" + REPO, "https://github.com/" + REPO + ".git"], "Unexpected origin")
    env = auth_env()
    require(not storage.git(root, ["ls-remote", "origin", "refs/heads/" + TARGET], env), "Promotion branch exists; never overwrite")
    current = storage.git(root, ["ls-remote", "origin", "refs/heads/" + SOURCE], env).split()
    require(bool(current) and current[0] == config_sha, "Working branch advanced")
    storage.git(root, ["switch", "-c", TARGET])
    storage.git(root, ["config", "user.name", "github-actions[bot]"])
    storage.git(root, ["config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    for name in HASHES:
        (root / name).write_bytes((bundle / name).read_bytes())
    verify_files(root)
    require(set(storage.git(root, ["diff", "--name-only"]).splitlines()) == set(HASHES), "Unexpected activation write paths")
    for name in sorted(HASHES):
        storage.git(root, ["add", "--", name])
        storage.git(root, ["commit", "-m", "feat: promote tested preview activation " + name])
    (root / MARKER).write_text(json.dumps(receipt(config_sha), indent=2) + "\n")
    storage.git(root, ["add", "--", MARKER])
    storage.git(root, ["commit", "-m", "test: record reviewed preview activation checkpoint"])
    require(set(storage.git(root, ["diff", "--name-only", config_sha, "HEAD"]).splitlines()) == set(HASHES) | {MARKER}, "Unexpected committed paths")
    current = storage.git(root, ["ls-remote", "origin", "refs/heads/" + SOURCE], env).split()
    require(bool(current) and current[0] == config_sha, "Working branch advanced before push")
    storage.git(root, ["push", "--force-with-lease=refs/heads/" + TARGET + ":", "origin", "HEAD:refs/heads/" + TARGET], env)
    return {"status": "PREPARED_NOT_MERGED", "head": storage.git(root, ["rev-parse", "HEAD"]), "branch": TARGET}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["verify", "prepare"])
    parser.add_argument("--config-sha", required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--target", default=TARGET)
    args = parser.parse_args()
    root, bundle = Path.cwd(), args.bundle.resolve()
    result = verify(root, args.config_sha, bundle) if args.mode == "verify" else prepare(root, args.config_sha, bundle, args.target)
    print(json.dumps(result, sort_keys=True))
