/** Responsive DOM fixtures; actual browser coverage is a separate suite. */
"use strict";
const assert=require("node:assert/strict");
const create=require("../webpage/schedule-timeline-view.js");
function environment(){
 const document={width:282,createElementNS(ns,name){return new Element(name,document);}};
 const frames=new Map(),listeners=new Map();let sequence=0;
 const host={requestAnimationFrame(fn){frames.set(++sequence,fn);return sequence;},cancelAnimationFrame(id){frames.delete(id);},
  addEventListener(name,fn){listeners.set(name,fn);},removeEventListener(name,fn){assert.equal(listeners.get(name),fn);listeners.delete(name);}};
 host.ResizeObserver=class{constructor(fn){this.callback=fn;document.observer=this;}observe(node){assert.ok(node);}disconnect(){this.disconnected=true;}};
 document.defaultView=host;
 class Element{
  constructor(name,owner){this.localName=name;this.ownerDocument=owner;this.attrs={};this.children=[];this.listeners={};this.style={height:"auto",touchAction:"pan-y"};this.capture=new Set();}
  setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return Object.hasOwn(this.attrs,k)?this.attrs[k]:null;}hasAttribute(k){return this.getAttribute(k)!==null;}removeAttribute(k){delete this.attrs[k];}
  appendChild(n){this.children.push(n);return n;}removeChild(n){this.children.splice(this.children.indexOf(n),1);}get firstChild(){return this.children[0]||null;}
  addEventListener(n,f){(this.listeners[n]||(this.listeners[n]=new Set())).add(f);}removeEventListener(n,f){this.listeners[n].delete(f);}
  setPointerCapture(id){this.capture.add(id);}hasPointerCapture(id){return this.capture.has(id);}releasePointerCapture(id){this.capture.delete(id);this.emit("lostpointercapture",{pointerId:id});}
  createSVGPoint(){return {x:0,y:0,matrixTransform(){return {x:this.x,y:this.y};}};}getScreenCTM(){return {inverse(){return {};}};}
  getBoundingClientRect(){return {width:this.ownerDocument.width};}
  emit(name,more={}){const e={target:this,pointerId:1,button:0,isPrimary:true,preventDefault(){},...more};for(const f of this.listeners[name]||[])f(e);}
 }
 return {svg:new Element("svg",document),document,host,frames,listeners,flush(){const pending=[...frames.values()];frames.clear();for(const f of pending)f();}};
}
const clone=x=>JSON.parse(JSON.stringify(x));
const model={validate:clone,formatTime(m){return String(Math.floor(m/60)).padStart(2,"0")+":"+String(m%60).padStart(2,"0");}};
const adapter={geometry(s){const e=s.events[0];return {lines:[],handles:[{kind:"target",minute:e.minute+e.fadeMinutes,targetTenths:e.targetTenths,eventIndex:0}]};},
 edit(s,i,start,end,target){const next=clone(s);next.events[i].targetTenths=Number(target)*10;return {schedule:next,index:i};}};
const env=environment(),edits=[];
const view=create(env.svg,{model,adapter,onEdit(v){edits.push(v);}});
view.render({defaultTenths:400,events:[{minute:100,fadeMinutes:100,targetTenths:400}]},0,0,1440,true);
assert.equal(env.svg.getAttribute("viewBox"),"0 0 282 224");assert.equal(env.svg.style.height,"224px");
const handle=()=>env.svg.children[0].children.find(n=>n.getAttribute("data-kind")==="target");
assert.ok(env.svg.children[0].children.some(n=>n.getAttribute("data-hit-kind")==="target"&&n.getAttribute("r")==="22"));
assert.ok(env.svg.children[0].children.filter(n=>n.localName==="text"&&n.getAttribute("text-anchor")==="middle").length<=4);
env.document.width=0;env.document.observer.callback();env.flush();assert.equal(env.svg.getAttribute("viewBox"),"0 0 282 224");
env.document.width=442;env.document.observer.callback();env.document.observer.callback();assert.equal(env.frames.size,1);env.flush();
assert.equal(env.svg.getAttribute("viewBox"),"0 0 442 224");assert.equal(edits.length,0);
env.svg.emit("pointerdown",{target:handle()});env.svg.emit("pointermove",{clientX:150,clientY:97});
env.document.width=808;env.host.requestAnimationFrame(()=>{});env.document.observer.callback();env.flush();env.svg.emit("pointerup");
assert.equal(edits.length,0);assert.equal(env.svg.hasPointerCapture(1),false);assert.equal(env.svg.getAttribute("viewBox"),"0 0 808 248");
env.svg.emit("pointerdown",{target:handle()});env.svg.emit("pointermove",{clientX:148,clientY:109});env.svg.emit("pointerup");
assert.equal(edits.length,1);assert.equal(edits[0].events[0].targetTenths,500);
env.document.observer.callback();view.destroy();view.destroy();
assert.equal(env.document.observer.disconnected,true);assert.equal(env.frames.size,0);assert.equal(env.listeners.size,0);assert.equal(env.svg.style.height,"auto");
env.document.observer.callback();assert.equal(env.frames.size,0);
console.log(JSON.stringify({status:"PASS",scope:"responsive fake DOM lifecycle and pointer fixtures"}));
