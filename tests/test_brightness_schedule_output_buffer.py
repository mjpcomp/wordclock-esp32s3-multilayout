#!/usr/bin/env python3
"""Pure output-buffer and recording-sink tests; not physical/backend validation."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]

def main():
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ required for output-buffer tests")
    with tempfile.TemporaryDirectory() as d:
        binary = Path(d) / "output-buffer"
        subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all",
                        "-I", str(ROOT / "include"),
                        str(ROOT / "tests/brightness_schedule_output_buffer_test.cpp"),
                        "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print("PASS: dormant output buffer; exhaustive scaling and 16 recording-sink configurations")

if __name__ == "__main__":
    main()
