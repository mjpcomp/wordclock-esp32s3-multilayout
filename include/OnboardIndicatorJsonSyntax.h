#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

// Restricted request grammar: ASCII strings without escapes, unsigned integers,
// booleans/null, objects/arrays. Full consumption, no comments/trailing commas.
namespace onboardIndicatorJsonSyntax {
constexpr size_t kMaxInput=1024;
class Reader {
 const uint8_t*data_;size_t size_,at_=0,keys_=0;
 void whitespace(){while(at_<size_&&(data_[at_]==' '||data_[at_]=='\t'||data_[at_]=='\r'||data_[at_]=='\n'))++at_;}
 bool take(uint8_t c){whitespace();if(at_==size_||data_[at_]!=c)return false;++at_;return true;}
 bool text(){
  if(!take('"'))return false;
  while(at_<size_){const uint8_t c=data_[at_++];if(c=='"')return true;if(c<0x20||c>=0x7f||c=='\\')return false;}
  return false;
 }
 bool number(){
  const size_t first=at_;while(at_<size_&&data_[at_]>='0'&&data_[at_]<='9')++at_;
  return at_>first&&!(data_[first]=='0'&&at_!=first+1);
 }
 bool literal(const char*word){const size_t n=strlen(word);if(size_-at_<n||memcmp(data_+at_,word,n))return false;at_+=n;return true;}
 bool value(unsigned depth){
  if(depth>4)return false;
  whitespace();if(at_==size_)return false;
  const uint8_t c=data_[at_];
  if(c=='{')return object(depth);
  if(c=='[')return array(depth);
  if(c=='"')return text();
  if(c>='0'&&c<='9')return number();
  if(c=='t')return literal("true");
  if(c=='f')return literal("false");
  if(c=='n')return literal("null");
  return false;
 }
 bool object(unsigned depth){
  if(!take('{'))return false;
  whitespace();if(at_<size_&&data_[at_]=='}'){++at_;return true;}
  for(;;){
   if(!text()||++keys_>13||!take(':')||!value(depth+1))return false;
   whitespace();if(at_<size_&&data_[at_]=='}'){++at_;return true;}
   if(!take(','))return false;
  }
 }
 bool array(unsigned depth){
  if(!take('['))return false;
  whitespace();if(at_<size_&&data_[at_]==']'){++at_;return true;}
  for(;;){
   if(!value(depth+1))return false;
   whitespace();if(at_<size_&&data_[at_]==']'){++at_;return true;}
   if(!take(','))return false;
  }
 }
public:
 Reader(const uint8_t*data,size_t size):data_(data),size_(size){}
 bool complete(size_t&keys){
  if(!data_||!size_||size_>kMaxInput||!object(1))return false;
  whitespace();if(at_!=size_)return false;keys=keys_;return true;
 }
};
}
