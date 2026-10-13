#!/usr/bin/env python3
"""Test production adapters with mocked platform/NeoPixelBus dependencies.
Run from the repo: python tests/test_status_prefix.py (requires g++).
This is not a firmware, timing, electrical, or real-library compatibility test.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

MOCK = r"""#pragma once
#include <cassert>
#include <cstdint>
#include <vector>
struct HsbColor { uint8_t value; explicit HsbColor(uint8_t v) : value(v) {} };
struct RgbwColor;
struct RgbColor {
    uint8_t R, G, B;
    RgbColor(uint8_t v = 0) : R(v), G(v), B(v) {}
    RgbColor(uint8_t r, uint8_t g, uint8_t b) : R(r), G(g), B(b) {}
    RgbColor(HsbColor c) : R(c.value), G(c.value), B(c.value) {}
    RgbColor(const RgbwColor &c);
};
struct RgbwColor {
    uint8_t R, G, B, W;
    RgbwColor(uint8_t v = 0) : R(v), G(v), B(v), W(v) {}
    RgbwColor(uint8_t r, uint8_t g, uint8_t b, uint8_t w) : R(r), G(g), B(b), W(w) {}
};
inline RgbColor::RgbColor(const RgbwColor &c) : R(c.R), G(c.G), B(c.B) {}
struct NeoMultiFeature { using ColorObject = RgbColor; };
struct NeoGrbwFeature { using ColorObject = RgbwColor; };
template<class Feature, class Method> class NeoPixelBus {
public:
    using Color = typename Feature::ColorObject;
    static NeoPixelBus *last;
    std::vector<Color> pixels;
    unsigned shows = 0;
    uint8_t pin = 255;
    NeoPixelBus(uint16_t n) : pixels(n) { last = this; }
    NeoPixelBus(uint16_t n, uint8_t p) : pixels(n), pin(p) { last = this; }
    void Begin() {}
    void SetPixelColor(uint16_t i, Color c) { assert(i < pixels.size()); pixels[i] = c; }
    Color GetPixelColor(uint16_t i) { assert(i < pixels.size()); return pixels[i]; }
    void Show() { ++shows; }
};
template<class F, class M> NeoPixelBus<F, M> *NeoPixelBus<F, M>::last = nullptr;
"""
TEST = r"""#include "NeoPixelBusLedStripAdapter.h"
#include <cassert>
#include <memory>
#include <type_traits>
struct Method {};
static unsigned white(const RgbColor &) { return 0; }
static unsigned white(const RgbwColor &c) { return c.W; }
template<class Adapter, class Feature> void check(uint16_t n, bool withPin) {
    std::unique_ptr<Adapter> a(withPin ? new Adapter(n, 5) : new Adapter(n));
    auto *bus = NeoPixelBus<Feature, Method>::last;
    assert(bus->pixels.size() == unsigned(n) + ledPrefix::COUNT);
    if (withPin) assert(bus->pin == 5);
    if (ledPrefix::COUNT) assert(bus->pixels[0].R == 0);
    assert(a->setStatusPixel(RgbColor(7, 8, 9)) == bool(ledPrefix::COUNT));
    for (uint16_t i = 0; i < n; ++i) {
        a->setRgbPixel(i, HsbColor(uint8_t(i % 200 + 1)));
        assert(a->getPixel(i).R == uint8_t(i % 200 + 1));
        assert(bus->pixels[i + ledPrefix::COUNT].R == uint8_t(i % 200 + 1));
    }
    if (!ledPrefix::COUNT && n) assert(bus->pixels[0].R == 1);
    a->setRgbPixel(n, HsbColor(42));
    a->setRgbwPixel(n, RgbwColor(42));
    a->clearPixel(n);
    a->clearPixel(UINT16_MAX);
    assert(a->getPixel(n).R == 0);
    if (n) {
        a->setRgbwPixel(n - 1, RgbwColor(11, 12, 13, 14));
        assert(a->getPixel(n - 1).R == 11);
        assert(white(bus->pixels[n - 1 + ledPrefix::COUNT]) ==
               (std::is_same<Feature, NeoGrbwFeature>::value ? 14U : 0U));
    }
    for (uint16_t i = 0; i < n; ++i) a->clearPixel(i);
    for (uint16_t i = 0; i < n; ++i) assert(a->getPixel(i).R == 0);
    if (ledPrefix::COUNT) assert(bus->pixels[0].R == 7 && bus->pixels[0].G == 8);
    auto shows = bus->shows;
    a->show();
    assert(bus->shows == shows + 1);
    if (ledPrefix::COUNT) {
        assert(a->setStatusPixel(RgbColor(9, 8, 7)));
        a->show();
        assert(bus->pixels[0].R == 9 && bus->shows == shows + 2);
    }
}
int main() {
    static_assert(ledPrefix::COUNT == TEST_EXPECT_PREFIX_COUNT, "default/configuration regression");
    for (auto n : {0, 1, 114, 300}) for (bool pin : {false, true}) {
        check<RgbLedStripAdapter<Method>, NeoMultiFeature>(n, pin);
        check<RgbwLedStripAdapter<Method>, NeoGrbwFeature>(n, pin);
    }
    assert(ledPrefix::physicalIndex(110) == 110 + ledPrefix::COUNT);
    assert(ledPrefix::physicalIndex(113) == 113 + ledPrefix::COUNT);
}
"""

def main():
    compiler = shutil.which('g++')
    if not compiler:
        raise SystemExit('g++ is required for this host test.')
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        for name in ('LedStatusPrefix.h', 'LedStripInterface.h', 'NeoPixelBusLedStripAdapter.h'):
            shutil.copyfile(ROOT / 'include' / name, work / name)
        stubs = {'Arduino.h': '#pragma once\n#include <stdint.h>\n',
                 'WordClockState.h': '#pragma once\n',
                 'NeoMultiFeature.hpp': '#pragma once\n#include "NeoPixelBus.h"\n',
                 'NeoPixelBus.h': MOCK, 'test.cpp': TEST}
        for name, content in stubs.items():
            (work / name).write_text(content)
        for mode in (None, 0, 1):
            exe = work / ('test-' + str(mode))
            expected = 0 if mode is None else mode
            args = [compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=undefined,bounds', '-DTEST_EXPECT_PREFIX_COUNT=' + str(expected),
                    '-I' + str(work), str(work / 'test.cpp'), '-o', str(exe)]
            if mode is not None:
                args.insert(1, '-DWORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL=' + str(mode))
            subprocess.run(args, check=True)
            subprocess.run([str(exe)], check=True)
        bad = subprocess.run([compiler, '-std=c++11', '-DTEST_EXPECT_PREFIX_COUNT=0',
            '-DWORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL=2', '-I' + str(work),
            '-c', str(work / 'test.cpp'), '-o', str(work / 'bad.o')],
            capture_output=True, text=True)
        if bad.returncode == 0 or 'must be 0 or 1' not in bad.stderr:
            raise AssertionError('Expected invalid-flag diagnostic was not emitted.')
    print('PASS: default OFF, explicit 0/1, RGB/RGBW, counts, constructors, mapping, clears, bounds, status and show.')

if __name__ == '__main__':
    main()
