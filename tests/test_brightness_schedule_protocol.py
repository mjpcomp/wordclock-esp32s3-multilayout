#!/usr/bin/env python3
"""Run real ArduinoJson tests normally and with the platform MAX_INPUT macro."""
from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
COMPAT = r'''#include "BrightnessScheduleProtocol.h"
#ifndef MAX_INPUT
#error "Protocol header removed the platform macro"
#endif
static_assert(MAX_INPUT == 255, "Platform macro must remain unchanged");
static_assert(brightnessScheduleProtocol::kMaxInput == 2048, "Protocol limit must remain 2048");
#include "brightness_schedule_protocol_test.cpp"
'''
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json-include', type=Path, default=ROOT / '.ci-deps/ArduinoJson/src')
    args = parser.parse_args()
    compiler = shutil.which('g++')
    if not compiler or not (args.json_include / 'ArduinoJson.h').is_file():
        raise SystemExit('g++ and actual ArduinoJson headers are required; see the pinned CI checkout')
    with tempfile.TemporaryDirectory() as folder:
        temp = Path(folder)
        compatibility = temp / 'macro_compat.cpp'
        compatibility.write_text(COMPAT)
        cases = [('standard', [], ROOT / 'tests/brightness_schedule_protocol_test.cpp'),
                 ('platform-macro', ['-DMAX_INPUT=255'], compatibility)]
        for name, defines, source in cases:
            binary = temp / name
            subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror'] + defines +
                           ['-I', str(args.json_include), '-I', str(ROOT / 'include'),
                            '-I', str(ROOT / 'tests'), str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
            print('PASS: actual ArduinoJson protocol ' + name)
if __name__ == '__main__':
    main()
