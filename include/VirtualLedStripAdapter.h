#pragma once
#include "LedStripInterface.h"
#include <vector>

// Logical framebuffer only. This class never constructs a physical bus/driver.
class VirtualLedStripAdapter : public LedStripInterface {
    std::vector<RgbwColor> pixels;
    bool rgbw;
    bool dirty = true;
    uint32_t requests = 0, frames = 0;

    void assign(uint16_t index, RgbwColor color) {
        if (index >= pixels.size()) return;
        const RgbwColor &old = pixels[index];
        if (old.R == color.R && old.G == color.G && old.B == color.B && old.W == color.W) return;
        pixels[index] = color;
        dirty = true;
    }
public:
    explicit VirtualLedStripAdapter(uint16_t count, bool useRgbw = false)
        : pixels(count, RgbwColor(0)), rgbw(useRgbw) {}
    void setRgbPixel(uint16_t index, HsbColor color) override {
        const RgbColor rgb(color);
        assign(index, RgbwColor(rgb.R, rgb.G, rgb.B, 0));
    }
    void setRgbwPixel(uint16_t index, RgbwColor color) override {
        if (!rgbw) color.W = 0;
        assign(index, color);
    }
    RgbColor getPixel(uint16_t index) override {
        if (index >= pixels.size()) return RgbColor(0);
        const RgbwColor &color = pixels[index];
        return RgbColor(color.R, color.G, color.B);
    }
    RgbwColor getRgbwPixel(uint16_t index) const {
        return index < pixels.size() ? pixels[index] : RgbwColor(0);
    }
    void clearPixel(uint16_t index) override { assign(index, RgbwColor(0)); }
    // External prefix output is absent here; onboard diagnostics has its own sink.
    bool setStatusPixel(RgbColor color) override { (void)color; return false; }
    bool isVirtual() const override { return true; }
    LedStripDiagnostics diagnostics() const override {
        return {static_cast<uint16_t>(pixels.size()), requests, frames, true};
    }
    void show() override {
        ++requests;
        if (dirty) { ++frames; dirty = false; }
    }
};
