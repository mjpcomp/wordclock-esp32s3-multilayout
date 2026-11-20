#!/usr/bin/env python3
"""Host-test the blackout bridge with the real runtime/model and mocked I/O."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CPP = r"""#include <stdint.h>
#include <cassert>
#include <string>
#include <vector>
#include <time.h>
#if WORDCLOCK_TEST_MODE != 0
struct Write { uint32_t now; uint8_t r,g,b; };
static std::vector<Write> writes;
static uint32_t testMs = 0, frameCount = 10;
uint32_t millis() { return testMs; }
time_t fakeTime(time_t *) { return 1700000000; }
#define time fakeTime
struct SerialMock { void printf(const char *, ...) {} } Serial;
struct Address { std::string toString() const { return "192.0.2.1"; } };
constexpr int WIFI_AP = 2, WL_CONNECTED = 3;
struct WifiMock {
 int status() { return WL_CONNECTED; }
 int getMode() { return 1; }
 Address localIP() { return {}; }
 Address gatewayIP() { return {}; }
 Address dnsIP(uint8_t) { return {}; }
} WiFi;
struct { char timeserver[16]="clock"; char timezone[16]="UTC0"; } G;
struct LedStripDiagnostics {
 uint16_t logicalPixels; uint32_t showRequests, changedFrames; bool countersAvailable;
};
struct Backend {
 LedStripDiagnostics diagnostics() { return {114, frameCount, frameCount, true}; }
 bool isVirtual() { return true; }
} backend;
Backend *activeLedStrip = &backend;
bool externalRTC = true;
#endif
#include "OnboardDiagnosticApplication.hpp"
#if WORDCLOCK_TEST_MODE != 0
void assertBlack() {
 const auto &w = writes.back(); assert(w.r == 0 && w.g == 0 && w.b == 0);
}
void assertBaseline() {
 const auto &w = writes.back(); assert(w.r == 0 && w.g > 0 && w.b == 0);
}
#endif
int main() {
 using namespace onboardDiagnosticApplication;
#if WORDCLOCK_TEST_MODE == 0
 wordclockDiagnosticBeforeNetworkWork();
 beforeNetworkWork(); suppress(); service(); service(false);
#else
 noteNtp(0); service();
 assert(writes.back().r == 20 && writes.back().g == 20 && writes.back().b == 20);
 testMs = 20; service();
 assert(writes.back().r == 20 && writes.back().g == 20 && writes.back().b == 20);
 size_t n = writes.size();
 testMs = 21; wordclockDiagnosticBeforeNetworkWork();
 assert(writes.size() == n+1 && writes.back().now == 21); assertBlack();
 wordclockDiagnosticBeforeNetworkWork(); assert(writes.size() == n+1);
 auto nestedCallback = []() {
  const size_t before = writes.size();
  wordclockDiagnosticBeforeNetworkWork(); noteNtp(22);
  assert(writes.size() == before);
 };
 nestedCallback();
 frameCount = 11; testMs = 200; service(); assertBaseline();
 frameCount = 12; testMs = 220; service();
 assert(writes.back().r == 16 && writes.back().g == 0 && writes.back().b == 20);
 testMs = 221; n = writes.size(); wordclockDiagnosticBeforeNetworkWork();
 assert(writes.size() == n+1); assertBlack();
 testMs = 222; service(false); assertBlack();
 n = writes.size(); wordclockDiagnosticBeforeNetworkWork(); assert(writes.size() == n);
 noteNtp(7050); frameCount = 30; testMs = 7070; service(false); assertBlack();
 testMs = 7100; service(true); assertBaseline();
 n = writes.size(); testMs = 7200; suppress();
 assert(writes.size() == n+1); assertBlack();
 wordclockDiagnosticBeforeNetworkWork(); assert(writes.size() == n+1);
 suppress(); assert(writes.size() == n+2);
 testMs = UINT32_MAX-10; service();
 n = writes.size(); wordclockDiagnosticBeforeNetworkWork(); assert(writes.size() == n+1);
 testMs = 5; wordclockDiagnosticBeforeNetworkWork(); assert(writes.size() == n+1);
 service(); assertBaseline();
 n = writes.size(); wordclockDiagnosticBeforeNetworkWork(); assert(writes.size() == n+1);
 assertBlack();
#endif
}
"""
SINK = r"""#pragma once
namespace onboardDiagnostic {
class Gpio48Sink {
public:
 bool service(uint32_t now, uint8_t r, uint8_t g, uint8_t b) {
  writes.push_back({now,r,g,b}); return true;
 }
};
}
"""

def main():
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ is required")
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        shutil.copyfile(ROOT / "include/OnboardDiagnosticApplication.hpp", work / "OnboardDiagnosticApplication.hpp")
        (work / "ClockTestPolicy.h").write_text(
            "#pragma once\n#include <stdint.h>\n"
            "namespace clockTestPolicy { constexpr int MODE=WORDCLOCK_TEST_MODE; }\n")
        (work / "test.cpp").write_text(CPP)
        for mode in (0, 1, 2):
            for name in ("OnboardDiagnosticSink.h", "OnboardDiagnosticRuntime.h", "OnboardDiagnosticModel.h"):
                (work / name).unlink(missing_ok=True)
            if mode:
                (work / "OnboardDiagnosticSink.h").write_text(SINK)
                for name in ("OnboardDiagnosticRuntime.h", "OnboardDiagnosticModel.h"):
                    shutil.copyfile(ROOT / "include" / name, work / name)
            subprocess.run([
                compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all",
                "-DWORDCLOCK_TEST_MODE=" + str(mode), "-I" + str(work),
                str(work / "test.cpp"), "-o", str(work / "test")], check=True)
            subprocess.run([str(work / "test")], check=True)
    print("PASS: blackout bridge modes 0/1/2 with real runtime/model; I/O mocked.")

if __name__ == "__main__":
    main()
