# Board-only schedule test candidates

These are build artifacts, not flash-ready firmware or permission to flash.

## Scope

Use the existing YD_ESP32S3_N16R8_BOARD_ONLY profile (test mode 1) for the
established Profile A stage: no external RTC or clock strip, no hardware buttons
or brightness sensors, and GPIO48 reserved for the existing onboard diagnostics.
The external clock-strip backend is expected to remain virtual. This build does
not add an independent GPIO48 schedule or use that LED as a clock-strip dimming
oracle. Ambient-light response cannot be tested while sensors are disabled.

Two artifacts are generated from the same validated source checkpoint:

- `control`: renderer cache 0, schedule output 0; default-off reference.
- `schedule-enabled`: renderer cache 1, schedule output 1; isolated candidate.

The workflow checks source files against 55c18061ace3e48272f6879d2775bba984d6dec6,
changes only the selected environment's build flags inside its checkout, and
adds compile-only assertions. Committed source gates and platformio.ini stay
unchanged. The build commit is recorded separately from that source checkpoint.
No source is pushed and no device upload target is invoked.

## Evidence before any device test

Each successful artifact contains binaries and build evidence from the existing
collector, plus `schedule-test.json`. Confirm the variant, board-only mode,
compiled project defines, source checkpoint, build commit and SHA-256 values.
The collector and schedule report must both say `flash_ready: false`.
Do not treat firmware.bin as a complete flash image or guess flash addresses.

## Separately authorized runtime checks

Before flashing, agree the exact device, firmware layout, settings backup and
recovery process. Keep the initial physical setup within Profile A: no external
RTC/strip. Then collect runtime evidence for virtual-backend/peripheral guards,
boot and web interface, NTP/timezone and demo-time separation, schedule changes,
automatic/manual routing, master off/on and restart behavior. Software show/frame
counters are not hardware acknowledgements. If required states cannot be
observed, add evidence rather than assuming a pass.

RTC-only testing and physical strip/power/wiring validation are later stages.
Nothing in this build verifies the external 300-LED strip electrically or proves
its visible brightness, and no physical-device test has been completed yet.
