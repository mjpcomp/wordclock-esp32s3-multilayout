/** Local Mirc0 sample controls. Inject read-only colour/layout getters and view.
 * No picker setters, sockets, controller commands or persistence.
 * Optional simulation injects a player/controls driver; destroy cancels its frames.
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
		const simulation = options.simulation;
		if (simulation && (!simulation.playback || typeof simulation.playback.create !== "function" || !simulation.model || ["createControls", "requestFrame", "cancelFrame", "readSchedule"].some(function(name) { return typeof simulation[name] !== "function"; }))) throw new Error("Complete simulation dependencies required");
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
		const player = simulation ? simulation.playback.create(simulation.model) : null;
		const view = options.view.create(svg);
		let destroyed = false;
		let simulationControls = null;
		function visible() { return !destroyed && !panel.hidden && options.available() && (typeof host.getClientRects !== "function" || host.getClientRects().length > 0); }
		function renderSample(hour, minute, sacrificial, levelTenths) {
			const colors = options.readColors();
			let sampleColors = colors;
			if (levelTenths !== null && levelTenths !== undefined) {
				if (!Number.isFinite(levelTenths) || levelTenths < 0 || levelTenths > 1000) throw new Error("Modeled level out of range");
				sampleColors = colors.map(function(color) {
					if (typeof color !== "string" || !/^#[0-9a-f]{6}$/i.test(color)) throw new Error("Six-digit sample colours required");
					return "#" + [1, 3, 5].map(function(offset) { return Math.round(parseInt(color.slice(offset, offset + 2), 16) * levelTenths / 1000).toString(16).padStart(2, "0"); }).join("");
				});
			}
			const value = { hour: hour, minute: minute, prefix: prefix.checked, foreground: sampleColors[0], inactive: sampleColors[1] };
			if (simulation) value.sacrificial = sacrificial;
			view.render(value);
			note.textContent = "Local sample only; not device time or output telemetry. Grey unlit letters are a guide for black backgrounds. Colour controls keep their existing device behaviour." + (simulation ? " Scheduled dimming is illustrative, not measured light output." : "");
		}
		function refresh() {
			if (destroyed) return;
			try {
				panel.hidden = !options.available();
				if (simulationControls) { simulationControls.refresh(); return; }
				if (panel.hidden) return;
				if (!/^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(time.value)) { note.textContent = "Choose a valid local sample time."; return; }
				renderSample(Number(time.value.slice(0, 2)), Number(time.value.slice(3)), false, null);
			} catch (error) { note.textContent = "Preview unavailable: " + (error.message || "invalid preview input"); }
		}
		function timeChanged() {
			if (!simulationControls) { refresh(); return; }
			if (!/^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(time.value)) {
				simulationControls.seekMinute(NaN);
				note.textContent = "Choose a valid local sample time.";
				return;
			}
			simulationControls.seekMinute(Number(time.value.slice(0, 2)) * 60 + Number(time.value.slice(3)));
		}
		host.appendChild(panel);
		panel.hidden = !options.available();
		try {
			if (simulation) {
				player.seek(530 * 60000);
				simulationControls = simulation.createControls(panel, {
					player: player,
					requestFrame: simulation.requestFrame,
					cancelFrame: simulation.cancelFrame,
					available: visible,
					readSchedule: simulation.readSchedule,
					onSample: function(sample) {
						if (!visible()) return;
						const minute = Math.floor(sample.state.localMinute);
						time.value = String(Math.floor(minute / 60)).padStart(2, "0") + ":" + String(minute % 60).padStart(2, "0");
						renderSample(Math.floor(minute / 60), minute % 60, sample.sacrificial, sample.state.levelTenths);
					}
				});
			}
		} catch (error) { view.destroy(); host.removeChild(panel); throw error; }
		time.addEventListener("input", timeChanged);
		prefix.addEventListener("change", refresh);
		mounted.add(host);
		refresh();
		return Object.freeze({
			refresh: refresh,
			destroy: function() {
				if (destroyed) return;
				destroyed = true;
				time.removeEventListener("input", timeChanged); prefix.removeEventListener("change", refresh);
				if (simulationControls) simulationControls.destroy();
				view.destroy(); host.removeChild(panel); mounted.delete(host);
			}
		});
	};
}));
