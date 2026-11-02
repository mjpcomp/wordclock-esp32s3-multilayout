/** Pure elapsed-time/state tests using the repository schedule evaluator. */
"use strict";
const assert = require("node:assert/strict"), fs = require("node:fs"), vm = require("node:vm");
const api = require("../webpage/mirc0-preview-playback.js"), model = require("../webpage/schedule-model.js");
const day = api.DAY_MS;
let checks = 0;
function equal(a, b) { assert.deepEqual(a, b); checks += 1; }
function reject(fn, player) { const before = player.snapshot(); assert.throws(fn); equal(player.snapshot(), before); }
const p = api.create(model);
equal(p.snapshot(), { positionMs: 0, localMinute: 0, speed: 60, running: false, loop: false, ended: false, scheduleSource: null, schedule: null, levelTenths: null });
p.advance(1000); equal(p.snapshot().positionMs, 0);
p.play(); p.advance(1000); equal(p.snapshot().positionMs, 60000);
p.pause(); p.advance(100000); equal(p.snapshot().positionMs, 60000);
p.play(); p.setSpeed(600); p.advance(1000); equal(p.snapshot().positionMs, 660000);
p.seek(day - 1); equal(p.snapshot().running, false); p.play(); p.advance(1);
equal([p.snapshot().positionMs, p.snapshot().running, p.snapshot().ended, p.snapshot().localMinute], [day, false, true, 0]);
p.play(); equal(p.snapshot().running, false);
p.reset(); equal(p.snapshot().positionMs, 0); equal(p.snapshot().running, false);
p.setLoop(true); p.setSpeed(3600); p.seek(day - 1000); p.play(); p.advance(1000);
equal(p.snapshot().positionMs, 3599000); equal(p.snapshot().running, true);
p.seek(0); p.play(); p.advance(48000); equal(p.snapshot().positionMs, 0);
for (const speed of api.SPEEDS) { p.seek(0); p.setSpeed(speed); p.play(); p.advance(10); equal(p.snapshot().positionMs, speed * 10); }
for (const value of [-1, NaN, Infinity, "60", 0, 30]) reject(() => p.setSpeed(value), p);
for (const value of [-1, NaN, Infinity, "1", Number.MAX_VALUE]) reject(() => p.advance(value), p);
for (const value of [-1, NaN, Infinity, "0", day + 1]) reject(() => p.seek(value), p);
reject(() => p.setLoop(1), p); reject(() => p.nextBoundary(), p);
const schedule = { defaultTenths: 900, events: [{ minute: 420, targetTenths: 800, fadeMinutes: 10 }, { minute: 1430, targetTenths: 200, fadeMinutes: 20 }] };
p.captureSchedule(schedule, "unsaved-draft"); schedule.events[0].targetTenths = 0;
equal(p.snapshot().schedule.events[0].targetTenths, 800);
const copy = p.snapshot(); copy.schedule.events.length = 0; equal(p.snapshot().schedule.events.length, 2);
p.seek(0); equal(p.snapshot().levelTenths, 500);
p.nextBoundary(); equal(p.snapshot().positionMs, 10 * 60000);
p.nextBoundary(); equal(p.snapshot().positionMs, 420 * 60000);
p.nextBoundary(); equal(p.snapshot().positionMs, 430 * 60000);
p.nextBoundary(); equal(p.snapshot().positionMs, 1430 * 60000);
p.nextBoundary(); equal(p.snapshot().positionMs, day); equal(p.snapshot().ended, true);
p.nextBoundary(); equal(p.snapshot().positionMs, day);
p.seek(425 * 60000); equal(p.snapshot().levelTenths, 500);
p.play(); reject(() => p.captureSchedule({}, "saved"), p); reject(() => p.captureSchedule(schedule, "device"), p);
p.captureSchedule({ defaultTenths: 370, events: [] }, "saved"); equal(p.snapshot().levelTenths, 370); equal(p.snapshot().running, false);
p.clearSchedule(); equal(p.snapshot().levelTenths, null); equal(p.snapshot().scheduleSource, null);
assert.throws(() => api.create({})); assert.ok(Object.isFrozen(api.SPEEDS));
const context = vm.createContext({ window: {} });
vm.runInContext(fs.readFileSync(require.resolve("../webpage/mirc0-preview-playback.js"), "utf8"), context);
equal(typeof context.window.WordclockMirc0Playback.create, "function");
console.log(JSON.stringify({ status: "PASS", assertions: checks, scope: "pure preview state and repository schedule model; no timers or device operations" }));
