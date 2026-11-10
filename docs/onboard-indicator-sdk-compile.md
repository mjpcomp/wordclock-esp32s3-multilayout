# Onboard indicator real-SDK compile/link gate

This is a standalone build fixture, not application integration. It compiles the accepted indicator headers and real ESP32 NVS calls with the existing espressif32 6.9.0 platform, esp32-s3-devkitc-1 board definition and Arduino framework. The CI CLI remains the repository's existing PlatformIO 6.1.18 pin. No root platformio.ini, production source, runtime owner, GPIO adapter or existing workflow is modified.

The fixture points include_dir three levels upward to the repository include directory. It does not provide a synthetic nvs.h. Read/write wrappers are retained explicitly with GNU linker undefined-symbol roots; merely including an unused header would not prove its SDK references resolve after section garbage collection. Neither setup nor loop calls either wrapper.

A successful gate requires an actual ELF and defined symbols for both wrappers and nvs_open, nvs_get_blob, nvs_set_blob, nvs_commit and nvs_close. CI preserves the exact commit SHA, PlatformIO version, resolved configuration, installed package listing, verbose build log, defined symbols and indicator-header SHA256 values. Platform package constraints can resolve compatible package patches; the package listing records what was actually installed instead of claiming all transitive versions are frozen.

The uploaded artifact contains logs and metadata only, not firmware binaries. No upload/flash/monitor target or repository write is used. The SDK project still creates normal temporary build outputs on the CI runner. Do not flash this fixture: it is not the Word Clock application and does not implement the BOARD_ONLY/RTC_ONLY peripheral guards. No claim is made about hardware safety if someone independently flashes it.

Passing establishes only compile/link compatibility for this standalone ESP32-S3 Arduino fixture. It does not establish real NVS persistence, reboot or power-loss behavior, startup ordering, configured-timezone readiness, GPIO48 quiet-hours suppression, UI/protocol behavior, the full application's build matrix or physical acceptance. Those remain separately planned work. Existing full-application build workflows remain unchanged.

Milestones 1 and 2A retain their accepted host/core evidence. This new workflow is an additional SDK evidence gate, not a request to repeat completed manual or device checks. Issues #3 and #4 remain open. Do not activate application persistence until the later lifecycle, timing and recovery contracts are planned and approved.
