# Indicator startup and timezone inspection

Inspected 2026-11-11 at e058e3a7a97f0ad1eed6187628f68c7dbbeeeadb in mjpcomp/wordclock-esp32s3-multilayout, branch feature/optional-status-prefix. Read with onboard-indicator-lifecycle-checkpoint.md and onboard-indicator-lifecycle-inspection.md in this directory. Inspection only: no firmware edits or new tests.

## Verified startup order

src/WordClock.cpp (blob c043132b1c4f65b283b78e7d04ee810a74fce81f): setup calls EEPROM.begin, eeprom::read, pin checks and ensureTimezone before power-cycle handling. The power-cycle path may call network.startConfigPortal before LED, RTC and WiFi setup. Factory defaults can subsequently replace G.timezone. ensureTimezone validates/replaces the config string but does not apply TZ.

Later setup initializes LEDs, loads RTC time when available, registers the time callback, marks diagnostics connecting, calls diagnostic service, then network.setup. After that it clears connecting, calls wifiStart, configTime and applyTimezone in that order. Thus diagnostics can run before configured TZ application, and RTC may already have made system time valid. applyTimezone currently calls ensureTimezone, setenv and tzset without checking setenv success. Scheduled permission must not infer configured-timezone readiness merely from a valid epoch. AlwaysEnabled must retain its documented clock independence.

Main loop processes network, HTTP, websocket and MQTT before clockWork.loop; diagnostic service is at the end. Existing brightness owner startup remains at setup end and is a separate feature: do not repurpose it as the indicator owner.

## Blocking-call boundaries visible in source

src/Network.cpp (blob 1767468766103b6a1576fcd08b43976002dd6e01) delegates to WiFiManager autoConnect/startConfigPortal with no diagnostic service hooks in this wrapper. Its loop calls wifiManager.process. This inspection does not establish library-internal timing or callbacks; do not claim a bounded service cadence during these calls. A planned black-before-call boundary can avoid leaving a colored diagnostic latched while the application cannot service it; it does not make the library cooperative.

src/WifiHelper.cpp (blob 858f441facb7ce207de6efdb55c59e6a1c8ca851) calls clockWork.initBootShowIp when bootShowIP is enabled. The visible beginning of include/ClockWork.hpp shows that method iterating scrollingText with delay(200). Startup also contains direct delays. Either explicit black around unserviced intervals or a separately tested cooperative path must be specified; do not claim the current application polls diagnostics throughout.

include/EEPROMAnything.h (blob 368e76a8f2324fe89737772ddb22e928f65ecef6) reads the raw G config and delays 100 ms; it does not apply TZ. Native indicator NVS initialization readiness still needs verification against the framework/startup contract; EEPROM.begin alone is not proof established by this inspection.

## Runtime timezone mutation

src/WebPageAdapter.cpp (blob b6b5b1f82308697b097e939a0f5799e9e51d69c0): COMMAND_SET_TIMEZONE copies payload into G.timezone, then the common path sets G.conf. It does not apply TZ in this handler. A future readiness guard must account for the interval between config mutation and actual application, including overwritten/deferred commands. Manual time commands call settimeofday and do not themselves establish an NTP source.

## Existing runtime regression coverage

tests/test_onboard_diagnostic_runtime.py (blob f7fee47c162a7f9f1c39479617d68c4f664a25c9) covers source truth, callback deferral, original NTP timestamps, frame deltas/reset, masking, expiry, wrap and sink forwarding, then invokes test_onboard_time_report.py. Preserve these checks and the chained report test when adding suppression coverage. No tests were executed in this batch.

## Unresolved source gap and immediate next step

The direct include/ClockWork.hpp response (blob 940315cbdee5e82236b300eda51c53985b119474) was truncated before its deferred command handler. Only visible portions were inspected. Do not claim the timezone command application path or all cooperative/blocking paths are verified. Obtain a bounded excerpt of the deferred COMMAND_SET_TIMEZONE/TIMESERVER handling and surrounding loop before writing an application patch. Also inspect current Config.h, the diagnostic model and test_onboard_time_report.py. GitHub search may index only the default branch: verify any search excerpt against the feature-branch blob, not merely its filename.

After closing these gaps, prepare the fresh exact-code lifecycle plan in small independent batches: module plus storage/TZ tests; runtime suppression plus no-replay tests; separately reviewed startup/application wiring and real target builds. Persist the plan in the repository, not only sandbox state. No plan approval or code activation is implied by this inspection note.
