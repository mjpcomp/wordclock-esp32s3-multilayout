#pragma once
#include "BrightnessScheduleOutputBuffer.h"
#include <NeoPixelBus.h>

namespace brightnessScheduleRenderer {
// Explicit caller choice: physical RGBW readback uses the library conversion;
// virtual RGBW readback returns RGB bytes only, matching its existing backend.
enum class PixelMode { Rgb, VirtualRgbw, PhysicalRgbw };

// Dormant renderer boundary, not a driver or LedStripInterface decorator.
// Capture already-converted native bytes BEFORE the new schedule gain.
// Caller owns backend/count agreement, serialized access and legacy brightness.
template<size_t Capacity> class Cache {
    brightnessScheduleOutput::Buffer<Capacity> buffer_;
    PixelMode mode_ = PixelMode::Rgb;
public:
    // Resets logical pixels/gain. Does NOT retire/clear any previous backend.
    bool configure(size_t count, PixelMode mode) {
        mode_ = mode;
        return buffer_.configure(count);
    }
    size_t count() const { return buffer_.count(); }
    bool pending() const { return buffer_.pending(); }
    uint16_t gain() const { return buffer_.gain(); }
    bool capture(size_t index, RgbwColor value) {
        if (mode_ == PixelMode::Rgb) value.W = 0;
        return buffer_.set(index, {value.R, value.G, value.B, value.W});
    }
    brightnessScheduleOutput::Pixel logical(size_t index) const {
        return buffer_.logical(index);
    }
    RgbColor read(size_t index) const {
        if (index >= count()) return RgbColor(0);
        const auto p = logical(index);
        if (mode_ == PixelMode::PhysicalRgbw)
            return RgbColor(RgbwColor(p.r, p.g, p.b, p.w));
        return RgbColor(p.r, p.g, p.b);
    }
    bool clear(size_t index) { return buffer_.clear(index); }
    void clearAll() { buffer_.clearAll(); }
    bool setGain(uint16_t gain) { return buffer_.setGain(gain); }
    void invalidateOutput() { buffer_.invalidateOutput(); }
    // Software submission only, never hardware acknowledgement.
    template<class Sink> bool flush(Sink &sink) { return buffer_.flush(sink); }
    // An explicit renderer show remains a show, including prefix-only changes.
    // Gain-only polling should use flush(), not this unconditional show boundary.
    template<class Sink> void show(Sink &sink) {
        if (!flush(sink)) sink.show();
    }
};
} // namespace brightnessScheduleRenderer
