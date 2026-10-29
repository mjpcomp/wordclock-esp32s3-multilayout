#!/usr/bin/env python3
"""Compare all JS sample masks with the real C++ host adapter test.

This executes the adapter with host mocks, not ClockWork or ESP32 output.
The existing C++ fixture defines the local sample-time phrase policy.
"""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    compiler, node = shutil.which("g++"), shutil.which("node")
    if not compiler or not node:
        raise SystemExit("g++ and node are required")
    with tempfile.TemporaryDirectory() as folder:
        executable = Path(folder) / "mirc0-preview-parity"
        subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-parameter", "-fsanitize=undefined,bounds",
                        "-I" + str(ROOT / "include/WordClockTypes"),
                        str(ROOT / "tests/test_mirc0_layout.cpp"), "-o", str(executable)], check=True)
        lines = subprocess.check_output([str(executable)], text=True).splitlines()
    script = "const p=require(process.argv[1]);console.log(JSON.stringify(Array.from({length:1440},(_,n)=>p.mask(Math.floor(n/60),n%60))));"
    masks = json.loads(subprocess.check_output([node, "-e", script, str(ROOT / "webpage/mirc0-preview.js")], text=True))
    assert len(lines) == len(masks) == 1440
    for number, (line, actual) in enumerate(zip(lines, masks)):
        hour, minute, values = line.split(":")
        assert int(hour) == number // 60 and int(minute) == number % 60
        expected = sorted({int(value) for value in values.split(",") if value})
        assert actual == expected, (hour, minute, actual, expected)
    print(json.dumps({"status": "PASS", "minutes": 1440,
                      "scope": "JS versus real host adapter/sample policy; not full firmware, browser or hardware"}))


if __name__ == "__main__":
    main()
