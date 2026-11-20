#include "ClockTestPolicy.h"
#include "OnboardIndicatorLifecycle.h"

#if WORDCLOCK_TEST_MODE != 0 && defined(ESP32) && defined(CONFIG_IDF_TARGET_ESP32S3)
#include "OnboardIndicatorCommandService.h"
#include "OnboardIndicatorNvsBackend.h"
#include "WordClockState.h"
#include <string.h>
#include <sys/time.h>
#include <time.h>

namespace onboardIndicatorLifecycle {
namespace {
bool timezoneApplied_ = false;
char appliedTimezone[sizeof(G.timezone)] = {};
onboardIndicatorCommandService::Service& service() {
    static onboardIndicatorStorage::NvsBackend backend;
    static onboardIndicatorCommandService::Service instance(backend);
    return instance;
}
bool configuredTimezoneValid() {
    return G.timezone[0] && memchr(G.timezone, '\0', sizeof(G.timezone));
}
}
bool supported() { return true; }
void preparePolicy() { (void)service().prepare(); }
bool prepared() { return service().snapshot().owner.initialized; }
void invalidateTimezone() { timezoneApplied_ = false; }
void timezoneApplied(bool success) {
    timezoneApplied_ = false;
    if (!success || !configuredTimezoneValid()) return;
    memcpy(appliedTimezone, G.timezone, sizeof(appliedTimezone));
    timezoneApplied_ = true;
}
bool timezoneReady() {
    return timezoneApplied_ && configuredTimezoneValid() &&
           strncmp(appliedTimezone, G.timezone, sizeof(appliedTimezone)) == 0;
}
bool permitted() {
    if (!prepared()) return false;
    struct timeval tv = {};
    struct tm local = {};
    const bool valid = gettimeofday(&tv, nullptr) == 0 && tv.tv_sec > 100000000 &&
        localtime_r(&tv.tv_sec, &local) && local.tm_hour >= 0 && local.tm_hour < 24 &&
        local.tm_min >= 0 && local.tm_min < 60;
    const uint16_t minute = valid ? uint16_t(local.tm_hour * 60 + local.tm_min) : 0;
    return service().permitted(valid, timezoneReady(), minute);
}
onboardIndicatorCommandService::Service* commandService() { return &service(); }
}
#else
namespace onboardIndicatorLifecycle {
bool supported() { return false; }
void preparePolicy() {}
bool prepared() { return false; }
void invalidateTimezone() {}
void timezoneApplied(bool) {}
bool timezoneReady() { return false; }
bool permitted() { return false; }
onboardIndicatorCommandService::Service* commandService() { return nullptr; }
}
#endif
