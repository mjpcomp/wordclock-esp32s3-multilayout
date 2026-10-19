#!/usr/bin/env python3
"""Mocked core API checks only; not a target compile or electrical validation."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CPP = r"""#include "OnboardDiagnosticSink.h"
#include <cassert>
#if WORDCLOCK_TEST_MODE != 0
int main() {
 onboardDiagnostic::Gpio48Sink sink;
 assert(sink.service(0,255,7,3)); assert(writes==1 && pinSeen==48);
 assert(rSeen==20 && gSeen==7 && bSeen==3);
 assert(!sink.service(19,0,0,0)); assert(writes==1);
 assert(sink.service(20,0,0,0)); assert(writes==2);
 assert(!sink.service(40,0,0,0));
 assert(!sink.service(59,1,2,3));
 assert(sink.service(60,1,2,3));
 assert(!sink.service(80,1,2,3));
 onboardDiagnostic::Gpio48Sink wrap;
 const uint32_t start=UINT32_MAX-9;
 assert(wrap.service(start,1,0,0));
 assert(!wrap.service(uint32_t(start+19u),0,0,1));
 assert(wrap.service(uint32_t(start+20u),0,0,1));
 assert(pinSeen==48 && bSeen==1);
}
#else
int main() { static_assert(!clockTestPolicy::IS_TEST,"normal mode"); }
#endif
"""

def main():
 compiler=shutil.which('g++')
 if not compiler: raise SystemExit('g++ is required')
 with tempfile.TemporaryDirectory() as folder:
  work=Path(folder)
  for name in ('OnboardDiagnosticSink.h','ClockTestPolicy.h'):
   shutil.copyfile(ROOT/'include'/name,work/name)
  (work/'LedStatusPrefix.h').write_text('#pragma once\n#define WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL 0\n')
  (work/'test.cpp').write_text(CPP)
  for mode in (0,1,2):
   for enabled in (0,1):
    for name in ('Arduino.h','esp32-hal-rgb-led.h'):
     (work/name).unlink(missing_ok=True)
    if mode:
     (work/'Arduino.h').write_text('#pragma once\n#include <stdint.h>\n')
     (work/'esp32-hal-rgb-led.h').write_text(
      '#pragma once\nstatic unsigned writes=0;\n'
      'static uint8_t pinSeen,rSeen,gSeen,bSeen;\n'
      'inline void neopixelWrite(uint8_t p,uint8_t r,uint8_t g,uint8_t b)'
      '{++writes;pinSeen=p;rSeen=r;gSeen=g;bSeen=b;}\n')
    args=[compiler,'-std=c++11','-Wall','-Wextra','-Werror',
     '-fsanitize=undefined,bounds','-fno-sanitize-recover=all',
     '-DESP32','-DCONFIG_IDF_TARGET_ESP32S3',
     '-DWORDCLOCK_TEST_MODE='+str(mode),
     '-DWORDCLOCK_ENABLE_ONBOARD_STATUS_LED='+str(enabled),
     '-I'+str(work),str(work/'test.cpp'),'-o',str(work/'test')]
    subprocess.run(args,check=True)
    subprocess.run([str(work/'test')],check=True)
  bad=subprocess.run([compiler,'-std=c++11','-DWORDCLOCK_TEST_MODE=1',
   '-I'+str(work),'-c',str(work/'test.cpp'),'-o',str(work/'bad.o')],capture_output=True,text=True)
  assert bad.returncode and 'requires ESP32-S3' in bad.stderr
 print('PASS: six mode/flag combinations; normal mode has no Arduino/HAL headers; GPIO48, clamp, cache, 20ms boundaries, wrap and wrong-target rejection.')

if __name__=='__main__': main()
