# Board validation and passive DNS/NTP reporting

Baseline: fec45638cfe5a01f9aad0de8bcb428e647bad0de. Observations supplied by the user on 2026-10-20.

## Observed passes
- Standalone raw-GPIO48 RGB/white/off test passed on Arduino-ESP32 3.3.12 and 2.0.17; the second log confirmed the core path and verified upload.
- Integrated BOARD_ONLY firmware, bootloader and partition hashes matched the supplied manifest before flashing. Boot and WiFi provisioning completed; RTC and brightness-sensor test-policy suppression were logged.
- The Pacific POSIX timezone persisted across restart. With server hostname time.windows.com no successful sync was observed; the same server's PC-resolved IPv4 address produced a device SNTP notification and advancing local time at UTC-7.
- Integrated amber blinking before sync and green breathing after sync were observed. The user's initial solid-green description was explicitly corrected. Colour/animation is not an unresolved defect.
- PC DNS and NTP tests succeeded. This narrows suspicion to the board hostname/resolver path but does not prove missing DNS support or identify a specific resolver failure.

## This diagnostic-only change
The isolated application adapter emits [TIME-DIAG] reports on first service, WiFi-status or observed-SNTP-event-count changes, and every 30 seconds. Reports are at least one second apart. Fields: millis, WiFi status, epoch/validity threshold, observed NTP count, configured server, timezone, local IP, gateway and both reported DNS addresses. The callback only increments an atomic count after forwarding the event; Serial output stays in the main task. Configured server is not claimed to be the active resolved endpoint. Normal mode remains no-op.

No DNS override, lookup probe, SNTP reconfiguration, EEPROM edit, extra task or GPIO change is introduced. Existing per-second GENERAL_VERBOSE clock output is unchanged; [TIME-DIAG] lines are distinguishable within it. Live NTP-setting application and a friendly timezone selector remain separate work. This patch is not the DNS fix.

## Validation and resume
Local g++ C++11 warnings-as-errors and undefined/bounds-sanitized interface fixtures passed in modes0/1/2, including fields, callback deferral, event/WiFi triggers, minimum/periodic intervals, wrap and continued sink service. The original runtime regression assertions are retained; their existing CI entry invokes the new report test, requiring no workflow edit. No new target builds or device checks ran locally. Wait for both isolated CI builds before using a new artifact, and verify its new hashes; do not reuse old manifest hashes for a new binary.

Next: collect reports after a connected boot with the currently working numeric server. Inspect DHCP DNS values before selecting a hostname test/probe. Do not replace resolvers blindly. A hostname retry must be correlated with device-side DNS and sync events. Preserve the working numeric-server result as a temporary diagnostic reference, not a permanent hardcoded fix. Existing blocking-portal limitations and untested peripheral cases still apply.
