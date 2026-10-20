#!/usr/bin/env python3
"""Extract actual RTC sections; host mocks do not certify SDK hardware behavior."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
PRE=r"""#include "ClockTestPolicy.h"
#include <cstdint>
#include <cassert>
#include <initializer_list>
unsigned constructors=0,begins=0,reads=0,adjusts=0,systemSets=0,portal=0,notices=0;
unsigned ntpNotices=0,rtcNotices=0;
unsigned driver=0;uint32_t adjusted=0;bool present=false,externalRTC=true;
int systemSetResult=0;
uint32_t millis(){return 42;}
struct DateTime{uint32_t t;explicit DateTime(uint32_t v):t(v){}uint32_t unixtime()const{return t;}};
struct TestTimeval{long tv_sec;long tv_usec;};
#define timeval TestTimeval
int settimeofday(const TestTimeval*tv,void*){assert(tv->tv_usec==0&&tv->tv_sec==1700000000);++systemSets;return systemSetResult;}
struct SerialMock{void println(const char*){}}Serial;
struct NetworkMock{void rtcMode(){++portal;}}network;
namespace prefixStatusRuntime{void noteTimeSet(){++notices;}}
namespace onboardDiagnosticApplication{
 void noteNtp(uint32_t ms){assert(ms==42);++ntpNotices;}
 void noteRtc(uint32_t ms){assert(ms==42);++rtcNotices;}
}
#if WORDCLOCK_TEST_MODE != 1
// No hardware RTC types exist in the board-only test translation unit.
template<unsigned Id>struct MockRtc{
 MockRtc(){++constructors;driver=Id;}
 bool begin(){++begins;return present;}
 DateTime now(){++reads;return DateTime(1700000000);}
 void adjust(const DateTime&dt){++adjusts;adjusted=dt.t;}
};
using RTC_DS3231=MockRtc<3231>;
#define RTC_Type MockRtc<8523>
#endif
"""
TEST=r"""
int main(){
 assert(constructors==(WORDCLOCK_TEST_MODE==1?0u:1u));
 if(WORDCLOCK_TEST_MODE==2)assert(driver==3231);
 if(WORDCLOCK_TEST_MODE==0)assert(driver==8523);
 for(bool found:{false,true}){
  present=found;externalRTC=true;begins=reads=systemSets=portal=rtcNotices=0;
  systemSetResult=0;setupRtc();
  if(WORDCLOCK_TEST_MODE==1){assert(!externalRTC&&begins==0&&reads==0&&systemSets==0&&portal==0&&rtcNotices==0);}
  else{assert(begins==1&&externalRTC==found&&reads==unsigned(found)&&systemSets==unsigned(found)&&portal==unsigned(found));assert(rtcNotices==(EXPECT_RTC_NOTE&&found?1u:0u));}
 }
 present=true;externalRTC=true;rtcNotices=0;systemSetResult=1;
 setupRtc();assert(rtcNotices==0);systemSetResult=0;
 for(bool staleFlag:{false,true}){
  externalRTC=staleFlag;adjusts=notices=ntpNotices=0;
  for(uint32_t i=0;i<100;++i)syncTime(1700000000+i);
  assert(notices==100&&ntpNotices==(EXPECT_NTP_NOTE?100u:0u));
  assert(adjusts==(WORDCLOCK_TEST_MODE!=1&&staleFlag?100u:0u));
  if(adjusts)assert(adjusted==1700000099);
 }
}
"""

def extract_callback(source):
    # Start after the architecture-specific time_is_set signature/utc branch,
    # not after a particular diagnostic statement or its brace formatting.
    start=source.index('void time_is_set(')
    branch_end=re.search(r'^#endif[^\S\n]*\n',source[start:],re.M)
    if branch_end is None:raise ValueError('Missing time_is_set architecture branch')
    start+=branch_end.end()
    end=source.index('    struct tm tm;',start)
    callback=source[start:end]
    if callback.count('prefixStatusRuntime::noteTimeSet()')!=1:
        raise ValueError('Expected one time notification in callback')
    return callback

def main():
    compiler=shutil.which('g++')
    if not compiler:raise SystemExit('g++ is required')
    source=(ROOT/'src/WordClock.cpp').read_text()
    expected={'begin':1,'now':1,'adjust':1}
    for method,count in expected.items():
        assert len(re.findall(r'\bRTC\s*\.\s*'+method+r'\s*\(',source))==count,method
    for directory in ('src','include'):
        for path in (ROOT/directory).rglob('*'):
            if path.suffix in ('.cpp','.h','.hpp') and path!=ROOT/'src/WordClock.cpp':
                assert not re.search(r'\bRTC\s*\.\s*(begin|now|adjust)\s*\(',path.read_text()),str(path)
    start=source.index('\n',source.index('const char TZ_Europe_Berlin[]'))+1
    end=source.index('#include "ClockWork.h"',start)
    declaration=source[start:end]
    callback=extract_callback(source)
    title=source.index('    // Start external real-time clock')
    divider=source.index('    //-------------------------------------',title)
    start=source.index('\n',divider)+1
    end=source.index('#ifdef ESP8266\n    settimeofday_cb',start)
    startup=source[start:end]
    assert 'struct timeval tv{};' in startup
    assert source.index('i2cBus::begin(G.i2cSdaPin, G.i2cSclPin);')<start
    code=PRE+declaration+'\nvoid setupRtc(){\n'+startup+'\n}\n'
    code+='void syncTime(uint32_t utc){\n'+callback+'\n}\n'+TEST
    with tempfile.TemporaryDirectory() as folder:
        work=Path(folder)
        shutil.copyfile(ROOT/'include/ClockTestPolicy.h',work/'ClockTestPolicy.h')
        (work/'LedStatusPrefix.h').write_text('#pragma once\n#define WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL 0\n')
        (work/'test.cpp').write_text(code)
        for mode in (0,1,2):
            exe=work/f'test-{mode}'
            subprocess.run([compiler,'-std=c++11','-Wall','-Wextra','-Werror',
                            '-fsanitize=undefined,bounds','-fno-sanitize-recover=all',
                            f'-DWORDCLOCK_TEST_MODE={mode}',
                            '-DEXPECT_NTP_NOTE='+str(int('onboardDiagnosticApplication::noteNtp(' in callback)),
                            '-DEXPECT_RTC_NOTE='+str(int('onboardDiagnosticApplication::noteRtc(' in startup)),
                            '-I'+str(work),str(work/'test.cpp'),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
    print('PASS: RTC modes0/1/2, DS3231 selection, stale flags, time notices, valid-load hook and initialized timeval; host only.')

if __name__=='__main__':main()
