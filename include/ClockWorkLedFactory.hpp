#pragma once

#include "ClockTestPolicy.h"
#if WORDCLOCK_TEST_MODE != 0
#include "VirtualLedStripAdapter.h"
#endif

// Included at the original factory definition, after its runtime globals.
void ClockWork::initLedStrip(uint8_t num) {
    NeoMultiFeature::setColortype(num);
    const uint16_t ledCount = MAX_LED_COUNT * getLedsPerLetter(G.buildTypeDef);

    const uint8_t outputPin = clockTestPolicy::MATRIX_OUTPUT
                                  ? G.hardwarePins.led : UINT8_MAX;
    if (activeLedPin != outputPin || activeLedColorType != num ||
        activeLedCount != ledCount) {
        deleteActiveLedStrip();
        activeLedPin = outputPin;
        activeLedColorType = num;
        activeLedCount = ledCount;
    }

    if (activeLedStrip != nullptr) {
        return;
    }

#if WORDCLOCK_TEST_MODE != 0
    activeLedStrip = new VirtualLedStripAdapter(ledCount, num == Grbw);
#else
#ifdef ESP8266
    if (num == Grbw) {
        if (G.hardwarePins.led == LED_PIN) {
            activeLedStrip =
                new RgbwLedStripAdapter<Neo800KbpsMethod>(ledCount);
        } else {
            activeLedStrip =
                new RgbwLedStripAdapter<NeoEsp8266BitBangWs2812xMethod>(
                    ledCount, G.hardwarePins.led);
        }
    } else if (G.hardwarePins.led == LED_PIN) {
        activeLedStrip = new RgbLedStripAdapter<Neo800KbpsMethod>(ledCount);
    } else {
        activeLedStrip = new RgbLedStripAdapter<NeoEsp8266BitBangWs2812xMethod>(
            ledCount, G.hardwarePins.led);
    }
#else
#if defined(ESP32)
    pinMode(G.hardwarePins.led, OUTPUT);
#endif
    if (num == Grbw) {
        activeLedStrip = new RgbwLedStripAdapter<NeoEsp32Rmt0Ws2812xMethod>(
            ledCount, G.hardwarePins.led);
    } else {
        activeLedStrip = new RgbLedStripAdapter<NeoEsp32Rmt0Ws2812xMethod>(
            ledCount, G.hardwarePins.led);
    }
#endif
#endif
#if defined(WORDCLOCK_ENABLE_RENDERER_CACHE) && WORDCLOCK_ENABLE_RENDERER_CACHE
    if (!brightnessScheduleBinding::application().attach(activeLedStrip, ledCount, num == Grbw))
        Serial.println("Renderer cache unavailable; retaining full-gain legacy routing");
#endif
}
