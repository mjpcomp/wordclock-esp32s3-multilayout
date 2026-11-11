# Indicator lifecycle checkpoint

Recorded: 2026-11-11. Branch: feature/optional-status-prefix.
This note is a durable handoff, not proof that pending code has landed.

## Landed baseline

Last verified firmware commit: 3a177a77a202ae7824ed665a3d5e6935d4911de3, feat: prepare indicator policy before communication session. It modified include/OnboardDiagnosticModel.h, include/OnboardIndicatorCommandService.h, include/OnboardIndicatorProtocol.h and tests/onboard_indicator_protocol_test.cpp (21 additions, 2 deletions). Refresh branch head before continuing; this documentation commit will advance it without changing firmware.

## Fresh Group 2A proposal: NOT COMMITTED

Only include/OnboardDiagnosticSink.h and tests/test_onboard_diagnostic_sink.py are proposed. The previous exact-code lifecycle recipe was not recovered. Treat this as a new proposal, not a reconstruction of prior approval. Do not rely on candidate hashes quoted during failed reconstruction attempts.

Verified source Git blob SHAs used for the fresh proposal:
- include/OnboardDiagnosticSink.h: b95e6562aee2bd9675cf9c3fbc6ce6953658d36f
- tests/test_onboard_diagnostic_sink.py: faec646af8eafdcc76a8b08a0e3987177953e3e6
- include/ClockTestPolicy.h: c5f893e4856a68fad5f08421a1f7a195fa63223b

Exact proposed sink operation: replace the single line below inside Gpio48Sink::service:

```cpp
        if (polled && uint32_t(now - lastPoll) < 20) return false;
```

with:

```cpp
        // Black bypasses throttling; duplicate black must not postpone color.
        const bool black = !red && !green && !blue;
        if (black && sent && !previousR && !previousG && !previousB)
            return false;
        if (!black && polled && uint32_t(now - lastPoll) < 20) return false;
```

Everything else in the sink remains unchanged. Initial black requests one write; black after color bypasses the 20 ms throttle; duplicate black performs no write and does not move lastPoll. Nonblack clamp, cache and poll behavior remain unchanged. No production-mode output is enabled.

The new host tests were run on 2026-11-11 against hash-verified source copies: six mode/flag combinations, C++11, -Wall -Wextra -Werror, undefined/bounds sanitizers, and wrong-target rejection passed. New assertions cover color at 0 followed by immediate black at 1; duplicate black at 2; color rejected at 20 and accepted at 21; cached color at 41 followed by black at 42; duplicate black at 61 and color at 62; initial black at 0 followed by duplicate at 19 and clamped color at 20; and priority-black/color-throttle behavior across uint32 wrap. Existing clamp, color cache and wrong-target checks are retained. Negative control: these new tests failed against the unchanged sink at the immediate-black assertion. These are reported host results from that turn, not a target build, CI result or electrical validation. Rerun before publication.

The proposal and patch were delivered in the conversation, but are not repository code. Do not assume sandbox variables or generated files persist between turns.

## Next bounded batches

1. Re-read this checkpoint and current sink/test/policy sources. Prepare and review only the two-file Group 2A change; rerun host tests and obtain exact-content confirmation before pushing. Update this note with the actual commit and evidence, not an assumed result.
2. Separately inspect command service, runtime owner, NVS adapter, configuration and application call sites before proposing the lifecycle module. Its implementation and storage/timezone tests are NOT complete or validated. Do not silently activate application wiring.
3. Review startup black, configured-timezone readiness, read-only startup policy load, suppression/no-replay and normal-mode absence as explicit requirements in the new lifecycle plan. Real target builds and device acceptance remain separate gates.

## Working rules

Use small self-contained batches. Read repository notes at the start of each continuation. Persist meaningful checkpoints to this repository after confirmed writes; never describe a local-only artifact as a repository update. If an old candidate is unavailable, prepare a fresh reviewed candidate rather than inventing expected hashes. Existing docs/onboard-indicator-commands.md describes the earlier dormant foundation and may predate later API changes; inspect current source. No attribution trailers unless explicitly enabled.
