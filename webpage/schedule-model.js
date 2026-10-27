/**
 * Pure daily brightness model: no DOM, network, timers or storage writes.
 * Times/durations are local minutes; brightness is integer tenths of a percent.
 * Event minute starts a fade from the previous event target. Zero duration jumps.
 * Targets hold until the next event, including across midnight. defaultTenths
 * applies only when events is empty; it is NOT an implicit midnight event.
 * A single event fades from its own target, so its fade is a no-op.
 * Preview accepts valid local time only; device clock/fault policy lives elsewhere.
 */
(function(root, factory) {
	"use strict";
	const api = factory();
	if (typeof module === "object" && module.exports) module.exports = api;
	else root.WordclockScheduleModel = api;
}(typeof window !== "undefined" ? window : this, function() {
	"use strict";
	const dayMinutes = 1440;
	const maxEvents = 16;
	function requireValue(condition, message) {
		if (!condition) throw new Error(message);
	}
	function integer(value, maximum, name) {
		requireValue(Number.isInteger(value) && value >= 0 && value <= maximum, name + " out of range");
		return value;
	}
	function fields(value, names) {
		requireValue(value !== null && typeof value === "object" && !Array.isArray(value), "Expected an object");
		requireValue(Object.keys(value).length === names.length && names.every(function(name) {
			return Object.prototype.hasOwnProperty.call(value, name);
		}), "Unexpected fields");
	}
	/** Return integer minute; reject whitespace, 24:00 and malformed HH:MM. */
	function parseTime(text) {
		requireValue(typeof text === "string" && text.length === 5 && /^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(text), "Use HH:MM");
		return Number(text.slice(0, 2)) * 60 + Number(text.slice(3));
	}
	/** Format a minute in this day. Day-end labels must separately indicate tomorrow. */
	function formatTime(minute) {
		integer(minute, 1439, "minute");
		return String(Math.floor(minute / 60)).padStart(2, "0") + ":" + String(minute % 60).padStart(2, "0");
	}
	/** Parse decimal text without %, preserving 0.1% precision without rounding. */
	function parsePercent(text) {
		requireValue(typeof text === "string" && text === text.trim() && /^(?:0|[1-9][0-9]?|100)(?:\.[0-9])?$/.test(text), "Use 0..100 with at most one decimal");
		const parts = text.split(".");
		return integer(Number(parts[0]) * 10 + Number(parts[1] || 0), 1000, "percentage");
	}
	/** Strict schema validation, detached canonical copy, or Error. Never mutate input. */
	function validate(value) {
		fields(value, ["defaultTenths", "events"]);
		integer(value.defaultTenths, 1000, "all-day brightness");
		requireValue(Array.isArray(value.events) && value.events.length <= maxEvents, "At most 16 events");
		const events = Array.from(value.events, function(event) {
			fields(event, ["minute", "targetTenths", "fadeMinutes"]);
			return { minute: integer(event.minute, 1439, "time"), targetTenths: integer(event.targetTenths, 1000, "target"), fadeMinutes: integer(event.fadeMinutes, 1439, "duration") };
		});
		events.forEach(function(event, index) {
			if (index) requireValue(events[index - 1].minute < event.minute, "Times must be unique and ascending");
			const gap = events.length === 1 ? dayMinutes : (events[(index + 1) % events.length].minute + dayMinutes - event.minute) % dayMinutes;
			requireValue(event.fadeMinutes <= gap, "Fade overlaps next change");
		});
		return { defaultTenths: value.defaultTenths, events: events };
	}
	/** Sort an editor copy explicitly; duplicates and other invalid data still fail. */
	function normalize(value) {
		fields(value, ["defaultTenths", "events"]);
		requireValue(Array.isArray(value.events) && value.events.length <= maxEvents, "At most 16 events");
		const events = Array.from(value.events);
		events.forEach(function(event) {
			fields(event, ["minute", "targetTenths", "fadeMinutes"]);
			integer(event.minute, 1439, "time");
		});
		events.sort(function(first, second) { return first.minute - second.minute; });
		return validate({ defaultTenths: value.defaultTenths, events: events });
	}
	/** Fractional tenths at finite local minute [0,1440); preview, not device output. */
	function sampleTenths(value, localMinute) {
		const schedule = validate(value);
		const events = schedule.events;
		requireValue(Number.isFinite(localMinute) && localMinute >= 0 && localMinute < dayMinutes, "Sample time must be in this day");
		if (!events.length) return schedule.defaultTenths;
		let index = events.length - 1;
		for (let i = 0; i < events.length; i += 1) {
			if (events[i].minute > localMinute) break;
			index = i;
		}
		const event = events[index];
		const previous = events[(index + events.length - 1) % events.length];
		const elapsed = (localMinute + dayMinutes - event.minute) % dayMinutes;
		if (!event.fadeMinutes || elapsed >= event.fadeMinutes) return event.targetTenths;
		return previous.targetTenths + (event.targetTenths - previous.targetTenths) * elapsed / event.fadeMinutes;
	}
	/**
	 * Clip cyclic graph segments to [0,1440]. Instant edges have zero duration.
	 * Include previous-day fades at midnight. eventIndex refers to canonical order.
	 * Returned arrays are detached; graph dragging must validate a new draft.
	 */
	function segments(value) {
		const schedule = validate(value);
		if (!schedule.events.length) return [{ kind: "hold", start: 0, end: dayMinutes, fromTenths: schedule.defaultTenths, toTenths: schedule.defaultTenths }];
		const result = [];
		function append(kind, start, end, from, target, index) {
			if (kind === "instant") {
				if (start >= 0 && start < dayMinutes) result.push({ kind: kind, start: start, end: start, fromTenths: from, toTenths: target, eventIndex: index });
				return;
			}
			const left = Math.max(0, start);
			const right = Math.min(dayMinutes, end);
			if (right <= left) return;
			function interpolate(time) { return from + (target - from) * (time - start) / (end - start); }
			result.push({ kind: kind, start: left, end: right, fromTenths: interpolate(left), toTenths: interpolate(right), eventIndex: index });
		}
		schedule.events.forEach(function(event, index, events) {
			const previous = events[(index + events.length - 1) % events.length];
			const gap = events.length === 1 ? dayMinutes : (events[(index + 1) % events.length].minute + dayMinutes - event.minute) % dayMinutes;
			[-dayMinutes, 0].forEach(function(offset) {
				const start = event.minute + offset;
				const end = start + event.fadeMinutes;
				append(event.fadeMinutes ? "linear" : "instant", start, end, previous.targetTenths, event.targetTenths, index);
				append("hold", end, start + gap, event.targetTenths, event.targetTenths, index);
			});
		});
		result.sort(function(first, second) { return first.start - second.start || first.end - second.end; });
		return result;
	}
	return Object.freeze({ MAX_EVENTS: maxEvents, parseTime: parseTime, formatTime: formatTime, parsePercent: parsePercent, validate: validate, normalize: normalize, sampleTenths: sampleTenths, segments: segments });
}));
