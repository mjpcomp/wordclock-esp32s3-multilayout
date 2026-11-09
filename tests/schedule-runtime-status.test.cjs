const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../webpage/schedule-runtime-status.js'), 'utf8');
class Events {
 constructor() { this.listeners = {}; this.textContent = ''; this.disabled = false; }
 addEventListener(name, fn) { (this.listeners[name] ||= new Set()).add(fn); }
 removeEventListener(name, fn) { this.listeners[name]?.delete(fn); }
 emit(name, event = {}) { for (const fn of [...(this.listeners[name] || [])]) fn(event); }
}
class Socket extends Events {
 constructor(state = 1) { super(); this.readyState = state; this.sent = []; this.fail = false; }
 send(text) { if (this.fail) throw new Error('uncertain'); this.sent.push(JSON.parse(text)); }
 emit(name,event={}) { super.emit(name,event); if(typeof this['on'+name]==='function')this['on'+name](event); }
 reply(value) { this.emit('message', { data: JSON.stringify(value) }); }
}
function setup() {
 const button = new Events(), notice = new Events(), values = new Events();
 const elements = { "[data-runtime='refresh']": button, "[data-runtime='status']": notice, "[data-runtime='values']": values };
 const timers = new Map(); let next = 0;
 const context = { window: {} }; vm.createContext(context); vm.runInContext(source, context);
 const observer = context.window.createWordclockRuntimeStatus({ querySelector: key => elements[key] }, {
  setTimeout: (fn, delay) => { assert.equal(delay, 8000); timers.set(++next, fn); return next; },
  clearTimeout: id => timers.delete(id)
 });
 return { button, notice, values, timers, observer, click: () => button.emit('click') };
}
function snapshot(id) {
 return { command: 'brightness-runtime', schema: 1, requestId: id, action: 'get', status: 'snapshot', initialized: true, hasAccepted: true, acceptedRevision: 2, observedStorageFault: false, pendingEvaluation: true, lastStorageResult: 'ok', sample: { ageMs: 10, gain: 4000, revision: 1, scheduled: true, pausedAutomatic: false, waitingForTime: false, storageFault: false, automatic: false, masterOn: true, timeValid: true }, backend: { kind: 'virtual', cacheCompiled: false, outputCompiled: false, rendererAttached: false } };
}
test('manual only, independent response, historical labeling and accepted/evaluated revisions', () => {
 const s=setup(), socket=new Socket(); let config=0; socket.onmessage=()=>config++;
 s.observer.attach(socket); assert.equal(socket.sent.length,0); assert.equal(s.timers.size,0);
 s.observer.attach(socket); assert.equal(socket.listeners.message.size,1);
 s.click(); s.click(); assert.equal(socket.sent.length,1); assert.equal(s.timers.size,1);
 assert.match(socket.sent[0].requestId,/^rt_g1_r1$/);
 socket.reply({command:'brightness-schedule',requestId:socket.sent[0].requestId,status:'saved'});
 socket.reply(snapshot('other')); assert.equal(s.timers.size,1);
 socket.reply(snapshot(socket.sent[0].requestId)); assert.equal(s.timers.size,0);
 assert.match(s.notice.textContent,/not live/); assert.match(s.values.textContent,/40.00%/);
 assert.match(s.values.textContent,/Accepted revision: 2/); assert.match(s.values.textContent,/Evaluated revision: 1/);
 assert.equal(config,3); assert.equal(typeof socket.onmessage,'function');
 s.observer.destroy(); assert.equal(socket.listeners.message.size,0); assert.equal(socket.sent.length,1);
});
test('connecting, timeout, no retry, late reply and stale socket callback isolation', () => {
 const s=setup(), old=new Socket(0); s.observer.attach(old); s.click(); assert.equal(old.sent.length,0);
 old.readyState=1; old.emit('open'); assert.equal(old.sent.length,0);
 s.click(); const oldHandler=[...old.listeners.message][0], deadline=[...s.timers.values()][0];
 const previous=snapshot(old.sent[0].requestId); deadline(); assert.match(s.notice.textContent,/timed out/);
 old.reply(previous); assert.equal(s.values.textContent,''); assert.equal(old.sent.length,1);
 s.click(); const staleTimeout=[...s.timers.values()][0]; const current=new Socket(); s.observer.attach(current); s.click();
 oldHandler({data:JSON.stringify(snapshot(current.sent[0].requestId))}); staleTimeout();
 assert.equal(s.timers.size,1); current.reply(snapshot(current.sent[0].requestId)); assert.match(s.values.textContent,/40.00%/);
 current.readyState=3; current.emit('close'); assert.equal(s.values.textContent,''); assert.equal(s.button.disabled,true);
 s.observer.destroy();
});
test('send exception and errors never retry or close sockets', () => {
 const s=setup(), socket=new Socket(); socket.fail=true; s.observer.attach(socket); s.click();
 assert.match(s.notice.textContent,/send failed/); assert.equal(s.timers.size,0); assert.equal(socket.readyState,1);
 socket.fail=false; s.click(); socket.emit('error'); assert.equal(s.timers.size,0); assert.equal(s.values.textContent,'');
 s.observer.destroy(); s.observer.destroy(); assert.equal(socket.listeners.message.size,0);
});
test('correlated invalid envelopes and types clear facts; unrelated garbage does not settle request', () => {
 const mutations=[v=>v.schema=2,v=>v.sample.gain=10001,v=>v.sample.gain=true,v=>v.sample.ageMs=-1,v=>v.acceptedRevision=0,v=>v.backend.outputCompiled=true,v=>v.backend.kind='<img>',v=>v.extra=1,v=>v.status='invalid-request',v=>v.action='save',v=>v.sample.timeValid='yes',v=>v.sample.revision=3,v=>v.initialized=false];
 for(const mutate of mutations) {
  const s=setup(), socket=new Socket(); s.observer.attach(socket); s.click();
  socket.emit('message',{data:'{broken'}); socket.emit('message',{data:new Uint8Array(1)});
  assert.equal(s.timers.size,1); const reply=snapshot(socket.sent[0].requestId); mutate(reply); socket.reply(reply);
  assert.equal(s.timers.size,0); assert.equal(s.values.textContent,''); assert.match(s.notice.textContent,/invalid/); s.observer.destroy();
 }
});
test('unknown sample stays unknown and model gain zero is a valid evaluated value', () => {
 const s=setup(), socket=new Socket(); s.observer.attach(socket); s.click();
 let reply=snapshot(socket.sent[0].requestId); reply.initialized=false; reply.hasAccepted=false; reply.acceptedRevision=0; reply.sample=null; reply.pendingEvaluation=true; socket.reply(reply);
 assert.match(s.values.textContent,/not yet sampled/); assert.doesNotMatch(s.values.textContent,/Evaluated gain:/);
 s.click(); reply=snapshot(socket.sent[1].requestId); reply.sample.gain=0; socket.reply(reply); assert.match(s.values.textContent,/0.00%/); s.observer.destroy();
});

