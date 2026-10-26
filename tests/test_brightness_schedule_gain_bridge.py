#!/usr/bin/env python3
"""Actual binding/cache/sink tests with transport/color mocks, not hardware parity.
No application hooks are staged and neither production gate is enabled.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
COLORS = r'''#pragma once
#include <stdint.h>
#include <stddef.h>
struct RgbwColor;
struct RgbColor {
    uint8_t R,G,B;
    RgbColor(uint8_t v=0):R(v),G(v),B(v){}
    RgbColor(uint8_t r,uint8_t g,uint8_t b):R(r),G(g),B(b){}
    RgbColor(const RgbwColor &);
};
struct RgbwColor {
    uint8_t R,G,B,W;
    RgbwColor(uint8_t v=0):R(v),G(v),B(v),W(0){}
    RgbwColor(uint8_t r,uint8_t g,uint8_t b,uint8_t w):R(r),G(g),B(b),W(w){}
};
inline RgbColor::RgbColor(const RgbwColor &p):R(p.R),G(p.G),B(p.B){}
'''
INTERFACE = r'''#pragma once
#include "NeoPixelBus.h"
// Minimal transport interface; existing adapter suites cover actual adapters.
class LedStripInterface {
public:
    virtual ~LedStripInterface() = default;
    virtual bool isVirtual() const = 0;
    virtual void setRgbwPixel(uint16_t,RgbwColor) = 0;
    virtual void show() = 0;
};
'''
CPP = r'''#include "BrightnessScheduleRendererBinding.h"
#if WORDCLOCK_ENABLE_RENDERER_CACHE
#include <cassert>
#include <initializer_list>
struct Strip : LedStripInterface {
    RgbwColor pixels[1200] = {};
    size_t count; bool virt, white; unsigned shows=0;
    Strip(size_t n,bool v,bool w):count(n),virt(v),white(w){}
    bool isVirtual() const override { return virt; }
    void setRgbwPixel(uint16_t i,RgbwColor p) override {
        assert(i<count); if(!white)p.W=0; pixels[i]=p;
    }
    void show() override { ++shows; }
};
static uint8_t scale(uint8_t v,uint16_t g) { return (uint32_t(v)*g+5000)/10000; }
static void output(const Strip &s,RgbwColor p,uint16_t gain) {
    const auto q=s.pixels[0];
    assert(q.R==scale(p.R,gain)&&q.G==scale(p.G,gain));
    assert(q.B==scale(p.B,gain)&&q.W==(s.white?scale(p.W,gain):0));
}
int main() {
    for(size_t n:{300,600,900,1200}) for(unsigned mode:{0,1,2}) {
        brightnessScheduleBinding::Binding binding;
        Strip strip(n,mode!=2,mode!=0), other(n,true,true);
        const RgbwColor a(201,103,51,127), b(17,33,65,129), zero(0);
        assert(!binding.attach(nullptr,n,true));
        assert(!binding.attach(&strip,0,true)&&!binding.attach(&strip,1201,true));
#if WORDCLOCK_ENABLE_SCHEDULE_OUTPUT
        assert(!binding.adoptGain(5000)&&!binding.repaint());
#endif
        assert(binding.attach(&strip,n,strip.white)&&binding.ready(&strip));
        assert(strip.shows==0);
        assert(!binding.attach(&other,n,true)&&!binding.retire(&other));
        assert(binding.capture(0,a));
        assert(!binding.capture(n,a)&&!binding.clear(n));
        assert(binding.read(0).R==a.R);
#if WORDCLOCK_ENABLE_SCHEDULE_OUTPUT
        assert(!binding.repaint()&&strip.shows==0);
        binding.show(); output(strip,a,0); // Fail-dark before adoption.
        assert(binding.adoptGain(10000)&&binding.repaint());
        output(strip,a,10000);
#else
        binding.show(); output(strip,a,10000); // Reference remains full gain.
#endif
        assert(binding.attach(&strip,n,strip.white)); // Reuse preserves gain/staging.
        assert(binding.capture(0,b)&&binding.read(0).R==b.R);
#if WORDCLOCK_ENABLE_SCHEDULE_OUTPUT
        for(uint16_t gain:{5000,0,10000}) {
            assert(binding.adoptGain(gain)&&binding.repaint());
            output(strip,a,gain); assert(binding.read(0).R==b.R);
            const unsigned shows=strip.shows;
            assert(!binding.adoptGain(gain)&&!binding.repaint());
            assert(strip.shows==shows);
        }
        assert(!binding.adoptGain(65535)&&!binding.repaint()); // Clamp at full gain.
#endif
        binding.show(); output(strip,b,10000);
        const unsigned shows=strip.shows;
        binding.show(); assert(strip.shows==shows+1);
        assert(binding.clear(0)&&binding.read(0).R==0);
#if WORDCLOCK_ENABLE_SCHEDULE_OUTPUT
        assert(binding.adoptGain(5000)&&binding.repaint()); output(strip,b,5000);
        binding.show(); output(strip,zero,5000);
        assert(binding.adoptGain(10000)&&binding.repaint()); output(strip,zero,10000);
#else
        binding.show(); output(strip,zero,10000);
#endif
        assert(binding.retire(&strip)&&!binding.ready(&strip)); output(strip,zero,10000);
#if WORDCLOCK_ENABLE_SCHEDULE_OUTPUT
        assert(!binding.adoptGain(10000)&&!binding.repaint());
#endif
        assert(binding.attach(&other,n,true)&&binding.capture(0,a));
        binding.show();
        output(other,a,WORDCLOCK_ENABLE_SCHEDULE_OUTPUT?0:10000);
        assert(binding.retire(&other));
    }
}
#else
int main() {}
#endif
'''

def main():
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ required")
    header = (ROOT / "include/BrightnessScheduleRendererBinding.h").read_text()
    for gate in ("RENDERER_CACHE", "SCHEDULE_OUTPUT"):
        if header.count("#define WORDCLOCK_ENABLE_" + gate + " 0") != 1:
            raise SystemExit("Production gate must remain default-off: " + gate)
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        for name in ("BrightnessScheduleRendererBinding.h", "BrightnessScheduleRendererCache.h",
                     "BrightnessScheduleOutputBuffer.h", "BrightnessScheduleRuntimeModel.h",
                     "BrightnessSchedule.h", "BrightnessScheduleStripSink.h"):
            shutil.copyfile(ROOT / "include" / name, work / name)
        for name, text in {"NeoPixelBus.h": COLORS, "LedStripInterface.h": INTERFACE,
                           "test.cpp": CPP}.items():
            (work / name).write_text(text)
        def build(cache, schedule, esp32=True, extra="", valid=True):
            source = work / "test.cpp"
            if extra:
                source = work / "invalid-api.cpp"
                source.write_text('#include "BrightnessScheduleRendererBinding.h"\n' + extra)
            binary = work / "test"
            command = [compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                       "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all",
                       "-DWORDCLOCK_ENABLE_RENDERER_CACHE=" + str(cache),
                       "-DWORDCLOCK_ENABLE_SCHEDULE_OUTPUT=" + str(schedule)]
            if esp32:
                command.append("-DESP32")
            result = subprocess.run(command + ["-I", str(work), str(source), "-o", str(binary)],
                                    capture_output=True, text=True)
            if valid:
                if result.returncode:
                    raise SystemExit(result.stderr)
                subprocess.run([str(binary)], check=True)
            elif not result.returncode:
                raise SystemExit("Unsupported gate/API combination compiled")
        for cache, schedule, esp32 in ((0,0,False),(0,0,True),(1,0,True),(1,1,True)):
            build(cache,schedule,esp32)
        for cache, schedule, esp32 in ((0,1,True),(2,0,True),(1,2,True),(1,1,False)):
            build(cache,schedule,esp32,valid=False)
        build(1,0,extra='int main(){ brightnessScheduleBinding::Binding b; b.adoptGain(1); }',valid=False)
        build(1,0,extra='int main(){ brightnessScheduleBinding::Binding b; b.repaint(); }',valid=False)
    print("PASS: 24 binding/cache cases, four supported builds, six rejected gate/API combinations")

if __name__ == "__main__":
    main()
