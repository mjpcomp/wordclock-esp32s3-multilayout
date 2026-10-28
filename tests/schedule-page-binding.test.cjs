/** Binding-unit tests: real binder, fake DOM/controller/view/model.
 * Not a browser, socket, shared-model composition or device test.
 */
"use strict";
const assert=require("node:assert/strict");
const create=require("../webpage/schedule-page-binding.js");
let checks=0;
function equal(actual,expected){assert.deepEqual(actual,expected);checks+=1;}
const names=["timeline","status","capabilities","changes","start","end","target","level-range","curve","all-day","add","apply","remove","save","reload","reset","discard","use-remote","keep-draft"];
class Element{
 constructor(document){this.ownerDocument=document;this.value="";this.disabled=false;this.children=[];this.listeners={};this.textContent="";}
 addEventListener(type,fn){(this.listeners[type]||(this.listeners[type]=new Set())).add(fn);}
 removeEventListener(type,fn){this.listeners[type].delete(fn);}
 appendChild(item){this.children.push(item);}
 removeChild(item){this.children.splice(this.children.indexOf(item),1);}
 get firstChild(){return this.children[0]||null;}
 emit(type){let prevented=false;for(const fn of this.listeners[type]||[])fn({preventDefault(){prevented=true;}});return prevented;}
}
function fixture(){
 const document={createElement(){return new Element(document);}},root=new Element(document),fields={};
 for(const name of names)fields[name]=new Element(document);
 root.querySelector=selector=>fields[selector.match(/'([^']+)'/)[1]]||null;
 const calls=[],paints=[];let controllerOptions,viewOptions,confirm=false;
 const state={connected:true,capabilities:{metadataState:"valid",configurationProtocol:true,rendererCacheCompiled:false,scheduleOutputCompiled:false},canEdit:true,canSave:true,canDiscard:true,pending:null,needsReload:false,remote:null,selected:0,view:[0,1440],status:"loaded",dirty:false,errorText:"",draft:{defaultTenths:400,events:[{minute:1185,targetTenths:100,fadeMinutes:15}]}};
 const snapshot=()=>JSON.parse(JSON.stringify(state));
 const controller={snapshot};
 for(const method of ["select","replaceDraft","setAllDay","updateSelected","add","removeSelected","save","reload","reset","discard","reconcile","open","close","receive","destroy"])controller[method]=(...args)=>{calls.push([method,...args]);return true;};
 const model={MAX_EVENTS:16,formatTime(value){return String(Math.floor(value/60)).padStart(2,"0")+":"+String(value%60).padStart(2,"0");},parsePercent(value){if(!/^(?:0|[1-9][0-9]?|100)(?:\.[0-9])?$/.test(value)||Number(value)>100)throw new Error("Invalid percentage");return Math.round(Number(value)*10);}};
 const options={controllerOptions:{model,adapter:{}},createController(value){controllerOptions=value;return controller;},createTimelineView(element,value){equal(element,fields.timeline);viewOptions=value;return {render(...args){paints.push(args);},destroy(){calls.push(["view-destroy"]);}};},confirmReset(){return confirm;}};
 const page=create(root,options);
 return {page,root,fields,state,calls,paints,options,emit(reason){controllerOptions.onState(snapshot(),reason);},view(){return viewOptions;},confirm(value){confirm=value;}};
}
{
 const test=fixture();equal(test.calls,[]);equal(test.fields.start.value,"19:45");equal(test.fields.end.value,"20:00");equal(test.fields.target.value,"10");
 equal(test.fields.save.disabled,false);equal(test.fields.capabilities.textContent.includes("Hardware readiness is not verified"),true);
 equal(test.fields.capabilities.textContent.includes("output=false"),true);
 test.fields.target.value="0.5";test.fields.target.emit("input");equal(test.fields["level-range"].value,"5");equal(test.calls,[]);
 test.fields["level-range"].value="7";test.fields["level-range"].emit("input");equal(test.fields.target.value,"0.7");equal(test.calls,[]);
 test.fields.apply.emit("click");equal(test.calls.pop(),["updateSelected","19:45","20:00","0.7","linear"]);
 test.fields.save.emit("click");equal(test.calls.pop(),["save"]);equal(test.root.emit("submit"),true);
 test.fields.target.value="bad";test.fields.target.emit("input");equal(test.fields.status.textContent,"Invalid percentage");
 test.state.selected=-1;test.emit();equal(test.fields["level-range"].value,"400");equal(test.fields.target.value,"40");
 test.state.selected=0;test.state.draft.events[0].minute=1410;test.state.draft.events[0].fadeMinutes=60;test.state.dirty=true;test.emit();
 equal(test.fields.end.value,"00:30");equal(test.fields.end.title.includes("tomorrow"),true);equal(test.fields.status.textContent.includes("Unsaved changes"),true);
 test.page.destroy();
}
{
 const test=fixture(),count=test.paints.length;test.emit("selection");equal(test.paints.length,count);
 test.view().onSelect(0);equal(test.calls.pop(),["select",0]);
 const draft={defaultTenths:20,events:[]};equal(test.view().onEdit(draft,-1),true);equal(test.calls.pop(),["replaceDraft",draft,-1]);
 test.state.pending={action:"save"};test.emit();equal(test.fields.save.disabled,true);equal(test.paints[test.paints.length-1][4],false);
 equal(test.view().onEdit(draft,-1),false);equal(test.calls,[]);test.fields.save.disabled=false;test.fields.save.emit("click");equal(test.calls,[]);test.page.destroy();
}
for(const capabilities of [null,{metadataState:"missing"},{metadataState:"invalid"},{metadataState:"valid",configurationProtocol:false}]){
 const test=fixture();test.state.capabilities=capabilities;test.emit();equal(test.fields.save.disabled,true);equal(test.fields.apply.disabled,true);
 test.fields.save.disabled=false;test.fields.save.emit("click");equal(test.calls,[]);
 test.fields.apply.disabled=false;test.fields.apply.emit("click");equal(test.calls,[]);equal(test.view().onEdit({defaultTenths:20,events:[]},-1),false);test.page.destroy();
}
{
 const test=fixture();test.fields.reset.emit("click");equal(test.calls,[]);
 test.confirm("true");test.fields.reset.emit("click");equal(test.calls,[]);
 test.confirm(true);test.fields.reset.emit("click");equal(test.calls.pop(),["reset",true]);
 test.state.needsReload=true;test.emit();equal(test.fields.reset.disabled,true);test.fields.reset.disabled=false;test.fields.reset.emit("click");equal(test.calls,[]);test.page.destroy();
}
{
 const test=fixture();test.fields.add.emit("click");equal(test.calls.pop(),["add","19:45","10"]);
 test.fields.remove.emit("click");equal(test.calls.pop(),["removeSelected"]);
 test.fields.discard.emit("click");equal(test.calls.pop(),["discard"]);
 test.fields.reload.emit("click");equal(test.calls.pop(),["reload"]);
 test.state.remote={revision:2};test.emit();test.fields["use-remote"].emit("click");equal(test.calls.pop(),["reconcile","use-remote"]);
 test.fields["keep-draft"].emit("click");equal(test.calls.pop(),["reconcile","keep-draft"]);
 test.state.draft.events=[];test.state.selected=-1;test.emit();equal(test.fields["all-day"].disabled,false);
 test.fields["all-day"].value="0";test.fields["all-day"].emit("change");equal(test.calls.pop(),["setAllDay","0"]);
 test.state.draft.events=Array.from({length:16},(_,index)=>({minute:index*90,targetTenths:100,fadeMinutes:0}));test.emit();equal(test.fields.add.disabled,true);test.page.destroy();
}
{
 const test=fixture();test.state.draft=null;test.state.canEdit=false;test.state.connected=false;test.emit();equal(test.fields.reload.disabled,true);equal(test.fields.save.disabled,true);
 test.state.errorText="<b>Rejected</b>";test.emit();equal(test.fields.status.textContent,"<b>Rejected</b>");test.page.destroy();
}
{
 const test=fixture();assert.throws(()=>create(test.root,test.options),/Unmounted/);checks+=1;
 const controls=Object.values(test.fields).concat(test.root);
 test.page.destroy();test.page.destroy();equal(test.calls,[["view-destroy"],["destroy"]]);
 equal(controls.reduce((total,element)=>total+Object.values(element.listeners).reduce((sum,set)=>sum+set.size,0),0),0);
 test.fields.save.emit("click");equal(test.calls.length,2);
 delete test.fields.start;assert.throws(()=>create(test.root,test.options),/Missing scheduler slot/);checks+=1;
}
console.log(JSON.stringify({status:"PASS",assertions:checks,scope:"binder with fake DOM/controller/view/model"}));
