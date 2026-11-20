# Deferred timezone handler inspection

Repository: mjpcomp/wordclock-esp32s3-multilayout
Branch: feature/optional-status-prefix
Inspected head: 85d1d892c30415df6129ba97973c566c68d322ee
Recorded: 2026-11-19
Inspection only: no code changes, test runs or application-wiring approval. Group 2C remains landed and dormant at 4e972a67.

## Source gap closed for the relevant handler, through history

The current direct full-file ClockWork.hpp response remains truncated. Instead, list_commits filtered to include/ClockWork.hpp on this feature branch returned four commits: import e7ca4cb815c72d3f374f17742ebf86600ddf54d3; language-rule change 8e742119e9585e044ef9c0c110081c21cfa77017; LED-factory extraction 0b945e7b9cad45c4a0cc8616df5a37746db8afdd; brightness guard 7f5ee959f5dbaf7b3c178b16bf173100eae9ac68. The result contained only these four entries, below the requested page size of 20.

The complete import patch was retrieved with get_commit full_patch: include/ClockWork.hpp added, 2023 lines, visible through its final closing brace. It includes the complete deferred command switch and surrounding ClockWork::loop. All three later patches were inspected in full: they only change language rules, replace initLedStrip with ClockWorkLedFactory.hpp, and add an early brightness-sensor guard. None changes the deferred handler or loop ordering described below. This is historical-source plus exhaustive subsequent path-diff evidence for the relevant region, not a claim of a fresh untruncated current-file download or a reconstructed full file matching the current blob. Previously observed current blob: 940315cbdee5e82236b300eda51c53985b119474.

## Verified deferred behavior

ClockWork::loop runs hardware-button processing, transition demo work, per-second work including weather.loop and automatic brightness, and per-minute persistence/MQTT work before switch(G.conf).

The timezone case is exactly:

```cpp
    case COMMAND_SET_TIMEZONE: {
        applyTimezone();
        eeprom::write();
        parametersChanged = true;
        delay(100);
        break;
    }
```

COMMAND_SET_TIMESERVER is grouped with other setting commands that only call eeprom::write and delay(100) in this switch. There is no configTime or SNTP restart in this deferred case. After the configuration switch the loop unconditionally assigns G.conf = COMMAND_IDLE, then processes G.prog. Transition-mode initialization also writes EEPROM and delays 100 ms. The reset case delays 500 ms and restarts; other visible cases call mqtt.init, network.reboot, network.disable or network.resetSettings. These call sites require considered suppression boundaries, not an assertion that all library internals are cooperative.

The current applyTimezone definition and startup call sequence remain those inspected in src/WordClock.cpp blob c043132b1c4f65b283b78e7d04ee810a74fce81f: ensureTimezone, unchecked setenv, tzset. Wiring must invalidate readiness before application and confirm only a successful checked application, including same-string reapplication.

## Immediate mutation and pending-command boundary

Read complete src/WebPageAdapter.cpp at inspected head, blob b6b5b1f82308697b097e939a0f5799e9e51d69c0. COMMAND_SET_TIMEZONE copies the payload into G.timezone immediately; COMMAND_SET_TIMESERVER similarly changes G.timeserver. A common trailing path assigns the command to G.conf. It is a single pending command field, not a queue, and later commands can overwrite it. The callback also calls sendMQTTUpdate. Neither timezone mutation case applies TZ itself. Manual time commands call settimeofday, with the local manual variant using localtime_r/mktime.

Design consequence: changed-string detection in the landed lifecycle prevents scheduled permission while config and last confirmed TZ differ, even if a deferred command was overwritten. Do not repair that case by marking TZ ready without application. Specify whether future wiring merely remains fail-closed until an explicit application or adds separately reviewed reconciliation. Same-string operations require explicit invalidation; string comparison alone cannot detect them. Keep callbacks free of new GPIO/storage work; main-loop boundaries own suppression.

## Network and IP display boundaries rechecked

Read complete src/Network.cpp blob 1767468766103b6a1576fcd08b43976002dd6e01. setup delegates to WiFiManager autoConnect; startConfigPortal delegates to the portal; loop calls process; reboot/reset/disable delegate to manager methods. These wrappers have no diagnostic service hooks. Library-internal timing is not established here.

Read complete src/WifiHelper.cpp blob 858f441facb7ce207de6efdb55c59e6a1c8ca851. wifiStart calls clockWork.initBootShowIp when configured. The verified ClockWork method scrolls in a loop with delay(200), without diagnostic polling. The power-cycle startup portal and ordinary network setup/IP display need explicit black-before-unserviced-call treatment in any wiring plan.

## Next bounded work

The former deferred-handler source blocker is resolved for the inspected regions; do not repeat the failed raw fetch or claim it remains wholly unknown. Read this note with onboard-indicator-wiring-prerequisites.md for conditional upstream NVS startup evidence and actual-package validation caveats.

Prepare a separate exact-code application-wiring plan after reading the remaining declarations/adapters needed for the chosen interfaces. Cover early startup black and read-only preparation, checked timezone application, normal-mode absence, main-loop permission service, and targeted blocking-call suppression with resume/no replay. Do not unconditionally suppress on every ordinary loop iteration, which would continually discard pulses/reset frame baselines. Include tests for changed/same-string TZ, failed application, overwritten G.conf, initialization order and blocking boundaries. Distinguish targeted known boundaries from any unproven universal cadence guarantee. Plan approval must precede code changes; exact-content confirmation must precede publication. No SDK, CI or hardware validation is claimed.
