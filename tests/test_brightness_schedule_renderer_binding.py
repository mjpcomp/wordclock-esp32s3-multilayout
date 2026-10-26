#!/usr/bin/env python3
"""Stage reviewed full-gain binding; preserve exact installed output promotions.
Mock colors; virtual backends; not full firmware or physical/library parity.
--stage-binding stages only remaining reviewed changes in a disposable checkout.
"""
from pathlib import Path
import argparse
import json
import re
import runpy
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "docs/patches/brightness-renderer-binding.patch"
TARGETS = ("src/Led.cpp", "src/WordClock.cpp", "include/ClockWorkLedFactory.hpp")

def output_rules():
    return json.loads((ROOT / "docs/patches/brightness-schedule-output.json").read_text())["replacements"]

def output_canonical(path, text):
    if path not in ("src/Led.cpp", "src/WordClock.cpp"): return text
    normalize = runpy.run_path(str(ROOT / "tests/test_brightness_schedule_output_candidate.py"))["normalize_promoted"]
    return normalize(text, path, output_rules())

def patch_sections():
    text = PATCH.read_text()
    sections = [s for s in re.split(r"(?=^--- a/)", text, flags=re.M) if s]
    paths = []
    for section in sections:
        match = re.match(r"--- a/([^\n]+)\n\+\+\+ b/([^\n]+)\n", section)
        if not match or match.group(1) != match.group(2):
            raise ValueError("unexpected patch header")
        paths.append(match.group(1))
    if tuple(paths) != TARGETS:
        raise ValueError("unexpected patch targets/order")
    return sections

def git_patch(root, section, reverse=False, check=False):
    command = ["git", "apply"]
    if reverse: command.append("--reverse")
    if check: command.append("--check")
    return subprocess.run(command, input=section, text=True, cwd=root,
                          capture_output=True)

def binding_state(root, path, section):
    original = (root / path).read_text()
    canonical = output_canonical(path, original)
    if canonical != original:
        # Probe only a temporary view. Never erase installed output code.
        with tempfile.TemporaryDirectory() as d:
            probe = Path(d)
            target = probe / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(canonical)
            forward = git_patch(probe, section, check=True).returncode == 0
            reverse = git_patch(probe, section, reverse=True, check=True).returncode == 0
        if forward or not reverse:
            raise ValueError("output promotion requires installed renderer hooks: " + path)
        return False, True
    return (git_patch(root, section, check=True).returncode == 0,
            git_patch(root, section, reverse=True, check=True).returncode == 0)

def apply_patch(root):
    pending = []
    for path, section in zip(TARGETS, patch_sections()):
        forward, reverse = binding_state(root, path, section)
        if forward == reverse:
            raise ValueError("binding patch drift or ambiguity: " + path)
        if forward: pending.append(section)
    # Preflight every file before changing any. Not an I/O-atomic transaction.
    for section in pending:
        result = git_patch(root, section)
        if result.returncode:
            raise RuntimeError(result.stderr)
    return len(pending)

def verify_promotions(work):
    sections = patch_sections()
    full = {p: (work / p).read_bytes() for p in TARGETS}
    for section in sections:
        result = git_patch(work, section, reverse=True)
        if result.returncode: raise RuntimeError(result.stderr)
    base = {p: (work / p).read_bytes() for p in TARGETS}
    for mask in range(8):
        for p, data in base.items(): (work / p).write_bytes(data)
        for i, section in enumerate(sections):
            if mask & (1 << i):
                result = git_patch(work, section)
                if result.returncode: raise RuntimeError(result.stderr)
        assert apply_patch(work) == 3 - bin(mask).count("1")
        assert {p: (work / p).read_bytes() for p in TARGETS} == full
        assert apply_patch(work) == 0
        assert {p: (work / p).read_bytes() for p in TARGETS} == full
    # Later-file drift must be rejected BEFORE applying an earlier pending file.
    for p, data in base.items(): (work / p).write_bytes(data)
    path = work / "src/WordClock.cpp"
    before = path.read_text()
    if before.count("void deleteActiveLedStrip()") != 1:
        raise ValueError("retirement signature drift")
    path.write_text(before.replace("void deleteActiveLedStrip()", "void driftedDelete()"))
    snapshot = {p: (work / p).read_bytes() for p in TARGETS}
    try:
        apply_patch(work)
    except ValueError:
        pass
    else:
        raise AssertionError("unexpected source drift accepted")
    assert {p: (work / p).read_bytes() for p in TARGETS} == snapshot
    for p, data in full.items(): (work / p).write_bytes(data)

