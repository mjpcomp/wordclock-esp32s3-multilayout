#pragma once
#include "BrightnessScheduleStorage.h"
#include "BrightnessScheduleRuntimeModel.h"
#if defined(ESP32)
#include <sys/time.h>
#include <time.h>
#endif

namespace brightnessScheduleRuntimeOwner {
namespace storage = brightnessScheduleStorage;
namespace model = brightnessScheduleRuntimeModel;
constexpr uint32_t kServiceIntervalMs = 50;
struct LocalTime { uint32_t dayMs; bool valid; };
using Clock = LocalTime (*)(void *);
class Owner {
    model::Model model_;
    storage::Store store_;
    storage::Record accepted_ = {};
    storage::Result last_ = storage::Result::Missing;
    model::Decision current_ = {0,0,true,false,false,false};
    bool observed_ = false, have_ = false, faultSeen_ = false, force_ = true, serviced_ = false;
    bool automatic_ = false, masterOn_ = true, timeValid_ = false;
    uint32_t lastMs_ = 0;
    static bool same(const storage::Record &a, const storage::Record &b) {
        if (a.revision != b.revision || a.schedule.defaultTenths != b.schedule.defaultTenths ||
            a.schedule.count != b.schedule.count) return false;
        for (uint8_t i=0;i<a.schedule.count;++i) {
            const brightnessSchedule::Event &x=a.schedule.events[i], &y=b.schedule.events[i];
            if (x.minute!=y.minute || x.targetTenths!=y.targetTenths || x.fadeMinutes!=y.fadeMinutes) return false;
        }
        return true;
    }
    static void observed(storage::Result result, const storage::Record *record, void *context) {
        Owner &self = *static_cast<Owner *>(context);
        self.last_ = result;
        using storage::Result;
        if (result == Result::Ok && record) {
            const bool changed = !self.have_ || self.faultSeen_ || !same(self.accepted_,*record);
            if (!record->revision || !brightnessSchedule::valid(record->schedule)) {
                self.model_.noteStorageIssue(); self.faultSeen_=true; self.observed_=true; self.force_=true; return;
            }
            if (changed) {
                self.model_.accept(record->schedule, record->revision);
                self.accepted_=*record; self.have_=true; self.faultSeen_=false; self.force_=true;
            }
            self.observed_=true;
        } else if (result == Result::Missing) {
            self.observed_=true;
            if (self.have_ || self.faultSeen_) { self.model_.noteStorageIssue(); self.faultSeen_=true; }
            else self.model_.begin(model::Startup::Missing);
            self.force_=true;
        } else if (result == Result::ResetRequired || result == Result::ReadFailed ||
                   result == Result::WriteUncertain || result == Result::ReadbackUncertain) {
            self.model_.noteStorageIssue(); self.faultSeen_=true; self.observed_=true; self.force_=true;
        }
    }
    bool due(uint32_t now, bool automatic, bool masterOn) const {
        return !serviced_ || force_ || automatic!=automatic_ || masterOn!=masterOn_ ||
               uint32_t(now-lastMs_)>=kServiceIntervalMs;
    }
    static bool equalDecision(const model::Decision &a, const model::Decision &b) {
        return a.gain==b.gain && a.revision==b.revision && a.scheduled==b.scheduled &&
               a.pausedAutomatic==b.pausedAutomatic && a.waitingForTime==b.waitingForTime &&
               a.storageFault==b.storageFault;
    }
public:
    explicit Owner(storage::Backend &backend) : store_(backend, observed, this) {}
    Owner(const Owner &) = delete;
    Owner &operator=(const Owner &) = delete;
    storage::Store &store() { return store_; }
    bool initialized() const { return observed_; }
    storage::Result lastResult() const { return last_; }
    const model::Decision &current() const { return current_; }
    storage::Result begin() {
        if (observed_) return last_;
        storage::Record record = {};
        return store_.load(record);
    }
    bool serviceLocal(uint32_t now, LocalTime clock, bool automatic, bool masterOn) {
        if (!due(now,automatic,masterOn) && clock.valid==timeValid_) return false;
        const model::Decision next = observed_ ? model_.sample(clock.dayMs,clock.valid,automatic,masterOn)
                                               : model::Decision{0,0,true,false,false,false};
        const bool changed = !equalDecision(next,current_);
        current_=next; lastMs_=now; serviced_=true; force_=false;
        automatic_=automatic; masterOn_=masterOn; timeValid_=clock.valid;
        return changed;
    }
    bool serviceFromClock(uint32_t now, Clock readClock, void *context, bool automatic, bool masterOn) {
        if (!due(now,automatic,masterOn)) return false;
        const LocalTime clock = readClock ? readClock(context) : LocalTime{0,false};
        return serviceLocal(now,clock,automatic,masterOn);
    }
};
#if defined(ESP32)
// Read-only conversion; application must apply its configured TZ before first output.
inline LocalTime localFromEpoch(time_t seconds, long micros) {
    if (seconds<=100000000 || micros<0 || micros>=1000000) return LocalTime{0,false};
    struct tm local = {};
    if (!localtime_r(&seconds,&local) || local.tm_hour<0 || local.tm_hour>23 ||
        local.tm_min<0 || local.tm_min>59 || local.tm_sec<0 || local.tm_sec>59) return LocalTime{0,false};
    const uint32_t dayMs=((uint32_t(local.tm_hour)*60+local.tm_min)*60+local.tm_sec)*1000+uint32_t(micros)/1000;
    return LocalTime{dayMs,true};
}
inline LocalTime systemLocalTime(void *) {
    struct timeval tv = {};
    if (gettimeofday(&tv,nullptr)!=0) return LocalTime{0,false};
    return localFromEpoch(static_cast<time_t>(tv.tv_sec),tv.tv_usec);
}
// External-linkage inline function: one function-local instance across translation units.
inline Owner &applicationRuntime() {
    static storage::NvsBackend backend;
    static Owner instance(backend);
    return instance;
}
#endif
} // namespace brightnessScheduleRuntimeOwner
