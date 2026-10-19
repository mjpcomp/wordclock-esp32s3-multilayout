#pragma once
#include "ClockTestPolicy.h"

// Include once in WordClock.cpp, after activeLedStrip is declared.
namespace onboardDiagnosticApplication {
#if WORDCLOCK_TEST_MODE == 0
inline void noteNtp(uint32_t) {}
inline void noteRtc(uint32_t) {}
inline void resetFrames() {}
inline void connecting(bool) {}
inline void service() {}
#endif
}
#if WORDCLOCK_TEST_MODE != 0
#include "OnboardDiagnosticSink.h"
#include "OnboardDiagnosticRuntime.h"
#include <time.h>
namespace onboardDiagnosticApplication {
namespace {
onboardDiagnostic::Gpio48Sink sink;
onboardDiagnostic::Runtime<onboardDiagnostic::Gpio48Sink,
                          clockTestPolicy::MODE == 2> runtime(sink);
bool connectionAttempt = false;
}
inline void noteNtp(uint32_t ms) { runtime.noteNtpSync(ms); }
inline void noteRtc(uint32_t ms) { runtime.noteRtcTime(ms); }
inline void resetFrames() { runtime.resetFrames(); }
inline void connecting(bool active) { connectionAttempt = active; }
inline void service() {
    using onboardDiagnostic::Network;
    const bool ap = (uint8_t(WiFi.getMode()) & uint8_t(WIFI_AP)) != 0;
    const Network state = ap ? Network::AccessPoint
        : WiFi.status() == WL_CONNECTED ? Network::Connected
        : connectionAttempt ? Network::Connecting : Network::Offline;
    const LedStripDiagnostics stats = activeLedStrip
        ? activeLedStrip->diagnostics() : LedStripDiagnostics{0,0,0,false};
    const bool unexpectedBackend = activeLedStrip && !activeLedStrip->isVirtual();
    runtime.service(millis(), state, time(nullptr) > 100000000,
                    externalRTC, unexpectedBackend,
                    stats.countersAvailable && !unexpectedBackend,
                    stats.changedFrames);
}
}
#endif
