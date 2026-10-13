#include "PrefixStatusRuntime.h"

#if WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL
#include "PrefixStatusPolicy.h"
#include "Led.h"
#include "LedStripInterface.h"
#include "WordClockState.h"
#include <Arduino.h>
#include <atomic>
#include <time.h>
#ifdef ESP8266
#include <ESP8266WiFi.h>
#elif defined(ESP32)
#include <WiFi.h>
#endif

extern LedStripInterface *activeLedStrip;
extern Led led;

namespace prefixStatusRuntime {
namespace {
std::atomic<bool> timeSetObserved{false};
prefixStatus::OutputCache outputCache;
} // namespace

void noteTimeSet() { timeSetObserved.store(true, std::memory_order_relaxed); }
void resetDisplay() { outputCache.reset(); }
void service() {
    const uint32_t ms = millis();
    if (!outputCache.due(ms, activeLedStrip)) return;
    const prefixStatus::Inputs inputs = {
        WiFi.status() == WL_CONNECTED,
        time(nullptr) > 100000000, // Same validity threshold as the existing loop.
        externalRTC, // Startup detection, not continuous RTC health verification.
        timeSetObserved.load(std::memory_order_relaxed)
    };
    const float brightness = led.getColorbyPositionWithAppliedBrightness(Foreground).B;
    const prefixStatus::Color color = prefixStatus::scale(prefixStatus::choose(inputs, ms), brightness);
    if (!outputCache.changed(color)) return;
    if (activeLedStrip->setStatusPixel(RgbColor(color.r, color.g, color.b))) {
        activeLedStrip->show();
        outputCache.sent(color);
    }
}
} // namespace prefixStatusRuntime
#endif
