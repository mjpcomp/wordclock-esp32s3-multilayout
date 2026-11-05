"use strict";
// Extract reviewed page functions and inject fake DOM/socket/console objects.
// All credential markers are synthetic. No browser, network or device is used.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../webpage/script.js"), "utf8");
function body(name) {
    const found = source.match(new RegExp("function " + name + "\\([^]*?\\n}\\n"));
    assert.ok(found, "Missing reviewed function: " + name);
    return found[0];
}
assert.match(source, /\blet debug = false;/);
assert.match(body("initConfigValues"), /\bdebug = false;/);
assert.doesNotMatch(source, /\bdebug\s*=\s*true\b/);
assert.match(source, /debugMessage\("WebSocket response received\."\);/);
assert.doesNotMatch(body("sendCmd"), /debugMessage\([^;]*\bdata\b/s);
function harness(options = {}) {
    const logs = [], sent = [], output = { textContent: "unchanged" };
    const socket = { readyState: 1, send(value) { sent.push(value); } };
    const context = {
        console: options.noConsole ? undefined : { log(...values) { logs.push(values); } },
        document: { getElementById() { return options.noOutput ? null : output; } },
        WebSocket: { OPEN: 1 }, websocket: socket
    };
    const program = "let debug = false;\n" + body("debugMessage") + body("nstr") + body("sendCmd") +
        "\n({ debugMessage, sendCmd, setDebug(value) { debug = value; } });";
    const api = vm.runInNewContext(program, context, { timeout: 1000 });
    return { api, logs, sent, output, socket };
}
let cases = 0;
for (const enabled of [false, true]) {
    for (const command of [85, 90]) {
        const h = harness(); h.api.setDebug(enabled);
        const marker = "SYNTHETIC_SECRET_NOT_A_REAL_CREDENTIAL";
        const payload = "fixture-fields-" + marker;
        h.api.sendCmd(command, payload);
        assert.deepEqual(h.sent, [String(command).padStart(3, "0") + payload]);
        assert.equal(JSON.stringify(h.logs).includes(marker), false);
        assert.equal(h.output.textContent.includes(marker), false);
        if (enabled) {
            assert.deepEqual(h.logs, [["WebSocket command " + command + " requested."]]);
            assert.equal(h.output.textContent, "WebSocket command " + command + " requested.");
        } else {
            assert.deepEqual(h.logs, []);
            assert.equal(h.output.textContent, "unchanged");
        }
        h.socket.readyState = 0;
        h.api.sendCmd(command, payload);
        assert.equal(h.sent.length, 1);
        cases += 1;
    }
}
{
    const h = harness(); h.api.setDebug(true);
    const secret = { password: "SYNTHETIC_OBJECT_SECRET" };
    h.api.debugMessage("WebSocket response received.", secret);
    assert.deepEqual(h.logs, [["WebSocket response received."]]);
    assert.equal(h.output.textContent, "WebSocket response received.");
    h.api.debugMessage(secret);
    assert.equal(h.logs.length, 1);
    assert.equal(h.output.textContent, "WebSocket response received.");
    cases += 1;
}
for (const options of [{ noConsole: true }, { noOutput: true }]) {
    const h = harness(options); h.api.setDebug(true);
    assert.doesNotThrow(() => h.api.debugMessage("Safe status."));
    cases += 1;
}
{
    const h = harness(); h.api.setDebug(true);
    h.api.sendCmd("SYNTHETIC_COMMAND_MARKER", "fixture");
    assert.deepEqual(h.logs, [["WebSocket command unknown requested."]]);
    assert.equal(h.output.textContent.includes("SYNTHETIC_COMMAND_MARKER"), false);
    cases += 1;
}
console.log("PASS: " + cases + " synthetic diagnostic-redaction/wire-preservation cases; not a device test");
