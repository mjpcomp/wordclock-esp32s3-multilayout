/**
 * Page controller: connects editor actions to the shared configuration client.
 * It does not open a WebSocket, query DOM, poll sensors or mutate device settings
 * on construction/edit/render. Caller supplies send(text,generation), deferred
 * setTimeout/clearTimeout, model, adapter, client and onState(snapshot, reason).
 * send must target exactly the socket generation supplied; false/throw means
 * delivery uncertain. Timers are armed BEFORE send to permit synchronous replies.
 * No automatic mutation retry. The only mutation entry points are save() and
 * confirmed reset(). open() sends a read-only get; reconnect preserves drafts
 * through the client reconciliation flow. received telemetry is not configuration.
 * Renderer onEdit should call replaceDraft(), not save(). Pending mutations make
 * canEdit false so the owner can cancel dragging by rerendering read-only.
 * Selection-only notifications use reason="selection": update numeric fields
 * without calling SVG render(), which would cancel pointerdown/drag setup.
 * onState must not throw; it receives detached data. Page owns translations and
 * field presentation. destroy cancels the deadline and invalidates its callbacks.
 */
(function(root, factory) {
	"use strict";
	if (typeof module === "object" && module.exports) module.exports = factory;
	else root.createWordclockScheduleController = factory;
}(typeof window !== "undefined" ? window : this, function(options) {
	"use strict";
	if (!options || !options.client || !options.model || !options.adapter || ["send", "setTimeout", "clearTimeout", "onState"].some(function(name) { return typeof options[name] !== "function"; })) throw new Error("Controller dependencies required");
	const client = options.client;
	const model = options.model;
	const adapter = options.adapter;
	const timeoutMs = options.timeoutMs === undefined ? 8000 : options.timeoutMs;
	if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 60000) throw new Error("Deadline must be 1..60000 milliseconds");
	let token = null;
	let deadline = null;
	let selected = -1;
	let view = [0, 1440];
	let errorText = "";
	let destroyed = false;
	function check(condition, message) { if (!condition) throw new Error(message); }
	function cancelDeadline() {
		const old = deadline;
		deadline = null;
		if (old && old.handle !== null) options.clearTimeout(old.handle);
	}
	function snapshot() {
		const state = client.snapshot();
		const count = state.draft ? state.draft.events.length : 0;
		if (selected >= count) selected = count - 1;
		const mutation = state.pending && state.pending.action !== "get";
		return Object.assign({}, state, { selected: selected, view: view.slice(), errorText: errorText, destroyed: destroyed, canEdit: !destroyed && Boolean(state.draft) && !mutation, canSave: !destroyed && state.connected && !state.pending && !state.needsReload && !state.resetRequired && Boolean(state.draft), canDiscard: !destroyed && !state.pending && !state.needsReload && Boolean(state.saved) && state.saved.revision > 0 && state.dirty });
	}
	function emit(reason) { options.onState(snapshot(), reason || "state"); }
	function action(run, reason) {
		check(!destroyed, "Controller destroyed");
		try { run(); errorText = ""; } catch (error) { errorText = error.message || "Editor operation failed"; emit(); return false; }
		emit(reason);
		return true;
	}
	function pendingMatches(generation, identifier) {
		const pending = client.snapshot().pending;
		return !destroyed && token === generation && pending && pending.id === identifier;
	}
	function request(actionName, confirmReset) {
		check(!destroyed, "Controller destroyed");
		const requestValue = client.begin(actionName, confirmReset);
		const generation = token;
		const identifier = requestValue.requestId;
		check(!deadline, "A request deadline already exists");
		const timer = { generation: generation, identifier: identifier, handle: null };
		deadline = timer;
		try {
			timer.handle = options.setTimeout(function() {
				if (deadline !== timer || !pendingMatches(generation, identifier)) return;
				deadline = null;
				client.timeout(generation, identifier);
				errorText = "Request timed out; reload before retrying a save.";
				emit();
			}, timeoutMs);
		} catch (error) {
			deadline = null;
			client.timeout(generation, identifier);
			errorText = "Could not establish a request deadline: " + error.message;
			emit();
			return false;
		}
		// UI callbacks are kept outside the transport catch boundary. A UI error
		// must not be misreported as uncertain device delivery.
		let delivery;
		try { delivery = options.send(JSON.stringify(requestValue), generation); } catch (error) { delivery = false; errorText = error.message ? "Transport send failed; delivery uncertain." : "Delivery uncertain."; }
		if (delivery === false && pendingMatches(generation, identifier)) {
			cancelDeadline();
			client.timeout(generation, identifier);
			errorText = "Delivery uncertain; reload before retrying a save.";
		}
		emit();
		return delivery !== false;
	}
	function requestAction(name, confirmed) {
		check(!destroyed, "Controller destroyed");
		errorText = "";
		try { return request(name, confirmed); } catch (error) { errorText = error.message || "Request rejected"; emit(); return false; }
	}
	return Object.freeze({
		/** Call from existing socket onopen; no new socket or mutation is created. */
		open: function() {
			check(!destroyed, "Controller destroyed");
			cancelDeadline();
			token = client.connect();
			requestAction("get");
			return token;
		},
		/** Only current socket close may cancel the active request. */
		close: function(generation) {
			if (destroyed || generation !== token) return false;
			cancelDeadline();
			client.disconnect(generation);
			emit();
			return true;
		},
		/** Return false for unrelated/malformed traffic; deadline handles lost replies. */
		receive: function(generation, input) {
			if (destroyed || generation !== token) return false;
			let reply;
			try { reply = typeof input === "string" ? JSON.parse(input) : input; } catch (error) { if (error instanceof SyntaxError) return false; throw error; }
			if (!reply || reply.command !== "brightness-schedule") return false;
			const consumed = client.receive(generation, reply);
			if (!consumed) return false;
			cancelDeadline();
			errorText = "";
			emit();
			return true;
		},
		save: function() { return requestAction("save"); },
		reload: function() { return requestAction("get"); },
		reset: function(confirmed) { return requestAction("reset", confirmed); },
		reconcile: function(choice) { return action(function() { client.reconcile(choice); }); },
		/** Use for a completed graph edit. No send or timer is started. */
		replaceDraft: function(value, index) {
			return action(function() {
				check(snapshot().canEdit, "Draft is not editable");
				client.edit(model.validate(value));
				selected = Number.isInteger(index) ? index : -1;
			});
		},
		updateSelected: function(start, end, target, transition) {
			return action(function() {
				const state = snapshot(); check(state.canEdit, "Draft is not editable");
				const result = adapter.edit(state.draft, selected, start, end, target, transition);
				client.edit(result.schedule); selected = result.index;
			});
		},
		add: function(start, target) {
			return action(function() {
				const state = snapshot(); check(state.canEdit, "Draft is not editable");
				const result = adapter.add(state.draft, start, target);
				client.edit(result.schedule); selected = result.index;
			});
		},
		removeSelected: function() {
			return action(function() {
				const state = snapshot(); check(state.canEdit, "Draft is not editable");
				client.edit(adapter.remove(state.draft, selected)); selected = -1;
			});
		},
		setAllDay: function(percentText) {
			return action(function() {
				const state = snapshot(); check(state.canEdit && !state.draft.events.length, "All-day mode requires no events");
				client.edit({ defaultTenths: model.parsePercent(percentText), events: [] });
			});
		},
		discard: function() {
			return action(function() {
				const state = snapshot(); check(state.canDiscard, "Reload and reconcile before discarding");
				client.edit(state.saved.schedule);
			});
		},
		select: function(index) {
			return action(function() {
				const state = snapshot(); check(state.draft && Number.isInteger(index) && index >= 0 && index < state.draft.events.length, "Select a valid change");
				selected = index;
			}, "selection");
		},
		setView: function(begin, end) {
			return action(function() { adapter.geometry({ defaultTenths: 0, events: [] }, begin, end); view = [begin, end]; });
		},
		snapshot: snapshot,
		destroy: function() {
			if (destroyed) return;
			cancelDeadline();
			if (token !== null) client.disconnect(token);
			destroyed = true;
		}
	});
}));
