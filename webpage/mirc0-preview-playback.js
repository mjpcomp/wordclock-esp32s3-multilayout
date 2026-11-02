/** Deterministic preview time only: no clocks, timers, DOM, sockets or storage.
 * advance() receives elapsed real milliseconds from the page-owned driver.
 * Position may equal DAY_MS only at the explicit stopped next-day boundary.
 * Captured schedules are detached; no editor or device method is invoked.
 */
(function(root, factory) {
    "use strict";
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    else root.WordclockMirc0Playback = api;
}(typeof window !== "undefined" ? window : this, function() {
    "use strict";
    const DAY_MS = 86400000;
    const SPEEDS = Object.freeze([1, 60, 600, 3600]);
    function requireValue(condition, message) { if (!condition) throw new Error(message); }
    function create(model) {
        requireValue(model && typeof model.validate === "function" && typeof model.sampleTenths === "function", "Schedule model required");
        let positionMs = 0;
        let speed = 60;
        let running = false;
        let loop = false;
        let schedule = null;
        let source = null;
        function snapshot() {
            const localMinute = (positionMs % DAY_MS) / 60000;
            return { positionMs: positionMs, localMinute: localMinute, speed: speed, running: running, loop: loop, ended: positionMs === DAY_MS,
                scheduleSource: source, schedule: schedule === null ? null : model.validate(schedule),
                levelTenths: schedule === null ? null : model.sampleTenths(schedule, localMinute) };
        }
        function seek(value) {
            requireValue(Number.isFinite(value) && value >= 0 && value <= DAY_MS, "Position must be in this sample day");
            positionMs = value; running = false;
            return snapshot();
        }
        return Object.freeze({
            snapshot: snapshot,
            seek: seek,
            play: function() { running = positionMs < DAY_MS; return snapshot(); },
            pause: function() { running = false; return snapshot(); },
            reset: function() { return seek(0); },
            setSpeed: function(value) {
                requireValue(SPEEDS.includes(value), "Unsupported playback speed");
                speed = value;
                return snapshot();
            },
            setLoop: function(value) {
                requireValue(typeof value === "boolean", "Boolean loop required");
                loop = value;
                return snapshot();
            },
            advance: function(elapsedMs) {
                requireValue(Number.isFinite(elapsedMs) && elapsedMs >= 0, "Nonnegative finite elapsed time required");
                const target = positionMs + elapsedMs * speed;
                requireValue(Number.isFinite(target) && target <= Number.MAX_SAFE_INTEGER, "Elapsed playback exceeds safe range");
                if (running) {
                    if (loop) positionMs = target % DAY_MS;
                    else { positionMs = Math.min(target, DAY_MS); if (positionMs === DAY_MS) running = false; }
                }
                return snapshot();
            },
            captureSchedule: function(value, label) {
                requireValue(label === "saved" || label === "unsaved-draft", "Explicit saved or unsaved-draft source required");
                const copy = model.validate(value);
                schedule = copy; source = label; running = false;
                return snapshot();
            },
            clearSchedule: function() { schedule = null; source = null; running = false; return snapshot(); },
            nextBoundary: function() {
                requireValue(schedule !== null, "Capture a schedule before stepping its boundaries");
                const points = [DAY_MS];
                schedule.events.forEach(function(event) {
                    points.push(event.minute * 60000);
                    if (event.fadeMinutes) points.push(((event.minute + event.fadeMinutes) * 60000) % DAY_MS);
                });
                const next = points.filter(function(value) { return value > positionMs; }).sort(function(a, b) { return a - b; })[0];
                return seek(next === undefined ? DAY_MS : next);
            }
        });
    }
    return Object.freeze({ DAY_MS: DAY_MS, SPEEDS: SPEEDS, create: create });
}));
