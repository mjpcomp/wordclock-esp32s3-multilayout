/** Pure model regressions; no browser, firmware or device validation claimed. */
"use strict";
const assert = require("node:assert/strict");
const model = require("../webpage/schedule-model.js");
let checks = 0;
function equal(actual, expected) { assert.deepEqual(actual, expected); checks += 1; }
function rejects(run) { assert.throws(run); checks += 1; }
function near(actual, expected) { assert.ok(Math.abs(actual - expected) < 1e-7); checks += 1; }
const schedule = { defaultTenths: 400, events: [
    { minute: 420, targetTenths: 400, fadeMinutes: 10 },
    { minute: 1185, targetTenths: 100, fadeMinutes: 15 },
    { minute: 1230, targetTenths: 0, fadeMinutes: 5 }
] };
for (let minute = 0; minute < 1440; minute += 1) equal(model.parseTime(model.formatTime(minute)), minute);
for (let value = 0; value <= 1000; value += 1) equal(model.parsePercent((value / 10).toFixed(1)), value);
["24:00", "7:00", "07:00\n", "12:60"].forEach(value => rejects(() => model.parseTime(value)));
["40%", "40\n", "0.01", "100.1", "", "01"].forEach(value => rejects(() => model.parsePercent(value)));
[[1184, 400], [1185, 400], [1192.5, 250], [1200, 100], [1232.5, 50], [1235, 0], [0, 0], [425, 200]].forEach(pair => near(model.sampleTenths(schedule, pair[0]), pair[1]));
const reverse = { defaultTenths: 400, events: schedule.events.slice().reverse() };
rejects(() => model.validate(reverse)); equal(model.normalize(reverse), schedule); equal(reverse.events[0].minute, 1230);
const detached = model.validate(schedule); detached.events[0].targetTenths = 999; equal(schedule.events[0].targetTenths, 400);
const wrap = { defaultTenths: 400, events: [{ minute: 420, targetTenths: 400, fadeMinutes: 0 }, { minute: 1430, targetTenths: 100, fadeMinutes: 20 }] };
near(model.sampleTenths(wrap, 0), 250); near(model.sampleTenths(wrap, 10), 100);
wrap.events[1].fadeMinutes = 431; rejects(() => model.validate(wrap));
wrap.events[1].fadeMinutes = 430; equal(model.validate(wrap).events.length, 2);
const single = { defaultTenths: 900, events: [{ minute: 600, targetTenths: 50, fadeMinutes: 60 }] };
near(model.sampleTenths(single, 630), 50); near(model.sampleTenths({ defaultTenths: 5, events: [] }, 0), 5);
rejects(() => model.validate({ defaultTenths: 400, events: new Array(1) }));
rejects(() => model.validate({ defaultTenths: 400, events: [{ minute: 0, targetTenths: 1, fadeMinutes: 0, curve: "smooth" }] }));
const maximum = { defaultTenths: 100, events: Array.from({ length: 16 }, (_, index) => ({ minute: index * 60, targetTenths: 100, fadeMinutes: 0 })) };
equal(model.validate(maximum).events.length, 16);
rejects(() => model.validate({ defaultTenths: 100, events: maximum.events.concat([{ minute: 1000, targetTenths: 100, fadeMinutes: 0 }]) }));
const duplicate = { defaultTenths: 100, events: [{ minute: 0, targetTenths: 100, fadeMinutes: 0 }, { minute: 0, targetTenths: 200, fadeMinutes: 0 }] };
rejects(() => model.validate(duplicate));
let seed = 731;
function random(limit) { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed % limit; }
for (let iteration = 0; iteration < 80; iteration += 1) {
    const times = [...new Set(Array.from({ length: 1 + random(16) }, () => random(1440)))].sort((first, second) => first - second);
    const value = { defaultTenths: random(1001), events: times.map((minute, index) => {
        const gap = times.length === 1 ? 1440 : (times[(index + 1) % times.length] + 1440 - minute) % 1440;
        return { minute, targetTenths: random(1001), fadeMinutes: random(Math.min(gap, 1439) + 1) };
    }) };
    const spans = model.segments(value).filter(segment => segment.kind !== "instant");
    near(spans[0].start, 0); near(spans[spans.length - 1].end, 1440);
    for (let index = 1; index < spans.length; index += 1) near(spans[index - 1].end, spans[index].start);
    for (let minute = 0.25; minute < 1440; minute += 7) {
        const span = spans.find(segment => segment.start <= minute && minute < segment.end);
        equal(Boolean(span), true);
        near(span.fromTenths + (span.toTenths - span.fromTenths) * (minute - span.start) / (span.end - span.start), model.sampleTenths(value, minute));
    }
}
const vm = require("node:vm");
const fs = require("node:fs");
const context = vm.createContext({ window: {} });
vm.runInContext(fs.readFileSync(require.resolve("../webpage/schedule-model.js"), "utf8"), context);
equal(typeof context.window.WordclockScheduleModel.validate, "function");
console.log(JSON.stringify({ status: "PASS", assertions: checks, generatedProfiles: 80 }));
