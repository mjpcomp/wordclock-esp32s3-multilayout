/**
 * Draft/save client. No DOM, sockets, timers, persistence or constructor IO.
 * Inject the schedule model; the page owns transmission and request deadlines.
 * begin() returns a pending schema-1 request to send ONCE. Capture connect()'s
 * generation in callbacks. On send uncertainty use timeout(); never auto-retry.
 *
 * saved: last accepted record (not necessarily fresh). draft: local edits.
 * remote: newly read record awaiting explicit user reconciliation. A read must
 * not erase edits. Runtime telemetry is separate and must not enter this API.
 * One request at a time. Editing is locked during mutations. A save timeout,
 * disconnect or malformed reply leaves outcome unknown until reload/reconcile.
 * All returned objects are detached. Brightness and time units belong to model.
 */
(function(root, factory) {
	"use strict";
	if (typeof module === "object" && module.exports) module.exports = factory;
	else root.createWordclockScheduleClient = factory;
}(typeof window !== "undefined" ? window : this, function(model) {
	"use strict";
	if (!model || typeof model.validate !== "function") throw new Error("Schedule model required");
	let generation = 0;
	let sequence = 0;
	let connected = false;
	let saved = null;
	let draft = null;
	let remote = null;
	let pending = null;
	let reload = true;
	let resetRequired = false;
	let status = "disconnected";
	function check(condition, message) { if (!condition) throw new Error(message); }
	function copy(value) { return value === null ? null : JSON.parse(JSON.stringify(value)); }
	function canonical(value) { return copy(model.validate(value)); }
	function same(first, second) { return JSON.stringify(first) === JSON.stringify(second); }
	function failure(reason, error) {
		status = pending && pending.action !== "get" ? "outcome-unknown" : reason;
		pending = null;
		remote = null;
		reload = true;
	}
	function record(reply) {
		check(Number.isInteger(reply.revision) && reply.revision >= 0 && reply.revision <= 4294967295, "Invalid revision");
		return { revision: reply.revision, schedule: canonical({ defaultTenths: reply.defaultTenths, events: reply.events }) };
	}
	return Object.freeze({
		/** New socket generation. Caller must explicitly request a load. */
		connect: function() {
			if (pending) failure("interrupted");
			connected = true;
			generation += 1;
			reload = true;
			remote = null;
			resetRequired = false;
			status = "reload-required";
			return generation;
		},
		/** Ignore close events from obsolete sockets; retain draft after loss. */
		disconnect: function(token) {
			if (token !== generation) return false;
			if (pending) failure("disconnected");
			connected = false;
			reload = true;
			remote = null;
			if (status !== "outcome-unknown") status = "disconnected";
			return true;
		},
		/** Local-only edit. Validation failure cannot partially change state. */
		edit: function(value) {
			check(!pending || pending.action === "get", "Wait for pending mutation");
			draft = canonical(value);
		},
		/** Build request before send; reset is schedule-only and needs literal true. */
		begin: function(action, confirmReset) {
			check(connected && !pending, "Connected idle client required");
			check(["get", "save", "reset"].includes(action), "Unsupported action");
			if (action !== "get") {
				check(!reload, "Reload and reconcile first");
				check(saved || (action === "reset" && resetRequired), "Load configuration first");
				check(action !== "reset" || confirmReset === true, "Confirm schedule reset");
				check(action !== "save" || (draft && !resetRequired), "Valid draft required");
				check(!saved || saved.revision < 4294967295, "Revision exhausted");
			}
			const request = { command: "brightness-schedule", schema: 1, requestId: "g" + generation + "r" + (++sequence), action: action };
			check(request.requestId.length <= 32, "Request ID exhausted");
			if (action !== "get") request.expectedRevision = saved ? saved.revision : 0;
			if (action === "save") Object.assign(request, canonical(draft));
			if (action === "reset") request.confirmReset = true;
			check(JSON.stringify(request).length <= 2048, "Request exceeds wire budget");
			pending = { id: request.requestId, action: action, revision: request.expectedRevision, schedule: action === "save" ? canonical(draft) : null };
			status = action === "get" ? "loading" : "saving";
			return copy(request);
		},
		/** Caller-owned deadline/send uncertainty. Never retries a mutation. */
		timeout: function(token, identifier) {
			if (token !== generation || !pending || identifier !== pending.id) return false;
			failure("load-failed");
			return true;
		},
		/** Parsed JSON only; wrong socket/ID ignored, malformed mutation is uncertain. */
		receive: function(token, reply) {
			if (!connected || token !== generation || !pending || !reply || reply.requestId !== pending.id) return false;
			const operation = pending;
			try {
				check(reply.command === "brightness-schedule" && reply.schema === 1, "Bad envelope");
				const errors = ["reset-required", "read-failed", "invalid-request", "conflict", "revision-exhausted", "write-uncertain", "readback-uncertain"];
				if (errors.includes(reply.status)) {
					check(reply.action === operation.action || (reply.status === "invalid-request" && reply.action === undefined), "Wrong action");
					check(reply.status !== "reset-required" || reply.revision === 0, "Bad reset revision");
					pending = null;
					remote = null;
					reload = true;
					resetRequired = false;
					if (reply.status === "reset-required" && operation.action === "get") {
						saved = null;
						resetRequired = true;
						reload = false;
					}
					status = reply.status;
					return true;
				}
				check(reply.action === operation.action, "Wrong action");
				const expected = { get: "loaded", save: "saved", reset: "reset" }[operation.action];
				const missing = operation.action === "get" && reply.status === "missing";
				check(missing || reply.status === expected, "Wrong outcome");
				check(reply.reloadRequired === undefined && (missing || reply.draft === undefined), "Contradictory success flags");
				const next = record(reply);
				if (missing) {
					check(next.revision === 0 && reply.draft === true && next.schedule.defaultTenths === 1000 && next.schedule.events.length === 0, "Bad missing draft");
				} else check(next.revision > 0, "Stored record needs revision");
				if (operation.action !== "get") {
					check(next.revision === operation.revision + 1, "Unexpected revision");
					const wanted = operation.action === "save" ? operation.schedule : { defaultTenths: 1000, events: [] };
					check(same(next.schedule, wanted), "Saved content differs from request");
				}
				pending = null;
				resetRequired = false;
				if (operation.action === "get" && draft !== null) {
					remote = next;
					reload = true;
					status = "reconcile-required";
				} else {
					saved = next;
					draft = canonical(next.schedule);
					remote = null;
					reload = false;
					status = missing ? "unsaved-default" : reply.status;
				}
				return true;
			} catch (error) {
				failure("invalid-reply", error);
				return true;
			}
		},
		/** Explicit local adopt/rebase; keeping draft does not silently save it. */
		reconcile: function(choice) {
			check(connected && !pending && remote, "Load remote snapshot first");
			check(choice === "use-remote" || choice === "keep-draft", "Choose reconciliation action");
			if (choice === "use-remote") draft = canonical(remote.schedule);
			saved = copy(remote);
			remote = null;
			reload = false;
			status = saved.revision === 0 ? "unsaved-default" : "ready";
		},
		/** Detached state. Revision-zero defaults remain unsaved even when unchanged. */
		snapshot: function() {
			return copy({ generation: generation, connected: connected, saved: saved, draft: draft, remote: remote, pending: pending, needsReload: reload, resetRequired: resetRequired, status: status, dirty: draft !== null && (!saved || saved.revision === 0 || !same(draft, saved.schedule)) });
		}
	});
}));
