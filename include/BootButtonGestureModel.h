#pragma once
#include <stdint.h>

namespace bootButtonGesture {
constexpr uint32_t DEBOUNCE_MS = 40;
constexpr uint32_t MODE_HOLD_MS = 2000;
constexpr uint32_t RECOVERY_HOLD_MS = 8000;
enum class Action : uint8_t { None, NextMode, WiFiSetup };

// Serialized caller, logical pressed input. No GPIO, time reads or side effects.
class Model {
    bool initialized = false, raw = false, stable = false;
    bool armed = false, active = false, modeAtPress = false;
    bool recoveryQualified = false;
    uint32_t changedAt = 0, pressedAt = 0;
public:
    void reset() { *this = Model(); }
    Action sample(uint32_t now, bool pressed, bool modeShortcutEnabled = false) {
        if (!initialized) {
            initialized = true;
            raw = stable = pressed;
            changedAt = now;
            armed = !pressed;
            return Action::None;
        }
        if (active && uint32_t(now - pressedAt) >= RECOVERY_HOLD_MS)
            recoveryQualified = true;
        if (pressed != raw) {
            raw = pressed;
            changedAt = now;
        }
        if (uint32_t(now - changedAt) < DEBOUNCE_MS || raw == stable)
            return Action::None;
        stable = raw;
        if (stable) {
            if (armed) {
                active = true;
                armed = false;
                pressedAt = now;
                modeAtPress = modeShortcutEnabled;
                recoveryQualified = false;
            }
            return Action::None;
        }
        armed = true;
        if (!active) return Action::None;
        active = false;
        const uint32_t duration = uint32_t(now - pressedAt);
        if (recoveryQualified || duration >= RECOVERY_HOLD_MS)
            return Action::WiFiSetup;
        if (modeAtPress && duration >= MODE_HOLD_MS)
            return Action::NextMode;
        return Action::None;
    }
};
} // namespace bootButtonGesture
