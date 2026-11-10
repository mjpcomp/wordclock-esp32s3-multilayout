#include "OnboardIndicatorNvsBackend.h"
#include "OnboardIndicatorRuntimeOwner.h"
#include <cassert>
#include <cstring>
#include <vector>
namespace s=onboardIndicatorStorage;namespace r=onboardIndicatorRecord;
namespace p=onboardIndicatorPolicy;namespace o=onboardIndicatorRuntimeOwner;
#if defined(ESP32)
namespace fake {
std::vector<uint8_t> data,pending;
bool space=false,key=false,wrongType=false,persistOnError=false;
esp_err_t openError=ESP_OK,probeError=ESP_OK,fetchError=ESP_OK,setError=ESP_OK,commitError=ESP_OK;
int fetchedSize=-1;
unsigned handles=0,opens=0,readOpens=0,writeOpens=0,probes=0,fetches=0,sets=0,commits=0,closes=0;
void reset(){
 data.clear();pending.clear();space=key=wrongType=persistOnError=false;
 openError=probeError=fetchError=setError=commitError=ESP_OK;fetchedSize=-1;
 handles=opens=readOpens=writeOpens=probes=fetches=sets=commits=closes=0;
}
void installed(){
 const r::Record record={1,p::freshPolicy()};data.resize(r::kBytes);
 assert(r::encode(record,data.data(),data.size()));space=key=true;
}
void balanced(){assert(handles==0&&closes<=opens);}
}
esp_err_t nvs_open(const char *name,nvs_open_mode_t mode,nvs_handle_t *handle){
 assert(!strcmp(name,"wc-onboard"));++fake::opens;
 if(mode==NVS_READONLY)++fake::readOpens;else{assert(mode==NVS_READWRITE);++fake::writeOpens;}
 if(fake::openError!=ESP_OK)return fake::openError;
 if(mode==NVS_READONLY&&!fake::space)return ESP_ERR_NVS_NOT_FOUND;
 if(mode==NVS_READWRITE)fake::space=true;
 assert(fake::handles==0);++fake::handles;*handle=1;return ESP_OK;
}
esp_err_t nvs_get_blob(nvs_handle_t handle,const char *name,void *out,size_t *length){
 assert(handle==1&&fake::handles==1&&!strcmp(name,"policy"));
 if(out)++fake::fetches;else ++fake::probes;
 const esp_err_t error=out?fake::fetchError:fake::probeError;
 if(error!=ESP_OK)return error;
 if(fake::wrongType)return ESP_ERR_NVS_TYPE_MISMATCH;
 if(!fake::key)return ESP_ERR_NVS_NOT_FOUND;
 if(!out){*length=fake::data.size();return ESP_OK;}
 if(*length<fake::data.size()){*length=fake::data.size();return ESP_ERR_NVS_INVALID_LENGTH;}
 if(!fake::data.empty())memcpy(out,fake::data.data(),fake::data.size());
 *length=fake::fetchedSize<0?fake::data.size():size_t(fake::fetchedSize);return ESP_OK;
}
esp_err_t nvs_set_blob(nvs_handle_t handle,const char *name,const void *data,size_t size){
 assert(handle==1&&fake::handles==1&&!strcmp(name,"policy")&&size==r::kBytes);++fake::sets;
 if(fake::wrongType)return ESP_ERR_NVS_TYPE_MISMATCH;
 if(fake::setError!=ESP_OK)return fake::setError;
 const uint8_t *bytes=static_cast<const uint8_t *>(data);
 fake::pending.assign(bytes,bytes+size);return ESP_OK;
}
esp_err_t nvs_commit(nvs_handle_t handle){
 assert(handle==1&&fake::handles==1);++fake::commits;
 if(fake::commitError==ESP_OK||fake::persistOnError){fake::data=fake::pending;fake::key=true;}
 return fake::commitError;
}
void nvs_close(nvs_handle_t handle){assert(handle==1&&fake::handles==1);--fake::handles;++fake::closes;}
#endif
int main(){
 static_assert(r::kBytes==24,"record size");
#if defined(ESP32)
 uint8_t data[24]={};size_t size=99;r::Record out={};
 fake::reset();s::NvsBackend backend;o::Owner owner(backend);
 assert(fake::opens==0);owner.begin();
 assert(!fake::space&&fake::readOpens==1&&!fake::writeOpens&&!fake::sets&&!fake::commits);
 for(unsigned i=0;i<10000;++i){(void)owner.observation();assert(owner.permitted(false,false,0));}
 assert(fake::opens==1);fake::balanced();
 fake::space=true;assert(backend.read(data,sizeof(data),size)==s::ReadResult::Missing&&size==0);fake::balanced();
 fake::installed();size=99;assert(backend.read(nullptr,24,size)==s::ReadResult::Failed&&size==0);
 const unsigned opens=fake::opens;size=99;assert(backend.read(data,23,size)==s::ReadResult::Invalid&&size==0&&fake::opens==opens);
 assert(backend.read(data,24,size)==s::ReadResult::Ok&&size==24);fake::balanced();
 for(size_t length:{size_t(0),size_t(23),size_t(25),size_t(4096)}){
  fake::reset();fake::installed();fake::data.resize(length);size=99;
  assert(backend.read(data,24,size)==s::ReadResult::Invalid&&size==0&&!fake::fetches&&!fake::writeOpens);fake::balanced();
 }
 for(esp_err_t error:{ESP_FAIL,ESP_ERR_NVS_NOT_INITIALIZED}){
  fake::reset();fake::openError=error;size=99;
  assert(backend.read(data,24,size)==s::ReadResult::Failed&&size==0&&!fake::closes);fake::balanced();
 }
 for(esp_err_t error:{ESP_FAIL,ESP_ERR_NVS_TYPE_MISMATCH,ESP_ERR_NVS_NOT_FOUND}){
  fake::reset();fake::installed();fake::probeError=error;size=99;
  const s::ReadResult expected=error==ESP_ERR_NVS_NOT_FOUND?s::ReadResult::Missing:
      error==ESP_ERR_NVS_TYPE_MISMATCH?s::ReadResult::Invalid:s::ReadResult::Failed;
  assert(backend.read(data,24,size)==expected&&size==0&&!fake::fetches);fake::balanced();
 }
 for(esp_err_t error:{ESP_FAIL,ESP_ERR_NVS_TYPE_MISMATCH,ESP_ERR_NVS_NOT_FOUND,ESP_ERR_NVS_INVALID_LENGTH}){
  fake::reset();fake::installed();fake::fetchError=error;size=99;
  assert(backend.read(data,24,size)==s::ReadResult::Failed&&size==0);fake::balanced();
 }
 for(int length:{0,23,25}){
  fake::reset();fake::installed();fake::fetchedSize=length;size=99;
  assert(backend.read(data,24,size)==s::ReadResult::Failed&&size==0);fake::balanced();
 }
 fake::reset();fake::installed();
 const auto good=fake::data;auto bad=good;bad[20]^=1;
 assert(!backend.write(nullptr,24)&&!backend.write(good.data(),23)&&!backend.write(good.data(),25)&&!backend.write(bad.data(),24));
 assert(!fake::opens&&!fake::sets&&!fake::commits);
 fake::openError=ESP_FAIL;assert(!backend.write(good.data(),24)&&!fake::sets&&!fake::commits);fake::balanced();
 fake::reset();fake::installed();fake::setError=ESP_FAIL;
 assert(!backend.write(good.data(),24)&&fake::sets==1&&!fake::commits&&fake::data==good);fake::balanced();
 const p::Policy disabled={p::Mode::Disabled,0,{{0,0},{0,0}}};
 fake::reset();fake::installed();o::Owner live(backend);live.begin();
 assert(live.store().save(1,disabled,out)==s::Result::Ok&&out.revision==2&&!live.permitted(true,true,0));fake::balanced();
 const unsigned writes=fake::writeOpens,commits=fake::commits;
 assert(live.store().save(1,disabled,out)==s::Result::Conflict&&fake::writeOpens==writes&&fake::commits==commits);
 assert(live.store().reset(2,out)==s::Result::Ok&&out.revision==3&&live.permitted(false,false,0));fake::balanced();
 for(bool persisted:{false,true}){
  fake::reset();fake::installed();o::Owner faulted(backend);faulted.begin();
  fake::commitError=ESP_FAIL;fake::persistOnError=persisted;out={77,p::freshPolicy()};
  assert(faulted.store().save(1,disabled,out)==s::Result::WriteUncertain&&out.revision==77);
  assert(faulted.observation().fault&&!faulted.permitted(true,true,0));fake::balanced();
  fake::commitError=ESP_OK;assert(faulted.store().load(out)==s::Result::Ok);
  assert(out.revision==(persisted?2u:1u)&&faulted.permitted(false,false,0)==!persisted);fake::balanced();
 }
 fake::reset();fake::installed();fake::wrongType=true;o::Owner typed(backend);typed.begin();
 assert(typed.observation().fault&&!typed.permitted(true,true,0)&&!fake::writeOpens);
 assert(typed.store().save(0,disabled,out)==s::Result::ResetRequired&&!fake::writeOpens);
 assert(typed.store().reset(0,out)==s::Result::WriteUncertain&&typed.observation().fault&&!fake::commits);fake::balanced();
 fake::reset();fake::openError=ESP_ERR_NVS_NOT_INITIALIZED;s::Store unavailable(backend);
 assert(unavailable.reset(0,out)==s::Result::ReadFailed&&!fake::writeOpens);fake::balanced();
#endif
}
