#!/usr/bin/env python3
"""Apply reviewed application anchors only; never write workflow files."""
from pathlib import Path
import sys

MAIN = [
 ('LedStripInterface *activeLedStrip = nullptr;\n',
  'LedStripInterface *activeLedStrip = nullptr;\n\n#include "OnboardDiagnosticApplication.hpp"\n'),
 ('    prefixStatusRuntime::resetDisplay();\n',
  '    prefixStatusRuntime::resetDisplay();\n    onboardDiagnosticApplication::resetFrames();\n'),
 ('    if (utc > 100000000) prefixStatusRuntime::noteTimeSet();\n',
  '    if (utc > 100000000) {\n        prefixStatusRuntime::noteTimeSet();\n        onboardDiagnosticApplication::noteNtp(millis());\n    }\n'),
 ('        settimeofday(&tv, nullptr);\n',
  '        const bool timeLoaded = settimeofday(&tv, nullptr) == 0;\n        if (timeLoaded && tv.tv_sec > 100000000)\n            onboardDiagnosticApplication::noteRtc(millis());\n'),
 ('    network.setup(G.hostname);\n',
  '    onboardDiagnosticApplication::connecting(true);\n    onboardDiagnosticApplication::service();\n    network.setup(G.hostname);\n    onboardDiagnosticApplication::connecting(false);\n'),
 ('    prefixStatusRuntime::service();\n',
  '    prefixStatusRuntime::service();\n    onboardDiagnosticApplication::service();\n'),
]
SUITES = 'clock_test_foundation button_isolation english_renderer led_factory brightness_isolation i2c_isolation rtc_isolation build_evidence prefix_status_policy onboard_diagnostic_model onboard_diagnostic_sink onboard_diagnostic_runtime'

def transform(text, edits):
 for old,new in edits:
  if text.count(old) != 1 or new in text:
   raise ValueError('Missing, repeated or already applied anchor: '+repr(old))
  text=text.replace(old,new,1)
 return text

def self_test():
 before='\n'.join(old for old,_ in MAIN)
 after=transform(before,MAIN)
 for _,new in MAIN: assert new in after
 for broken in (after,before+MAIN[0][0],before.replace(MAIN[0][0],'',1)):
  try: transform(broken,MAIN)
  except ValueError: pass
  else: raise AssertionError('Unsafe input accepted')
 print('PASS: application anchors and repeat/missing/duplicate refusal; fixture test only.')

def main():
 if '--self-test' in sys.argv: self_test(); return
 ci=Path('.github/workflows/isolated-build.yml').read_text()
 if ci.count('for suite in '+SUITES+'; do') != 1:
  raise ValueError('Twelve-suite CI must already be committed; refusing application edit')
 path=Path('src/WordClock.cpp')
 output=transform(path.read_text(),MAIN)
 path.write_text(output)
 print('Applied reviewed onboard application hooks; workflow files were not written.')
if __name__=='__main__': main()
