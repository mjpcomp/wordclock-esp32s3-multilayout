/** Local Mirc0 sample controls. Inject read-only colour/layout getters and view.
 * No picker setters, sockets, controller commands, timers or persistence.
 * IDs intentionally avoid legacy brightness/slider/transition auto-send hooks.
 * Caller refreshes after existing colour/config updates; destroy before removal.
 */
(function(root, factory) {
	"use strict";
	if (typeof module === "object" && module.exports) module.exports = factory();
	else root.createWordclockMirc0PreviewPage = factory();
}(typeof window !== "undefined" ? window : this, function() {
	"use strict";
	const mounted = new WeakSet();
	return function(host, options) {
		if (!host || !host.ownerDocument || mounted.has(host)) throw new Error("Unmounted preview host required");
		if (!options || !options.view || typeof options.view.create !== "function" || typeof options.readColors !== "function" || typeof options.available !== "function") throw new Error("Preview view and read-only getters required");
		const document = host.ownerDocument;
		function element(name, attributes, text) {
			const item = name === "svg" ? document.createElementNS("http://www.w3.org/2000/svg", name) : document.createElement(name);
			Object.keys(attributes).forEach(function(key) { item.setAttribute(key, attributes[key]); });
			if (text !== undefined) item.textContent = text;
			return item;
		}
		const panel = element("section", { id: "mirc0-preview-panel", "aria-labelledby": "mirc0-preview-title" });
		const title = element("h3", { id: "mirc0-preview-title" }, "Mirc0 face preview");
		const svg = element("svg", { "data-mirc0": "face" });
		const controls = element("div", { "class": "pure-form mirc0-preview-controls" });
		const timeLabel = element("label", { "for": "mirc0-sample-time" }, "Sample time ");
		const time = element("input", { id: "mirc0-sample-time", type: "time", step: 60 });
		time.value = "08:50";
		timeLabel.appendChild(time);
		const prefixLabel = element("label", { "for": "mirc0-sample-prefix" });
		const prefix = element("input", { id: "mirc0-sample-prefix", type: "checkbox" });
		prefix.checked = true;
		prefixLabel.appendChild(prefix);
		prefixLabel.appendChild(element("span", {}, "Show IT IS (local only)"));
		controls.appendChild(timeLabel); controls.appendChild(prefixLabel);
		const note = element("p", { "data-mirc0": "note", role: "status", "aria-live": "polite" });
		[title, svg, controls, note].forEach(function(item) { panel.appendChild(item); });
		const view = options.view.create(svg);
		let destroyed = false;
		function refresh() {
			if (destroyed) return;
			try {
				panel.hidden = !options.available();
				if (panel.hidden) return;
				if (!/^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(time.value)) { note.textContent = "Choose a valid local sample time."; return; }
				const colors = options.readColors();
				view.render({ hour: Number(time.value.slice(0, 2)), minute: Number(time.value.slice(3)), prefix: prefix.checked, foreground: colors[0], inactive: colors[1] });
				note.textContent = "Local sample only; not device time or output telemetry. Colour controls keep their existing device behaviour.";
			} catch (error) { note.textContent = "Preview unavailable: " + (error.message || "invalid preview input"); }
		}
		time.addEventListener("input", refresh);
		prefix.addEventListener("change", refresh);
		host.appendChild(panel);
		mounted.add(host);
		refresh();
		return Object.freeze({
			refresh: refresh,
			destroy: function() {
				if (destroyed) return;
				destroyed = true;
				time.removeEventListener("input", refresh); prefix.removeEventListener("change", refresh);
				view.destroy(); host.removeChild(panel); mounted.delete(host);
			}
		});
	};
}));
