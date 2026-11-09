(function(global) {
	"use strict";
	function object(value) {
		return value !== null && typeof value === "object" && !Array.isArray(value);
	}
	function fields(value, names) {
		return object(value) && Object.keys(value).length === names.length && names.every(function(name) { return Object.prototype.hasOwnProperty.call(value, name); });
	}
	function uint(value, maximum) {
		return Number.isInteger(value) && value >= 0 && value <= maximum;
	}
	function booleans(value, names) {
		return names.every(function(name) { return typeof value[name] === "boolean"; });
	}
	function valid(value) {
		const root = ["command", "schema", "requestId", "action", "status", "initialized", "hasAccepted", "acceptedRevision", "observedStorageFault", "pendingEvaluation", "lastStorageResult", "sample", "backend"];
		if (!fields(value, root) || value.schema !== 1 || value.action !== "get" || value.status !== "snapshot") return false;
		if (!booleans(value, ["initialized", "hasAccepted", "observedStorageFault", "pendingEvaluation"]) || !uint(value.acceptedRevision, 4294967295)) return false;
		if (value.hasAccepted !== (value.acceptedRevision > 0) || (value.hasAccepted && !value.initialized)) return false;
		if (["ok", "missing", "reset-required", "read-failed", "invalid-input", "conflict", "revision-exhausted", "write-uncertain", "readback-uncertain"].indexOf(value.lastStorageResult) < 0) return false;
		const backend = value.backend;
		if (!fields(backend, ["kind", "cacheCompiled", "outputCompiled", "rendererAttached"]) || ["unknown", "none", "virtual", "physical"].indexOf(backend.kind) < 0) return false;
		if (!booleans(backend, ["cacheCompiled", "outputCompiled", "rendererAttached"])) return false;
		if ((backend.outputCompiled || backend.rendererAttached) && !backend.cacheCompiled) return false;
		if (backend.rendererAttached && (backend.kind === "none" || backend.kind === "unknown")) return false;
		const sample = value.sample;
		if (sample === null) return true;
		if (!value.initialized || !fields(sample, ["ageMs", "gain", "revision", "scheduled", "pausedAutomatic", "waitingForTime", "storageFault", "automatic", "masterOn", "timeValid"])) return false;
		return uint(sample.ageMs, 4294967295) && uint(sample.gain, 10000) && uint(sample.revision, 4294967295) && sample.revision <= value.acceptedRevision && booleans(sample, ["scheduled", "pausedAutomatic", "waitingForTime", "storageFault", "automatic", "masterOn", "timeValid"]);
	}
	function create(root, options) {
		const button = root.querySelector("[data-runtime='refresh']");
		const notice = root.querySelector("[data-runtime='status']");
		const values = root.querySelector("[data-runtime='values']");
		let session = null;
		let generation = 0;
		let sequence = 0;
		let pending = null;
		let destroyed = false;
		function clear() {
			if (pending !== null) options.clearTimeout(pending.timer);
			pending = null;
		}
		function display(message, value) {
			notice.textContent = message;
			button.disabled = destroyed || !session || !session.opened || session.socket.readyState !== 1 || pending !== null;
			values.textContent = "";
			if (!value) return;
			const sample = value.sample;
			const lines = ["Initialized: " + value.initialized, "Accepted revision: " + value.acceptedRevision, "Evaluation pending: " + value.pendingEvaluation, "Observed storage fault: " + value.observedStorageFault, "Last storage result: " + value.lastStorageResult];
			if (sample === null) lines.push("Evaluated sample: unavailable (not yet sampled)");
			else lines.push("Evaluated revision: " + sample.revision, "Evaluated gain: " + (sample.gain / 100).toFixed(2) + "% (model value, not physical brightness)", "Sample age at response: " + sample.ageMs + " ms", "Scheduled model branch: " + sample.scheduled, "Paused for automatic mode: " + sample.pausedAutomatic, "Waiting for time: " + sample.waitingForTime, "Sample storage fault: " + sample.storageFault, "Sample automatic/master/time valid: " + sample.automatic + "/" + sample.masterOn + "/" + sample.timeValid);
			lines.push("Backend: " + value.backend.kind, "Cache compiled: " + value.backend.cacheCompiled, "Schedule output compiled: " + value.backend.outputCompiled, "Renderer attached: " + value.backend.rendererAttached, "These facts do not prove output was applied or electrically acknowledged.");
			values.textContent = lines.join("\n");
		}
		function fail(message) { clear(); display(message); }
		function refresh() {
			if (destroyed || pending !== null || !session || !session.opened || session.socket.readyState !== 1) return;
			sequence += 1;
			const id = "rt_g" + generation + "_r" + sequence;
			if (!Number.isSafeInteger(sequence) || id.length > 32) { fail("Runtime request identifier exhausted; reload the page."); return; }
			const request = { id: id, session: session, timer: null };
			pending = request;
			request.timer = options.setTimeout(function() {
				if (pending === request && session === request.session) fail("Runtime snapshot unavailable: request timed out. Refresh manually to try again.");
			}, 8000);
			display("Requesting a device snapshot...");
			try {
				request.session.socket.send(JSON.stringify({ command: "brightness-runtime", schema: 1, requestId: id, action: "get" }));
			} catch (error) {
				const reason = error && typeof error === "object" ? "send failed." : "transport failed.";
				if (pending === request) fail("Runtime snapshot unavailable: " + reason + " No automatic retry was attempted.");
			}
		}
		function detach() {
			clear();
			if (session) Object.keys(session.handlers).forEach(function(name) { session.socket.removeEventListener(name, session.handlers[name]); });
			session = null;
		}
		function attach(socket) {
			if (destroyed || (session && session.socket === socket)) return;
			detach();
			generation += 1;
			if (!Number.isSafeInteger(generation)) { display("Runtime socket identifier exhausted; reload the page."); return; }
			const attached = { socket: socket, opened: false, handlers: {} };
			session = attached;
			attached.handlers.open = function() {
				if (session !== attached || attached.opened || socket.readyState !== 1) return;
				attached.opened = true;
				display("Connected. Refresh manually to read a device snapshot.");
			};
			attached.handlers.close = function() {
				if (session !== attached) return;
				attached.opened = false;
				fail("Disconnected. Runtime facts cleared.");
			};
			attached.handlers.error = function() {
				if (session !== attached) return;
				attached.opened = false;
				fail("Connection error. Runtime facts cleared.");
			};
			attached.handlers.message = function(event) {
				if (session !== attached || !attached.opened || socket.readyState !== 1 || pending === null || typeof event.data !== "string" || event.data.length > 2048) return;
				let value;
				try { value = JSON.parse(event.data); } catch (error) { if (error instanceof SyntaxError) return; throw error; }
				if (!object(value) || value.command !== "brightness-runtime" || value.requestId !== pending.id) return;
				clear();
				if (!valid(value)) { display("Runtime snapshot unavailable: invalid or unsupported response."); return; }
				display("Device snapshot received; not live and may already be out of date. Refresh to update.", value);
			};
			Object.keys(attached.handlers).forEach(function(name) { socket.addEventListener(name, attached.handlers[name]); });
			display("Connecting. Runtime facts unavailable.");
			attached.handlers.open();
		}
		function destroy() {
			if (destroyed) return;
			destroyed = true;
			detach();
			button.removeEventListener("click", refresh);
			display("Runtime observer detached.");
		}
		button.addEventListener("click", refresh);
		display("Connect, then refresh to read a device snapshot.");
		return { attach: attach, destroy: destroy };
	}
	global.createWordclockRuntimeStatus = create;
}(window));
