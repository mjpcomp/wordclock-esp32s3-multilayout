#!/usr/bin/env python3
"""Publish allow-listed simulated UI evidence, never application sources or images."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import tempfile

REPOSITORY = "mjpcomp/wordclock-esp32s3-multilayout"
SOURCE_BRANCH = "feature/optional-status-prefix"
EVIDENCE_BRANCH = "ci-evidence"
REPORTS = {
    "layout": "layout-evidence/layout-report.json",
    "timeline": "layout-evidence/timeline-responsive.json",
    "actions": "layout-evidence/action-states.json",
    "preview": "layout-evidence/mirc0-preview.json",
    "disabled_fields": "layout-evidence/disabled-fields.json"
}
SOURCE_FILES = ["webpage/script.js", "webpage/index.html", "webpage/style.css", "Gruntfile.js", "webpage/mirc0-preview.js", "webpage/mirc0-preview-page.js"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(root, relative):
    path = root / relative
    if not path.is_file():
        return None
    if not path.resolve().is_relative_to(root.resolve()) or path.stat().st_size > 2_000_000:
        return {"status": "invalid", "error": "Unsafe or oversized evidence: " + relative}
    try:
        value = json.loads(path.read_text())
    except (ValueError, OSError):
        return {"status": "invalid", "error": "Unreadable JSON evidence: " + relative}
    if not isinstance(value, dict):
        return {"status": "invalid", "error": "Evidence object required: " + relative}
    return value


def report_summary(data):
    if data is None:
        return {"status": "missing"}
    result = {"status": data.get("status", "not-reported"), "scope": data.get("scope", ""), "captures": []}
    if data.get("error"):
        result["error"] = str(data["error"]).splitlines()[0][:400]
    for item in data.get("measurements", []):
        row = {key: item[key] for key in ["width", "viewport", "phase", "label", "overflow", "status"] if key in item}
        if "documentClient" in item:
            row["overflow"] = item["documentScroll"] > item["documentClient"]
        if "letters" in item:
            letters = item["letters"]
            row.update(letters=len(letters), lit=sum(bool(t.get("lit")) for t in letters), minimum_font_px=min((t["fontPx"] for t in letters), default=None))
            row["computed_unlit_colours"] = sorted({t.get("computedFill", "not-recorded") for t in letters if not t.get("lit")})
        if "fields" in item:
            row["fields"] = item["fields"]
        if "buttons" in item:
            row["buttons"] = [{k: b[k] for k in ["name", "disabled", "hidden", "height", "color", "background", "opacity"] if k in b} for b in item["buttons"]]
        result["captures"].append(row)
    result["sessions"] = len(data.get("sessions", []))
    result["errors"] = data.get("errors", [])
    result["blocked"] = data.get("blocked", [])
    if "peer" in data:
        peer = data["peer"]
        result["peer"] = {"connections": peer.get("connections"), "errors": peer.get("errors", []), "scheduler_actions": [r.get("action") for r in peer.get("requests", [])]}
    if "intentionalLegacyColourWrites" in data:
        result["intentional_mock_colour_writes"] = len(data["intentionalLegacyColourWrites"])
    return result


def build_bundle(root, meta):
    reports = {name: read_json(root, path) for name, path in REPORTS.items()}
    manifest = read_json(root, "compact-layout-evidence/preview-source.json")
    review = {"schema": 1, **meta, "visual_review": "User sign-off required; screenshots remain in Actions.", "reports": {name: report_summary(data) for name, data in reports.items()}, "source_checks": {}}
    if manifest:
        for name in SOURCE_FILES:
            entry = manifest.get("files", {}).get(name, {})
            artifact = entry.get("artifact", "")
            path = root / "compact-layout-evidence" / artifact
            valid = bool(artifact and Path(artifact).name == artifact and path.is_file() and path.resolve().is_relative_to(root.resolve()) and path.stat().st_size <= 2_000_000)
            review["source_checks"][name] = bool(valid and digest(path.read_bytes()) == entry.get("sha256"))
    wanted = {name: "PASS" for name in REPORTS}
    wanted["layout"] = "PASS_DIAGNOSTICS_ONLY"
    complete = manifest is not None and len(review["source_checks"]) == len(SOURCE_FILES) and all(review["source_checks"].values())
    complete = complete and all(reports[name] is not None and reports[name].get("status") == status and bool(reports[name].get("measurements")) for name, status in wanted.items())
    review["status"] = "PASS" if complete and meta["candidate_result"] == "success" and meta["final_checks"] == "success" and meta["final_build"] == "success" and meta["download_result"] == "success" else "NOT_VERIFIED"
    bundle = {"review.json": review}
    if manifest:
        bundle["preview-source.json"] = manifest
    for name, data in reports.items():
        if data is not None:
            bundle["reports/" + name + ".json"] = data
    baseline = read_json(root, "compact-layout-evidence/baseline-layout-report.json")
    if baseline:
        bundle["reports/baseline-layout.json"] = baseline
    for name in ["timeline-source.json", "action-state-source.json"]:
        data = read_json(root, "compact-layout-evidence/" + name)
        if data:
            bundle[name] = data
    return bundle


def git(folder, args, env=None):
    return subprocess.check_output(["git", "-C", str(folder), *args], text=True, stderr=subprocess.PIPE, env=env).strip()


def commit_json(folder, relative, value, message):
    target = folder / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2) + "\n")
    git(folder, ["add", "--", relative])
    git(folder, ["commit", "-m", message])
    return git(folder, ["rev-parse", "HEAD"])


def write_bundle(folder, bundle, meta, update_latest):
    prefix = "runs/" + meta["run_id"] + "-" + meta["attempt"]
    review_path = prefix + "/review.json"
    commits = {}
    for relative, value in bundle.items():
        path = prefix + "/" + relative
        if (folder / path).exists():
            raise ValueError("Evidence run already exists: " + prefix)
        commits[relative] = commit_json(folder, path, value, "ci: record UI evidence " + meta["run_id"] + " " + relative)
    if update_latest:
        index = {"schema": 1, "source_sha": meta["source_sha"], "run_id": meta["run_id"], "attempt": meta["attempt"], "status": bundle["review.json"]["status"], "review_path": review_path, "review_commit": commits["review.json"], "run_url": meta["run_url"], "artifact_name": meta.get("artifact_name", "not-reported"), "file_commits": commits}
        if "preview-source.json" in commits:
            index.update(manifest_path=prefix + "/preview-source.json", manifest_commit=commits["preview-source.json"])
        commit_json(folder, "latest.json", index, "ci: update latest UI evidence pointer")
    return commits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    env = os.environ
    if env.get("GITHUB_REPOSITORY") != REPOSITORY or env.get("GITHUB_REF_NAME") != SOURCE_BRANCH or env.get("GITHUB_EVENT_NAME") != "push":
        raise SystemExit("Refusing evidence publication outside the approved repository/branch/push event")
    sha = env["GITHUB_SHA"]
    run_id, attempt = env["GITHUB_RUN_ID"], env["GITHUB_RUN_ATTEMPT"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not run_id.isdecimal() or not attempt.isdecimal():
        raise SystemExit("Invalid source/run identity")
    meta = {"repository": REPOSITORY, "source_branch": SOURCE_BRANCH, "source_sha": sha, "run_id": run_id, "attempt": attempt,
            "run_url": "https://github.com/" + REPOSITORY + "/actions/runs/" + run_id,
            "artifact_name": env.get("CANDIDATE_ARTIFACT_NAME", ""), "artifact_attempt": env.get("CANDIDATE_ATTEMPT", ""), "candidate_result": env.get("CANDIDATE_RESULT", "not-reported"),
            "baseline_gates": env.get("BASELINE_RESULT", "not-reported"), "final_build": env.get("FINAL_BUILD_RESULT", "not-reported"),
            "final_checks": env.get("FINAL_CHECKS_RESULT", "not-reported"), "download_result": env.get("DOWNLOAD_RESULT", "not-reported")}
    bundle = build_bundle(Path(args.input), meta)
    origin = git(Path.cwd(), ["remote", "get-url", "origin"])
    expected = "https://github.com/" + REPOSITORY
    if origin not in [expected, expected + ".git"] or git(Path.cwd(), ["rev-parse", "HEAD"]) != sha:
        raise SystemExit("Refusing unexpected checkout or remote")
    auth = dict(env)
    auth.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                GIT_CONFIG_VALUE_0="AUTHORIZATION: basic " + base64.b64encode(("x-access-token:" + env["GH_TOKEN"]).encode()).decode())
    with tempfile.TemporaryDirectory() as temp:
        target = Path(temp)
        git(target, ["init", "--initial-branch=" + EVIDENCE_BRANCH])
        git(target, ["remote", "add", "origin", origin])
        remote = git(target, ["ls-remote", "origin", "refs/heads/" + EVIDENCE_BRANCH], auth)
        if remote:
            git(target, ["fetch", "--depth=1", "origin", "refs/heads/" + EVIDENCE_BRANCH], auth)
            git(target, ["checkout", "-B", EVIDENCE_BRANCH, "FETCH_HEAD"])
        git(target, ["config", "user.name", "github-actions[bot]"])
        git(target, ["config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
        current = git(target, ["ls-remote", "origin", "refs/heads/" + SOURCE_BRANCH], auth).split()
        write_bundle(target, bundle, meta, bool(current and current[0] == sha))
        git(target, ["push", "origin", "HEAD:refs/heads/" + EVIDENCE_BRANCH], auth)
        print(json.dumps({"branch": EVIDENCE_BRANCH, "source_sha": sha, "status": bundle["review.json"]["status"]}))


if __name__ == "__main__":
    main()
