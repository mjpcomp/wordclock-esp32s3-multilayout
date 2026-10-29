#!/usr/bin/env python3
"""Apply action presentation only to the pinned CI candidate; never promote it."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = "7a44bbd93c4ee6364ed1721377fcf66ea2c626ef"
DENSITY = "f3c5c55b4bcb06150b48b17752c6d37c8f6cdb4ec4713307c2c7bbdcfcab326c"
RENDERER = "9ac27148d665581407853e9c511654fa9491a26f74f9d9fc07e103fb81f3d25d"
CSS = """
/* Scheduler presentation only: keep busy controls readable and collapse absent choices. */
#schedule-editor [hidden],
#schedule-editor .pure-controls:has(> [data-schedule='use-remote'][hidden]) {
    display: none;
}

#schedule-editor .pure-button:disabled {
    color: #526171;
    background: #e4eaf0;
    border: 1px solid #bac5d0;
    box-shadow: none;
    opacity: 1;
    cursor: not-allowed;
}

#schedule-editor .schedule-build-details {
    margin-bottom: 0.5rem;
}

#schedule-editor .schedule-build-details > summary {
    box-sizing: border-box;
    min-height: var(--app-control-height);
    padding: 0.5rem 0;
    color: var(--app-text-muted);
    cursor: pointer;
}
"""
STATUS = """        function statusMessage(state) {
            if (state.pending) {
                const pending = { get: "Reading schedule...", save: "Saving schedule...", reset: "Resetting schedule..." };
                return text("status-pending-" + state.pending.action, pending[state.pending.action] || "Schedule request in progress...");
            }
            if (!state.connected) return text("status-offline", "Disconnected. Reconnect before saving.");
            if (!supported(state)) return text("status-unavailable", "Scheduler configuration unavailable; reconnect or reload to check support.");
            if (state.remote) return text("status-choice", "Device version available. Choose which version to keep.");
            if (state.resetRequired) return text("status-reset-required", "Stored schedule cannot be used. An explicit schedule reset is required.");
            if (state.needsReload) return text("status-reload", "Reload the schedule to confirm the device version before saving.");
            const messages = { loaded: "Schedule loaded.", "unsaved-default": "No saved schedule. Edit a local draft, then Save.", saved: "Schedule saved.", reset: "Schedule reset.", ready: "Schedule ready." };
            return text("status-" + state.status, messages[state.status] || "Schedule status: " + state.status + ".");
        }
""".replace("    ", "\t")
CHANGES = [
    ('\t\tfunction report(error)', STATUS + '\t\tfunction report(error)'),
    ('text("status-" + state.status, state.status)', 'statusMessage(state)'),
    ('fields.discard.disabled = !state.canDiscard;', 'fields.discard.disabled = !state.canDiscard;\n\t\t\tfields.discard.hidden = !state.dirty && !state.canDiscard;'),
    ('fields["use-remote"].disabled = fields["keep-draft"].disabled = !state.connected || Boolean(state.pending) || !state.remote;', 'fields["use-remote"].disabled = fields["keep-draft"].disabled = !state.connected || Boolean(state.pending) || !state.remote;\n\t\t\tfields["use-remote"].hidden = fields["keep-draft"].hidden = !state.remote;')
]
CAPABILITY = '<p data-schedule="capabilities">Hardware readiness is not verified.</p>'
DETAILS = '<details class="schedule-build-details">\n                        <summary>Configuration support and build details</summary>\n                        ' + CAPABILITY + '\n                    </details>'


def transform_binding(source):
    for old, new in CHANGES:
        if source.count(old) != 1:
            raise ValueError("Binding anchor missing or ambiguous: " + old[:70])
        source = source.replace(old, new)
    return source


def digest(value):
    return hashlib.sha256(value).hexdigest()


def main():
    css_path = ROOT / "webpage/style.css"
    original_css = css_path.read_bytes()
    if digest(original_css) != DENSITY:
        raise SystemExit("Refusing: density CSS changed")
    if digest((ROOT / "webpage/schedule-timeline-view.js").read_bytes()) != RENDERER:
        raise SystemExit("Refusing: validated responsive renderer changed")
    originals = {}
    for name in ["webpage/schedule-page-binding.js", "webpage/index.html"]:
        original = subprocess.check_output(["git", "show", CHECKPOINT + ":" + name], cwd=ROOT)
        if (ROOT / name).read_bytes() != original:
            raise SystemExit("Refusing: reviewed page source differs: " + name)
        originals[name] = original
    binding = transform_binding(originals["webpage/schedule-page-binding.js"].decode("utf-8"))
    html = originals["webpage/index.html"].decode("utf-8")
    if html.count(CAPABILITY) != 1:
        raise SystemExit("Refusing: capability paragraph anchor differs")
    html = html.replace(CAPABILITY, DETAILS)
    final_css = original_css.decode("utf-8").rstrip() + "\n" + CSS
    evidence = ROOT / "compact-layout-evidence"
    results = {"webpage/style.css": final_css, "webpage/schedule-page-binding.js": binding, "webpage/index.html": html}
    manifest = {"scope": "CI action presentation candidate only; no promotion, transport changes or hardware proof",
                "density_base_css_sha256": DENSITY, "unchanged_renderer_sha256": RENDERER, "files": {}}
    for name, result in results.items():
        (ROOT / name).write_text(result, encoding="utf-8")
        artifact = "action-state-" + Path(name).name
        (evidence / artifact).write_text(result, encoding="utf-8")
        manifest["files"][name] = {"artifact": artifact, "sha256": digest(result.encode("utf-8"))}
    patch = difflib.unified_diff(original_css.decode("utf-8").splitlines(True), final_css.splitlines(True), fromfile="density-style.css", tofile="action-state-style.css")
    (evidence / "action-state-style.patch").write_text("".join(patch), encoding="utf-8")
    (evidence / "action-state-source.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
