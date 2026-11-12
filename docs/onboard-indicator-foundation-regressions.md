# Group 2C foundation regression evidence

Repository: mjpcomp/wordclock-esp32s3-multilayout
Branch: feature/optional-status-prefix
Inspected base: d1d904876f83173199f1d077875cdf647f556c16
Recorded: 2026-11-11

## Completed in this batch

Original repository runners and C++ fixtures were copied completely, Git-blob verified, and executed without changing assertions. All required shared headers were also blob verified. All three runners compiled using C++11, -O2, -Wall -Wextra -Werror, undefined/bounds sanitizers and no sanitizer recovery.

- python3 tests/test_onboard_indicator_core.py: passed. Output: 8294400 3136 24480 9, respectively membership checks, window-pair checks, single-byte corruptions and logical-invalid cases. Runner blob 6b7ef1c117087187cc46709def4b471519739c4d; fixture e6b1d5b872ad60526f16e87ee541d5a9e204fcbc.
- python3 tests/test_onboard_indicator_commands.py: passed, exit 0. Runner blob eb809679025f8e041cde791b2000a5fa9299a310; fixture b30b2a29f643f9f5fef4d4f84bb192751c82ae72. Covers typed commands, stale/fenced requests, uncertain storage, mailbox bounds/routes and reply failure without automatic replay.
- python3 tests/test_onboard_indicator_nvs.py: passed both portable and nvs-stub builds. Runner blob 4ddeb04eab2266818d40c740a59f4c991a05d566; fixture c07984bcaf0f6304812afd608621d18075f6a590. Native ABI is mocked, not physical flash.

## Evidence scope

These unchanged foundation suites do not link or exercise the new lifecycle translation unit. They verify the actual shared service/owner/storage/codec/backend contracts used by the candidate. The separate actual-lifecycle host result remains recorded in docs/onboard-indicator-lifecycle-validation.md: four profiles and fourteen scenario processes passed in the earlier turn. Do not conflate these results with a full application/SDK build.

No candidate source was modified or published in this regression batch. The Group 2C four-file candidate remains uncommitted. Full source is in the approved Group 2C plan and tested-candidate artifacts; its exact computed hashes are recorded in the lifecycle validation note. The JSON regression evidence was delivered in the conversation. Do not assume sandbox files persist.

## Immediate next batch

Rerun existing diagnostic runtime with its chained time-report test, and the landed sink regression. Then refresh repository head, verify the four candidate identities, and request exact-content confirmation before code publication. Do not reapply Group 2A or 2B. Preserve the explicit TZ caller contract and leave application wiring dormant.

Real SDK/target builds, CI status and device acceptance remain separate and unclaimed. Deferred ClockWork.hpp timezone handler inspection remains unresolved for later application wiring.
