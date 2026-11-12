# Group 2C lifecycle candidate validation

Repository: mjpcomp/wordclock-esp32s3-multilayout
Branch: feature/optional-status-prefix
Base inspected: a94f9b7121b345a957947f36e7bd804429a812e6
Recorded: 2026-11-11
Status: approved plan; four-file candidate generated and lifecycle host suite passed locally; CODE NOT COMMITTED.

## Candidate contract

Dormant lifecycle API: supported, preparePolicy, prepared, invalidateTimezone, timezoneApplied(bool), timezoneReady, permitted and commandService. One function-local native backend/service pair in a single .cpp; lookup has no storage IO. Isolated ESP32-S3 profiles only; normal/unsupported profiles are no-op and expose no service. The source explicitly includes ClockTestPolicy.h before profile conditionals.

Preparation is read-only and does not begin a communication session. It must only be called after framework NVS initialization, whose application placement remains deferred. Timezone confirmation snapshots the bounded G.timezone string after the caller reports successful application; changed configuration invalidates comparison. Callers must invalidate before same-string reapplication or external TZ operations. This is not POSIX-string semantic validation or proof of arbitrary process-environment consistency. AlwaysEnabled remains independent of time readiness, subject to storage-owner faults. No application, GPIO, network, codec or existing runtime changes are proposed.

## Exact generated candidate identities

These hashes were computed from the actual tested candidate, not recovered from the lost recipe.

- include/OnboardIndicatorLifecycle.h: 645 bytes; Git blob e3ea91d05419ab445d5344a3543f74b57b3d7b04; SHA256 be0870d7c9faee8a61db025eb7dfa91c05a2932cdc4574c45343a39f5b7319bf.
- src/OnboardIndicatorLifecycle.cpp: 2278 bytes; Git blob e51335a14f9a93f52a9f0eb1138e1f55471fc583; SHA256 f93f230d38e1198b5aaa58cb5e8940a99371892e62ed08bbd880e4c174fcc1ac.
- tests/onboard_indicator_lifecycle_test.cpp: 4515 bytes; Git blob 450df38e2be7e231799c6bc0fdbb64b1adb86c71; SHA256 974493354e208800b10d675c46f1605a283d53e10ed7be1828322bee5b9676c9.
- tests/test_onboard_indicator_lifecycle.py: 2775 bytes; Git blob a6cdc2129424085f3777f645e7c0133584ebce1f; SHA256 6100e4adc97c03f3d360a04db56a8a00c131a55c52443bbcb8e9c489c142acbc.

## Actual evidence

python3 tests/test_onboard_indicator_lifecycle.py passed locally. The actual lifecycle .cpp was compiled and linked with real repository service/owner/storage/record/policy/NVS-adapter headers, each Git-blob verified; NVS ABI and application state were mocked. Four profiles: normal, isolated board, isolated RTC, unsupported ESP32 target. Fourteen fresh scenario processes: six each for board/RTC (missing, always, disabled, scheduled, corrupt, IO) plus normal and unsupported. C++11, -Wall -Wextra -Werror, undefined/bounds sanitizers.

Checks include no constructor/lookup IO, one read-only preparation attempt, no automatic retry, repeated polling without storage IO, zero session before begin, NotInitialized commands before begin, later begin without reread, singleton identity across two TUs, configured-TZ changes/invalidation, real host UTC/UTC1 conversion, invalid time/clock errors, empty and unterminated TZ strings, and no-op unsupported profiles. No writes are allowed by the NVS mock.

The tested candidate ZIP and JSON manifest were delivered in the conversation. They are not repository code; do not assume sandbox files persist. Full approved source is in the Group 2C plan and candidate conversation artifacts; verify actual bytes against these hashes before resuming. Hashes alone do not recover missing source.

## Next bounded validation batch

Run existing indicator core, commands and NVS host suites, plus diagnostic runtime/chained report and sink regressions against this candidate. These reruns have NOT occurred in the lifecycle-validation turn. Obtain exact-content confirmation before publishing the four files. If source bytes differ, re-review and retest instead of assuming equivalence. After actual push inspect the published patch and record the real commit.

No SDK/target build, CI result, startup-order or physical acceptance is claimed. Application wiring remains separate and the deferred ClockWork.hpp timezone handler source gap remains open. Read docs/onboard-diagnostic-suppression.md for landed Group 2B; do not reapply earlier batches.
