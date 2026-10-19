#!/usr/bin/env python3
"""Apply only reviewed onboard application/CI anchors; refuse partial repeats."""
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
SUITES = 'clock_test_foundation button_isolation english_renderer led_factory brightness_isolation i2c_isolation rtc_isolation build_evidence prefix_status_policy onboard_diagnostic_model'
CI = [('Run ten host suites','Run twelve host suites'),
      ('for suite in '+SUITES+'; do',
       'for suite in '+SUITES+' onboard_diagnostic_sink onboard_diagnostic_runtime; do')]

def transform(text, edits):
 for old,new in edits:
  if text.count(old) != 1 or new in text:
   raise ValueError('Missing, repeated or already applied anchor: '+repr(old))
  text=text.replace(old,new,1)
 return text

def self_test():
 for edits in (MAIN,CI):
  before='\n'.join(old for old,_ in edits)
  after=transform(before,edits)
  for _,new in edits: assert new in after
  for broken in (after,before+edits[0][0],before.replace(edits[0][0],'',1)):
   try: transform(broken,edits)
   except ValueError: pass
   else: raise AssertionError('Unsafe input accepted')
 print('PASS: application/CI anchors, duplicate/missing anchor refusal and repeat refusal; fixture test only.')

def main():
 if '--self-test' in sys.argv: self_test(); return
 paths=[Path('src/WordClock.cpp'),Path('.github/workflows/isolated-build.yml')]
 # Compute both outputs before modifying either file.
 outputs=[transform(p.read_text(),edits) for p,edits in zip(paths,(MAIN,CI))]
 for p,text in zip(paths,outputs): p.write_text(text)
 print('Applied reviewed onboard hooks and twelve-suite CI registration.')
if __name__=='__main__': main()
