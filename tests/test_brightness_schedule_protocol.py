#!/usr/bin/env python3
"""Run the actual ArduinoJson protocol tests; never silently substitute a fake parser."""
from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json-include', type=Path, default=ROOT / '.ci-deps/ArduinoJson/src')
    args = parser.parse_args()
    compiler = shutil.which('g++')
    if not compiler or not (args.json_include / 'ArduinoJson.h').is_file():
        raise SystemExit('g++ and actual ArduinoJson headers are required; see the pinned CI checkout')
    with tempfile.TemporaryDirectory() as folder:
        binary = Path(folder) / 'protocol'
        subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                        '-I', str(args.json_include), '-I', str(ROOT / 'include'),
                        str(ROOT / 'tests/brightness_schedule_protocol_test.cpp'),
                        '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('PASS: actual ArduinoJson brightness-schedule protocol suite')
if __name__ == '__main__':
    main()
