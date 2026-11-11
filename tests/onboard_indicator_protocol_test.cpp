#include "OnboardIndicatorJsonSyntax.h"
#include <cassert>
#include <cstring>
#include <string>
#include <vector>
#ifndef ONBOARD_SYNTAX_ONLY
#include "OnboardIndicatorProtocol.h"
#endif
bool syntax(const std::string&text){size_t keys=99;onboardIndicatorJsonSyntax::Reader reader(reinterpret_cast<const uint8_t*>(text.data()),text.size());return reader.complete(keys);}
#ifndef ONBOARD_SYNTAX_ONLY
namespace wire=onboardIndicatorProtocol;namespace c=onboardIndicatorCommandService;namespace m=onboardIndicatorCommandMailbox;
namespace s=onboardIndicatorStorage;namespace p=onboardIndicatorPolicy;namespace r=onboardIndicatorRecord;
struct Memory:s::Backend{
 std::vector<uint8_t> bytes;bool present=false,fail=false;unsigned reads=0,writes=0;
 s::ReadResult read(uint8_t*data,size_t capacity,size_t&size)override{++reads;size=0;if(!present)return s::ReadResult::Missing;if(bytes.size()>capacity)return s::ReadResult::Invalid;size=bytes.size();memcpy(data,bytes.data(),size);return s::ReadResult::Ok;}
 bool write(const uint8_t*data,size_t size)override{++writes;if(fail)return false;bytes.assign(data,data+size);present=true;return true;}
};
bool parse(const std::string&text,c::Request&request,char(&id)[33]){return wire::parse(reinterpret_cast<const uint8_t*>(text.data()),text.size(),request,id);}
std::string changed(std::string text,const std::string&old,const std::string&value){const auto at=text.find(old);assert(at!=std::string::npos);text.replace(at,old.size(),value);return text;}
struct Output {m::Route live={1,7};std::string text;bool fail=false;};
bool current(const m::Route&route,void*context){const auto live=static_cast<Output*>(context)->live;return route.client==live.client&&route.connection==live.connection;}
bool send(const m::Envelope&request,const c::Reply&reply,void*context){auto&out=*static_cast<Output*>(context);char data[wire::kReplyBytes];size_t size=0;assert(wire::encodeReply(request,reply,data,sizeof(data),size));out.text.assign(data,size);return !out.fail;}
#endif
int main(){
 assert(syntax(R"({"a":[{"b":12},{"b":0}],"c":true})"));
 for(const std::string text:{"", "[]", "{}{}", "{} junk", "{a:1}", "{\"a\":1,}", "{\"a\":[1,]}", "{\"a\":01}", "{\"a\":-1}", "{\"a\":1.0}", "{\"a\":1e2}", "{\"a\":/*x*/1}", "{\"a\":\"\\u0061\"}", "{\"a\":\"\\n\"}", "{\"a\":true false}", "{\"a\":[[[[0]]]]}"})assert(!syntax(text));
 assert(!syntax(std::string(1025,' ')));assert(!syntax(std::string("{\"a\":\"")+char(0x80)+"\"}"));
#ifndef ONBOARD_SYNTAX_ONLY
 {
  Memory fresh; c::Service prepared(fresh);
  assert(prepared.prepare()==s::Result::Missing&&fresh.reads==1);
  prepared.prepare();assert(fresh.reads==1);
  m::Envelope boot={};strcpy(boot.requestId,"boot");boot.request.action=c::Action::Snapshot;
  char data[wire::kReplyBytes];size_t count=0;
  auto notReady=prepared.handle(c::Request{});
  assert(wire::encodeReply(boot,notReady,data,sizeof(data),count));
  StaticJsonDocument<1536> decoded;
  assert(!deserializeJson(decoded,static_cast<const char*>(data),count));
  assert(decoded["session"].isNull()&&decoded["initialized"].as<bool>());
  assert(!strcmp(decoded["status"],"not-initialized"));
  assert(prepared.begin(7)&&fresh.reads==1);
 }
 const std::string snapshot=R"({"command":"onboard-indicator","schema":1,"requestId":"tab-1","action":"snapshot"})";
 const std::string reload=R"({"command":"onboard-indicator","schema":1,"requestId":"r","action":"reload","expectedSession":"ffffffffffffffff","expectedView":1})";
 const std::string save=R"({"command":"onboard-indicator","schema":1,"requestId":"s","action":"save","expectedSession":"ffffffffffffffff","expectedView":1,"expectedRevision":0,"mode":"scheduled","windows":[{"startMinute":1200,"endMinute":420}]})";
 const std::string reset=R"({"command":"onboard-indicator","schema":1,"requestId":"x","action":"reset","expectedSession":"ffffffffffffffff","expectedView":1,"expectedRevision":0,"confirmReset":true})";
 c::Request request={};char id[33]={};assert(parse(snapshot,request,id)&&request.action==c::Action::Snapshot&&!strcmp(id,"tab-1"));
 assert(parse(reload,request,id)&&request.action==c::Action::Reload&&request.expected.session==~uint64_t(0));
 assert(parse(save,request,id)&&request.policy.windows[0].startMinute==1200&&request.policy.windows[0].endMinute==420);
 assert(parse(reset,request,id)&&request.confirmReset);
 char hex[17];wire::sessionText(~uint64_t(0),hex);assert(!strcmp(hex,"ffffffffffffffff"));
 wire::sessionText(uint64_t(9007199254740993ULL),hex);assert(!strcmp(hex,"0020000000000001"));
 for(const auto&text:std::vector<std::string>{
  changed(snapshot,"\"schema\":1","\"schema\":true"),changed(snapshot,"\"schema\":1","\"schema\":\"1\""),changed(snapshot,"\"schema\":1","\"schema\":2"),
  changed(snapshot,"\"action\":\"snapshot\"","\"action\":\"snapshot\",\"action\":\"snapshot\""),changed(snapshot,"\"action\":\"snapshot\"","\"action\":\"get\""),
  changed(snapshot,"\"action\":\"snapshot\"","\"action\":\"snapshot\",\"extra\":0"),changed(snapshot,"tab-1","bad!"),changed(snapshot,"tab-1",std::string(33,'a')),
  changed(reload,"ffffffffffffffff","0000000000000000"),changed(reload,"ffffffffffffffff","FFFFFFFFFFFFFFFF"),changed(reload,"ffffffffffffffff","fffffffffffffff"),
  changed(reload,"\"ffffffffffffffff\"","9007199254740993"),changed(reload,"\"expectedView\":1","\"expectedView\":0"),changed(reload,"\"expectedView\":1","\"expectedView\":4294967296"),
  changed(save,"\"expectedRevision\":0","\"expectedRevision\":false"),changed(save,"1200","1440"),changed(save,"1200","true"),changed(save,"1200","420"),
  changed(save,"\"startMinute\":1200","\"startMinute\":1200,\"startMinute\":1200"),changed(save,"\"windows\":[{\"startMinute\":1200,\"endMinute\":420}]","\"windows\":[]"),
  changed(reset,"\"confirmReset\":true","\"confirmReset\":1"),changed(reset,"\"confirmReset\":true","\"confirmReset\":false"),snapshot+" {}"}){
   request.action=c::Action::Reset;request.expectedRevision=77;strcpy(id,"unchanged");assert(!parse(text,request,id)&&request.action==c::Action::Reset&&request.expectedRevision==77&&!strcmp(id,"unchanged"));
 }
 const auto maxRevision=changed(reset,"\"expectedRevision\":0","\"expectedRevision\":4294967295");assert(parse(maxRevision,request,id)&&request.expectedRevision==0xffffffffUL);
 const auto two=changed(save,"[{\"startMinute\":1200,\"endMinute\":420}]","[{\"startMinute\":0,\"endMinute\":420},{\"startMinute\":420,\"endMinute\":1200}]");assert(parse(two,request,id)&&request.policy.count==2);
 assert(!parse(changed(two,"\"startMinute\":420","\"startMinute\":400"),request,id));
 const auto maxId=changed(snapshot,"tab-1",std::string(32,'a'));assert(parse(maxId,request,id));
 Memory memory;c::Service service(memory);assert(service.begin(~uint64_t(0)));m::Mailbox queue;Output out;const unsigned reads=memory.reads;
 auto enqueue=[&](const std::string&text,wire::Frame frame=wire::Frame::Text){return wire::enqueue(queue,{1,7},frame,reinterpret_cast<const uint8_t*>(text.data()),text.size());};
 assert(enqueue(save,wire::Frame::Fragment)==wire::Ingress::NotText&&enqueue(std::string(1025,'x'))==wire::Ingress::TooLarge);
 assert(enqueue("{}") ==wire::Ingress::InvalidRequest&&queue.size()==0&&memory.reads==reads&&memory.writes==0);
 assert(wire::enqueue(queue,{1,0},wire::Frame::Text,reinterpret_cast<const uint8_t*>(save.data()),save.size())==wire::Ingress::InvalidRoute);
 assert(enqueue(save)==wire::Ingress::Queued&&memory.writes==0&&memory.reads==reads);
 assert(queue.consumeOne(service,current,send,&out)==m::Drain::Delivered&&memory.writes==1);
 StaticJsonDocument<1536> reply;assert(!deserializeJson(reply,out.text));assert(!strcmp(reply["status"],"saved")&&!strcmp(reply["session"],"ffffffffffffffff"));assert(reply["storageAttempted"].as<bool>()&&reply["expectedRevision"].as<uint32_t>()==1&&reply["view"].as<uint32_t>()==2);
 assert(enqueue(save)==wire::Ingress::Queued);assert(queue.consumeOne(service,current,send,&out)==m::Drain::Delivered&&memory.writes==1);reply.clear();assert(!deserializeJson(reply,out.text)&&!strcmp(reply["status"],"stale-view")&&!reply["storageAttempted"].as<bool>());
 for(unsigned i=0;i<4;++i)assert(enqueue(snapshot)==wire::Ingress::Queued);
 assert(enqueue(snapshot)==wire::Ingress::QueueFull);
 while(queue.size())assert(queue.consumeOne(service,current,send,&out)==m::Drain::Delivered);
 assert(enqueue(save)==wire::Ingress::Queued);out.live.connection=8;const unsigned before=memory.reads;assert(queue.consumeOne(service,current,send,&out)==m::Drain::Dropped&&memory.reads==before&&memory.writes==1);
 char output[wire::kReplyBytes];size_t used=99;assert(wire::encodeIngressError(wire::Ingress::QueueFull,output,sizeof(output),used));reply.clear();assert(!deserializeJson(reply,static_cast<const char*>(output),used)&&!strcmp(reply["status"],"queue-full")&&reply["requestId"].isNull());
 assert(!wire::encodeIngressError(wire::Ingress::Queued,output,sizeof(output),used)&&used==0);
 assert(!wire::encodeIngressError(wire::Ingress::QueueFull,output,1,used)&&used==0&&output[0]==0);
 assert(!wire::encodeIngressError(wire::Ingress::QueueFull,nullptr,0,used)&&used==0);
 m::Envelope env={};env.route={1,7};strcpy(env.requestId,"reply");env.request.action=c::Action::Snapshot;
 auto value=service.handle(c::Request{});assert(wire::encodeReply(env,value,output,sizeof(output),used));reply.clear();assert(!deserializeJson(reply,static_cast<const char*>(output),used)&&!strcmp(reply["status"],"snapshot")&&reply["storageStatus"].isNull());
 env.requestId[0]=0;assert(!wire::encodeReply(env,value,output,sizeof(output),used)&&used==0);
#endif
}
