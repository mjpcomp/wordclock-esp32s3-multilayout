#!/usr/bin/env python3
"""Refine the validated CSS candidate only inside a disposable CI checkout.

The original source and first candidate are SHA-guarded. Preserve the original
baseline-to-final diff and publish final evidence, never push or flash it.
The first pass made the 320px editor 16.65625px taller despite a shorter page;
this patch targets full-width field wrapping and row gaps, not desktop styling.
"""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "7a44bbd93c4ee6364ed1721377fcf66ea2c626ef:webpage/style.css"
SOURCE_SHA = "5cd97ab05f3b9fb3e030ca9be8b63a869082333e250c2a44fdf0b38c057216df"
BASE_SHA = "592a9be372ebe161536442b7693ec0d109bc510b1a1979f352c9565da0fa9e91"
MOBILE_CSS = """
/* Narrow scheduler fields must not inherit Pure's full-width input rule.
 * Preserve native time controls and existing touch sizes; only row gaps and
 * field widths change. Desktop grouping remains the validated first pass.
 */
@media (width <= 41em) {
    #schedule-editor .pure-form-aligned {
        row-gap: 0.4rem;
    }

    #schedule-editor .pure-control-group > input[type="number"] {
        flex: 0 1 7rem;
        width: 7rem;
    }

    #schedule-editor .pure-control-group > input[type="time"] {
        flex: 0 1 9.5rem;
        width: 9.5rem;
        min-height: var(--app-control-height);
    }

    #schedule-editor .pure-control-group > input[type="range"] {
        flex: 0 1 9rem;
        width: 9rem;
    }
}
"""


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def refine(original, base):
    if digest(original) != SOURCE_SHA or digest(base) != BASE_SHA:
        raise SystemExit("Refusing: source or first CSS candidate differs from review")
    return base.rstrip() + "\n" + MOBILE_CSS


def main():
    original = subprocess.check_output(["git", "show", SOURCE], cwd=ROOT).decode("utf-8")
    target = ROOT / "webpage/style.css"
    base = target.read_bytes().decode("utf-8")
    final = refine(original, base)
    evidence = ROOT / "compact-layout-evidence"
    prior = json.loads((evidence / "source.json").read_text())
    if prior["source_sha256"] != SOURCE_SHA or prior["candidate_sha256"] != BASE_SHA:
        raise SystemExit("Refusing: first-candidate evidence does not match")
    patch = "".join(difflib.unified_diff(original.splitlines(True), final.splitlines(True),
                                      fromfile="a/webpage/style.css", tofile="b/webpage/style.css"))
    target.write_text(final, encoding="utf-8")
    (evidence / "style.css").write_text(final, encoding="utf-8")
    (evidence / "layout.patch").write_text(patch, encoding="utf-8")
    summary = {"scope": "CI checkout mobile-refined CSS candidate only; not promoted or flash-ready",
               "source_sha256": SOURCE_SHA, "base_candidate_sha256": BASE_SHA,
               "candidate_sha256": digest(final)}
    (evidence / "source.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
