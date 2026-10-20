#!/usr/bin/env python3
"""Compile the real application adapter against interface mocks; no live DNS."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
CPP=r"""#include <stdint.h>
#include <cassert>
#include <atomic>
#include <string>
#include <cstdarg>
#include <cstdio>
#include <time.h>
#if WORDCLOCK_TEST_MODE != 0
static std::string logText;
static unsigned reportCalls=0, sinkCalls=0;
struct SerialMock { void printf(const char *fmt,...) {
 char b[512];va_list args;va_start(args,fmt);vsnprintf(b,sizeof(b),fmt,args);va_end(args);
 logText+=b; ++reportCalls;
}} Serial;
struct Address {std::string value; std::string toString() const {return value;}};
constexpr int WIFI_AP=2,WL_CONNECTED=3;
struct WifiMock {
 int state=3,mode=1;
 int status() {return state;}int getMode(){return mode;}
 Address localIP(){return {"192.168.16.124"};}
 Address gatewayIP(){return {"192.168.16.1"};}
 Address dnsIP(uint8_t i){return {i?"0.0.0.0":"192.168.16.1"};}
} WiFi;
struct {char timeserver[32]="168.61.215.74";char timezone[32]="PST8PDT,M3.2.0,M11.1.0";} G;
struct LedStripDiagnostics {uint16_t logicalPixels;uint32_t showRequests,changedFrames;bool countersAvailable;};
struct Backend {
 bool virt=true;
 LedStripDiagnostics diagnostics(){return {114,99,4,true};}
 bool isVirtual(){return virt;}
} backend;
Backend *activeLedStrip=&backend;bool externalRTC=false;
static uint32_t testMs=0;uint32_t millis(){return testMs;}
static time_t testEpoch=1700000000;
time_t fakeTime(time_t*){return testEpoch;}
#define time fakeTime
#endif
#include "OnboardDiagnosticApplication.hpp"
int main(){using namespace onboardDiagnosticApplication;
#if WORDCLOCK_TEST_MODE == 0
 service();noteNtp(0);noteRtc(0);resetFrames();connecting(true);
#else
 service();assert(reportCalls==3&&sinkCalls==1);
 assert(logText.find("dns0=192.168.16.1 dns1=0.0.0.0")!=std::string::npos);
 assert(logText.find("epoch=1700000000 time_valid=1 ntp_events=0")!=std::string::npos);
 assert(logText.find("configured_ntp=168.61.215.74")!=std::string::npos);
 assert(logText.find("timezone=PST8PDT,M3.2.0,M11.1.0")!=std::string::npos);
 unsigned n=reportCalls;noteNtp(20);assert(reportCalls==n);
 testMs=20;service();assert(reportCalls==n);
 testMs=1000;service();assert(reportCalls==6);
 assert(logText.find("ntp_events=1")!=std::string::npos);
 n=reportCalls;testMs=30999;service();assert(reportCalls==n);
 testMs=31000;service();assert(reportCalls==9);
 WiFi.state=0;testMs=31500;service();assert(reportCalls==9);
 testEpoch=0;testMs=32000;service();assert(reportCalls==12);
 assert(logText.find("wifi_status=0 epoch=0 time_valid=0")!=std::string::npos);
 noteNtp(33000);testMs=33000;service();assert(reportCalls==15);
 testMs=UINT32_MAX-499;service();n=reportCalls;
 testMs=500;service();assert(reportCalls==n);
 testMs=29500;service();assert(reportCalls==n+3);
#endif
}
"""
RUNTIME=r"""#pragma once
namespace onboardDiagnostic {
enum class Network {Offline,Connecting,AccessPoint,Connected};
template<class Sink,bool Rtc>class Runtime {public:
 explicit Runtime(Sink&){}
 void noteNtpSync(uint32_t){}void noteRtcTime(uint32_t){}void resetFrames(){}
 void service(uint32_t,Network,bool,bool,bool,bool,uint32_t){++sinkCalls;}
};
}
"""
def main():
 compiler=shutil.which('g++')
 if not compiler:raise SystemExit('g++ is required')
 source=(ROOT/'include/OnboardDiagnosticApplication.hpp').read_text()
 for forbidden in ('WiFi.config(', 'hostByName(', 'configTime(', 'sntp_get_sync_status('):
  assert forbidden not in source,forbidden
 with tempfile.TemporaryDirectory() as folder:
  work=Path(folder)
  (work/'ClockTestPolicy.h').write_text('#pragma once\n#include <stdint.h>\nnamespace clockTestPolicy {constexpr int MODE=WORDCLOCK_TEST_MODE;}\n')
  (work/'test.cpp').write_text(CPP)
  (work/'OnboardDiagnosticApplication.hpp').write_text(source)
  for mode in (0,1,2):
   for name in ('OnboardDiagnosticSink.h','OnboardDiagnosticRuntime.h'):
    (work/name).unlink(missing_ok=True)
   if mode:
    (work/'OnboardDiagnosticSink.h').write_text('#pragma once\nnamespace onboardDiagnostic {class Gpio48Sink{};}\n')
    (work/'OnboardDiagnosticRuntime.h').write_text(RUNTIME)
   subprocess.run([compiler,'-std=c++11','-Wall','-Wextra','-Werror',
    '-fsanitize=undefined,bounds','-fno-sanitize-recover=all',
    '-DWORDCLOCK_TEST_MODE='+str(mode),'-I'+str(work),str(work/'test.cpp'),
    '-o',str(work/'test')],check=True)
   subprocess.run([str(work/'test')],check=True)
 print('PASS: time-report modes0/1/2, fields, callback deferral, rate limits, WiFi/event triggers, wrap and sink service forwarding; interfaces mocked.')
if __name__=='__main__':main()
