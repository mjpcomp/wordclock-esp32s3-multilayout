"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { once } = require("node:events");
const { peerFor } = require("../tests/webpage-layout.test.cjs");
const root = path.resolve(__dirname, "..");
function isRead(text) {
    if (/^\d{3}/.test(text)) return [200, 201, 203, 204, 205, 206].includes(Number(text.slice(0, 3)));
    try {
        const value = JSON.parse(text);
        return value !== null && value.command === "brightness-schedule" && value.schema === 1 && value.action === "get";
    } catch { return false; }
}
async function main() {
    const smoke = process.argv.includes("--smoke");
    let chromium;
    try { ({ chromium } = require("playwright")); }
    catch { ({ chromium } = require(path.join(root, ".preview-runtime/node_modules/playwright"))); }
    const html = fs.readFileSync(path.join(root, ".pio/build/webpage/index.html"));
    const report = { scope: "Simulated UI only; not hardware proof", blockedHTTP: 0, blockedSockets: 0, blockedWrites: 0, errors: [] };
    const server = http.createServer((request, response) => {
        if (request.method !== "GET" || !["/", "/favicon.ico"].includes(request.url)) {
            response.writeHead(404); response.end(); return;
        }
        response.writeHead(request.url === "/" ? 200 : 204, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" });
        response.end(request.url === "/" ? html : undefined);
    });
    let browser;
    let interrupted = false;
    let stop;
    const stopped = new Promise(resolve => { stop = resolve; });
    const interrupt = () => { interrupted = true; stop(); };
    process.once("SIGINT", interrupt);
    process.once("SIGTERM", interrupt);
    try {
        server.listen(0, "127.0.0.1");
        await once(server, "listening");
        const origin = "http://127.0.0.1:" + server.address().port;
        const host = new URL(origin).host;
        const peer = peerFor(host);
        browser = await chromium.launch({ headless: smoke });
        browser.once("disconnected", stop);
        if (interrupted) throw new Error("Interrupted during startup");
        const context = await browser.newContext({ serviceWorkers: "block", viewport: { width: 1280, height: 900 } });
        await context.route("**/*", route => {
            const url = new URL(route.request().url());
            if (url.origin === origin && ["/", "/favicon.ico"].includes(url.pathname) && route.request().method() === "GET") return route.continue();
            report.blockedHTTP += 1;
            return route.abort();
        });
        await context.routeWebSocket(/.*/, socket => {
            const url = new URL(socket.url());
            if (!["ws:", "wss:"].includes(url.protocol) || url.host !== host) {
                report.blockedSockets += 1; void socket.close({ code: 1008 }); return;
            }
            peer.route({
                url: () => socket.url(), send: value => socket.send(value), close: options => socket.close(options),
                onMessage: handler => socket.onMessage(message => {
                    const text = String(message);
                    if (!isRead(text)) { report.blockedWrites += 1; return; }
                    handler(message);
                })
            });
        });
        const page = await context.newPage();
        page.setDefaultTimeout(15000);
        page.on("pageerror", error => report.errors.push(error.message));
        await page.goto(origin + "/", { waitUntil: "load" });
        await page.locator("[data-mirc0='simulation-controls']").waitFor({ state: "visible" });
        await page.waitForFunction(() => Boolean(readMirc0PreviewSchedule()));
        await page.evaluate(() => {
            const banner = document.createElement("div");
            banner.id = "local-preview-banner";
            banner.textContent = "LOCAL SIMULATION - no device connection. Settings writes are blocked; drafts stay in this session.";
            banner.style.cssText = "padding:12px;background:#fff3cd;color:#202020;position:sticky;top:0;z-index:9999";
            document.body.prepend(banner);
        });
        if (smoke) {
            for (const text of ["001", "199", "999", "garbage", "null", JSON.stringify({command: "brightness-schedule", schema: 1, action: "save"})]) assert.equal(isRead(text), false);
            for (const text of ["200", "201", "203", "204", "205", "206", JSON.stringify({command: "brightness-schedule", schema: 1, action: "get"})]) assert.equal(isRead(text), true);
            assert.equal(peer.connections, 1);
            assert.deepEqual(peer.errors, []);
            assert.deepEqual(report.errors, []);
            assert.equal(report.blockedHTTP + report.blockedSockets + report.blockedWrites, 0);
            assert.equal(await page.locator("#mirc0-preview-panel svg [data-led-index]").count(), 114);
            await page.evaluate(async () => {
                await fetch("https://preview-isolation.invalid/probe").then(() => { throw new Error("Foreign fetch succeeded"); }, () => {});
                async function probe(url, message) {
                    await new Promise((resolve, reject) => {
                        const socket = new WebSocket(url);
                        const timer = setTimeout(() => { socket.close(); reject(new Error("Socket probe timeout")); }, 5000);
                        socket.onopen = () => { if (message) { socket.send(message); setTimeout(() => socket.close(), 100); } else { reject(new Error("Foreign socket opened")); socket.close(); } };
                        socket.onclose = () => { clearTimeout(timer); resolve(); };
                    });
                }
                await probe("wss://preview-isolation.invalid/probe");
                await probe("ws://" + location.host, "001");
            });
            assert.equal(report.blockedHTTP, 1);
            assert.equal(report.blockedSockets, 1);
            assert.equal(report.blockedWrites, 1);
            assert.deepEqual(peer.errors, []);
            assert.deepEqual(report.errors, []);
            report.expectedProbeBlocks = { http: 1, sockets: 1, writes: 1 };
            report.status = "PASS";
        } else {
            console.log("Local simulated preview ready in the managed browser. Close that window or press Ctrl+C to stop. Save operations are blocked.");
            await stopped;
            report.status = "CLOSED";
        }
    } catch (error) {
        report.status = "FAIL";
        report.error = error.message;
        throw error;
    } finally {
        process.removeListener("SIGINT", interrupt);
        process.removeListener("SIGTERM", interrupt);
        try { if (browser) await browser.close(); }
        finally {
            if (server.listening) await new Promise(resolve => server.close(resolve));
            fs.writeFileSync(path.join(root, "local-preview-session.json"), JSON.stringify(report, null, 2) + "\n");
        }
    }
}
module.exports = { isRead };
if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
