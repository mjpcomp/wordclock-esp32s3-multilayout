#!/usr/bin/env python3
"""Final CI-only text palette; never enable controls or change their values."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
INPUT_CSS = "4d5c96fddeaa4823a971f6dc8d88585b472617b459a0c838bfc6eef767eb7f65"
CSS = """
/* Disabled scheduler text stays readable without changing native disabled state. */
#schedule-editor .pure-form input[type='number']:disabled,
#schedule-editor .pure-form input[type='time']:disabled,
#schedule-editor .pure-form select:disabled {
    color: #526171;
    background: #e4eaf0;
    opacity: 1;
}
"""


def append_css(source):
    return source.rstrip() + "\n" + CSS


def main():
    target = ROOT / "webpage/style.css"
    evidence = ROOT / "compact-layout-evidence"
    metadata = evidence / "preview-source.json"
    original = target.read_bytes()
    manifest = json.loads(metadata.read_text())
    if hashlib.sha256(original).hexdigest() != INPUT_CSS or manifest["files"]["webpage/style.css"]["sha256"] != INPUT_CSS:
        raise SystemExit("Refusing: reviewed integrated stylesheet differs")
    result = append_css(original.decode("utf-8"))
    digest = hashlib.sha256(result.encode("utf-8")).hexdigest()
    manifest["scope"] = "CI UI candidate only; no source promotion, device changes or hardware proof"
    manifest["disabled_field_base_css_sha256"] = INPUT_CSS
    manifest["disabled_field_palette"] = {"foreground": "#526171", "background": "#e4eaf0"}
    manifest["files"]["webpage/style.css"]["sha256"] = digest
    target.write_text(result, encoding="utf-8")
    (evidence / manifest["files"]["webpage/style.css"]["artifact"]).write_text(result, encoding="utf-8")
    metadata.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"scope": manifest["scope"], "stylesheet_sha256": digest}))


if __name__ == "__main__":
    main()
