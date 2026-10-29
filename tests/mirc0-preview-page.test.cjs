/** Real binding with fake DOM/view/getters; not generated-page browser proof. */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const create=require("../webpage/mirc0-preview-page.js");
class Element{
 constructor(name,document){this.localName=name;this.ownerDocument=document;this.attrs={};this.children=[];this.listeners={};this.value="";this.textContent="";}
 setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return Object.hasOwn(this.attrs,k)?this.attrs[k]:null;}
 appendChild(n){this.children.push(n);return n;}removeChild(n){const i=this.children.indexOf(n);assert.ok(i>=0);this.children.splice(i,1);}
 addEventListener(n,f){(this.listeners[n]||(this.listeners[n]=new Set())).add(f);}removeEventListener(n,f){this.listeners[n].delete(f);}
 emit(n){for(const fn of this.listeners[n]||[])fn();}
}
const document={createElement(name){return new Element(name,document);},createElementNS(ns,name){assert.equal(ns,"http://www.w3.org/2000/svg");return new Element(name,document);}};
const host=new Element("div",document),existing=new Element("p",document);host.appendChild(existing);
let available=false,broken=false,reads=0,disposals=0;const colors=["#008000","#000000"],renders=[];
const options={available(){return available;},readColors(){reads+=1;return colors;},view:{create(svg){assert.equal(svg.localName,"svg");return {render(value){if(broken)throw new Error("Fixture invalid colour");renders.push(value);},destroy(){disposals+=1;}};}}};
const page=create(host,options);assert.throws(()=>create(host,options));assert.equal(reads,0);assert.equal(renders.length,0);
const panel=host.children[1],all=[];function walk(e){all.push(e);e.children.forEach(walk);}walk(panel);
const time=all.find(e=>e.getAttribute("id")==="mirc0-sample-time"),prefix=all.find(e=>e.getAttribute("id")==="mirc0-sample-prefix"),note=all.find(e=>e.getAttribute("data-mirc0")==="note");
assert.equal(panel.hidden,true);available=true;page.refresh();assert.equal(panel.hidden,false);
assert.deepEqual(renders.pop(),{hour:8,minute:50,prefix:true,foreground:"#008000",inactive:"#000000"});
time.value="23:59";time.emit("input");assert.equal(renders.at(-1).hour,23);assert.equal(renders.at(-1).minute,59);
prefix.checked=false;prefix.emit("change");assert.equal(renders.at(-1).prefix,false);
const count=renders.length;time.value="";time.emit("input");assert.equal(renders.length,count);assert.ok(note.textContent.includes("valid local sample time"));
time.value="00:04";colors[0]="#000080";page.refresh();assert.equal(renders.at(-1).foreground,"#000080");assert.equal(renders.at(-1).minute,4);assert.ok(note.textContent.includes("not device time or output telemetry"));
broken=true;page.refresh();assert.ok(note.textContent.includes("Preview unavailable"));broken=false;page.refresh();assert.ok(note.textContent.includes("Local sample only"));
available=false;const before=reads;page.refresh();assert.equal(reads,before);assert.equal(panel.hidden,true);
assert.ok(all.every(e=>!/(brightness|slider|transition)/.test(e.getAttribute("id")||"")));
assert.deepEqual(colors,["#000080","#000000"]);assert.equal(all.reduce((sum,e)=>sum+Object.values(e.listeners).reduce((n,set)=>n+set.size,0),0),2);
page.destroy();page.destroy();assert.equal(disposals,1);assert.deepEqual(host.children,[existing]);
assert.equal(all.reduce((sum,e)=>sum+Object.values(e.listeners).reduce((n,set)=>n+set.size,0),0),0);
const old=reads;page.refresh();time.emit("input");prefix.emit("change");assert.equal(reads,old);create(host,options).destroy();assert.equal(disposals,2);
const context=vm.createContext({window:{}});vm.runInContext(fs.readFileSync(require.resolve("../webpage/mirc0-preview-page.js"),"utf8"),context);assert.equal(typeof context.window.createWordclockMirc0PreviewPage,"function");
console.log(JSON.stringify({status:"PASS",scope:"page binding with injected read-only getters, fake SVG view and DOM"}));
