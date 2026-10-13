# Optional leading status pixel

Implemented driver option on feature/optional-status-prefix. Default OFF.

## Configuration

The default in include/LedStatusPrefix.h is:

```cpp
#define WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL 0
```

Use 0 for ordinary installations with no extra first pixel. To opt in, append this flag to the selected PlatformIO environment's existing build_flags (do not replace other flags):

```ini
-DWORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL=1
```

Alternatively edit the header default before compiling. The setting must be 0 or 1 and consistent across translation units. Defining it locally in an unrelated .cpp file is not sufficient. There is no web toggle and no saved-settings schema change. Arduino IDE packaging and the ESP32-S3 build target remain separate pending work.

## Numbering and count

The strip constructor's pixelCount remains the logical count; do not add one yourself. The adapter allocates pixelCount + prefix count. Logical index i maps to physical i when disabled, or i+1 when enabled. For 114 logical pixels: 114 physical when disabled, 115 when enabled. Minute-dot logical indices 110..113 become physical 111..114 only when enabled. If a caller allocates a larger logical buffer, that buffer also grows by one; this option does not reduce it to 114.

Do not renumber the Mirc0 layout, serpentine coordinates, minute arrays, or transition indices. Reads, writes and individual clears are mapped at the same driver boundary. Out-of-range logical operations are ignored; out-of-range reads return black. Ordinary logical clears do not access the prefix. Constructor counts must fit uint16_t after adding the prefix; current checks use assert and are not production validation when NDEBUG is defined.

## Dedicated status access

```cpp
if (activeLedStrip->setStatusPixel(RgbColor(0, 20, 0))) {
    activeLedStrip->show();
}
```

Requires a valid initialized activeLedStrip. The setter returns false when disabled and does not transmit on its own. Enabled prefix pixels initialize black. Automatic Wi-Fi/RTC color updates are NOT connected yet; that is a separate runtime integration. Show forwards to NeoPixelBus; host tests do not establish real-library dirty-buffer behavior or timing.

For WS2812B RGB strips, use a compatible RGB prefix pixel. RGBW software mapping is tested separately but requires compatible RGBW prefix hardware; do not prepend the selected RGB WS2812B to a 32-bit RGBW stream. This option does not validate or guarantee the diode voltage-drop workaround.

## Tests and limitations

Run `python tests/test_status_prefix.py` with g++ available. Tests compile copies of the actual three production headers with mocked platform/NeoPixelBus dependencies. They check default OFF (including default-regression detection), explicit 0/1, invalid flag rejection, RGB/RGBW conversions, both constructor forms, logical counts 0/1/114/300, first/last pixels, minute-dot indices, invalid accesses, matrix clearing without prefix loss, and explicit status/show calls.

No production dependency is mocked in a firmware build. These host tests do not replace the existing Mirc0 layout tests, the real ESP32-S3 build, a formatting check, or hardware verification. No firmware or electrical validation claim is made here.
