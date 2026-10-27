/** Renderer unit tests with a fake SVG DOM and injected model/adapter fixtures.
 * They test view lifecycle/callback isolation, not real browser hit-testing,
 * touch behavior, screen transforms, model parity, or the actual ESP32 page.
 */
"use strict";
const assert=require("node:assert/strict");
const create=require("../webpage/schedule-timeline-view.js");
let checks=0;
function equal(a,b){assert.deepEqual(a,b);checks+=1;}
function rejects(run){assert.throws(run);checks+=1;}
class Element {
 constructor(name,document){this.localName=name;this.ownerDocument=document;this.attrs={};this.children=[];this.listeners={};this.style={touchAction:"pan-y"};this.capture=new Set();}
 setAttribute(key,value){this.attrs[key]=String(value);}
 getAttribute(key){return Object.prototype.hasOwnProperty.call(this.attrs,key)?this.attrs[key]:null;}
 hasAttribute(key){return this.getAttribute(key)!==null;}
 removeAttribute(key){delete this.attrs[key];}
 appendChild(node){this.children.push(node);return node;}
 removeChild(node){const index=this.children.indexOf(node);assert.ok(index>=0);this.children.splice(index,1);return node;}
 get firstChild(){return this.children[0]||null;}
 addEventListener(name,callback){(this.listeners[name]||(this.listeners[name]=new Set())).add(callback);}
 removeEventListener(name,callback){this.listeners[name].delete(callback);}
 setPointerCapture(id){this.capture.add(id);}
 hasPointerCapture(id){return this.capture.has(id);}
 releasePointerCapture(id){this.capture.delete(id);this.emit("lostpointercapture",{pointerId:id});}
 createSVGPoint(){return {x:0,y:0,matrixTransform(){return {x:this.x,y:this.y};}};}
 getScreenCTM(){return {inverse(){return {};}};}
 emit(name,attributes){const event=Object.assign({target:this,button:0,isPrimary:true,pointerId:1,preventDefault(){}},attributes);for(const callback of this.listeners[name]||[])callback(event);}
}
function environment(){const document={createElementNS(namespace,name){return new Element(name,document);}};return new Element("svg",document);}
const clone=value=>JSON.parse(JSON.stringify(value));
const model={validate:clone,formatTime(minute){return String(Math.floor(minute/60)).padStart(2,"0")+":"+String(minute%60).padStart(2,"0");}};
const adapter={
 geometry(schedule,left,right){if(right<=left)throw new Error("Bad view");const event=schedule.events[0];return event?{lines:[{start:event.minute,end:event.minute+event.fadeMinutes,fromTenths:0,toTenths:event.targetTenths,eventIndex:0,kind:"linear"}],handles:[{kind:"start",minute:event.minute,targetTenths:0,eventIndex:0},{kind:"target",minute:event.minute+event.fadeMinutes,targetTenths:event.targetTenths,eventIndex:0}]}:{lines:[],handles:[]};},
 edit(schedule,index,start,end,target){const level=Number(target)*10;if(level>900)throw new Error("Fixture validation rejected target");const next=clone(schedule);const parse=text=>Number(text.slice(0,2))*60+Number(text.slice(3));next.events[index]={minute:parse(start),fadeMinutes:(parse(end)+1440-parse(start))%1440,targetTenths:level};return {schedule:next,index};}
};
const schedule={defaultTenths:400,events:[{minute:100,targetTenths:400,fadeMinutes:100}]};
function point(minute,level){return {clientX:65+minute*880/1440,clientY:255-level*230/1000};}
function setup(extra={}){const svg=environment(),edits=[],errors=[],selections=[];const view=create(svg,Object.assign({model,adapter,onEdit(value,index){edits.push([value,index]);},onError(message){errors.push(message);},onSelect(index){selections.push(index);}},extra));view.render(schedule,0,0,1440,true);return {svg,view,edits,errors,selections};}
function handle(svg,kind){return svg.children[0].children.find(item=>item.getAttribute("data-kind")===kind);}
function down(fixture,kind="target",id=1){fixture.svg.emit("pointerdown",{target:handle(fixture.svg,kind),pointerId:id});}
// Local move renders preview; only pointerup emits one detached edit.
{
 const test=setup(),before=JSON.stringify(schedule);down(test);
 test.svg.emit("pointermove",point(220,500));equal(test.edits.length,0);
 test.svg.emit("pointerup",{});equal(test.edits.length,1);equal(test.edits[0][0].events[0].targetTenths,500);
 equal(JSON.stringify(schedule),before);equal(test.svg.hasPointerCapture(1),false);
 test.svg.emit("pointerup",{});equal(test.edits.length,1);test.view.destroy();
}
// Cancel paths never call onEdit; stale/multiple pointer streams cannot complete a drag.
for(const kind of ["pointercancel","lostpointercapture","escape","external-render"]){
 const test=setup();down(test);test.svg.emit("pointermove",point(220,500));
 if(kind==="escape")test.svg.emit("keydown",{key:"Escape"});
 else if(kind==="external-render")test.view.render(schedule,0,0,1440,true);
 else test.svg.emit(kind,{});
 test.svg.emit("pointerup",{});equal(test.edits.length,0);equal(test.svg.hasPointerCapture(1),false);test.view.destroy();
}
{
 const test=setup();down(test);test.svg.emit("pointermove",Object.assign(point(220,500),{pointerId:2}));test.svg.emit("pointerup",{pointerId:2});equal(test.edits.length,0);test.svg.emit("pointerup",{});equal(test.edits.length,0);test.view.destroy();
}
// Invalid moves preserve the old accepted state and report a bounded error.
{
 const test=setup();down(test);test.svg.emit("pointermove",point(220,1000));test.svg.emit("pointerup",{});
 equal(test.edits.length,0);equal(test.errors.length,1);test.view.destroy();
}
// Read-only allows selection but never edits. Enter/Space select for numeric editing.
{
 const test=setup();test.view.render(schedule,0,0,1440,false);down(test);test.svg.emit("pointermove",point(220,500));test.svg.emit("pointerup",{});equal(test.edits.length,0);
 test.svg.emit("keydown",{target:handle(test.svg,"target"),key:"Enter"});equal(test.selections.length,2);test.view.destroy();
}
// A callback may veto, throw or synchronously provide a newer authoritative render.
{
 const test=setup({onEdit(){return false;}});down(test);test.svg.emit("pointermove",point(220,500));test.svg.emit("pointerup",{});equal(handle(test.svg,"target").getAttribute("aria-label").includes("40%"),true);test.view.destroy();
}
{
 const test=setup({onEdit(){throw new Error("Owner rejected edit");}});down(test);test.svg.emit("pointermove",point(220,500));test.svg.emit("pointerup",{});equal(test.errors[0],"Owner rejected edit");test.view.destroy();
}
{
 let view;const test=setup({onEdit(){const newer=clone(schedule);newer.events[0].targetTenths=700;view.render(newer,0,0,1440,true);}});view=test.view;
 down(test);test.svg.emit("pointermove",point(220,500));test.svg.emit("pointerup",{});equal(handle(test.svg,"target").getAttribute("aria-label").includes("70%"),true);test.view.destroy();
}
// Re-render and disposal do not leak listeners or remove unrelated SVG children.
{
 const svg=environment();svg.setAttribute("viewBox","1 2 3 4");const unrelated=svg.ownerDocument.createElementNS("","defs");svg.appendChild(unrelated);
 const view=create(svg,{model,adapter,onEdit(){}});rejects(()=>create(svg,{model,adapter,onEdit(){}}));
 for(let index=0;index<50;index+=1)view.render(schedule,0,0,1440,true);
 equal(Object.values(svg.listeners).reduce((total,set)=>total+set.size,0),6);
 view.destroy();view.destroy();equal(svg.children,[unrelated]);equal(svg.getAttribute("viewBox"),"1 2 3 4");equal(svg.style.touchAction,"pan-y");equal(Object.values(svg.listeners).reduce((total,set)=>total+set.size,0),0);
 rejects(()=>view.render(schedule,0,0,1440,true));const again=create(svg,{model,adapter,onEdit(){}});again.destroy();
}
console.log(JSON.stringify({status:"PASS",assertions:checks,scope:"fake SVG DOM and dependency fixtures"}));
