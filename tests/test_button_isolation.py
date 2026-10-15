#!/usr/bin/env python3
"""Compile the real button controller/policy with GPIO spies; not full isolation."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
ARDUINO = r"""#pragma once
#include <cstdint>
constexpr bool HIGH=true, LOW=false;
constexpr int INPUT_PULLUP=2;
extern unsigned writes, reads, ticks;
extern uint32_t nowMs;
extern bool levels[256];
inline void pinMode(uint8_t,int){++writes;}
inline bool digitalRead(uint8_t p){++reads;return levels[p];}
inline uint32_t millis(){++ticks;return nowMs;}
"""
STATE = r"""#pragma once
#include <cstdint>
constexpr uint8_t HARDWARE_PIN_DISABLED=255;
struct HardwarePins{uint8_t led=5,powerButton=255,modeButton=255,speedButton=255;};
"""
TEST = r"""#include "HardwareButtonController.h"
#include <cassert>
unsigned writes=0,reads=0,ticks=0;
uint32_t nowMs=0;
bool levels[256];
int main(){
 for(auto &level:levels)level=HIGH;
 for(unsigned pin=0;pin<256;++pin){
  HardwareButtonController controller;HardwarePins pins;
  pins.powerButton=pins.modeButton=pins.speedButton=pin;
  if(WORDCLOCK_TEST_MODE!=0)assert(controller.loop()==HardwareButtonAction::None);
  for(unsigned repeat=0;repeat<2;++repeat){
   controller.begin(pins);
   assert(controller.loop()==HardwareButtonAction::None);
  }
 }
 if(WORDCLOCK_TEST_MODE!=0){assert(writes==0&&reads==0&&ticks==0);return 0;}
 assert(writes==1530&&reads==3060);
 HardwareButtonController controller;HardwarePins pins;
 pins.powerButton=10;pins.modeButton=11;pins.speedButton=12;
 controller.begin(pins);
 auto press=[&](uint8_t pin,uint32_t duration,HardwareButtonAction action){
  levels[pin]=LOW;nowMs+=10;assert(controller.loop()==HardwareButtonAction::None);
  nowMs+=50;assert(controller.loop()==HardwareButtonAction::None);
  nowMs+=duration;levels[pin]=HIGH;assert(controller.loop()==HardwareButtonAction::None);
  nowMs+=50;assert(controller.loop()==action);
 };
 press(10,100,HardwareButtonAction::TogglePower);
 press(11,100,HardwareButtonAction::NextMode);
 press(11,2100,HardwareButtonAction::NextTransition);
 press(12,100,HardwareButtonAction::IncreaseBrightness);
 press(12,2100,HardwareButtonAction::NextHue);
}
"""

def main():
    compiler=shutil.which('g++')
    if not compiler: raise SystemExit('g++ is required')
    with tempfile.TemporaryDirectory() as folder:
        work=Path(folder)
        for path in ('include/HardwareButtonController.h','include/ClockTestPolicy.h',
                     'src/HardwareButtonController.cpp'):
            shutil.copyfile(ROOT/path,work/Path(path).name)
        for name,content in {'Arduino.h':ARDUINO,'WordClockState.h':STATE,
                             'LedStatusPrefix.h':'#pragma once\n#define WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL 0\n',
                             'test.cpp':TEST}.items():
            (work/name).write_text(content)
        for mode in (0,1,2):
            exe=work/f'test-{mode}'
            subprocess.run([compiler,'-std=c++11','-Wall','-Wextra','-Werror',
                            '-fsanitize=undefined,bounds','-fno-sanitize-recover=all',
                            f'-DWORDCLOCK_TEST_MODE={mode}','-I'+str(work),
                            str(work/'HardwareButtonController.cpp'),str(work/'test.cpp'),
                            '-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
    print('PASS: all 256 pin values, repeated init, test modes without GPIO/timer calls, normal short/long actions.')

if __name__=='__main__':
    main()
