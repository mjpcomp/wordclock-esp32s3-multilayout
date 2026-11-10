#pragma once
#include <stdint.h>

// Pure permission rules for the onboard indicator, independent of strip gain.
// Minutes are local HH:MM in 0..1439. No clock reads, GPIO, allocation or IO.
namespace onboardIndicatorPolicy {
constexpr uint16_t kMinutesPerDay=1440;
enum class Mode:uint8_t {Disabled,AlwaysEnabled,Scheduled};
struct Window {uint16_t startMinute,endMinute;};
struct Policy {Mode mode;uint8_t count;Window windows[2];};
// Half-open [start,end); midnight crossing is supported, equal endpoints are not.
inline bool contains(const Window&w,uint16_t minute) {
 if(minute>=1440||w.startMinute>=1440||w.endMinute>=1440||w.startMinute==w.endMinute)return false;
 return w.startMinute<w.endMinute?minute>=w.startMinute&&minute<w.endMinute:minute>=w.startMinute||minute<w.endMinute;
}
// Adjacent windows are valid. Hidden retained windows must also remain valid.
inline bool valid(const Policy&p) {
 if(uint8_t(p.mode)>2||p.count>2||(p.mode==Mode::Scheduled&&!p.count))return false;
 for(uint8_t i=0;i<p.count;++i)if(p.windows[i].startMinute>=1440||p.windows[i].endMinute>=1440||p.windows[i].startMinute==p.windows[i].endMinute)return false;
 return p.count!=2||!(contains(p.windows[0],p.windows[1].startMinute)||contains(p.windows[1],p.windows[0].startMinute));
}
// This grants permission for current patterns; it never commands steady light.
// AlwaysEnabled does not depend on the clock; callers enforce hardware guards.
inline bool allows(const Policy&p,bool timeValid,uint16_t minute) {
 if(!valid(p)||p.mode==Mode::Disabled)return false;
 if(p.mode==Mode::AlwaysEnabled)return true;
 if(!timeValid||minute>=1440)return false;
 for(uint8_t i=0;i<p.count;++i)if(contains(p.windows[i],minute))return true;
 return false;
}
inline Policy freshPolicy(){return Policy{Mode::AlwaysEnabled,0,{{0,0},{0,0}}};}
}
