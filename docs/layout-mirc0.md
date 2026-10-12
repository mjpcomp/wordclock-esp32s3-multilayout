# Mirc0. English layout adapter

Creator and physical front: [Mirc0.](https://makerworld.com/en/@Mirc0), including the trailing period. Original project: https://makerworld.com/en/models/2461080-word-clock-with-esp32-rtc-web-interface

The exact front is documented in EN10x11.mirc0.hpp. The supplied word indices match that face with serpentine wiring: even rows left-to-right, odd rows right-to-left. All 21 original word groups were checked against the printed letters. The adapter converts physical indices into visual positions and then into upstream right-origin bit columns.

- 10 rows x 11 columns, indices 0-109; minute dots 110-113.
- For the original wiring, use Normal build, MeanderRows enabled, no extra LEDs per row or rotation. Hardware verification is still required.
- Word drawing excludes WIFI indices 7-10. Full-matrix modes can use those cells; a separate status-overlay policy is pending.
- Seven-dot, corner-dot, frame, A-quarter and birthday-word capabilities are not advertised.

Status: class and host test only, not registered/default/selectable yet. Registry, S3 defaults and UI handling follow separately. No target firmware build or hardware test has been performed.

Run: python tests/test_mirc0_layout.py (requires g++). The test compiles the real imported ClockType plus adapter with platform/global mocks; checks visual words and all 1440 physical masks, dots and capabilities; uses bounds/undefined sanitizers. It does not execute the full ClockWork time renderer. Reintroducing the old row-major assumption was tested and correctly fails the visual test.

This adds an adapter and hardware mapping, not maker firmware logic or 3D files. The generic upstream English layout remains unchanged.
