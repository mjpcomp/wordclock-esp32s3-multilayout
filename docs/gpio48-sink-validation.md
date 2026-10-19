# GPIO48 sink checkpoint

Continuation of docs/gpio48-integration-checkpoint.md, 2026-10-19.

Added: include/OnboardDiagnosticSink.h and tests/test_onboard_diagnostic_sink.py.
The sink is only available in isolated ESP32-S3 test modes. It requests raw GPIO48 writes through the core neopixelWrite API, caps each channel at 20, suppresses unchanged colours and rate-limits polling to 20ms. It adds no delay calls. The core transport may block; this is not an asynchronous-output claim.

Local validation: the new test passed with g++, C++11, warnings as errors and undefined/bounds sanitizers, using ClockTestPolicy.h reconstructed from its sole introduction diff. Six mode/onboard-flag combinations passed, including normal mode without Arduino/HAL headers; GPIO48, clamp, cache, timing boundaries, wrap and wrong-target rejection were checked. Arduino/HAL calls were mocked. The installed target core, physical RGB order and electrical output were not validated. No full host-suite run or firmware build was performed.

This header is not connected to the application yet. Existing firmware, matrix driver and CI workflow are unchanged. The new test must be added to CI during runtime integration.

Next: verify resolved core GPIO/RMT implementation; inspect current time-source/AP/connection handling; add main-loop-owned model/sink service and atomic event mailbox; consume changedFrames with backend-reset handling; run integration tests and both isolated target builds. Do not infer RTC source from mere RTC detection or NTP source from an unspecified time-set callback. Physical colour validation remains pending. Not flash-ready.
