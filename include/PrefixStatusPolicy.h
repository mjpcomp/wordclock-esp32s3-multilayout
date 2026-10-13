#pragma once
#include <stdint.h>

namespace prefixStatus {
struct Inputs {
    bool connected;
    bool timeValid;
    bool rtcDetected;
    bool timeSetObserved;
};
struct Color {
    uint8_t r, g, b;
    bool operator!=(const Color &other) const {
        return r != other.r || g != other.g || b != other.b;
    }
};
inline Color choose(const Inputs &in, uint32_t ms) {
    if (!in.timeValid) {
        if (!in.connected) return {0, 0, uint8_t((ms / 500) % 2 ? 24 : 4)};
        return {32, 0, 0};
    }
    if (!in.rtcDetected) return {32, 6, 0};
    if (!in.connected) return {16, 10, 0};
    if (!in.timeSetObserved) return {0, 12, 20};
    return {0, 20, 0};
}
inline Color scale(Color color, float brightness) {
    if (!(brightness > 0)) return {0, 0, 0}; // Includes NaN.
    if (brightness > 1) brightness = 1;
    return {uint8_t(color.r * brightness), uint8_t(color.g * brightness),
            uint8_t(color.b * brightness)};
}
class OutputCache {
    const void *driver = nullptr;
    uint32_t lastPoll = 0;
    bool polled = false, hasColor = false;
    Color previous = {0, 0, 0};
public:
    void reset() { driver = nullptr; polled = false; hasColor = false; }
    bool due(uint32_t ms, const void *currentDriver) {
        if (!currentDriver) return false;
        if (driver != currentDriver) {
            reset();
            driver = currentDriver;
        }
        if (polled && uint32_t(ms - lastPoll) < 250) return false;
        polled = true;
        lastPoll = ms;
        return true;
    }
    bool changed(Color color) const { return !hasColor || color != previous; }
    void sent(Color color) { previous = color; hasColor = true; }
};
} // namespace prefixStatus
