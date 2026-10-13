# ESP32-S3 build phase: YD-ESP32-23 N16R8

Active repository: mjpcomp/wordclock-esp32s3-multilayout.
Working branch: feature/optional-status-prefix.

The new YD_ESP32S3_N16R8 environment is the default build environment. It extends the existing ESP32 environment, retains its pinned espressif32 6.9.0 platform, libraries and asset-generation script, and selects the ESP32-S3 board profile with 16 MB quad flash / 8 MB octal PSRAM settings. It does not enable the optional leading pixel.

Build explicitly with:

```text
pio run -e YD_ESP32S3_N16R8
```

Node/npm are still needed for the existing Grunt-generated web assets. A successful INI parse or JavaScript syntax check is NOT a successful PlatformIO/firmware build.

Do not flash this intermediate profile yet. Registration/default selection of the Mirc0 English layout, board GPIO defaults and the English layout label remain pending. The WORDCLOCK_BOARD_YD_ESP32S3_N16R8 flag is reserved for that following board-default patch; the current Config.h does not consume it yet. Existing defaults are still LED GPIO3, disabled ESP32 I2C and the German alternative layout. Old EEPROM settings are preserved and may override future defaults; do not change SERNR or erase flash automatically.

The intended next defaults are LED GPIO5, RTC SDA GPIO8 / SCL GPIO9, GRB, DS3231, one LED per letter and serpentine rows. Buttons remain disabled. USB/upload/serial behavior must be checked on the actual board/connector; this patch does not force USB CDC flags or an upload port.

The browser UI now uses English when no explicit query-string or saved cookie language choice is present. Other languages remain selectable. Browser language alone no longer overrides the English default.

Review finding: CLOCK_TYPES_LIST has ID35 before its final ID34 entry, but the old implicit ClockTypeDefMax was35, incorrectly rejecting the registered ID35. The forthcoming registry patch must preserve IDs, add Mirc0 as36, and fix max/validation. The imported LED factory already selects NeoEsp32Rmt0Ws2812xMethod for ESP32; verify S3 compilation before replacing it. It currently allocates MAX_LED_COUNT=300 logical pixels in Normal mode; prefix mode adds one to that allocation rather than assuming an exact115-pixel frame.

Future comments/docs should be English. Retain compatibility-sensitive names/keys and upstream attribution; explain inherited German names in English comments instead of blind renaming.
