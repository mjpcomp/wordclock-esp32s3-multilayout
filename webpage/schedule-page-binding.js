/**
 * Scheduler DOM binding, not live-page bootstrap. Requires a dedicated root with
 * data-schedule slots listed below. Future IDs must use schedule-* names without
 * brightness/slider/transition: legacy script.js binds automatic sends to those.
 * Inject controller/view factories, controllerOptions and confirmReset(). No socket
 * is created. Supply the tested capability reader in controllerOptions. Build facts
 * permit configuration UI only, never imply active/working hardware output.
 * Numeric/range controls stage local edits; Apply updates the draft, Save persists.
 * confirmReset must return literal true. text(key,fallback) optionally translates.
 * Call destroy before removing/reusing the root. Selection must not repaint SVG.
 */
(function(root, factory) {
	"use strict";
	if (typeof module === "object" && module.exports) module.exports = factory();
	else root.createWordclockSchedulePage = factory();
}(typeof window !== "undefined" ? window : this, function() {
	"use strict";
	const mounted = new WeakSet();
	return function(root, options) {
		if (!root || !root.ownerDocument || mounted.has(root)) throw new Error("Unmounted scheduler root required");
		if (!options || !options.controllerOptions || ["createController", "createTimelineView", "confirmReset"].some(function(name) { return typeof options[name] !== "function"; })) throw new Error("Page dependencies required");
		const names = ["timeline", "status", "capabilities", "changes", "start", "end", "target", "level-range", "curve", "all-day", "add", "apply", "remove", "save", "reload", "reset", "discard", "use-remote", "keep-draft"];
		const fields = {};
		names.forEach(function(name) {
			fields[name] = root.querySelector("[data-schedule='" + name + "']");
			if (!fields[name]) throw new Error("Missing scheduler slot: " + name);
		});
		const model = options.controllerOptions.model;
		const listeners = [];
		let destroyed = false;
		let view;
		function text(key, fallback) { return typeof options.text === "function" ? options.text(key, fallback) : fallback; }
		function supported(state) { return Boolean(state.connected && state.capabilities && state.capabilities.metadataState === "valid" && state.capabilities.configurationProtocol === true); }
		function editable(state) { return supported(state) && state.canEdit && !state.pending; }
		function savable(state) { return supported(state) && state.canSave && !state.pending; }
		function resettable(state) { return supported(state) && !state.pending && !state.needsReload; }
		function report(error) { fields.status.textContent = error.message || text("edit-error", "Edit rejected"); }
		const controller = options.createController(Object.assign({}, options.controllerOptions, { onState: render }));
		function render(state, reason) {
			if (destroyed) return;
			const draft = state.draft;
			const selected = draft && draft.events[state.selected];
			const canEdit = editable(state);
			fields.end.title = selected && selected.minute + selected.fadeMinutes >= 1440 ? text("next-day", "Target reached tomorrow.") : "";
			fields.status.textContent = state.errorText || text("status-" + state.status, state.status) + (state.dirty ? text("unsaved", " — Unsaved changes") : "");
			fields.capabilities.textContent = supported(state) ? text("configuration-only", "Configuration supported. Build components: cache=") + String(state.capabilities.rendererCacheCompiled) + ", output=" + String(state.capabilities.scheduleOutputCompiled) + text("not-readiness", ". Hardware readiness is not verified.") : text("unavailable", "Scheduler configuration support unavailable; reload after connecting.");
			["changes", "start", "target", "level-range", "curve"].forEach(function(name) { fields[name].disabled = !canEdit; });
			fields.apply.disabled = !canEdit || !selected;
			fields.remove.disabled = !canEdit || !selected;
			fields.add.disabled = !canEdit || draft.events.length >= model.MAX_EVENTS;
			fields.save.disabled = !savable(state);
			fields.reload.disabled = !state.connected || Boolean(state.pending);
			fields.reset.disabled = !resettable(state);
			fields.discard.disabled = !state.canDiscard;
			fields["use-remote"].disabled = fields["keep-draft"].disabled = !state.connected || Boolean(state.pending) || !state.remote;
			fields["all-day"].disabled = !canEdit || draft.events.length !== 0;
			if (draft) fields["all-day"].value = String(draft.defaultTenths / 10);
			if (reason !== "selection") {
				while (fields.changes.firstChild) fields.changes.removeChild(fields.changes.firstChild);
				const placeholder = root.ownerDocument.createElement("option");
				placeholder.value = "-1"; placeholder.disabled = true; placeholder.textContent = text("select", "Select a change"); fields.changes.appendChild(placeholder);
				if (draft) {
					draft.events.forEach(function(event, index) {
						const item = root.ownerDocument.createElement("option");
						item.value = String(index); item.textContent = model.formatTime(event.minute) + " → " + event.targetTenths / 10 + "% (" + event.fadeMinutes + " min)"; fields.changes.appendChild(item);
					});
				}
			}
			fields.changes.value = String(state.selected);
			if (selected) {
				fields.start.value = model.formatTime(selected.minute);
				fields.end.value = model.formatTime((selected.minute + selected.fadeMinutes) % 1440);
				fields.target.value = String(selected.targetTenths / 10);
				fields.curve.value = selected.fadeMinutes ? "linear" : "instant";
			} else {
				if (!fields.start.value) fields.start.value = "07:00";
				if (!fields.end.value) fields.end.value = fields.start.value;
				fields.target.value = draft ? String(draft.defaultTenths / 10) : "100";
				if (!fields.curve.value) fields.curve.value = "instant";
			}
			fields["level-range"].value = String(selected ? selected.targetTenths : draft ? draft.defaultTenths : 0);
			fields.end.disabled = !canEdit || fields.curve.value === "instant";
			if (view && reason !== "selection") {
				if (draft) view.render(draft, state.selected, state.view[0], state.view[1], canEdit);
				else view.render({ defaultTenths: 0, events: [] }, -1, state.view[0], state.view[1], false);
			}
		}
		function listen(name, type, run) {
			const element = name === null ? root : fields[name];
			function handler(event) {
				if (type === "click" || type === "submit") event.preventDefault();
				if (destroyed || element.disabled) return;
				try { run(event); } catch (error) { report(error); }
			}
			element.addEventListener(type, handler); listeners.push([element, type, handler]);
		}
		try {
			view = options.createTimelineView(fields.timeline, { model: model, adapter: options.controllerOptions.adapter, onSelect: function(index) { controller.select(index); }, onEdit: function(value, index) { return editable(controller.snapshot()) && controller.replaceDraft(value, index); }, onError: function(message) { report(new Error(message)); } });
		} catch (error) { controller.destroy(); throw error; }
		fields["level-range"].min = "0"; fields["level-range"].max = "1000"; fields["level-range"].step = "1";
		listen(null, "submit", function() {});
		listen("changes", "change", function() { if (editable(controller.snapshot())) controller.select(Number(fields.changes.value)); });
		listen("target", "input", function() { if (editable(controller.snapshot())) fields["level-range"].value = String(model.parsePercent(fields.target.value)); });
		listen("level-range", "input", function() { if (editable(controller.snapshot())) { const value = String(Number(fields["level-range"].value) / 10); model.parsePercent(value); fields.target.value = value; } });
		listen("curve", "change", function() { fields.end.disabled = !editable(controller.snapshot()) || fields.curve.value === "instant"; });
		listen("all-day", "change", function() { const state = controller.snapshot(); if (editable(state) && !state.draft.events.length) controller.setAllDay(fields["all-day"].value); });
		listen("apply", "click", function() { const state = controller.snapshot(); if (editable(state) && state.selected >= 0) controller.updateSelected(fields.start.value, fields.end.value, fields.target.value, fields.curve.value); });
		listen("add", "click", function() { const state = controller.snapshot(); if (editable(state) && state.draft.events.length < model.MAX_EVENTS) controller.add(fields.start.value, fields.target.value); });
		listen("remove", "click", function() { const state = controller.snapshot(); if (editable(state) && state.selected >= 0) controller.removeSelected(); });
		listen("save", "click", function() { const state = controller.snapshot(); if (savable(state)) controller.save(); });
		listen("reload", "click", function() { const state = controller.snapshot(); if (state.connected && !state.pending) controller.reload(); });
		listen("reset", "click", function() { if (resettable(controller.snapshot()) && options.confirmReset() === true && resettable(controller.snapshot())) controller.reset(true); });
		listen("discard", "click", function() { if (controller.snapshot().canDiscard) controller.discard(); });
		["use-remote", "keep-draft"].forEach(function(choice) { listen(choice, "click", function() { const state = controller.snapshot(); if (state.connected && !state.pending && state.remote) controller.reconcile(choice); }); });
		mounted.add(root);
		render(controller.snapshot());
		return Object.freeze({
			open: controller.open,
			close: controller.close,
			receive: controller.receive,
			snapshot: controller.snapshot,
			refresh: function() { render(controller.snapshot()); },
			destroy: function() {
				if (destroyed) return;
				destroyed = true;
				listeners.forEach(function(entry) { entry[0].removeEventListener(entry[1], entry[2]); });
				view.destroy(); controller.destroy(); mounted.delete(root);
			}
		});
	};
}));
