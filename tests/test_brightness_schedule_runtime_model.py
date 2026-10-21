#!/usr/bin/env python3
"""Host tests for dormant runtime decisions/logical pixels, not physical LED validation."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
def main():
    compiler = shutil.which('g++')
    if not compiler:
        raise SystemExit('g++ required for runtime-model tests')
    with tempfile.TemporaryDirectory() as folder:
        binary = Path(folder) / 'runtime-model'
        subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        '-I', str(ROOT / 'include'),
                        str(ROOT / 'tests/brightness_schedule_runtime_model_test.cpp'),
                        '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('PASS: runtime decisions and unscaled RGB/RGBW cache; host model only')
if __name__ == '__main__':
    main()
