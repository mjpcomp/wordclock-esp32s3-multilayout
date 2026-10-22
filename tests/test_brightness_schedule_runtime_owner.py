#!/usr/bin/env python3
"""Runtime-owner/observer host tests; native API is stubbed, not physical persistence."""
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
CPP = r'''#include "BrightnessScheduleRuntimeOwner.h"
#include <assert.h>
#include <vector>
#include <type_traits>
#include <cstdlib>
namespace st=brightnessScheduleStorage;
namespace rt=brightnessScheduleRuntimeOwner;
static std::vector<uint8_t> bytes(const st::Record &r) {
 uint8_t buffer[st::MAX_BYTES];size_t n=0;assert(st::encode(r,buffer,sizeof(buffer),n));
 return std::vector<uint8_t>(buffer,buffer+n);
}
class Memory:public st::Backend {
public:
 std::vector<uint8_t> data;unsigned reads=0,writes=0;
 bool readFail=false,writeFail=false,changedDespiteFailure=false,differentReadback=false;
 st::ReadResult read(uint8_t *p,size_t cap,size_t &n)override {
  ++reads;if(readFail)return st::ReadResult::Failed;
  if(data.empty())return st::ReadResult::Missing;
  if(data.size()>cap)return st::ReadResult::Invalid;
  n=data.size();memcpy(p,data.data(),n);
  if(differentReadback&&writes){p[6]^=1;st::put32(p+n-4,st::crc32(p,n-4));}
  return st::ReadResult::Ok;
 }
 bool write(const uint8_t *p,size_t n)override {
  ++writes;if(!writeFail||changedDespiteFailure)data.assign(p,p+n);return !writeFail;
 }
};
struct Spy {unsigned calls=0;bool record=false;st::Result result=st::Result::Missing;uint32_t revision=0;};
static void observed(st::Result r,const st::Record *p,void *ctx) {
 Spy &s=*static_cast<Spy*>(ctx);++s.calls;s.result=r;s.record=p!=nullptr;s.revision=p?p->revision:0;
}
struct Clock {unsigned reads=0;rt::LocalTime value={0,true};};
static rt::LocalTime clockRead(void *ctx){Clock &c=*static_cast<Clock*>(ctx);++c.reads;return c.value;}
#if defined(ESP32)
unsigned nativeCalls=0;
esp_err_t nvs_open(const char *,nvs_open_mode_t,nvs_handle_t*){++nativeCalls;return ESP_FAIL;}
esp_err_t nvs_get_blob(nvs_handle_t,const char*,void*,size_t*){++nativeCalls;return ESP_FAIL;}
esp_err_t nvs_set_blob(nvs_handle_t,const char*,const void*,size_t){++nativeCalls;return ESP_FAIL;}
esp_err_t nvs_commit(nvs_handle_t){++nativeCalls;return ESP_FAIL;}
void nvs_close(nvs_handle_t){++nativeCalls;}
rt::Owner *otherOwner();
#endif
int main(){
 static_assert(!std::is_copy_constructible<rt::Owner>::value,"owner context cannot be copied");
 brightnessSchedule::Schedule a={};a.defaultTenths=400;
 brightnessSchedule::Schedule b=a;b.defaultTenths=600;
 st::Record out={};out.revision=999;
 Memory plain;Spy spy;st::Store observedStore(plain,observed,&spy);
 assert(!plain.reads&&!plain.writes&&!spy.calls);
 assert(observedStore.load(out)==st::Result::Missing&&spy.calls==1&&!spy.record&&out.revision==999);
 assert(observedStore.save(0,a,out)==st::Result::Ok&&spy.calls==2&&spy.record&&spy.revision==1);
 assert(plain.reads==3&&plain.writes==1);
 assert(observedStore.save(0,a,out)==st::Result::Conflict&&spy.calls==3&&!spy.record);
 brightnessSchedule::Schedule bad=a;bad.defaultTenths=1001;
 unsigned reads=plain.reads;
 assert(observedStore.save(1,bad,out)==st::Result::InvalidInput&&spy.calls==4&&!spy.record&&plain.reads==reads);
 Memory memory;rt::Owner owner(memory);assert(owner.current().gain==0&&!owner.initialized()&&!memory.reads);
 assert(owner.begin()==st::Result::Missing&&memory.reads==1&&!memory.writes);
 assert(owner.begin()==st::Result::Missing&&memory.reads==1);
 Clock clock;owner.serviceFromClock(0,clockRead,&clock,false,true);
 assert(owner.current().gain==10000&&!owner.current().scheduled&&clock.reads==1);
 owner.serviceFromClock(10,clockRead,&clock,false,true);assert(clock.reads==1);
 assert(owner.store().save(0,a,out)==st::Result::Ok);
 owner.serviceFromClock(11,clockRead,&clock,false,true);
 assert(clock.reads==2&&owner.current().gain==4000&&owner.current().revision==1);
 owner.serviceFromClock(12,clockRead,&clock,true,true);
 assert(owner.current().gain==10000&&owner.current().pausedAutomatic);
 owner.serviceFromClock(13,clockRead,&clock,true,false);assert(owner.current().gain==0);
 const unsigned ioReads=memory.reads,ioWrites=memory.writes;
 for(unsigned i=1;i<500;++i)owner.serviceFromClock(13+i,clockRead,&clock,false,true);
 assert(memory.reads==ioReads&&memory.writes==ioWrites);
 assert(owner.store().save(0,b,out)==st::Result::Conflict);
 owner.serviceLocal(600,{0,true},false,true);assert(!owner.current().storageFault&&owner.current().gain==4000);
 memory.writeFail=memory.changedDespiteFailure=true;
 assert(owner.store().save(1,b,out)==st::Result::WriteUncertain);
 owner.serviceLocal(601,{0,true},false,true);
 assert(owner.current().gain==4000&&owner.current().revision==1&&owner.current().storageFault);
 memory.writeFail=false;
 assert(owner.store().load(out)==st::Result::Ok&&out.revision==2);
 owner.serviceLocal(602,{0,true},false,true);
 assert(owner.current().gain==6000&&owner.current().revision==2&&!owner.current().storageFault);
 Memory mismatch;st::Record seed={};seed.revision=1;seed.schedule=a;mismatch.data=bytes(seed);
 rt::Owner mismatchOwner(mismatch);assert(mismatchOwner.begin()==st::Result::Ok);
 mismatchOwner.serviceLocal(0,{0,true},false,true);mismatch.differentReadback=true;
 assert(mismatchOwner.store().save(1,b,out)==st::Result::ReadbackUncertain);
 mismatchOwner.serviceLocal(1,{0,true},false,true);
 assert(mismatchOwner.current().gain==4000&&mismatchOwner.current().revision==1&&mismatchOwner.current().storageFault);
 Memory fault;fault.readFail=true;rt::Owner cold(fault);
 assert(cold.begin()==st::Result::ReadFailed);
 cold.serviceLocal(0,{0,true},false,true);assert(cold.current().gain==0&&cold.current().storageFault);
 fault.readFail=false;assert(cold.store().load(out)==st::Result::Missing);
 cold.serviceLocal(1,{0,true},false,true);assert(cold.current().gain==0);
 assert(cold.store().reset(0,out)==st::Result::Ok);
 cold.serviceLocal(2,{0,true},false,true);assert(cold.current().gain==10000&&!cold.current().storageFault);
 Memory wrapMemory;wrapMemory.data=bytes(seed);rt::Owner wrap(wrapMemory);wrap.begin();
 wrap.serviceLocal(0xffffffffUL-20,{0,true},false,true);
 Clock wrapClock;wrap.serviceFromClock(10,clockRead,&wrapClock,false,true);assert(!wrapClock.reads);
 wrap.serviceFromClock(30,clockRead,&wrapClock,false,true);assert(wrapClock.reads==1);
#if defined(ESP32)
 assert(nativeCalls==0);rt::Owner &app=rt::applicationRuntime();assert(&app==otherOwner()&&nativeCalls==0);
 assert(app.begin()==st::Result::ReadFailed&&nativeCalls==1);
 assert(app.begin()==st::Result::ReadFailed&&nativeCalls==1);
 setenv("TZ","UTC0",1);tzset();
 auto utc=rt::localFromEpoch(1792526269,123456);assert(utc.valid&&utc.dayMs==((19*60+57)*60+49)*1000UL+123);
 setenv("TZ","PST8PDT,M3.2.0,M11.1.0",1);tzset();
 auto pacific=rt::localFromEpoch(1792526269,123456);assert(pacific.valid&&pacific.dayMs==((12*60+57)*60+49)*1000UL+123);
 assert(!rt::localFromEpoch(0,0).valid&&!rt::localFromEpoch(1792526269,-1).valid);
 assert(!rt::localFromEpoch(1792526269,1000000).valid&&nativeCalls==1);
#endif
 return 0;
}
'''
def main():
    compiler = shutil.which('g++')
    if not compiler:
        raise SystemExit('g++ required for runtime-owner tests')
    stub = runpy.run_path(str(ROOT / 'tests/test_brightness_schedule_storage.py'))['STUB']
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        (work / 'test.cpp').write_text(CPP)
        (work / 'nvs.h').write_text(stub)
        other = work / 'other.cpp'
        other.write_text('#include "BrightnessScheduleRuntimeOwner.h"\n'
                         'brightnessScheduleRuntimeOwner::Owner *otherOwner() {\n'
                         ' return &brightnessScheduleRuntimeOwner::applicationRuntime(); }\n')
        for name, defines, extra in [('core', [], []), ('native-stub', ['-DESP32'], [str(other)])]:
            binary = work / name
            subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all'] + defines +
                           ['-I', str(work), '-I', str(ROOT / 'include'), str(work / 'test.cpp')] +
                           extra + ['-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
            print('PASS: runtime-owner/verified-observer ' + name)
if __name__ == '__main__':
    main()
