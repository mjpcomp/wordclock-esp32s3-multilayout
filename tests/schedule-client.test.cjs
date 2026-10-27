/** Client + committed model; protocol JSON fixtures, NOT compiled C++/NVS tests. */
"use strict";
const assert = require("node:assert/strict");
const model = require("../webpage/schedule-model.js");
const createClient = require("../webpage/schedule-client.js");
let checks = 0;
function equal(actual, expected) { assert.deepEqual(actual, expected); checks += 1; }
function rejects(run) { assert.throws(run); checks += 1; }
const constant = value => ({ defaultTenths: value, events: [] });
function reply(request, status, value = 400, revision = 1) {
    return { command: request.command, schema: 1, requestId: request.requestId, action: request.action, status, revision, ...constant(value) };
}
function ready() {
    const client = createClient(model);
    const token = client.connect();
    const request = client.begin("get");
    equal(client.receive(token, reply(request, "loaded")), true);
    return { client, token };
}
// Successful save requires exact accepted content/revision and never aliases caller objects.
{
    const { client, token } = ready();
    client.edit(constant(50));
    const request = client.begin("save");
    equal(request.expectedRevision, 1);
    rejects(() => client.edit(constant(60))); rejects(() => client.begin("save"));
    client.receive(token, reply(request, "saved", 50, 2));
    equal(client.snapshot().dirty, false);
    const detached = client.snapshot(); detached.draft.defaultTenths = 999;
    equal(client.snapshot().draft.defaultTenths, 50);
}
// Firmware missing defaults are explicitly UNSAVED, not silently persisted.
{
    const client = createClient(model), token = client.connect(), request = client.begin("get");
    client.receive(token, { ...reply(request, "missing", 1000, 0), draft: true });
    equal(client.snapshot().dirty, true); equal(client.begin("save").expectedRevision, 0);
}
// Lost or malformed mutation outcomes retain draft and forbid blind retries.
for (const cause of ["timeout", "disconnect", "content", "revision", "flags"]) {
    const { client, token } = ready(); client.edit(constant(5)); const request = client.begin("save");
    if (cause === "timeout") client.timeout(token, request.requestId);
    if (cause === "disconnect") client.disconnect(token);
    if (cause === "content") client.receive(token, reply(request, "saved", 6, 2));
    if (cause === "revision") client.receive(token, reply(request, "saved", 5, 1));
    if (cause === "flags") client.receive(token, { ...reply(request, "saved", 5, 2), reloadRequired: true });
    equal(client.snapshot().status, "outcome-unknown"); equal(client.snapshot().draft, constant(5));
    rejects(() => client.begin("save"));
    const nextToken = client.connect(), load = client.begin("get");
    equal(client.receive(token, reply(request, "saved", 5, 2)), false);
    equal(client.disconnect(token), false); equal(client.timeout(token, request.requestId), false);
    client.receive(nextToken, reply(load, "loaded", 5, 2));
    equal(client.snapshot().status, "reconcile-required"); rejects(() => client.begin("save"));
    client.reconcile("keep-draft"); equal(client.snapshot().dirty, false);
}
// Invalid-request can omit action; reset-required need not include reloadRequired.
for (const status of ["read-failed", "invalid-request", "conflict", "revision-exhausted", "write-uncertain", "readback-uncertain", "reset-required"]) {
    const { client, token } = ready(); client.edit(constant(50)); const request = client.begin("save");
    const message = { command: request.command, schema: 1, requestId: request.requestId, status };
    if (status !== "invalid-request") message.action = "save";
    if (status === "reset-required") message.revision = 0; else if (status !== "invalid-request") message.reloadRequired = true;
    client.receive(token, message); equal(client.snapshot().status, status);
    equal(client.snapshot().draft, constant(50)); rejects(() => client.begin("save"));
}
// Corruption requires explicit schedule reset, never a reboot or automatic write.
{
    const client = createClient(model), token = client.connect(), request = client.begin("get");
    client.receive(token, { command: request.command, schema: 1, requestId: request.requestId, action: "get", status: "reset-required", revision: 0 });
    rejects(() => client.begin("save")); rejects(() => client.begin("reset"));
    const reset = client.begin("reset", true); equal(reset.expectedRevision, 0);
    client.receive(token, reply(reset, "reset", 1000, 1)); equal(client.snapshot().dirty, false);
}
// Real validator rejects overlapping fades without changing the previous draft.
{
    const { client, token } = ready();
    rejects(() => client.edit({ defaultTenths: 400, events: [{ minute: 10, targetTenths: 100, fadeMinutes: 20 }, { minute: 20, targetTenths: 0, fadeMinutes: 0 }] }));
    equal(client.snapshot().draft, constant(400));
    const load = client.begin("get"); client.edit(constant(25));
    client.receive(token, reply(load, "loaded", 800, 8)); equal(client.snapshot().draft, constant(25));
    client.reconcile("keep-draft"); equal(client.begin("save").expectedRevision, 8);
}
// Capacity remains within schema-1 wire budget; returned requests cannot edit pending data.
{
    const { client } = ready();
    const events = Array.from({ length: 16 }, (_, index) => ({ minute: index * 90, targetTenths: 1000, fadeMinutes: 90 }));
    client.edit({ defaultTenths: 1000, events }); const request = client.begin("save");
    equal(Buffer.byteLength(JSON.stringify(request)) <= 2048, true);
    request.events[0].targetTenths = 0; equal(client.snapshot().pending.schedule.events[0].targetTenths, 1000);
}
// Browser registration does not touch DOM or open a socket.
{
    const vm = require("node:vm"), fs = require("node:fs"); const context = vm.createContext({ window: {} });
    ["../webpage/schedule-model.js", "../webpage/schedule-client.js"].forEach(path => vm.runInContext(fs.readFileSync(require.resolve(path), "utf8"), context));
    const client = context.window.createWordclockScheduleClient(context.window.WordclockScheduleModel);
    equal(client.snapshot().status, "disconnected");
}
console.log(JSON.stringify({ status: "PASS", assertions: checks }));
