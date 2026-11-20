#pragma once
namespace onboardIndicatorCommandService { class Service; }

// Serialized main/control-loop API; never call from callbacks or interrupts.
namespace onboardIndicatorLifecycle {
bool supported();
// Call only after the framework has initialized NVS. No session or writes.
void preparePolicy();
bool prepared();
void invalidateTimezone();
// Caller confirms successful application of the current G.timezone to libc TZ.
void timezoneApplied(bool success);
bool timezoneReady();
bool permitted();
// nullptr outside isolated ESP32-S3 profiles; lookup performs no storage IO.
onboardIndicatorCommandService::Service* commandService();
}
