#include "BrightnessScheduleProtocol.h"
#include <assert.h>
#include <string>
#include <vector>
namespace proto = brightnessScheduleProtocol;
using namespace brightnessScheduleStorage;
class Memory : public Backend {
public:
 std::vector<uint8_t> data;
 unsigned reads=0,writes=0;
 bool failRead=false,failWrite=false,changedDespiteFailure=false,badReadback=false;
 ReadResult read(uint8_t *out,size_t cap,size_t &size) override {
  ++reads;if(failRead||(badReadback&&writes))return ReadResult::Failed;
  if(data.empty())return ReadResult::Missing;
  if(data.size()>cap)return ReadResult::Invalid;
  size=data.size();memcpy(out,data.data(),size);return ReadResult::Ok;
 }
 bool write(const uint8_t *p,size_t size) override {
  ++writes;if(!failWrite||changedDespiteFailure)data.assign(p,p+size);return !failWrite;
 }
};
static std::string call(Store &store,const std::string &request) {
 char output[proto::MIN_OUTPUT];size_t size=0;
 assert(proto::handle(store,reinterpret_cast<const uint8_t *>(request.data()),request.size(),output,sizeof(output),size));
 assert(size<sizeof(output)&&output[size]==0);
 return std::string(output,size);
}
static std::string status(Store &store,const std::string &request) {
 DynamicJsonDocument doc(proto::RESPONSE_CAPACITY);
 const std::string response=call(store,request);
 assert(!deserializeJson(doc,response));
 assert(doc["command"]=="brightness-schedule"&&doc["schema"]==1);
 return doc["status"].as<std::string>();
}
int main() {
 const std::string get=R"({"command":"brightness-schedule","schema":1,"requestId":"g","action":"get"})";
 const std::string save=R"({"command":"brightness-schedule","schema":1,"requestId":"s","action":"save","expectedRevision":0,"defaultTenths":400,"events":[{"minute":420,"targetTenths":400,"fadeMinutes":10},{"minute":1185,"targetTenths":100,"fadeMinutes":15},{"minute":1230,"targetTenths":0,"fadeMinutes":5}]})";
 const std::string reset=R"({"command":"brightness-schedule","schema":1,"requestId":"r","action":"reset","expectedRevision":1,"confirmReset":true})";
 Memory memory;Store store(memory);
 assert(status(store,get)=="missing"&&!memory.writes);
 assert(status(store,save)=="saved"&&memory.writes==1);
 DynamicJsonDocument reply(proto::RESPONSE_CAPACITY);
 assert(!deserializeJson(reply,call(store,get)));
 assert(reply["status"]=="loaded"&&reply["requestId"]=="g"&&reply["revision"]==1);
 assert(reply["events"].size()==3&&reply["events"][1]["minute"]==1185);
 assert(status(store,save)=="conflict"&&memory.writes==1);
 const unsigned reads=memory.reads,writes=memory.writes;
 std::vector<std::string> invalid={
  "", "[]", get+"x", get+"{}", "{broken}",
  R"({command:"brightness-schedule","schema":1,"requestId":"g","action":"get"})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"g","action":"get","action":"get"})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"g","action":"get","extra":1})",
  R"({"command":"brightness-schedule","schema":true,"requestId":"g","action":"get"})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"g\u0000x","action":"get"})",
  R"({"command":"brightness-schedule\u0000x","schema":1,"requestId":"g","action":"get"})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"g","action":"delete"})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"r","action":"reset","expectedRevision":1,"confirmReset":false})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"r","action":"reset","expectedRevision":1,"confirmReset":1})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"s","action":"save","expectedRevision":-1,"defaultTenths":400,"events":[]})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"s","action":"save","expectedRevision":4294967296,"defaultTenths":400,"events":[]})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"s","action":"save","expectedRevision":1,"defaultTenths":1001,"events":[]})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"s","action":"save","expectedRevision":1,"defaultTenths":true,"events":[]})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"s","action":"save","expectedRevision":1,"defaultTenths":1.0,"events":[]})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"s","action":"save","expectedRevision":1,"defaultTenths":400,"events":null})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"s","action":"save","expectedRevision":1,"defaultTenths":400,"events":[{"minute":0,"targetTenths":100,"fadeMinutes":0},{"minute":0,"targetTenths":200,"fadeMinutes":0}]})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"s","action":"save","expectedRevision":1,"defaultTenths":400,"events":[{"minute":1,"targetTenths":100,"fadeMinutes":10},{"minute":5,"targetTenths":200,"fadeMinutes":0}]})",
  R"({"command":"brightness-schedule","schema":1,"requestId":"s","action":"save","expectedRevision":1,"defaultTenths":400,"events":[{"minute":1,"targetTenths":100,"targetTenths":200,"fadeMinutes":0}]})"
 };
 invalid.push_back(std::string(2049,' '));
 std::string rawNul=get;rawNul.insert(2,1,'\0');invalid.push_back(rawNul);
 for(const std::string &request:invalid)assert(status(store,request)=="invalid-request");
 assert(memory.reads==reads&&memory.writes==writes);
 char small[8];size_t used=99;
 assert(!proto::handle(store,reinterpret_cast<const uint8_t *>(save.data()),save.size(),small,sizeof(small),used));
 assert(!used&&memory.reads==reads&&memory.writes==writes);
 assert(!deserializeJson(reply,call(store,invalid[8])));
 assert(reply["requestId"]=="g");
 assert(status(store,reset)=="reset"&&memory.writes==2);
 assert(!deserializeJson(reply,call(store,get)));
 assert(reply["revision"]==2&&reply["defaultTenths"]==1000&&reply["events"].size()==0);
 Memory fullMemory;Store full(fullMemory);
 std::string maximum=R"({"command":"brightness-schedule","schema":1,"requestId":"maximum","action":"save","expectedRevision":0,"defaultTenths":1000,"events":[)";
 for(unsigned i=0;i<16;++i) {
  if(i)maximum+=",";
  maximum+="{\"minute\":"+std::to_string(i*90)+",\"targetTenths\":1000,\"fadeMinutes\":90}";
 }
 maximum+="]}";
 assert(status(full,maximum)=="saved");
 assert(!deserializeJson(reply,call(full,get))&&reply["events"].size()==16);
 Memory brokenMemory;brokenMemory.data.assign(3,1);Store broken(brokenMemory);
 assert(status(broken,get)=="reset-required"&&!brokenMemory.writes);
 assert(status(broken,save)=="reset-required"&&!brokenMemory.writes);
 Memory io;io.failRead=true;Store unavailable(io);
 assert(status(unavailable,get)=="read-failed"&&!io.writes);
 Memory uncertain;uncertain.failWrite=uncertain.changedDespiteFailure=true;Store ambiguous(uncertain);
 assert(status(ambiguous,save)=="write-uncertain");
 assert(!deserializeJson(reply,call(ambiguous,save))&&reply["reloadRequired"]==true&&!reply.containsKey("revision"));
 Memory readback;readback.badReadback=true;Store verify(readback);
 assert(status(verify,save)=="readback-uncertain");
 return 0;
}
