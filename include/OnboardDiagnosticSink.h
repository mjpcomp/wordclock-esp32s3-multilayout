#pragma once
#include "ClockTestPolicy.h"

// Deliberately absent in normal firmware, even with the onboard flag enabled.
#if WORDCLOCK_TEST_MODE != 0
#if !defined(ESP32) || !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "Onboard diagnostic sink requires ESP32-S3"
#endif
#include <Arduino.h>
#include <esp32-hal-rgb-led.h>

namespace onboardDiagnostic {
static_assert(clockTestPolicy::ONBOARD_OUTPUT &&
              clockTestPolicy::ONBOARD_GPIO == 48 &&
              !clockTestPolicy::MATRIX_OUTPUT, "Isolated GPIO48 output required");
// Main-loop owner only. The core handles WS2812 timing using RMT;
// this is rate-limited, not a claim that the physical write is asynchronous.
class Gpio48Sink {
    bool polled = false, sent = false;
    uint32_t lastPoll = 0;
    uint8_t previousR = 0, previousG = 0, previousB = 0;
    static uint8_t bounded(uint8_t value) { return value > 20 ? 20 : value; }
public:
    // Returns true only when a physical write was requested, not acknowledged.
    bool service(uint32_t now, uint8_t red, uint8_t green, uint8_t blue) {
        if (polled && uint32_t(now - lastPoll) < 20) return false;
        polled = true;
        lastPoll = now;
        red = bounded(red); green = bounded(green); blue = bounded(blue);
        if (sent && red == previousR && green == previousG && blue == previousB)
            return false;
        // Raw GPIO is intentional: do not redefine the core RGB_BUILTIN alias.
        neopixelWrite(clockTestPolicy::ONBOARD_GPIO, red, green, blue);
        previousR = red; previousG = green; previousB = blue; sent = true;
        return true;
    }
};
} // namespace onboardDiagnostic
#endif