def verify_output_promotions(work):
    full = {p: (work / p).read_bytes() for p in TARGETS}
    groups = {p: [item for item in output_rules() if item["path"] == p]
              for p in TARGETS[:2]}
    if not all(groups.values()): raise ValueError("missing output promotion groups")
    for mask in range(4):
        for p, data in full.items(): (work / p).write_bytes(data)
        for i, path in enumerate(TARGETS[:2]):
            if not mask & (1 << i): continue
            text = (work / path).read_text()
            for item in groups[path]:
                if text.count(item["old"]) != 1: raise ValueError("output anchor drift: " + path)
                text = text.replace(item["old"], item["new"], 1)
            (work / path).write_text(text)
        snapshot = {p: (work / p).read_bytes() for p in TARGETS}
        assert apply_patch(work) == 0
        assert {p: (work / p).read_bytes() for p in TARGETS} == snapshot
        assert apply_patch(work) == 0
        assert {p: (work / p).read_bytes() for p in TARGETS} == snapshot
        assert {p: output_canonical(p, (work / p).read_text()).encode()
                for p in TARGETS} == full
    # A corrupted output helper must fail without modifying any file.
    path = work / "src/WordClock.cpp"
    text = path.read_text()
    altered = text.replace("owner.current()", "owner.unreviewedCurrent()", 1)
    assert altered != text
    path.write_text(altered)
    snapshot = {p: (work / p).read_bytes() for p in TARGETS}
    try:
        apply_patch(work)
    except ValueError:
        pass
    else:
        raise AssertionError("edited output promotion accepted")
    assert {p: (work / p).read_bytes() for p in TARGETS} == snapshot
    # Preserve preflight behavior with pending Led hooks and promoted WordClock.
    for p, data in full.items(): (work / p).write_bytes(data)
    result = git_patch(work, patch_sections()[0], reverse=True)
    if result.returncode: raise RuntimeError(result.stderr)
    text = (work / "src/WordClock.cpp").read_text()
    for item in groups["src/WordClock.cpp"]:
        if text.count(item["old"]) != 1: raise ValueError("output anchor drift")
        text = text.replace(item["old"], item["new"], 1)
    text = text.replace("#if WORDCLOCK_ENABLE_RENDERER_CACHE", "#if WRONG_RENDERER_GATE", 1)
    (work / "src/WordClock.cpp").write_text(text)
    snapshot = {p: (work / p).read_bytes() for p in TARGETS}
    try:
        apply_patch(work)
    except ValueError:
        pass
    else:
        raise AssertionError("corrupt renderer hooks under output promotion accepted")
    assert {p: (work / p).read_bytes() for p in TARGETS} == snapshot
    for p, data in full.items(): (work / p).write_bytes(data)

