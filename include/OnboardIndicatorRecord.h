#pragma once
#include "OnboardIndicatorPolicy.h"
#include <stddef.h>
#include <string.h>

// Versioned little-endian record, never raw struct storage or an export token.
// CRC detects accidental corruption; it provides no authentication/encryption.
namespace onboardIndicatorRecord {
constexpr size_t kBytes=24;
struct Record {uint32_t revision;onboardIndicatorPolicy::Policy policy;};
inline uint16_t get16(const uint8_t*p){return uint16_t(p[0])|(uint16_t(p[1])<<8);}
inline uint32_t get32(const uint8_t*p){uint32_t v=0;for(uint8_t i=0;i<4;++i)v|=uint32_t(p[i])<<(8*i);return v;}
inline void put16(uint8_t*p,uint16_t v){p[0]=uint8_t(v);p[1]=uint8_t(v>>8);}
inline void put32(uint8_t*p,uint32_t v){for(uint8_t i=0;i<4;++i)p[i]=uint8_t(v>>(8*i));}
inline uint32_t crc32(const uint8_t*p,size_t n){uint32_t c=0xffffffffUL;for(size_t i=0;i<n;++i){c^=p[i];for(uint8_t b=0;b<8;++b)c=(c>>1)^((c&1)?0xedb88320UL:0);}return c^0xffffffffUL;}
// Failed validation/capacity checks leave the destination bytes unchanged.
inline bool encode(const Record&r,uint8_t*out,size_t capacity){
 if(!out||capacity<kBytes||!r.revision||!onboardIndicatorPolicy::valid(r.policy))return false;
 uint8_t data[kBytes]={0};memcpy(data,"WCOS",4);data[4]=1;
 data[5]=uint8_t(r.policy.mode);data[6]=r.policy.count;put32(data+8,r.revision);
 for(uint8_t i=0;i<r.policy.count;++i){put16(data+12+4*i,r.policy.windows[i].startMinute);put16(data+14+4*i,r.policy.windows[i].endMinute);}
 put32(data+20,crc32(data,20));memcpy(out,data,kBytes);return true;
}
// Only a complete canonical record replaces the caller's last accepted value.
inline bool decode(const uint8_t*data,size_t size,Record&out){
 if(!data||size!=kBytes||memcmp(data,"WCOS",4)||data[4]!=1||data[5]>2||data[6]>2||data[7]||get32(data+20)!=crc32(data,20))return false;
 Record candidate={};candidate.revision=get32(data+8);
 candidate.policy.mode=static_cast<onboardIndicatorPolicy::Mode>(data[5]);candidate.policy.count=data[6];
 for(uint8_t i=0;i<2;++i){const uint16_t start=get16(data+12+4*i),end=get16(data+14+4*i);if(i>=candidate.policy.count&&(start||end))return false;candidate.policy.windows[i]={start,end};}
 if(!candidate.revision||!onboardIndicatorPolicy::valid(candidate.policy))return false;
 out=candidate;return true;
}
}
