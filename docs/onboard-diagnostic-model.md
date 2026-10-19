# Onboard diagnostic model contract

Palette, timings and priorities approved on October19,2026. Scope of this
checkpoint: pure timestamp-driven logic only. It does not construct a NeoPixel
bus, select GPIO48, transmit pixels or connect runtime hooks. The external-prefix
status policy is unchanged.

## Inputs and truthfulness
Network is Offline, Connecting, AccessPoint or Connected. Clock is Invalid, Rtc
or Ntp: valid time with an observed source, not ongoing accuracy. RTC detection
is an observation, not continuous RTC-health verification. RTC expectation must
be false for BOARD_ONLY and true for RTC_ONLY, derived from the immutable profile,
not arbitrary web pin settings. A reported application fault or invalid enum
selects Fault. The model cannot detect electrical faults or strip acknowledgements.

## Approved baselines
Channel values are semantic RGB, at most20 out of255. Physical colour order and
brightness still need validation with the separate GPIO48 driver.

| Baseline | Pattern | RGB while lit |
|---|---|---|
| Fault | Red double blink:100ms on/100off/100on,1s period |20,0,0|
| AccessPoint | Blue double blink, same timing |0,0,16|
| Connecting | Amber triangular breathe,2s period |R2..18,Gceil(R/3),B0|
| Offline | Blue100ms blink every2s |0,0,12|
| RTC expected but not detected | Amber double blink,1s period |18,6,0|
| Connected, time invalid | Amber100ms blink every1s |18,6,0|
| Connected, valid RTC-sourced time | Cyan triangular breathe,2s |0,floor(level/2),level; level2..12|
| Connected, valid NTP-sourced time | Green triangular breathe,2s |0,level,0; level2..12|

Priority: Fault > AP > Connecting > Offline > expected RTC missing > invalid time
> valid clock source. Missing RTC is not a warning in BOARD_ONLY. Patterns restart
on baseline changes, not every sample.

## Approved bounded overlays
Only valid-clock baselines display overlays. All other states mask them; masked
events still expire and expired events are not replayed.
- Observed software time sync: white20,20,20 for180ms, at most once/5s.
- Changed software frame: magenta16,0,20 for80ms, at most once/1s.
- Time sync takes priority over a simultaneous frame event.
Frame events must come from changedFrames, not repeated showRequests, and never
mean that a physical strip acknowledged output. Rejected repeated events do not
extend a pulse. Rate limits preserve baseline visibility under event storms.

## Ownership and integration
The main loop owns the controller. Async callbacks must signal an atomic/mailbox;
they must not mutate this model or transmit the LED directly. Supply advancing
uint32 millisecond timestamps and poll regularly (no unobserved full wrap interval).
There are no delays, clock reads, allocation, waits or I/O. Timestamp zero is valid;
reset drops old events. The future sink should sample sufficiently often for80ms
pulses (target20ms tick), cache unchanged colours and enforce GPIO48 separately.

Host tests cover96 valid combinations, invalid enums, wave boundaries, priorities,
simultaneous/masked/expired events, event storms, reset and wrap. This is not
physical LED, RTC-accuracy or Wi-Fi/main-loop validation. The restricted sink and
runtime integration require a separate checkpoint. No flash-readiness claim.
