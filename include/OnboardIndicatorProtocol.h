#pragma once
#include "OnboardIndicatorJsonSyntax.h"
#include "OnboardIndicatorCommandMailbox.h"
#include <ArduinoJson.h>
#include <string.h>

namespace onboardIndicatorProtocol {
namespace c=onboardIndicatorCommandService;namespace m=onboardIndicatorCommandMailbox;
namespace p=onboardIndicatorPolicy;namespace s=onboardIndicatorStorage;
constexpr size_t kMaxInput=onboardIndicatorJsonSyntax::kMaxInput;
constexpr size_t kReplyBytes=1536;
inline bool equals(JsonString text,const char*word){return text.c_str()&&text.size()==strlen(word)&&!memcmp(text.c_str(),word,text.size());}
inline bool stringIs(JsonVariantConst value,const char*word){return value.is<const char*>()&&equals(value.as<JsonString>(),word);}
inline bool fields(JsonObjectConst obj,const char*const*names,size_t count){
 if(obj.isNull()||obj.size()!=count)return false;
 for(JsonPairConst pair:obj){bool found=false;for(size_t i=0;i<count;++i)if(equals(pair.key(),names[i]))found=true;if(!found)return false;}
 return true;
}
inline bool number(JsonVariantConst value,uint32_t limit,uint32_t&out){
 if(value.is<bool>()||!value.is<uint32_t>())return false;
 const uint32_t n=value.as<uint32_t>();if(n>limit)return false;
 out=n;return true;
}
inline bool session(JsonVariantConst value,uint64_t&out){
 if(!value.is<const char*>())return false;
 const JsonString text=value.as<JsonString>();if(text.size()!=16)return false;
 uint64_t result=0;
 for(size_t i=0;i<16;++i){const char v=text.c_str()[i];uint8_t digit=0;
  if(v>='0'&&v<='9')digit=uint8_t(v-'0');else if(v>='a'&&v<='f')digit=uint8_t(v-'a'+10);else return false;
  result=(result<<4)|digit;
 }
 if(!result)return false;
 out=result;return true;
}
inline void sessionText(uint64_t value,char(&out)[17]){
 const char*digits="0123456789abcdef";for(size_t i=0;i<16;++i){out[15-i]=digits[value&15];value>>=4;}out[16]=0;
}
// No partial mutation: request and correlation are replaced only after validation.
inline bool parse(const uint8_t*data,size_t size,c::Request&out,char(&id)[33]){
 size_t keys=0;onboardIndicatorJsonSyntax::Reader syntax(data,size);if(!syntax.complete(keys))return false;
 StaticJsonDocument<1024> doc;
 if(deserializeJson(doc,reinterpret_cast<const char*>(data),size,DeserializationOption::NestingLimit(4))||doc.overflowed())return false;
 JsonObjectConst obj=doc.as<JsonObjectConst>();uint32_t n=0;
 if(obj.isNull()||!stringIs(obj["command"],"onboard-indicator")||!number(obj["schema"],1,n)||n!=1||!obj["requestId"].is<const char*>())return false;
 const JsonString correlation=obj["requestId"].as<JsonString>();char parsedId[33]={};
 if(!correlation.size()||correlation.size()>32)return false;
 memcpy(parsedId,correlation.c_str(),correlation.size());if(!m::validId(parsedId))return false;
 c::Request request={};
 const char*const snapshotKeys[]={"command","schema","requestId","action"};
 const char*const reloadKeys[]={"command","schema","requestId","action","expectedSession","expectedView"};
 const char*const saveKeys[]={"command","schema","requestId","action","expectedSession","expectedView","expectedRevision","mode","windows"};
 const char*const resetKeys[]={"command","schema","requestId","action","expectedSession","expectedView","expectedRevision","confirmReset"};
 if(stringIs(obj["action"],"snapshot")){
  if(!fields(obj,snapshotKeys,4)||keys!=4)return false;
 request.action=c::Action::Snapshot;
 }else{
  if(!session(obj["expectedSession"],request.expected.session)||!number(obj["expectedView"],0xffffffffUL,request.expected.view)||!request.expected.view)return false;
  if(stringIs(obj["action"],"reload")){
   if(!fields(obj,reloadKeys,6)||keys!=6)return false;
 request.action=c::Action::Reload;
  }else{
   if(!number(obj["expectedRevision"],0xffffffffUL,request.expectedRevision))return false;
   if(stringIs(obj["action"],"reset")){
    if(!fields(obj,resetKeys,8)||keys!=8||!obj["confirmReset"].is<bool>()||!obj["confirmReset"].as<bool>())return false;
    request.action=c::Action::Reset;request.confirmReset=true;
   }else if(stringIs(obj["action"],"save")){
    if(!fields(obj,saveKeys,9))return false;
 request.action=c::Action::Save;
    if(stringIs(obj["mode"],"disabled"))request.policy.mode=p::Mode::Disabled;
    else if(stringIs(obj["mode"],"always"))request.policy.mode=p::Mode::AlwaysEnabled;
    else if(stringIs(obj["mode"],"scheduled"))request.policy.mode=p::Mode::Scheduled;else return false;
    JsonArrayConst windows=obj["windows"].as<JsonArrayConst>();
    if(windows.isNull()||windows.size()>2||keys!=9+2*windows.size())return false;
    request.policy.count=uint8_t(windows.size());uint8_t i=0;
    const char*const windowKeys[]={"startMinute","endMinute"};
    for(JsonVariantConst value:windows){JsonObjectConst window=value.as<JsonObjectConst>();
     if(!fields(window,windowKeys,2)||!number(window["startMinute"],1439,n))return false;
 request.policy.windows[i].startMinute=uint16_t(n);
     if(!number(window["endMinute"],1439,n))return false;
 request.policy.windows[i].endMinute=uint16_t(n);++i;
    }
    if(!p::valid(request.policy))return false;
   }else return false;
  }
 }
 out=request;memcpy(id,parsedId,sizeof(parsedId));return true;
}
enum class Frame {Text,Fragment,Other};
enum class Ingress {Queued,NotText,TooLarge,InvalidRequest,InvalidRoute,QueueFull};
inline Ingress enqueue(m::Mailbox&mailbox,m::Route route,Frame frame,const uint8_t*data,size_t size){
 if(frame!=Frame::Text)return Ingress::NotText;
 if(size>kMaxInput)return Ingress::TooLarge;
 if(!route.connection)return Ingress::InvalidRoute;
 m::Envelope value={};value.route=route;if(!parse(data,size,value.request,value.requestId))return Ingress::InvalidRequest;
 return mailbox.enqueue(value)?Ingress::Queued:Ingress::QueueFull;
}
inline const char*actionName(c::Action action){
 switch(action){case c::Action::Snapshot:return "snapshot";case c::Action::Reload:return "reload";case c::Action::Save:return "save";case c::Action::Reset:return "reset";}return "unknown";
}
inline const char*resultName(s::Result result){
 switch(result){case s::Result::Ok:return "ok";case s::Result::Missing:return "missing";case s::Result::ResetRequired:return "reset-required";
 case s::Result::ReadFailed:return "read-failed";case s::Result::InvalidInput:return "invalid-input";case s::Result::Conflict:return "conflict";
 case s::Result::RevisionExhausted:return "revision-exhausted";case s::Result::WriteUncertain:return "write-uncertain";case s::Result::ReadbackUncertain:return "readback-uncertain";}return "error";
}
inline const char*statusName(const c::Reply&reply,c::Action action){
 switch(reply.code){case c::Code::Snapshot:return "snapshot";case c::Code::Completed:
  if(reply.result!=s::Result::Ok)return resultName(reply.result);
  return action==c::Action::Save?"saved":action==c::Action::Reset?"reset":"loaded";
 case c::Code::NotInitialized:return "not-initialized";case c::Code::InvalidRequest:return "invalid-request";case c::Code::StaleView:return "stale-view";
 case c::Code::RevisionMismatch:return "revision-mismatch";case c::Code::ReloadRequired:return "reload-required";case c::Code::ResetRequired:return "reset-required";
 case c::Code::CounterExhausted:return "counter-exhausted";}return "error";
}
inline bool serialize(JsonDocument&doc,char*output,size_t capacity,size_t&used){
 used=0;if(output&&capacity)output[0]=0;
 if(!output||capacity<kReplyBytes||doc.overflowed())return false;
 const size_t expected=measureJson(doc);if(expected>=capacity)return false;
 const size_t written=serializeJson(doc,output,capacity);if(written!=expected){output[0]=0;return false;}
 output[written]=0;used=written;return true;
}
inline bool encodeReply(const m::Envelope&request,const c::Reply&value,char*output,size_t capacity,size_t&used){
 used=0;if(output&&capacity)output[0]=0;if(!m::validId(request.requestId))return false;
 StaticJsonDocument<1024> doc;char token[17]={};sessionText(value.state.stamp.session,token);
 doc["command"]="onboard-indicator";doc["schema"]=1;doc["requestId"]=request.requestId;doc["action"]=actionName(request.request.action);
 doc["status"]=statusName(value,request.request.action);doc["storageAttempted"]=value.storageAttempted;
 if(value.storageAttempted)doc["storageStatus"]=resultName(value.result);else doc["storageStatus"]=nullptr;
 if(value.state.owner.initialized)doc["session"]=token;else doc["session"]=nullptr;
 doc["view"]=value.state.stamp.view;doc["expectedRevision"]=value.state.expectedRevision;doc["reloadRequired"]=value.state.reloadRequired;
 const auto&owner=value.state.owner;doc["initialized"]=owner.initialized;doc["hasRecord"]=owner.hasRecord;doc["storageFault"]=owner.fault;
 doc["draft"]=owner.initialized&&!owner.hasRecord&&!owner.fault;
 if(owner.initialized)doc["lastStorageStatus"]=resultName(owner.lastResult);
 if(owner.initialized&&(!owner.fault||owner.hasRecord)){
  doc["acceptedRevision"]=owner.record.revision;doc["mode"]=owner.record.policy.mode==p::Mode::Disabled?"disabled":owner.record.policy.mode==p::Mode::AlwaysEnabled?"always":"scheduled";
  JsonArray windows=doc.createNestedArray("windows");for(uint8_t i=0;i<owner.record.policy.count;++i){JsonObject window=windows.createNestedObject();window["startMinute"]=owner.record.policy.windows[i].startMinute;window["endMinute"]=owner.record.policy.windows[i].endMinute;}
 }
 return serialize(doc,output,capacity,used);
}
inline bool encodeIngressError(Ingress result,char*output,size_t capacity,size_t&used){
 used=0;if(output&&capacity)output[0]=0;if(result==Ingress::Queued)return false;
 const char*status=result==Ingress::NotText?"complete-text-frame-required":result==Ingress::TooLarge?"frame-too-large":result==Ingress::InvalidRoute?"invalid-route":result==Ingress::QueueFull?"queue-full":"invalid-request";
 StaticJsonDocument<256> doc;doc["command"]="onboard-indicator";doc["schema"]=1;doc["requestId"]=nullptr;doc["status"]=status;
 return serialize(doc,output,capacity,used);
}
}
