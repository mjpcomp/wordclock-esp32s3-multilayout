#!/usr/bin/env python3
"""Host I2C helper guards with Wire spies; direct RTC calls remain separate."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
ARDUINO=r"""#pragma once
#include <cstdint>
using byte=uint8_t;
extern unsigned delays;
inline void delay(unsigned){++delays;}
struct SerialMock{void println(const char*){};void printf(const char*,...){};};
extern SerialMock Serial;
"""
CONFIG='#pragma once\n#define SDA_PIN_ESP8266 4\n#define SCL_PIN_ESP8266 5\n#define SDA_PIN_ESP32 14\n#define SCL_PIN_ESP32 15\n#define SDA_PIN_ESP32C3 18\n#define SCL_PIN_ESP32C3 19\n'
WIRE=r"""#pragma once
#include <cstdint>
extern unsigned begins,ends,tx,rx,seen[128];
extern uint8_t lastSda,lastScl,lastAddress;
extern int ack;
struct WireMock{
 void end(){++ends;}
 void begin(uint8_t s,uint8_t c){++begins;lastSda=s;lastScl=c;}
 void beginTransmission(uint8_t a){++tx;lastAddress=a;++seen[a];}
 uint8_t endTransmission(){++rx;return ack==-2||ack==lastAddress?0:4;}
};
extern WireMock Wire;
"""
CPP=r"""#include "Arduino.h"
#include "Wire.h"
#include "I2CBus.h"
#include <cassert>
#include <cstring>
#include <initializer_list>
unsigned delays=0,begins=0,ends=0,tx=0,rx=0,seen[128]={};
uint8_t lastSda=0,lastScl=0,lastAddress=0;int ack=-1;
SerialMock Serial;WireMock Wire;
void reset(){delays=begins=ends=tx=rx=0;std::memset(seen,0,sizeof(seen));ack=-1;}
bool untouched(){return begins==0&&ends==0&&tx==0&&rx==0&&delays==0;}
#ifdef ESP8266
constexpr unsigned END_CALLS=0,MAX_PIN=16;
#else
constexpr unsigned END_CALLS=1,MAX_PIN=39;
#endif
int main(){using namespace i2cBus;
 auto pins=defaultPins();
#if WORDCLOCK_TEST_MODE == 1
 assert(pins.sda==255&&pins.scl==255);
#elif WORDCLOCK_TEST_MODE == 2
 assert(pins.sda==8&&pins.scl==9);
#elif defined(ESP8266)
 assert(pins.sda==4&&pins.scl==5);
#elif defined(CONFIG_IDF_TARGET_ESP32C3)
 assert(pins.sda==18&&pins.scl==19);
#else
 assert(pins.sda==14&&pins.scl==15);
#endif
 uint8_t s=0,c=0;setDefaultPins(s,c);assert(s==pins.sda&&c==pins.scl);
 for(unsigned sda=0;sda<256;++sda)for(unsigned scl=0;scl<256;++scl){
  reset();begin(sda,scl);
#if WORDCLOCK_TEST_MODE == 1
  assert(untouched());
#elif WORDCLOCK_TEST_MODE == 2
  assert(begins==1&&ends==END_CALLS&&lastSda==8&&lastScl==9);
#else
  assert(ends==END_CALLS&&begins==unsigned(sda!=255&&scl!=255));
  if(begins)assert(lastSda==sda&&lastScl==scl);
#endif
  reset();auto found=scan(sda,scl,8,9);
  const bool valid=sda<=MAX_PIN&&scl<=MAX_PIN&&sda!=scl;
#if WORDCLOCK_TEST_MODE == 1
  (void)valid;assert(found.status==ScanStatus::Disabled&&untouched());
#else
  if(sda==255&&scl==255){assert(found.status==ScanStatus::Disabled&&untouched());}
  else if(!valid||(WORDCLOCK_TEST_MODE==2&&(sda!=8||scl!=9))){
   assert(found.status==ScanStatus::Invalid&&untouched());
  }else{
   assert(found.status==ScanStatus::Ok&&found.addressCount==0);
   assert(begins==2&&ends==2*END_CALLS&&lastSda==8&&lastScl==9&&delays==1);
   assert(tx==(WORDCLOCK_TEST_MODE==2?1u:126u)&&rx==tx);
   for(unsigned a=1;a<127;++a)assert(seen[a]==unsigned(WORDCLOCK_TEST_MODE==0||a==0x68));
  }
#endif
  reset();assert(findBH1750Address(sda,scl)==0);
  assert(tx==((WORDCLOCK_TEST_MODE==0&&sda!=255&&scl!=255)?2u:0u));
  assert(rx==tx&&begins==0&&ends==0);
 }
 reset();ack=-2;auto found=scan(8,9,48,49);
#if WORDCLOCK_TEST_MODE == 1
 assert(found.status==ScanStatus::Disabled&&untouched());
#elif WORDCLOCK_TEST_MODE == 2
 assert(found.addressCount==1&&found.addresses[0]==0x68&&tx==1);
 assert(lastSda==8&&lastScl==9);
#else
 assert(found.addressCount==3&&found.addresses[0]==1&&found.addresses[2]==3&&tx==3);
 assert(lastSda==48&&lastScl==49);
#endif
 for(int address:{0x23,0x5c}){
  reset();ack=address;auto result=findBH1750Address(8,9);
  if(WORDCLOCK_TEST_MODE)assert(result==0&&untouched());
  else assert(result==address&&tx==unsigned(address==0x23?1:2));
 }
}
"""

def main():
    compiler=shutil.which('g++')
    if not compiler:raise SystemExit('g++ is required')
    with tempfile.TemporaryDirectory() as folder:
        work=Path(folder)
        for path in ('include/I2CBus.h','include/ClockTestPolicy.h','src/I2CBus.cpp'):
            shutil.copyfile(ROOT/path,work/Path(path).name)
        for name,text in {'Arduino.h':ARDUINO,'Config.h':CONFIG,'Wire.h':WIRE,
                          'WordClockState.h':'#pragma once\n#define HARDWARE_PIN_DISABLED 255\n',
                          'LedStatusPrefix.h':'#pragma once\n#define WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL 0\n',
                          'test.cpp':CPP}.items():(work/name).write_text(text)
        targets=[['ESP8266'],['ESP32'],['ESP32','CONFIG_IDF_TARGET_ESP32C3'],
                 ['ESP32','CONFIG_IDF_TARGET_ESP32S3']]
        for flags in targets:
            for mode in (0,1,2):
                args=[compiler,'-std=c++11','-Wall','-Wextra','-Werror',
                      '-fsanitize=undefined,bounds','-fno-sanitize-recover=all',
                      *['-D'+f for f in flags],f'-DWORDCLOCK_TEST_MODE={mode}',
                      '-I'+str(work),str(work/'I2CBus.cpp'),str(work/'test.cpp'),
                      '-o',str(work/'test')]
                result=subprocess.run(args,capture_output=True,text=True)
                if mode and 'CONFIG_IDF_TARGET_ESP32S3' not in flags:
                    assert result.returncode!=0 and 'I2C test modes require the ESP32-S3 target' in result.stderr
                else:
                    if result.returncode:raise SystemExit(result.stderr)
                    subprocess.run([str(work/'test')],check=True)
    print('PASS: six host configurations, all 65536 pin pairs, RTC-only scans/restores, sensor probes, and six unsupported-test-target rejections.')

if __name__=='__main__':
    main()
