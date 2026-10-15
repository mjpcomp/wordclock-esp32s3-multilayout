#!/usr/bin/env python3
"""Host-check test capabilities and virtual backend; not full GPIO isolation."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
MOCK = r"""#pragma once
#include <stdint.h>
struct HsbColor { uint8_t value; explicit HsbColor(uint8_t v):value(v){} };
struct RgbColor {
 uint8_t R,G,B;
 RgbColor(uint8_t v=0):R(v),G(v),B(v){}
 RgbColor(uint8_t r,uint8_t g,uint8_t b):R(r),G(g),B(b){}
 RgbColor(HsbColor h):R(h.value),G(h.value),B(h.value){}
};
struct RgbwColor {
 uint8_t R,G,B,W;
 RgbwColor(uint8_t v=0):R(v),G(v),B(v),W(v){}
 RgbwColor(uint8_t r,uint8_t g,uint8_t b,uint8_t w):R(r),G(g),B(b),W(w){}
};
"""
TEST = r"""#include "ClockTestPolicy.h"
#include "VirtualLedStripAdapter.h"
#include <cassert>
using namespace clockTestPolicy;
int main() {
 static_assert(MODE==EXPECT_MODE,"mode/default");
 static_assert(MATRIX_OUTPUT==(EXPECT_MODE==0),"matrix gate");
 static_assert(PREFIX_OUTPUT==((EXPECT_MODE==0) && WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL),"prefix gate");
 static_assert(ONBOARD_OUTPUT==((EXPECT_MODE!=0) || WORDCLOCK_ENABLE_ONBOARD_STATUS_LED),"onboard exception");
 static_assert(BUTTON_INPUTS==(EXPECT_MODE==0) && BRIGHTNESS_SENSORS==(EXPECT_MODE==0),"input gates");
 static_assert(RTC==(EXPECT_MODE!=1),"RTC gate");
 for(unsigned pin=0;pin<256;++pin)
  assert(permitsOnboardPin(pin)==(ONBOARD_OUTPUT && pin==48));
 for(unsigned sda=0;sda<256;++sda)for(unsigned scl=0;scl<256;++scl)
  assert(permitsI2cPins(sda,scl)==(EXPECT_MODE==0 || (EXPECT_MODE==2 && sda==8 && scl==9)));
 for(unsigned a=0;a<256;++a)
  assert(permitsI2cAddress(a)==(EXPECT_MODE==0 || (EXPECT_MODE==2 && a==0x68)));
 for(unsigned n:{0,1,114,300,1200})for(bool rgbw:{false,true}) {
  VirtualLedStripAdapter backend(n,rgbw);
  LedStripInterface &base=backend;
  assert(base.isVirtual());
  assert(base.diagnostics().logicalPixels==n && base.diagnostics().countersAvailable);
  base.show();base.show();
  assert(base.diagnostics().showRequests==2 && base.diagnostics().changedFrames==1);
  assert(!base.setStatusPixel(RgbColor(7,8,9)));
  assert(base.getPixel(n).R==0);
  base.setRgbPixel(n,HsbColor(7));base.clearPixel(UINT16_MAX);
  if(n) {
   base.setRgbPixel(0,HsbColor(17));assert(base.getPixel(0).R==17);
   base.setRgbwPixel(n-1,RgbwColor(1,2,3,4));
   assert(backend.getRgbwPixel(n-1).W==(rgbw?4:0));
   base.show();assert(base.diagnostics().changedFrames==2);
   base.show();assert(base.diagnostics().changedFrames==2);
   for(unsigned i=0;i<n;++i)base.clearPixel(i);
   base.show();assert(base.diagnostics().changedFrames==3);
   assert(base.getPixel(0).R==0);
  }
 }
}
"""

def main():
    compiler = shutil.which('g++')
    if not compiler:
        raise SystemExit('g++ is required.')
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        for name in ('ClockTestPolicy.h', 'VirtualLedStripAdapter.h',
                     'LedStripInterface.h', 'LedStatusPrefix.h'):
            shutil.copyfile(ROOT / 'include' / name, work / name)
        for name, content in {'Arduino.h':'#pragma once\n#include <stdint.h>\n',
                              'WordClockState.h':'#pragma once\n',
                              'NeoPixelBus.h':MOCK, 'test.cpp':TEST}.items():
            (work / name).write_text(content)
        for mode, onboard, prefix in ((None,0,0),(0,1,1),(1,0,1),(2,0,1)):
            executable = work / ('test-' + str(mode))
            args = [compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=undefined,bounds', '-DEXPECT_MODE='+str(mode or 0),
                    '-DWORDCLOCK_ENABLE_ONBOARD_STATUS_LED='+str(onboard),
                    '-DWORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL='+str(prefix),
                    '-I'+str(work), str(work / 'test.cpp'), '-o', str(executable)]
            if mode is not None:
                args.insert(1, '-DWORDCLOCK_TEST_MODE='+str(mode))
            subprocess.run(args, check=True)
            subprocess.run([str(executable)], check=True)
        bad = subprocess.run([compiler, '-std=c++11', '-DWORDCLOCK_TEST_MODE=3',
                              '-DEXPECT_MODE=3', '-I'+str(work), '-c',
                              str(work / 'test.cpp'), '-o', str(work / 'bad.o')],
                             capture_output=True, text=True)
        assert bad.returncode != 0 and 'must be 0, 1 or 2' in bad.stderr
    print('PASS: mode/default capabilities, onboard48 exception, RTC whitelist and virtual frames/counters.')
if __name__ == '__main__':
    main()
