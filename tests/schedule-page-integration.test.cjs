/** Actual JS model/client/adapter/controller; only transport and deadlines are fake.
 * JSON reply fixtures do not execute ArduinoJson, NVS, real sockets or DOM.
 */
"use strict";
const assert=require("node:assert/strict");
const model=require("../webpage/schedule-model.js");
const makeClient=require("../webpage/schedule-client.js");
const adapter=require("../webpage/schedule-timeline-adapter.js")(model);
const makeController=require("../webpage/schedule-page-controller.js");
let checks=0;
function equal(a,b){assert.deepEqual(a,b);checks+=1;}
function fixture(custom={}){
 const sent=[],states=[],tasks=new Map();let serial=0;
 const options=Object.assign({client:makeClient(model),model,adapter,onState(state,reason){states.push([state,reason]);},setTimeout(callback){const id=++serial;tasks.set(id,()=>{tasks.delete(id);callback();});return id;},clearTimeout(id){tasks.delete(id);},send(text,token){sent.push([JSON.parse(text),token]);}},custom);
 const controller=makeController(options);return {controller,options,sent,states,tasks};
}
const profile={defaultTenths:400,events:[{minute:420,targetTenths:400,fadeMinutes:0},{minute:1185,targetTenths:100,fadeMinutes:15},{minute:1230,targetTenths:0,fadeMinutes:5},{minute:1410,targetTenths:400,fadeMinutes:0}]};
function reply(request,schedule=profile,revision=1){return {command:"brightness-schedule",schema:1,requestId:request.requestId,action:request.action,status:request.action==="get"?"loaded":request.action==="reset"?"reset":"saved",revision,...schedule};}
function ready(){const test=fixture();test.token=test.controller.open();test.controller.receive(test.token,reply(test.sent[0][0]));return test;}
// Real adapter -> local draft -> explicit wire save -> exact client acknowledgement.
{
 const test=ready(),page=test.controller;equal(test.sent[0][0].action,"get");equal(test.tasks.size,0);
 page.select(3);equal(test.states[test.states.length-1][1],"selection");
 equal(page.updateSelected("23:30","00:30","40","linear"),true);
 equal(page.snapshot().draft.events[3].fadeMinutes,60);equal(test.sent.length,1);
 const lines=adapter.geometry(page.snapshot().draft,1320,1560).lines;
 equal(lines.find(line=>line.start===1440&&line.kind==="linear").fromTenths,200);
 const before=JSON.stringify(page.snapshot().draft);
 equal(page.updateSelected("23:30","08:00","40","linear"),false);equal(JSON.stringify(page.snapshot().draft),before);
 equal(page.save(),true);equal(page.snapshot().canEdit,false);equal(test.sent.length,2);
 const save=test.sent[1][0];equal(save.expectedRevision,1);equal(save.events[3].fadeMinutes,60);
 page.receive(test.token,reply(save,{defaultTenths:save.defaultTenths,events:save.events},2));
 equal(page.snapshot().dirty,false);equal(test.tasks.size,0);page.destroy();
}
// Real missing/default path is unsaved; a user Save uses expectedRevision zero.
{
 const test=fixture(),page=test.controller,token=page.open(),get=test.sent[0][0];
 page.receive(token,{command:get.command,schema:1,requestId:get.requestId,action:"get",status:"missing",revision:0,defaultTenths:1000,events:[],draft:true});
 equal(page.snapshot().dirty,true);equal(page.setAllDay("0.5"),true);equal(test.sent.length,1);
 page.save();equal(test.sent[1][0].expectedRevision,0);equal(test.sent[1][0].defaultTenths,5);page.destroy();
}
// Timeout cannot retry or discard uncertain state. Reload does not overwrite the draft.
{
 const test=ready(),page=test.controller;page.select(3);page.updateSelected("23:30","00:30","40","linear");page.save();
 const save=test.sent[1][0],deadline=[...test.tasks.values()][0];deadline();
 equal(page.snapshot().status,"outcome-unknown");equal(page.save(),false);equal(page.discard(),false);equal(test.sent.length,2);
 equal(page.reload(),true);const get=test.sent[2][0];deadline();equal(page.snapshot().pending.action,"get");
 page.receive(test.token,reply(get,{defaultTenths:save.defaultTenths,events:save.events},2));
 equal(page.snapshot().status,"reconcile-required");equal(page.snapshot().draft.events[3].fadeMinutes,60);
 equal(page.reconcile("keep-draft"),true);equal(page.snapshot().dirty,false);page.destroy();
}
// A stale socket close/reply cannot cancel a new generation's deadline.
{
 const test=ready(),page=test.controller;page.reload();const old=test.sent[1][0],token=page.open(),get=test.sent[2][0];
 equal(page.close(test.token),false);equal(page.receive(test.token,reply(old)),false);equal(test.tasks.size,1);
 equal(page.receive(token,"{"),false);equal(page.receive(token,{command:"autoBright"}),false);equal(test.tasks.size,1);
 page.receive(token,reply(get));equal(test.tasks.size,0);equal(page.snapshot().status,"reconcile-required");
 page.reconcile("use-remote");equal(page.snapshot().canSave,true);page.destroy();
}
// Real explicit reset flow and correlated error envelope without action.
{
 const test=ready(),page=test.controller;equal(page.reset(false),false);equal(test.sent.length,1);
 page.reset(true);const reset=test.sent[1][0];equal(reset.confirmReset,true);
 page.receive(test.token,reply(reset,{defaultTenths:1000,events:[]},2));equal(page.snapshot().draft.events,[]);
 page.setAllDay("25");page.save();const save=test.sent[2][0];
 page.receive(test.token,{command:save.command,schema:1,requestId:save.requestId,status:"invalid-request"});
 equal(page.snapshot().status,"invalid-request");equal(page.snapshot().needsReload,true);equal(test.tasks.size,0);page.destroy();
}
// A synchronous transport fixture response is matched with no deadline leak.
{
 let page;const test=fixture({send(text,token){page.receive(token,reply(JSON.parse(text)));}});page=test.controller;page.open();equal(test.tasks.size,0);equal(page.snapshot().canSave,true);page.destroy();
}
// False/throw send after begin is uncertain and never loses draft.
for(const mode of ["false","throw"]){
 const test=ready(),page=test.controller;page.replaceDraft({defaultTenths:5,events:[]},-1);
 test.options.send=()=>{if(mode==="throw")throw new Error("Transport");return false;};
 equal(page.save(),false);equal(page.snapshot().status,"outcome-unknown");equal(page.snapshot().draft.defaultTenths,5);equal(test.tasks.size,0);page.destroy();
}
console.log(JSON.stringify({status:"PASS",assertions:checks,scope:"real JS modules with simulated transport/deadlines"}));
