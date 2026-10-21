#include "BrightnessScheduleRuntimeModel.h"
#include <assert.h>
using namespace brightnessScheduleRuntimeModel;
static uint32_t at(unsigned h, unsigned m, unsigned s=0) { return ((h*60UL+m)*60UL+s)*1000UL; }
int main() {
    Model model;
    assert(model.begin(Startup::Missing));
    Decision d=model.sample(0,false,false,true);
    assert(d.gain==10000&&!d.scheduled&&!d.storageFault);
    assert(model.sample(0,false,true,false).gain==0);
    assert(!model.begin(Startup::Fault));
    d=model.sample(0,false,false,true);assert(d.gain==0&&d.scheduled&&d.storageFault);
    brightnessSchedule::Schedule s={};s.defaultTenths=400;s.count=3;
    s.events[0]={420,400,10};s.events[1]={1185,100,15};s.events[2]={1230,0,5};
    assert(model.accept(s,1));
    assert(model.sample(at(19,45),true,false,true).gain==4000);
    assert(model.sample(at(19,52,30),true,false,true).gain==2500);
    assert(model.sample(at(20,0),true,false,true).gain==1000);
    assert(model.sample(at(20,32,30),true,false,true).gain==500);
    assert(model.sample(at(0,0),true,false,true).gain==0);
    assert(model.sample(at(7,5),true,false,true).gain==2000);
    d=model.sample(at(12,0),false,false,true);assert(d.gain==0&&d.waitingForTime);
    d=model.sample(at(20,40),true,true,true);assert(d.gain==10000&&!d.scheduled&&d.pausedAutomatic);
    assert(model.sample(at(12,0),true,false,false).gain==0);
    model.noteStorageIssue();d=model.sample(at(12,0),true,false,true);
    assert(d.gain==4000&&d.storageFault&&d.revision==1);
    brightnessSchedule::Schedule bad=s;bad.defaultTenths=1001;
    assert(!model.accept(bad,2)&&!model.accept(s,0));
    assert(model.sample(at(12,0),true,false,true).gain==4000);
    Model reboot;assert(reboot.begin(Startup::Ready,&s,1));
    assert(reboot.sample(at(19,52,30),true,false,true).gain==2500);
    assert(model.accept(s,2)&&!model.sample(0,false,false,true).storageFault);
    brightnessSchedule::Schedule flat={};flat.defaultTenths=5;
    assert(model.accept(flat,3));d=model.sample(0,false,false,true);
    assert(d.gain==50&&!d.waitingForTime);
    Frame<4> frame;assert(!frame.set(0,Pixel{1,2,3,4}));
    assert(frame.configure(4));assert(frame.set(0,Pixel{255,128,64,32}));
    Pixel raw=frame.logical(0),half=frame.output(0,5000);
    assert(half.r==128&&half.g==64&&half.b==32&&half.w==16);
    for(unsigned i=0;i<1000;++i) {
        Pixel p=frame.output(0,5000);assert(p.r==128&&p.w==16);
        assert(frame.logical(0).r==255&&frame.logical(0).w==32);
    }
    Pixel off=frame.output(0,0),restored=frame.output(0,10000);
    assert(off.r==0&&off.g==0&&off.b==0&&off.w==0);
    assert(restored.r==raw.r&&restored.g==raw.g&&restored.b==raw.b&&restored.w==raw.w);
    assert(frame.output(0,65535).r==255);
    assert(!frame.set(4,Pixel{1,2,3,4})&&frame.logical(4).r==0);
    assert(frame.clear(0)&&frame.logical(0).w==0);
    assert(frame.set(1,Pixel{1,2,3,4})&&frame.configure(2)&&frame.logical(1).r==0);
    assert(!frame.configure(5)&&frame.count()==0&&frame.output(0,10000).r==0);
    assert(!frame.configure(0));
    for(unsigned gain=0;gain<=10000;++gain) {
        assert(scale(255,gain)<=255);
        if(gain)assert(scale(255,gain)>=scale(255,gain-1));
    }
    return 0;
}
