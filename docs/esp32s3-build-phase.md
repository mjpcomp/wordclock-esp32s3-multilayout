# ESP32-S3 build phase: YD-ESP32-23 N16R8

Active repository: mjpcomp/wordclock-esp32s3-multilayout.
Working branch: feature/optional-status-prefix.

YD_ESP32S3_N16R8 is the default build environment. It extends the existing ESP32 environment and retains its espressif32 6.9.0 platform, library constraints and asset-generation script. The profile selects the S3 board with 16 MB quad flash / 8 MB octal PSRAM settings. The prefix pixel stays OFF unless explicitly enabled.

```text
pio run -e YD_ESP32S3_N16R8
```

Node/npm are needed for Grunt-generated web assets. A parsed INI, host test or JavaScript syntax check is not a successful firmware build. Do not flash until the real S3 build and configuration review pass.

## Current defaults

Mirc0. English is registered as Eng10x11Mirc0, ID36, key en-10-11-mirc0, and is the sole DEFAULT_LAYOUT. Registry validation now accepts the previously rejected ID35 without renumbering existing layouts. The target profile flag selects LED GPIO5, DS3231 SDA GPIO8 and SCL GPIO9. GRB, DS3231, Normal build, four minute dots and serpentine rows remain configured. Other profiles retain their old pin defaults.

SERNR remains440; stored valid layout/pin choices can override defaults. Select Mirc0 and the correct pins explicitly in the web settings if upgrading an existing installation. Do not clear EEPROM or change SERNR just to force defaults. The UI uses English absent a saved/explicit language choice; other languages remain selectable.

The imported factory already selects NeoEsp32Rmt0Ws2812xMethod for ESP32. Verify actual S3/library compilation before replacing it. Normal mode currently allocates300 logical pixels; prefix adds one to the allocation. The physical Mirc0 face uses114 pixels, but do not assume an exact115-pixel transport frame.

## Optional buttons

Button support is already compiled in. POWER_BUTTON_PIN, MODE_BUTTON_PIN and SPEED_BUTTON_PIN remain255 (disabled). Configure verified GPIOs only when adding buttons. Enabled inputs use INPUT_PULLUP: an open switch normally reads HIGH; pressing a normally-open switch to GND reads LOW. Do not connect a button input to5V. Unconnected pull-up inputs are not a meaningful current-draw concern, but assigning unused pins creates unnecessary conflicts/noise exposure.

Avoid LED/RTC pins, flash/PSRAM connections, boot-strapping/USB pins and other on-board uses. The inherited validation still has legacy pin-range limits; do not assume every exposed S3 pin can be selected safely. Review the actual N16R8 pinout before choosing button GPIOs. This update does not assign buttons or change their actions.

## Checks and remaining work

```text
python tests/test_mirc0_layout.py
python tests/test_mirc0_defaults.py
python tests/test_status_prefix.py
python tests/test_prefix_status_policy.py
```

Defaults tests use mocked platform headers. Node-based label/config checks run when Node is available. They do not execute the real i18next detector or a browser. Previous layout tests do not execute the full ClockWork renderer. Full firmware compilation, formatting, USB/upload/serial checks and hardware validation remain pending. Do not claim target readiness from host checks alone.

Maintain English comments/docs/diagnostics. Retain compatibility-sensitive identifiers and settings keys with English explanations, and preserve upstream credits/licenses.
