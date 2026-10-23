#pragma once
#include "BrightnessScheduleOutputBuffer.h"
#include "LedStripInterface.h"

namespace brightnessScheduleOutput {
// Non-owning sink, not an adapter decorator. Backend identity is unchanged.
// Caller must match buffer count to backend capacity and serialize access.
// Already-converted bytes bypass HSB; RGB backends retain their W-drop policy.
class StripSink {
    LedStripInterface &strip_;
public:
    explicit StripSink(LedStripInterface &strip) : strip_(strip) {}
    void writePixel(size_t index, Pixel value) {
        if (index > UINT16_MAX) return;
        strip_.setRgbwPixel(static_cast<uint16_t>(index),
                           RgbwColor(value.r, value.g, value.b, value.w));
    }
    void show() { strip_.show(); }
};
} // namespace brightnessScheduleOutput
