#pragma once
#include <stdint.h>

namespace onboardDiagnostic {
enum class Network : uint8_t { Offline, Connecting, AccessPoint, Connected };
enum class Clock : uint8_t { Invalid, Rtc, Ntp };
enum class Baseline : uint8_t { Offline, Connecting, AccessPoint, TimeInvalid, RtcMissing, ClockRtc, ClockNtp, Fault };
enum class Event : uint8_t { None, TimeSync, FrameChange };
struct Inputs {
    Network network = Network::Offline;
    Clock clock = Clock::Invalid;
    bool rtcExpected = false, rtcDetected = false, fault = false;
};
struct Color {
    uint8_t r, g, b;
    bool operator==(Color other) const { return r == other.r && g == other.g && b == other.b; }
    bool operator!=(Color other) const { return !(*this == other); }
};
struct Frame { Color color; Baseline baseline; Event event; };
constexpr uint32_t TIME_FLASH_MS = 180, TIME_GAP_MS = 5000;
constexpr uint32_t FRAME_FLASH_MS = 80, FRAME_GAP_MS = 1000;

// Single-loop owner. No GPIO, clock reads, allocation, sleeping or network calls.
class Controller {
    Baseline previous = Baseline::Offline;
    bool started = false, timeSeen = false, frameSeen = false;
    bool timeActive = false, frameActive = false;
    uint32_t phaseAt = 0, timeAt = 0, frameAt = 0;
    static Baseline choose(const Inputs &in) {
        if (in.fault || uint8_t(in.network) > uint8_t(Network::Connected) || uint8_t(in.clock) > uint8_t(Clock::Ntp)) return Baseline::Fault;
        switch (in.network) {
        case Network::AccessPoint: return Baseline::AccessPoint;
        case Network::Connecting: return Baseline::Connecting;
        case Network::Offline: return Baseline::Offline;
        case Network::Connected: break;
        }
        if (in.rtcExpected && !in.rtcDetected) return Baseline::RtcMissing;
        if (in.clock == Clock::Invalid) return Baseline::TimeInvalid;
        return in.clock == Clock::Ntp ? Baseline::ClockNtp : Baseline::ClockRtc;
    }
    static bool doubleOn(uint32_t phase) { return phase < 100 || (phase >= 200 && phase < 300); }
    static Color color(Baseline base, uint32_t phase) {
        switch (base) {
        case Baseline::Fault: return doubleOn(phase) ? Color{20,0,0} : Color{0,0,0};
        case Baseline::AccessPoint: return doubleOn(phase) ? Color{0,0,16} : Color{0,0,0};
        case Baseline::RtcMissing: return doubleOn(phase) ? Color{18,6,0} : Color{0,0,0};
        case Baseline::Offline: return phase < 100 ? Color{0,0,12} : Color{0,0,0};
        case Baseline::TimeInvalid: return phase < 100 ? Color{18,6,0} : Color{0,0,0};
        case Baseline::Connecting: {
            const uint32_t ramp = phase <= 1000 ? phase : 2000 - phase;
            const uint8_t level = uint8_t(2 + ramp * 16 / 1000);
            return {level, uint8_t((level + 2) / 3), 0};
        }
        case Baseline::ClockRtc:
        case Baseline::ClockNtp: {
            const uint32_t ramp = phase <= 1000 ? phase : 2000 - phase;
            const uint8_t level = uint8_t(2 + ramp * 10 / 1000);
            return base == Baseline::ClockNtp ? Color{0,level,0} : Color{0,uint8_t(level / 2),level};
        }
        }
        return {0,0,0};
    }
public:
    void reset() { *this = Controller(); }
    bool noteTimeSync(uint32_t now) {
        if (timeSeen && uint32_t(now - timeAt) < TIME_GAP_MS) return false;
        timeSeen = timeActive = true; timeAt = now; return true;
    }
    bool noteFrameChange(uint32_t now) {
        if (frameSeen && uint32_t(now - frameAt) < FRAME_GAP_MS) return false;
        frameSeen = frameActive = true; frameAt = now; return true;
    }
    Frame sample(const Inputs &in, uint32_t now) {
        if (timeActive && uint32_t(now - timeAt) >= TIME_FLASH_MS) timeActive = false;
        if (frameActive && uint32_t(now - frameAt) >= FRAME_FLASH_MS) frameActive = false;
        if (timeSeen && uint32_t(now - timeAt) >= TIME_GAP_MS) timeSeen = false;
        if (frameSeen && uint32_t(now - frameAt) >= FRAME_GAP_MS) frameSeen = false;
        const Baseline base = choose(in);
        if (!started || base != previous) { started = true; previous = base; phaseAt = now; }
        const uint32_t period = base == Baseline::Offline || base == Baseline::Connecting || base == Baseline::ClockRtc || base == Baseline::ClockNtp ? 2000 : 1000;
        const uint32_t phase = uint32_t(now - phaseAt) % period;
        phaseAt = now - phase;
        if (base == Baseline::ClockNtp || base == Baseline::ClockRtc) {
            if (timeActive) return {{20,20,20}, base, Event::TimeSync};
            if (frameActive) return {{16,0,20}, base, Event::FrameChange};
        }
        return {color(base, phase), base, Event::None};
    }
};
} // namespace onboardDiagnostic
