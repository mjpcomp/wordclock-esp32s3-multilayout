#!/usr/bin/env python3
"""Structural asset checks, not browser interaction or physical output tests."""
from pathlib import Path
from html.parser import HTMLParser
from collections import Counter
import argparse
import gzip
import subprocess

SLOTS = set("timeline status capabilities changes start end target level-range curve all-day add apply remove save reload reset discard use-remote keep-draft".split())
MODULES = ["schedule-model", "schedule-client", "schedule-timeline-adapter", "schedule-timeline-view", "schedule-capabilities", "schedule-page-controller", "schedule-page-binding", "schedule-socket-bridge"]
class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.slots=[]; self.scripts=[]; self.labels=[]
    def handle_starttag(self, tag, attributes):
        attrs=dict(attributes)
        if "id" in attrs: self.ids.append(attrs["id"])
        if "data-schedule" in attrs:
            self.slots.append(attrs["data-schedule"])
            assert all(word not in attrs.get("id", "") for word in ("brightness", "slider", "transition"))
        if tag == "label" and "for" in attrs: self.labels.append(attrs["for"])
        if tag == "script" and "src" in attrs: self.scripts.append(attrs["src"])

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--built", action="store_true"); args=parser.parse_args()
    html=gzip.decompress(Path(".pio/build/webpage/index.html.gz").read_bytes()).decode() if args.built else Path("webpage/index.html").read_text()
    page=Page(); page.feed(html)
    assert all(count == 1 for count in Counter(page.ids).values()), "Duplicate IDs"
    assert set(page.slots) == SLOTS and len(page.slots) == len(SLOTS), "Missing/duplicate scheduler slots"
    assert "schedule-editor" in page.ids
    assert all(identifier in page.ids for identifier in page.labels if identifier.startswith("schedule-"))
    if args.built:
        assert not any(value.startswith("./") for value in page.scripts), "Local scripts were not inlined"
        for marker in ("createWordclockSchedulePage", "createWordclockScheduleSocketBridge", "brightness-schedule"):
            assert marker in html, "Missing embedded module: " + marker
    else:
        positions=[page.scripts.index("./" + name + ".js") for name in MODULES] + [page.scripts.index("./script.js")]
        assert positions == sorted(positions), "Script dependency order"
        script=Path("webpage/script.js").read_text()
        assert script.count("new WebSocket(") == 1, "Unexpected second socket"
        assert script.count("if (socket !== websocket) return;") == 4
        assert "if (scheduleBridge) scheduleBridge.attach(socket);" in script
        for name in ("webpage/script.js", "Gruntfile.js"):
            subprocess.run(["node", "--check", name], check=True)
    print("PASS: scheduler " + ("embedded asset" if args.built else "source structure") + " checks; no browser/device validation")
if __name__ == "__main__":
    main()
