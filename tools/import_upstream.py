#!/usr/bin/env python3
"""Verify and import a pinned upstream snapshot. Dry-run unless --apply is set."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def checked_path(root, name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe path: " + name)
    path = root.joinpath(*rel.parts)
    path.resolve().relative_to(root.resolve())
    if path.is_symlink():
        raise ValueError("Symlink not allowed: " + name)
    return path


def prepare(source, root, manifest):
    names = manifest["files"]
    if manifest["format_version"] != 1 or len(names) != manifest["selected_file_count"]:
        raise ValueError("Invalid manifest version/count")
    if names != sorted(set(names)):
        raise ValueError("Manifest paths must be unique and sorted")
    metadata, planned = [], []
    for name in names:
        if name == "README.md" or name.startswith(".github/") or name == "tools/import_upstream.py":
            raise ValueError("Protected destination: " + name)
        raw = checked_path(source, name).read_bytes()
        metadata.append([name, hashlib.sha256(raw).hexdigest(), len(raw)])
        final = raw
        if name == "platformio.ini":
            text = raw.decode("utf-8")
            text = re.sub(r"(?m)^[ \t]*post:erase_before_upload\.py(?:\r?\n|$)", "", text)
            if "erase_before_upload.py" in text or "--erase-all" in text:
                raise ValueError("Automatic flash erase remains in configuration")
            final = text.encode("utf-8")
        destination = checked_path(root, name)
        if destination.exists() and destination.read_bytes() != final:
            raise ValueError("Refusing to overwrite different existing file: " + name)
        planned.append((name, final, not destination.exists()))
    digest = hashlib.sha256(json.dumps(metadata, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    if digest != manifest["metadata_sha256"]:
        raise ValueError("Snapshot metadata checksum does not match approved manifest")
    return planned


def batches(entries):
    result, pending, kind = [], [], None
    ordered = sorted(entries, key=lambda entry: (0 if len(entry[1]) > 10240 else 1 if len(entry[1]) >= 2048 else 2, entry[0]))
    for name, data, needed in ordered:
        if not needed:
            continue
        category = "large" if len(data) > 10240 else "medium" if len(data) >= 2048 else "small"
        limit = {"large": 1, "medium": 4, "small": 8}[category]
        if pending and (category != kind or len(pending) >= limit):
            result.append(pending)
            pending = []
        kind = category
        pending.append((name, data))
    if pending:
        result.append(pending)
    return result


def execute(source, root, manifest, apply=False, push=False):
    if push and not apply:
        raise ValueError("--push requires --apply")
    if push:
        remote = git(root, "remote", "get-url", "origin").rstrip("/")
        if remote.endswith(".git"):
            remote = remote[:-4]
        expected = manifest["destination_repository"]
        if remote not in ("https://github.com/" + expected, "git@github.com:" + expected):
            raise ValueError("Refusing to push to an unexpected repository")
    actual_revision = git(source, "rev-parse", "HEAD")
    if actual_revision != manifest["revision"]:
        raise ValueError("Source revision mismatch: " + actual_revision)
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Destination has uncommitted tracked changes")
    if git(root, "branch", "--show-current") != "main":
        raise ValueError("Destination must be checked out on main")
    start_commit = git(root, "rev-parse", "HEAD")
    plan = prepare(source, root, manifest)
    groups = batches(plan)
    report = {
        "mode": "apply" if apply else "dry-run", "revision": actual_revision,
        "verified_files": len(plan), "new_files": sum(needed for _, _, needed in plan),
        "commit_batches": len(groups), "start_commit": start_commit, "commits": [],
        "automatic_full_flash_erase": False, "s3_port_ready": False,
        "arduino_export_ready": False, "target_compile_performed": False,
    }
    if apply:
        for index, group in enumerate(groups, 1):
            for name, data in group:
                path = checked_path(root, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            names = [name for name, _ in group]
            git(root, "add", "--", *names)
            if not git(root, "diff", "--cached", "--name-only"):
                continue
            message = "import: upstream {} batch {}/{}".format(actual_revision[:12], index, len(groups))
            git(root, "commit", "-m", message)
            commit = git(root, "rev-parse", "HEAD")
            report["commits"].append({"sha": commit, "paths": names})
            print("Committed", commit[:12], "files:", ", ".join(names), flush=True)
        if push and report["commits"]:
            git(root, "push", "origin", "HEAD:main")
    report["end_commit"] = git(root, "rev-parse", "HEAD")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--root", default=Path("."), type=Path)
    parser.add_argument("--manifest", default=Path("UPSTREAM.json"), type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = execute(args.source.resolve(), args.root.resolve(), manifest, args.apply, args.push)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "commits"}, indent=2))


if __name__ == "__main__":
    main()
