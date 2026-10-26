#pragma once
#ifndef WORDCLOCK_ENABLE_RENDERER_CACHE
#define WORDCLOCK_ENABLE_RENDERER_CACHE 0
#endif
#if WORDCLOCK_ENABLE_RENDERER_CACHE != 0 && WORDCLOCK_ENABLE_RENDERER_CACHE != 1
#error "WORDCLOCK_ENABLE_RENDERER_CACHE must be 0 or 1"
#endif
#ifndef WORDCLOCK_ENABLE_SCHEDULE_OUTPUT
#define WORDCLOCK_ENABLE_SCHEDULE_OUTPUT 0
#endif
#if WORDCLOCK_ENABLE_SCHEDULE_OUTPUT != 0 && WORDCLOCK_ENABLE_SCHEDULE_OUTPUT != 1
#error "WORDCLOCK_ENABLE_SCHEDULE_OUTPUT must be 0 or 1"
#endif
#if WORDCLOCK_ENABLE_SCHEDULE_OUTPUT && !WORDCLOCK_ENABLE_RENDERER_CACHE
#error "Schedule output requires the renderer cache"
#endif
#if WORDCLOCK_ENABLE_RENDERER_CACHE
#if !defined(ESP32)
#error "Renderer cache binding is currently ESP32-only"
#endif
#include "BrightnessScheduleRendererCache.h"
#include "BrightnessScheduleStripSink.h"

namespace brightnessScheduleBinding {
// Non-owning, serialized binding. Factory identity is never replaced.
// Cache-only builds retain full gain. Schedule-output builds attach dark.
// The loop must adopt an evaluated owner gain before scheduled presentation.
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
        cache_.setGain(WORDCLOCK_ENABLE_SCHEDULE_OUTPUT ? 0 : brightnessScheduleOutput::kFullGain);
        mode_ = mode;
        strip_ = strip;
        return true;
    }
    bool capture(size_t index, RgbwColor pixel) { return strip_ && cache_.capture(index, pixel); }
    RgbColor read(size_t index) const { return strip_ ? cache_.read(index) : RgbColor(0); }
    bool clear(size_t index) { return strip_ && cache_.clear(index); }
#if WORDCLOCK_ENABLE_SCHEDULE_OUTPUT
    // Serialized loop-owned handoff only; no clock/storage access or submission.
    // Pass current().gain after evaluation, not the service "changed" result.
    bool adoptGain(uint16_t gain) { return strip_ && cache_.setGain(gain); }
    // Gain-only polling never presents an unshown staged transition target.
    bool repaint() {
        if (!strip_) return false;
        brightnessScheduleOutput::StripSink sink(*strip_);
        return cache_.repaint(sink);
    }
#endif
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
