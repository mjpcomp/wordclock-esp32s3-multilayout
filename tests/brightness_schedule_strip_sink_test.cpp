#include "BrightnessScheduleStripSink.h"
#include "NeoPixelBusLedStripAdapter.h"
#include "VirtualLedStripAdapter.h"
#include "LedStatusPrefix.h"
#include <cassert>
#include <initializer_list>
#include <type_traits>
using namespace brightnessScheduleOutput;
unsigned hsbConversions=0;
static uint8_t white(RgbColor){return 0;}
static uint8_t white(RgbwColor p){return p.W;}
template<bool White> void physicalTest(uint16_t count){
 using Adapter=typename std::conditional<White,RgbwLedStripAdapter<MockMethod>,RgbLedStripAdapter<MockMethod>>::type;
 using Feature=typename std::conditional<White,NeoGrbwFeature,NeoMultiFeature>::type;
 Adapter backend(count,8);
 auto *bus=NeoPixelBus<Feature,MockMethod>::last;
 assert(bus&&bus->begins==1&&bus->shows==0);
 assert(!backend.isVirtual()&&!backend.diagnostics().countersAvailable);
 assert(backend.setStatusPixel(RgbColor(7,8,9))==(ledPrefix::COUNT!=0));
 Buffer<1200> buffer;StripSink sink(backend);
 assert(bus->shows==0);
 assert(buffer.configure(count));buffer.setGain(10000);
 for(unsigned v=0;v<256;++v){
  Pixel p={static_cast<uint8_t>(v),static_cast<uint8_t>(255-v),static_cast<uint8_t>(v^85),static_cast<uint8_t>(v)};
  assert(buffer.set(0,p)&&buffer.set(count-1,p));buffer.flush(sink);
  auto q=bus->pixels[ledPrefix::COUNT];
  assert(q.R==p.r&&q.G==p.g&&q.B==p.b&&white(q)==(White?p.w:0));
  assert(bus->pixels[count-1+ledPrefix::COUNT].R==p.r);
 }
 buffer.set(0,Pixel{201,103,51,127});buffer.setGain(5000);assert(buffer.flush(sink));
 auto half=bus->pixels[ledPrefix::COUNT];assert(half.R==101&&half.G==52&&half.B==26&&white(half)==(White?64:0));
 assert(buffer.logical(0).r==201&&buffer.logical(0).w==127);
 unsigned shows=bus->shows;assert(!buffer.flush(sink)&&bus->shows==shows);
 buffer.setGain(0);buffer.flush(sink);assert(bus->pixels[ledPrefix::COUNT].R==0);
 buffer.setGain(10000);buffer.flush(sink);assert(bus->pixels[ledPrefix::COUNT].R==201);
 if(ledPrefix::COUNT){auto status=bus->pixels[0];assert(status.R==7&&status.G==8&&status.B==9&&white(status)==0);}
 unsigned writes=bus->writes;sink.writePixel(65536,Pixel{1,2,3,4});assert(bus->writes==writes);
 buffer.clearAll();buffer.flush(sink);assert(bus->pixels[ledPrefix::COUNT].R==0);
}
static void virtualTest(uint16_t count,bool rgbw){
 VirtualLedStripAdapter backend(count,rgbw);LedStripInterface *identity=&backend;
 Buffer<1200> buffer;StripSink sink(backend);
 assert(identity==&backend&&identity->isVirtual());
 assert(backend.diagnostics().showRequests==0);
 assert(buffer.configure(count));buffer.set(0,Pixel{201,103,51,127});buffer.setGain(10000);
 assert(buffer.flush(sink));auto full=backend.getRgbwPixel(0);
 assert(full.R==201&&full.G==103&&full.B==51&&full.W==(rgbw?127:0));
 assert(backend.diagnostics().showRequests==1&&backend.diagnostics().changedFrames==1);
 assert(!buffer.flush(sink)&&backend.diagnostics().showRequests==1);
 buffer.setGain(5000);buffer.flush(sink);
 assert(backend.getRgbwPixel(0).R==101&&backend.getRgbwPixel(0).W==(rgbw?64:0));
 assert(buffer.logical(0).r==201&&buffer.logical(0).w==127);
 assert(backend.getPixel(0).R==101); // Backend still reads submitted output; live readback binding is separate.
 assert(!backend.setStatusPixel(RgbColor(7,8,9)));
 buffer.setGain(10000);buffer.flush(sink);assert(backend.getRgbwPixel(0).R==201);
 unsigned shows=backend.diagnostics().showRequests;sink.writePixel(65536,Pixel{1,2,3,4});assert(backend.diagnostics().showRequests==shows);
 buffer.clearAll();buffer.flush(sink);assert(backend.getRgbwPixel(0).R==0);
}
int main(){
 for(uint16_t count:{300,600,900,1200}){
  physicalTest<false>(count);physicalTest<true>(count);
  virtualTest(count,false);virtualTest(count,true);
 }
 assert(hsbConversions==0);
 return 0;
}
