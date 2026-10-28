/** Real controller/client/model/reader; simulated transport/timers, no device/DOM.
 * Timeline editing is not exercised here; existing page integration covers it.
 */
"use strict";
const assert=require("node:assert/strict");
const model=require("../webpage/schedule-model.js");
const makeClient=require("../webpage/schedule-client.js");
const makeController=require("../webpage/schedule-page-controller.js");
const read=require("../webpage/schedule-capabilities.js");
let checks=0;
function equal(actual,expected){assert.deepEqual(actual,expected);checks+=1;}
function off(state="missing"){return {metadataState:state,configurationProtocol:false,rendererCacheCompiled:false,scheduleOutputCompiled:false};}
function facts(){return {schema:1,configurationProtocol:true,rendererCacheCompiled:true,scheduleOutputCompiled:true};}
function fixture(withReader=true){
 const sent=[],states=[],tasks=new Map();let serial=0;
 const options={client:makeClient(model),model,adapter:{},send(text,token){sent.push([JSON.parse(text),token]);},onState(state){states.push(state);},setTimeout(callback){tasks.set(++serial,callback);return serial;},clearTimeout(id){tasks.delete(id);}};
 if(withReader)options.readCapabilities=read;
 const page=makeController(options);
 return {page,options,sent,states,tasks,last(){return sent[sent.length-1][0];}};
}
function reply(request,capabilities=facts()){
 return {command:request.command,schema:1,requestId:request.requestId,action:request.action,status:request.action==="get"?"loaded":"saved",revision:request.action==="get"?1:request.expectedRevision+1,defaultTenths:400,events:[],capabilities};
}
function ready(){const test=fixture();test.token=test.page.open();test.page.receive(test.token,reply(test.last()));return test;}
{
 const test=fixture();equal(test.sent.length,0);equal(test.page.snapshot().capabilities,off());
 const token=test.page.open();equal(test.states[test.states.length-1].capabilities,off());
 equal(test.page.receive(token,reply(test.last())),true);
 equal(test.page.snapshot().capabilities,{metadataState:"valid",configurationProtocol:true,rendererCacheCompiled:true,scheduleOutputCompiled:true});
 equal(test.states[test.states.length-1].capabilities.metadataState,"valid");
 const snapshot=test.page.snapshot();snapshot.capabilities.rendererCacheCompiled=false;equal(test.page.snapshot().capabilities.rendererCacheCompiled,true);
 equal(test.tasks.size,0);test.page.destroy();equal(test.page.snapshot().capabilities,off());
}
{
 const test=ready(),page=test.page;page.reload();const request=test.last();
 equal(page.receive(test.token+1,reply(request)),false);
 equal(page.receive(test.token,Object.assign(reply(request),{requestId:"obsolete"})),false);
 equal(page.receive(test.token,"{"),false);equal(page.snapshot().capabilities.metadataState,"valid");equal(test.tasks.size,1);
 const legacy=reply(request);delete legacy.capabilities;
 page.receive(test.token,legacy);equal(page.snapshot().capabilities,off());equal(test.tasks.size,0);page.destroy();
}
{
 const test=ready(),page=test.page;page.reload();
 // Client receive() consumes malformed correlated replies too: true is not acceptance.
 page.receive(test.token,Object.assign(reply(test.last()),{action:"save"}));
 equal(page.snapshot().status,"invalid-reply");equal(page.snapshot().capabilities,off("invalid"));equal(test.tasks.size,0);page.destroy();
}
{
 const test=ready(),page=test.page;page.save();
 page.receive(test.token,Object.assign(reply(test.last()),{defaultTenths:500}));
 equal(page.snapshot().status,"outcome-unknown");equal(page.snapshot().capabilities,off("invalid"));
 equal(page.snapshot().draft.defaultTenths,400);equal(page.snapshot().needsReload,true);page.destroy();
}
{
 const test=ready(),page=test.page,old=test.token;page.reload();const stale=reply(test.last());
 const token=page.open();equal(page.snapshot().capabilities,off());
 equal(page.receive(old,stale),false);equal(page.close(old),false);equal(test.tasks.size,1);
 page.receive(token,reply(test.last()));equal(page.snapshot().capabilities.metadataState,"valid");
 equal(page.close(old),false);equal(page.snapshot().capabilities.metadataState,"valid");
 equal(page.close(token),true);equal(page.snapshot().capabilities,off());
 equal(page.receive(token,reply(test.last())),false);equal(page.snapshot().capabilities,off());page.destroy();
}
for(const metadata of [null,{schema:2},{schema:1,configurationProtocol:"true",rendererCacheCompiled:true,scheduleOutputCompiled:true}]){
 const test=fixture(),token=test.page.open();test.page.receive(token,reply(test.last(),metadata));
 equal(test.page.snapshot().status,"loaded");equal(test.page.snapshot().capabilities,off("invalid"));test.page.destroy();
}
{
 const test=fixture(false),token=test.page.open();test.page.receive(token,reply(test.last()));
 equal(test.page.snapshot().capabilities,off());equal(test.page.snapshot().status,"loaded");test.page.destroy();
 assert.throws(()=>makeController(Object.assign({},test.options,{readCapabilities:null})),/Capability reader/);checks+=1;
}
{
 const test=ready(),page=test.page;page.reload();const request=test.last();
 page.receive(test.token,{command:request.command,schema:1,requestId:request.requestId,action:"get",status:"read-failed",capabilities:facts()});
 equal(page.snapshot().status,"read-failed");equal(page.snapshot().capabilities.metadataState,"valid");page.destroy();
}
console.log(JSON.stringify({status:"PASS",assertions:checks,scope:"actual controller/client/model/reader with simulated transport"}));
