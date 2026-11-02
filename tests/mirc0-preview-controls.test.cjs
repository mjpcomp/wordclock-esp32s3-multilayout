/** Local controls with the real player, fake DOM and manually delivered frames. */
"use strict";
const assert = require("node:assert/strict");
const create = require("../webpage/mirc0-preview-controls.js");
const playback = require("../webpage/mirc0-preview-playback.js");
const model = require("../webpage/schedule-model.js");
let checks = 0;
function equal(actual, expected) { assert.deepEqual(actual, expected); checks += 1; }
class Target {
 constructor() { this.listeners = {}; }
 addEventListener(name, fn) { (this.listeners[name] || (this.listeners[name] = new Set())).add(fn); }
 removeEventListener(name, fn) { this.listeners[name].delete(fn); }
 emit(name) { for (const fn of [...(this.listeners[name] || [])]) fn(); }
 count() { return Object.values(this.listeners).reduce((sum, set) => sum + set.size, 0); }
}
class Element extends Target {
 constructor(name, document) { super(); this.localName = name; this.ownerDocument = document; this.attrs = {}; this.children = []; this.style = {}; this.value = ""; this.textContent = ""; this.checked = false; }
 setAttribute(name, value) { this.attrs[name] = String(value); }
 getAttribute(name) { return Object.hasOwn(this.attrs, name) ? this.attrs[name] : null; }
 appendChild(item) { this.children.push(item); return item; }
 removeChild(item) { const index = this.children.indexOf(item); assert.ok(index >= 0); this.children.splice(index, 1); }
}
class Document extends Target {
 constructor() { super(); this.hidden = false; }
 createElement(name) { return new Element(name, this); }
}
const document = new Document(), host = new Element("div", document), existing = new Element("p", document);
host.appendChild(existing);
const player = playback.create(model), frames = new Map(), allFrames = new Map(), samples = [];
let handle = 0, available = true, reads = 0, broken = false;
let draft = { schedule: { defaultTenths: 370, events: [] }, source: "unsaved-draft" };
const options = {
 player,
 requestFrame(fn) { const id = ++handle; frames.set(id, fn); allFrames.set(id, fn); return id; },
 cancelFrame(id) { frames.delete(id); },
 onSample(value) { if (broken) throw new Error("Injected render failure"); samples.push(value); },
 available() { return available; },
 readSchedule() { reads += 1; return draft; }
};
const controls = create(host, options);
assert.throws(() => create(host, options));
const panel = host.children[1], nodes = [];
function walk(item) { nodes.push(item); item.children.forEach(walk); } walk(panel);
const field = name => nodes.find(item => item.getAttribute("data-mirc0") === name);
const buttons = nodes.filter(item => item.localName === "button");
const [play, reset, minute, five, boundary, capture] = buttons;
const seek = field("day-position"), speed = field("speed"), loop = field("loop"), prefix = field("sacrificial"), color = field("sacrificial-color");
const summary = field("simulation-summary"), chip = field("sacrificial-sample"), note = field("simulation-note");
function tick(time) { equal(frames.size, 1); const [id, fn] = frames.entries().next().value; frames.delete(id); fn(time); }
equal(reads, 0); equal(frames.size, 0); equal(prefix.checked, false); equal(color.disabled, true); equal(chip.hidden, true); equal(boundary.disabled, true);
equal(samples.at(-1).state.levelTenths, null); assert.ok(summary.textContent.includes("unavailable"));
assert.ok(buttons.every(item => item.getAttribute("type") === "button"));
prefix.checked = true; prefix.emit("change"); equal(color.disabled, false); equal(chip.hidden, false);
color.value = "#224466"; color.emit("input"); equal(samples.at(-1).sacrificialColor, "#224466"); equal(samples.at(-1).sacrificial, true);
assert.ok(field("mapping-summary").textContent.includes("physical 1–114")); equal(reads, 0);
play.emit("click"); equal(frames.size, 1); controls.refresh(); equal(frames.size, 1); tick(100); tick(1100); equal(player.snapshot().positionMs, 60000);
const stale = [...frames.keys()][0]; play.emit("click"); equal(frames.size, 0); equal(player.snapshot().running, false);
const sampleCount = samples.length; allFrames.get(stale)(999999); equal(samples.length, sampleCount); equal(player.snapshot().positionMs, 60000);
minute.emit("click"); equal(player.snapshot().positionMs, 120000); five.emit("click"); equal(player.snapshot().positionMs, 420000);
seek.value = "3600"; seek.emit("input"); equal(player.snapshot().positionMs, 3600000); equal(frames.size, 0);
capture.emit("click"); equal(reads, 1); equal(player.snapshot().scheduleSource, "unsaved-draft"); equal(player.snapshot().levelTenths, 370); equal(boundary.disabled, false);
draft.schedule.defaultTenths = 900; controls.refresh(); equal(player.snapshot().levelTenths, 370); equal(reads, 1);
capture.emit("click"); equal(player.snapshot().levelTenths, 900); equal(reads, 2);
draft = null; capture.emit("click"); equal(player.snapshot().levelTenths, 900); assert.ok(note.textContent.includes("previous capture retained"));
play.emit("click"); speed.value = "600"; speed.emit("change"); equal(frames.size, 1); tick(2000); tick(3000); equal(player.snapshot().positionMs, 4200000);
available = false; const hiddenCount = samples.length; controls.refresh(); equal(player.snapshot().running, false); equal(frames.size, 0); equal(samples.length, hiddenCount);
available = true; controls.refresh(); equal(frames.size, 0); play.emit("click"); tick(5000);
document.hidden = true; document.emit("visibilitychange"); equal(frames.size, 0); equal(player.snapshot().running, false);
document.hidden = false; document.emit("visibilitychange"); equal(frames.size, 0);
controls.seekMinute("2"); assert.ok(note.textContent.includes("Numeric sample minute"));
controls.seekMinute(1439.9); play.emit("click"); tick(6000); tick(7000); equal(player.snapshot().ended, true); equal(frames.size, 0); assert.ok(summary.textContent.includes("End of day"));
reset.emit("click"); equal(player.snapshot().positionMs, 0); loop.checked = true; loop.emit("change");
play.emit("click"); tick(8000); tick(152000); equal(player.snapshot().positionMs, 0); equal(player.snapshot().running, true);
seek.value = ""; seek.emit("input"); equal(player.snapshot().running, false); equal(frames.size, 0); assert.ok(note.textContent.includes("Day position required"));
speed.value = "30"; speed.emit("change"); equal(player.snapshot().speed, 600); assert.ok(note.textContent.includes("Unsupported"));
color.value = "bad"; color.emit("input"); assert.ok(note.textContent.includes("Six-digit")); color.value = "#000000"; controls.refresh();
play.emit("click"); tick(10000); tick(9000); equal(player.snapshot().running, false); equal(frames.size, 0); assert.ok(note.textContent.includes("monotonic"));
broken = true; controls.refresh(); equal(frames.size, 0); assert.ok(note.textContent.includes("Injected render failure")); broken = false;
play.emit("click"); const destroyedFrame = [...frames.keys()][0]; const beforeDestroy = samples.length;
controls.destroy(); controls.destroy(); equal(frames.size, 0); equal(player.snapshot().running, false); equal(host.children, [existing]);
equal(nodes.reduce((sum, node) => sum + node.count(), 0), 0); equal(document.count(), 0);
allFrames.get(destroyedFrame)(20000); controls.refresh(); controls.seekMinute(10); play.emit("click"); equal(samples.length, beforeDestroy);
create(host, options).destroy(); equal(host.children, [existing]);
console.log(JSON.stringify({ status: "PASS", assertions: checks, scope: "fake DOM and injected frames; no browser layout, sockets, storage or hardware" }));
