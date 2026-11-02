#!/usr/bin/env python3
"""Apply pinned activation edits in a disposable CI checkout; never push files."""
from pathlib import Path
import difflib
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "webpage/script.js": "cee85d74736c6a0fa949e3dc67aeb7e6e345022eaf8bf5d5c24dc1979147603f",
    "webpage/index.html": "304769437af4fa347fd48a08d12cc8f1e492010003af008f622b6a3664b7fec4",
    "webpage/style.css": "22689a11e2673feb037634c749a29d2aa57f95b3cb0fe9f1101933c1f2e60f01",
}
OLD_INIT = '''function initMirc0PreviewPage() {
\tconst host = document.querySelector(".box-color");
\tif (!host) return;
\tmirc0PreviewPage = window.createWordclockMirc0PreviewPage(host, {
\t\tview: window.WordclockMirc0Preview,
\t\tavailable: function() { return document.getElementById("front-layout").value === "36"; },
\t\treadColors: function() {
\t\t\treturn hsb.slice(0, 2).map(function(color) { return new iro.Color({ h: color[0], s: color[1], v: color[2] }).hexString; });
\t\t}
\t});
}
'''
NEW_INIT = '''function readMirc0PreviewSchedule() {
\tif (!scheduleBridge) return null;
\tconst state = scheduleBridge.snapshot();
\tconst caps = state.capabilities;
\tif (!state.connected || !state.draft || !caps || caps.metadataState !== "valid" || caps.configurationProtocol !== true || state.pending || state.needsReload || state.resetRequired) return null;
\tconst unsaved = state.dirty || !state.saved || state.saved.revision === 0;
\treturn { schedule: window.WordclockScheduleModel.validate(state.draft), source: unsaved ? "unsaved-draft" : "saved" };
}
function initMirc0PreviewPage() {
\tconst host = document.querySelector(".box-color");
\tif (!host) return;
\tmirc0PreviewPage = window.createWordclockMirc0PreviewPage(host, {
\t\tview: window.WordclockMirc0Preview,
\t\tavailable: function() { return document.getElementById("front-layout").value === "36"; },
\t\treadColors: function() {
\t\t\treturn hsb.slice(0, 2).map(function(color) { return new iro.Color({ h: color[0], s: color[1], v: color[2] }).hexString; });
\t\t},
\t\tsimulation: {
\t\t\tplayback: window.WordclockMirc0Playback,
\t\t\tmodel: window.WordclockScheduleModel,
\t\t\tcreateControls: window.createWordclockMirc0PreviewControls,
\t\t\trequestFrame: function(callback) { return window.requestAnimationFrame(callback); },
\t\t\tcancelFrame: function(handle) { window.cancelAnimationFrame(handle); },
\t\t\treadSchedule: readMirc0PreviewSchedule
\t\t}
\t});
}
'''
SCRIPT_ANCHOR = '<script src="./mirc0-preview-page.js"></script>'
SCRIPT_INSERT = '<script src="./mirc0-preview-playback.js"></script>\n<script src="./mirc0-preview-controls.js"></script>\n' + SCRIPT_ANCHOR
CSS = '''
/* Local simulation controls: prevent intrinsic select/button widths causing overflow. */
#mirc0-preview-panel [data-mirc0='simulation-controls'] {
    min-width: 0;
    max-width: 100%;
    overflow-wrap: anywhere;
}

#mirc0-preview-panel [data-mirc0='simulation-controls'] label {
    flex-wrap: wrap;
}

#mirc0-preview-panel [data-mirc0='simulation-controls'] select,
#mirc0-preview-panel [data-mirc0='simulation-controls'] input[type='range'] {
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
    max-width: 100%;
    min-height: var(--app-control-height);
}

#mirc0-preview-panel [data-mirc0='simulation-controls'] button {
    max-width: 100%;
    white-space: normal;
}
'''


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Activation anchor absent or repeated")
    return text.replace(old, new, 1)


def apply(root):
    sources = {}
    for name, expected in EXPECTED.items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Pinned activation base differs: " + name)
        sources[name] = data.decode("utf-8")
    candidate = {
        "webpage/script.js": replace_once(sources["webpage/script.js"], OLD_INIT, NEW_INIT),
        "webpage/index.html": replace_once(sources["webpage/index.html"], SCRIPT_ANCHOR, SCRIPT_INSERT),
        "webpage/style.css": sources["webpage/style.css"] + CSS,
    }
    evidence = root / "preview-activation-evidence"
    evidence.mkdir(exist_ok=True)
    patches = []
    manifest = {"scope": "CI activation candidate only; no repository promotion, device changes or hardware proof", "files": {}}
    for name, text in candidate.items():
        patches.extend(difflib.unified_diff(sources[name].splitlines(True), text.splitlines(True), fromfile="a/" + name, tofile="b/" + name))
        (root / name).write_text(text)
        manifest["files"][name] = {"base_sha256": EXPECTED[name], "candidate_sha256": hashlib.sha256(text.encode()).hexdigest()}
    (evidence / "activation-source.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (evidence / "activation.diff").write_text("".join(patches))
    return manifest


if __name__ == "__main__":
    print(json.dumps(apply(ROOT), sort_keys=True))
