#pragma once

// Compile-time UI capability facts only. No IO, new defaults or feature enabling.
// Do not equate these flags with runtime binding readiness, valid local time,
// a selected physical strip backend, or successful electrical/visible output.
// Flags are intentionally not defined here: the real build owns their values.
namespace brightnessScheduleCapabilities {
constexpr unsigned SCHEMA = 1;
#if defined(WORDCLOCK_ENABLE_RENDERER_CACHE) && WORDCLOCK_ENABLE_RENDERER_CACHE
constexpr bool RENDERER_CACHE_COMPILED = true;
#else
constexpr bool RENDERER_CACHE_COMPILED = false;
#endif
#if defined(WORDCLOCK_ENABLE_SCHEDULE_OUTPUT) && WORDCLOCK_ENABLE_SCHEDULE_OUTPUT
constexpr bool SCHEDULE_OUTPUT_COMPILED = true;
#else
constexpr bool SCHEDULE_OUTPUT_COMPILED = false;
#endif

// Called only by the scheduler protocol reply builder. A template keeps the
// compile-fact header independent of ArduinoJson; real JSON instantiation is
// exercised by the dedicated host/native compile gates. No storage is touched.
template <typename Document>
inline void appendTo(Document &reply) {
  auto capabilities = reply.createNestedObject("capabilities");
  capabilities["schema"] = SCHEMA;
  capabilities["configurationProtocol"] = true;
  capabilities["rendererCacheCompiled"] = RENDERER_CACHE_COMPILED;
  capabilities["scheduleOutputCompiled"] = SCHEDULE_OUTPUT_COMPILED;
}
} // namespace brightnessScheduleCapabilities
