#!/usr/bin/env python3
"""Activate the reviewed Mirc0 modules only inside the CI page candidate."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = "7a44bbd93c4ee6364ed1721377fcf66ea2c626ef"
PREVIEW = "bd6346d60ceceb3c0f1b3ddd708e0fd2bce4e7d4"
EXPECTED = {
    "webpage/style.css": "aa71ce8442c5825a179a3a6c0aa58c46fbb300dbb188203081ef91582d192439",
    "webpage/index.html": "91300dbf352af003dc66245bca6e86663d1084e80d6410cc4e0fbe7ec9bc7a85",
    "webpage/schedule-timeline-view.js": "9ac27148d665581407853e9c511654fa9491a26f74f9d9fc07e103fb81f3d25d"
}
BOOTSTRAP = """
let mirc0PreviewPage = null;
function initMirc0PreviewPage() {
    const host = document.querySelector(".box-color");
    if (!host) return;
    mirc0PreviewPage = window.createWordclockMirc0PreviewPage(host, {
        view: window.WordclockMirc0Preview,
        available: function() { return document.getElementById("front-layout").value === "36"; },
        readColors: function() {
            return hsb.slice(0, 2).map(function(color) { return new iro.Color({ h: color[0], s: color[1], v: color[2] }).hexString; });
        }
    });
}
""".replace("    ", "\t")
CSS = """
/* The face is local illustration; existing colour and scheduler controls stay intact. */
#mirc0-preview-panel {
    box-sizing: border-box;
    width: 100%;
    max-width: 20.625rem;
    min-width: 0;
    margin: 0.75rem auto 0;
    text-align: left;
}

#mirc0-preview-panel[hidden] {
    display: none;
}

#mirc0-preview-panel h3 {
    margin: 0 0 0.5rem;
    font-size: 1rem;
    font-weight: 500;
}

#mirc0-preview-panel svg {
    display: block;
    width: 100%;
    height: auto;
}

#mirc0-preview-panel text[data-lit='false'][fill='#000000'] {
    fill: #59636f;
}

#mirc0-preview-panel .mirc0-preview-controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.5rem;
}

#mirc0-preview-panel label {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    min-height: var(--app-control-height);
    margin: 0;
}

#mirc0-preview-panel input[type='time'] {
    box-sizing: border-box;
    width: 9.5rem;
    min-width: 0;
    max-width: 100%;
    min-height: var(--app-control-height);
}

#mirc0-preview-panel p {
    margin: 0.5rem 0 0;
    font-size: 0.85rem;
    line-height: 1.35;
}

@media (width >= 60em) {
    .box-color #mirc0-preview-panel {
        grid-column: 1;
        grid-row: 3;
        align-self: start;
    }
}

@media (width >= 80em) {
    .box-color:has(#mirc0-preview-panel:not([hidden])) {
        grid-template-columns: minmax(0, 302px) minmax(0, 300px) minmax(0, 330px);
    }

    .box-color #mirc0-preview-panel {
        grid-column: 3;
        grid-row: 1 / span 2;
        margin-top: 0;
    }
}
"""
SCRIPT_CHANGES = [
    ("let colorPicker;", "let colorPicker;\n" + BOOTSTRAP.rstrip("\n")),
    ("\tcreateColorPicker();", "\tcreateColorPicker();\n\tinitMirc0PreviewPage();"),
    ("\tcolorPicker.setColors([hsbFg]);", "\tcolorPicker.setColors([hsbFg]);\n\tif (mirc0PreviewPage) mirc0PreviewPage.refresh();"),
    ('document.getElementById("front-layout").value = data.clockTypeDef;', 'document.getElementById("front-layout").value = data.clockTypeDef;\n\t\t\t\tif (mirc0PreviewPage) mirc0PreviewPage.refresh();')
]


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Missing or ambiguous preview anchor: " + old[:70])
    return source.replace(old, new)


def transform_script(source):
    for old, new in SCRIPT_CHANGES:
        source = replace_once(source, old, new)
    return source


def sha(value):
    return hashlib.sha256(value).hexdigest()


def main():
    for name, expected in EXPECTED.items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise SystemExit("Refusing: validated candidate input differs: " + name)
    original = {}
    for name in ["webpage/script.js", "Gruntfile.js", "webpage/mirc0-preview.js", "webpage/mirc0-preview-page.js"]:
        ref = PREVIEW if "mirc0-preview" in name else BASE
        value = subprocess.check_output(["git", "show", ref + ":" + name], cwd=ROOT)
        if (ROOT / name).read_bytes() != value:
            raise SystemExit("Refusing: reviewed source differs: " + name)
        original[name] = value
    tag = '<script src="./script.js"></script>'
    scripts = '<script src="./mirc0-preview.js"></script>\n<script src="./mirc0-preview-page.js"></script>\n' + tag
    grunt_anchor = '"<%= settings.srcDirectory %>/schedule-*.js",'
    result = {
        "webpage/script.js": transform_script(original["webpage/script.js"].decode("utf-8")),
        "webpage/index.html": replace_once((ROOT / "webpage/index.html").read_text(), tag, scripts),
        "webpage/style.css": (ROOT / "webpage/style.css").read_text().rstrip() + "\n" + CSS,
        "Gruntfile.js": replace_once(original["Gruntfile.js"].decode("utf-8"), grunt_anchor, grunt_anchor + '\n\t\t\t\t"<%= settings.srcDirectory %>/mirc0-*.js",')
    }
    evidence = ROOT / "compact-layout-evidence"
    manifest = {"scope": "CI preview integration only; local samples, not device telemetry or flash-ready output", "preview_checkpoint": PREVIEW, "unlit_black_text_guide": "#59636f", "files": {}}
    for name in ["webpage/mirc0-preview.js", "webpage/mirc0-preview-page.js"]:
        content = original[name].decode("utf-8")
        if name.endswith("mirc0-preview-page.js"):
            content = replace_once(content,
                                   "Local sample only; not device time or output telemetry. Colour controls keep their existing device behaviour.",
                                   "Local sample only; not device time or output telemetry. Grey unlit letters are a guide for black backgrounds. Colour controls keep their existing device behaviour.")
        result[name] = content
    for name, content in result.items():
        (ROOT / name).write_text(content, encoding="utf-8")
        artifact = "preview-" + Path(name).name
        (evidence / artifact).write_text(content, encoding="utf-8")
        manifest["files"][name] = {"artifact": artifact, "sha256": sha(content.encode("utf-8"))}
    (evidence / "preview-source.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
