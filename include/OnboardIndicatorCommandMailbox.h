#pragma once
#include "OnboardIndicatorCommandService.h"
#include <stddef.h>

// Single serialized context, NOT a mutex/ISR-safe or cross-task queue.
// Caller owns synchronization, connection generations and non-reentrant callbacks.
namespace onboardIndicatorCommandMailbox {
namespace c=onboardIndicatorCommandService;
struct Route {uint8_t client;uint64_t connection;};
struct Envelope {Route route;char requestId[33];c::Request request;};
using Current=bool(*)(const Route&,void*);
using Sender=bool(*)(const Envelope&,const c::Reply&,void*);
enum class Drain {Empty,Unavailable,Dropped,Delivered,ReplyFailed};
inline bool validId(const char(&id)[33]){
 for(size_t i=0;i<33;++i){
  const char v=id[i];if(!v)return i!=0;
  if(!((v>='a'&&v<='z')||(v>='A'&&v<='Z')||(v>='0'&&v<='9')||v=='-'||v=='_'))return false;
 }
 return false;
}
class Mailbox {
 Envelope slots_[4]={};uint8_t head_=0,count_=0;
public:
 Mailbox()=default;
 Mailbox(const Mailbox&)=delete;Mailbox&operator=(const Mailbox&)=delete;
 size_t size()const{return count_;}
 // Copies all data; overflow/invalid route/ID never invokes service or storage.
 bool enqueue(const Envelope&value){
  if(count_==4||!value.route.connection||!validId(value.requestId))return false;
  slots_[(head_+count_)%4]=value;++count_;return true;
 }
 // Consumer only. At most one command; no retry, broadcast or automatic replay.
 // Connection validity is checked at dequeue, not an atomic disconnect guarantee.
 Drain consumeOne(c::Service&service,Current current,Sender send,void*context){
  if(!count_)return Drain::Empty;
  if(!current||!send)return Drain::Unavailable;
  const Envelope value=slots_[head_];head_=(head_+1)%4;--count_;
  if(!current(value.route,context))return Drain::Dropped;
  const c::Reply reply=service.handle(value.request);
  // Sender pointers/references are borrowed only for this synchronous callback.
  return send(value,reply,context)?Drain::Delivered:Drain::ReplyFailed;
 }
};
}
