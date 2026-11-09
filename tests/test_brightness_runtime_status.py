from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
CPP = r'''#include "BrightnessRuntimeStatusProtocol.h"
#include "BrightnessScheduleTransport.h"
#include <cassert>
#include <vector>
#include <string>
namespace rt=brightnessScheduleRuntimeOwner;
namespace st=brightnessScheduleStorage;
namespace status=brightnessRuntimeStatusProtocol;
class Memory:public st::Backend {
public:
 std::vector<uint8_t> data; unsigned reads=0,writes=0; bool fail=false;
 st::ReadResult read(uint8_t *p,size_t cap,size_t &n)override {
  ++reads;
  if(fail)return st::ReadResult::Failed;
  if(data.empty())return st::ReadResult::Missing;
  if(data.size()>cap)return st::ReadResult::Invalid;
  n=data.size(); memcpy(p,data.data(),n); return st::ReadResult::Ok;
 }
 bool write(const uint8_t *p,size_t n)override {++writes;data.assign(p,p+n);return true;}
};
struct Context {
 rt::Owner &owner; unsigned calls; uint32_t now;
 Context(rt::Owner &value,unsigned count,uint32_t stamp):owner(value),calls(count),now(stamp){}
};
static status::State read(void *p) {
 auto &ctx=*static_cast<Context *>(p); ++ctx.calls; status::State value={};
 value.observation=ctx.owner.observation(ctx.now); value.backend=status::BackendKind::Virtual; return value;
}
static bool bridge(const uint8_t *p,size_t n,char *out,size_t cap,size_t &used,void *ctx) {
 auto &context=*static_cast<Context *>(ctx);
 const auto result=status::handle(p,n,out,cap,used,read,ctx);
 if(result!=status::Result::NotRuntime)return result==status::Result::Handled;
 return brightnessScheduleProtocol::handle(context.owner.store(),p,n,out,cap,used);
}
static bool sendReply(uint8_t,const char *,size_t,void *) { return true; }
static std::string query(rt::Owner &owner, const std::string &request, unsigned &calls) {
 char output[status::kMinOutput]; size_t used=0; Context context{owner,0,101};
 auto result=status::handle(reinterpret_cast<const uint8_t *>(request.data()),request.size(),output,sizeof(output),used,read,&context);
 calls=context.calls; assert(result==status::Result::Handled); assert(used>0&&used<sizeof(output)&&output[used]==0); return {output,used};
}
int main() {
 const std::string get=R"({"command":"brightness-runtime","schema":1,"requestId":"rt_g1_r1","action":"get"})";
 Memory memory; rt::Owner owner(memory); unsigned calls=0;
 auto cold=owner.observation(0); assert(!cold.hasSample&&!cold.initialized);
 owner.serviceLocal(1,{0,true},false,true); assert(!owner.observation(1).hasSample);
 assert(owner.begin()==st::Result::Missing); assert(!owner.observation(2).hasSample);
 const unsigned reads=memory.reads,writes=memory.writes;
 DynamicJsonDocument doc(4096); assert(!deserializeJson(doc,query(owner,get,calls))); assert(calls==1&&doc["sample"].isNull());
 owner.serviceLocal(3,{0,true},false,true); assert(owner.observation(3).hasSample);
 assert(!deserializeJson(doc,query(owner,get,calls))); assert(doc["sample"]["gain"]==10000&&!doc["sample"]["scheduled"].as<bool>());
 for(unsigned i=0;i<100;++i) (void)owner.observation(i);
 assert(memory.reads==reads&&memory.writes==writes);
 brightnessSchedule::Schedule flat={}; flat.defaultTenths=400; st::Record record={};
 assert(owner.store().save(0,flat,record)==st::Result::Ok);
 auto pending=owner.observation(4); assert(pending.acceptedRevision==1&&pending.decision.revision==0&&pending.pendingEvaluation);
 owner.serviceLocal(4,{0,false},false,true); auto sampled=owner.observation(5);
 assert(sampled.decision.gain==4000&&!sampled.decision.waitingForTime&&!sampled.pendingEvaluation);
 owner.serviceLocal(5,{0,true},true,true); assert(owner.observation(5).decision.pausedAutomatic&&owner.current().gain==10000);
 owner.serviceLocal(6,{0,true},false,false); assert(owner.current().gain==0);
 owner.serviceLocal(7,{0,true},false,true); memory.fail=true;
 assert(owner.store().load(record)==st::Result::ReadFailed);
 auto fault=owner.observation(8); assert(fault.observedStorageFault&&!fault.decision.storageFault&&fault.pendingEvaluation);
 owner.serviceLocal(8,{0,true},false,true); assert(owner.current().storageFault&&owner.current().gain==4000);
 memory.fail=false; assert(owner.store().reset(1,record)==st::Result::Ok); assert(owner.observation(9).acceptedRevision==2&&owner.current().revision==1);
 owner.serviceLocal(0xfffffff0UL,{0,true},false,true); assert(owner.observation(5).sampleAgeMs==21);
 Memory coldMemory; coldMemory.fail=true; rt::Owner coldFault(coldMemory);
 assert(coldFault.begin()==st::Result::ReadFailed&&!coldFault.observation(0).hasSample);
 coldFault.serviceLocal(0,{0,true},false,true); assert(coldFault.current().gain==0&&coldFault.current().storageFault);
 Memory timedMemory; rt::Owner timed(timedMemory); timed.begin();
 brightnessSchedule::Schedule events={}; events.defaultTenths=400; events.count=1; events.events[0]={60,200,0};
 assert(timed.store().save(0,events,record)==st::Result::Ok);
 timed.serviceLocal(0,{0,false},false,true); assert(timed.current().waitingForTime);
 timed.serviceLocal(1,{3600000,true},false,true); assert(!timed.current().waitingForTime&&timed.current().gain==2000);
 const unsigned beforeReads=memory.reads,beforeWrites=memory.writes;
 std::vector<std::string> invalid={
  R"({"command":"brightness-runtime","schema":true,"requestId":"x","action":"get"})",
  R"({"command":"brightness-runtime","schema":2,"requestId":"x","action":"get"})",
  R"({"command":"brightness-runtime","schema":1,"requestId":"x","action":"save"})",
  R"({"command":"brightness-runtime","schema":1,"requestId":"x","action":"get","extra":0})",
  R"({"command":"brightness-runtime","schema":1,"requestId":"bad!","action":"get"})",
  R"({"command":"brightness-runtime","schema":1,"requestId":"x\u0000y","action":"get"})",
  R"({"command":"brightness-runtime","schema":1,"requestId":"x","action":"get","action":"get"})"
 };
 for(const auto &text:invalid){assert(!deserializeJson(doc,query(owner,text,calls)));assert(calls==0&&doc["status"]=="invalid-request");}
 char output[status::kMinOutput]; size_t used=100; Context context{owner,0,100};
 for(const auto &text:std::vector<std::string>{get+"x",get+"{}",std::string(2049,' '),"[]","{broken}",R"({"command":"brightness-schedule","schema":1,"requestId":"c","action":"get"})"})
  assert(status::handle(reinterpret_cast<const uint8_t *>(text.data()),text.size(),output,sizeof(output),used,read,&context)==status::Result::NotRuntime);
 assert(status::handle(reinterpret_cast<const uint8_t *>(get.data()),get.size(),output,1,used,read,&context)==status::Result::Unavailable&&!used&&!context.calls);
 assert(memory.reads==beforeReads&&memory.writes==beforeWrites);
 namespace transport=brightnessScheduleTransport;
 Context framed{owner,0,100}; char buffer[transport::kReplyBytes];
 const unsigned framedReads=memory.reads,framedWrites=memory.writes;
 assert(transport::dispatch(transport::Frame::Fragment,7,nullptr,0,buffer,sizeof(buffer),bridge,sendReply,&framed)==transport::Result::Handled);
 std::vector<uint8_t> huge(transport::kMaxTextBytes+1,'x');
 assert(transport::dispatch(transport::Frame::Text,7,huge.data(),huge.size(),buffer,sizeof(buffer),bridge,sendReply,&framed)==transport::Result::Handled);
 const uint8_t legacy[]={'2','0','1'};
 assert(transport::dispatch(transport::Frame::Text,7,legacy,3,buffer,sizeof(buffer),bridge,sendReply,&framed)==transport::Result::PassThrough);
 assert(!framed.calls&&memory.reads==framedReads&&memory.writes==framedWrites);
 assert(transport::dispatch(transport::Frame::Text,7,reinterpret_cast<const uint8_t *>(get.data()),get.size(),buffer,sizeof(buffer),bridge,sendReply,&framed)==transport::Result::Handled);
 assert(framed.calls==1&&memory.reads==framedReads&&memory.writes==framedWrites);
 static_assert(MAX_INPUT==255,"SDK macro unchanged");
 return 0;
}
'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json-include', type=Path, default=ROOT / '.ci-deps/ArduinoJson/src')
    args = parser.parse_args()
    compiler = shutil.which('g++')
    if not compiler or not (args.json_include / 'ArduinoJson.h').is_file():
        raise SystemExit('g++ and the existing pinned actual ArduinoJson headers are required')
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        source = work / 'test.cpp'
        source.write_text(CPP)
        binary = work / 'test'
        subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                        '-DMAX_INPUT=255',
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        '-I', str(args.json_include), '-I', str(ROOT / 'include'), str(source), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('PASS: actual runtime observation and ArduinoJson status protocol')
if __name__ == '__main__':
    main()
