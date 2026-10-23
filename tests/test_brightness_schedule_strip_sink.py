#!/usr/bin/env python3
"""Compile actual adapter sources with a mock bus; not real GPIO/library validation."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
MOCK = '#pragma once\n#include <stdint.h>\n#include <stddef.h>\n#include <vector>\n#include <cassert>\nextern unsigned hsbConversions;\nstruct HsbColor { explicit HsbColor(float) {} };\nstruct RgbwColor;\nstruct RgbColor {\n uint8_t R,G,B;\n RgbColor(uint8_t n=0):R(n),G(n),B(n){}\n RgbColor(uint8_t r,uint8_t g,uint8_t b):R(r),G(g),B(b){}\n RgbColor(HsbColor):R(1),G(2),B(3){++hsbConversions;}\n RgbColor(const RgbwColor&);\n};\nstruct RgbwColor {\n uint8_t R,G,B,W;\n RgbwColor(uint8_t n=0):R(n),G(n),B(n),W(0){}\n RgbwColor(uint8_t r,uint8_t g,uint8_t b,uint8_t w):R(r),G(g),B(b),W(w){}\n};\ninline RgbColor::RgbColor(const RgbwColor &p):R(p.R),G(p.G),B(p.B){}\nstruct NeoGrbwFeature {using ColorObject=RgbwColor;};\nstruct MockMethod {};\ntemplate<class Feature,class Method> class NeoPixelBus {\npublic:\n using Color=typename Feature::ColorObject;\n static NeoPixelBus *last;\n std::vector<Color> pixels;unsigned begins=0,shows=0,writes=0;\n explicit NeoPixelBus(uint16_t n):pixels(n){last=this;}\n NeoPixelBus(uint16_t n,uint8_t):pixels(n){last=this;}\n void Begin(){++begins;}\n void SetPixelColor(uint16_t i,Color p){assert(i<pixels.size());pixels[i]=p;++writes;}\n Color GetPixelColor(uint16_t i){assert(i<pixels.size());return pixels[i];}\n void Show(){++shows;}\n};\ntemplate<class F,class M> NeoPixelBus<F,M>*NeoPixelBus<F,M>::last=nullptr;\n'

def main():
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ required for strip sink tests")
    names = ("BrightnessScheduleStripSink.h", "BrightnessScheduleOutputBuffer.h",
             "BrightnessScheduleRuntimeModel.h", "BrightnessSchedule.h",
             "LedStripInterface.h", "NeoPixelBusLedStripAdapter.h",
             "VirtualLedStripAdapter.h", "LedStatusPrefix.h")
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        for name in names:
            shutil.copyfile(ROOT / "include" / name, work / name)
        mocks = {
            "NeoPixelBus.h": MOCK,
            "NeoMultiFeature.hpp": '#pragma once\n#include "NeoPixelBus.h"\nstruct NeoMultiFeature {using ColorObject=RgbColor;};\n',
            "Arduino.h": "#pragma once\n#include <stdint.h>\n",
            "WordClockState.h": "#pragma once\n",
        }
        for name, content in mocks.items():
            (work / name).write_text(content)
        shutil.copyfile(ROOT / "tests/brightness_schedule_strip_sink_test.cpp", work / "test.cpp")
        for prefix in (0, 1):
            binary = work / ("sink-" + str(prefix))
            subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all",
                            "-DWORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL=" + str(prefix),
                            "-I", str(work), str(work / "test.cpp"), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
    print("PASS: dormant strip sink; physical-adapter mock bus and virtual backend, prefix off/on")

if __name__ == "__main__":
    main()
