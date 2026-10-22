#include "BrightnessScheduleRuntimeOwner.h"
#include <assert.h>
#include <string.h>
#include <vector>
namespace st=brightnessScheduleStorage;
namespace rt=brightnessScheduleRuntimeOwner;
class Memory: public st::Backend {
public:
 std::vector<uint8_t> data; unsigned reads=0,writes=0;bool fail=false;
 st::ReadResult read(uint8_t *p,size_t cap,size_t &n) override {
  ++reads;if(fail)return st::ReadResult::Failed;
  if(data.empty())return st::ReadResult::Missing;
  assert(cap>=data.size());n=data.size();memcpy(p,data.data(),n);return st::ReadResult::Ok;
 }
 bool write(const uint8_t *p,size_t n) override {++writes;data.assign(p,p+n);return true;}
};
Memory memory;rt::Owner owner(memory);
bool configReady=false,tzReady=false;uint32_t nowMs=0;
unsigned clockReads=0;rt::LocalTime local={5UL*60000,true};
struct Config {unsigned autoBrightEnabled=0;} G;
struct Led {bool on=true;bool getState(){return on;}} led;
uint32_t millis(){return nowMs;}
namespace brightnessScheduleRuntimeOwner {
Owner &applicationRuntime(){assert(configReady&&tzReady);return owner;}
LocalTime systemLocalTime(void*){++clockReads;assert(tzReady);return local;}
}
#define ESP32 1
void startup(){
/*BOOT*/
}
void sampleAfterControls(){
/*SERVICE*/
}
int main(){
 assert(memory.reads==0&&memory.writes==0);
 brightnessSchedule::Schedule schedule={};schedule.defaultTenths=1000;schedule.count=2;
 schedule.events[0]={60,800,0};schedule.events[1]={1430,200,30};
 st::Record record={};record.revision=1;record.schedule=schedule;
 uint8_t data[st::MAX_BYTES];size_t n=0;assert(st::encode(record,data,sizeof(data),n));
 memory.data.assign(data,data+n);configReady=tzReady=true;
 startup();startup();assert(memory.reads==1&&memory.writes==0);
 sampleAfterControls();assert(clockReads==1&&owner.current().gain==5000);
 nowMs=49;sampleAfterControls();assert(clockReads==1);
 nowMs=50;sampleAfterControls();assert(clockReads==2);
 G.autoBrightEnabled=1;nowMs=51;sampleAfterControls();
 assert(owner.current().pausedAutomatic&&owner.current().gain==10000&&clockReads==3);
 G.autoBrightEnabled=2;nowMs=52;sampleAfterControls();
 assert(!owner.current().pausedAutomatic&&owner.current().gain==5000&&clockReads==4);
 led.on=false;nowMs=53;sampleAfterControls();assert(owner.current().gain==0&&clockReads==5);
 led.on=true;nowMs=54;sampleAfterControls();assert(owner.current().gain==5000&&clockReads==6);
 local={10UL*60000,true};nowMs=104;sampleAfterControls();assert(owner.current().gain==4000);
 assert(memory.reads==1&&memory.writes==0);
 schedule.count=0;schedule.defaultTenths=350;
 assert(owner.store().save(1,schedule,record)==st::Result::Ok);
 nowMs=105;sampleAfterControls();assert(owner.current().revision==2&&owner.current().gain==3500);
 assert(memory.writes==1);
 return 0;
}
