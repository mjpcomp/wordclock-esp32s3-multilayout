#include "BrightnessScheduleRendererCache.h"
#include <cassert>
#include <initializer_list>
using brightnessScheduleOutput::Pixel;
using brightnessScheduleRenderer::PixelMode;
struct Sink {
    Pixel pixels[1200] = {};
    unsigned writes = 0, shows = 0;
    unsigned char prefix = 0;
    void writePixel(size_t i, Pixel p) { assert(i < 1200); pixels[i] = p; ++writes; }
    void show() { ++shows; }
};
static void same(RgbColor a, RgbColor b) {
    assert(a.R == b.R && a.G == b.G && a.B == b.B);
}
unsigned hsbConversions = 0;
unsigned rgbwReadConversions = 0;
static void exercise(size_t count, PixelMode mode) {
    brightnessScheduleRenderer::Cache<1200> cache;
    Sink sink;
    assert(cache.configure(count, mode) && cache.gain() == 0);
    assert(sink.shows == 0 && sink.writes == 0);
    const RgbwColor original(201, 103, 51, 127);
    assert(cache.capture(0, original));
    const auto logical = cache.logical(0);
    assert(logical.r == 201 && logical.w == (mode == PixelMode::Rgb ? 0 : 127));
    const auto expected = mode == PixelMode::PhysicalRgbw ? RgbColor(original) : RgbColor(201, 103, 51);
    const unsigned conversions = rgbwReadConversions;
    same(cache.read(0), expected); // Staged read: no show or flush occurred.
    assert(rgbwReadConversions == conversions + (mode == PixelMode::PhysicalRgbw ? 1 : 0));
    assert(sink.shows == 0);
    cache.setGain(10000); cache.show(sink);
    assert(sink.shows == 1 && sink.pixels[0].r == 201);
    for (uint16_t gain : {5000, 0, 10000}) {
        const unsigned before = sink.shows;
        assert(cache.setGain(gain) && cache.flush(sink));
        assert(sink.shows == before + 1);
        same(cache.read(0), expected);
        assert(cache.logical(0).r == 201);
        const uint8_t r = gain == 5000 ? 101 : gain == 0 ? 0 : 201;
        assert(sink.pixels[0].r == r);
        assert(!cache.flush(sink));
    }
    unsigned shows = sink.shows;
    assert(!cache.setGain(10000) && !cache.flush(sink));
    sink.prefix = 42; cache.show(sink);
    assert(sink.shows == shows + 1 && sink.prefix == 42);
    // Representative duplicated-letter, minute and frame indices; no geometry
    // mapping or real Led.cpp/Transition execution is claimed by this harness.
    for (size_t index : {size_t(1), size_t(2), count - 2, count - 1})
        assert(cache.capture(index, RgbwColor(12, 24, 36, 48)));
    cache.show(sink);
    for (size_t index : {size_t(1), size_t(2), count - 2, count - 1})
        assert(sink.pixels[index].r == 12);
    cache.clear(0); same(cache.read(0), RgbColor(0));
    cache.show(sink); assert(sink.pixels[0].r == 0);
    cache.setGain(0); cache.flush(sink);
    cache.setGain(10000); cache.flush(sink);
    assert(sink.pixels[0].r == 0); // Explicit clear is not resurrected.
    cache.clearAll(); cache.show(sink);
    for (size_t i = 0; i < count; ++i) assert(sink.pixels[i].r == 0);
    assert(!cache.capture(count, original) && !cache.clear(count));
    same(cache.read(count), RgbColor(0));
    cache.invalidateOutput(); assert(cache.flush(sink));
    assert(cache.configure(count, mode));
    assert(cache.gain() == 0 && cache.logical(0).r == 0);
    assert(!cache.configure(1201, mode) && cache.count() == 0);
    assert(!cache.flush(sink));
}
static uint8_t scaled(uint8_t value, uint16_t gain) {
    return (uint32_t(value) * gain + 5000) / 10000;
}
static void output(Pixel p, RgbwColor native, uint16_t gain, PixelMode mode) {
    assert(p.r == scaled(native.R,gain) && p.g == scaled(native.G,gain));
    assert(p.b == scaled(native.B,gain));
    assert(p.w == (mode == PixelMode::Rgb ? 0 : scaled(native.W,gain)));
}
static void presentation(size_t count, PixelMode mode) {
    brightnessScheduleRenderer::Cache<1200> cache; Sink sink;
    assert(cache.configure(count,mode)); cache.setGain(10000);
    const RgbwColor a(201,53,27,31), b(17,133,65,129);
    assert(cache.capture(0,a));
    assert(!cache.repaint(sink) && sink.shows == 0); // Nothing submitted yet.
    cache.show(sink); output(sink.pixels[0],a,10000,mode);
    assert(cache.capture(0,b));
    const RgbColor staged = mode == PixelMode::PhysicalRgbw ? RgbColor(b) : RgbColor(b.R,b.G,b.B);
    cache.invalidateOutput(); assert(cache.repaint(sink));
    output(sink.pixels[0],a,10000,mode); same(cache.read(0),staged);
    assert(!cache.repaint(sink));
    for (uint16_t gain : {5000,0,10000}) {
        assert(cache.setGain(gain) && cache.repaint(sink));
        output(sink.pixels[0],a,gain,mode); same(cache.read(0),staged);
        const unsigned shows = sink.shows;
        assert(!cache.repaint(sink) && sink.shows == shows);
    }
    assert(cache.pending()); // Staged B was never acknowledged by a repaint.
    cache.show(sink); output(sink.pixels[0],b,10000,mode);
    cache.clearAll(); same(cache.read(0),RgbColor(0));
    cache.setGain(5000); assert(cache.repaint(sink));
    output(sink.pixels[0],b,5000,mode); // A staged clear is not a show.
    cache.show(sink); output(sink.pixels[0],RgbwColor(0),5000,mode);
    cache.setGain(10000); assert(cache.repaint(sink));
    output(sink.pixels[0],RgbwColor(0),10000,mode);
    sink.prefix = 42; const unsigned shows = sink.shows;
    cache.show(sink); assert(sink.shows == shows + 1 && sink.prefix == 42);
    assert(cache.configure(count,mode)); cache.setGain(10000);
    assert(!cache.repaint(sink));
    assert(!cache.configure(1201,mode)); cache.setGain(10000);
    assert(!cache.repaint(sink));
}
int main() {
    for (size_t count : {300, 600, 900, 1200})
        for (auto mode : {PixelMode::Rgb, PixelMode::VirtualRgbw, PixelMode::PhysicalRgbw})
            { exercise(count, mode); presentation(count, mode); }
    assert(hsbConversions == 0);
}
