#include "BrightnessScheduleRendererCache.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>
using brightnessScheduleRenderer::PixelMode;
struct Sink {
    brightnessScheduleOutput::Pixel pixel{};
    void writePixel(size_t i, brightnessScheduleOutput::Pixel p) { assert(i == 0); pixel = p; }
    void show() {}
};
// The runner appends the project's unchanged RGB-to-RGBW conversion here.
/*NATIVE_CONVERSION*/
static void same(RgbColor a, RgbColor b) { assert(a.R==b.R && a.G==b.G && a.B==b.B); }
static uint8_t scaled(uint8_t value, uint16_t gain) { return (uint32_t(value)*gain+5000)/10000; }
int main() {
    unsigned cases=0;
    for (float h : {0.f,.1f,.25f,.5f,.75f,.9999f})
    for (float s : {0.f,.5f,1.f})
    for (float b : {0.f,.01f,.5f,1.f})
    for (unsigned white=0;white<3;++white)
    for (auto mode : {PixelMode::Rgb,PixelMode::VirtualRgbw,PixelMode::PhysicalRgbw}) {
        const RgbColor rgb(HsbColor(h,s,b));
        const RgbwColor native=mode==PixelMode::Rgb ? RgbwColor(rgb.R,rgb.G,rgb.B,0)
            : convertRgbToRgbw(rgb,static_cast<WhiteType>(white));
        const RgbColor expected=mode==PixelMode::PhysicalRgbw ? RgbColor(native)
            : RgbColor(native.R,native.G,native.B);
        brightnessScheduleRenderer::Cache<1> cache; Sink sink;
        assert(cache.configure(1,mode)); assert(cache.capture(0,native));
        same(cache.read(0),expected);
        for (uint16_t gain : {10000,5000,0,10000}) {
            cache.setGain(gain); cache.show(sink);
            same(cache.read(0),expected);
            assert(sink.pixel.r==scaled(native.R,gain));
            assert(sink.pixel.g==scaled(native.G,gain));
            assert(sink.pixel.b==scaled(native.B,gain));
            assert(sink.pixel.w==scaled(native.W,gain));
        }
        assert(cache.clear(0)); same(cache.read(0),RgbColor(0)); cache.show(sink);
        assert(!(sink.pixel.r||sink.pixel.g||sink.pixel.b||sink.pixel.w));
        ++cases;
    }
    assert(cases==648);
    std::printf("PASS: %u real-library color/cache cases; no LED bus or driver constructed\n",cases);
}
