# Dormant typed commands and deferred mailbox

This is a typed C++ control foundation, not a JSON/WebSocket endpoint or application activation. No production caller/instance is added. Existing brightness callbacks, command IDs, startup, GPIO and UI remain untouched.

## Service and ownership
Service exclusively owns its RAM Owner; use one serialized control context and do not share its backend with another writer. Constructor does no IO. begin(nonzeroSession) performs one read-only owner startup load; repeated same-session begin is inert, a different session is rejected. True means service initialization, not healthy storage. Ordinary snapshots, Snapshot requests and permission reads are RAM-only. No Store escape hatch exists.

The application must supply a session different across service lifecycles. This foundation does not generate entropy, persist a boot counter or guarantee global uniqueness. Reusing a session can defeat cross-lifecycle stale protection. Future wire adapters must encode the uint64 session without JavaScript-number precision loss, e.g. as a validated fixed-width string. Tokens are concurrency metadata, not authentication or settings-transfer data.

Each stateful request carries session/view and expectedRevision; Reload needs the session/view only. Invalid requests and stale/mismatched/fenced writes perform no backend IO. View starts at1, advances BEFORE each possible Reload/Save/Reset operation even if it fails, and never wraps. Counter exhaustion blocks further storage operations; snapshots remain available. It does not itself change accepted logical pattern permission.

## Known state, faults and recovery
Replies distinguish local Code from an attempted Store result and include a cached owner snapshot. Snapshot means cached observation, not a fresh disk read. Non-attempted replies have storageAttempted=false; their result field is not a storage outcome. A cached accepted revision can differ from the next known reset base.

Verified Ok establishes the accepted record revision. Explicitly observed Missing/ResetRequired establishes reset base0 without discarding an older accepted owner record; the older owner remains faulted after lineage loss. Save is blocked while owner is faulted; explicit confirmed Reset may use known base0. Unknown IO/write/readback outcomes or storage conflicts fence further Save/Reset until explicit Reload. Neither cached Get nor a new client snapshot clears that fence.

This prevents stale requests within a non-reused service session even when record revision returns to1 after loss/reset (ABA). It assumes exclusive serialized access; a foreign writer reusing identical record revisions without an observed reload is outside this guarantee. There is no automatic retry, rollback, key erase or wrong-type repair. A rejected reset stays a failure; physical darkness still belongs to future hardware wiring.

## Four-entry mailbox
Enqueue copies a fixed-size envelope, route connection generation and1..32-character alphanumeric/hyphen/underscore correlation ID. It performs no service/storage/network work. Full or invalid enqueue returns false without eviction. The consumer must explicitly call consumeOne; it processes at most one command and checks the supplied route/current-connection predicate before service execution. Stale or disconnected routes are dropped without storage IO.

This mailbox is not a mutex, ISR-safe queue or cross-task transport. Producer/consumer/callback access must be serialized or protected by the future integration layer. Current-route and sender callbacks must not reenter service/mailbox; their references are borrowed only during the synchronous call. Connection generation assignment and non-reuse are caller responsibilities. Dequeue validation is not an atomic guarantee against a later disconnect. A completed write cannot be undone if its response fails; the item is consumed, never replayed automatically. Client reconciliation must reload rather than resubmit an assumed failed save.

## Evidence and deferred work
Host tests cover RAM-only polling, no constructor/invalid/stale IO, two competing views, different boot sessions, loss/reset ABA, uncertain writes before/after persistence, readback faults, explicit recovery, counter helper exhaustion, bounded FIFO copies/overflow, reconnect drops and reply failure without replay. The existing SDK fixture additionally parses the two new headers; its original real NVS link gate and empty setup/loop remain unchanged. This does not validate socket routing, real session generation, JSON schema, runtime storage or hardware.

No new dependencies are added. Existing CLI/platform pins, read-only CI and the repaired job-env context remain unchanged. JSON framing/validation, live socket routing, lifecycle and session generation, configured-timezone readiness, startup/priority black/cooperative blocking/no replay, GPIO48/UI integration and physical acceptance require later plans. Issues #3/#4 remain open.
