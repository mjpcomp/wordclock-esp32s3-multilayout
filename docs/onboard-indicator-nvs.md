# Dormant onboard indicator NVS adapter

This adds an adapter implementation, not application activation. It is not instantiated by setup, diagnostics, a singleton, a web route or a background task. Existing firmware output and startup behavior remain unchanged.

The adapter exclusively names wc-onboard/policy in the existing default NVS partition, separate from brightness wc-bright/schedule. This is namespace isolation, not a separate partition or flash encryption. No credentials, brightness records or settings-transfer keys are read or written by this adapter.

Construction performs no IO. The application/framework must initialize NVS; this adapter never initializes, deinitializes or erases it. Missing namespace/key is Missing only during open/initial lookup. Wrong stored type or non-24-byte blob is Invalid. Other failures, including a value changing/disappearing during the second read, are Failed. Returned size is zero on every unsuccessful read. Every successfully opened handle is closed exactly once.

Writes accept only a canonical 24-byte WCOS record; invalid buffers cause no NVS calls. A valid request opens read-write, sets once, commits only if set succeeded, then closes. False is an uncertain outcome, not a promise that flash stayed unchanged. Store still performs its own independent canonical readback before reporting success or adopting a record. Callers remain serialized; these operations do not provide cross-task locking or globally unique revision epochs.

There is no automatic erase or repair of wrong-type keys. If NVS rejects an explicit reset, Store reports failure and the owner stays faulted. A separate repair design would be required to authorize key removal; no successful recovery is claimed from that failure.

The host runner checks portable inclusion without nvs.h and ESP32-guarded code with a synthetic SDK-shaped header. It verifies namespace/key routing, length/type/error mapping, bounded reads, handle closure, no constructor/boot/read-path writes, canonical write rejection, commit failures before/after persistence, verified adoption, conflicts, explicit reset and faulted-owner behavior. These tests are not real SDK compilation, NVS persistence, reboot, power-loss or physical validation.

SDK compilation and integration, protocol/time/GPIO/UI activation and physical acceptance remain later milestones. Preserve all isolated-mode guards, timezone readiness, early/priority black and no-replay requirements. Issues #3/#4 remain ongoing; no settings-transfer implementation is added.
