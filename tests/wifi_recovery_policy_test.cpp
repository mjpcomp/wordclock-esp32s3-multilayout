#include "WifiRecoveryPolicy.h"
#include <cassert>
namespace w = wifiRecovery;

static w::Inputs inputs(bool enabled, bool setup, bool busy, bool link) {
    w::Inputs in = {};
    in.wifiEnabled = enabled;
    in.setupActive = setup;
    in.attemptBusy = busy;
    in.linkUp = link;
    return in;
}
static w::Inputs offline() { return inputs(true, false, false, false); }
static w::Inputs online() { return inputs(true, false, false, true); }

int main() {
    static_assert(w::STABLE_MS == 60000, "stable interval");
    const uint32_t base[6] = {10000, 20000, 40000, 80000, 160000, 300000};
    for (unsigned step = 0; step < 6; ++step) {
        assert(w::baseDelayMs(uint8_t(step)) == base[step]);
        assert(w::delayMs(uint8_t(step), 0) == base[step] / 4 * 3);
        assert(w::delayMs(uint8_t(step), 250) == base[step]);
        for (uint32_t random = 0; random < 2000; ++random) {
            const uint32_t delay = w::delayMs(uint8_t(step), random);
            assert(delay >= base[step] / 4 * 3 && delay <= base[step]);
        }
    }
    assert(w::baseDelayMs(6) == 300000 && w::baseDelayMs(255) == 300000);

    {
        w::Policy policy;
        assert(policy.step() == 0 && !policy.scheduled());
        uint32_t now = 1000;
        assert(policy.sample(now, offline(), 0) == w::Action::None && policy.scheduled());
        uint32_t due = now + 7500;
        assert(policy.sample(due - 1, offline(), 250) == w::Action::None);
        assert(policy.sample(due, offline(), 250) == w::Action::Reconnect);
        assert(policy.step() == 1);
        now = due;
        const uint32_t expected[5] = {20000, 40000, 80000, 160000, 300000};
        for (unsigned i = 0; i < 5; ++i) {
            assert(policy.sample(now + expected[i] - 1, offline(), 0) == w::Action::None);
            now += expected[i];
            assert(policy.sample(now, offline(), 250) == w::Action::Reconnect);
        }
        assert(policy.step() == w::MAX_STEP);
        assert(policy.sample(now + 299999, offline(), 0) == w::Action::None);
        now += 300000;
        assert(policy.sample(now, offline(), 0) == w::Action::Reconnect);
        assert(policy.step() == w::MAX_STEP);
    }

    for (unsigned kind = 0; kind < 4; ++kind) {
        w::Policy policy;
        assert(policy.sample(0, offline(), 0) == w::Action::None);
        const w::Inputs blocked =
            kind == 0 ? inputs(false, false, false, false) :
            kind == 1 ? inputs(true, true, false, false) :
            kind == 2 ? inputs(true, false, true, false) : online();
        for (uint32_t t = 100000; t < 1000000; t += 7777)
            assert(policy.sample(t, blocked, 0) == w::Action::None);
        assert(!policy.scheduled());
        assert(policy.sample(2000000, offline(), 0) == w::Action::None && policy.scheduled());
        assert(policy.sample(2000000 + 7499, offline(), 0) == w::Action::None);
        assert(policy.sample(2000000 + 7500, offline(), 0) == w::Action::Reconnect);
    }

    {
        w::Policy policy;
        uint32_t now = 0;
        assert(policy.sample(now, offline(), 250) == w::Action::None);
        now += 10000;
        assert(policy.sample(now, offline(), 250) == w::Action::Reconnect);
        now += 20000;
        assert(policy.sample(now, offline(), 250) == w::Action::Reconnect);
        now += 40000;
        assert(policy.sample(now, offline(), 250) == w::Action::Reconnect);
        assert(policy.step() == 3);
        now += 1;
        assert(policy.sample(now, inputs(true, true, false, false), 250) == w::Action::None);
        assert(policy.step() == 0 && !policy.scheduled());
        const uint32_t restart = now + 5000;
        assert(policy.sample(restart, offline(), 250) == w::Action::None);
        assert(policy.sample(restart + 9999, offline(), 250) == w::Action::None);
        assert(policy.sample(restart + 10000, offline(), 250) == w::Action::Reconnect);
    }

    {
        w::Policy policy;
        uint32_t now = 0;
        assert(policy.sample(now, offline(), 250) == w::Action::None);
        now += 10000;
        assert(policy.sample(now, offline(), 250) == w::Action::Reconnect);
        now += 20000;
        assert(policy.sample(now, offline(), 250) == w::Action::Reconnect);
        assert(policy.step() == 2);
        now += 1000;
        const uint32_t upAt = now;
        assert(policy.sample(upAt, online(), 250) == w::Action::None);
        assert(policy.sample(upAt + 59999, online(), 250) == w::Action::None);
        assert(policy.step() == 2);
        const uint32_t downAt = upAt + 60000 - 1;
        assert(policy.sample(downAt, offline(), 250) == w::Action::None && policy.scheduled());
        assert(policy.sample(downAt + 39999, offline(), 250) == w::Action::None);
        assert(policy.sample(downAt + 40000, offline(), 250) == w::Action::Reconnect);
        assert(policy.step() == 3);
        const uint32_t stableAt = downAt + 50000;
        assert(policy.sample(stableAt, online(), 250) == w::Action::None);
        assert(policy.sample(stableAt + 59999, online(), 250) == w::Action::None);
        assert(policy.step() == 3);
        assert(policy.sample(stableAt + 60000, online(), 250) == w::Action::None);
        assert(policy.step() == 0);
        const uint32_t lostAt = stableAt + 61000;
        assert(policy.sample(lostAt, offline(), 250) == w::Action::None);
        assert(policy.sample(lostAt + 9999, offline(), 250) == w::Action::None);
        assert(policy.sample(lostAt + 10000, offline(), 250) == w::Action::Reconnect);
    }

    {
        w::Policy policy;
        const uint32_t start = 0xFFFFFFFFU - 5000U;
        assert(policy.sample(start, offline(), 250) == w::Action::None);
        assert(policy.sample(start + 9999U, offline(), 250) == w::Action::None);
        const uint32_t reconnectAt = start + 10000U;
        assert(reconnectAt < start);
        assert(policy.sample(reconnectAt, offline(), 250) == w::Action::Reconnect);
        assert(policy.step() == 1);
        assert(policy.sample(reconnectAt + 5U, online(), 250) == w::Action::None);
        assert(policy.sample(reconnectAt + 5U + 60000U, online(), 250) == w::Action::None);
        assert(policy.step() == 0);
    }

    {
        w::Policy policy;
        uint32_t seed = 12345U, now = 0xFFFF0000U, eligibleSince = now;
        bool wasEligible = false;
        unsigned reconnects = 0;
        w::Inputs in = offline();
        for (unsigned i = 0; i < 400000; ++i) {
            seed = seed * 1664525U + 1013904223U;
            now += 1U + (seed >> 8) % 3000U;
            seed = seed * 1664525U + 1013904223U;
            if ((seed >> 8) % 50U == 0) {
                seed = seed * 1664525U + 1013904223U;
                const uint32_t pick = seed >> 8;
                in = inputs(pick % 11U != 0, pick / 11U % 7U == 0,
                            pick / 77U % 5U == 0, pick / 385U % 3U == 0);
            }
            const bool eligible = in.wifiEnabled && !in.setupActive &&
                                  !in.attemptBusy && !in.linkUp;
            if (!eligible) {
                wasEligible = false;
            } else if (!wasEligible) {
                wasEligible = true;
                eligibleSince = now;
            }
            seed = seed * 1664525U + 1013904223U;
            const w::Action action = policy.sample(now, in, seed >> 8);
            if (action == w::Action::Reconnect) {
                assert(eligible);
                assert(uint32_t(now - eligibleSince) >= 7500U);
                eligibleSince = now;
                ++reconnects;
            }
            assert(policy.step() <= w::MAX_STEP);
        }
        assert(reconnects > 100);
    }
}
