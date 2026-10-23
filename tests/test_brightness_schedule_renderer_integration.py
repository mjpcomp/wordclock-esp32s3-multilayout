#!/usr/bin/env python3
"""Selected real Led/transition bodies + real EN10x11 mapping; mock colors/backends.
Not full firmware, real HSB/RGBW library parity, factory wiring or all layouts.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
SIGNATURES = (
    r"void Led::setPixel\(uint16_t ledIndex, HsbColor color\)",
    r"void Led::setPixel\(uint8_t row, uint8_t col, HsbColor color\)",
    r"RgbColor Led::getPixel\(uint16_t i\)",
    r"void Led::clearPixel\(uint16_t i\)",
    r"void Led::clearPixel\(uint8_t row, uint8_t col\)",
    r"void Led::show\(\)",
    r"void Led::setbyMinuteArray\(ColorPosition colorPosition\)",
    r"void Led::setbySecondArray\(ColorPosition colorPosition\)",
)

def extract(text, signature):
    matches = list(re.finditer(r"^" + signature + r"\s*\{", text, re.M))
    if len(matches) != 1:
        raise ValueError("method signature drift: " + signature)
    match = matches[0]
    pos, depth = match.end(), 1
    while depth and pos < len(text):
        if text[pos] == "{": depth += 1
        elif text[pos] == "}": depth -= 1
        pos += 1
    if depth:
        raise ValueError("unbalanced method: " + signature)
    return text[match.start():pos]

def main():
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ required")
    led = (ROOT / "src/Led.cpp").read_text()
    transition = (ROOT / "include/TransitionTypes/Transition.hpp").read_text()
    begin = led.index("const uint8_t whiteAdjR[3]")
    end = led.index("} // namespace", begin)
    native_conversion = led[begin:end]
    bodies = [extract(led, s) for s in SIGNATURES]
    bodies.append(extract(transition, r"void Transition::analyzeColors\(RgbfColor \*\*dest, RgbfColor \*\*source,\s*RgbfColor &foreground, RgbfColor &background\)"))
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        for name in ("BrightnessScheduleRendererCache.h", "BrightnessScheduleOutputBuffer.h", "BrightnessScheduleRuntimeModel.h", "BrightnessSchedule.h"):
            shutil.copyfile(ROOT / "include" / name, work / name)
        for name in ("ClockType.hpp", "EN10x11.hpp"):
            shutil.copyfile(ROOT / "include/WordClockTypes" / name, work / name)
        shutil.copyfile(ROOT / "tests/brightness_schedule_renderer_integration_test.cpp", work / "test.cpp")
        (work / "NeoPixelBus.h").write_text(MOCK)
        (work / "extracted.inc").write_text(native_conversion + "\n" + "\n".join(bodies))
        exe = work / "test"
        subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all", "-I", str(work), str(work / "test.cpp"), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("PASS: 48 extracted-renderer/transition cases; real EN10x11 mapping, mock colors/backends")

MOCK = '#pragma once\n#include <stdint.h>\n#include <stddef.h>\n#include <cmath>\n// Test transport encoding only. These are deliberately NOT real HSB conversions.\nstruct HsbColor {float H,S,B;HsbColor(float h=0,float s=0,float b=0):H(h),S(s),B(b){}};\nstruct RgbwColor;\nstruct RgbColor {uint8_t R,G,B;RgbColor(uint8_t n=0):R(n),G(n),B(n){}RgbColor(uint8_t r,uint8_t g,uint8_t b):R(r),G(g),B(b){}RgbColor(HsbColor c):R(std::lround(c.H*255)),G(std::lround(c.S*255)),B(std::lround(c.B*255)){}RgbColor(const RgbwColor&);};\nstruct RgbwColor {uint8_t R,G,B,W;RgbwColor(uint8_t n=0):R(n),G(n),B(n),W(0){}RgbwColor(uint8_t r,uint8_t g,uint8_t b,uint8_t w):R(r),G(g),B(b),W(w){}};\ninline RgbColor::RgbColor(const RgbwColor &p):R(p.R),G(p.G),B(p.B){}\n'

if __name__ == "__main__":
    main()
