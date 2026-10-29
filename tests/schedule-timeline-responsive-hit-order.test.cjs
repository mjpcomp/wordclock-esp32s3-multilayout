/** Fake-DOM stacking regression; real pointer/save assertions remain in Chromium. */
"use strict";
const assert=require("node:assert/strict");
const create=require("../webpage/schedule-timeline-view.js");
class Element{
 constructor(name,document){this.localName=name;this.ownerDocument=document;this.attrs={};this.children=[];this.style={};}
 setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return Object.hasOwn(this.attrs,k)?this.attrs[k]:null;}hasAttribute(k){return this.getAttribute(k)!==null;}removeAttribute(k){delete this.attrs[k];}
 appendChild(n){this.children.push(n);return n;}removeChild(n){this.children.splice(this.children.indexOf(n),1);}get firstChild(){return this.children[0]||null;}
 addEventListener(){}removeEventListener(){}getBoundingClientRect(){return {width:1000};}
}
const document={createElementNS(ns,name){return new Element(name,document);}},svg=new Element("svg",document);
const clone=x=>JSON.parse(JSON.stringify(x));
const model={validate:clone,formatTime(){return "20:00";}};
const handles=[{kind:"target",minute:1200,targetTenths:100,eventIndex:0},{kind:"start",minute:1230,targetTenths:100,eventIndex:1}];
const adapter={geometry(){return {lines:[],handles};}};
const view=create(svg,{model,adapter,onEdit(){}});
const schedule={defaultTenths:400,events:[{minute:1185,fadeMinutes:15,targetTenths:100},{minute:1230,fadeMinutes:5,targetTenths:0}]};
for(let render=0;render<2;render+=1){
 view.render(schedule,0,0,1440,true);
 const nodes=svg.children[0].children,hits=nodes.filter(n=>n.hasAttribute("data-hit-kind")),visible=nodes.filter(n=>n.hasAttribute("data-kind"));
 assert.equal(hits.length,2);assert.equal(visible.length,2);
 const target=visible.find(n=>n.getAttribute("data-kind")==="target"),neighbor=hits.find(n=>n.getAttribute("data-index")==="1");
 assert.ok(Math.abs(Number(neighbor.getAttribute("cx"))-Number(target.getAttribute("cx")))<Number(neighbor.getAttribute("r")),"Fixture must include a neighbor hit area covering the visible target");
 assert.ok(Math.max(...hits.map(n=>nodes.indexOf(n)))<Math.min(...visible.map(n=>nodes.indexOf(n))),"Hit area painted over visible handle");
 assert.equal(target.getAttribute("data-index"),"0");
}
view.destroy();
console.log(JSON.stringify({status:"PASS",scope:"overlapping touch-area stacking; fake DOM, not browser hit testing"}));
