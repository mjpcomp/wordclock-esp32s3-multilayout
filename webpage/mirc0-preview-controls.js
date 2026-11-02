/** Local preview controls; receives a pure player and read-only callbacks.
 * No sockets, storage, RTC/NTP changes or editor mutation methods.
 * Page owns availability/face updates. Hidden document or panel pauses playback.
 * Frame callbacks are generation-guarded and cancelled before teardown.
 */
(function(root, factory) {
	"use strict";
	if (typeof module === "object" && module.exports) module.exports = factory();
	else root.createWordclockMirc0PreviewControls = factory();
}(typeof window !== "undefined" ? window : this, function() {
	"use strict";
	const mounted = new WeakSet();
	return function(host, options) {
		if (!host || !host.ownerDocument || mounted.has(host)) throw new Error("Unmounted controls host required");
		if (!options || !options.player || ["requestFrame", "cancelFrame", "onSample", "available", "readSchedule"].some(function(name) { return typeof options[name] !== "function"; })) throw new Error("Preview dependencies required");
		const player = options.player;
		const document = host.ownerDocument;
		const listeners = [];
		let destroyed = false;
		let frame = null;
		let previousTime = null;
		let generation = 0;
		function element(name, attributes, text) {
			const item = document.createElement(name);
			Object.keys(attributes).forEach(function(key) { item.setAttribute(key, attributes[key]); });
			if (text !== undefined) item.textContent = text;
			return item;
		}
		function listen(target, name, callback) {
			target.addEventListener(name, callback);
			listeners.push([target, name, callback]);
		}
		const panel = element("section", { "data-mirc0": "simulation-controls", "aria-label": "Local preview test controls" });
		const buttons = element("div", { "class": "mirc0-preview-controls" });
		function button(label) {
			const item = element("button", { type: "button", "class": "pure-button" }, label);
			buttons.appendChild(item);
			return item;
		}
		const play = button("Play");
		const reset = button("Reset to 00:00");
		const minute = button("+1 minute");
		const fiveMinutes = button("+5 minutes");
		const boundary = button("Next schedule boundary");
		const capture = button("Use current draft");
		function input(labelText, attributes) {
			const label = element("label", {});
			const item = element("input", attributes);
			label.appendChild(item);
			label.appendChild(element("span", {}, labelText));
			panel.appendChild(label);
			return item;
		}
		panel.appendChild(buttons);
		const seek = input("Day position", { type: "range", min: 0, max: 86400, step: 1, "data-mirc0": "day-position" });
		const speedLabel = element("label", {}, "Playback speed ");
		const speed = element("select", { "data-mirc0": "speed" });
		[1, 60, 600, 3600].forEach(function(value) { speed.appendChild(element("option", { value: value }, value + " simulated seconds per second")); });
		speedLabel.appendChild(speed); panel.appendChild(speedLabel);
		const loop = input("Loop day (local only)", { type: "checkbox", "data-mirc0": "loop" });
		const sacrificial = input("Include sacrificial LED (preview only)", { type: "checkbox", "data-mirc0": "sacrificial" });
		loop.checked = player.snapshot().loop;
		sacrificial.checked = false;
		const color = input("Sample LED colour (local only)", { type: "color", "data-mirc0": "sacrificial-color" });
		color.value = "#000000";
		const chip = element("p", { "data-mirc0": "sacrificial-sample" });
		const swatch = element("span", { "aria-hidden": "true" }, "●");
		chip.appendChild(swatch);
		chip.appendChild(element("span", {}, " Sacrificial LED — physical index 0 (local sample)"));
		const summary = element("p", { "data-mirc0": "simulation-summary" });
		const mapping = element("p", { "data-mirc0": "mapping-summary" });
		const note = element("p", { "data-mirc0": "simulation-note", role: "status", "aria-live": "polite" });
		[chip, summary, mapping, note].forEach(function(item) { panel.appendChild(item); });
		function stopFrames() {
			generation += 1;
			const old = frame;
			frame = null; previousTime = null;
			if (old !== null) options.cancelFrame(old);
		}
		function visible() { return !document.hidden && options.available(); }
		function emit() {
			const state = player.snapshot();
			const sampleColor = color.value;
			if (!/^#[0-9a-f]{6}$/i.test(sampleColor)) throw new Error("Six-digit sample LED colour required");
			seek.value = String(state.positionMs / 1000);
			speed.value = String(state.speed);
			loop.checked = state.loop;
			play.textContent = state.running ? "Pause" : "Play";
			boundary.disabled = state.schedule === null;
			color.disabled = !sacrificial.checked;
			chip.hidden = !sacrificial.checked;
			swatch.style.color = sampleColor;
			const seconds = Math.floor((state.positionMs % 86400000) / 1000);
			const time = [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60].map(function(value) { return String(value).padStart(2, "0"); }).join(":");
			const level = state.levelTenths === null ? "Scheduled level unavailable" : "Modeled scheduled level " + (state.levelTenths / 10).toFixed(1) + "% (" + state.scheduleSource + ")";
			summary.textContent = time + (state.ended ? " — End of day / next-day boundary. " : ". ") + level + ".";
			mapping.textContent = sacrificial.checked ? "Logical 0–113 → physical 1–114; separate prefix at 0 (115 modeled positions)." : "Logical 0–113 → physical 0–113 (114 modeled positions).";
			if (visible()) options.onSample({ state: state, sacrificial: sacrificial.checked, sacrificialColor: sampleColor });
		}
		function fail(error) {
			stopFrames(); player.pause();
			note.textContent = "Preview paused: " + (error.message || "invalid input");
			play.textContent = "Play";
		}
		function queueFrame() {
			if (destroyed || frame !== null || !player.snapshot().running) return;
			const epoch = generation;
			frame = options.requestFrame(function(timestamp) {
				if (destroyed || epoch !== generation) return;
				frame = null;
				try {
					if (!visible()) { stopFrames(); player.pause(); emit(); return; }
					if (!Number.isFinite(timestamp) || (previousTime !== null && timestamp < previousTime)) throw new Error("Invalid monotonic preview timestamp");
					if (previousTime !== null) player.advance(timestamp - previousTime);
					previousTime = timestamp;
					emit(); queueFrame();
				} catch (error) { fail(error); }
			});
		}
		function action(run) {
			if (destroyed) return;
			try {
				run();
				if (!visible()) { stopFrames(); player.pause(); }
				note.textContent = "Nominal 24-hour local sample; not device time, settings or output telemetry.";
				emit(); queueFrame();
			} catch (error) { fail(error); }
		}
		function pauseAndSeek(value) { stopFrames(); player.seek(value); }
		listen(play, "click", function() { action(function() { stopFrames(); if (player.snapshot().running) player.pause(); else player.play(); }); });
		listen(reset, "click", function() { action(function() { stopFrames(); player.reset(); }); });
		listen(minute, "click", function() { action(function() { pauseAndSeek(Math.min(86400000, player.snapshot().positionMs + 60000)); }); });
		listen(fiveMinutes, "click", function() { action(function() { pauseAndSeek(Math.min(86400000, player.snapshot().positionMs + 300000)); }); });
		listen(boundary, "click", function() { action(function() { stopFrames(); player.nextBoundary(); }); });
		listen(seek, "input", function() { action(function() { if (seek.value.trim() === "") throw new Error("Day position required"); pauseAndSeek(Number(seek.value) * 1000); }); });
		listen(speed, "change", function() { action(function() { stopFrames(); player.setSpeed(Number(speed.value)); }); });
		listen(loop, "change", function() { action(function() { player.setLoop(loop.checked); }); });
		listen(sacrificial, "change", function() { action(function() {}); });
		listen(color, "input", function() { action(function() {}); });
		listen(capture, "click", function() {
			action(function() {
				const value = options.readSchedule();
				if (!value) throw new Error("Schedule unavailable; previous capture retained");
				stopFrames(); player.captureSchedule(value.schedule, value.source);
			});
		});
		listen(document, "visibilitychange", function() { action(function() { if (document.hidden) { stopFrames(); player.pause(); } }); });
		host.appendChild(panel); mounted.add(host);
		action(function() {});
		return Object.freeze({
			refresh: function() { action(function() {}); },
			seekMinute: function(value) { action(function() { if (typeof value !== "number") throw new Error("Numeric sample minute required"); pauseAndSeek(value * 60000); }); },
			destroy: function() {
				if (destroyed) return;
				destroyed = true; stopFrames(); player.pause();
				listeners.forEach(function(entry) { entry[0].removeEventListener(entry[1], entry[2]); });
				host.removeChild(panel); mounted.delete(host);
			}
		});
	};
}));
