# Protocol native-build macro collision and regression check

## Observed failure
On 2026-10-21 the user reported the d6ea6e5 protocol host job green but both isolated native compiles failed. The supplied RTC_ONLY trace reaches include/BrightnessScheduleProtocol.h through ArduinoJson, Arduino.h, FreeRTOS and the ESP32 toolchain limits.h, then rejects `constexpr size_t MAX_INPUT = 2048` with `expected unqualified-id before numeric constant`. The successful compiledb step only produced the compilation database; it did not establish a successful application compile.

## Root cause and scoped correction
MAX_INPUT is also a platform preprocessor macro. Macro replacement runs before C++ namespace lookup, so placing the constant in brightnessScheduleProtocol does not protect the identifier. Rename exactly the three protocol-header occurrences to kMaxInput. Keep the protocol input limit at 2048 and leave the platform macro, dependencies, board/profile settings, storage behavior and safety policies untouched. Do not fix this by undefining the SDK macro or suppressing native checks.

The protocol host runner now executes the unchanged actual-ArduinoJson test harness twice: its ordinary build and a build with -DMAX_INPUT=255. The latter includes a temporary wrapper that checks the platform macro still exists with value 255, checks kMaxInput is 2048, then includes and runs the complete existing protocol harness. No fake parser substitutes for those tests. The current workflow already watches both changed source/test paths, so a workflow edit is unnecessary.

## Local validation and remaining gates
Reconstructed baseline header/runner hashes match the published reviewed payload. A local C++11 compiler probe with the macro predefined reproduces the old declaration failure; the renamed declaration compiles with warnings-as-errors and both macro/limit assertions intact. Updated Python runner syntax and its refusal to run without actual ArduinoJson headers were checked. Complete real-ArduinoJson and ESP32 target tests have not been run locally and remain required on the new CI run before integration.

Lesson: project-owned constants in platform-facing headers should avoid generic all-caps names used by C/SDK headers. Host tests should exercise relevant platform macro/include conditions, while real-framework compiles remain mandatory. A passing host suite or compiledb target is not proof of a passing embedded build.

The protocol remains dormant. This correction does not register transport handlers, activate scheduling, reset stored settings or require a board flash. Current validated a37c3bc BOARD_ONLY UI-polish firmware stays running. Scheduler issue #3 and later full-settings export/AP import issue #4 remain the work queue.
