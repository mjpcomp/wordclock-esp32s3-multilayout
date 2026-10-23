// Extracted-method integration harness; mock colors/backends, real EN10x11 mapping.
#include <algorithm>
#include <cassert>
#include <cstring>
#include <vector>
#include <initializer_list>
#include "BrightnessScheduleRendererCache.h"
using std::min;
using brightnessScheduleRenderer::PixelMode;
uint32_t frontMatrix[22]={};
enum class BuildTypeDef{Normal,DoubleResM1};
enum class MinuteVariant{Off,LED4x,LED7x,Corners,InWords};
enum{FlipHorzVert,MeanderRows,ExtraLedPerRow};
enum ColorPosition{Foreground,Frame};
enum WhiteType{Warm,Neutral,Cool};
enum{Rgb,Grbw};
struct{void printf(const char*,...){};}Serial;
struct{BuildTypeDef buildTypeDef=BuildTypeDef::Normal;bool layoutVariant[6]={};int Colortype=Rgb;WhiteType wType=Warm;}G;
unsigned letters=1;
uint8_t getLedsPerLetter(BuildTypeDef){return letters;}
#include "EN10x11.hpp"
// Only frame geometry is a fixture override; front mapping is the real base method.
class Face:public En10x11_t{public:uint8_t numPixelsFrameMatrix()override{return 8;}uint16_t getFrameMatrixIndex(uint16_t i)override{return 260+i;}};
ClockType *usedClockType=nullptr;
uint16_t minutePixelArray[4]={240,241,242,243};uint8_t minuteArray=5;bool frameArray[8]={};
class LedStripInterface{public:virtual~LedStripInterface()=default;virtual void setRgbPixel(uint16_t,HsbColor)=0;virtual void setRgbwPixel(uint16_t,RgbwColor)=0;virtual RgbColor getPixel(uint16_t)=0;virtual void clearPixel(uint16_t)=0;virtual void show()=0;};
class Raw:public LedStripInterface{
public:std::vector<RgbwColor> pixels;PixelMode mode;unsigned shows=0;
 Raw(size_t n,PixelMode m):pixels(n),mode(m){}
 void setRgbPixel(uint16_t i,HsbColor c)override{RgbColor p(c);setRgbwPixel(i,RgbwColor(p.R,p.G,p.B,0));}
 void setRgbwPixel(uint16_t i,RgbwColor p)override{assert(i<pixels.size());if(mode==PixelMode::Rgb)p.W=0;pixels[i]=p;}
 RgbColor getPixel(uint16_t i)override{const auto p=pixels.at(i);return mode==PixelMode::PhysicalRgbw?RgbColor(p):RgbColor(p.R,p.G,p.B);}
 void clearPixel(uint16_t i)override{setRgbwPixel(i,RgbwColor(0));}
 void show()override{++shows;}
};
class Probe:public LedStripInterface{
 struct Sink{Raw &raw;void writePixel(size_t i,brightnessScheduleOutput::Pixel p){raw.setRgbwPixel(i,RgbwColor(p.r,p.g,p.b,p.w));}void show(){raw.show();}};
public:brightnessScheduleRenderer::Cache<1200> cache;Sink sink;
 Probe(Raw &raw):sink{raw}{assert(cache.configure(raw.pixels.size(),raw.mode));cache.setGain(10000);}
 void setRgbPixel(uint16_t i,HsbColor c)override{RgbColor p(c);setRgbwPixel(i,RgbwColor(p.R,p.G,p.B,0));}
 void setRgbwPixel(uint16_t i,RgbwColor p)override{assert(cache.capture(i,p));}
 RgbColor getPixel(uint16_t i)override{return cache.read(i);}
 void clearPixel(uint16_t i)override{assert(cache.clear(i));}
 void show()override{cache.show(sink);}
 void gain(uint16_t value){cache.setGain(value);cache.flush(sink);}
};
LedStripInterface *activeLedStrip=nullptr;
class Led{public:
 void setPixel(uint16_t,HsbColor);void setPixel(uint8_t,uint8_t,HsbColor);
 RgbColor getPixel(uint16_t);void clearPixel(uint16_t);void clearPixel(uint8_t,uint8_t);void show();
 void setbyMinuteArray(ColorPosition);void setbySecondArray(ColorPosition);
 HsbColor getColorbyPositionWithAppliedBrightness(ColorPosition p){return p==Frame?HsbColor(.3f,.4f,.5f):HsbColor(.8f,.6f,.2f);}
}led;
struct RgbfColor:RgbColor{bool fg=false,overlay=false;RgbfColor(uint8_t n=0):RgbColor(n){}RgbfColor(RgbColor p):RgbColor(p){}bool operator==(const RgbfColor &p)const{return R==p.R&&G==p.G&&B==p.B;}void setForeground(bool v){fg=v;}void setOverlay(bool v){overlay=v;}};
#define STRIPE NULL
class Transition{public:uint8_t maxRows=10,maxCols=11;void analyzeColors(RgbfColor**,RgbfColor**,RgbfColor&,RgbfColor&);};
#include "extracted.inc"
static bool same(RgbwColor a,RgbwColor b){return a.R==b.R&&a.G==b.G&&a.B==b.B&&a.W==b.W;}
static void draw(){
 led.setPixel(uint8_t(1),uint8_t(1),HsbColor(.85f,.6f,.25f));
 led.setPixel(uint8_t(4),uint8_t(7),HsbColor(.85f,.6f,.25f));
 led.setbyMinuteArray(Foreground);led.setbySecondArray(Frame);
}
static void check(size_t count,PixelMode mode,unsigned multiplicity,bool meander){
 Face face;usedClockType=&face;letters=multiplicity;G.layoutVariant[MeanderRows]=meander;G.Colortype=mode==PixelMode::Rgb?Rgb:Grbw;
 std::fill(frameArray,frameArray+8,false);frameArray[0]=true;frameArray[7]=true;
 Raw baseline(count,mode),output(count,mode);Probe probe(output);
 activeLedStrip=&baseline;draw();
 activeLedStrip=&probe;draw();assert(output.shows==0);
 // Independent normal/meander oracle for the two real matrix coordinates.
 unsigned first=(meander?11+9:11+1)*letters,second=(4*11+7)*letters;
 assert(probe.cache.logical(first).r!=0&&probe.cache.logical(second).r!=0);
 for(unsigned j=0;j<letters;++j)assert(probe.cache.logical(first+j).r==probe.cache.logical(first).r);
 assert(probe.cache.logical(240).r!=0&&probe.cache.logical(242).r!=0);
 for(size_t i:{260,261}){const auto p=probe.cache.logical(i);assert(p.r||p.g||p.b||p.w);}
 // Actual transition method snapshots the newly staged frame BEFORE show.
 RgbfColor values[10][11],*rows[10];for(unsigned r=0;r<10;++r)rows[r]=values[r];
 Transition transition;RgbfColor fg,bg;transition.analyzeColors(rows,STRIPE,fg,bg);
 RgbColor expected=baseline.getPixel(first);
 assert(values[1][1].R==expected.R&&values[1][1].G==expected.G&&values[1][1].B==expected.B);
 led.show();assert(output.shows==1);
 for(size_t i=0;i<count;++i)assert(same(output.pixels[i],baseline.pixels[i]));
 for(uint16_t gain:{5000,0,10000}){
  probe.gain(gain);transition.analyzeColors(rows,STRIPE,fg,bg);
  assert(values[1][1].R==expected.R&&values[1][1].G==expected.G&&values[1][1].B==expected.B);
  assert(probe.cache.logical(first).r==baseline.pixels[first].R);
  auto original=baseline.pixels[first];auto submitted=output.pixels[first];
  assert(submitted.R==(uint32_t(original.R)*gain+5000)/10000);
  assert(submitted.W==(uint32_t(original.W)*gain+5000)/10000);
 }
 unsigned shows=output.shows;led.show();assert(output.shows==shows+1);
 led.clearPixel(uint8_t(1),uint8_t(1));
 for(unsigned j=0;j<letters;++j)assert(led.getPixel(first+j).R==0);
 led.show();probe.gain(0);probe.gain(10000);
 for(unsigned j=0;j<letters;++j)assert(same(output.pixels[first+j],RgbwColor(0)));
 activeLedStrip=nullptr;usedClockType=nullptr;
}
int main(){for(size_t n:{300,600,900,1200})for(auto mode:{PixelMode::Rgb,PixelMode::VirtualRgbw,PixelMode::PhysicalRgbw})for(unsigned copies:{1u,2u})for(bool meander:{false,true})check(n,mode,copies,meander);}
