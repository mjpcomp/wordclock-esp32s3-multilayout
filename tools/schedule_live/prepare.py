#!/usr/bin/env python3
"""Read-only CI candidate preparation: patches worktree only; NEVER commits/pushes."""
from pathlib import Path
import subprocess

BASES = {
    "Gruntfile.js": "12973853e20090249352a4456134663e000a40dd",
    "webpage/script.js": "ef83dbe8a121000821bf194966a751331167a84d",
    "webpage/index.html": "7d4cba4bbbb69b83a23be5113b3a3a470582de75",
}
MODULES = ["schedule-model", "schedule-client", "schedule-timeline-adapter",
           "schedule-timeline-view", "schedule-capabilities", "schedule-page-controller",
           "schedule-page-binding", "schedule-socket-bridge"]
BOOTSTRAP = '''
let scheduleBridge = null;
function initSchedulePage() {
\tconst root = document.getElementById("schedule-editor");
\tif (!root) return;
\tscheduleBridge = window.createWordclockScheduleSocketBridge(function(send) {
\t\tconst model = window.WordclockScheduleModel;
\t\treturn window.createWordclockSchedulePage(root, {
\t\t\tcreateController: window.createWordclockScheduleController,
\t\t\tcreateTimelineView: window.createWordclockTimelineView,
\t\t\tcontrollerOptions: {
\t\t\t\tmodel: model,
\t\t\t\tadapter: window.createWordclockTimelineAdapter(model),
\t\t\t\tclient: window.createWordclockScheduleClient(model),
\t\t\t\treadCapabilities: window.readWordclockScheduleCapabilities,
\t\t\t\tsend: send,
\t\t\t\tsetTimeout: function(callback, delay) { return window.setTimeout(callback, delay); },
\t\t\t\tclearTimeout: function(handle) { window.clearTimeout(handle); }
\t\t\t},
\t\t\tconfirmReset: function() { return window.confirm(connectionText("schedule.confirm-reset", "Reset ONLY the stored schedule? This does not reset Wi-Fi or other settings.")); },
\t\t\ttext: function(key, fallback) { return connectionText("schedule." + key, fallback); }
\t\t});
\t});
\tif (typeof i18next !== "undefined" && typeof i18next.on === "function") {
\t\ti18next.on("languageChanged", function() { if (scheduleBridge) scheduleBridge.refresh(); });
\t}
}
'''

def once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit("Expected exactly one unchanged anchor: " + old[:100])
    return text.replace(old, new, 1)

def main():
    subprocess.run(["git", "diff", "--quiet"], check=True)
    sources = {}
    for name, expected in BASES.items():
        revision = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", name], text=True).strip()
        if revision != expected:
            raise SystemExit("Baseline changed; re-review required: " + name)
        sources[name] = Path(name).read_text()
    original = dict(sources)
    script = sources["webpage/script.js"]
    script = once(script, "let websocket;", "let websocket;\n" + BOOTSTRAP)
    script = once(script, "\twebsocket = new WebSocket(ipEsp);", "\tconst socket = new WebSocket(ipEsp);\n\twebsocket = socket;\n\tif (scheduleBridge) scheduleBridge.attach(socket);")
    for event in ("open", "close", "message", "error"):
        old = "\twebsocket.on" + event + " = function(event) {"
        new = "\tsocket.on" + event + " = function(event) {\n\t\tif (socket !== websocket) return;"
        script = once(script, old, new)
    script = once(script, "\t\tlet data = JSON.parse(event.data);", "\t\tif (typeof event.data !== \"string\") return;\n\t\tlet data;\n\t\ttry { data = JSON.parse(event.data); } catch (error) { if (error instanceof SyntaxError) return; throw error; }\n\t\tif (!data || data.command === \"brightness-schedule\") return;")
    script = once(script, "\tinitWebsocket();\n\tsetColors();", "\tinitSchedulePage();\n\tinitWebsocket();\n\tsetColors();")
    sources["webpage/script.js"] = script
    html = sources["webpage/index.html"]
    fragment = Path("tools/schedule_live/panel.html").read_text()
    html = once(html, '                </section>\n\n            <section class="pure-u-24-24 section section-functions">', fragment + '                </section>\n\n            <section class="pure-u-24-24 section section-functions">')
    tags = "\n".join('<script src="./' + name + '.js"></script>' for name in MODULES)
    html = once(html, '<script src="./script.js"></script>', tags + '\n<script src="./script.js"></script>')
    sources["webpage/index.html"] = html
    sources["Gruntfile.js"] = once(sources["Gruntfile.js"], '\t\t\t\t"<%= settings.srcDirectory %>/script.js",', '\t\t\t\t"<%= settings.srcDirectory %>/script.js",\n\t\t\t\t"<%= settings.srcDirectory %>/schedule-*.js",')
    for name, source in sources.items():
        if source == original[name]:
            raise SystemExit("Expected a scoped change: " + name)
    for name, source in sources.items():
        Path(name).write_text(source)
    changed = set(subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines())
    if changed != set(BASES):
        raise SystemExit("Unexpected candidate diff paths: " + repr(changed))
    subprocess.run(["git", "diff", "--check"], check=True)
    subprocess.run(["git", "diff", "--stat"], check=True)
    subprocess.run(["git", "diff", "--", *BASES], check=True)

if __name__ == "__main__":
    main()
