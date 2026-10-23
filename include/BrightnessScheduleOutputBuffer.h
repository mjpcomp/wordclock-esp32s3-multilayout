#pragma once
#include "BrightnessScheduleRuntimeModel.h"

namespace brightnessScheduleOutput {
using Pixel = brightnessScheduleRuntimeModel::Pixel;
constexpr uint16_t kFullGain = brightnessScheduleRuntimeModel::kFullGain;

// Dormant byte-level helper, not a LedStripInterface or a hardware driver.
// Serialized use only. The sink must accept count() logical pixel indices.
// Sink contract: void writePixel(size_t, Pixel), void show(); no reentry.
// flush() reports software submission, never physical acknowledgement.
template<size_t Capacity> class Buffer {
    brightnessScheduleRuntimeModel::Frame<Capacity> frame_;
    uint16_t gain_ = 0;
    bool dirty_ = false;
    static bool equal(Pixel a, Pixel b) {
        return a.r == b.r && a.g == b.g && a.b == b.b && a.w == b.w;
    }
public:
    Buffer() = default;
    Buffer(const Buffer &) = delete;
    Buffer &operator=(const Buffer &) = delete;
    // Clears logical data and resets gain to zero. Does not clear an old sink.
    // The integration must retire/clear old physical output before reconfigure.
    bool configure(size_t count) {
        const bool ok = frame_.configure(count);
        gain_ = 0;
        dirty_ = ok;
        return ok;
    }
    size_t count() const { return frame_.count(); }
    uint16_t gain() const { return gain_; }
    bool pending() const { return count() != 0 && dirty_; }
    Pixel logical(size_t index) const { return frame_.logical(index); }
    bool set(size_t index, Pixel value) {
        if (index >= count()) return false;
        if (!equal(frame_.logical(index), value)) {
            frame_.set(index, value);
            dirty_ = true;
        }
        return true;
    }
    bool clear(size_t index) { return set(index, Pixel{}); }
    void clearAll() {
        for (size_t i = 0; i < count(); ++i) clear(i);
    }
    bool setGain(uint16_t gain) {
        if (gain > kFullGain) gain = kFullGain;
        if (gain == gain_) return false;
        gain_ = gain;
        if (count()) dirty_ = true;
        return true;
    }
    // Explicit resubmission after external sink invalidation; no pixel mutation.
    void invalidateOutput() { if (count()) dirty_ = true; }
    template<class Sink> bool flush(Sink &sink) {
        if (!pending()) return false;
        for (size_t i = 0; i < count(); ++i)
            sink.writePixel(i, frame_.output(i, gain_));
        sink.show();
        dirty_ = false;
        return true;
    }
};
} // namespace brightnessScheduleOutput
