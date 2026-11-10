#!/usr/bin/env python3
"""Standalone C++11 model/store/owner checks; no SDK, flash or physical validation."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
def main():
    compiler=shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ is required")
    with tempfile.TemporaryDirectory() as folder:
        binary=Path(folder)/"core"
        subprocess.run([compiler,"-std=c++11","-O2","-Wall","-Wextra","-Werror",
            "-fsanitize=undefined,bounds","-fno-sanitize-recover=all","-I",str(ROOT/"include"),
            str(ROOT/"tests/onboard_indicator_core_test.cpp"),"-o",str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
if __name__=="__main__":
    main()
