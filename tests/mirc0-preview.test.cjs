/** Physical-face and fake-SVG lifecycle tests; not browser or hardware proof. */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const preview=require("../webpage/mirc0-preview.js"),reference=require("./fixtures/mirc0-physical-face.json");
assert.deepEqual(preview.rows,reference.rows);assert.equal(Object.isFrozen(preview.rows),true);
const locations=new Set();for(let row=0;row<10;row+=1)for(let col=0;col<11;col+=1)locations.add(preview.logicalIndex(row,col));
assert.equal(locations.size,110);assert.equal(preview.logicalIndex(1,0),21);assert.equal(preview.logicalIndex(1,10),11);
for(const args of [[-1,0],[10,0],[0,11],[0,0.5]])assert.throws(()=>preview.logicalIndex(...args));
const photo=[0,1,3,4,33,34,36,37,38,51,52,53,54];assert.deepEqual(preview.mask(8,50),photo);
assert.deepEqual(preview.mask(8,50,false),photo.filter(i=>![0,1,3,4].includes(i)));
for(let time=0;time<1440;time+=1){
 const minute=time%60,lit=preview.mask(Math.floor(time/60),minute);
 assert.equal(new Set(lit).size,lit.length);assert.ok(lit.every(i=>Number.isInteger(i)&&i>=0&&i<114&&!(i>=7&&i<=10)));
 assert.deepEqual(lit.filter(i=>i>=110),reference.minute_dots.logical_indices.slice(0,minute%5));
}
for(const args of [[24,0],[-1,0],[0,60],[0,-1],[0,1.5],[0,0,"true"]])assert.throws(()=>preview.mask(...args));
class Element{
 constructor(name,document){this.localName=name;this.ownerDocument=document;this.attrs={};this.children=[];}
 setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return Object.hasOwn(this.attrs,k)?this.attrs[k]:null;}removeAttribute(k){delete this.attrs[k];}
 appendChild(n){this.children.push(n);return n;}removeChild(n){const i=this.children.indexOf(n);assert.ok(i>=0);this.children.splice(i,1);}
}
const document={createElementNS(ns,name){assert.equal(ns,"http://www.w3.org/2000/svg");return new Element(name,document);}},svg=new Element("svg",document);
svg.setAttribute("viewBox","1 2 3 4");svg.setAttribute("aria-label","Original");const defs=new Element("defs",document);svg.appendChild(defs);
const view=preview.create(svg);assert.throws(()=>preview.create(svg));const layer=svg.children[1];assert.equal(layer.children.length,115);
const letters=layer.children.filter(n=>n.localName==="text"),dots=layer.children.filter(n=>n.localName==="circle");assert.equal(letters.length,110);assert.equal(dots.length,4);
assert.equal(letters.map(n=>n.textContent).join(""),reference.rows.join(""));
for(let row=0;row<10;row+=1)for(let col=0;col<11;col+=1)assert.equal(letters[row*11+col].getAttribute("data-led-index"),String(preview.logicalIndex(row,col)));
assert.deepEqual(dots.map(n=>n.getAttribute("data-led-index")),["110","111","112","113"]);assert.ok(dots.every(n=>Number(n.getAttribute("cy"))>282));assert.equal(dots.reduce((sum,n)=>sum+Number(n.getAttribute("cx")),0)/4,165);
view.render({hour:8,minute:50,foreground:"#00ff00",inactive:"#445566"});
const active=()=>layer.children.filter(n=>n.getAttribute("data-lit")==="true").map(n=>Number(n.getAttribute("data-led-index"))).sort((a,b)=>a-b);
assert.deepEqual(active(),photo);assert.ok(layer.children.filter(n=>n.getAttribute("data-lit")==="true").every(n=>n.getAttribute("fill")==="#00ff00"));
assert.ok(svg.getAttribute("aria-label").includes("08:50"));assert.ok(svg.getAttribute("aria-label").includes("not device telemetry"));
const before=JSON.stringify(layer.children.map(n=>n.attrs));assert.throws(()=>view.render({hour:8,minute:50,foreground:"url(evil)"}));assert.throws(()=>view.render({hour:24,minute:0}));assert.equal(JSON.stringify(layer.children.map(n=>n.attrs)),before);
view.render({hour:23,minute:59,prefix:false});assert.deepEqual(active(),preview.mask(23,59,false));
view.destroy();view.destroy();assert.deepEqual(svg.children,[defs]);assert.equal(svg.getAttribute("viewBox"),"1 2 3 4");assert.equal(svg.getAttribute("aria-label"),"Original");assert.equal(svg.getAttribute("role"),null);assert.throws(()=>view.render({hour:0,minute:0}));preview.create(svg).destroy();
const context=vm.createContext({window:{}});vm.runInContext(fs.readFileSync(require.resolve("../webpage/mirc0-preview.js"),"utf8"),context);assert.equal(typeof context.window.WordclockMirc0Preview.create,"function");
console.log(JSON.stringify({status:"PASS",minutes:1440,cells:110,dots:4,scope:"physical fixture, pure sample masks and fake SVG lifecycle"}));
