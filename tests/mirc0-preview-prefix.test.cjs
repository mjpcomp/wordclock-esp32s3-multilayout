/** Prefix-index metadata only: no extra face pixels, transport or device writes. */
"use strict";
const assert = require("node:assert/strict");
const preview = require("../webpage/mirc0-preview.js");
let checks = 0;
function equal(actual, expected) { assert.deepEqual(actual, expected); checks += 1; }
for (let index = 0; index < 114; index += 1) {
 equal(preview.physicalIndex(index), index);
 equal(preview.physicalIndex(index, false), index);
 equal(preview.physicalIndex(index, true), index + 1);
}
for (const index of [-1, 114, 1.5, NaN, Infinity, "0", null]) assert.throws(() => preview.physicalIndex(index, true));
for (const option of [0, 1, "true", null, {}, []]) assert.throws(() => preview.physicalIndex(0, option));
equal([110, 111, 112, 113].map(index => preview.physicalIndex(index, true)), [111, 112, 113, 114]);
class Element {
 constructor(name, document) { this.localName = name; this.ownerDocument = document; this.attrs = {}; this.children = []; }
 setAttribute(key, value) { this.attrs[key] = String(value); }
 getAttribute(key) { return Object.hasOwn(this.attrs, key) ? this.attrs[key] : null; }
 removeAttribute(key) { delete this.attrs[key]; }
 appendChild(value) { this.children.push(value); return value; }
 removeChild(value) { const index = this.children.indexOf(value); assert.ok(index >= 0); this.children.splice(index, 1); }
}
const document = { createElementNS(namespace, name) { equal(namespace, "http://www.w3.org/2000/svg"); return new Element(name, document); } };
const svg = new Element("svg", document);
svg.setAttribute("viewBox", "1 2 3 4"); svg.setAttribute("aria-label", "Original");
const view = preview.create(svg), layer = svg.children[0];
const cells = layer.children.filter(cell => cell.getAttribute("data-led-index") !== null);
equal(layer.children.length, 115); equal(cells.length, 114);
equal(cells.filter(cell => cell.localName === "text").length, 110);
equal(cells.filter(cell => cell.localName === "circle").length, 4);
const shape = cells.map(cell => [cell.localName, cell.textContent, cell.getAttribute("x"), cell.getAttribute("y"), cell.getAttribute("cx"), cell.getAttribute("cy"), cell.getAttribute("data-led-index")]);
for (let minute = 0; minute < 1440; minute += 1) {
 const hour = Math.floor(minute / 60), within = minute % 60;
 view.render({ hour, minute: within, sacrificial: true });
 equal(cells.filter(cell => cell.getAttribute("data-lit") === "true").map(cell => Number(cell.getAttribute("data-led-index"))).sort((first, second) => first - second), preview.mask(hour, within));
 equal(cells.map(cell => Number(cell.getAttribute("data-physical-led-index"))), cells.map(cell => Number(cell.getAttribute("data-led-index")) + 1));
 view.render({ hour, minute: within, sacrificial: false });
 equal(cells.map(cell => cell.getAttribute("data-physical-led-index")), cells.map(cell => cell.getAttribute("data-led-index")));
}
equal(cells.map(cell => [cell.localName, cell.textContent, cell.getAttribute("x"), cell.getAttribute("y"), cell.getAttribute("cx"), cell.getAttribute("cy"), cell.getAttribute("data-led-index")]), shape);
view.render({ hour: 23, minute: 59, prefix: false, sacrificial: true });
equal(cells.filter(cell => cell.getAttribute("data-lit") === "true").map(cell => Number(cell.getAttribute("data-led-index"))).sort((first, second) => first - second), preview.mask(23, 59, false));
const before = JSON.stringify(cells.map(cell => cell.attrs));
for (const sacrificial of [null, 1, "true"]) { assert.throws(() => view.render({ hour: 8, minute: 50, sacrificial })); equal(JSON.stringify(cells.map(cell => cell.attrs)), before); }
view.render({ hour: 0, minute: 0 });
equal(cells.map(cell => cell.getAttribute("data-physical-led-index")), cells.map(cell => cell.getAttribute("data-led-index")));
view.destroy(); view.destroy(); equal(svg.children, []);
equal(svg.getAttribute("viewBox"), "1 2 3 4"); equal(svg.getAttribute("aria-label"), "Original");
assert.throws(() => view.render({ hour: 0, minute: 0, sacrificial: true }));
preview.create(svg).destroy();
console.log(JSON.stringify({ status: "PASS", assertions: checks, minutes: 1440, logicalCells: 114, scope: "pure mapping and fake SVG metadata/lifecycle; not browser or hardware proof" }));
