/** Physical Mirc0 face and local sample-time view, not firmware telemetry.
 * Five-minute phrases use the existing host adapter test's floor policy.
 * No sockets, timers, storage, event listeners or automatic device changes.
 * Prefix and colours are explicit local inputs; WIFI is never a time word.
 */
(function(root, factory) {
	"use strict";
	if (typeof module === "object" && module.exports) module.exports = factory();
	else root.WordclockMirc0Preview = factory();
}(typeof window !== "undefined" ? window : this, function() {
	"use strict";
	const rows = Object.freeze(["ITKISMOWIFI", "ACQUARTERDG", "TWENTYFIVEL", "HALFBTENFTO", "PASTAELNINE", "ONESIXTHREE", "FOURFIVETWO", "EIGHTELEVEN", "SEVENTWELVE", "TENSEOCLOCK"]);
	const hours = [[93, 6], [63, 3], [74, 3], [55, 5], [66, 4], [70, 4], [60, 3], [88, 5], [83, 5], [51, 4], [107, 3], [77, 6]];
	const minutes = { 5: [28, 4], 10: [36, 3], 15: [13, 7], 20: [22, 6], 25: [22, 10], 30: [40, 4], 35: [22, 10], 40: [22, 6], 45: [13, 7], 50: [36, 3], 55: [28, 4] };
	const mounted = new WeakSet();
	function logicalIndex(row, column) {
		if (!Number.isInteger(row) || row < 0 || row >= 10 || !Number.isInteger(column) || column < 0 || column >= 11) throw new Error("Mirc0 cell out of range");
		return row * 11 + (row % 2 ? 10 - column : column);
	}
	function mask(hour, minute, prefix) {
		if (!Number.isInteger(hour) || hour < 0 || hour > 23 || !Number.isInteger(minute) || minute < 0 || minute > 59) throw new Error("Valid local sample hour and minute required");
		if (prefix !== undefined && typeof prefix !== "boolean") throw new Error("Boolean prefix required");
		const lit = new Set();
		function add(first, count) { for (let index = first; index < first + count; index += 1) lit.add(index); }
		if (prefix !== false) { add(0, 2); add(3, 2); }
		const rounded = Math.floor(minute / 5) * 5;
		const spoken = hours[(hour + (rounded >= 35 ? 1 : 0)) % 12];
		add(spoken[0], spoken[1]);
		if (rounded === 0) add(99, 6);
		else {
			const word = minutes[rounded];
			add(word[0], word[1]);
			if (rounded >= 35) add(33, 2); else add(44, 4);
		}
		for (let dot = 0; dot < minute % 5; dot += 1) lit.add(110 + dot);
		return Array.from(lit).sort(function(first, second) { return first - second; });
	}
	function create(svg) {
		if (!svg || svg.localName !== "svg" || !svg.ownerDocument || mounted.has(svg)) throw new Error("Unmounted preview SVG required");
		const previous = ["viewBox", "role", "aria-label"].map(function(name) { return [name, svg.getAttribute(name)]; });
		const document = svg.ownerDocument;
		const layer = document.createElementNS("http://www.w3.org/2000/svg", "g");
		const cells = [];
		let destroyed = false;
		function node(name, attributes, text) {
			const item = document.createElementNS("http://www.w3.org/2000/svg", name);
			Object.keys(attributes).forEach(function(key) { item.setAttribute(key, attributes[key]); });
			if (text !== undefined) item.textContent = text;
			layer.appendChild(item);
			return item;
		}
		node("rect", { "x": 0, "y": 0, width: 330, height: 340, rx: 12, fill: "#10151b", "aria-hidden": "true" });
		rows.forEach(function(row, rowIndex) {
			Array.from(row).forEach(function(letter, column) {
				const index = logicalIndex(rowIndex, column);
				cells[index] = node("text", { "x": 15 + column * 30, "y": 30 + rowIndex * 28, "text-anchor": "middle", "font-family": "monospace", "font-size": 18, "font-weight": 600, "data-led-index": index, "data-lit": "false", "aria-hidden": "true", fill: "#4b5968" }, letter);
			});
		});
		for (let dot = 0; dot < 4; dot += 1) cells[110 + dot] = node("circle", { cx: 123 + dot * 28, cy: 318, "r": 5, "data-led-index": 110 + dot, "data-lit": "false", "aria-hidden": "true", fill: "#4b5968" });
		svg.setAttribute("viewBox", "0 0 330 340");
		svg.setAttribute("role", "img");
		svg.setAttribute("aria-label", "Mirc0 local sample preview. No sample time selected. Not device telemetry.");
		svg.appendChild(layer);
		mounted.add(svg);
		return Object.freeze({
			render: function(value) {
				if (destroyed) throw new Error("Preview destroyed");
				if (!value || typeof value !== "object") throw new Error("Preview value required");
				const foreground = value.foreground === undefined ? "#68e3a4" : value.foreground;
				const inactive = value.inactive === undefined ? "#4b5968" : value.inactive;
				if (typeof foreground !== "string" || typeof inactive !== "string" || !/^#[0-9a-f]{6}$/i.test(foreground) || !/^#[0-9a-f]{6}$/i.test(inactive)) throw new Error("Six-digit hex preview colours required");
				const lit = new Set(mask(value.hour, value.minute, value.prefix));
				cells.forEach(function(cell, index) {
					cell.setAttribute("fill", lit.has(index) ? foreground : inactive);
					cell.setAttribute("data-lit", lit.has(index) ? "true" : "false");
				});
				const time = String(value.hour).padStart(2, "0") + ":" + String(value.minute).padStart(2, "0");
				svg.setAttribute("aria-label", "Mirc0 local sample preview, " + time + ". Illustration only; not device telemetry.");
			},
			destroy: function() {
				if (destroyed) return;
				destroyed = true;
				svg.removeChild(layer);
				previous.forEach(function(entry) { if (entry[1] === null) svg.removeAttribute(entry[0]); else svg.setAttribute(entry[0], entry[1]); });
				mounted.delete(svg);
			}
		});
	}
	return Object.freeze({ rows: rows, logicalIndex: logicalIndex, mask: mask, create: create });
}));
