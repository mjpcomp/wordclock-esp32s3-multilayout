# Indicator lifecycle checkpoint

Recorded: 2026-11-11. Repository: mjpcomp/wordclock-esp32s3-multilayout.
Branch: feature/optional-status-prefix. Read this note at each continuation.

## Landed history

- Group 1: 3a177a77a202ae7824ed665a3d5e6935d4911de3, feat: prepare indicator policy before communication session. Four files changed: include/OnboardDiagnosticModel.h, include/OnboardIndicatorCommandService.h, include/OnboardIndicatorProtocol.h, tests/onboard_indicator_protocol_test.cpp; 21 additions, 2 deletions.
- Initial durable checkpoint: c2871f36dc82007eec5990c33d858f5a434ee342 (documentation only).
- Group 2A: 7e69202973b65eff124a8cddc718973e2d0bdfbe, fix: prioritize diagnostic black writes without delaying color. Published with exact-content user confirmation; actual commit patch inspected. Only include/OnboardDiagnosticSink.h and tests/test_onboard_diagnostic_sink.py changed; 23 additions, 8 deletions.

Refresh branch head before later changes. This note update advances the branch without changing firmware. Group 2A is committed; do not reapply it.

## Group 2A behavior and evidence

Black bypasses the sink's 20 ms color throttle. Initial black requests one write; duplicate black requests perform no write and do not postpone color. Nonblack clamp/cache/poll behavior and normal-mode isolation remain unchanged. No lifecycle or application wiring was activated.

Host regression rerun before publication: six mode/flag combinations, C++11, -Wall -Wextra -Werror, undefined/bounds sanitizers, and wrong-target rejection passed. Negative control failed at immediate black with the unchanged sink, as expected. Coverage includes immediate black after color, duplicate-black cadence, initial black, clamp, color cache, 20 ms boundaries and uint32 wrap. Tests use a mocked GPIO HAL; no real target build, CI result or electrical acceptance is claimed.

Pre-change Git blob SHAs, retained only for historical reproducibility (not current sink/test identities):
- include/OnboardDiagnosticSink.h: b95e6562aee2bd9675cf9c3fbc6ce6953658d36f
- tests/test_onboard_diagnostic_sink.py: faec646af8eafdcc76a8b08a0e3987177953e3e6
- include/ClockTestPolicy.h: c5f893e4856a68fad5f08421a1f7a195fa63223b

## Next bounded batch: lifecycle proposal, not implementation

1. Read current command service, runtime owner and NVS adapter, then configuration and application call sites in separate small batches. Existing docs/onboard-indicator-commands.md may predate current APIs; source is authoritative.
2. Prepare a fresh reviewed lifecycle plan covering read-only startup policy load before session creation, configured-timezone readiness, startup black, suppression/no-replay and normal-mode absence. Lifecycle source and storage/timezone tests remain NOT implemented or validated. Do not silently activate application wiring.
3. Obtain plan approval before implementation and exact-content confirmation before any further repository write. Real target builds and device acceptance remain separate gates.

## Continuity rules

The old exact-code Milestone 5A recipe was not recovered. This work uses fresh candidates, not a claimed reconstruction of lost approval. PLAN-7.md from conversation attachments is an older brightness-runtime-owner proposal, not that lifecycle recipe. Do not reuse unverified candidate hashes from failed reconstruction attempts.

Use small self-contained batches. Do not assume sandbox files or variables persist across turns. Record actual commits and evidence in repository notes after confirmed writes; never call local-only work a repository update. No attribution trailers unless explicitly enabled.
