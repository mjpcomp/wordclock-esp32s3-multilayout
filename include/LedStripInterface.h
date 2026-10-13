#pragma once

#include "WordClockState.h"
#include <Arduino.h>
#include <NeoPixelBus.h>

class LedStripInterface {
public:
    virtual ~LedStripInterface() = default;
    virtual void setRgbPixel(uint16_t index, HsbColor color) = 0;
    virtual void setRgbwPixel(uint16_t index, RgbwColor color) = 0;
    virtual RgbColor getPixel(uint16_t index) = 0;
    virtual void clearPixel(uint16_t index) = 0;
    // Dedicated physical prefix access; never part of ordinary logical indices.
    // Returns false when unsupported/disabled. Call show() to transmit a change.
    virtual bool setStatusPixel(RgbColor color) { (void)color; return false; }
    virtual void show() = 0;
};
