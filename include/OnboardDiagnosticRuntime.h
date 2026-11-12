#pragma once
#include "OnboardDiagnosticModel.h"
#include <atomic>

namespace onboardDiagnostic {
// Main-loop orchestration. Sink must provide service(now,r,g,b).
// The only callback-safe entry point is noteNtpSync(); timestamps are captured
// at the event, so a delayed main loop cannot replay an expired white pulse.
template<class Sink, bool RtcExpected> class Runtime {
    Controller model;
    Sink &sink;
    Clock source = Clock::Invalid;
    std::atomic<uint32_t> ntpStamp{0};
    std::atomic<bool> ntpPending{false};
    bool framesSeen = false, muted = false;
    uint32_t previousFrames = 0;
    void consumePendingNtp() {
        if (ntpPending.exchange(false, std::memory_order_acquire)) {
            source = Clock::Ntp;
            model.noteTimeSync(ntpStamp.load(std::memory_order_relaxed));
        }
    }
public:
    explicit Runtime(Sink &output) : sink(output) {}
    Runtime(const Runtime &) = delete;
    Runtime &operator=(const Runtime &) = delete;
    void noteNtpSync(uint32_t eventMs) {
        ntpStamp.store(eventMs, std::memory_order_relaxed);
        ntpPending.store(true, std::memory_order_release);
    }
    // Main-loop only; call after a successful, valid RTC time load.
    // Detection alone must not call this method. BOARD_ONLY ignores it.
    void noteRtcTime(uint32_t eventMs) {
        if (!RtcExpected) return;
        source = Clock::Rtc;
        model.noteTimeSync(eventMs);
    }
    // Main-loop only; call on backend deletion/recreation, even at the same address.
    void resetFrames() { framesSeen = false; }
    // Main-loop only; suppress pulses without forgetting source or cooldowns.
    void suppress(uint32_t now) {
        consumePendingNtp();
        model.clearActiveEvents();
        resetFrames();
        muted = true;
        sink.service(now, 0, 0, 0);
    }
    Frame service(uint32_t now, Network network, bool timeValid,
                  bool rtcDetected, bool fault, bool countersAvailable,
                  uint32_t changedFrames, bool permitted = true) {
        consumePendingNtp();
        const bool resuming = permitted && muted;
        if (!countersAvailable) {
            resetFrames();
        } else {
            if (permitted && !resuming && framesSeen && changedFrames != previousFrames)
                model.noteFrameChange(now);
            previousFrames = changedFrames;
            framesSeen = true;
        }
        Inputs in;
        in.network = network;
        in.clock = timeValid ? source : Clock::Invalid;
        in.rtcExpected = RtcExpected;
        in.rtcDetected = rtcDetected;
        in.fault = fault;
        if (!permitted || muted) model.clearActiveEvents();
        muted = !permitted;
        Frame frame = model.sample(in, now);
        if (!permitted) {
            frame.color = {0, 0, 0};
            frame.event = Event::None;
        }
        sink.service(now, frame.color.r, frame.color.g, frame.color.b);
        return frame;
    }
};
} // namespace onboardDiagnostic
