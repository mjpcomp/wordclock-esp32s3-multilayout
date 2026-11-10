#include "OnboardIndicatorCommandMailbox.h"
#include <cassert>
#include <cstring>
#include <string>
#include <vector>
namespace c=onboardIndicatorCommandService;namespace m=onboardIndicatorCommandMailbox;
namespace p=onboardIndicatorPolicy;namespace s=onboardIndicatorStorage;namespace r=onboardIndicatorRecord;
struct Memory:s::Backend{
 std::vector<uint8_t> data;bool present=false,readFailed=false,writeFailed=false,persistDespite=false,readbackFailed=false,corruptReadback=false;
 unsigned reads=0,writes=0;
 s::ReadResult read(uint8_t*out,size_t capacity,size_t&size)override{
  ++reads;size=0;if(readFailed||(readbackFailed&&writes))return s::ReadResult::Failed;
  if(!present)return s::ReadResult::Missing;
  if(data.size()>capacity)return s::ReadResult::Invalid;
  size=data.size();if(size)memcpy(out,data.data(),size);
  if(corruptReadback&&writes&&size)out[0]^=1;
  return s::ReadResult::Ok;
 }
 bool write(const uint8_t*in,size_t size)override{
  ++writes;if(!writeFailed||persistDespite){data.assign(in,in+size);present=true;}return !writeFailed;
 }
 void install(uint32_t revision,const p::Policy&policy=p::freshPolicy()){
  const r::Record record={revision,policy};data.resize(r::kBytes);assert(r::encode(record,data.data(),data.size()));present=true;
 }
};
c::Request request(c::Service&service,c::Action action){
 const auto state=service.snapshot();return c::Request{action,state.stamp,state.expectedRevision,p::freshPolicy(),action==c::Action::Reset};
}
const p::Policy disabled={p::Mode::Disabled,0,{{0,0},{0,0}}};
struct Routing{
 m::Route live={1,10};bool fail=false;unsigned sent=0;std::vector<std::string> ids;c::Reply last={};
};
bool current(const m::Route&route,void*context){const auto&live=static_cast<Routing*>(context)->live;return route.client==live.client&&route.connection==live.connection;}
bool send(const m::Envelope&value,const c::Reply&reply,void*context){auto&state=*static_cast<Routing*>(context);++state.sent;state.ids.emplace_back(value.requestId);state.last=reply;return !state.fail;}
m::Envelope envelope(c::Service&service,c::Action action,const char*id="request"){
 m::Envelope value={};value.route={1,10};strcpy(value.requestId,id);value.request=request(service,action);return value;
}
int main(){
 Memory memory;c::Service service(memory);assert(memory.reads==0&&memory.writes==0);
 assert(service.handle(c::Request{}).code==c::Code::NotInitialized);
 assert(!service.begin(0)&&memory.reads==0);assert(service.begin(100)&&memory.reads==1);
 assert(service.begin(100)&&!service.begin(101)&&memory.reads==1);
 assert(service.snapshot().expectedRevision==0&&!service.snapshot().owner.fault&&!service.snapshot().reloadRequired);
 for(unsigned i=0;i<10000;++i){assert(service.handle(request(service,c::Action::Snapshot)).code==c::Code::Snapshot);(void)service.snapshot();assert(service.permitted(false,false,0));}
 assert(memory.reads==1&&memory.writes==0);
 auto first=request(service,c::Action::Save);first.policy=disabled;const auto stale=first;
 auto reply=service.handle(first);assert(reply.storageAttempted&&reply.result==s::Result::Ok&&reply.state.expectedRevision==1&&!service.permitted(true,true,0));
 unsigned reads=memory.reads,writes=memory.writes;
 assert(service.handle(stale).code==c::Code::StaleView&&memory.reads==reads&&memory.writes==writes);
 auto bad=request(service,c::Action::Save);bad.policy.count=3;
 assert(service.handle(bad).code==c::Code::InvalidRequest);
 bad=request(service,c::Action::Reset);bad.confirmReset=false;assert(service.handle(bad).code==c::Code::InvalidRequest);
 bad=request(service,c::Action::Save);bad.expectedRevision=0;assert(service.handle(bad).code==c::Code::RevisionMismatch);
 bad=request(service,c::Action::Save);bad.action=static_cast<c::Action>(255);assert(service.handle(bad).code==c::Code::InvalidRequest);
 assert(memory.reads==reads&&memory.writes==writes);
 c::Service reboot(memory);assert(reboot.begin(200));bad=request(service,c::Action::Save);
 assert(reboot.handle(bad).code==c::Code::StaleView);
 memory.install(7);first=request(service,c::Action::Save);reply=service.handle(first);
 assert(reply.result==s::Result::Conflict&&reply.state.reloadRequired);
 reads=memory.reads;writes=memory.writes;
 assert(service.handle(request(service,c::Action::Save)).code==c::Code::ReloadRequired);
 assert(service.handle(request(service,c::Action::Reset)).code==c::Code::ReloadRequired&&memory.reads==reads&&memory.writes==writes);
 reply=service.handle(request(service,c::Action::Reload));assert(reply.result==s::Result::Ok&&reply.state.expectedRevision==7&&!reply.state.reloadRequired);
 // ABA: record revision returns to 1 after loss/reset, but the view never returns.
 Memory aba;aba.install(1,disabled);c::Service fenced(aba);assert(fenced.begin(300));const auto oldTab=request(fenced,c::Action::Save);
 aba.present=false;reply=fenced.handle(request(fenced,c::Action::Reload));
 assert(reply.result==s::Result::Missing&&reply.state.owner.fault&&reply.state.expectedRevision==0);
 reads=aba.reads;assert(fenced.handle(request(fenced,c::Action::Save)).code==c::Code::ResetRequired&&aba.reads==reads);
 reply=fenced.handle(request(fenced,c::Action::Reset));assert(reply.result==s::Result::Ok&&reply.state.expectedRevision==1&&!reply.state.owner.fault);
 reads=aba.reads;writes=aba.writes;assert(fenced.handle(oldTab).code==c::Code::StaleView&&aba.reads==reads&&aba.writes==writes);
 for(bool persisted:{false,true}){
  Memory device;device.install(1);c::Service owner(device);assert(owner.begin(400));
  device.writeFailed=true;device.persistDespite=persisted;auto save=request(owner,c::Action::Save);save.policy=disabled;
  reply=owner.handle(save);assert(reply.result==s::Result::WriteUncertain&&reply.state.reloadRequired&&reply.state.owner.fault);
  reads=device.reads;writes=device.writes;
  assert(owner.handle(request(owner,c::Action::Reset)).code==c::Code::ReloadRequired&&device.reads==reads&&device.writes==writes);
  device.writeFailed=false;reply=owner.handle(request(owner,c::Action::Reload));
  assert(reply.result==s::Result::Ok&&!reply.state.reloadRequired&&!reply.state.owner.fault);
  assert(reply.state.expectedRevision==(persisted?2u:1u)&&owner.permitted(false,false,0)==!persisted);
 }
 for(bool corrupt:{false,true}){
  Memory device;device.install(1);c::Service owner(device);assert(owner.begin(500));
  device.corruptReadback=corrupt;device.readbackFailed=!corrupt;
  reply=owner.handle(request(owner,c::Action::Save));assert(reply.result==s::Result::ReadbackUncertain&&reply.state.reloadRequired&&reply.state.owner.fault);
  device.corruptReadback=device.readbackFailed=false;reply=owner.handle(request(owner,c::Action::Reload));assert(reply.result==s::Result::Ok&&!reply.state.owner.fault);
 }
 Memory broken;broken.install(3);broken.data[0]^=1;c::Service corrupt(broken);assert(corrupt.begin(600));
 assert(corrupt.snapshot().expectedRevision==0&&corrupt.snapshot().owner.fault);
 assert(corrupt.handle(request(corrupt,c::Action::Save)).code==c::Code::ResetRequired);
 reply=corrupt.handle(request(corrupt,c::Action::Reset));assert(reply.result==s::Result::Ok&&reply.state.expectedRevision==1);
 Memory offline;offline.readFailed=true;c::Service unavailable(offline);assert(unavailable.begin(700));
 assert(unavailable.handle(request(unavailable,c::Action::Save)).code==c::Code::ReloadRequired);
 assert(unavailable.handle(request(unavailable,c::Action::Reset)).code==c::Code::ReloadRequired&&offline.writes==0);
 offline.readFailed=false;assert(unavailable.handle(request(unavailable,c::Action::Reload)).result==s::Result::Missing);
 c::Stamp limit={9,0xfffffffeUL};assert(c::advance(limit)&&limit.view==0xffffffffUL);assert(!c::advance(limit)&&limit.view==0xffffffffUL);
 Memory queued;c::Service consumer(queued);assert(consumer.begin(800));m::Mailbox box;Routing routing;
 auto item=envelope(consumer,c::Action::Snapshot,"one");reads=queued.reads;
 assert(box.enqueue(item));item.requestId[0]='x';
 assert(box.enqueue(envelope(consumer,c::Action::Snapshot,"two"))&&box.enqueue(envelope(consumer,c::Action::Snapshot,"three"))&&box.enqueue(envelope(consumer,c::Action::Snapshot,"four")));
 assert(!box.enqueue(envelope(consumer,c::Action::Save))&&box.size()==4&&queued.reads==reads&&queued.writes==0);
 assert(box.consumeOne(consumer,nullptr,send,&routing)==m::Drain::Unavailable&&box.size()==4);
 for(unsigned i=0;i<4;++i)assert(box.consumeOne(consumer,current,send,&routing)==m::Drain::Delivered);
 assert((routing.ids==std::vector<std::string>{"one","two","three","four"})&&queued.reads==reads&&queued.writes==0);
 assert(box.consumeOne(consumer,current,send,&routing)==m::Drain::Empty);
 item=envelope(consumer,c::Action::Save);item.route.connection=0;assert(!box.enqueue(item));
 item=envelope(consumer,c::Action::Save);memset(item.requestId,'a',33);assert(!box.enqueue(item));
 item=envelope(consumer,c::Action::Save);item.requestId[0]=0;assert(!box.enqueue(item));
 item=envelope(consumer,c::Action::Save);item.requestId[0]='!';assert(!box.enqueue(item));
 item=envelope(consumer,c::Action::Save);assert(box.enqueue(item));routing.live.connection=11;
 assert(box.consumeOne(consumer,current,send,&routing)==m::Drain::Dropped&&queued.reads==reads&&queued.writes==0);
 routing.live.connection=10;routing.fail=true;item=envelope(consumer,c::Action::Save);item.request.policy=disabled;assert(box.enqueue(item));
 assert(box.consumeOne(consumer,current,send,&routing)==m::Drain::ReplyFailed&&queued.writes==1&&box.size()==0);
 assert(box.consumeOne(consumer,current,send,&routing)==m::Drain::Empty&&queued.writes==1);
 routing.fail=false;assert(box.enqueue(item));assert(box.consumeOne(consumer,current,send,&routing)==m::Drain::Delivered&&routing.last.code==c::Code::StaleView&&queued.writes==1);
}
