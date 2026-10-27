/**
 * Stateless reader for additive scheduler reply capability metadata.
 * Call ONLY after the client accepts the correlated reply for the current socket
 * generation. Envelope checks here do not authenticate or correlate a reply.
 * Missing/invalid metadata fails closed; never inherit facts across reconnects.
 * These are compile-time facts, NOT clock validity, runtime binding, selected
 * strip backend, electrical output, or permission to activate either feature.
 * No DOM, socket, storage, timer, mutation, or automatic feature enabling.
 */
(function(root, factory) {
	"use strict";
	if (typeof module === "object" && module.exports) module.exports = factory();
	else root.readWordclockScheduleCapabilities = factory();
}(typeof window !== "undefined" ? window : this, function() {
	"use strict";
	function own(value, key) { return Object.prototype.hasOwnProperty.call(value, key); }
	function object(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
	function unavailable(state) {
		return Object.freeze({ metadataState: state, configurationProtocol: false, rendererCacheCompiled: false, scheduleOutputCompiled: false });
	}
	return function(reply) {
		if (!object(reply) || reply.command !== "brightness-schedule" || reply.schema !== 1) return unavailable("invalid");
		if (!own(reply, "capabilities")) return unavailable("missing");
		const facts = reply.capabilities;
		const names = ["configurationProtocol", "rendererCacheCompiled", "scheduleOutputCompiled"];
		if (!object(facts) || !own(facts, "schema") || facts.schema !== 1 || names.some(function(name) { return !own(facts, name) || typeof facts[name] !== "boolean"; })) return unavailable("invalid");
		// Ignore unknown additive fields; only this explicitly validated schema is read.
		return Object.freeze({ metadataState: "valid", configurationProtocol: facts.configurationProtocol, rendererCacheCompiled: facts.rendererCacheCompiled, scheduleOutputCompiled: facts.scheduleOutputCompiled });
	};
}));
