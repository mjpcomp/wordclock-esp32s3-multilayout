#pragma once
#include "OnboardIndicatorRuntimeOwner.h"

// Sole serialized owner; backend and service must not be shared/reentered.
// No constructor IO, clocks, GPIO, JSON, sockets, allocation or session RNG.
namespace onboardIndicatorCommandService {
namespace p=onboardIndicatorPolicy;
namespace s=onboardIndicatorStorage;
namespace o=onboardIndicatorRuntimeOwner;
struct Stamp { uint64_t session; uint32_t view; };
inline bool same(Stamp a,Stamp b){return a.session==b.session&&a.view==b.view;}
inline bool advance(Stamp&stamp){if(stamp.view==0xffffffffUL)return false;++stamp.view;return true;}
enum class Action:uint8_t {Snapshot,Reload,Save,Reset};
struct Request {Action action;Stamp expected;uint32_t expectedRevision;p::Policy policy;bool confirmReset;};
enum class Code:uint8_t {Snapshot,Completed,NotInitialized,InvalidRequest,StaleView,RevisionMismatch,ReloadRequired,ResetRequired,CounterExhausted};
struct Snapshot {Stamp stamp;uint32_t expectedRevision;bool reloadRequired;o::Observation owner;};
struct Reply {Code code;bool storageAttempted;s::Result result;Snapshot state;};
class Service {
 o::Owner owner_;Stamp stamp_={0,0};uint32_t revision_=0;bool begun_=false,reload_=true;
 void observed(s::Result result){
  if(result==s::Result::Ok){revision_=owner_.observation().record.revision;reload_=false;}
  else if(result==s::Result::Missing||result==s::Result::ResetRequired){revision_=0;reload_=false;}
  else reload_=true;
 }
 Reply reply(Code code,bool attempted=false,s::Result result=s::Result::InvalidInput)const{
  return Reply{code,attempted,result,snapshot()};
 }
public:
 explicit Service(s::Backend&backend):owner_(backend){}
 Service(const Service&)=delete;Service&operator=(const Service&)=delete;
 // Caller supplies a nonzero session that differs across service lifecycles.
 // True means initialized, not storage healthy. Repeated same-session begin is inert.
 s::Result prepare(){
  if(owner_.observation().initialized)return owner_.observation().lastResult;
  owner_.begin();const s::Result result=owner_.observation().lastResult;observed(result);return result;
 }
 bool begin(uint64_t session){
  if(begun_)return session==stamp_.session;
  if(!session)return false;
  (void)prepare();begun_=true;stamp_={session,1};return true;
 }
 Snapshot snapshot()const{return Snapshot{stamp_,revision_,reload_,owner_.observation()};}
 bool permitted(bool timeValid,bool timezoneReady,uint16_t minute)const{
  return owner_.permitted(timeValid,timezoneReady,minute);
 }
 Reply handle(const Request&request){
  if(!begun_)return reply(Code::NotInitialized);
  if(uint8_t(request.action)>uint8_t(Action::Reset))return reply(Code::InvalidRequest);
  if(request.action==Action::Snapshot)return reply(Code::Snapshot);
  if((request.action==Action::Save&&!p::valid(request.policy))||
     (request.action==Action::Reset&&!request.confirmReset))return reply(Code::InvalidRequest);
  if(!same(request.expected,stamp_))return reply(Code::StaleView);
  if(request.action!=Action::Reload){
   if(reload_)return reply(Code::ReloadRequired);
   if(request.expectedRevision!=revision_)return reply(Code::RevisionMismatch);
   if(request.action==Action::Save&&owner_.observation().fault)return reply(Code::ResetRequired);
  }
  // Invalidate older views BEFORE any possible backend operation; never wrap.
  if(!advance(stamp_))return reply(Code::CounterExhausted);
  s::Record record={};s::Result result=s::Result::InvalidInput;
  switch(request.action){
   case Action::Reload:result=owner_.store().load(record);break;
   case Action::Save:result=owner_.store().save(request.expectedRevision,request.policy,record);break;
   case Action::Reset:result=owner_.store().reset(request.expectedRevision,record);break;
   default:break;
  }
  observed(result);return reply(Code::Completed,true,result);
 }
};
}
