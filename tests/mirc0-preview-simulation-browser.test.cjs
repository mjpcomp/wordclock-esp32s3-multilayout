/** Generated activation candidate, real Chromium, simulated peers only. */
"use strict";
const assert = require("node:assert/strict"), fs = require("node:fs"), http = require("node:http"), path = require("node:path");
const { chromium } = require("playwright"), { setTimeout: pause } = require("node:timers/promises");
const { peerFor } = require("./webpage-layout.test.cjs");
const preview = require("../webpage/mirc0-preview.js");
const output = path.join(__dirname, "../preview-activation-evidence");
async function masks(page) {
 const time = await page.locator("#mirc0-sample-time").inputValue();
 const [hour, minute] = time.split(":").map(Number);
 const prefix = await page.locator("#mirc0-sample-prefix").isChecked();
 const actual = await page.locator("#mirc0-preview-panel svg [data-lit='true']").evaluateAll(nodes => nodes.map(node => Number(node.getAttribute("data-led-index"))).sort((first, second) => first - second));
 assert.deepEqual(actual, preview.mask(hour, minute, prefix));
}
async function main() {
 fs.mkdirSync(output, { recursive: true });
 const html = fs.readFileSync(path.join(__dirname, "../.pio/build/webpage/index.html"));
 const server = http.createServer((request, response) => { response.writeHead(request.url === "/" ? 200 : 204, { "Content-Type": "text/html; charset=utf-8" }); response.end(request.url === "/" ? html : undefined); });
 await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
 const origin = "http://127.0.0.1:" + server.address().port;
 const report = { scope: "CI activation candidate; real Chromium with simulated peers, not hardware proof", sessions: [], errors: [], blocked: [], mutations: [] };
 let browser, context;
 try {
  browser = await chromium.launch({ headless: true });
  for (const width of [320, 480, 768, 1024, 1440]) {
   context = await browser.newContext({ locale: "en-US", viewport: { width, height: 1000 }, reducedMotion: "reduce" });
   const page = await context.newPage(); page.setDefaultTimeout(10000);
   page.on("pageerror", error => report.errors.push(error.message));
   await context.route("**/*", route => { const url = new URL(route.request().url()); if (url.origin === origin && (url.pathname === "/" || url.pathname === "/favicon.ico")) return route.continue(); report.blocked.push(url.href); return route.abort(); });
   const peer = peerFor(new URL(origin).host);
   await page.routeWebSocket(/.*/, socket => {
    peer.route({ url: () => socket.url(), send: value => socket.send(value), close: args => socket.close(args), onMessage: handler => socket.onMessage(message => {
     const text = String(message);
     if (/^\d{3}/.test(text) && Number(text.slice(0, 3)) < 200) { report.mutations.push(text); return; }
     if (text.startsWith("{")) { const value = JSON.parse(text); if (value.command === "brightness-schedule" && value.action !== "get") { report.mutations.push(text); return; } }
     handler(message);
    }) });
   });
   await page.goto(origin + "/", { waitUntil: "load" });
   const panel = page.locator("#mirc0-preview-panel"), controls = panel.locator("[data-mirc0='simulation-controls']");
   await controls.waitFor({ state: "visible" });
   await page.waitForFunction(() => Boolean(readMirc0PreviewSchedule()));
   assert.equal(await page.locator("#mirc0-sample-time").inputValue(), "08:50");
   const buttons = name => controls.getByRole("button", { name, exact: true });
   const prefix = controls.locator("[data-mirc0='sacrificial']");
   await prefix.check();
   await controls.locator("[data-mirc0='sacrificial-color']").evaluate(input => { input.value = "#ff0000"; input.dispatchEvent(new Event("input", { bubbles: true })); });
   assert.equal(await controls.locator("[data-mirc0='sacrificial-sample']").isVisible(), true);
   assert.equal(await controls.locator("[data-mirc0='sacrificial-sample'] span").first().evaluate(node => getComputedStyle(node).color), "rgb(255, 0, 0)");
   const physical = await panel.locator("svg [data-led-index]").evaluateAll(nodes => nodes.map(node => [Number(node.getAttribute("data-led-index")), Number(node.getAttribute("data-physical-led-index"))]));
   assert.equal(physical.length, 114); assert.ok(physical.every(([logical, actual]) => actual === logical + 1));
   assert.equal(await panel.locator("svg text").count(), 110); assert.equal(await panel.locator("svg circle").count(), 4);
   await prefix.uncheck(); await masks(page);
   await page.locator("#mirc0-sample-prefix").uncheck(); await masks(page); await page.locator("#mirc0-sample-prefix").check();
   await buttons("Use current draft").click();
   const summary = controls.locator("[data-mirc0='simulation-summary']");
   const expected = await page.evaluate(() => window.WordclockScheduleModel.sampleTenths(readMirc0PreviewSchedule().schedule, 530) / 10);
   assert.ok((await summary.textContent()).includes(expected.toFixed(1) + "%"));
   const frozen = await summary.textContent();
   const eventCount = await page.evaluate(() => readMirc0PreviewSchedule().schedule.events.length);
   if (eventCount === 0) {
    await page.locator("#schedule-editor [data-schedule='all-day']").fill("0");
    await page.locator("#schedule-editor [data-schedule='all-day']").dispatchEvent("change");
   } else {
    for (let index = 0; index < eventCount; index += 1) {
     await page.locator("#schedule-editor [data-schedule='changes']").selectOption(String(index));
     await page.locator("#schedule-editor [data-schedule='target']").fill("0");
     await page.locator("#schedule-editor [data-schedule='apply']").click();
    }
   }
   assert.equal(await summary.textContent(), frozen);
   await buttons("Use current draft").click();
   assert.ok((await summary.textContent()).includes("0.0% (unsaved-draft)"));
   assert.ok((await panel.locator("svg [data-lit='true']").evaluateAll(nodes => nodes.map(node => node.getAttribute("fill")))).every(color => color === "#000000"));
   await page.locator("#mirc0-sample-time").fill("08:00");
   await controls.locator("[data-mirc0='speed']").selectOption("3600"); await buttons("Play").click();
   await page.waitForFunction(() => document.getElementById("mirc0-sample-time").value !== "08:00");
   await buttons("Pause").click(); await masks(page);
   const paused = await page.locator("#mirc0-sample-time").inputValue(); await pause(100);
   assert.equal(await page.locator("#mirc0-sample-time").inputValue(), paused);
   await page.locator("#mirc0-sample-time").fill("23:59"); await buttons("Play").click();
   await page.waitForFunction(() => document.querySelector("[data-mirc0='simulation-summary']").textContent.includes("End of day"));
   assert.equal(await page.locator("#mirc0-sample-time").inputValue(), "00:00");
   await buttons("Reset to 00:00").click(); await controls.locator("[data-mirc0='loop']").check();
   await page.locator("#mirc0-sample-time").fill("23:59"); await buttons("Play").click();
   await page.waitForFunction(() => document.getElementById("mirc0-sample-time").value.startsWith("00:"));
   await buttons("Pause").click(); await controls.locator("[data-mirc0='loop']").uncheck();
   await buttons("Play").click();
   await page.locator(".pure-menu-link[data-navigation='settings']").evaluate(node => node.click());
   await page.waitForFunction(() => Array.from(document.querySelectorAll("#mirc0-preview-panel button")).some(button => button.textContent === "Play"));
   await page.locator(".pure-menu-link[data-navigation='main']").evaluate(node => node.click()); await controls.waitFor({ state: "visible" });
   const resumed = await page.locator("#mirc0-sample-time").inputValue(); await pause(100);
   assert.equal(await page.locator("#mirc0-sample-time").inputValue(), resumed);
   await buttons("Play").click();
   await page.evaluate(() => { mirc0PreviewPage.destroy(); initMirc0PreviewPage(); });
   await page.locator("[data-mirc0='simulation-controls']").waitFor({ state: "visible" }); await pause(100);
   assert.equal(await page.locator("#mirc0-preview-panel").count(), 1);
   assert.equal(await page.locator("#mirc0-sample-time").inputValue(), "08:50"); await masks(page);
   const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
   assert.equal(overflow, false); assert.equal(peer.connections, 1); assert.deepEqual(peer.errors, []); assert.ok(peer.requests.every(request => request.action === "get"));
   await page.screenshot({ path: path.join(output, "simulation-" + width + ".png"), fullPage: true, animations: "disabled" });
   report.sessions.push({ width, overflow, logicalCells: 114, peerConnections: peer.connections, schedulerActions: peer.requests.map(request => request.action) });
   await context.close(); context = null;
  }
  assert.deepEqual(report.errors, []); assert.deepEqual(report.blocked, []); assert.deepEqual(report.mutations, []); report.status = "PASS";
 } catch (error) { report.status = "FAIL"; report.error = error.stack || String(error); throw error; }
 finally { fs.writeFileSync(path.join(output, "simulation-browser.json"), JSON.stringify(report, null, 2)); if (context) await context.close(); if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); }
 console.log(JSON.stringify({ status: report.status, sessions: report.sessions.length, mutations: report.mutations.length }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
