#!/usr/bin/env python3
"""Host-test ADC getters, brightness loop and BH1750 setup; not all I2C/RTC paths."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
PRE=r"""#include "ClockTestPolicy.h"
#include <cstdint>
#include <cmath>
#include <algorithm>
#include <cassert>
#include <initializer_list>
using std::min;using std::max;
using byte=uint8_t;
constexpr int A0=0;
constexpr uint32_t AUTOBRIGHT_LDR_RESDARK=1000,AUTOBRIGHT_LDR_RESBRIGHT=100,AUTOBRIGHT_LDR_RESDIVIDER=10;
unsigned adcCalls=0,probeCalls=0,beginCalls=0,readyCalls=0,readCalls=0;
bool bh1750Initialized=false,autoBrightUsingBH1750=false,parametersChanged=false,ready=true;
uint8_t discovered=0;
float ledGain=77;
struct{int autoBrightEnabled=1;uint16_t autoBrightMin=10,autoBrightMax=90,autoBrightPeak=1000;uint8_t i2cSdaPin=8,i2cSclPin=9;}G;
uint16_t analogRead(int){++adcCalls;return 512;}
long map(long x,long a,long b,long c,long d){return (x-a)*(d-c)/(b-a)+c;}
struct{void println(const char*){}}Serial;
namespace i2cBus{byte findBH1750Address(uint8_t,uint8_t){++probeCalls;return discovered;}}
struct BH1750{static constexpr int CONTINUOUS_HIGH_RES_MODE=1;
 void begin(int,uint8_t){++beginCalls;}
 bool measurementReady(){++readyCalls;return ready;}
 float readLightLevel(){++readCalls;return 450;}
}lightMeter;
void resetCounts(){adcCalls=probeCalls=beginCalls=readyCalls=readCalls=0;}
"""
TEST=r"""
int main(){ClockWork clock;
 for(uint8_t pin:{0,8,48,255})for(uint8_t address:{0,0x23}){
  G.i2cSdaPin=pin;G.i2cSclPin=255-pin;discovered=address;
  bh1750Initialized=autoBrightUsingBH1750=true;resetCounts();setupBrightness();
  if(WORDCLOCK_TEST_MODE){
   assert(probeCalls==0&&beginCalls==0&&!bh1750Initialized&&!autoBrightUsingBH1750);
  }else{
   assert(probeCalls==1&&beginCalls==unsigned(address!=0));
   assert(bh1750Initialized==(address!=0)&&autoBrightUsingBH1750==(address!=0));
  }
 }
 resetCounts();
 for(int i=0;i<100;++i){
  auto raw=clock.getAdcRawValue();auto volts=clock.getAdcValue();
  if(WORDCLOCK_TEST_MODE)assert(raw==0&&volts==0);
  else assert(raw==512&&std::fabs(volts-1.65f)<0.001f);
 }
 assert(adcCalls==(WORDCLOCK_TEST_MODE?0u:200u));
 for(bool enabled:{false,true})for(bool found:{false,true})
 for(bool available:{false,true})for(bool equal:{false,true}){
  G.autoBrightEnabled=enabled;G.autoBrightMin=equal?90:10;G.autoBrightMax=90;
  bh1750Initialized=found;ready=available;ledGain=77;clock.lux=123;resetCounts();
  clock.loopAutoBrightLogic();
  if(WORDCLOCK_TEST_MODE||!enabled||equal){
   assert(adcCalls==0&&readyCalls==0&&readCalls==0);
   assert(ledGain==((!WORDCLOCK_TEST_MODE&&enabled&&equal)?90:77));
  }else{
   assert(readyCalls==unsigned(found));
   assert(readCalls==unsigned(found&&available));
   assert(adcCalls==unsigned(!(found&&available)));
  }
 }
}
"""

def extract(text,marker):
    start=text.index(marker);end=text.index('{',start)+1;depth=1
    while depth:
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    return text[start:end]

def main():
    compiler=shutil.which('g++')
    if not compiler:raise SystemExit('g++ is required')
    header=(ROOT/'include/ClockWork.h').read_text()
    clock=(ROOT/'include/ClockWork.hpp').read_text()
    setup=(ROOT/'src/WordClock.cpp').read_text()
    assert '#include "ClockTestPolicy.h"' in header
    getters=extract(header,'float getAdcValue()')+'\n'+extract(header,'uint16_t getAdcRawValue()')
    loop=extract(clock,'void ClockWork::loopAutoBrightLogic()')
    start=setup.index('    // Find BH1750 and initialize')
    end=setup.index('\n    //-------------------------------------',start)
    code=PRE+'\nclass ClockWork{public:uint32_t lux=123;void loopAutoBrightLogic();\n'+getters+'\n};\n'+loop
    code+='\nvoid setupBrightness(){\n'+setup[start:end]+'\n}\n'+TEST
    with tempfile.TemporaryDirectory() as folder:
        work=Path(folder)
        shutil.copyfile(ROOT/'include/ClockTestPolicy.h',work/'ClockTestPolicy.h')
        (work/'LedStatusPrefix.h').write_text('#pragma once\n#define WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL 0\n')
        (work/'test.cpp').write_text(code)
        for mode in (0,1,2):
            exe=work/f'test-{mode}'
            subprocess.run([compiler,'-std=c++11','-Wall','-Wextra','-Werror',
                            '-fsanitize=undefined,bounds','-fno-sanitize-recover=all',
                            f'-DWORDCLOCK_TEST_MODE={mode}','-I'+str(work),
                            str(work/'test.cpp'),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
    print('PASS: modes0/1/2 ADC getters, brightness branches and startup BH1750 guards; not full peripheral isolation.')

if __name__=='__main__':
    main()
