#include "OnboardIndicatorRuntimeOwner.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <vector>
#include <initializer_list>
namespace p=onboardIndicatorPolicy;namespace r=onboardIndicatorRecord;
namespace s=onboardIndicatorStorage;namespace o=onboardIndicatorRuntimeOwner;
const uint8_t golden[][24]={{87,67,79,83,1,1,0,0,1,0,0,0,0,0,0,0,0,0,0,0,191,41,184,12},
{87,67,79,83,1,2,1,0,7,0,0,0,176,4,164,1,0,0,0,0,172,143,163,242},
{87,67,79,83,1,2,2,0,42,0,0,0,164,1,208,2,192,3,176,4,238,111,37,226},
{87,67,79,83,1,0,2,0,9,0,0,0,164,1,208,2,192,3,176,4,119,215,12,37}};
struct Memory:s::Backend {
 enum class Write {Good,FalseBefore,FalseAfter,ReadbackFailed,Corrupt,Other};
 std::vector<uint8_t> bytes;bool present=false,readFailed=false,invalid=false;
 unsigned reads=0,writes=0;Write mode=Write::Good;
 s::ReadResult read(uint8_t*data,size_t capacity,size_t&size)override{
  ++reads;size=0;if(readFailed)return s::ReadResult::Failed;if(!present)return s::ReadResult::Missing;
  if(invalid||bytes.size()>capacity)return s::ReadResult::Invalid;
  size=bytes.size();if(size)memcpy(data,bytes.data(),size);return s::ReadResult::Ok;
 }
 bool write(const uint8_t*data,size_t size)override{
  ++writes;if(mode==Write::FalseBefore)return false;bytes.assign(data,data+size);present=true;
  if(mode==Write::FalseAfter)return false;
  if(mode==Write::ReadbackFailed)readFailed=true;
  if(mode==Write::Corrupt)bytes[0]^=1;
  if(mode==Write::Other){r::Record other={99,{p::Mode::Disabled,0,{{0,0},{0,0}}}};assert(r::encode(other,bytes.data(),bytes.size()));}
  return true;
 }
 void install(const r::Record&record){bytes.resize(24);assert(r::encode(record,bytes.data(),24));present=true;readFailed=invalid=false;mode=Write::Good;}
};
bool same(const r::Record&a,const r::Record&b){uint8_t x[24],y[24];assert(r::encode(a,x,24)&&r::encode(b,y,24));return !memcmp(x,y,24);}
bool reference(p::Window w,uint16_t m){return (m+1440u-w.startMinute)%1440u<(w.endMinute+1440u-w.startMinute)%1440u;}
int main(){
 unsigned membership=0,pairs=0,corruptions=0,logical=0;
 for(unsigned a=0;a<1440;++a)for(unsigned b=0;b<1440;++b){p::Window w={uint16_t(a),uint16_t(b)};for(unsigned m:{a,b,(a+1439)%1440,(b+1439)%1440}){assert(p::contains(w,uint16_t(m))==reference(w,uint16_t(m)));++membership;}}
 const unsigned edges[]={0,1,60,420,720,960,1200,1439};
 for(unsigned a:edges)for(unsigned b:edges)if(a!=b)for(unsigned c:edges)for(unsigned d:edges)if(c!=d){
  p::Policy policy={p::Mode::Scheduled,2,{{uint16_t(a),uint16_t(b)},{uint16_t(c),uint16_t(d)}}};bool overlap=false;
  for(unsigned m=0;m<1440;++m)if(reference(policy.windows[0],uint16_t(m))&&reference(policy.windows[1],uint16_t(m))){overlap=true;break;}
  assert(p::valid(policy)==!overlap);++pairs;
 }
 for(const auto&data:golden){r::Record rec={};assert(r::decode(data,24,rec));uint8_t encoded[24];assert(r::encode(rec,encoded,24)&&!memcmp(encoded,data,24));
  for(unsigned i=0;i<24;++i)for(unsigned v=0;v<256;++v)if(v!=data[i]){uint8_t bad[24];memcpy(bad,data,24);bad[i]=uint8_t(v);r::Record out=rec;assert(!r::decode(bad,24,out)&&same(out,rec));++corruptions;}
 }
 auto reject=[&](uint8_t*data){r::put32(data+20,r::crc32(data,20));r::Record out={};assert(!r::decode(data,24,out));++logical;};
 uint8_t bad[24];memcpy(bad,golden[2],24);bad[5]=255;reject(bad);
 memcpy(bad,golden[2],24);bad[6]=3;reject(bad);
 memcpy(bad,golden[2],24);bad[7]=1;reject(bad);
 memcpy(bad,golden[2],24);r::put32(bad+8,0);reject(bad);
 memcpy(bad,golden[2],24);r::put16(bad+12,1440);reject(bad);
 memcpy(bad,golden[2],24);r::put16(bad+14,420);reject(bad);
 memcpy(bad,golden[2],24);r::put16(bad+16,600);reject(bad);
 memcpy(bad,golden[0],24);bad[12]=1;reject(bad);
 memcpy(bad,golden[0],24);bad[5]=2;reject(bad);
 r::Record sentinel={};assert(r::decode(golden[0],24,sentinel));uint8_t buffer[24];memset(buffer,0xa5,24);
 assert(!r::decode(nullptr,24,sentinel)&&!r::decode(golden[0],23,sentinel)&&!r::decode(golden[0],25,sentinel));
 assert(!r::encode(sentinel,nullptr,24)&&!r::encode(sentinel,buffer,23));for(auto b:buffer)assert(b==0xa5);
 const p::Policy disabled={p::Mode::Disabled,0,{{0,0},{0,0}}};
 const p::Policy scheduled={p::Mode::Scheduled,2,{{420,720},{960,1200}}};
 Memory memory;o::Owner owner(memory);assert(!owner.permitted(true,true,420));assert(memory.reads==0&&memory.writes==0);
 owner.begin();assert(memory.reads==1&&memory.writes==0);owner.begin();assert(memory.reads==1);
 assert(owner.permitted(false,false,65535)&&!owner.observation().hasRecord&&!owner.observation().fault);
 for(unsigned i=0;i<10000;++i){(void)owner.observation();assert(owner.permitted(false,false,0));}assert(memory.reads==1&&memory.writes==0);
 r::Record saved={};assert(owner.store().save(0,scheduled,saved)==s::Result::Ok&&saved.revision==1);
 assert(!owner.permitted(true,false,420)&&!owner.permitted(false,true,420));
 assert(owner.permitted(true,true,420)&&!owner.permitted(true,true,720)&&owner.permitted(true,true,960)&&!owner.permitted(true,true,1200));
 const unsigned reads=memory.reads,writes=memory.writes;p::Policy invalid=scheduled;invalid.count=3;
 assert(owner.store().save(1,invalid,saved)==s::Result::InvalidInput&&memory.reads==reads&&memory.writes==writes);
 assert(owner.store().save(0,disabled,saved)==s::Result::Conflict&&memory.writes==writes&&owner.permitted(true,true,420));
 assert(owner.store().save(1,disabled,saved)==s::Result::Ok&&saved.revision==2&&!owner.permitted(true,true,420));
 assert(owner.store().reset(2,saved)==s::Result::Ok&&saved.revision==3&&owner.permitted(false,false,0));
 memory.present=false;assert(owner.store().load(saved)==s::Result::Missing&&owner.observation().fault&&!owner.permitted(true,true,420));
 for(auto mode:{Memory::Write::FalseBefore,Memory::Write::FalseAfter,Memory::Write::ReadbackFailed,Memory::Write::Corrupt,Memory::Write::Other}){
  Memory m;m.install(sentinel);o::Owner own(m);own.begin();m.mode=mode;r::Record out=sentinel;
  const s::Result result=own.store().save(1,disabled,out);
  assert(result==((mode==Memory::Write::FalseBefore||mode==Memory::Write::FalseAfter)?s::Result::WriteUncertain:s::Result::ReadbackUncertain));
  assert(same(out,sentinel)&&own.observation().fault&&!own.permitted(true,true,420));
  assert(m.writes==1);m.readFailed=false;m.mode=Memory::Write::Good;
  if(mode==Memory::Write::FalseBefore||mode==Memory::Write::FalseAfter){assert(own.store().load(out)==s::Result::Ok);assert(own.permitted(true,true,420)==(mode==Memory::Write::FalseBefore));}
 }
 for(bool ioFailure:{false,true}){Memory m;m.present=true;m.bytes={1,2,3};m.readFailed=ioFailure;o::Owner own(m);own.begin();assert(own.observation().fault&&!own.permitted(false,false,0)&&m.writes==0);r::Record out={};
  assert(own.store().save(0,disabled,out)==(ioFailure?s::Result::ReadFailed:s::Result::ResetRequired));
  assert(own.store().reset(0,out)==(ioFailure?s::Result::ReadFailed:s::Result::Ok));assert(m.writes==(ioFailure?0u:1u));
 }
 Memory exhausted;exhausted.install(r::Record{0xffffffffUL,p::freshPolicy()});s::Store store(exhausted);r::Record out={};assert(store.save(0xffffffffUL,disabled,out)==s::Result::RevisionExhausted&&exhausted.writes==0);
 std::cout<<membership<<" "<<pairs<<" "<<corruptions<<" "<<logical<<"\n";
}
