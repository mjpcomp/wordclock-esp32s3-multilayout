# GPIO48 and hostname NTP: board validation checkpoint

Date: 2026-10-20. Firmware under test: 9c1147bc327a5a3f1f3485d434e22c4d07830bcb, BOARD_ONLY. Continues gpio48-board-validation-and-dns-diagnostics.md. Evidence below is user-supplied board/PC output and observations, not an independently captured hardware test.

## DNS incident resolved
Hostname-based synchronization initially failed, while a numeric address for the same server worked. The ESP32 reported the router as its primary DNS server. Explicit PC queries to that resolver timed out for both time.windows.com and pool.ntp.org. The user found AdGuard Home had crashed on the connected GL.iNet router, restarted it, and confirmed resolution through the router recovered.

The user restored time.windows.com in the clock UI and performed one restart. Boot read back the hostname and Pacific timezone. After WiFi connected and setup completed, the device logged:

```text
Set new time: 11:26:50 (time.windows.com)
[TIME-DIAG] ms=11116 wifi_status=3 epoch=1792520810 time_valid=1 ntp_events=1
[TIME-DIAG] configured_ntp=time.windows.com timezone=PST8PDT,M3.2.0,M11.1.0
2026-10-20 11:26:50 (-0700)
```

Subsequent clock lines advanced normally. This validates the device's hostname-based NTP path after resolver recovery and closes this observed failure as a router DNS-service outage. Do not describe it as missing firmware DNS support. No firmware DNS override, alternate resolver or hardcoded server-IP fix was needed. A secondary DNS address of zero was not the demonstrated cause. Pre-connection zero network fields in the earliest report must not be mistaken for the connected configuration.

## Accumulated observed passes
- Standalone raw GPIO48 RGB/white/off test passed with Arduino-ESP32 3.3.12 and 2.0.17.
- Integrated BOARD_ONLY boot, provisioning, web configuration round-trip, RTC suppression and brightness-sensor suppression were observed.
- NTP synchronization using a numeric address passed. Hostname-based synchronization now also passed after router recovery.
- Pacific POSIX timezone persisted through reboot and produced UTC-7 local time on the tested date. A future DST transition was not exercised.
- Amber blinking before synchronization and green breathing afterward were observed. The user's initial solid-green description was corrected; do not reopen it as an animation defect.
- The passive diagnostic firmware built successfully according to the user's Actions report and produced live TIME-DIAG output on the board.

## Remaining work and limits
The complete clock is not certified finished or generally flash-ready. PSRAM health, all peripheral isolation paths, RTC_ONLY hardware, fault states, reconnect scenarios, overlay coverage and long-duration stability have not all been validated. Blocking startup/portal calls can still pause diagnostic animation.

Next software checkpoint should be scoped and reviewed before edits: quieter optional clock-tick logging while retaining useful diagnostics; a friendly region/timezone selector with advanced POSIX input; explicit live application and status reporting for NTP-server changes. No implementation plan or code for those features is approved by this documentation commit. Preserve the existing BOARD_ONLY/RTC_ONLY policy and normal matrix driver. Keep secrets out of logs and future checkpoints.

Resume from the working hostname configuration and diagnostic firmware. Do not ask the user to repeat the standalone colour/core tests, rewire GPIO48, bridge the factory-populated resistor, or install a public DNS workaround to solve this resolved incident.
