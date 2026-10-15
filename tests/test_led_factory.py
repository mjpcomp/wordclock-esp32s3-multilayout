#!/usr/bin/env python3
"""Host factory selection/cache tests, not a target build or full GPIO isolation."""
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
CPP = r"""#include "ClockTestPolicy.h"
#include "LedStripInterface.h"
#include <cassert>
#include <initializer_list>
constexpr uint16_t MAX_LED_COUNT=300;
constexpr uint8_t LED_PIN=3, Grbw=4;
struct{uint8_t buildTypeDef=1;struct{uint8_t led=LED_PIN;}hardwarePins;}G;
uint8_t getLedsPerLetter(uint8_t multiplier){return multiplier;}
struct NeoMultiFeature{static void setColortype(uint8_t){}};
unsigned created=0,removed=0,pinWrites=0;
uint16_t lastCount=0;uint8_t lastPin=0;int lastMethod=-1;bool lastWhite=false;
#if WORDCLOCK_TEST_MODE == 0
constexpr int OUTPUT=1;
void pinMode(uint8_t,int){++pinWrites;}
struct Neo800KbpsMethod{static constexpr int id=0;};
struct NeoEsp8266BitBangWs2812xMethod{static constexpr int id=1;};
struct NeoEsp32Rmt0Ws2812xMethod{static constexpr int id=2;};
template<class Method,bool White>class Physical:public LedStripInterface{
public:
 explicit Physical(uint16_t n,uint8_t p=LED_PIN){++created;lastCount=n;lastPin=p;lastMethod=Method::id;lastWhite=White;}
 void setRgbPixel(uint16_t,HsbColor)override{}
 void setRgbwPixel(uint16_t,RgbwColor)override{}
 RgbColor getPixel(uint16_t)override{return RgbColor(0);}
 void clearPixel(uint16_t)override{}
 void show()override{}
};
template<class M>using RgbLedStripAdapter=Physical<M,false>;
template<class M>using RgbwLedStripAdapter=Physical<M,true>;
#endif
// No physical types or pinMode exist in this translation unit in test modes.
LedStripInterface*activeLedStrip=nullptr;
uint8_t activeLedPin=UINT8_MAX,activeLedColorType=UINT8_MAX;
uint16_t activeLedCount=0;
void deleteActiveLedStrip(){if(activeLedStrip){++removed;delete activeLedStrip;activeLedStrip=nullptr;}}
class ClockWork{public:void initLedStrip(uint8_t);};
#include "ClockWorkLedFactory.hpp"
int main(){ClockWork clock;
 for(uint8_t multiplier:{1,2,4})for(uint8_t color:{uint8_t(0),Grbw}){
  G.buildTypeDef=multiplier;clock.initLedStrip(color);
  assert(activeLedStrip);activeLedStrip->setRgbPixel(0,HsbColor(17));
  activeLedStrip->show();
  for(unsigned pin=0;pin<256;++pin){
   G.hardwarePins.led=pin;
   auto*previous=activeLedStrip;unsigned before=removed;
   clock.initLedStrip(color);
   auto*current=activeLedStrip;unsigned after=removed;
   clock.initLedStrip(color);assert(activeLedStrip==current&&removed==after);
#if WORDCLOCK_TEST_MODE != 0
   assert(activeLedStrip==previous&&removed==before);
   assert(activeLedPin==UINT8_MAX&&activeLedStrip->isVirtual());
   assert(activeLedStrip->diagnostics().logicalPixels==300*multiplier);
   assert(activeLedStrip->getPixel(0).R==17);
   assert(!activeLedStrip->setStatusPixel(RgbColor(7,8,9)));
   auto*virtualStrip=static_cast<VirtualLedStripAdapter*>(activeLedStrip);
   activeLedStrip->setRgbwPixel(1,RgbwColor(1,2,3,4));
   assert(virtualStrip->getRgbwPixel(1).W==(color==Grbw?4:0));
#else
   (void)previous;(void)before;
   assert(!activeLedStrip->isVirtual()&&activeLedPin==pin);
   assert(lastPin==pin&&lastCount==300*multiplier&&lastWhite==(color==Grbw));
#ifdef ESP8266
   assert(lastMethod==(pin==LED_PIN?0:1));assert(pinWrites==0);
#else
   assert(lastMethod==2&&pinWrites==created);
#endif
#endif
  }
 }
#if WORDCLOCK_TEST_MODE != 0
 assert(created==0&&pinWrites==0);
#else
 assert(created>0);
#endif
 deleteActiveLedStrip();
}
"""

def main():
    compiler=shutil.which('g++')
    if not compiler:raise SystemExit('g++ is required')
    source=(ROOT/'include/ClockWork.hpp').read_text()
    assert source.count('#include "ClockWorkLedFactory.hpp"')==1
    assert 'void ClockWork::initLedStrip(' not in source
    mock=runpy.run_path(str(ROOT/'tests/test_clock_test_foundation.py'))['MOCK']
    with tempfile.TemporaryDirectory() as folder:
        work=Path(folder)
        for name in ('ClockWorkLedFactory.hpp','ClockTestPolicy.h',
                     'VirtualLedStripAdapter.h','LedStripInterface.h'):
            shutil.copyfile(ROOT/'include'/name,work/name)
        for name,content in {'Arduino.h':'#pragma once\n#include <stdint.h>\n',
                             'NeoPixelBus.h':mock,
                             'WordClockState.h':'#pragma once\n',
                             'LedStatusPrefix.h':'#pragma once\n#define WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL 1\n',
                             'test.cpp':CPP}.items():
            (work/name).write_text(content)
        for target in ('ESP32','ESP8266'):
            for mode in (0,1,2):
                exe=work/f'{target}-{mode}'
                subprocess.run([compiler,'-std=c++11','-Wall','-Wextra','-Werror',
                                '-fsanitize=undefined,bounds','-fno-sanitize-recover=all',
                                f'-D{target}',f'-DWORDCLOCK_TEST_MODE={mode}',
                                '-I'+str(work),str(work/'test.cpp'),'-o',str(exe)],check=True)
                subprocess.run([str(exe)],check=True)
    print('PASS: six target/mode combinations, 256 pins, RGB/RGBW, three sizes, cache reuse and no physical symbols in test modes.')

if __name__=='__main__':
    main()
