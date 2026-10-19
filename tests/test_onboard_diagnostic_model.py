#!/usr/bin/env python3
"""Pure onboard pattern logic only; no Arduino, GPIO48 driver or runtime hooks."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
CPP=r"""#include "OnboardDiagnosticModel.h"
#include <cassert>
using namespace onboardDiagnostic;
static bool same(Color a,Color b){return a==b;}
int main(){
 const Baseline disconnected[]={Baseline::Offline,Baseline::Connecting,Baseline::AccessPoint};
 const Baseline clocks[]={Baseline::TimeInvalid,Baseline::ClockRtc,Baseline::ClockNtp};
 for(unsigned net=0;net<4;++net)for(unsigned clock=0;clock<3;++clock)
 for(unsigned expected=0;expected<2;++expected)for(unsigned detected=0;detected<2;++detected)
 for(unsigned fault=0;fault<2;++fault){
  Inputs in;in.network=Network(net);in.clock=Clock(clock);in.rtcExpected=expected;in.rtcDetected=detected;in.fault=fault;
  const Baseline wanted=fault?Baseline::Fault:net<3?disconnected[net]:expected&&!detected?Baseline::RtcMissing:clocks[clock];
  Controller model;assert(model.sample(in,0).baseline==wanted);
  for(uint32_t t=0;t<4001;++t){auto frame=model.sample(in,t);assert(frame.event==Event::None);assert(frame.color.r<=20&&frame.color.g<=20&&frame.color.b<=20);}
 }
 for(unsigned value=4;value<256;++value){Inputs bad;bad.network=Network(value);Controller m;assert(m.sample(bad,0).baseline==Baseline::Fault);}
 for(unsigned value=3;value<256;++value){Inputs bad;bad.clock=Clock(value);Controller m;assert(m.sample(bad,0).baseline==Baseline::Fault);}
 Inputs in;in.network=Network::AccessPoint;
 Controller model;assert(same(model.sample(in,0).color,{0,0,16}));
 assert(same(model.sample(in,99).color,{0,0,16}));assert(same(model.sample(in,100).color,{0,0,0}));
 assert(same(model.sample(in,200).color,{0,0,16}));assert(same(model.sample(in,300).color,{0,0,0}));
 assert(same(model.sample(in,1000).color,{0,0,16}));
 model.reset();in.network=Network::Connecting;
 assert(same(model.sample(in,0).color,{2,1,0}));assert(same(model.sample(in,1000).color,{18,6,0}));
 assert(same(model.sample(in,2000).color,{2,1,0}));
 model.reset();in.network=Network::Connected;in.clock=Clock::Ntp;
 assert(same(model.sample(in,0).color,{0,2,0}));
 Controller heartbeat;assert(same(heartbeat.sample(in,0).color,{0,2,0}));
 assert(same(heartbeat.sample(in,1000).color,{0,12,0}));assert(same(heartbeat.sample(in,2000).color,{0,2,0}));
 assert(model.noteTimeSync(0)&&model.noteFrameChange(0));
 assert(model.sample(in,0).event==Event::TimeSync);
 assert(!model.noteTimeSync(100)&&!model.noteFrameChange(50));
 assert(model.sample(in,179).event==Event::TimeSync);
 assert(model.sample(in,180).event==Event::None);
 assert(!model.noteFrameChange(999)&&model.noteFrameChange(1000));
 assert(model.sample(in,1000).event==Event::FrameChange);
 assert(model.sample(in,1079).event==Event::FrameChange);
 assert(model.sample(in,1080).event==Event::None);
 assert(!model.noteTimeSync(4999)&&model.noteTimeSync(5000));
 in.fault=true;auto fault=model.sample(in,5000);assert(fault.baseline==Baseline::Fault&&fault.event==Event::None);
 in.fault=false;assert(model.sample(in,5200).event==Event::None);
 model.reset();model.noteFrameChange(0);in.network=Network::AccessPoint;
 assert(model.sample(in,0).event==Event::None);in.network=Network::Connected;
 assert(model.sample(in,80).event==Event::None);
 model.reset();const uint32_t near=UINT32_MAX-20;
 assert(model.noteFrameChange(near));assert(model.sample(in,near).event==Event::FrameChange);
 assert(model.sample(in,uint32_t(near+80u)).event==Event::None);
 assert(!model.noteFrameChange(uint32_t(near+999u))&&model.noteFrameChange(uint32_t(near+1000u)));
 model.reset();assert(model.noteTimeSync(near));assert(model.sample(in,near).event==Event::TimeSync);
 assert(model.sample(in,uint32_t(near+180u)).event==Event::None);
 model.reset();unsigned times=0,frames=0,base=0;
 for(uint32_t t=0;t<20000;++t){model.noteTimeSync(t);model.noteFrameChange(t);auto f=model.sample(in,t);
  if(f.event==Event::TimeSync)++times;else if(f.event==Event::FrameChange)++frames;else ++base;
 }
 assert(times==720&&frames==1280&&base==18000);
 model.reset();assert(model.sample(in,0).event==Event::None);
 model.noteTimeSync(0);model.sample(in,6000);assert(model.noteTimeSync(1));
 model.reset();in.rtcExpected=false;in.rtcDetected=false;assert(model.sample(in,0).baseline==Baseline::ClockNtp);
 in.rtcExpected=true;assert(model.sample(in,1).baseline==Baseline::RtcMissing);
 in.rtcDetected=true;in.clock=Clock::Invalid;assert(model.sample(in,2).baseline==Baseline::TimeInvalid);
 in.clock=Clock::Rtc;assert(same(model.sample(in,3).color,{0,1,2}));
}
"""

def main():
    compiler=shutil.which('g++')
    if not compiler:raise SystemExit('g++ is required')
    with tempfile.TemporaryDirectory() as folder:
        work=Path(folder);(work/'test.cpp').write_text(CPP)
        subprocess.run([compiler,'-std=c++11','-Wall','-Wextra','-Werror',
                        '-fsanitize=undefined,bounds','-fno-sanitize-recover=all',
                        '-I'+str(ROOT/'include'),str(work/'test.cpp'),'-o',str(work/'test')],check=True)
        subprocess.run([str(work/'test')],check=True)
    print('PASS: 96 input combinations, pattern boundaries, priority, event limits, wrap, reset and no-frame-starvation; pure model only.')

if __name__=='__main__':main()