def extract(text, signature):
    matches = list(re.finditer(r"^" + signature + r"\s*\{", text, re.M))
    if len(matches) != 1:
        raise ValueError("signature drift: " + signature)
    match = matches[0]
    pos, depth = match.end(), 1
    while depth and pos < len(text):
        if text[pos] == "{": depth += 1
        elif text[pos] == "}": depth -= 1
        pos += 1
    if depth: raise ValueError("unbalanced method")
    return text[match.start():pos]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-binding", action="store_true")
    parser.add_argument("--gate", choices=("0", "1"), default="0")
    args = parser.parse_args()
    if args.stage_binding:
        apply_patch(ROOT)
        path = ROOT / "include/BrightnessScheduleRendererBinding.h"
        text = path.read_text()
        old = "#define WORDCLOCK_ENABLE_RENDERER_CACHE 0"
        if text.count(old) != 1: raise ValueError("default gate drift")
        path.write_text(text.replace(old, "#define WORDCLOCK_ENABLE_RENDERER_CACHE " + args.gate))
        return
    compiler = shutil.which("g++")
    if not compiler: raise SystemExit("g++ required")
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        for p in TARGETS:
            target = work / p
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(output_canonical(p, (ROOT / p).read_text()))
        apply_patch(work)
        verify_promotions(work)
        verify_output_promotions(work)
        led = (work / "src/Led.cpp").read_text()
        wc = (work / "src/WordClock.cpp").read_text()
        start = led.index("const uint8_t whiteAdjR[3]")
        conversion = led[start:led.index("} // namespace", start)]
        bodies = [extract(led, s) for s in (r"void Led::setPixel\(uint16_t ledIndex, HsbColor color\)", r"RgbColor Led::getPixel\(uint16_t i\)", r"void Led::clearPixel\(uint16_t i\)", r"void Led::show\(\)")]
        bodies.append(extract(wc, r"void deleteActiveLedStrip\(\)"))
        (work / "extracted.inc").write_text(conversion + "\n" + "\n".join(bodies))
        for name in ("BrightnessScheduleRendererBinding.h", "BrightnessScheduleRendererCache.h", "BrightnessScheduleOutputBuffer.h", "BrightnessScheduleRuntimeModel.h", "BrightnessSchedule.h", "BrightnessScheduleStripSink.h", "LedStripInterface.h", "VirtualLedStripAdapter.h", "ClockTestPolicy.h", "LedStatusPrefix.h"):
            shutil.copyfile(ROOT / "include" / name, work / name)
        shutil.copyfile(work / "include/ClockWorkLedFactory.hpp", work / "ClockWorkLedFactory.hpp")
        for name, text in {"test.cpp": CPP, "NeoPixelBus.h": MOCK, "Arduino.h": "#pragma once\n#include <stdint.h>\n", "WordClockState.h": "#pragma once\n"}.items():
            (work / name).write_text(text)
        for gate in (0, 1):
            for mode in (1, 2):
                exe = work / ("binding-" + str(gate) + "-" + str(mode))
                subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all", "-DESP32", "-DWORDCLOCK_TEST_MODE=" + str(mode), "-DWORDCLOCK_ENABLE_RENDERER_CACHE=" + str(gate), "-I", str(work), str(work / "test.cpp"), "-o", str(exe)], check=True)
                subprocess.run([str(exe)], check=True)
    print("PASS: eight renderer states, four output states, drift rejection; full-gain binding gate off/on, both isolated modes, three counts and RGB/RGBW")

