# Diagnostic suppression checkpoint (Group 2B)

Repository: mjpcomp/wordclock-esp32s3-multilayout
Branch: feature/optional-status-prefix
Recorded: 2026-11-11

## Landed code

Commit aea7f4d638f0ebd021ce5d8bc85f0651d974c5bf: feat: add diagnostic suppression without event replay. Plan approved, then exact two-file content separately confirmed before publication. Actual published patch inspected: include/OnboardDiagnosticRuntime.h and tests/test_onboard_diagnostic_runtime.py only; 56 additions, 8 deletions. Do not reapply Group 2B.

Earlier Group 2A sink priority-black behavior is landed at 7e69202973b65eff124a8cddc718973e2d0bdfbe. Earlier inspection notes describe pre-2B Runtime APIs and are historical where they state that no suppression API exists.

## API and boundaries

Runtime now provides main-loop-only suppress(now), which consumes currently pending NTP into source/cooldown state, clears active pulses, resets frame tracking, marks muted and requests black. service has a final bool permitted=true argument; unchanged callers retain prior behavior. Denied service forwards black with Event::None while maintaining source observations. First permitted service after suppression discards queued pulses and establishes a fresh frame baseline. It does not reset the Controller or forget source/cooldown history.

The original single-slot atomic NTP mailbox and callback behavior are unchanged; no stronger cross-task event ordering guarantee is claimed. An event arriving after a consume boundary can be handled by a later service. Sink write requests are not physical acknowledgments. No application caller uses the new permission input or suppress API yet, so this commit does not activate scheduling, startup black or blocking-call wiring.

## Actual local evidence before publication

Source copies verified by Git blob hashes. Runtime preimage a74b3414a157c95df62d9ddd05beddfda3d26941; test preimage f7fee47c162a7f9f1c39479617d68c4f664a25c9. Tested candidate blob identities: Runtime 021b24a87462e2161c03e4961b8e54f23e5de5fb; runner d65a11e4e0b6694377b5077d8249a8dbf23cdf46.

- python3 tests/test_onboard_diagnostic_runtime.py passed, including its unchanged chained test_onboard_time_report.py (modes 0/1/2). C++11, -Wall -Wextra -Werror, undefined/bounds sanitizers.
- python3 tests/test_onboard_diagnostic_sink.py passed all six mode/flag combinations and wrong-target rejection.
- New Runtime assertions cover quiet polling, resume without replay, subsequent frame events, NTP cooldown recovery, no-poll gaps, RTC source and uint32 wrap. All prior assertions retained.
- New tests against the old Runtime failed compilation for the missing suppression API, as expected; not a behavioral negative control.

These are host/interface-mock results, not real SDK builds, CI status or device/electrical validation. No tests were rerun after publication in the publishing turn; only the actual commit patch was verified.

## Next small batch

Read this note with docs/onboard-indicator-lifecycle-checkpoint.md, docs/onboard-indicator-lifecycle-inspection.md and docs/onboard-indicator-startup-inspection.md. Refresh branch head and current source before further edits.

Lifecycle module, read-only startup load integration, timezone readiness, application permission binding, startup/blocking-call black boundaries and real-target acceptance remain pending. The full feature-branch ClockWork.hpp deferred timezone handler remains unverified because direct output truncated and commit-pinned raw fetch failed. Do not claim that gap closed or reconstruct the full header from partial excerpts. Current Config.h does not include ClockTestPolicy.h; future lifecycle source must include it before mode conditionals.

Prepare the next fresh lifecycle module/test plan independently of unresolved application wiring. Preserve the single service/backend owner; do not start a communication session merely to prepare policy. Obtain exact-content confirmation before external writes, keep batches small, and persist actual results in repository notes rather than relying on sandbox state.
