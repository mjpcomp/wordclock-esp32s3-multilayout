#pragma once
#include <stdint.h>

namespace wifiRecovery {
constexpr uint32_t STABLE_MS = 60000;
constexpr uint8_t MAX_STEP = 5;
constexpr uint32_t MIN_JITTER_PERMILLE = 750;
enum class Action : uint8_t { None, Reconnect };

// linkUp means associated with a non-zero IP, not merely a valid system clock.
// attemptBusy must be true only when the caller positively knows an
// association or DHCP attempt is in progress.
struct Inputs {
    bool wifiEnabled;
    bool setupActive;
    bool attemptBusy;
    bool linkUp;
};

inline uint32_t baseDelayMs(uint8_t step) {
    switch (step) {
    case 0: return 10000;
    case 1: return 20000;
    case 2: return 40000;
    case 3: return 80000;
    case 4: return 160000;
    default: return 300000;
    }
}
// 75-100 percent of the base delay; random is supplied by the caller.
inline uint32_t delayMs(uint8_t step, uint32_t random) {
    return baseDelayMs(step) * (MIN_JITTER_PERMILLE + random % 251U) / 1000U;
}

// Single serialized caller. No Wi-Fi/SDK calls, clock reads, randomness,
// persistence or side effects. A Reconnect result is only a request; the
// mechanism, and any interaction with the framework's own retries, belongs to
// a later integration batch. This model never requests setup/AP mode.
class Policy {
    bool wasUp_ = false, scheduled_ = false;
    uint8_t step_ = 0;
    uint32_t stableSince_ = 0, dueAt_ = 0;
public:
    void reset() { *this = Policy(); }
    uint8_t step() const { return step_; }
    bool scheduled() const { return scheduled_; }
    Action sample(uint32_t now, const Inputs &in, uint32_t random) {
        if (!in.wifiEnabled || in.setupActive) {
            wasUp_ = scheduled_ = false;
            step_ = 0;
            return Action::None;
        }
        if (in.linkUp) {
            scheduled_ = false;
            if (!wasUp_) {
                wasUp_ = true;
                stableSince_ = now;
            } else if (uint32_t(now - stableSince_) >= STABLE_MS) {
                step_ = 0;
            }
            return Action::None;
        }
        wasUp_ = false;
        if (in.attemptBusy) {
            scheduled_ = false;
            return Action::None;
        }
        if (!scheduled_) {
            dueAt_ = now + delayMs(step_, random);
            scheduled_ = true;
            return Action::None;
        }
        if (int32_t(now - dueAt_) < 0) return Action::None;
        if (step_ < MAX_STEP) ++step_;
        dueAt_ = now + delayMs(step_, random);
        return Action::Reconnect;
    }
};
} // namespace wifiRecovery
