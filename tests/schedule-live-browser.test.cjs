/** Actual Chromium + built page. Firmware peer is simulated: no NVS/device/LED proof. */
"use strict";
const assert=require("node:assert/strict");
const http=require("node:http");
const fs=require("node:fs");
const path=require("node:path");
const {setTimeout:pause}=require("node:timers/promises");
const {chromium}=require("playwright");
const model=require("../webpage/schedule-model.js");
let checks=0;
function equal(actual,expected){assert.deepEqual(actual,expected);checks+=1;}
const copy=value=>JSON.parse(JSON.stringify(value));
const profile={defaultTenths:400,events:[{minute:420,targetTenths:400,fadeMinutes:10},{minute:1185,targetTenths:100,fadeMinutes:15},{minute:1230,targetTenths:0,fadeMinutes:5}]};
const capabilities={schema:1,configurationProtocol:true,rendererCacheCompiled:false,scheduleOutputCompiled:false};
const selector=name=>"[data-schedule='"+name+"']";
async function until(predicate){const limit=Date.now()+10000;while(!predicate()){if(Date.now()>limit)throw new Error("Peer condition timed out");await pause(20);}}
async function disabled(page,name,value){await page.waitForFunction(({selector,value})=>{const element=document.querySelector(selector);return element&&element.disabled===value;},{selector:selector(name),value});checks+=1;}
function peerFor(mode,host){
 const peer={record:mode==="missing"?null:{revision:1,...copy(profile)},requests:[],numeric:[],errors:[],connections:0,saves:0,resets:0,holdSave:false,pending:null,ws:null};
 peer.envelope=request=>{
  const reply={command:"brightness-schedule",schema:1,requestId:request.requestId,action:request.action};
  if(mode!=="legacy")reply.capabilities=mode==="malformed"?{schema:1,configurationProtocol:"true"}:capabilities;
  return reply;
 };
 peer.route=ws=>{
  peer.connections+=1;peer.ws=ws;
  if(new URL(ws.url()).host!==host){peer.errors.push("Unexpected WebSocket URL: "+ws.url());void ws.close({code:1008});return;}
  ws.onMessage(message=>{
   const value=String(message);
   if(/^\d{3}/.test(value)){peer.numeric.push(Number(value.slice(0,3)));return;}
   try{
    const request=JSON.parse(value);peer.requests.push(request);
    assert.equal(request.command,"brightness-schedule");assert.equal(request.schema,1);
    let reply=peer.envelope(request);
    if(request.action==="get"){
     reply=peer.record?{...reply,status:"loaded",...copy(peer.record)}:{...reply,status:"missing",revision:0,defaultTenths:1000,events:[],draft:true};
    }else if(request.action==="save"){
     assert.equal(request.expectedRevision,peer.record?peer.record.revision:0);
     peer.record={revision:request.expectedRevision+1,...model.validate({defaultTenths:request.defaultTenths,events:request.events})};peer.saves+=1;
     reply={...reply,status:"saved",...copy(peer.record)};
     if(peer.holdSave){peer.pending={ws,reply};return;}
    }else if(request.action==="reset"){
     assert.equal(request.confirmReset,true);assert.equal(request.expectedRevision,peer.record?peer.record.revision:0);
     peer.record={revision:request.expectedRevision+1,defaultTenths:1000,events:[]};peer.resets+=1;reply={...reply,status:"reset",...copy(peer.record)};
    }else throw new Error("Unexpected scheduler action");
    ws.send(JSON.stringify(reply));
   }catch(error){peer.errors.push(error.stack||String(error));}
  });
 };
 peer.ack=()=>{assert.ok(peer.pending);peer.pending.ws.send(JSON.stringify(peer.pending.reply));peer.pending=null;};
 return peer;
}
async function exercise(browser,origin,mode){
 const context=await browser.newContext({locale:"en-US",viewport:{width:1280,height:1000}});
 const page=await context.newPage();page.setDefaultTimeout(10000);
 const errors=[],blocked=[],peer=peerFor(mode,new URL(origin).host);
 page.on("pageerror",error=>errors.push(error.message));
 await context.route("**/*",route=>{
  const url=new URL(route.request().url());
  if(url.origin===origin&&(url.pathname==="/"||url.pathname==="/favicon.ico"))return route.continue();
  blocked.push(url.href);return route.abort();
 });
 // No connectToServer(): this is a fully mocked peer, never a real clock socket.
 await page.routeWebSocket(/^ws:/,peer.route);
 try{
  await page.goto(origin+"/",{waitUntil:"load"});
  await page.locator("#schedule-editor").waitFor({state:"visible"});
  await until(()=>peer.requests.some(request=>request.action==="get"));
  if(mode==="legacy"||mode==="malformed"){
   await page.waitForFunction(()=>document.querySelector("[data-schedule='capabilities']").textContent.includes("unavailable"));
   await disabled(page,"save",true);await disabled(page,"apply",true);await disabled(page,"reload",false);
   equal(peer.saves,0);equal(peer.resets,0);
  }else{
   await disabled(page,"save",false);
   if(mode==="missing"){
    await disabled(page,"all-day",false);
    await page.locator(selector("all-day")).fill("0.5");await page.locator(selector("all-day")).dispatchEvent("change");
    equal(peer.record,null);equal(peer.saves,0);
    await page.locator(selector("save")).click();await until(()=>peer.saves===1);await disabled(page,"save",false);
    equal(peer.requests.find(request=>request.action==="save").expectedRevision,0);equal(peer.record.defaultTenths,5);
   }else{
    equal((await page.locator(selector("capabilities")).textContent()).includes("Hardware readiness is not verified"),true);
    const originalMode=await page.locator("#auto-bright-enabled").inputValue();
    await page.locator(selector("changes")).selectOption("1");
    equal(await page.locator(selector("start")).inputValue(),"19:45");equal(await page.locator(selector("end")).inputValue(),"20:00");
    const before=peer.requests.length;
    const handle=page.locator(selector("timeline")+" [data-kind='target'][data-index='1']");
    await handle.scrollIntoViewIfNeeded();const box=await handle.boundingBox();assert.ok(box&&box.width>0);checks+=1;
    await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();
    await page.mouse.move(box.x+box.width/2+3,box.y+box.height/2-4,{steps:3});await page.mouse.up();
    await page.waitForFunction(()=>document.querySelector("[data-schedule='status']").textContent.includes("Unsaved changes"));
    equal(peer.requests.length,before);equal(peer.saves,0);
    await page.locator(selector("start")).fill("19:45");await page.locator(selector("end")).fill("20:00");
    await page.locator(selector("target")).fill("0.5");equal(await page.locator(selector("level-range")).inputValue(),"5");
    await page.locator(selector("level-range")).focus();await page.locator(selector("level-range")).press("ArrowRight");
    equal(await page.locator(selector("target")).inputValue(),"0.6");
    await page.locator(selector("target")).fill("0.5");await page.locator(selector("apply")).click();
    equal(peer.record.events[1].targetTenths,100);equal(peer.requests.length,before);
    peer.holdSave=true;await page.locator(selector("save")).click();await until(()=>peer.saves===1);
    await disabled(page,"save",true);await disabled(page,"apply",true);
    equal(peer.record.events[1].targetTenths,5);peer.ack();peer.holdSave=false;
    await disabled(page,"save",false);
    equal((await page.locator(selector("status")).textContent()).includes("Unsaved changes"),false);
    page.once("dialog",async dialog=>{await dialog.dismiss();});await page.locator(selector("reset")).click();equal(peer.resets,0);
    await page.locator(selector("target")).fill("1.0");await page.locator(selector("apply")).click();
    peer.holdSave=true;await page.locator(selector("save")).click();await until(()=>peer.saves===2);
    await peer.ws.close({code:1001,reason:"Simulated lost acknowledgement"});
    await disabled(page,"save",true);
    await page.locator("#section-connection-lost .status-button").click();
    await until(()=>peer.connections===2);await disabled(page,"keep-draft",false);await disabled(page,"save",true);
    equal(peer.saves,2);await page.locator(selector("keep-draft")).click();await disabled(page,"save",false);
    equal(peer.saves,2);equal(await page.locator(selector("target")).inputValue(),"1");
    page.once("dialog",async dialog=>{await dialog.accept();});await page.locator(selector("reset")).click();
    await until(()=>peer.resets===1);await disabled(page,"save",false);
    equal(peer.record.events,[]);equal(peer.record.defaultTenths,1000);
    equal(await page.locator("#auto-bright-enabled").inputValue(),originalMode);
   }
  }
  equal(peer.numeric.filter(command=>command<200),[]);
  equal(peer.errors,[]);equal(errors,[]);equal(blocked,[]);
 }catch(error){
  console.error(JSON.stringify({mode,pageErrors:errors,blocked,peerErrors:peer.errors,requests:peer.requests}));throw error;
 }finally{await context.close();}
}
async function main(){
 const html=fs.readFileSync(path.join(__dirname,"../.pio/build/webpage/index.html"));
 const server=http.createServer((request,response)=>{
  if(request.url==="/"){response.writeHead(200,{"Content-Type":"text/html; charset=utf-8"});response.end(html);}
  else{response.writeHead(204);response.end();}
 });
 await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
 const origin="http://127.0.0.1:"+server.address().port;
 let browser;
 try{
  browser=await chromium.launch({headless:true});
  for(const mode of ["normal","missing","legacy","malformed"])await exercise(browser,origin,mode);
  console.log(JSON.stringify({status:"PASS",assertions:checks,scope:"actual Chromium and generated page; simulated firmware peer only"}));
 }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
