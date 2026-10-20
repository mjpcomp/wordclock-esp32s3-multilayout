#pragma once
#include <stdint.h>

namespace brightnessSchedule {
constexpr uint8_t MAX_EVENTS = 16;
constexpr uint32_t DAY_MS = 86400000UL;
struct Event {
    uint16_t minute;
    uint16_t targetTenths;
    uint16_t fadeMinutes;
};
struct Schedule {
    uint16_t defaultTenths;
    uint8_t count;
    Event events[MAX_EVENTS];
};
inline bool valid(const Schedule &s) {
    if (s.defaultTenths > 1000 || s.count > MAX_EVENTS) return false;
    for (uint8_t i = 0; i < s.count; ++i) {
        const Event &e = s.events[i];
        if (e.minute >= 1440 || e.targetTenths > 1000 || e.fadeMinutes >= 1440) return false;
        if (i && s.events[i - 1].minute >= e.minute) return false;
        const uint16_t next = s.events[(i + 1) % s.count].minute;
        const uint16_t gap = s.count == 1 ? 1440 : (next + 1440 - e.minute) % 1440;
        if (e.fadeMinutes > gap) return false;
    }
    return true;
}
inline float percent(const Schedule &s, uint32_t localMs, bool timeValid) {
    if (!valid(s)) return 0.f;
    if (!s.count) return s.defaultTenths / 10.f;
    if (!timeValid) {
        uint16_t lowest = s.defaultTenths;
        for (uint8_t i = 0; i < s.count; ++i)
            if (s.events[i].targetTenths < lowest) lowest = s.events[i].targetTenths;
        return lowest / 10.f;
    }
    localMs %= DAY_MS;
    uint8_t current = s.count - 1;
    for (uint8_t i = 0; i < s.count; ++i) {
        if (uint32_t(s.events[i].minute) * 60000UL > localMs) break;
        current = i;
    }
    const Event &e = s.events[current];
    const Event &previous = s.events[(current + s.count - 1) % s.count];
    const uint32_t elapsed = (localMs + DAY_MS - uint32_t(e.minute) * 60000UL) % DAY_MS;
    const uint32_t duration = uint32_t(e.fadeMinutes) * 60000UL;
    if (!duration || elapsed >= duration) return e.targetTenths / 10.f;
    const float start = previous.targetTenths;
    return (start + (float(e.targetTenths) - start) * (float(elapsed) / duration)) / 10.f;
}
inline bool fromLegacy(const uint8_t levels[8], Schedule &out) {
    const uint16_t minutes[8] = {0, 360, 480, 720, 960, 1080, 1200, 1320};
    Schedule candidate = {};
    candidate.defaultTenths = uint16_t(levels[0]) * 10;
    bool same = true;
    for (uint8_t i = 0; i < 8; ++i) {
        if (levels[i] > 100) return false;
        candidate.events[i] = {minutes[i], uint16_t(levels[i] * 10), 0};
        if (levels[i] != levels[0]) same = false;
    }
    candidate.count = same ? 0 : 8;
    out = candidate;
    return true;
}
} // namespace brightnessSchedule
