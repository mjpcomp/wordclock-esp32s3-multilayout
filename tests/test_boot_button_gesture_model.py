#!/usr/bin/env python3
"""Standalone gesture policy checks; no Arduino, GPIO, storage or Wi-Fi."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ is required")
    with tempfile.TemporaryDirectory() as folder:
        binary = Path(folder) / "boot-gesture"
        subprocess.run([
            compiler, "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all",
            "-I", str(ROOT / "include"),
            str(ROOT / "tests/boot_button_gesture_model_test.cpp"),
            "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print("PASS: BOOT gesture model only; no GPIO, SDK, persistence or network validation.")

if __name__ == "__main__":
    main()
