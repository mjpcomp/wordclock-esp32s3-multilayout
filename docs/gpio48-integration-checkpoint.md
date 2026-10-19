# GPIO48 diagnostic integration checkpoint

Updated: 2026-10-19. Baseline inspected: 0298e25a7cb513b7fc5846bc6481d3726e3326af.

## Confirmed scope and board facts
- Board: YD-ESP32-23 N16R8. The onboard addressable RGB LED is on GPIO48.
- User confirms the RGB connection is populated with a factory-fitted resistor. Do not request solder bridging or external wiring inspection as a prerequisite.
- GPIO48 is the intended persistent notification/debug output, not the external matrix.
- Preserve BOARD_ONLY and RTC_ONLY isolation; no external matrix output. BOARD_ONLY does not expect an RTC.
- Keep the normal external matrix driver unchanged. No attribution trailers unless explicitly enabled.

## Implemented versus pending
- Implemented: include/OnboardDiagnosticModel.h and tests/test_onboard_diagnostic_model.py. Approved palette/timings/priorities are in docs/onboard-diagnostic-model.md.
- Pending: restricted physical GPIO48 sink, runtime hooks, integration tests, target compilation and physical validation.
- No new tests or builds were run during this checkpoint inspection. No flash-readiness claim.

## Verified integration findings
- b1f053c introduced include/ClockWorkLedFactory.hpp. In test modes it constructs VirtualLedStripAdapter; physical NeoEsp32Rmt0Ws2812xMethod construction is in the normal-mode branch. 0b945e7 routes ClockWork.hpp through this factory.
- Therefore, do not treat simultaneous physical matrix/onboard RMT allocation as an assumed blocker in isolated profiles. Verify other peripheral users and the chosen sink allocation; the virtual matrix does not itself construct that physical RMT0 adapter.
- cecbf523 adds PrefixStatusRuntime.h to src/WordClock.cpp, calls noteTimeSet() in the time callback and service() after clockWork.loop(tm). Inspect the current runtime definitions and later edits before reusing these hooks.
- dc5335f defines isolated build flags enabling onboard output, disabling prefix output, and compile assertions for GPIO48. The workflow has later fixes; use current branch versions, not the original diff alone.
- Arduino-ESP32 2.0.17 RGB HAL history uses RMT and rmtWriteBlocking(). neopixelWrite avoids another library, not necessarily another RMT resource. RGB_BUILTIN may be an encoded identifier rather than raw GPIO48.

## Resume checklist
- [ ] Read current policy, prefix runtime, virtual diagnostics, time-source handling and pinned dependency definitions via commit/PR diffs.
- [ ] Verify exact driver API, physical pin resolution and RMT ownership against resolved dependencies. Do not assume an RMT1 NeoPixelBus alias exists.
- [ ] Implement a test-profile-only sink fixed to GPIO48; no web-selectable pin, cache unchanged colours, target 20ms sampling.
- [ ] Connect observed network/time states and changedFrames; callbacks signal a mailbox only, main loop owns model and output.
- [ ] Preserve approved model semantics: no missing-RTC warning in BOARD_ONLY; frame event means software change, not physical acknowledgement.
- [ ] Add integration/isolation tests, run host suites and compile both isolated profiles; retain provenance and actual results.
- [ ] Validate low-brightness RGB mapping and persistent patterns on the user's board before any readiness claim.

## Continuity rules
Update this checkpoint with landed commit IDs, checks actually run, failures and the first unfinished task. Never mark planned work complete. Workspace prompt retrieval is not a firmware prerequisite; ask only about a specific unresolved instruction if needed.
