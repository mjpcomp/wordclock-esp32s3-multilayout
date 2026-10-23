#include "BrightnessScheduleOutputBuffer.h"
#include <cassert>
#include <initializer_list>
#include <vector>
#include <type_traits>
using namespace brightnessScheduleOutput;
static bool same(Pixel a,Pixel b){return a.r==b.r&&a.g==b.g&&a.b==b.b&&a.w==b.w;}
struct Sink {
 std::vector<Pixel> pixels;size_t logicalCount,prefix;bool rgbw;
 unsigned writes=0,shows=0;
 Sink(size_t n,size_t p,bool w):pixels(n+p),logicalCount(n),prefix(p),rgbw(w){
  if(prefix)pixels[0]=Pixel{7,8,9,0};
 }
 void writePixel(size_t i,Pixel p){assert(i<logicalCount);if(!rgbw)p.w=0;pixels[i+prefix]=p;++writes;}
 void show(){++shows;}
 Pixel at(size_t i){return pixels[i+prefix];}
};
int main(){
 static_assert(!std::is_copy_constructible<Buffer<1200>>::value,"no accidental cache copies");
 for(unsigned v=0;v<=255;++v){
  unsigned previous=0;
  for(unsigned g=0;g<=10000;++g){
   auto out=brightnessScheduleRuntimeModel::scale(v,g);
   assert(out==(v*g+5000)/10000&&out<=v&&out>=previous);previous=out;
  }
 }
 for(size_t count: {300u,600u,900u,1200u})for(size_t prefix: {0u,1u})for(bool rgbw: {false,true}){
  Buffer<1200> buffer;Sink sink(count,prefix,rgbw);
  assert(buffer.count()==0&&!buffer.pending()&&!buffer.flush(sink));
  assert(sink.writes==0&&sink.shows==0);
  assert(buffer.configure(count)&&buffer.gain()==0&&buffer.pending());
  assert(buffer.flush(sink)&&same(sink.at(0),Pixel{}));
  assert(!buffer.flush(sink)&&sink.shows==1);
  const Pixel original={201,103,51,127};
  assert(buffer.set(0,original)&&buffer.set(count-1,Pixel{255,254,1,255}));
  assert(!buffer.set(count,original));
  assert(buffer.setGain(10000)&&buffer.flush(sink));
  assert(same(sink.at(0),Pixel{201,103,51,static_cast<uint8_t>(rgbw?127:0)}));
  const unsigned shows=sink.shows;
  assert(buffer.set(0,original)&&!buffer.pending()&&!buffer.setGain(10000));
  assert(!buffer.flush(sink)&&sink.shows==shows);
  for(unsigned repeat=0;repeat<100;++repeat){
   assert(buffer.setGain(5000)&&buffer.flush(sink));
   assert(same(sink.at(0),Pixel{101,52,26,static_cast<uint8_t>(rgbw?64:0)}));
   assert(same(buffer.logical(0),original));
   assert(buffer.setGain(0)&&buffer.flush(sink)&&same(sink.at(0),Pixel{}));
   assert(buffer.setGain(10000)&&buffer.flush(sink));
   assert(sink.at(0).r==201&&same(buffer.logical(0),original));
  }
  assert(!buffer.setGain(65535)&&!buffer.pending());
  buffer.invalidateOutput();assert(buffer.pending()&&buffer.flush(sink));
  assert(buffer.clear(count-1)&&buffer.flush(sink)&&same(sink.at(count-1),Pixel{}));
  assert(!buffer.clear(count));
  buffer.clearAll();assert(buffer.flush(sink)&&same(sink.at(0),Pixel{}));
  buffer.clearAll();assert(!buffer.pending());
  if(prefix)assert(same(sink.pixels[0],Pixel{7,8,9,0}));
  const unsigned writes=sink.writes;
  assert(!buffer.configure(1201)&&buffer.count()==0&&buffer.gain()==0);
  assert(!buffer.flush(sink)&&sink.writes==writes);
  assert(buffer.configure(300)&&same(buffer.logical(0),Pixel{})&&buffer.gain()==0);
  assert(!buffer.configure(0)&&!buffer.pending());
 }
 return 0;
}
