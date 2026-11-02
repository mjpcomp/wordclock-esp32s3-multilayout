#!/usr/bin/env python3
"""Publish activation JSON/diff evidence only, never UI sources or screenshots."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

import prepare_preview_simulation_activation as activation
import publish_ui_evidence as storage

REPOSITORY = "mjpcomp/wordclock-esp32s3-multilayout"
SOURCE = "feature/optional-status-prefix"
TARGET = "ci-evidence"
REPORTS = {
    "activation-source.json": "preview-activation-evidence/activation-source.json",
    "simulation-browser.json": "preview-activation-evidence/simulation-browser.json",
    "layout.json": "layout-evidence/layout-report.json",
    "preview.json": "layout-evidence/mirc0-preview.json",
}
NAMES = set(REPORTS) | {"review.json", "activation-diff.json"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(sha, run_id, attempt):
    require(re.fullmatch(r"[0-9a-f]{40}", sha) is not None, "Invalid source SHA")
    require(all(re.fullmatch(r"[1-9][0-9]{0,24}", value) for value in [run_id, attempt]), "Invalid run identity")
    return "mirc0-activation-candidate-" + sha + "-" + run_id + "-" + attempt


def read_text(root, name):
    path = root / name
    require(path.is_file() and not path.is_symlink(), "Missing/unsafe evidence: " + name)
    require(path.resolve().is_relative_to(root.resolve()) and path.stat().st_size <= 2_000_000, "Oversized or escaped evidence: " + name)
    return path.read_text(encoding="utf-8")


def reproduce(checkout):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for name in activation.EXPECTED:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(checkout / name, target)
        manifest = activation.apply(root)
        diff = (root / "preview-activation-evidence/activation.diff").read_text()
        return manifest, diff


def build_bundle(root, meta, proof):
    expected_name = identity(meta["source_sha"], meta["run_id"], meta["attempt"])
    errors = []
    bundle = {}
    for name, relative in REPORTS.items():
        try:
            value = json.loads(read_text(root, relative))
            require(isinstance(value, dict), "Evidence object required: " + name)
            bundle[name] = value
        except (OSError, ValueError) as error:
            errors.append(str(error))
    try:
        diff = read_text(root, "preview-activation-evidence/activation.diff")
        require(diff == proof[1], "Activation diff differs from reproduced candidate")
        bundle["activation-diff.json"] = {"format": "unified-diff", "sha256": hashlib.sha256(diff.encode()).hexdigest(), "text": diff}
    except (OSError, ValueError) as error:
        errors.append(str(error))
    checks = {"artifact_identity": meta.get("artifact_name") == expected_name, "candidate": meta.get("candidate_result") == "success", "build": meta.get("build_result") == "success", "browser_step": meta.get("checks_result") == "success", "upload": meta.get("upload_result") == "success", "download": meta.get("download_result") == "success"}
    checks["source_manifest"] = bundle.get("activation-source.json") == proof[0]
    checks["diff"] = "activation-diff.json" in bundle
    report = bundle.get("simulation-browser.json", {})
    sessions = report.get("sessions")
    valid_sessions = isinstance(sessions, list) and len(sessions) == 5 and all(isinstance(row, dict) and type(row.get("width")) is int for row in sessions)
    checks["simulation"] = bool(report.get("status") == "PASS" and all(report.get(key) == [] for key in ["errors", "blocked", "mutations"]) and valid_sessions and {row.get("width") for row in sessions} == {320, 480, 768, 1024, 1440} and all(row.get("overflow") is False and row.get("logicalCells") == 114 and row.get("peerConnections") == 1 and isinstance(row.get("schedulerActions"), list) and bool(row["schedulerActions"]) and all(action == "get" for action in row["schedulerActions"]) for row in sessions))
    layout = bundle.get("layout.json", {})
    measurements = layout.get("measurements")
    checks["layout"] = bool(layout.get("status") == "PASS_DIAGNOSTICS_ONLY" and isinstance(measurements, list) and len(measurements) == 45 and all(isinstance(row, dict) and isinstance(row.get("documentScroll"), (int, float)) and isinstance(row.get("documentClient"), (int, float)) and row["documentScroll"] <= row["documentClient"] for row in measurements))
    checks["preview"] = bundle.get("preview.json", {}).get("status") == "PASS"
    review = {"schema": 1, **meta, "scope": "Activation candidate evidence; no UI-source promotion or hardware readiness", "checks": checks, "errors": errors, "visual_review": "Screenshots remain in Actions; visual sign-off is separate", "status": "PASS" if not errors and all(checks.values()) else "NOT_VERIFIED"}
    return {"review.json": review, **bundle}


def safe_target(folder, relative):
    target = folder / relative
    require(target.resolve().is_relative_to(folder.resolve()), "Evidence path escaped checkout")
    for item in [target, *target.parents]:
        if item == folder.parent:
            break
        require(not item.is_symlink(), "Symlink in evidence destination")
    return target


def write_bundle(folder, bundle, meta, update_latest):
    identity(meta["source_sha"], meta["run_id"], meta["attempt"])
    require("review.json" in bundle and set(bundle) <= NAMES, "Unexpected publication files")
    prefix = "activation-runs/" + meta["run_id"] + "-" + meta["attempt"]
    require(not safe_target(folder, prefix).exists(), "Activation evidence already exists; never overwrite")
    safe_target(folder, "activation-latest.json")
    for name in bundle:
        safe_target(folder, prefix + "/" + name)
    commits = {}
    for name, value in bundle.items():
        commits[name] = storage.commit_json(folder, prefix + "/" + name, value, "ci: record activation evidence " + meta["run_id"] + " " + name)
    if update_latest:
        index = {"schema": 1, "source_sha": meta["source_sha"], "run_id": meta["run_id"], "attempt": meta["attempt"], "status": bundle["review.json"]["status"], "run_url": meta["run_url"], "artifact_name": meta["artifact_name"], "review_path": prefix + "/review.json", "review_commit": commits["review.json"], "file_commits": commits}
        storage.commit_json(folder, "activation-latest.json", index, "ci: update latest activation evidence pointer")
    return commits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    env = os.environ
    require(env.get("GITHUB_REPOSITORY") == REPOSITORY and env.get("GITHUB_REF_NAME") == SOURCE and env.get("GITHUB_EVENT_NAME") == "push", "Unexpected publication context")
    sha, run_id = env["GITHUB_SHA"], env["GITHUB_RUN_ID"]
    attempt = env.get("CANDIDATE_ATTEMPT") or env["GITHUB_RUN_ATTEMPT"]
    identity(sha, run_id, attempt)
    checkout = Path.cwd()
    origin = storage.git(checkout, ["remote", "get-url", "origin"])
    require(origin in ["https://github.com/" + REPOSITORY, "https://github.com/" + REPOSITORY + ".git"] and storage.git(checkout, ["rev-parse", "HEAD"]) == sha, "Unexpected publication checkout")
    meta = {"repository": REPOSITORY, "source_branch": SOURCE, "source_sha": sha, "run_id": run_id, "attempt": attempt, "publisher_attempt": env["GITHUB_RUN_ATTEMPT"], "run_url": "https://github.com/" + REPOSITORY + "/actions/runs/" + run_id, "artifact_name": env.get("CANDIDATE_ARTIFACT_NAME", ""), "candidate_result": env.get("CANDIDATE_RESULT", ""), "build_result": env.get("FINAL_BUILD_RESULT", ""), "checks_result": env.get("FINAL_CHECKS_RESULT", ""), "upload_result": env.get("UPLOAD_RESULT", ""), "download_result": env.get("DOWNLOAD_RESULT", "")}
    bundle = build_bundle(args.input, meta, reproduce(checkout))
    auth = dict(env)
    token = auth.pop("GH_TOKEN")
    auth.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader", GIT_CONFIG_VALUE_0="AUTHORIZATION: basic " + base64.b64encode(("x-access-token:" + token).encode()).decode())
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder)
        storage.git(target, ["init", "--initial-branch=" + TARGET])
        storage.git(target, ["remote", "add", "origin", origin])
        require(bool(storage.git(target, ["ls-remote", "origin", "refs/heads/" + TARGET], auth)), "Evidence branch missing")
        storage.git(target, ["fetch", "--depth=1", "origin", "refs/heads/" + TARGET], auth)
        storage.git(target, ["checkout", "-B", TARGET, "FETCH_HEAD"])
        storage.git(target, ["config", "user.name", "github-actions[bot]"])
        storage.git(target, ["config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
        current = storage.git(target, ["ls-remote", "origin", "refs/heads/" + SOURCE], auth).split()
        write_bundle(target, bundle, meta, bool(current and current[0] == sha))
        storage.git(target, ["push", "origin", "HEAD:refs/heads/" + TARGET], auth)
        print(json.dumps({"branch": TARGET, "source_sha": sha, "status": bundle["review.json"]["status"]}))


if __name__ == "__main__":
    main()