CPP = '#include <algorithm>\n#include <cassert>\n#include <initializer_list>\n#include "ClockTestPolicy.h"\n#include "LedStripInterface.h"\n#include "BrightnessScheduleRendererBinding.h"\nusing std::min;\nconstexpr uint16_t MAX_LED_COUNT=300;\nconstexpr uint8_t Grbw=4;\nenum WhiteType{Warm,Neutral,Cool};\nstruct{uint8_t buildTypeDef=1;struct{uint8_t led=3;}hardwarePins;WhiteType wType=Warm;uint8_t Colortype=0;}G;\nuint8_t getLedsPerLetter(uint8_t n){return n;}\nstruct NeoMultiFeature{static void setColortype(uint8_t){}};\nunsigned failures=0;\nstruct SerialMock{void println(const char*){++failures;}};SerialMock Serial;\nnamespace prefixStatusRuntime{void resetDisplay(){}}\nnamespace onboardDiagnosticApplication{void resetFrames(){}}\nLedStripInterface *activeLedStrip=nullptr;\nuint8_t activeLedPin=UINT8_MAX,activeLedColorType=UINT8_MAX;\nuint16_t activeLedCount=0;\nclass ClockWork{public:void initLedStrip(uint8_t);};\nclass Led{public:void setPixel(uint16_t,HsbColor);RgbColor getPixel(uint16_t);void clearPixel(uint16_t);void show();};\n#include "extracted.inc"\n#include "ClockWorkLedFactory.hpp"\nint main(){ClockWork clock;Led led;\n for(uint8_t copies:{1,2,4})for(uint8_t color:{uint8_t(0),Grbw}){\n  G.buildTypeDef=copies;G.Colortype=color;clock.initLedStrip(color);\n  assert(activeLedStrip&&activeLedStrip->isVirtual());\n  auto *backend=static_cast<VirtualLedStripAdapter*>(activeLedStrip);\n  const unsigned before=backend->diagnostics().showRequests;\n#if WORDCLOCK_ENABLE_RENDERER_CACHE\n  auto &binding=brightnessScheduleBinding::application();\n  assert(binding.ready(backend));\n  assert(!binding.attach(nullptr,300,false));\n  assert(!binding.attach(backend,0,false));\n  assert(!binding.attach(backend,1201,false));\n  VirtualLedStripAdapter other(300);\n  assert(!binding.attach(&other,300,false)&&!binding.retire(&other));\n  assert(binding.ready(backend));\n#endif\n  HsbColor colorValue(.8f,.6f,.2f);RgbColor rgb(colorValue);\n  const RgbwColor expected=color==Grbw?convertRgbToRgbw(rgb,G.wType):RgbwColor(rgb.R,rgb.G,rgb.B,0);\n  led.setPixel(0,colorValue);\n  RgbColor staged=led.getPixel(0);\n  assert(staged.R==expected.R&&staged.G==expected.G&&staged.B==expected.B);\n  clock.initLedStrip(color); // Reuse must preserve the staged cache.\n  assert(activeLedStrip==backend&&backend->diagnostics().showRequests==before);\n  assert(led.getPixel(0).R==expected.R);\n#if WORDCLOCK_ENABLE_RENDERER_CACHE\n  assert(backend->getRgbwPixel(0).R==0);\n#endif\n  led.show();const auto out=backend->getRgbwPixel(0);\n  assert(out.R==expected.R&&out.G==expected.G&&out.B==expected.B&&out.W==expected.W);\n  const unsigned shows=backend->diagnostics().showRequests;\n  led.show();assert(backend->diagnostics().showRequests==shows+1);\n  led.clearPixel(0);assert(led.getPixel(0).R==0);led.show();\n  assert(backend->getRgbwPixel(0).R==0&&backend->getRgbwPixel(0).W==0);\n }\n deleteActiveLedStrip();assert(!activeLedStrip&&failures==0);\n#if WORDCLOCK_ENABLE_RENDERER_CACHE\n auto &binding=brightnessScheduleBinding::application();\n VirtualLedStripAdapter last(300,true);\n assert(binding.attach(&last,300,true));\n assert(binding.capture(0,RgbwColor(12,24,36,48)));binding.show();\n assert(last.getRgbwPixel(0).W==48);\n assert(binding.retire(&last)&&!binding.ready(&last));\n assert(last.getRgbwPixel(0).R==0&&last.getRgbwPixel(0).W==0);\n#endif\n}\n'
MOCK = '#pragma once\n#include <stdint.h>\n#include <stddef.h>\n#include <cmath>\n// Transport mock, not real HSB or RGBW color-library validation.\nstruct HsbColor{float H,S,B;HsbColor(float h=0,float s=0,float b=0):H(h),S(s),B(b){}};\nstruct RgbwColor;\nstruct RgbColor{uint8_t R,G,B;RgbColor(uint8_t n=0):R(n),G(n),B(n){}RgbColor(uint8_t r,uint8_t g,uint8_t b):R(r),G(g),B(b){}RgbColor(HsbColor c):R(std::lround(c.H*255)),G(std::lround(c.S*255)),B(std::lround(c.B*255)){}RgbColor(const RgbwColor&);};\nstruct RgbwColor{uint8_t R,G,B,W;RgbwColor(uint8_t n=0):R(n),G(n),B(n),W(0){}RgbwColor(uint8_t r,uint8_t g,uint8_t b,uint8_t w):R(r),G(g),B(b),W(w){}};\ninline RgbColor::RgbColor(const RgbwColor &p):R(p.R),G(p.G),B(p.B){}\n'

if __name__ == "__main__":
    main()
