# Mirc0. English layout adapter

Creator and physical front: [Mirc0.](https://makerworld.com/en/@Mirc0), including the trailing period. Original project: https://makerworld.com/en/models/2461080-word-clock-with-esp32-rtc-web-interface

EN10x11.mirc0.hpp implements the supplied English face with serpentine wiring: even zero-based rows left-to-right, odd rows right-to-left. The adapter converts logical strip indices to visual positions and upstream right-origin bit columns. The original word groups remain unchanged.

- 10 rows x11 columns, logical matrix indices0..109; minute dots110..113.
- Registry: Eng10x11Mirc0, ID36, instance _mirc0_en10x11, UI key en-10-11-mirc0.
- Mirc0 is the project default for new settings. Valid saved layouts are preserved.
- Use Normal build, MeanderRows enabled, no extra LEDs per row or rotation.
- Optional prefix mode shifts physical output in the driver; do not renumber this layout.
- Word drawing excludes logical WIFI cells7..10. Full-matrix modes can use them; no new in-matrix status-overlay policy is added here.
- Seven-dot, corner-dot, perimeter-frame, A-quarter and birthday-word capabilities are not advertised.

The adapter is now registered and has an English UI label. Source registration/defaults and host checks are not a successful S3 firmware build or hardware verification.

Run python tests/test_mirc0_layout.py with g++. It checks the imported ClockType plus adapter with mocks, visual words, all1440 physical masks, dots and capabilities. It does not execute the full ClockWork time renderer. Also run tests/test_mirc0_defaults.py for registry/default/pin checks.

This adaptation includes mapping code, not maker firmware logic or3D model files. Other registered layouts remain available. Preserve upstream notices and the Mirc0. creator credit.
