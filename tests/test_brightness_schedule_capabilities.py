#!/usr/bin/env python3
"""Use actual pinned ArduinoJson; never substitute a fake parser or device test."""
from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-include", type=Path, default=ROOT / ".ci-deps/ArduinoJson/src")
    args = parser.parse_args()
    compiler = shutil.which("g++")
    if not compiler or not (args.json_include / "ArduinoJson.h").is_file():
        raise SystemExit("g++ and actual ArduinoJson headers are required; use pinned CI checkout")
    count = 0
    with tempfile.TemporaryDirectory() as folder:
        for cache in (0, 1):
            for output in (0, 1):
                for macro in (False, True):
                    binary = Path(folder) / "capabilities"
                    flags = ["-DWORDCLOCK_ENABLE_RENDERER_CACHE=" + str(cache),
                             "-DWORDCLOCK_ENABLE_SCHEDULE_OUTPUT=" + str(output),
                             "-DEXPECT_CACHE=" + str(cache), "-DEXPECT_OUTPUT=" + str(output)]
                    if macro:
                        flags.append("-DMAX_INPUT=255")
                    subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror"] + flags +
                                   ["-I", str(args.json_include), "-I", str(ROOT / "include"),
                                    str(ROOT / "tests/brightness_schedule_capabilities_test.cpp"),
                                    "-o", str(binary)], check=True)
                    subprocess.run([str(binary)], check=True)
                    count += 1
    print("PASS: " + str(count) + " real-JSON capability serializer cases; no device tests")

if __name__ == "__main__":
    main()
