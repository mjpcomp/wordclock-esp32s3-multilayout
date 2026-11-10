#pragma once
#include "OnboardIndicatorStorage.h"

// Single serialized control-loop owner. No GPIO/time APIs/callback-thread IO.
// Ordinary permission/snapshot reads never access the backend or write storage.
namespace onboardIndicatorRuntimeOwner {
namespace storage=onboardIndicatorStorage;
struct Observation {bool initialized,hasRecord,fault;storage::Result lastResult;storage::Record record;};
class Owner {
 storage::Store store_;storage::Record accepted_={};
 bool initialized_=false,everVerified_=false,hasRecord_=false,fault_=true;
 storage::Result lastResult_=storage::Result::Missing;
 static void observe(storage::Result result,const storage::Record*record,void*context){static_cast<Owner*>(context)->accept(result,record);}
 void accept(storage::Result result,const storage::Record*record){
  lastResult_=result;
  if(result==storage::Result::Ok&&record){accepted_=*record;everVerified_=hasRecord_=true;fault_=false;return;}
  if(result==storage::Result::Missing&&!everVerified_){accepted_={0,onboardIndicatorPolicy::freshPolicy()};hasRecord_=false;fault_=false;return;}
  switch(result){
   case storage::Result::Missing:case storage::Result::ResetRequired:case storage::Result::ReadFailed:
   case storage::Result::WriteUncertain:case storage::Result::ReadbackUncertain:fault_=true;break;
   default:break; // Input/conflict/exhaustion errors do not replace accepted data.
  }
 }
public:
 explicit Owner(storage::Backend&backend):store_(backend,observe,this){}
 Owner(const Owner&)=delete;Owner&operator=(const Owner&)=delete;
 // One read-only startup load. Retry only through an explicit later load/action.
 void begin(){if(initialized_)return;initialized_=true;storage::Record record={};(void)store_.load(record);}
 storage::Store&store(){return store_;}
 Observation observation()const{return Observation{initialized_,hasRecord_,fault_,lastResult_,accepted_};}
 // Local-time conversion and timezone readiness are supplied by future wiring.
 // Logical permission is not proof that a hardware sink exists or is dark.
 bool permitted(bool timeValid,bool timezoneReady,uint16_t minute)const{
  return initialized_&&!fault_&&onboardIndicatorPolicy::allows(accepted_.policy,timeValid&&timezoneReady,minute);
 }
};
}
