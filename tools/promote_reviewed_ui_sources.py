#!/usr/bin/env python3
"""Reproduce the pinned UI candidate and prepare only its isolated branch."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess

REPO = "mjpcomp/wordclock-esp32s3-multilayout"
SOURCE = "feature/optional-status-prefix"
TARGET = "promotion/reviewed-ui-b598076f"
REVIEWED = "b598076fb48cfccdfe1ac018f6eaa94ffbdb61f8"
RUN = "41094048890"
MARKER = "tools/ui-source-checkpoint.json"
EXPECTED = {
    "webpage/script.js": "cee85d74736c6a0fa949e3dc67aeb7e6e345022eaf8bf5d5c24dc1979147603f",
    "webpage/index.html": "304769437af4fa347fd48a08d12cc8f1e492010003af008f622b6a3664b7fec4",
    "webpage/style.css": "22689a11e2673feb037634c749a29d2aa57f95b3cb0fe9f1101933c1f2e60f01",
    "Gruntfile.js": "84773d760615fc2fb60ace240eae046a9bc06ed0817fba830c5272da215995ec",
    "webpage/mirc0-preview.js": "495494464087eed475bada07be8513235c0af60bf18e49d2d8e48f56a587362d",
    "webpage/mirc0-preview-page.js": "9cb0d73a8b59fc4ab958eb75b61f17c5c8185dd524aef6569eb0dee3e4af6d05",
    "webpage/schedule-timeline-view.js": "9ac27148d665581407853e9c511654fa9491a26f74f9d9fc07e103fb81f3d25d",
    "webpage/schedule-page-binding.js": "1085404f1f46a4f67099094940c40c6d9b2dee67ba567a2d3d6f03acb6a30a4c",
}
GENERATORS = ["prepare_compact_layout.py", "refine_compact_layout_mobile.py", "prepare_responsive_timeline.py", "prepare_schedule_action_states.py", "prepare_mirc0_preview_page.py", "refine_disabled_schedule_fields.py"]
EVIDENCE = {
    "review": ("63d44b5992d484b8e0271d883ebead8e762ba7f7", "review.json"),
    "preview": ("053e28a5a41ec1e91d421e23c86a58a440b8d33d", "preview-source.json"),
    "timeline": ("06923cb3f5926e5bbbf9870c9128db608f32ab1a", "timeline-source.json"),
    "actions": ("3c8946f67769e1564a30a0b96f39e7a38e5410c0", "action-state-source.json"),
}
CONFIG = ["tools/promote_reviewed_ui_sources.py", "tests/test_reviewed_ui_sources.py", ".github/workflows/prepare-reviewed-ui-promotion.yml", ".github/workflows/prepare-reviewed-ui-branch.yml"]


def git(root, args, env=None):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE, env=env).strip()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    require(path.is_file() and not path.is_symlink(), "Missing or symlinked source: " + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_files(root):
    for name, expected in EXPECTED.items():
        require(digest(root / name) == expected, "Reviewed hash differs: " + name)


def manifest_hashes(preview, timeline, actions):
    files = preview["files"]
    require(set(files) == set(EXPECTED) - {"webpage/schedule-timeline-view.js", "webpage/schedule-page-binding.js"}, "Unexpected preview manifest paths")
    result = {name: item["sha256"] for name, item in files.items()}
    result["webpage/schedule-timeline-view.js"] = timeline["candidate_sha256"]
    result["webpage/schedule-page-binding.js"] = actions["files"]["webpage/schedule-page-binding.js"]["sha256"]
    require(actions["unchanged_renderer_sha256"] == result["webpage/schedule-timeline-view.js"], "Renderer evidence differs")
    require(result == EXPECTED, "Pinned evidence hashes differ")
    return result


def checkpoint(config_sha):
    return {"schema": 2, "reviewed_source": REVIEWED, "configuration_sha": config_sha, "review_run": RUN, "scope": "UI sources only; no firmware or hardware proof", "files": EXPECTED}


def clean_base(root, config_sha):
    require(len(config_sha) == 40 and all(c in "0123456789abcdef" for c in config_sha), "Invalid configuration SHA")
    require(git(root, ["rev-parse", "HEAD"]) == config_sha, "Configuration checkout differs")
    require(not git(root, ["status", "--porcelain", "--untracked-files=no"]), "Tracked checkout is dirty")
    require(not (root / MARKER).exists(), "Promotion marker already exists")
    changed = set(git(root, ["diff", "--name-only", REVIEWED, config_sha]).splitlines())
    require(changed <= set(CONFIG), "Unreviewed changes outside preparation configuration")


def verify(root, config_sha, bundle):
    clean_base(root, config_sha)
    git(root, ["fetch", "--no-tags", "origin", "ci-evidence"])
    evidence = {key: json.loads(git(root, ["show", commit + ":runs/" + RUN + "-1/" + name])) for key, (commit, name) in EVIDENCE.items()}
    review = evidence["review"]
    require(review["source_sha"] == REVIEWED and review["status"] == "PASS", "Review/source did not pass")
    require(all(review.get(key) == "success" for key in ["candidate_result", "baseline_gates", "final_build", "final_checks", "download_result"]), "Review gates incomplete")
    require(set(review["source_checks"]) == set(evidence["preview"]["files"]) and all(value is True for value in review["source_checks"].values()), "Source checks incomplete")
    manifest_hashes(evidence["preview"], evidence["timeline"], evidence["actions"])
    work = root.parent / "reviewed-ui-replay"
    require(not work.exists(), "Replay directory already exists")
    git(root, ["worktree", "add", "--detach", str(work), REVIEWED])
    for name in GENERATORS:
        subprocess.run(["python3", "tools/" + name], cwd=work, check=True)
    verify_files(work)
    changed = set(git(work, ["diff", "--name-only"]).splitlines())
    require(changed <= set(EXPECTED) and changed, "Unexpected replay paths")
    require(not git(work, ["ls-files", "--others", "--exclude-standard", "--", "webpage"]), "Unexpected untracked webpage sources")
    require(not bundle.exists(), "Bundle already exists")
    bundle.mkdir(parents=True)
    for name in EXPECTED:
        target = bundle / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((work / name).read_bytes())
    (bundle / "receipt.json").write_text(json.dumps(checkpoint(config_sha), sort_keys=True) + "\n")
    return {"status": "VERIFIED", "configuration_sha": config_sha, "files": len(EXPECTED)}


def auth_env():
    env = dict(os.environ)
    token = env.pop("GH_TOKEN")
    value = base64.b64encode(("x-access-token:" + token).encode()).decode()
    env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader", GIT_CONFIG_VALUE_0="AUTHORIZATION: basic " + value)
    return env


def guard_context(config_sha, target):
    require(target == TARGET, "Unexpected target branch")
    require(os.environ.get("GITHUB_REPOSITORY") == REPO, "Unexpected repository")
    require(os.environ.get("GITHUB_EVENT_NAME") == "push", "Preparation requires push event")
    require(os.environ.get("GITHUB_REF") == "refs/heads/" + SOURCE, "Unexpected source ref")
    require(os.environ.get("GITHUB_SHA") == config_sha, "Unexpected event SHA")


def prepare(root, config_sha, bundle, target):
    guard_context(config_sha, target)
    clean_base(root, config_sha)
    require(json.loads((bundle / "receipt.json").read_text()) == checkpoint(config_sha), "Bundle receipt differs")
    require({str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_file()} == set(EXPECTED) | {"receipt.json"}, "Unexpected bundle files")
    verify_files(bundle)
    origin = git(root, ["remote", "get-url", "origin"])
    require(origin in ["https://github.com/" + REPO, "https://github.com/" + REPO + ".git"], "Unexpected origin")
    env = auth_env()
    require(not git(root, ["ls-remote", "origin", "refs/heads/" + TARGET], env), "Target branch exists; do not overwrite")
    refs = git(root, ["ls-remote", "origin", "refs/heads/" + SOURCE], env).split()
    require(bool(refs) and refs[0] == config_sha, "Source branch advanced")
    git(root, ["switch", "-c", TARGET])
    git(root, ["config", "user.name", "github-actions[bot]"])
    git(root, ["config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    for name in EXPECTED:
        (root / name).write_bytes((bundle / name).read_bytes())
    verify_files(root)
    changed = set(git(root, ["diff", "--name-only"]).splitlines())
    require(changed and changed <= set(EXPECTED), "Unexpected preparation paths")
    for name in sorted(changed):
        git(root, ["add", "--", name])
        git(root, ["commit", "-m", "feat: promote reviewed UI source " + name])
    (root / MARKER).write_text(json.dumps(checkpoint(config_sha), indent=2) + "\n")
    git(root, ["add", "--", MARKER])
    git(root, ["commit", "-m", "test: record exact reviewed UI checkpoint"])
    require(set(git(root, ["diff", "--name-only", config_sha, "HEAD"]).splitlines()) == changed | {MARKER}, "Commit paths differ")
    refs = git(root, ["ls-remote", "origin", "refs/heads/" + SOURCE], env).split()
    require(bool(refs) and refs[0] == config_sha, "Source advanced before push")
    git(root, ["push", "--force-with-lease=refs/heads/" + TARGET + ":", "origin", "HEAD:refs/heads/" + TARGET], env)
    head = git(root, ["rev-parse", "HEAD"])
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write("head=" + head + "\n")
    return {"status": "PREPARED_NOT_VALIDATED", "head": head, "branch": TARGET}


def check(root, config_sha):
    require(json.loads((root / MARKER).read_text()) == checkpoint(config_sha), "Checkpoint differs")
    verify_files(root)
    return {"status": "PASS", "scope": "exact reviewed UI sources; not firmware or hardware"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["verify", "prepare", "check"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config-sha", required=True)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--target", default=TARGET)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "verify":
        result = verify(root, args.config_sha, args.bundle.resolve())
    elif args.mode == "prepare":
        result = prepare(root, args.config_sha, args.bundle.resolve(), args.target)
    else:
        result = check(root, args.config_sha)
    print(json.dumps(result, sort_keys=True))
