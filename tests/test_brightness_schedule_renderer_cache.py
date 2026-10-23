#!/usr/bin/env python3
"""Dormant cache tests. Mock colors test routing, NOT real library color parity."""
from pathlib import Path
import shutil
import subprocess
import tempfile
from test_brightness_schedule_strip_sink import MOCK
ROOT = Path(__file__).resolve().parents[1]

def main():
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ required for renderer cache tests")
    old = "inline RgbColor::RgbColor(const RgbwColor &p):R(p.R),G(p.G),B(p.B){}"
    new = "extern unsigned rgbwReadConversions;\ninline RgbColor::RgbColor(const RgbwColor &p):R(p.R),G(p.G),B(p.B){++rgbwReadConversions;}"
    if MOCK.count(old) != 1:
        raise SystemExit("mock conversion changed: review cache routing instrumentation")
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        for name in ("BrightnessScheduleRendererCache.h", "BrightnessScheduleOutputBuffer.h",
                     "BrightnessScheduleRuntimeModel.h", "BrightnessSchedule.h"):
            shutil.copyfile(ROOT / "include" / name, work / name)
        (work / "NeoPixelBus.h").write_text(MOCK.replace(old, new))
        shutil.copyfile(ROOT / "tests/brightness_schedule_renderer_cache_test.cpp", work / "test.cpp")
        binary = work / "cache-test"
        subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all",
                        "-I", str(work), str(work / "test.cpp"), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print("PASS: 12 dormant renderer-cache configurations; mock routing, not live renderer validation")

if __name__ == "__main__":
    main()
