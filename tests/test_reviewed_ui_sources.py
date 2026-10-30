#!/usr/bin/env python3
"""Test checkpoint/permission policy with temporary files; no GitHub writes."""
from pathlib import Path
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("promotion", ROOT / "tools/promote_reviewed_ui_sources.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main():
    saved = module.EXPECTED
    try:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            module.EXPECTED = {"webpage/example.js": module.sha(b"reviewed"), "Gruntfile.js": module.sha(b"build")}
            assert module.verify_checkpoint(root) is False
            (root / "webpage").mkdir()
            (root / "webpage/example.js").write_bytes(b"reviewed")
            (root / "Gruntfile.js").write_bytes(b"build")
            marker = root / module.MARKER
            marker.parent.mkdir()
            marker.write_text(json.dumps(module.checkpoint()))
            assert module.verify_checkpoint(root) is True
            (root / "webpage/example.js").write_bytes(b"unreviewed")
            try:
                module.verify_checkpoint(root)
            except ValueError:
                pass
            else:
                raise AssertionError("Changed source accepted")
            (root / "webpage/example.js").write_bytes(b"reviewed")
            data = module.checkpoint()
            data["reviewed_source"] = "other"
            marker.write_text(json.dumps(data))
            try:
                module.verify_checkpoint(root)
            except ValueError:
                pass
            else:
                raise AssertionError("Changed receipt accepted")
    finally:
        module.EXPECTED = saved
    assert len(saved) == 8
    assert all(len(value) == 64 and int(value, 16) >= 0 for value in saved.values())
    assert module.TARGET != module.SOURCE and module.TARGET != "main"
    print(json.dumps({"status": "PASS", "scope": "exact-source checkpoint guards; no network or branch write"}))


if __name__ == "__main__":
    main()