test('all backend identities and gate combinations remain metadata, never output acknowledgments', () => {
 for(const kind of ['unknown','none','virtual','physical'])for(const gates of [[false,false,false],[true,false,false],[true,true,false],[true,true,true]]) {
  if(gates[2]&&(kind==='none'||kind==='unknown'))continue;
  const s=setup(), socket=new Socket(); s.observer.attach(socket); s.click();
  const reply=snapshot(socket.sent[0].requestId); reply.backend={kind,cacheCompiled:gates[0],outputCompiled:gates[1],rendererAttached:gates[2]};
  socket.reply(reply); assert.match(s.values.textContent,new RegExp('Backend: '+kind)); assert.match(s.values.textContent,/do not prove output/); s.observer.destroy();
 }
});
test('configuration listener, pending request and draft are independent of runtime lifecycle', () => {
 const s=setup(), socket=new Socket(), config={pending:true,revision:4,draft:'unsaved',reconcile:false};
 socket.addEventListener('message',event=>{const data=JSON.parse(event.data);if(data.command==='brightness-schedule'&&data.requestId==='config-save'){config.pending=false;config.revision=5;}});
 s.observer.attach(socket); s.click(); const deadline=[...s.timers.values()][0];
 socket.reply(snapshot(socket.sent[0].requestId)); assert.deepEqual(config,{pending:true,revision:4,draft:'unsaved',reconcile:false});
 s.click(); socket.reply({command:'brightness-schedule',requestId:'config-save',status:'saved'});
 assert.equal(s.timers.size,1); assert.equal(config.pending,false); assert.equal(config.revision,5);
 deadline(); assert.equal(s.timers.size,1); s.observer.destroy();
 assert.equal(config.draft,'unsaved'); assert.equal(config.reconcile,false);
});
