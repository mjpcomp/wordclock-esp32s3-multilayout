#!/usr/bin/env python3
"""Apply one reviewed CSS candidate in an isolated checkout, never push it.

SHA guards preserve unrelated styling and the existing language contrast fix.
This changes only webpage/style.css and writes review evidence. The generated
page must pass Grunt/browser checks before any separate source promotion.
"""
from pathlib import Path
import difflib
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SOURCE = "5cd97ab05f3b9fb3e030ca9be8b63a869082333e250c2a44fdf0b38c057216df"
EXPECTED_RESULT = "592a9be372ebe161536442b7693ec0d109bc510b1a1979f352c9565da0fa9e91"
CHANGES = [('    margin-bottom: 15px;\n    margin-top: 0;\n    line-height: 1.45;',
  '    margin-bottom: 10px;\n    margin-top: 0;\n    line-height: 1.45;'),
 ('    padding: 0.85em 1em;', '    padding: 0.65em 0.9em;'),
 ('    padding: .7em;', '    padding: .5em;'),
 ('    min-height: 76px;', '    min-height: 58px;'),
 ('    padding: 1.1em;\n    margin: 1em;', '    padding: 0.75rem;\n    margin: 0.625rem;'),
 ('    margin-top: -3px;\n'
  '    border-bottom: 1px solid var(--app-border);\n'
  '    padding-bottom: 0.6em;\n'
  '    margin-left: -1em;\n'
  '    margin-right: -1em;\n'
  '    padding-right: 1em;\n'
  '    padding-left: 1em;',
  '    margin: 0 -0.75rem 0.65rem;\n'
  '    border-bottom: 1px solid var(--app-border);\n'
  '    padding-bottom: 0.4rem;\n'
  '    padding-right: 0.75rem;\n'
  '    padding-left: 0.75rem;'),
 ('    grid-template-rows: repeat(2, 50px);\n    gap: 10px;',
  '    grid-template-rows: repeat(2, 44px);\n    gap: 8px;'),
 ('        margin: 0.75em;\n        padding: 0.9em;',
  '        margin: 0.5rem;\n        padding: 0.625rem;'),
 ('        min-height: 70px;', '        min-height: 58px;')]
EXTRA_CSS = """
/* Compact form layout keeps controls at their existing 44px minimum height.
 * The 320px baseline overflow survives hiding the entire schedule editor: the
 * 300px picker must fit its card without clipping or CSS-scaling its hit area.
 * General density and desktop grouping are independent of chart responsiveness.
 */
.main,
.main > .pure-g,
.section,
.box {
    min-width: 0;
}

.pure-form-aligned .pure-control-group {
    margin-bottom: 0.45rem;
}

.pure-form-aligned .pure-controls {
    margin-top: 0.75rem;
}

#schedule-editor .pure-form-aligned {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 0.65rem 1rem;
}

#schedule-editor .pure-control-group {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem 0.5rem;
    min-width: 0;
    margin: 0;
}

#schedule-editor .pure-control-group > label {
    width: auto;
    margin: 0;
    text-align: left;
}

#schedule-editor .pure-control-group > input,
#schedule-editor .pure-control-group > select {
    box-sizing: border-box;
    min-width: 0;
    max-width: 100%;
}

#schedule-editor .pure-controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.25rem 0 0;
}

#schedule-editor .pure-form-aligned > p {
    margin: 0;
}

@media (width >= 60em) {
    /* Reuse the existing three color-control groups without changing DOM order
     * or introducing a blank placeholder for the future virtual face.
     */
    .box-color {
        display: grid;
        grid-template-columns: minmax(0, 302px) minmax(0, 300px);
        justify-content: center;
        align-items: center;
        gap: 1rem 1.5rem;
    }

    .box-color > .mode-color-form {
        grid-column: 1;
        grid-row: 1;
        align-self: end;
        min-width: 0;
        max-width: 100%;
        margin: 0;
    }

    .box-color > .color-picker {
        grid-column: 2;
        grid-row: 1 / span 2;
    }

    .box-color > .swatch-grid {
        grid-column: 1;
        grid-row: 2;
        align-self: start;
        margin: 0;
    }

    #schedule-editor .pure-form-aligned {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    #schedule-editor .pure-form-aligned > p,
    #schedule-editor .pure-controls {
        grid-column: 1 / -1;
    }
}

@media (width <= 41em) {
    .box h2 {
        margin-left: -0.625rem;
        margin-right: -0.625rem;
        padding-right: 0.625rem;
        padding-left: 0.625rem;
    }
}

@media (width <= 22.5em) {
    /* Preserve the actual 300px iro geometry at the supported 320px viewport.
     * Do not conceal overflow or scale just the SVG without updating hit tests.
     */
    .box-color {
        margin-right: 0.25rem;
        margin-left: 0.25rem;
        padding-right: 0.25rem;
        padding-left: 0.25rem;
    }
}
"""


def main():
    target = ROOT / "webpage/style.css"
    original = target.read_text()
    if hashlib.sha256(original.encode()).hexdigest() != EXPECTED_SOURCE:
        raise SystemExit("Refusing: stylesheet differs from the reviewed source")
    candidate = original
    for old, new in CHANGES:
        if candidate.count(old) != 1:
            raise SystemExit("Refusing: a reviewed CSS anchor is missing or ambiguous")
        candidate = candidate.replace(old, new)
    candidate = candidate.rstrip() + "\n" + EXTRA_CSS
    if hashlib.sha256(candidate.encode()).hexdigest() != EXPECTED_RESULT:
        raise SystemExit("Refusing: generated CSS differs from the reviewed result")
    evidence = ROOT / "compact-layout-evidence"
    evidence.mkdir(exist_ok=True)
    patch = "".join(difflib.unified_diff(original.splitlines(True), candidate.splitlines(True),
                                      fromfile="a/webpage/style.css", tofile="b/webpage/style.css"))
    target.write_text(candidate)
    (evidence / "style.css").write_text(candidate)
    (evidence / "layout.patch").write_text(patch)
    summary = {"scope": "CI checkout CSS candidate only; not promoted or flash-ready",
               "source_sha256": EXPECTED_SOURCE, "candidate_sha256": EXPECTED_RESULT}
    (evidence / "source.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
