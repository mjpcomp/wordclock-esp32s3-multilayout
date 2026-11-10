# Onboard indicator core: scope and contracts

This is a dormant policy/storage-boundary/runtime-owner core, not a working quiet-hours feature. It does not instantiate a production backend, load device settings, read a clock, touch GPIO, modify the web page, or change existing output behavior. Do not claim firmware, NVS, SDK or physical validation from host tests.

## Policy
Disabled never permits patterns. Always enabled permits existing diagnostics without requiring time; it does not force steady light. Scheduled requires one or two valid daily enabled windows. Boundaries are start-inclusive/end-exclusive; midnight crossing is supported, adjacency allowed, equal endpoints and overlap rejected. Retained windows remain validated in other modes. Times are local minutes0..1439, not UTC offsets, epochs or fade events.

The proposed genuinely-missing-record default is Always enabled with zero windows, revision0 and no boot write, preserving current diagnostic permission. This is a new design choice approved with this milestone, not a pre-existing user requirement. Invalid/read-failed/uncertain state never becomes that default.

## Record
Exactly24bytes:WCOS[0..3],schema1[4],mode0/1/2[5],count[6],reservedzero[7],LE32revision[8..11],two LE16start/end slots[12..19],CRC32ofbytes0..19[20..23]. Unused slots are zero; persisted revision is nonzero. Encoding never writes a raw C++ struct. CRC is not authentication or encryption. Python struct/zlib reference vectors are embedded in the C++ test.

## Storage and ownership
One serialized caller owns Store and Owner. Constructors perform no IO. begin loads once; later reconciliation is explicit. Permission/observation reads do no backend IO. Observer callbacks copy verified records and must not reenter storage.

Save validates before reading, checks expectedRevision, increments without wrapping, writes once and requires canonical byte-for-byte readback before adoption/success. A false write can have changed storage; uncertain results force dark logical permission until explicit verified reconciliation. Missing-after-verified is a fault, not a fresh default. Invalid input/conflict/exhaustion preserves the accepted snapshot. Reset is explicit and cannot treat IO failure as permission to overwrite.

Reset of missing/corrupt data starts revision1. Consequently this revision is not a globally unique epoch and does not guarantee stale-tab detection across loss/reset of revision lineage. The later protocol/client plan must state its reconciliation/session boundary explicitly rather than claim universal stale-write exclusion. Normal valid-record compare-and-swap conflicts are tested.

## Later milestones and trackers
Issue3 tracks the full scheduler and independent GPIO48 quiet-hours feature. Hardware wiring must retain the existing isolated-mode sink boundary, load policy before startup indications, fail dark until configured local time is usable, suppress every pattern and avoid replay of suppressed events. Existing 20ms throttling also delays black: priority-black/cooperative-blocking contracts still belong to the hardware-integration plan. Do not weaken the existing adapter/startup/promotion guards.

Issue4 remains full-settings transfer after scheduler work. Include portable indicator mode/windows eventually, not raw record bytes, source revision, GPIO ownership, counters or pulse state. Preserve destination identities/local revision rules and the separately generated recovery-key design. No transfer implementation is included here.
