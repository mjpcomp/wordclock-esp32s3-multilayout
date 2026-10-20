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
std::atomic<uint32_t> observedNtpEvents{0};
bool reported = false;
uint32_t lastReportMs = 0, lastReportedEvents = 0;
int lastReportedWifi = -1;

// Main task only. Observe configuration; do not change DNS, resolve names,
// restart SNTP, read/clear SNTP completion status, or transmit from callbacks.
void reportTimeState(uint32_t ms, int wifiStatus) {
    const uint32_t events = observedNtpEvents.load(std::memory_order_relaxed);
    const uint32_t elapsed = uint32_t(ms - lastReportMs);
    if (reported && (elapsed < 1000 ||
        (elapsed < 30000 && wifiStatus == lastReportedWifi && events == lastReportedEvents)))
        return;
    reported = true; lastReportMs = ms;
    lastReportedWifi = wifiStatus; lastReportedEvents = events;
    const time_t utc = time(nullptr);
    Serial.printf("[TIME-DIAG] ms=%lu wifi_status=%d epoch=%lld time_valid=%u ntp_events=%lu\n",
                  static_cast<unsigned long>(ms), wifiStatus,
                  static_cast<long long>(utc), unsigned(utc > 100000000),
                  static_cast<unsigned long>(events));
    Serial.printf("[TIME-DIAG] configured_ntp=%s timezone=%s\n", G.timeserver, G.timezone);
    Serial.printf("[TIME-DIAG] ip=%s gateway=%s dns0=%s dns1=%s\n",
                  WiFi.localIP().toString().c_str(), WiFi.gatewayIP().toString().c_str(),
                  WiFi.dnsIP(0).toString().c_str(), WiFi.dnsIP(1).toString().c_str());
}
}
inline void noteNtp(uint32_t ms) {
    runtime.noteNtpSync(ms);
    observedNtpEvents.fetch_add(1, std::memory_order_relaxed);
}
inline void noteRtc(uint32_t ms) { runtime.noteRtcTime(ms); }
inline void resetFrames() { runtime.resetFrames(); }
inline void connecting(bool active) { connectionAttempt = active; }
inline void service() {
    using onboardDiagnostic::Network;
    const uint32_t ms = millis();
    const int wifiStatus = WiFi.status();
    const bool ap = (uint8_t(WiFi.getMode()) & uint8_t(WIFI_AP)) != 0;
    const Network state = ap ? Network::AccessPoint
        : wifiStatus == WL_CONNECTED ? Network::Connected
        : connectionAttempt ? Network::Connecting : Network::Offline;
    const LedStripDiagnostics stats = activeLedStrip
        ? activeLedStrip->diagnostics() : LedStripDiagnostics{0,0,0,false};
    const bool unexpectedBackend = activeLedStrip && !activeLedStrip->isVirtual();
    runtime.service(ms, state, time(nullptr) > 100000000,
                    externalRTC, unexpectedBackend,
                    stats.countersAvailable && !unexpectedBackend,
                    stats.changedFrames);
    reportTimeState(ms, wifiStatus);
}
}
#endif
