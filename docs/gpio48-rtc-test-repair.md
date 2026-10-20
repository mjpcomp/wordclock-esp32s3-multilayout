# RTC extractor repair and integration retry

Baseline: 60debd544b52a517f3f8ce2f9580e440c7fb0fa8. User supplied the failed run log on 2026-10-19.

Failure: tests/test_rtc_isolation.py searched for the exact one-line prefix notification. The onboard integration legitimately expanded it to a block. Extraction raised ValueError before RTC assertions ran; the workflow did not reach target compilation or its automatic application commit. Do not describe that run as an RTC assertion failure or a successful build.

Repair: extract after the architecture-specific time_is_set branch, ending at the existing tm declaration. Keep RTC call-site scanning and all mode/constructor/begin/read/adjust/stale-flag/timeval assertions. Mock the added millis/NTP/RTC notification hooks. Check notification forwarding when hooks are present and reject RTC-source notification after failed settimeofday. Support both original and integrated callback layouts.

Local validation: g++ C++11 warnings-as-errors and undefined/bounds sanitizers passed all three modes for old and integrated source-section fixtures. Fixtures reconstructed the inspected sections and used a minimal policy include shim, not a full repository checkout. A negative fixture removing the RTC callback guard failed board-only compilation as intended. No firmware builds or hardware tests ran locally.

Workflow retry: update only its strict parent and exact changed-file allowlist for this three-file repair. Preserve the twelve-suite/two-target acceptance gate, branch-movement refusal and tested two-file follow-up commit. The application patch script and GPIO48 code are unchanged.

Lesson: when changing application hooks, inspect source-extracting regression tests as well as target code; avoid anchoring hardware-isolation tests to unrelated diagnostic statement formatting. After approval, inspect the retried run before claiming integration complete. Blocking-portal and physical validation limitations still apply.
