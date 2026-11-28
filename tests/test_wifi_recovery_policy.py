#!/usr/bin/env python3
# Host-only policy checks. No Wi-Fi SDK, network, router, device or flash validation.
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
        binary = Path(folder) / "wifi-recovery-policy"
        subprocess.run([
            compiler, "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all",
            "-I", str(ROOT / "include"),
            str(ROOT / "tests/wifi_recovery_policy_test.cpp"),
            "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print("PASS: Wi-Fi recovery policy model only; no SDK, network, router or device validation.")

if __name__ == "__main__":
    main()
