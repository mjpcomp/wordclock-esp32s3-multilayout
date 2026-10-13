#pragma once

#include "LedStripInterface.h"
#include "NeoMultiFeature.hpp"
#include "LedStatusPrefix.h"
#include <assert.h>

template <typename T_METHOD>
class RgbLedStripAdapter : public LedStripInterface {
private:
    NeoPixelBus<NeoMultiFeature, T_METHOD> *strip;
    uint16_t logicalCount;

public:
    explicit RgbLedStripAdapter(uint16_t pixelCount) : logicalCount(pixelCount) {
        assert(uint32_t(pixelCount) + ledPrefix::COUNT <= UINT16_MAX);
        strip = new NeoPixelBus<NeoMultiFeature, T_METHOD>(pixelCount + ledPrefix::COUNT);
        strip->Begin();
        if (ledPrefix::COUNT) strip->SetPixelColor(0, RgbColor(0));
    }

    RgbLedStripAdapter(uint16_t pixelCount, uint8_t pin) : logicalCount(pixelCount) {
        assert(uint32_t(pixelCount) + ledPrefix::COUNT <= UINT16_MAX);
        strip = new NeoPixelBus<NeoMultiFeature, T_METHOD>(pixelCount + ledPrefix::COUNT, pin);
        strip->Begin();
        if (ledPrefix::COUNT) strip->SetPixelColor(0, RgbColor(0));
    }

    ~RgbLedStripAdapter() override { delete strip; }

    void setRgbPixel(uint16_t index, HsbColor color) override {
        if (index < logicalCount) strip->SetPixelColor(ledPrefix::physicalIndex(index), color);
    }

    void setRgbwPixel(uint16_t index, RgbwColor color) override {
        if (index < logicalCount) strip->SetPixelColor(ledPrefix::physicalIndex(index), RgbColor(color.R, color.G, color.B));
    }

    RgbColor getPixel(uint16_t index) override {
        return index < logicalCount ? strip->GetPixelColor(ledPrefix::physicalIndex(index)) : RgbColor(0);
    }

    void clearPixel(uint16_t index) override {
        if (index < logicalCount) strip->SetPixelColor(ledPrefix::physicalIndex(index), 0);
    }

    bool setStatusPixel(RgbColor color) override {
        if (!ledPrefix::COUNT) return false;
        strip->SetPixelColor(0, color);
        return true;
    }

    void show() override { strip->Show(); }
};

template <typename T_METHOD>
class RgbwLedStripAdapter : public LedStripInterface {
private:
    NeoPixelBus<NeoGrbwFeature, T_METHOD> *strip;
    uint16_t logicalCount;

public:
    explicit RgbwLedStripAdapter(uint16_t pixelCount) : logicalCount(pixelCount) {
        assert(uint32_t(pixelCount) + ledPrefix::COUNT <= UINT16_MAX);
        strip = new NeoPixelBus<NeoGrbwFeature, T_METHOD>(pixelCount + ledPrefix::COUNT);
        strip->Begin();
        if (ledPrefix::COUNT) strip->SetPixelColor(0, RgbwColor(0));
    }

    RgbwLedStripAdapter(uint16_t pixelCount, uint8_t pin) : logicalCount(pixelCount) {
        assert(uint32_t(pixelCount) + ledPrefix::COUNT <= UINT16_MAX);
        strip = new NeoPixelBus<NeoGrbwFeature, T_METHOD>(pixelCount + ledPrefix::COUNT, pin);
        strip->Begin();
        if (ledPrefix::COUNT) strip->SetPixelColor(0, RgbwColor(0));
    }

    ~RgbwLedStripAdapter() override { delete strip; }

    void setRgbPixel(uint16_t index, HsbColor color) override {
        RgbColor rgbColor(color);
        if (index < logicalCount) strip->SetPixelColor(ledPrefix::physicalIndex(index), RgbwColor(rgbColor.R, rgbColor.G, rgbColor.B, 0));
    }

    void setRgbwPixel(uint16_t index, RgbwColor color) override {
        if (index < logicalCount) strip->SetPixelColor(ledPrefix::physicalIndex(index), color);
    }

    RgbColor getPixel(uint16_t index) override {
        return index < logicalCount ? RgbColor(strip->GetPixelColor(ledPrefix::physicalIndex(index))) : RgbColor(0);
    }

    void clearPixel(uint16_t index) override {
        if (index < logicalCount) strip->SetPixelColor(ledPrefix::physicalIndex(index), 0);
    }

    bool setStatusPixel(RgbColor color) override {
        if (!ledPrefix::COUNT) return false;
        strip->SetPixelColor(0, RgbwColor(color.R, color.G, color.B, 0));
        return true;
    }

    void show() override { strip->Show(); }
};
