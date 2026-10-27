/** Adapter integration with shared model, not the independent offline prototype. */
"use strict";
const assert=require("node:assert/strict");
const model=require("../webpage/schedule-model.js");
const adapter=require("../webpage/schedule-timeline-adapter.js")(model);
let count=0;
function equal(a,b){assert.deepEqual(a,b);count+=1;}
function reject(run){assert.throws(run);count+=1;}
function near(a,b){assert.ok(Math.abs(a-b)<1e-7);count+=1;}
const profile={defaultTenths:400,events:[{minute:420,targetTenths:400,fadeMinutes:0},{minute:1185,targetTenths:100,fadeMinutes:15},{minute:1230,targetTenths:0,fadeMinutes:5},{minute:1410,targetTenths:400,fadeMinutes:60}]};
const original=JSON.stringify(profile);
equal(adapter.resolveTiming("23:30","00:30","linear").fadeMinutes,60);
equal(adapter.resolveTiming("23:30","00:30","linear").nextDay,true);
equal(adapter.resolveTiming("23:30","23:45","linear").nextDay,false);
equal(adapter.resolveTiming("23:30","23:30","linear").transition,"instant");
equal(adapter.resolveTiming("23:30","","instant").fadeMinutes,0);
reject(()=>adapter.resolveTiming("23:30","","linear"));
reject(()=>adapter.resolveTiming("23:30","00:30","smooth"));
const edited=adapter.edit(profile,3,"23:30","00:30","40","linear");
equal(edited.schedule,profile);equal(edited.index,3);equal(JSON.stringify(profile),original);
reject(()=>adapter.edit(profile,3,"23:30","08:00","40","linear"));
reject(()=>adapter.edit(profile,3,"07:00","08:00","40","linear"));
equal(JSON.stringify(profile),original);
const reordered=adapter.edit(profile,3,"12:00","12:00","40","instant");
equal(reordered.index,1);equal(reordered.schedule.events[1].minute,720);
equal(adapter.add(profile,"12:00","40").schedule.events.length,5);
reject(()=>adapter.add(profile,"19:45","40"));
equal(adapter.remove({defaultTenths:900,events:[{minute:1,targetTenths:50,fadeMinutes:0}]},0),{defaultTenths:50,events:[]});
const single={defaultTenths:900,events:[{minute:600,targetTenths:50,fadeMinutes:60}]};
const empty={defaultTenths:5,events:[]};
// Check coverage and preview parity in full-day, evening and unwrapped midnight views.
function geometryCheck(value,left,right){
 const geometry=adapter.geometry(value,left,right),spans=geometry.lines.filter(line=>line.kind!=="instant");
 near(spans[0].start,left);near(spans[spans.length-1].end,right);
 for(let i=1;i<spans.length;i+=1)near(spans[i-1].end,spans[i].start);
 for(let time=left+0.25;time<right;time+=7){
  const line=spans.find(piece=>piece.start<=time&&time<piece.end);equal(Boolean(line),true);
  const projected=line.fromTenths+(line.toTenths-line.fromTenths)*(time-line.start)/(line.end-line.start);
  near(projected,model.sampleTenths(value,time%1440));
 }
 const keys=geometry.handles.map(handle=>`${handle.kind}/${handle.minute}/${handle.eventIndex}`);
 equal(new Set(keys).size,keys.length);
 return geometry;
}
for(const value of [profile,single,empty])for(const bounds of [[0,1440],[1080,1320],[1320,1560],[1440,2880]])geometryCheck(value,...bounds);
const night=adapter.geometry(profile,1320,1560);
equal(night.handles.find(handle=>handle.eventIndex===3&&handle.kind==="target").minute,1470);
const continuation=night.lines.find(line=>line.eventIndex===3&&line.start===1440&&line.kind==="linear");
equal([continuation.start,continuation.end,continuation.fromTenths,continuation.toTenths],[1440,1470,200,400]);
for(const bounds of [[-1,100],[0,0],[0,1441],[1320,2881],[NaN,10]])reject(()=>adapter.geometry(profile,...bounds));
let seed=731;
function random(limit){seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed%limit;}
for(let i=0;i<60;i+=1){
 const times=[...new Set(Array.from({length:1+random(16)},()=>random(1440)))].sort((a,b)=>a-b);
 const value={defaultTenths:random(1001),events:times.map((minute,index)=>{
  const gap=times.length===1?1440:(times[(index+1)%times.length]+1440-minute)%1440;
  return {minute,targetTenths:random(1001),fadeMinutes:random(Math.min(gap,1439)+1)};
 })};
 geometryCheck(value,0,1440);geometryCheck(value,1320,1560);
}
// Calls must delegate validation/segment construction to the injected model.
let validations=0,projections=0;
const spy=Object.assign({},model,{validate(value){validations+=1;return model.validate(value);},segments(value){projections+=1;return model.segments(value);}});
require("../webpage/schedule-timeline-adapter.js")(spy).geometry(profile,1320,1560);
equal(validations>0,true);equal(projections,1);
console.log(JSON.stringify({status:"PASS",assertions:count,generatedProfiles:60}));
