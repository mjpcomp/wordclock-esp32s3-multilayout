#!/usr/bin/env python3
"""Compile and execute the hardware-independent schedule evaluator tests."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
def main():
    compiler = shutil.which('g++')
    if not compiler:
        raise SystemExit('g++ is required for brightness-schedule host tests')
    with tempfile.TemporaryDirectory() as temp:
        binary = Path(temp) / 'brightness_schedule_test'
        subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                        '-I', str(ROOT / 'include'),
                        str(ROOT / 'tests/brightness_schedule_test.cpp'),
                        '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('PASS: hardware-independent brightness schedule tests')
if __name__ == '__main__':
    main()
