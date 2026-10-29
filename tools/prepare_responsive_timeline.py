#!/usr/bin/env python3
"""Stage responsive SVG geometry only in CI; preserve reviewed density CSS.

Pinned source and single-anchor guards refuse unrelated edits. Resize changes
presentation only: no persistence, new socket, source promotion or board upload.
"""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "7a44bbd93c4ee6364ed1721377fcf66ea2c626ef:webpage/schedule-timeline-view.js"
CSS_SHA = "f3c5c55b4bcb06150b48b17752c6d37c8f6cdb4ec4713307c2c7bbdcfcab326c"
GEOMETRY = """
        // CSS-pixel geometry keeps axes legible; hidden panels retain valid size.
        const hostWindow = svg.ownerDocument.defaultView;
        let dimensions = { width: 1000, height: 300, plotLeft: 65, plotTop: 25, plotWidth: 880, plotHeight: 230, labelY: 280 };
        let resizeObserver = null;
        let frameToken = null;
        function fitGeometry() {
            if (destroyed || typeof svg.getBoundingClientRect !== "function") return false;
            const width = Math.floor(svg.getBoundingClientRect().width);
            if (!Number.isFinite(width) || width < 120) return false;
            const height = width < 600 ? 224 : 248;
            if (dimensions.width === width && dimensions.height === height) return false;
            cancel(); revision += 1;
            dimensions = { width: width, height: height, plotLeft: 48, plotTop: 24, plotWidth: width - 88, plotHeight: height - 78, labelY: height - 10 };
            svg.style.height = height + "px";
            svg.setAttribute("viewBox", "0 0 " + width + " " + height);
            return true;
        }
        function queueFit() {
            if (destroyed || frameToken !== null) return;
            if (hostWindow && typeof hostWindow.requestAnimationFrame === "function" && typeof hostWindow.cancelAnimationFrame === "function") {
                frameToken = hostWindow.requestAnimationFrame(function() {
                    frameToken = null;
                    if (fitGeometry() && current) paint(current, selected);
                });
            } else if (fitGeometry() && current) paint(current, selected);
        }
        function tickStep() {
            const minimum = right - left > 500 ? 180 : 30;
            const needed = Math.max(minimum, (right - left) * 80 / dimensions.plotWidth);
            return [30, 60, 120, 180, 240, 360, 480, 720, 1440].find(function(step) { return step >= needed; }) || 1440;
        }
""".replace("    ", "\t")
INIT = """
        fitGeometry();
        if (hostWindow && typeof hostWindow.addEventListener === "function") hostWindow.addEventListener("resize", queueFit);
        if (hostWindow && typeof hostWindow.ResizeObserver === "function") {
            resizeObserver = new hostWindow.ResizeObserver(queueFit);
            resizeObserver.observe(svg);
        }""".replace("    ", "\t")
CLEANUP = """
                if (resizeObserver) resizeObserver.disconnect();
                if (hostWindow && typeof hostWindow.removeEventListener === "function") hostWindow.removeEventListener("resize", queueFit);
                if (frameToken !== null && hostWindow) hostWindow.cancelAnimationFrame(frameToken);
                frameToken = null;""".replace("    ", "\t")
CHANGES = [
    ('touch: svg.style.touchAction }', 'touch: svg.style.touchAction, height: svg.style.height }'),
    ('\t\tlet revision = 0;', '\t\tlet revision = 0;' + GEOMETRY),
    ('return 65 + (minute - left) * 880 / (right - left);', 'return dimensions.plotLeft + (minute - left) * dimensions.plotWidth / (right - left);'),
    ('return 255 - level * 230 / 1000;', 'return dimensions.plotTop + dimensions.plotHeight - level * dimensions.plotHeight / 1000;'),
    ('x1: 65, y1: positionY(level), x2: 945', 'x1: dimensions.plotLeft, y1: positionY(level), x2: dimensions.plotLeft + dimensions.plotWidth'),
    ('"x": 55, "y": positionY(level)', '"x": dimensions.plotLeft - 10, "y": positionY(level)'),
    ('const step = right - left > 500 ? 180 : 30;', 'const step = tickStep();'),
    ('"y": 280, "text-anchor": "middle"', '"y": dimensions.labelY, "text-anchor": "middle"'),
    ('geometry.handles.forEach(function(handle) {', 'geometry.handles.forEach(function(handle) {\n\t\t\t\t// Keep touch areas below every visible handle, including later events.\n\t\t\t\tnode("circle", { "cx": positionX(handle.minute), "cy": positionY(handle.targetTenths), "r": 22, "data-index": handle.eventIndex, "data-hit-kind": handle.kind, "aria-hidden": "true", fill: "transparent", stroke: "none" });\n\t\t\t});\n\t\t\tgeometry.handles.forEach(function(handle) {'),
    ('kind: target.getAttribute("data-kind")', 'kind: target.getAttribute("data-kind") || target.getAttribute("data-hit-kind")'),
    ('svg.style.touchAction = "none";', 'svg.style.touchAction = "none";' + INIT),
    ('(local.x - 65) * (right - left) / 880', '(local.x - dimensions.plotLeft) * (right - left) / dimensions.plotWidth'),
    ('(255 - local.y) * 1000 / 230', '(dimensions.plotTop + dimensions.plotHeight - local.y) * 1000 / dimensions.plotHeight'),
    ('left = begin; right = end; editable = allowEditing === true;', 'left = begin; right = end; editable = allowEditing === true;\n\t\t\t\tfitGeometry();'),
    ('cancel(); destroyed = true;', 'cancel(); destroyed = true;' + CLEANUP),
    ('svg.style.touchAction = previous.touch;', 'svg.style.touchAction = previous.touch;\n\t\t\t\tsvg.style.height = previous.height || "";')
]


def transform(source):
    result = source
    for old, new in CHANGES:
        if result.count(old) != 1:
            raise ValueError("Renderer anchor missing or ambiguous: " + old[:70])
        result = result.replace(old, new)
    return result


def main():
    if hashlib.sha256((ROOT / "webpage/style.css").read_bytes()).hexdigest() != CSS_SHA:
        raise SystemExit("Refusing: reviewed density CSS differs")
    target = ROOT / "webpage/schedule-timeline-view.js"
    original = subprocess.check_output(["git", "show", SOURCE], cwd=ROOT)
    if target.read_bytes() != original:
        raise SystemExit("Refusing: renderer differs from reviewed checkpoint")
    result = transform(original.decode("utf-8"))
    target.write_text(result, encoding="utf-8")
    evidence = ROOT / "compact-layout-evidence"
    (evidence / "schedule-timeline-view.js").write_text(result, encoding="utf-8")
    summary = {"scope": "CI renderer candidate only; not promoted or flash-ready",
               "source_sha256": hashlib.sha256(original).hexdigest(),
               "candidate_sha256": hashlib.sha256(result.encode("utf-8")).hexdigest(),
               "density_css_sha256": CSS_SHA}
    (evidence / "timeline-source.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
