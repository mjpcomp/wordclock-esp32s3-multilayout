/**
 * Timeline editing/projection adapter. Inject the committed schedule model.
 * No second evaluator, storage, socket, DOM, timer or constructor IO.
 * All edits call model.validate/normalize and return detached drafts or throw.
 * Times are local wall-clock minutes; crossing DST is runtime policy, not an
 * elapsed-time calculation here. View coordinates may extend past 1440 so a
 * midnight-spanning view stays continuous. Stored event times remain 0..1439.
 */
(function(root, factory) {
	"use strict";
	if (typeof module === "object" && module.exports) module.exports = factory;
	else root.createWordclockTimelineAdapter = factory;
}(typeof window !== "undefined" ? window : this, function(model) {
	"use strict";
	if (!model || ["validate", "normalize", "parseTime", "parsePercent", "segments"].some(function(name) { return typeof model[name] !== "function"; })) throw new Error("Shared schedule model required");
	function check(condition, message) { if (!condition) throw new Error(message); }
	function selected(value, index) {
		const schedule = model.validate(value);
		check(Number.isInteger(index) && index >= 0 && index < schedule.events.length, "Select a change first");
		return schedule;
	}
	/** Earlier end implies tomorrow; equal times are Instant, never 24 hours. */
	function resolveTiming(startText, endText, transition) {
		check(transition === "linear" || transition === "instant", "Unsupported transition");
		const minute = model.parseTime(startText);
		const end = transition === "instant" ? minute : model.parseTime(endText);
		const nextDay = end < minute;
		const duration = end + (nextDay ? 1440 : 0) - minute;
		return { minute: minute, endMinute: minute + duration, fadeMinutes: duration, nextDay: nextDay, transition: duration ? "linear" : "instant", notice: nextDay ? "overnight-inferred" : duration ? "same-day" : "instant" };
	}
	/** Numeric controls and dragging share this atomic path. No model/UI writes. */
	function edit(value, index, startText, endText, targetText, transition) {
		const schedule = selected(value, index);
		const timing = resolveTiming(startText, endText, transition);
		schedule.events[index] = { minute: timing.minute, targetTenths: model.parsePercent(targetText), fadeMinutes: timing.fadeMinutes };
		const result = model.normalize(schedule);
		return { schedule: result, index: result.events.findIndex(function(event) { return event.minute === timing.minute; }), timing: timing };
	}
	/** Add an Instant change; never truncate another fade to make room. */
	function add(value, startText, targetText) {
		const schedule = model.validate(value);
		check(schedule.events.length < model.MAX_EVENTS, "Maximum schedule capacity reached");
		const minute = model.parseTime(startText);
		schedule.events.push({ minute: minute, targetTenths: model.parsePercent(targetText), fadeMinutes: 0 });
		const result = model.normalize(schedule);
		return { schedule: result, index: result.events.findIndex(function(event) { return event.minute === minute; }) };
	}
	/** Deleting the last change retains that target as an explicit all-day draft. */
	function remove(value, index) {
		const schedule = selected(value, index);
		if (schedule.events.length === 1) schedule.defaultTenths = schedule.events[index].targetTenths;
		schedule.events.splice(index, 1);
		// Removing a point may connect a previous fade to a different next event.
		// Validate rather than silently editing any remaining duration.
		return model.validate(schedule);
	}
	function viewBounds(left, right) {
		check(Number.isFinite(left) && Number.isFinite(right) && left >= 0 && right > left && right <= 2880 && right - left <= 1440, "Invalid timeline view");
	}
	/**
	 * Project shared-model segments into an unwrapped view, e.g. [1320,1560].
	 * Only clipping/interpolation occurs here, not schedule evaluation. Midnight
	 * segments already split by the shared model are repeated for the next day.
	 * Instant edges use half-open view bounds to avoid duplicated seam handles.
	 */
	function geometry(value, left, right) {
		viewBounds(left, right);
		const schedule = model.validate(value);
		const pieces = model.segments(schedule);
		const lines = [];
		const handles = [];
		[0, 1440].forEach(function(offset) {
			pieces.forEach(function(piece) {
				const start = piece.start + offset;
				const end = piece.end + offset;
				if (piece.kind === "instant") {
					if (start >= left && start < right) lines.push({ kind: piece.kind, start: start, end: start, fromTenths: piece.fromTenths, toTenths: piece.toTenths, eventIndex: piece.eventIndex });
					return;
				}
				const begin = Math.max(left, start);
				const finish = Math.min(right, end);
				if (finish <= begin) return;
				function level(time) { return piece.fromTenths + (piece.toTenths - piece.fromTenths) * (time - start) / (end - start); }
				lines.push({ kind: piece.kind, start: begin, end: finish, fromTenths: level(begin), toTenths: level(finish), eventIndex: piece.eventIndex });
			});
		});
		schedule.events.forEach(function(event, index, events) {
			const previous = events[(index + events.length - 1) % events.length];
			[-1440, 0, 1440].forEach(function(offset) {
				const start = event.minute + offset;
				const end = start + event.fadeMinutes;
				if (start >= left && start < right) handles.push({ kind: "start", minute: start, targetTenths: previous.targetTenths, eventIndex: index });
				if (end >= left && end < right) handles.push({ kind: "target", minute: end, targetTenths: event.targetTenths, eventIndex: index });
			});
		});
		lines.sort(function(first, second) { return first.start - second.start || first.end - second.end; });
		return { lines: lines, handles: handles };
	}
	return Object.freeze({ resolveTiming: resolveTiming, edit: edit, add: add, remove: remove, geometry: geometry });
}));
