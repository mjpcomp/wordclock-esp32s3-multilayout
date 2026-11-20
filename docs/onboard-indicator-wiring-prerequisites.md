# Indicator wiring prerequisite inspection

Repository: mjpcomp/wordclock-esp32s3-multilayout
Branch: feature/optional-status-prefix
Inspected head: 33ab0e2fa055a9411dfc07e638a7e1036575f5cf
Recorded: 2026-11-19
Inspection only. No firmware edits, new tests, build, flash or application-wiring approval. Read docs/onboard-indicator-lifecycle-landed.md first; Group 2C is landed at 4e972a67 and must not be reapplied.

## Configured framework and startup ordering

Current platformio.ini blob 55db6a43ee95c5c355db44b455fd42e66aa4a044 pins espressif32 6.9.0 and framework arduino for the ESP32 environments. The isolated S3 BOARD_ONLY and RTC_ONLY profiles inherit that platform. No framework package override is visible in this file.

Read platformio/platform-espressif32 platform.json at tag v6.9.0, blob ee0745b680045e47c8488290cba184d4139b2f7a: Arduino package is platformio/framework-arduinoespressif32 with version constraint ~3.20017.0. This is a package range, not an inspected local installation or lockfile. No dependency update is proposed.

Inspected upstream espressif/arduino-esp32 at tag 2.0.17:
- cores/esp32/main.cpp blob 27b92948d5d4f75fd24b4c6d609554c2b90ff9a0: under CONFIG_AUTOSTART_ARDUINO, app_main calls initArduino before creating loopTask; loopTask calls setup before its loop.
- cores/esp32/esp32-hal-misc.c blob 835cce6f08c482feab5bff5ed818733ef6fff05d: initArduino calls nvs_flash_init. For NO_FREE_PAGES or NEW_VERSION_FOUND it may erase the NVS partition and retry. Other/final errors are logged, not propagated as a setup gate.

Thus the inspected upstream Arduino startup attempts NVS initialization before setup, but reaching setup is not proof that NVS is healthy. Confirm actual resolved framework package/build configuration during target validation; the upstream inspection is not proof of installed artifact identity. EEPROM.begin is not the basis for this ordering. Future lifecycle wiring should not add NVS initialization, retry or erase logic; retain storage read failure as a cached fail-closed condition and do not automatically retry preparation. Existing framework recovery can erase the whole NVS partition, so the module's read-only preparation must not be described as a guarantee that the entire boot never erases storage.

## Application startup rechecked

Read complete src/WordClock.cpp blob c043132b1c4f65b283b78e7d04ee810a74fce81f. setup currently starts with EEPROM/config handling; a power-cycle path can call network.startConfigPortal before LED/diagnostic startup. The ordinary path services diagnostics before network.setup, then calls wifiStart, configTime and applyTimezone. applyTimezone calls ensureTimezone, unchecked setenv and tzset. Factory-default handling can replace G.timezone before this application. Main-loop diagnostic service remains after clockWork.loop. No lifecycle calls are wired. The separate brightness owner is not the indicator owner.

These facts reinforce the need for an early explicit black boundary, read-only policy preparation after framework startup, and checked timezone application before scheduled readiness. They are design constraints for a later plan, not an implemented or approved patch. Do not globally deny AlwaysEnabled when time/TZ is unavailable. Future black/suppression boundaries around blocking calls require separate inspection and tests.

## Deferred timezone handler remains unverified

Direct read of include/ClockWork.hpp at inspected head reports blob 940315cbdee5e82236b300eda51c53985b119474 but truncates before the deferred command handler. Visible initBootShowIp still loops scrollingText with delay(200). Commit-pinned raw URL fetch failed again. GitHub code search for COMMAND_SET_TIMEZONE in this path returned no items with incomplete_results=true; this is not evidence that the handler is absent, and code search is not a verified feature-branch read.

Do not reconstruct or claim the missing handler was inspected. Next obtain a complete or bounded verified excerpt containing COMMAND_SET_TIMEZONE, related TIMESERVER handling and the surrounding clockWork loop. Use direct reads first; if connector limitations persist, discover path-specific commit/PR history and inspect relevant diffs, clearly labeling any historical/partial evidence. Check feature-branch blob identity before using default-branch excerpts. Do not repeat an identical failed raw fetch without a materially different retrieval route.

## Next gate

Close the deferred-handler source gap and verify relevant mutation and blocking-call paths before writing the separate exact-code application-wiring plan. Actual resolved framework/build configuration and real target acceptance remain validation gates. No new code, tests or wiring are authorized by this inspection checkpoint.
