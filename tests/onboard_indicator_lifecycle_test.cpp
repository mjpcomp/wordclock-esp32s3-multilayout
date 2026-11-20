#include "OnboardIndicatorLifecycle.h"
#include <cassert>
#if TEST_SUPPORTED
#include "OnboardIndicatorCommandService.h"
#include "WordClockState.h"
#include <nvs.h>
#include <cstdlib>
#include <cstring>
#include <sys/time.h>
#include <time.h>
namespace life=onboardIndicatorLifecycle;
namespace p=onboardIndicatorPolicy;
namespace r=onboardIndicatorRecord;
TestGlobal G={"UTC0"};
static bool exists=false,ioError=false,clockError=false;
static unsigned opens=0,handles=0,writes=0;
static uint8_t bytes[r::kBytes]={};
static time_t epoch=1700000000;
extern "C" int onboard_test_gettimeofday(struct timeval*value,void*) noexcept {
 value->tv_sec=epoch;value->tv_usec=0;return clockError?-1:0;
}
esp_err_t nvs_open(const char*name,nvs_open_mode_t mode,nvs_handle_t*handle){
 assert(!strcmp(name,"wc-onboard")&&mode==NVS_READONLY);++opens;
 if(ioError)return ESP_FAIL;
 if(!exists)return ESP_ERR_NVS_NOT_FOUND;
 ++handles;*handle=1;return ESP_OK;
}
esp_err_t nvs_get_blob(nvs_handle_t handle,const char*key,void*out,size_t*size){
 assert(handle==1&&handles==1&&!strcmp(key,"policy"));
 if(!out){*size=r::kBytes;return ESP_OK;}
 assert(*size>=r::kBytes);memcpy(out,bytes,r::kBytes);*size=r::kBytes;return ESP_OK;
}
esp_err_t nvs_set_blob(nvs_handle_t,const char*,const void*,size_t){++writes;assert(false);return ESP_FAIL;}
esp_err_t nvs_commit(nvs_handle_t){++writes;assert(false);return ESP_FAIL;}
void nvs_close(nvs_handle_t handle){assert(handle==1&&handles==1);--handles;}
onboardIndicatorCommandService::Service* otherService();
#endif
int main(int argc,char**argv){
 namespace life=onboardIndicatorLifecycle;
#if TEST_SUPPORTED
 assert(argc==2);const char*scenario=argv[1];
 assert(setenv("TZ","UTC0",1)==0);tzset();
 const bool scheduled=!strcmp(scenario,"scheduled");
 const bool always=!strcmp(scenario,"missing")||!strcmp(scenario,"always");
 p::Policy policy=p::freshPolicy();
 if(!strcmp(scenario,"disabled"))policy.mode=p::Mode::Disabled;
 struct tm utc={};assert(gmtime_r(&epoch,&utc));
 const uint16_t minute=uint16_t(utc.tm_hour*60+utc.tm_min);
 if(scheduled)policy={p::Mode::Scheduled,1,{{minute,uint16_t((minute+1)%1440)},{0,0}}};
 if(strcmp(scenario,"missing")&&strcmp(scenario,"io")){
  exists=true;const r::Record record={7,policy};assert(r::encode(record,bytes,sizeof(bytes)));
 }
 if(!strcmp(scenario,"corrupt"))bytes[0]^=1;
 ioError=!strcmp(scenario,"io");
 assert(life::supported()&&!life::prepared()&&!life::permitted()&&opens==0);
 auto*service=life::commandService();assert(service&&service==otherService()&&opens==0);
 life::preparePolicy();assert(life::prepared()&&opens==1&&handles==0&&writes==0);
 life::preparePolicy();assert(opens==1);
 assert(service->snapshot().stamp.session==0&&service->snapshot().stamp.view==0);
 assert(service->handle(onboardIndicatorCommandService::Request{}).code==onboardIndicatorCommandService::Code::NotInitialized);
 assert(life::permitted()==always);
 life::timezoneApplied(false);assert(!life::timezoneReady());
 life::timezoneApplied(true);assert(life::timezoneReady());
 assert(life::permitted()==(always||scheduled));
 for(unsigned i=0;i<10000;++i)(void)life::permitted();
 assert(opens==1&&writes==0);
 if(scheduled){
  epoch+=60;assert(!life::permitted());epoch-=60;
  life::invalidateTimezone();assert(!life::timezoneReady()&&!life::permitted());
  life::timezoneApplied(true);assert(life::permitted());
  strcpy(G.timezone,"UTC1");assert(!life::timezoneReady()&&!life::permitted());
  assert(setenv("TZ","UTC1",1)==0);tzset();life::timezoneApplied(true);
  assert(life::timezoneReady()&&!life::permitted());
  strcpy(G.timezone,"UTC0");assert(setenv("TZ","UTC0",1)==0);tzset();
  life::timezoneApplied(true);assert(life::permitted());
 }
 clockError=true;assert(life::permitted()==always);clockError=false;
 epoch=0;assert(life::permitted()==always);epoch=1700000000;
 memset(G.timezone,'X',sizeof(G.timezone));life::timezoneApplied(true);assert(!life::timezoneReady());
 G.timezone[0]=0;life::timezoneApplied(true);assert(!life::timezoneReady());
 strcpy(G.timezone,"UTC0");life::timezoneApplied(true);assert(life::timezoneReady());
 assert(service->begin(99)&&opens==1&&service->snapshot().stamp.view==1);
 assert(service->begin(99)&&!service->begin(100)&&opens==1);
 assert(writes==0&&handles==0);
#else
 (void)argc;(void)argv;
 assert(!life::supported()&&!life::prepared()&&!life::permitted()&&!life::commandService());
 life::preparePolicy();life::invalidateTimezone();life::timezoneApplied(true);
 assert(!life::timezoneReady());
#endif
}
