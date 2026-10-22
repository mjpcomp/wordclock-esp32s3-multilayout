#!/usr/bin/env python3
"""Review/stage exact state-only startup binding and compile extracted call sites."""
from pathlib import Path
import argparse
import hashlib
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = 'a5e1102a5e67b3fa4419a5a5c06f76a8cd1a8b441e4bd3c54d9001a9e600807f'
OUTPUT_SHA = '626e25abbba018c6b2359c4ccb8ff5011d5067b39b97d375480bf7e336f2df1b'
INCLUDE = '#if defined(ESP32)\n#include "BrightnessScheduleRuntimeOwner.h"\n#endif\n'
BOOT = '#if defined(ESP32)\n    // Read-only startup load; faults are retained, never automatically reset.\n    (void)brightnessScheduleRuntimeOwner::applicationRuntime().begin();\n#endif\n'
SERVICE = '#if defined(ESP32)\n    // State only: control changes above are applied before sampling real time.\n    (void)brightnessScheduleRuntimeOwner::applicationRuntime().serviceFromClock(\n        millis(), brightnessScheduleRuntimeOwner::systemLocalTime, nullptr,\n        G.autoBrightEnabled == 1, led.getState());\n#endif\n'
PATCHES = [('#include "PrefixStatusRuntime.h"\n', '#include "PrefixStatusRuntime.h"\n#if defined(ESP32)\n#include "BrightnessScheduleRuntimeOwner.h"\n#endif\n'), ('    // Setup Done\n    //-------------------------------------\n    parametersChanged = true;', '    // Setup Done\n    //-------------------------------------\n#if defined(ESP32)\n    // Read-only startup load; faults are retained, never automatically reset.\n    (void)brightnessScheduleRuntimeOwner::applicationRuntime().begin();\n#endif\n    parametersChanged = true;'), ('    clockWork.loop(tm);\n', '    clockWork.loop(tm);\n#if defined(ESP32)\n    // State only: control changes above are applied before sampling real time.\n    (void)brightnessScheduleRuntimeOwner::applicationRuntime().serviceFromClock(\n        millis(), brightnessScheduleRuntimeOwner::systemLocalTime, nullptr,\n        G.autoBrightEnabled == 1, led.getState());\n#endif\n')]

def prepared(text):
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest == BASE_SHA:
        for old, new in PATCHES:
            if text.count(old) != 1:
                raise SystemExit("Unexpected application anchor")
            text = text.replace(old, new, 1)
    elif digest != OUTPUT_SHA:
        raise SystemExit("Unexpected WordClock baseline; inspect before changing hashes")
    if hashlib.sha256(text.encode()).hexdigest() != OUTPUT_SHA:
        raise SystemExit("Unexpected application output")
    setup = text[text.index("void setup() {"):text.index("void loop() {")]
    loop = text[text.index("void loop() {"):]
    assert text.count(INCLUDE) == text.count(BOOT) == text.count(SERVICE) == 1
    assert setup.index("eeprom::read();") < setup.index("applyTimezone();") < setup.index(BOOT)
    assert setup.index("transition->init();") < setup.index(BOOT)
    assert loop.index("webSocket.loop();") < loop.index("clockWork.loop(tm);") < loop.index(SERVICE)
    assert loop.index(SERVICE) < loop.index("prefixStatusRuntime::service();") < loop.index("onboardDiagnosticApplication::service();")
    return text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-application", action="store_true")
    args = parser.parse_args()
    path = ROOT / "src/WordClock.cpp"
    current = path.read_text()
    candidate = prepared(current)
    cpp = (ROOT / "tests/brightness_schedule_application_binding_test.cpp").read_text()
    assert cpp.count("/*BOOT*/") == cpp.count("/*SERVICE*/") == 1
    cpp = cpp.replace("/*BOOT*/", BOOT).replace("/*SERVICE*/", SERVICE)
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ required for application binding tests")
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        src = work / "application.cpp"
        src.write_text(cpp)
        binary = work / "application"
        subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all",
                        "-I", str(ROOT / "include"), str(src), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    if args.stage_application and current != candidate:
        path.write_text(candidate)
        print("Staged reviewed application in build workspace only")
    print("PASS: state-only application source contract and call-site host test")

if __name__ == "__main__":
    main()
