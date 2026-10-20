#!/usr/bin/env python3
"""Host orchestration checks with a recording sink, not physical GPIO/WiFi."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
CPP = r"""#include "OnboardDiagnosticRuntime.h"
#include <cassert>
using namespace onboardDiagnostic;
struct Sink {
 unsigned calls=0; Color last{0,0,0};
 bool service(uint32_t,uint8_t r,uint8_t g,uint8_t b) {
  ++calls; last={r,g,b}; return true;
 }
};
int main() {
 Sink sink; Runtime<Sink,false> run(sink);
 auto poll=[&](uint32_t t,bool valid=true,bool available=true,uint32_t frames=0) {
  return run.service(t,Network::Connected,valid,false,false,available,frames);
 };
 assert(poll(0).baseline==Baseline::TimeInvalid);
 run.noteRtcTime(0); assert(poll(1).baseline==Baseline::TimeInvalid);
 unsigned before=sink.calls; run.noteNtpSync(0); assert(sink.calls==before);
 assert(poll(20).event==Event::TimeSync);
 assert(poll(180).baseline==Baseline::ClockNtp);
 assert(poll(180).event==Event::None);
 assert(poll(200,true,true,1).event==Event::FrameChange);
 assert(poll(280,true,true,1).event==Event::None);
 assert(poll(1200,true,true,1).event==Event::None);
 assert(poll(1220,true,true,2).event==Event::FrameChange);
 run.resetFrames();
 assert(poll(2300,true,true,0).event==Event::None);
 assert(poll(2320,true,true,1).event==Event::FrameChange);
 poll(2400,true,false); assert(poll(3400,true,true,99).event==Event::None);
 assert(poll(3420,true,true,100).event==Event::FrameChange);
 assert(poll(3500,false).baseline==Baseline::TimeInvalid);
 run.noteNtpSync(6000); assert(poll(6200).event==Event::None);
 assert(poll(6200).baseline==Baseline::ClockNtp);
 run.noteNtpSync(12000);
 auto ap=run.service(12000,Network::AccessPoint,true,false,false,false,0);
 assert(ap.baseline==Baseline::AccessPoint && ap.event==Event::None);
 assert(poll(12200).event==Event::None);
 auto fault=run.service(12300,Network::Connected,true,false,true,false,0);
 assert(fault.baseline==Baseline::Fault);
 Sink rtcSink; Runtime<Sink,true> rtc(rtcSink);
 assert(rtc.service(0,Network::Connected,true,true,false,false,0).baseline==Baseline::TimeInvalid);
 rtc.noteRtcTime(0);
 assert(rtc.service(180,Network::Connected,true,true,false,false,0).baseline==Baseline::ClockRtc);
 assert(rtc.service(200,Network::Connected,true,false,false,false,0).baseline==Baseline::RtcMissing);
 Sink wrapSink; Runtime<Sink,false> wrap(wrapSink);
 wrap.noteNtpSync(UINT32_MAX-99);
 assert(wrap.service(100,Network::Connected,true,false,false,false,0).event==Event::None);
 assert(wrapSink.calls==1 && wrapSink.last.g==2);
 Sink zeroSink; Runtime<Sink,false> zero(zeroSink);
 zero.noteNtpSync(0);
 assert(zero.service(0,Network::Connected,true,false,false,false,0).event==Event::TimeSync);
 assert(zeroSink.last.r==20 && zeroSink.last.g==20 && zeroSink.last.b==20);
}
"""
def main():
 compiler=shutil.which('g++')
 if not compiler: raise SystemExit('g++ is required')
 with tempfile.TemporaryDirectory() as folder:
  work=Path(folder); (work/'test.cpp').write_text(CPP)
  subprocess.run([compiler,'-std=c++11','-Wall','-Wextra','-Werror',
   '-fsanitize=undefined,bounds','-fno-sanitize-recover=all','-I'+str(ROOT/'include'),
   str(work/'test.cpp'),'-o',str(work/'test')],check=True)
  subprocess.run([str(work/'test')],check=True)
 print('PASS: source truthfulness, callback deferral, original event timestamps, frame deltas/reset, masking, expiry, wrap and sink forwarding.')
 subprocess.run([sys.executable,str(ROOT/'tests/test_onboard_time_report.py')],check=True)
if __name__=='__main__': main()
