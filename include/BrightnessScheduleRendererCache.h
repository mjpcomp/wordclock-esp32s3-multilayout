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
    brightnessScheduleRuntimeModel::Frame<Capacity> presented_;
    uint16_t presentedGain_ = 0;
    bool havePresented_ = false, presentedInvalid_ = false;
public:
    // Resets logical pixels/gain. Does NOT retire/clear any previous backend.
    bool configure(size_t count, PixelMode mode) {
        mode_ = mode;
        havePresented_ = presentedInvalid_ = false;
        presentedGain_ = 0;
        const bool ok = buffer_.configure(count);
        (void)presented_.configure(ok ? count : 0);
        return ok;
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
    void invalidateOutput() {
        buffer_.invalidateOutput();
        if (havePresented_) presentedInvalid_ = true;
    }
    // Software submission only, never hardware acknowledgement.
    // flush() explicitly submits staging and updates presentation history.
    template<class Sink> bool flush(Sink &sink) {
        if (!buffer_.flush(sink)) return false;
        for (size_t i = 0; i < count(); ++i) presented_.set(i, logical(i));
        presentedGain_ = gain();
        havePresented_ = true;
        presentedInvalid_ = false;
        return true;
    }
    // Gain-only loop repaint: never submit an unshown staged target.
    template<class Sink> bool repaint(Sink &sink) {
        if (!havePresented_ || (!presentedInvalid_ && presentedGain_ == gain())) return false;
        for (size_t i = 0; i < count(); ++i) sink.writePixel(i, presented_.output(i, gain()));
        sink.show();
        presentedGain_ = gain();
        presentedInvalid_ = false;
        return true;
    }
    // An explicit renderer show remains a show, including prefix-only changes.
    // Gain-only loop polling uses repaint(); flush() still submits staged pixels.
    template<class Sink> void show(Sink &sink) {
        if (!flush(sink)) sink.show();
    }
};
} // namespace brightnessScheduleRenderer
