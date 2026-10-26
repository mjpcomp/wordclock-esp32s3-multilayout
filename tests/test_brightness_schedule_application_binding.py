#!/usr/bin/env python3
"""Verify state-only startup binding while preserving exact reviewed output hooks."""
from pathlib import Path
import argparse
import hashlib
import json
import runpy
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
RENDERER_BASE = '#include "OnboardDiagnosticApplication.hpp"\n\nvoid deleteActiveLedStrip() {\n    prefixStatusRuntime::resetDisplay();\n    onboardDiagnosticApplication::resetFrames();\n    delete activeLedStrip;\n    activeLedStrip = nullptr;\n}\n'
RENDERER_BOUND = '#include "OnboardDiagnosticApplication.hpp"\n#include "BrightnessScheduleRendererBinding.h"\n\nvoid deleteActiveLedStrip() {\n    prefixStatusRuntime::resetDisplay();\n    onboardDiagnosticApplication::resetFrames();\n#if WORDCLOCK_ENABLE_RENDERER_CACHE\n    (void)brightnessScheduleBinding::application().retire(activeLedStrip);\n#endif\n    delete activeLedStrip;\n    activeLedStrip = nullptr;\n}\n'

def output_rules():
    return json.loads((ROOT / "docs/patches/brightness-schedule-output.json").read_text())["replacements"]

def output_canonical(text):
    normalize = runpy.run_path(str(ROOT / "tests/test_brightness_schedule_output_candidate.py"))["normalize_promoted"]
    return normalize(text, "src/WordClock.cpp", output_rules())

def prepared(text):
    canonical_output = output_canonical(text)
    if canonical_output != text:
        if prepared(canonical_output) != canonical_output:
            raise SystemExit("Output promotion requires the verified application binding")
        return text  # Preserve installed output code; never write its older baseline.
    if RENDERER_BOUND in text:
        if text.count(RENDERER_BOUND) != 1:
            raise SystemExit("Unexpected renderer retirement count")
        canonical = text.replace(RENDERER_BOUND, RENDERER_BASE, 1)
        if prepared(canonical) != canonical:
            raise SystemExit("Renderer retirement requires the verified application binding")
        return text
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

def verify_baselines(text):
    text = output_canonical(text)
    canonical = text.replace(RENDERER_BOUND, RENDERER_BASE, 1)
    assert prepared(canonical) == canonical
    assert canonical.count(RENDERER_BASE) == 1
    promoted = canonical.replace(RENDERER_BASE, RENDERER_BOUND, 1)
    assert prepared(promoted) == promoted
    unbound = canonical
    for block in (INCLUDE, BOOT, SERVICE):
        assert unbound.count(block) == 1
        unbound = unbound.replace(block, "", 1)
    assert hashlib.sha256(unbound.encode()).hexdigest() == BASE_SHA
    assert prepared(unbound) == canonical
    faults = (
        promoted.replace("#if WORDCLOCK_ENABLE_RENDERER_CACHE", "#if WRONG_RENDERER_GATE", 1),
        promoted.replace("    (void)brightnessScheduleBinding::application().retire(activeLedStrip);", "", 1),
        promoted.replace("    delete activeLedStrip;", "    delete activeLedStrip; // unexpected change", 1),
        promoted.replace("constexpr uint16_t EEPROM_SIZE = 512;", "constexpr uint16_t EEPROM_SIZE = 513;", 1),
        promoted + '#include "BrightnessScheduleRendererBinding.h"\n',
    )
    for altered in faults:
        assert altered != promoted
        try:
            prepared(altered)
        except SystemExit:
            pass
        else:
            raise AssertionError("Unreviewed source drift accepted")

def verify_output_promotions(text):
    canonical = output_canonical(text)
    promoted = canonical
    group = [item for item in output_rules() if item["path"] == "src/WordClock.cpp"]
    if len(group) != 2: raise ValueError("WordClock promotion group drift")
    for item in group:
        if promoted.count(item["old"]) != 1: raise ValueError("Output promotion anchor drift")
        promoted = promoted.replace(item["old"], item["new"], 1)
    assert prepared(canonical) == canonical
    assert prepared(promoted) == promoted
    assert output_canonical(promoted) == canonical
    faults = (
        promoted.replace("owner.current()", "owner.unreviewedCurrent()", 1),
        promoted.replace("constexpr uint16_t EEPROM_SIZE = 512;", "constexpr uint16_t EEPROM_SIZE = 513;", 1),
        canonical.replace(group[0]["old"], group[0]["new"], 1),
        promoted + group[0]["new"],
    )
    for altered in faults:
        assert altered != promoted and altered != canonical
        try:
            prepared(altered)
        except (ValueError, SystemExit):
            pass
        else:
            raise AssertionError("Unreviewed output promotion accepted")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-application", action="store_true")
    args = parser.parse_args()
    path = ROOT / "src/WordClock.cpp"
    current = path.read_text()
    candidate = prepared(current)
    verify_baselines(candidate)
    verify_output_promotions(candidate)
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
    print("PASS: state-only source contract, exact output promotions and call-site host test")

if __name__ == "__main__":
    main()
