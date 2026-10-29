#!/usr/bin/env python3
"""Check the physical preview reference, not device rendering or LED output.

The fixture is transcribed from the user-approved Mirc0. photograph. Every
letter, including filler cells, must match the adapter's documented face.
Logical indices remain serpentine; the four dots sit below, not at corners.
Run from any directory with Python; no third-party packages are required.
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def verify(reference, source):
    rows = reference["rows"]
    assert reference["layout_id"] == 36
    assert reference["creator"] == "Mirc0."
    assert len(rows) == 10 and all(len(row) == 11 for row in rows)
    documented = [re.sub(r"\s+", "", match.group(1)) for match in
                  re.finditer(r"^\s*\*\s*\d+\s*\|\s*(.*?)\s*$", source, re.M)]
    assert documented == rows, "Photo fixture differs from adapter face"
    dots = reference["minute_dots"]
    assert dots["logical_indices"] == [110, 111, 112, 113]
    assert dots["placement"] == "centered horizontal row below the letter matrix"
    cells = {}
    for index in range(110):
        row, column = divmod(index, 11)
        column = 10 - column if row % 2 else column
        assert (row, column) not in cells
        cells[row, column] = index
    assert len(cells) == 110
    # The photographed IT IS / TEN TO / NINE pattern checks both row directions.
    lit = {0, 1, 3, 4, 33, 34, 36, 37, 38, 51, 52, 53, 54}
    phrase = "".join(rows[row][column] for row, column in sorted(cells)
                     if cells[row, column] in lit)
    assert phrase == "ITISTENTONINE", phrase
    return {"cells": len(cells), "dots": len(dots["logical_indices"])}


def main():
    reference = json.loads((ROOT / "tests/fixtures/mirc0-physical-face.json").read_text())
    source = (ROOT / "include/WordClockTypes/EN10x11.mirc0.hpp").read_text()
    result = verify(reference, source)
    print(json.dumps({"status": "PASS", **result,
                      "scope": "physical-face reference only; not firmware or browser execution"}))


if __name__ == "__main__":
    main()
