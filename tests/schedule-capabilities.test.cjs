/** Real pure JS reader; fixtures are not ArduinoJson, sockets, firmware or DOM. */
"use strict";
const assert=require("node:assert/strict");
const vm=require("node:vm");
const fs=require("node:fs");
const path=require("node:path");
const read=require("../webpage/schedule-capabilities.js");
let checks=0;
function equal(actual,expected){assert.deepEqual(actual,expected);checks+=1;}
function off(state){return {metadataState:state,configurationProtocol:false,rendererCacheCompiled:false,scheduleOutputCompiled:false};}
function envelope(capabilities){return {command:"brightness-schedule",schema:1,capabilities};}
function facts(){return {schema:1,configurationProtocol:true,rendererCacheCompiled:true,scheduleOutputCompiled:true};}
const legacy={command:"brightness-schedule",schema:1};
equal(read(legacy),off("missing"));
for(const input of [null,undefined,[],"{}",{},false,{command:"autoBright",schema:1},{command:"brightness-schedule",schema:true},{command:"brightness-schedule",schema:2}])equal(read(input),off("invalid"));
for(const input of [null,undefined,[],false,1,"true",{},Object.assign(facts(),{schema:2}),Object.assign(facts(),{schema:true})])equal(read(envelope(input)),off("invalid"));
for(const name of ["configurationProtocol","rendererCacheCompiled","scheduleOutputCompiled"]){
 for(const value of [0,1,"true","false",null,undefined,[],{}])equal(read(envelope(Object.assign(facts(),{[name]:value}))),off("invalid"));
 const missing=facts();delete missing[name];equal(read(envelope(missing)),off("invalid"));
}
const inherited=Object.create(facts());equal(read(envelope(inherited)),off("invalid"));
for(const configurationProtocol of [false,true]){
 for(const rendererCacheCompiled of [false,true]){
  for(const scheduleOutputCompiled of [false,true]){
   const input=envelope({schema:1,configurationProtocol,rendererCacheCompiled,scheduleOutputCompiled});
   const before=JSON.stringify(input),result=read(input);
   equal(result,{metadataState:"valid",configurationProtocol,rendererCacheCompiled,scheduleOutputCompiled});
   equal(JSON.stringify(input),before);equal(Object.isFrozen(result),true);
  }
 }
}
const input=envelope(facts()),result=read(input);input.capabilities.rendererCacheCompiled=false;
equal(result.rendererCacheCompiled,true);
assert.throws(()=>{result.scheduleOutputCompiled=false;},TypeError);checks+=1;
equal(read(envelope(Object.assign(facts(),{futureField:"ignored"}))).metadataState,"valid");
// Stateless legacy/reconnect fallback must never retain the previous build facts.
read(envelope(facts()));equal(read(legacy),off("missing"));equal(read(envelope(null)),off("invalid"));
// The browser global and CommonJS entry points expose the same pure reader.
const browser={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,"../webpage/schedule-capabilities.js"),"utf8"),browser);
equal(typeof browser.window.readWordclockScheduleCapabilities,"function");
equal(JSON.parse(JSON.stringify(browser.window.readWordclockScheduleCapabilities(envelope(facts())))),read(envelope(facts())));
console.log(JSON.stringify({status:"PASS",assertions:checks,scope:"pure capability reader; no live-page or device execution"}));
