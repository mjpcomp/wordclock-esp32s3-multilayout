#pragma once
#include "OnboardIndicatorRecord.h"

// Serialized byte-store boundary. No NVS implementation, erase or constructor IO.
// Port the Backend to its own namespace later; never use wc-bright/schedule.
namespace onboardIndicatorStorage {
using Record=onboardIndicatorRecord::Record;
enum class Result {Ok,Missing,ResetRequired,ReadFailed,InvalidInput,Conflict,RevisionExhausted,WriteUncertain,ReadbackUncertain};
enum class ReadResult {Ok,Missing,Invalid,Failed};
class Backend {
public:
 virtual ~Backend()=default;
 // Implementations must not write past capacity; invalid size/type is Invalid.
 virtual ReadResult read(uint8_t*data,size_t capacity,size_t&size)=0;
 // False is an uncertain outcome, NOT proof that stored bytes are unchanged.
 virtual bool write(const uint8_t*data,size_t size)=0;
};
// Callback record pointers are borrowed only during this synchronous callback.
// Do not reenter Store, perform IO, or retain the pointer; copy accepted data.
using Observer=void(*)(Result,const Record*,void*);
class Store {
 Backend&backend_;Observer observer_;void*context_;
 Result loadRaw(Record&out){
  uint8_t data[onboardIndicatorRecord::kBytes]={0};size_t size=0;
  const ReadResult result=backend_.read(data,sizeof(data),size);
  if(result==ReadResult::Missing)return Result::Missing;
  if(result==ReadResult::Invalid)return Result::ResetRequired;
  if(result!=ReadResult::Ok)return Result::ReadFailed;
  return onboardIndicatorRecord::decode(data,size,out)?Result::Ok:Result::ResetRequired;
 }
 void notify(Result result,const Record&record){if(observer_)observer_(result,result==Result::Ok?&record:nullptr,context_);}
 Result persist(const Record&candidate,Record&out){
  uint8_t expected[onboardIndicatorRecord::kBytes]={0};
  if(!onboardIndicatorRecord::encode(candidate,expected,sizeof(expected)))return Result::InvalidInput;
  if(!backend_.write(expected,sizeof(expected)))return Result::WriteUncertain;
  Record verified={};if(loadRaw(verified)!=Result::Ok)return Result::ReadbackUncertain;
  uint8_t actual[onboardIndicatorRecord::kBytes]={0};
  if(!onboardIndicatorRecord::encode(verified,actual,sizeof(actual))||memcmp(actual,expected,sizeof(actual)))return Result::ReadbackUncertain;
  out=verified;return Result::Ok;
 }
 Result replace(uint32_t expectedRevision,const onboardIndicatorPolicy::Policy&policy,bool explicitReset,Record&out){
  if(!onboardIndicatorPolicy::valid(policy))return Result::InvalidInput;
  Record current={};const Result loaded=loadRaw(current);
  if(loaded==Result::ReadFailed)return loaded;
  if(loaded==Result::ResetRequired&&!explicitReset)return loaded;
  const uint32_t revision=loaded==Result::Ok?current.revision:0;
  if(expectedRevision!=revision)return Result::Conflict;
  if(revision==0xffffffffUL)return Result::RevisionExhausted;
  const Record candidate={revision+1,policy};return persist(candidate,out);
 }
public:
 explicit Store(Backend&backend,Observer observer=nullptr,void*context=nullptr):backend_(backend),observer_(observer),context_(context){}
 Store(const Store&)=delete;Store&operator=(const Store&)=delete;
 Result load(Record&out){const Result result=loadRaw(out);notify(result,out);return result;}
 Result save(uint32_t expectedRevision,const onboardIndicatorPolicy::Policy&policy,Record&out){const Result result=replace(expectedRevision,policy,false,out);notify(result,out);return result;}
 // Explicit reset only; unreadable IO is never treated as permission to reset.
 // Missing/corrupt lineage starts at revision 1. This is not an epoch identifier.
 Result reset(uint32_t expectedRevision,Record&out){const Result result=replace(expectedRevision,onboardIndicatorPolicy::freshPolicy(),true,out);notify(result,out);return result;}
};
}
