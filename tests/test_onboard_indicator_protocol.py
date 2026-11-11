#!/usr/bin/env python3
"""Real-parser tests by default; explicit syntax-only mode is not codec evidence."""
from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--json-include',type=Path,default=ROOT/'.ci-deps/ArduinoJson/src')
    parser.add_argument('--syntax-only',action='store_true')
    args=parser.parse_args()
    compiler=shutil.which('g++')
    if not compiler or (not args.syntax_only and not (args.json_include/'ArduinoJson.h').is_file()):
        raise SystemExit('g++ and actual pinned ArduinoJson headers required for full codec tests')
    with tempfile.TemporaryDirectory() as folder:
        for name,defines in ([('syntax-only',['-DONBOARD_SYNTAX_ONLY'])] if args.syntax_only else [('full',[]),('platform-macro',['-DMAX_INPUT=255'])]):
            binary=Path(folder)/name
            subprocess.run([compiler,'-std=c++11','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined,bounds','-fno-sanitize-recover=all']+defines+
                ['-I',str(ROOT/'include'),'-I',str(args.json_include),str(ROOT/'tests/onboard_indicator_protocol_test.cpp'),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)
            print('PASS: onboard indicator protocol '+name)
if __name__=='__main__':
    main()
