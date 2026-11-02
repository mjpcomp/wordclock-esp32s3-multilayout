/** Optional simulation binding contract with fake controls/player/view/DOM. */
"use strict";
const assert = require("node:assert/strict");
const create = require("../webpage/mirc0-preview-page.js");
let checks = 0;
function equal(actual, expected) { assert.deepEqual(actual, expected); checks += 1; }
class Element {
 constructor(name, document) { this.localName = name; this.ownerDocument = document; this.attrs = {}; this.children = []; this.listeners = {}; this.value = ""; }
 setAttribute(key, value) { this.attrs[key] = String(value); }
 getAttribute(key) { return Object.hasOwn(this.attrs, key) ? this.attrs[key] : null; }
 appendChild(item) { this.children.push(item); return item; }
 removeChild(item) { const index = this.children.indexOf(item); assert.ok(index >= 0); this.children.splice(index, 1); }
 addEventListener(name, fn) { (this.listeners[name] || (this.listeners[name] = new Set())).add(fn); }
 removeEventListener(name, fn) { this.listeners[name].delete(fn); }
 emit(name) { for (const fn of this.listeners[name] || []) fn(); }
}
const document = { createElement(name) { return new Element(name, document); }, createElementNS(ns, name) { equal(ns, "http://www.w3.org/2000/svg"); return new Element(name, document); } };
const host = new Element("div", document), existing = new Element("p", document); host.appendChild(existing);
let available = true, geometryVisible = true, colorReads = 0, scheduleReads = 0, viewDisposals = 0, controlDisposals = 0, paused = false;
host.getClientRects = () => geometryVisible ? [{}] : [];
const colors = ["#008000", "#000000"], renders = [];
const state = { localMinute: 0, levelTenths: null };
const player = { seek(ms) { state.localMinute = (ms % 86400000) / 60000; paused = true; } };
let injected, sacrificial = false;
function sample() { if (injected.available()) injected.onSample({ state: { ...state }, sacrificial, sacrificialColor: "#ff0000" }); else paused = true; }
const readSchedule = () => { scheduleReads += 1; return null; };
const simulation = {
 model: {}, playback: { create(value) { equal(value, simulation.model); return player; } },
 requestFrame() {}, cancelFrame() {}, readSchedule,
 createControls(panel, options) {
  equal(panel.getAttribute("id"), "mirc0-preview-panel"); injected = options;
  sample();
  return { refresh: sample, seekMinute(value) { if (!Number.isFinite(value)) { paused = true; return; } player.seek(value * 60000); sample(); }, destroy() { controlDisposals += 1; paused = true; } };
 }
};
const options = { simulation, available() { return available; }, readColors() { colorReads += 1; return colors; }, view: { create() { return { render(value) { renders.push(value); }, destroy() { viewDisposals += 1; } }; } } };
const page = create(host, options);
const panel = host.children[1], nodes = [];
function walk(item) { nodes.push(item); item.children.forEach(walk); } walk(panel);
const time = nodes.find(item => item.getAttribute("id") === "mirc0-sample-time"), prefix = nodes.find(item => item.getAttribute("id") === "mirc0-sample-prefix"), note = nodes.find(item => item.getAttribute("data-mirc0") === "note");
equal(time.value, "08:50"); equal(state.localMinute, 530);
equal(renders.at(-1), { hour: 8, minute: 50, prefix: true, foreground: "#008000", inactive: "#000000", sacrificial: false });
equal(injected.readSchedule, readSchedule); equal(scheduleReads, 0);
equal(injected.requestFrame, simulation.requestFrame); equal(injected.cancelFrame, simulation.cancelFrame);
state.localMinute = 719.5; state.levelTenths = 500; sacrificial = true; sample();
equal(time.value, "11:59"); equal(renders.at(-1).foreground, "#004000"); equal(renders.at(-1).sacrificial, true);
equal(colors, ["#008000", "#000000"]); assert.ok(note.textContent.includes("illustrative"));
time.value = "23:59"; time.emit("input"); equal(state.localMinute, 1439); equal(paused, true);
prefix.checked = false; prefix.emit("change"); equal(renders.at(-1).prefix, false);
state.levelTenths = 0; sample(); equal(renders.at(-1).foreground, "#000000");
state.levelTenths = null; sample(); equal(renders.at(-1).foreground, "#008000");
const count = renders.length; time.value = ""; time.emit("input"); equal(renders.length, count); assert.ok(note.textContent.includes("valid local sample time"));
available = false; const reads = colorReads; page.refresh(); equal(panel.hidden, true); equal(colorReads, reads);
available = true; geometryVisible = false; page.refresh(); equal(colorReads, reads); equal(paused, true);
geometryVisible = true; page.refresh(); equal(colorReads, reads + 1); equal(scheduleReads, 0);
equal(injected.readSchedule(), null); equal(scheduleReads, 1);
state.levelTenths = 1001; page.refresh(); assert.ok(note.textContent.includes("Preview unavailable")); state.levelTenths = null;
page.destroy(); page.destroy(); equal(controlDisposals, 1); equal(viewDisposals, 1); equal(host.children, [existing]);
const after = colorReads; page.refresh(); time.emit("input"); prefix.emit("change"); sample(); equal(colorReads, after);
assert.ok(nodes.every(item => Object.values(item.listeners).every(set => set.size === 0)));
create(host, options).destroy(); equal(controlDisposals, 2); equal(viewDisposals, 2);
const invalidHost = new Element("div", document);
assert.throws(() => create(invalidHost, { ...options, simulation: {} })); equal(invalidHost.children.length, 0);
assert.throws(() => create(invalidHost, { ...options, simulation: { ...simulation, playback: { create() { throw new Error("Player failure"); } } } })); equal(invalidHost.children.length, 0);
assert.throws(() => create(invalidHost, { ...options, simulation: { ...simulation, createControls() { throw new Error("Controls failure"); } } })); equal(invalidHost.children.length, 0);
console.log(JSON.stringify({ status: "PASS", assertions: checks, scope: "injected simulation binding contract; not actual frame/browser/transport integration" }));
