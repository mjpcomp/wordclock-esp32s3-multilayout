#include <Arduino.h>
#include "OnboardIndicatorNvsBackend.h"

#if !defined(ESP32)
#error "This fixture requires the real ESP32 SDK"
#endif

// Link roots only. Neither setup nor loop calls these functions.
extern "C" __attribute__((noinline))
onboardIndicatorStorage::ReadResult onboard_indicator_sdk_read(
    uint8_t *data, size_t capacity, size_t *size) {
    onboardIndicatorStorage::NvsBackend backend;
    return backend.read(data, capacity, *size);
}

extern "C" __attribute__((noinline))
bool onboard_indicator_sdk_write(const uint8_t *data, size_t size) {
    onboardIndicatorStorage::NvsBackend backend;
    return backend.write(data, size);
}

void setup() {}
void loop() {}
