#!/usr/bin/env python3
"""Stage reviewed full-gain binding in temporary sources; test real method hooks.
Mock colors; virtual backends; not full firmware or physical/library parity.
--stage-binding applies the candidate to a disposable CI checkout only.
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "docs/patches/brightness-renderer-binding.patch"

def apply_patch(root):
    subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=root, check=True)
    subprocess.run(["git", "apply", str(PATCH)], cwd=root, check=True)

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
        for p in ("src/Led.cpp", "src/WordClock.cpp", "include/ClockWorkLedFactory.hpp"):
            target = work / p
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / p, target)
        apply_patch(work)
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
    print("PASS: full-gain binding gate off/on, both isolated modes, three counts and RGB/RGBW")

CPP = '#include <algorithm>\n#include <cassert>\n#include <initializer_list>\n#include "ClockTestPolicy.h"\n#include "LedStripInterface.h"\n#include "BrightnessScheduleRendererBinding.h"\nusing std::min;\nconstexpr uint16_t MAX_LED_COUNT=300;\nconstexpr uint8_t Grbw=4;\nenum WhiteType{Warm,Neutral,Cool};\nstruct{uint8_t buildTypeDef=1;struct{uint8_t led=3;}hardwarePins;WhiteType wType=Warm;uint8_t Colortype=0;}G;\nuint8_t getLedsPerLetter(uint8_t n){return n;}\nstruct NeoMultiFeature{static void setColortype(uint8_t){}};\nunsigned failures=0;\nstruct SerialMock{void println(const char*){++failures;}};SerialMock Serial;\nnamespace prefixStatusRuntime{void resetDisplay(){}}\nnamespace onboardDiagnosticApplication{void resetFrames(){}}\nLedStripInterface *activeLedStrip=nullptr;\nuint8_t activeLedPin=UINT8_MAX,activeLedColorType=UINT8_MAX;\nuint16_t activeLedCount=0;\nclass ClockWork{public:void initLedStrip(uint8_t);};\nclass Led{public:void setPixel(uint16_t,HsbColor);RgbColor getPixel(uint16_t);void clearPixel(uint16_t);void show();};\n#include "extracted.inc"\n#include "ClockWorkLedFactory.hpp"\nint main(){ClockWork clock;Led led;\n for(uint8_t copies:{1,2,4})for(uint8_t color:{uint8_t(0),Grbw}){\n  G.buildTypeDef=copies;G.Colortype=color;clock.initLedStrip(color);\n  assert(activeLedStrip&&activeLedStrip->isVirtual());\n  auto *backend=static_cast<VirtualLedStripAdapter*>(activeLedStrip);\n  const unsigned before=backend->diagnostics().showRequests;\n#if WORDCLOCK_ENABLE_RENDERER_CACHE\n  auto &binding=brightnessScheduleBinding::application();\n  assert(binding.ready(backend));\n  assert(!binding.attach(nullptr,300,false));\n  assert(!binding.attach(backend,0,false));\n  assert(!binding.attach(backend,1201,false));\n  VirtualLedStripAdapter other(300);\n  assert(!binding.attach(&other,300,false)&&!binding.retire(&other));\n  assert(binding.ready(backend));\n#endif\n  HsbColor colorValue(.8f,.6f,.2f);RgbColor rgb(colorValue);\n  const RgbwColor expected=color==Grbw?convertRgbToRgbw(rgb,G.wType):RgbwColor(rgb.R,rgb.G,rgb.B,0);\n  led.setPixel(0,colorValue);\n  RgbColor staged=led.getPixel(0);\n  assert(staged.R==expected.R&&staged.G==expected.G&&staged.B==expected.B);\n  clock.initLedStrip(color); // Reuse must preserve the staged cache.\n  assert(activeLedStrip==backend&&backend->diagnostics().showRequests==before);\n  assert(led.getPixel(0).R==expected.R);\n#if WORDCLOCK_ENABLE_RENDERER_CACHE\n  assert(backend->getRgbwPixel(0).R==0);\n#endif\n  led.show();const auto out=backend->getRgbwPixel(0);\n  assert(out.R==expected.R&&out.G==expected.G&&out.B==expected.B&&out.W==expected.W);\n  const unsigned shows=backend->diagnostics().showRequests;\n  led.show();assert(backend->diagnostics().showRequests==shows+1);\n  led.clearPixel(0);assert(led.getPixel(0).R==0);led.show();\n  assert(backend->getRgbwPixel(0).R==0&&backend->getRgbwPixel(0).W==0);\n }\n deleteActiveLedStrip();assert(!activeLedStrip&&failures==0);\n#if WORDCLOCK_ENABLE_RENDERER_CACHE\n auto &binding=brightnessScheduleBinding::application();\n VirtualLedStripAdapter last(300,true);\n assert(binding.attach(&last,300,true));\n assert(binding.capture(0,RgbwColor(12,24,36,48)));binding.show();\n assert(last.getRgbwPixel(0).W==48);\n assert(binding.retire(&last)&&!binding.ready(&last));\n assert(last.getRgbwPixel(0).R==0&&last.getRgbwPixel(0).W==0);\n#endif\n}\n'
MOCK = '#pragma once\n#include <stdint.h>\n#include <stddef.h>\n#include <cmath>\n// Transport mock, not real HSB or RGBW color-library validation.\nstruct HsbColor{float H,S,B;HsbColor(float h=0,float s=0,float b=0):H(h),S(s),B(b){}};\nstruct RgbwColor;\nstruct RgbColor{uint8_t R,G,B;RgbColor(uint8_t n=0):R(n),G(n),B(n){}RgbColor(uint8_t r,uint8_t g,uint8_t b):R(r),G(g),B(b){}RgbColor(HsbColor c):R(std::lround(c.H*255)),G(std::lround(c.S*255)),B(std::lround(c.B*255)){}RgbColor(const RgbwColor&);};\nstruct RgbwColor{uint8_t R,G,B,W;RgbwColor(uint8_t n=0):R(n),G(n),B(n),W(0){}RgbwColor(uint8_t r,uint8_t g,uint8_t b,uint8_t w):R(r),G(g),B(b),W(w){}};\ninline RgbColor::RgbColor(const RgbwColor &p):R(p.R),G(p.G),B(p.B){}\n'

if __name__ == "__main__":
    main()
