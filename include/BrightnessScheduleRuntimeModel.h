#pragma once
#include "BrightnessSchedule.h"
#include <stddef.h>
#include <stdint.h>

namespace brightnessScheduleRuntimeModel {
constexpr uint16_t kFullGain = 10000;
enum class Startup { Missing, Ready, Fault };
struct Decision {
    uint16_t gain;
    uint32_t revision;
    bool scheduled;
    bool pausedAutomatic;
    bool waitingForTime;
    bool storageFault;
};
class Model {
    brightnessSchedule::Schedule profile = {};
    uint32_t revision_ = 0;
    bool haveProfile = false, fault = false;
public:
    bool begin(Startup state, const brightnessSchedule::Schedule *value = nullptr, uint32_t revision = 0) {
        haveProfile = false; fault = false; revision_ = 0;
        profile = brightnessSchedule::Schedule{};
        if (state == Startup::Missing) return true;
        if (state == Startup::Ready && value) return accept(*value, revision);
        fault = true; return false;
    }
    bool accept(const brightnessSchedule::Schedule &value, uint32_t revision) {
        if (!revision || !brightnessSchedule::valid(value)) { fault = true; return false; }
        profile = value; revision_ = revision; haveProfile = true; fault = false;
        return true;
    }
    void noteStorageIssue() { fault = true; }
    Decision sample(uint32_t realLocalMs, bool timeValid, bool automatic, bool masterOn) const {
        Decision d = {kFullGain, revision_, false, automatic && haveProfile, false, fault};
        if (!automatic && (haveProfile || fault)) {
            d.scheduled = true;
            if (!haveProfile) d.gain = 0;
            else {
                const float value = brightnessSchedule::percent(profile, realLocalMs, timeValid);
                d.gain = value <= 0 ? 0 : value >= 100 ? kFullGain : static_cast<uint16_t>(value * 100.f + 0.5f);
                d.waitingForTime = profile.count != 0 && !timeValid;
            }
        }
        if (!masterOn) d.gain = 0;
        return d;
    }
};
struct Pixel { uint8_t r, g, b, w; };
static_assert(sizeof(Pixel) == 4, "Logical cache pixels must use four bytes");
inline uint8_t scale(uint8_t value, uint16_t gain) {
    if (gain > kFullGain) gain = kFullGain;
    return static_cast<uint8_t>((uint32_t(value) * gain + kFullGain / 2) / kFullGain);
}
template<size_t Capacity> class Frame {
    static_assert(Capacity > 0, "Cache capacity must be positive");
    Pixel pixels[Capacity] = {};
    size_t count_ = 0;
public:
    bool configure(size_t count) {
        for (size_t i = 0; i < Capacity; ++i) pixels[i] = Pixel{};
        count_ = count <= Capacity ? count : 0;
        return count != 0 && count <= Capacity;
    }
    size_t count() const { return count_; }
    bool set(size_t index, Pixel value) {
        if (index >= count_) return false;
        pixels[index] = value; return true;
    }
    bool clear(size_t index) { return set(index, Pixel{}); }
    Pixel logical(size_t index) const { return index < count_ ? pixels[index] : Pixel{}; }
    Pixel output(size_t index, uint16_t gain) const {
        const Pixel p = logical(index);
        return Pixel{scale(p.r,gain),scale(p.g,gain),scale(p.b,gain),scale(p.w,gain)};
    }
};
} // namespace brightnessScheduleRuntimeModel
