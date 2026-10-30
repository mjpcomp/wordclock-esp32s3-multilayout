#!/usr/bin/env python3
"""Verify the reviewed UI and emit only a scoped promotion request."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

REPOSITORY = "mjpcomp/wordclock-esp32s3-multilayout"
SOURCE = "feature/optional-status-prefix"
TARGET = "promotion/reviewed-ui-b598076f"
REVIEWED = "b598076fb48cfccdfe1ac018f6eaa94ffbdb61f8"
REVIEW_COMMIT = "63d44b5992d484b8e0271d883ebead8e762ba7f7"
MANIFEST_COMMIT = "053e28a5a41ec1e91d421e23c86a58a440b8d33d"
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
    "webpage/schedule-page-binding.js": "1085404f1f46a4f67099094940c40c6d9b2dee67ba567a2d3d6f03acb6a30a4c"
}
GENERATORS = ["prepare_compact_layout.py", "refine_compact_layout_mobile.py", "prepare_responsive_timeline.py", "prepare_schedule_action_states.py", "prepare_mirc0_preview_page.py", "refine_disabled_schedule_fields.py"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(root, args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE).strip()


def checkpoint():
    return {"schema": 1, "reviewed_source": REVIEWED, "review_commit": REVIEW_COMMIT, "review_run": RUN, "scope": "UI sources only; no firmware or hardware proof", "files": EXPECTED}


def verify_files(root):
    for name, expected in EXPECTED.items():
        path = root / name
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise ValueError("Reviewed UI source hash differs: " + name)


def verify_checkpoint(root):
    marker = root / MARKER
    if not marker.exists():
        return False
    if json.loads(marker.read_text()) != checkpoint():
        raise ValueError("UI checkpoint differs from the approved promotion")
    verify_files(root)
    return True


def export_sources(root):
    evidence = root / "compact-layout-evidence"
    evidence.mkdir(exist_ok=True)
    manifest = {"scope": "Reviewed repository UI sources; no firmware or hardware proof", "reviewed_source": REVIEWED, "review_run": RUN,
                "unlit_black_text_guide": "#59636f", "disabled_field_palette": {"foreground": "#526171", "background": "#e4eaf0"}, "files": {}}
    for name, expected in EXPECTED.items():
        artifact = "preview-" + Path(name).name
        (evidence / artifact).write_bytes((root / name).read_bytes())
        manifest["files"][name] = {"artifact": artifact, "sha256": expected}
    (evidence / "preview-source.json").write_text(json.dumps(manifest, indent=2) + "\n")


def check(root):
    exists = (root / MARKER).exists()
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write("promoted=" + str(exists).lower() + "\n")
    if exists:
        verify_checkpoint(root)
        export_sources(root)
        print(json.dumps({"status": "PASS", "scope": "exact reviewed repository UI sources", "files": len(EXPECTED)}))
    else:
        print("No promotion marker; source checks are not applicable yet.")


def preflight(root, source_head):
    if source_head != REVIEWED or git(root, ["rev-parse", "HEAD"]) != source_head:
        raise ValueError("Preparation checkout differs from reviewed source SHA")
    if (root / MARKER).exists():
        raise ValueError("Promotion receipt already exists")
    subprocess.run(["git", "-C", str(root), "diff", "--exit-code"], check=True)
    review = json.loads(git(root, ["show", REVIEW_COMMIT + ":runs/" + RUN + "-1/review.json"]))
    manifest = json.loads(git(root, ["show", MANIFEST_COMMIT + ":runs/" + RUN + "-1/preview-source.json"]))
    if review.get("source_sha") != REVIEWED or review.get("status") != "PASS" or not all(review.get("source_checks", {}).values()):
        raise ValueError("Reviewed evidence did not pass")
    items = manifest.get("files", {})
    if set(items) != set(EXPECTED) or any(EXPECTED[name] != item.get("sha256") for name, item in items.items()):
        raise ValueError("Reviewed source manifest differs")
    for name in GENERATORS:
        path = root / "tools" / name
        if path.read_bytes() != subprocess.check_output(["git", "show", REVIEWED + ":tools/" + name], cwd=root):
            raise ValueError("Reviewed generator differs: " + name)
    verify_files(root)
    subprocess.run(["python3", "tools/schedule_live/check.py"], cwd=root, check=True)
    return {"source_sha": REVIEWED, "target_branch": TARGET, "checkpoint": checkpoint()}


def prepare(root, source_head, target_branch):
    env = os.environ
    if env.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or env.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise SystemExit("Branch write permitted only in dispatched child workflow")
    if target_branch != TARGET or env.get("GITHUB_REF_NAME") != SOURCE:
        raise SystemExit("Unexpected promotion target or workflow source ref")
    preflight(root, source_head)
    original_head = git(root, ["rev-parse", "HEAD"])
    if original_head != env.get("GITHUB_SHA"):
        raise SystemExit("Child checkout differs from dispatched SHA")
    origin = git(root, ["remote", "get-url", "origin"])
    url = "https://github.com/" + REPOSITORY
    if origin not in [url, url + ".git"]:
        raise SystemExit("Unexpected origin")
    auth = dict(env)
    auth.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                GIT_CONFIG_VALUE_0="AUTHORIZATION: basic " + __import__("base64").b64encode(("x-access-token:" + env["GH_TOKEN"]).encode()).decode())
    if git(root, ["ls-remote", "origin", "refs/heads/" + target_branch], auth):
        raise SystemExit("Promotion branch already exists; inspect it instead of overwriting")
    if git(root, ["ls-remote", "origin", "refs/heads/" + SOURCE], auth).split()[0] != original_head:
        raise SystemExit("Source branch advanced; re-review before preparing")
    changed = set(git(root, ["diff", "--name-only"]).splitlines())
    if changed != set(EXPECTED) - {"webpage/mirc0-preview.js"}:
        raise SystemExit("Unexpected source promotion diff")
    git(root, ["switch", "-c", target_branch])
    git(root, ["config", "user.name", "github-actions[bot]"])
    git(root, ["config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    for name in sorted(changed):
        git(root, ["add", "--", name])
        git(root, ["commit", "-m", "feat: promote reviewed UI source " + name])
    (root / MARKER).write_text(json.dumps(checkpoint(), indent=2) + "\n")
    git(root, ["add", "--", MARKER])
    git(root, ["commit", "-m", "test: record exact reviewed UI source checkpoint"])
    verify_checkpoint(root)
    git(root, ["push", "origin", "HEAD:refs/heads/" + target_branch], auth)
    return {"status": "PREPARED_NOT_MERGED", "branch": target_branch, "source_sha": original_head, "checkpoint": checkpoint(), "head": git(root, ["rev-parse", "HEAD"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["check", "prepare", "preflight"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--source-head")
    parser.add_argument("--target-branch", default=TARGET)
    parser.add_argument("--receipt")
    args = parser.parse_args()
    if args.mode == "check":
        check(args.root)
    elif args.mode == "preflight":
        if git(args.root, ["rev-parse", "HEAD"]) != args.source_head:
            raise SystemExit("Verifier checkout differs from requested reviewed SHA")
        receipt = preflight(args.root, args.source_head)
        if args.receipt:
            Path(args.receipt).write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({"status": "SOURCE_VERIFIED", "source_sha": receipt["source_sha"], "target_branch": receipt["target_branch"]}))
    else:
        print(json.dumps(prepare(args.root, args.source_head, args.target_branch), sort_keys=True))
