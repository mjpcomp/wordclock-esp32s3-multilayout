# Group 2C landed lifecycle checkpoint

Repository: mjpcomp/wordclock-esp32s3-multilayout
Branch: feature/optional-status-prefix
Recorded: 2026-11-19

## Landed code

Commit 4e972a67c2c1f84470f808e77d60990b9e8cfb28, feat: add dormant onboard indicator lifecycle. The user separately approved the exact four-file publication after plan approval and validation. Published full patch inspected: four added files, 207 additions, no existing files modified.

- include/OnboardIndicatorLifecycle.h
- src/OnboardIndicatorLifecycle.cpp
- tests/onboard_indicator_lifecycle_test.cpp
- tests/test_onboard_indicator_lifecycle.py

All four candidate SHA256/Git-blob identities were recomputed before publication and matched docs/onboard-indicator-lifecycle-validation.md. The source is now in GitHub; do not reconstruct it from old conversation artifacts or reapply Group 2C. Earlier notes saying CODE NOT COMMITTED are historical, superseded by this checkpoint. No application, GPIO, startup, networking or UI wiring was changed. No communication session is started by policy preparation.

## Validation chronology and scope

The actual lifecycle module passed four profiles and fourteen fresh-process scenarios on November 11, as recorded in docs/onboard-indicator-lifecycle-validation.md. Core, commands/mailbox and portable/mocked-NVS suites passed separately; see docs/onboard-indicator-foundation-regressions.md. Those foundation suites do not link the lifecycle translation unit.

On November 19 before publication, the unchanged full python3 tests/test_onboard_diagnostic_runtime.py passed, including its chained tests/test_onboard_time_report.py modes 0/1/2. The unchanged full python3 tests/test_onboard_diagnostic_sink.py passed all six mode/flag combinations and wrong-target rejection. Both runners exited 0 with empty stderr. All eight input source files were Git-blob verified. C++11, -Wall -Wextra -Werror, undefined/bounds sanitizers and no sanitizer recovery. The earlier November 19 runtime-component-only result is superseded by the successful full runner.

Verified input blobs:
- include/OnboardDiagnosticRuntime.h: 021b24a87462e2161c03e4961b8e54f23e5de5fb
- include/OnboardDiagnosticModel.h: f1afdc5c8be5251ae7f5ea94415c8a947fce5525
- include/OnboardDiagnosticSink.h: a6324e68dc9e7dc153b68aa1090370a6ad4008e8
- include/OnboardDiagnosticApplication.hpp: f3f5dd5b1f4c288786ca51fa0dbcb4ae1828e18c
- include/ClockTestPolicy.h: c5f893e4856a68fad5f08421a1f7a195fa63223b
- tests/test_onboard_diagnostic_runtime.py: d65a11e4e0b6694377b5077d8249a8dbf23cdf46
- tests/test_onboard_time_report.py: 2ee81cfc15f045da9720e30e32bbe9558f8df95f
- tests/test_onboard_diagnostic_sink.py: fef81a503de762a5a134286df94f4bd74c99c27f

The time-report test uses mocked runtime/sink interfaces; these are separate host/interface tests, not a complete firmware integration test. No new lifecycle C++ execution occurred on November 19 before publication; candidate identities were unchanged and Python syntax was rechecked. No tests were rerun in the code-publication turn; only the actual published patch was inspected. JSON evidence and source/candidate ZIPs were delivered in the conversation. No SDK build, CI success, flash operation or physical/electrical acceptance is claimed.

## Next bounded work

Refresh branch head and read this checkpoint first, then the earlier lifecycle-validation, foundation-regressions, diagnostic-suppression and startup-inspection notes. Groups 1, 2A, 2B and 2C are landed; do not reapply them.

Before planning application wiring, obtain verified source for the full deferred ClockWork.hpp timezone application handler and establish the framework NVS initialization contract. The earlier truncated-read/raw-fetch source gap is still open. Inspect actual application startup, loop and blocking-call boundaries; then propose a separate exact-code wiring plan and obtain plan approval. No application wiring is approved by Group 2C publication.

Preserve one backend/service owner; read-only preparation after NVS initialization without starting a communication session; explicit timezone invalidation/confirmation; time-independent AlwaysEnabled subject to storage faults; no-op normal/unsupported profiles; suppression/no replay; and main-loop-only GPIO/storage access. Timezone confirmation is a caller contract, not arbitrary libc TZ semantic validation. Preserve explicit black boundaries for unserviced/blocking intervals in any future wiring design. Real-target builds and device acceptance remain separate gates.
