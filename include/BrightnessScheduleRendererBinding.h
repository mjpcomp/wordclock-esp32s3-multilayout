#pragma once
#ifndef WORDCLOCK_ENABLE_RENDERER_CACHE
#define WORDCLOCK_ENABLE_RENDERER_CACHE 0
#endif
#if WORDCLOCK_ENABLE_RENDERER_CACHE != 0 && WORDCLOCK_ENABLE_RENDERER_CACHE != 1
#error "WORDCLOCK_ENABLE_RENDERER_CACHE must be 0 or 1"
#endif
#if WORDCLOCK_ENABLE_RENDERER_CACHE
#if !defined(ESP32)
#error "Renderer cache binding is currently ESP32-only"
#endif
#include "BrightnessScheduleRendererCache.h"
#include "BrightnessScheduleStripSink.h"

namespace brightnessScheduleBinding {
// Non-owning, serialized binding. Factory identity is never replaced.
// Fixed full gain only: no schedule coupling or legacy brightness changes.
class Binding {
    brightnessScheduleRenderer::Cache<1200> cache_;
    LedStripInterface *strip_ = nullptr;
    brightnessScheduleRenderer::PixelMode mode_ = brightnessScheduleRenderer::PixelMode::Rgb;
public:
    bool ready(const LedStripInterface *strip) const {
        return strip != nullptr && strip_ == strip;
    }
    bool attach(LedStripInterface *strip, size_t count, bool rgbw) {
        using brightnessScheduleRenderer::PixelMode;
        if (!strip || count == 0 || count > 1200) return false;
        const auto mode = !rgbw ? PixelMode::Rgb :
            strip->isVirtual() ? PixelMode::VirtualRgbw : PixelMode::PhysicalRgbw;
        if (strip_) return ready(strip) && cache_.count() == count && mode_ == mode;
        if (!cache_.configure(count, mode)) return false;
        cache_.setGain(brightnessScheduleOutput::kFullGain);
        mode_ = mode;
        strip_ = strip;
        return true;
    }
    bool capture(size_t index, RgbwColor pixel) { return strip_ && cache_.capture(index, pixel); }
    RgbColor read(size_t index) const { return strip_ ? cache_.read(index) : RgbColor(0); }
    bool clear(size_t index) { return strip_ && cache_.clear(index); }
    void show() {
        if (!strip_) return;
        brightnessScheduleOutput::StripSink sink(*strip_);
        cache_.show(sink);
    }
    // Call while the old backend is alive, BEFORE delete. No physical ack claim.
    bool retire(LedStripInterface *strip) {
        if (!ready(strip)) return false;
        cache_.clearAll();
        show();
        strip_ = nullptr;
        cache_.configure(0, mode_);
        return true;
    }
};
inline Binding &application() {
    // One shared bounded cache, never on the rendering/loop stack.
    static Binding binding;
    return binding;
}
} // namespace brightnessScheduleBinding
#endif
