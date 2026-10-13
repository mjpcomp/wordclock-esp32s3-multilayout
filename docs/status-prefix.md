# Optional leading status pixel

Source-level driver and runtime integration is present on feature/optional-status-prefix. Default OFF. Not yet verified with a real ESP32-S3 firmware build or hardware.

## Configuration

The default in include/LedStatusPrefix.h is:

```cpp
#define WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL 0
```

Use 0 for ordinary installations with no extra first pixel. To opt in, append this flag to the selected PlatformIO environment's existing build_flags (do not replace other flags):

```ini
-DWORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL=1
```

Alternatively edit the header default before compiling. The setting must be 0 or 1 and consistent across translation units. Defining it locally in an unrelated .cpp file is not sufficient. There is no web toggle or saved-settings schema change. Arduino IDE packaging and the ESP32-S3 build target remain separate pending work.

## Numbering and count

The strip constructor's pixelCount stays logical; do not add one yourself. The adapter allocates pixelCount + prefix count. Logical i maps to physical i when disabled, or i+1 when enabled. For 114 logical pixels: 114 physical when disabled, 115 when enabled. Minute-dot logical indices 110..113 become physical 111..114 only when enabled. If a caller allocates a larger logical buffer, it also grows by one; this option does not reduce it to 114.

Do not renumber layout tables, serpentine coordinates, minute arrays or transition indices. Reads, writes and individual clears use the same driver mapping. Invalid logical operations are ignored and invalid reads return black. Ordinary logical clears do not access the prefix. Counts must fit uint16_t after adding the prefix; assert checks are not production validation when NDEBUG is defined.

## Automatic status colors

The main loop now services the indicator after normal rendering. State is polled at most every 250ms; output is requested only when its scaled color changes. Driver deletion resets the cache so recreation at the same address is handled. The time-set callback records an atomic marker when the existing validity threshold is satisfied. With the option OFF, runtime implementation is excluded and hooks are no-ops.

Priority is top-to-bottom; brightness may dim or hide every color:

| Color | Meaning |
| --- | --- |
| Pulsing blue | No usable time under the existing rule, and Wi-Fi disconnected |
| Red | Wi-Fi connected, but no usable time under the existing rule |
| Orange | Time usable, but RTC was not detected at startup |
| Amber | Time usable, RTC detected at startup, Wi-Fi disconnected |
| Cyan | Time usable, RTC detected, Wi-Fi connected; no valid time-set callback observed this boot |
| Green | Time usable, RTC detected, Wi-Fi connected; valid time-set callback observed this boot |

The existing time rule is time(nullptr) > 100000000, not strict calendar/RTC validation. RTC detection is not a continuous health check, battery test or lost-power check. The callback marker is not proof of recent NTP synchronization; ESP8266's generic time-set callback can also reflect manual setting. It remains set for the boot. A frozen green indicator is not independent evidence that the controller is healthy.

Status scales with the existing foreground brightness calculation, including manual/hourly/automatic brightness. Zero brightness hides it. It is not a standalone power LED and begins normal runtime updates after setup completes, not throughout potentially blocking setup.

## Dedicated status access

```cpp
if (activeLedStrip->setStatusPixel(RgbColor(0, 20, 0))) {
    activeLedStrip->show();
}
```

Requires a valid initialized activeLedStrip. The setter returns false when disabled and does not transmit on its own. Automatic runtime policy may replace a manually assigned status color on a later poll. Enabled prefixes initialize black. Show forwards to NeoPixelBus; host tests do not establish real-library dirty-buffer behavior or timing.

WS2812B RGB output needs a compatible RGB prefix pixel. RGBW software mapping requires compatible RGBW prefix hardware; do not prepend the selected RGB WS2812B to a 32-bit RGBW stream. Software does not validate or guarantee the diode voltage-drop workaround.

## Tests and validation

Run with g++ available:

```text
python tests/test_status_prefix.py
python tests/test_prefix_status_policy.py
```

The adapter runner compiles the production headers with mocked platform/NeoPixelBus dependencies. It checks default OFF, explicit 0/1, invalid flag rejection, RGB/RGBW conversions, constructor forms, logical counts 0/1/114/300, mapping, invalid accesses, matrix clearing without prefix loss and explicit status/show calls. The policy runner checks priority, pulse, brightness, cache timing/reset, null driver and millis rollover.

Preparation checks passed, including deliberate default-ON regression detection and mocked runtime checks for disabled/enabled behavior. The checked-in policy runner does not execute the entire main loop. These tests do not replace existing Mirc0 layout tests, real firmware compilation, formatting checks or hardware verification. No firmware/electrical validation claim is made.
