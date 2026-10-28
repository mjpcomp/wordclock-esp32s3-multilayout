/**
 * SVG timeline view. Inject shared model + timeline adapter and callbacks.
 * No storage, network, persistence, auto-save or application-global state.
 * render(schedule, selection, left, right, editable) accepts authoritative local
 * draft state. Pointer moves preview a detached candidate; only pointerup emits
 * onEdit(schedule,index). Callback may veto with false or replace state via render.
 * External render cancels active dragging; old pointer events cannot commit it.
 * Escape, pointercancel and lost capture restore the original accepted draft.
 * Enter/Space selects a handle for the page's exact numeric editor; arrow-key
 * editing is deliberately not implemented here. Page owns translation/status UI.
 * destroy() releases capture/listeners, removes owned SVG content and restores
 * attributes/styles. Caller should destroy before removing or reusing the SVG.
 */
(function(root, factory) {
	"use strict";
	const createView = factory();
	if (typeof module === "object" && module.exports) module.exports = createView;
	else root.createWordclockTimelineView = createView;
}(typeof window !== "undefined" ? window : this, function() {
	"use strict";
	const mounted = new WeakSet();
	return function(svg, options) {
		if (!svg || svg.localName !== "svg" || !svg.ownerDocument || mounted.has(svg)) throw new Error("Unmounted SVG required");
		if (!options || !options.model || !options.adapter || typeof options.onEdit !== "function") throw new Error("Model, adapter and onEdit required");
		const model = options.model;
		const adapter = options.adapter;
		const namespace = "http://www.w3.org/2000/svg";
		const previous = { viewBox: svg.getAttribute("viewBox"), role: svg.getAttribute("role"), label: svg.getAttribute("aria-label"), touch: svg.style.touchAction };
		const layer = svg.ownerDocument.createElementNS(namespace, "g");
		const listeners = [];
		let current = null;
		let selected = -1;
		let left = 0;
		let right = 1440;
		let editable = false;
		let drag = null;
		let destroyed = false;
		let revision = 0;
		function notifyError(error) {
			if (typeof options.onError === "function") options.onError(error.message || "Timeline edit failed");
		}
		function clock(minute) {
			return model.formatTime(((minute % 1440) + 1440) % 1440) + (minute >= 1440 ? " +1d" : "");
		}
		function node(name, attributes, text) {
			const item = svg.ownerDocument.createElementNS(namespace, name);
			Object.keys(attributes).forEach(function(key) { item.setAttribute(key, attributes[key]); });
			if (text !== undefined) item.textContent = text;
			layer.appendChild(item);
			return item;
		}
		function positionX(minute) { return 65 + (minute - left) * 880 / (right - left); }
		function positionY(level) { return 255 - level * 230 / 1000; }
		function paint(schedule, selection) {
			const geometry = adapter.geometry(schedule, left, right);
			while (layer.firstChild) layer.removeChild(layer.firstChild);
			for (let level = 0; level <= 1000; level += 250) {
				node("line", { x1: 65, y1: positionY(level), x2: 945, y2: positionY(level), stroke: "#e2e9f0" });
				node("text", { "x": 55, "y": positionY(level) + 4, "text-anchor": "end", "font-size": 12, fill: "#60758b" }, level / 10 + "%");
			}
			const step = right - left > 500 ? 180 : 30;
			for (let minute = Math.ceil(left / step) * step; minute <= right; minute += step) {
				node("text", { "x": positionX(minute), "y": 280, "text-anchor": "middle", "font-size": 12, fill: "#60758b" }, clock(minute));
			}
			geometry.lines.forEach(function(line) {
				const attributes = { x1: positionX(line.start), y1: positionY(line.fromTenths), x2: positionX(line.end), y2: positionY(line.toTenths), "data-index": line.eventIndex };
				if (Number.isInteger(line.eventIndex)) node("line", Object.assign({}, attributes, { stroke: "transparent", "stroke-width": 18 }));
				node("line", Object.assign({}, attributes, { stroke: line.eventIndex === selection ? "#17558c" : "#287bc1", "stroke-width": 3, "pointer-events": "none" }));
			});
			geometry.handles.forEach(function(handle) {
				const horizontal = positionX(handle.minute);
				const vertical = positionY(handle.targetTenths);
				const attributes = { "data-index": handle.eventIndex, "data-kind": handle.kind, tabindex: 0, role: "button", "aria-label": handle.kind + " " + clock(handle.minute) + ", " + handle.targetTenths / 10 + "%. Select for exact editing.", stroke: "#226da8", "stroke-width": 2, fill: handle.eventIndex === selection ? "#287bc1" : "white" };
				if (handle.kind === "start") node("path", Object.assign({}, attributes, { "d": "M " + horizontal + " " + (vertical - 7) + " L " + (horizontal + 7) + " " + vertical + " L " + horizontal + " " + (vertical + 7) + " L " + (horizontal - 7) + " " + vertical + " Z" }));
				else node("circle", Object.assign({}, attributes, { cx: horizontal, cy: vertical, "r": 8 }));
			});
		}
		function release(pointerId) {
			if (svg.hasPointerCapture(pointerId)) svg.releasePointerCapture(pointerId);
		}
		function cancel() {
			if (!drag) return;
			const pointerId = drag.pointerId;
			drag = null;
			release(pointerId);
			if (current && !destroyed) paint(current, selected);
		}
		function hit(event) {
			const target = event.target;
			if (!current || !target || !target.hasAttribute("data-index")) return null;
			const index = Number(target.getAttribute("data-index"));
			if (!Number.isInteger(index) || index < 0 || index >= current.events.length) return null;
			return { index: index, kind: target.getAttribute("data-kind") };
		}
		function select(index) {
			selected = index;
			if (typeof options.onSelect === "function") options.onSelect(index);
		}
		function listen(type, handler) { svg.addEventListener(type, handler); listeners.push([type, handler]); }
		mounted.add(svg);
		svg.appendChild(layer);
		svg.setAttribute("viewBox", "0 0 1000 300");
		svg.setAttribute("role", "group");
		svg.setAttribute("aria-label", options.label || "Daily brightness timeline");
		svg.style.touchAction = "none";
		listen("pointerdown", function(event) {
			if (destroyed || drag || event.button !== 0 || event.isPrimary === false) return;
			const handle = hit(event);
			if (!handle) return;
			const version = revision;
			select(handle.index);
			if (version !== revision || destroyed) return;
			if (!editable || !handle.kind) { paint(current, selected); return; }
			drag = { pointerId: event.pointerId, source: model.validate(current), index: handle.index, kind: handle.kind, candidate: null };
			svg.setPointerCapture(event.pointerId);
			event.preventDefault();
		});
		listen("pointermove", function(event) {
			if (!drag || event.pointerId !== drag.pointerId) return;
			try {
				const point = svg.createSVGPoint();
				point["x"] = event.clientX; point["y"] = event.clientY;
				const local = point.matrixTransform(svg.getScreenCTM().inverse());
				const minute = Math.round(Math.max(left, Math.min(right, left + (local.x - 65) * (right - left) / 880)));
				const target = Math.round(Math.max(0, Math.min(1000, (255 - local.y) * 1000 / 230)));
				const original = drag.source.events[drag.index];
				const start = drag.kind === "start" ? minute : original.minute;
				const end = drag.kind === "start" ? minute + original.fadeMinutes : minute;
				const level = drag.kind === "target" ? target : original.targetTenths;
				const result = adapter.edit(drag.source, drag.index, model.formatTime(start % 1440), model.formatTime(end % 1440), String(level / 10), "linear");
				drag.candidate = result;
				paint(result.schedule, result.index);
			} catch (error) { notifyError(error); }
		});
		listen("pointerup", function(event) {
			if (!drag || event.pointerId !== drag.pointerId) return;
			const candidate = drag.candidate;
			drag = null;
			release(event.pointerId);
			if (!candidate) { paint(current, selected); return; }
			const version = revision;
			try {
				const accepted = options.onEdit(model.validate(candidate.schedule), candidate.index);
				if (!destroyed && version === revision) {
					if (accepted !== false) { current = model.validate(candidate.schedule); selected = candidate.index; }
					paint(current, selected);
				}
			} catch (error) { if (!destroyed && version === revision) paint(current, selected); notifyError(error); }
		});
		listen("pointercancel", function(event) { if (drag && event.pointerId === drag.pointerId) cancel(); });
		listen("lostpointercapture", function(event) { if (drag && event.pointerId === drag.pointerId) cancel(); });
		listen("keydown", function(event) {
			if (event.key === "Escape") { cancel(); return; }
			if (event.key !== "Enter" && event.key !== " ") return;
			const handle = hit(event);
			if (handle) {
				event.preventDefault();
				const version = revision;
				select(handle.index);
				if (!destroyed && version === revision) paint(current, selected);
			}
		});
		return Object.freeze({
			render: function(value, index, begin, end, allowEditing) {
				if (destroyed) throw new Error("Timeline view destroyed");
				const schedule = model.validate(value);
				adapter.geometry(schedule, begin, end);
				cancel(); revision += 1;
				current = schedule; selected = Number.isInteger(index) && index >= 0 && index < schedule.events.length ? index : -1;
				left = begin; right = end; editable = allowEditing === true;
				paint(current, selected);
			},
			destroy: function() {
				if (destroyed) return;
				cancel(); destroyed = true;
				listeners.forEach(function(entry) { svg.removeEventListener(entry[0], entry[1]); });
				svg.removeChild(layer);
				[["viewBox", previous.viewBox], ["role", previous.role], ["aria-label", previous.label]].forEach(function(entry) {
					if (entry[1] === null) svg.removeAttribute(entry[0]); else svg.setAttribute(entry[0], entry[1]);
				});
				svg.style.touchAction = previous.touch;
				mounted.delete(svg);
			}
		});
	};
}));
