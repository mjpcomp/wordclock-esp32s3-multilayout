/** Generated-page Mirc0 preview. All transport is mocked; one intentional legacy colour edit. */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),http=require("node:http"),path=require("node:path");
const {chromium}=require("playwright"),{setTimeout:pause}=require("node:timers/promises");
const {configuration,peerFor}=require("./webpage-layout.test.cjs");
const preview=require("../webpage/mirc0-preview.js"),reference=require("./fixtures/mirc0-physical-face.json");
const output=path.join(__dirname,"../layout-evidence");
async function until(fn){const limit=Date.now()+10000;while(!fn()){if(Date.now()>limit)throw new Error("Mock peer condition timed out");await pause(20);}}
async function lit(page){return page.locator("#mirc0-preview-panel [data-lit='true']").evaluateAll(nodes=>nodes.map(n=>Number(n.getAttribute("data-led-index"))).sort((a,b)=>a-b));}
async function measure(page,width,report){
 const data=await page.evaluate(()=>{
  const panel=document.querySelector("#mirc0-preview-panel"),svg=panel.querySelector("svg");
  const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};};
  const matrix=svg.getScreenCTM();return {panel:rect(panel),svg:rect(svg),letters:Array.from(svg.querySelectorAll("text")).map(e=>({letter:e.textContent,fontPx:parseFloat(getComputedStyle(e).fontSize)*Math.hypot(matrix.c,matrix.d),...rect(e)})),
   dots:Array.from(svg.querySelectorAll("circle")).map(rect),labels:Array.from(panel.querySelectorAll("label")).map(rect),
   overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth};
 });
 assert.equal(data.overflow,false);assert.equal(data.letters.length,110);assert.equal(data.dots.length,4);
 assert.equal(data.letters.map(t=>t.letter).join(""),reference.rows.join(""));
 for(const t of data.letters){assert.ok(t.fontPx>=12);assert.ok(t.left>=data.svg.left-1&&t.right<=data.svg.right+1);assert.ok(t.top>=data.svg.top-1&&t.bottom<=data.svg.bottom+1);}
 assert.ok(data.labels.every(r=>r.height>=43.8));assert.ok(data.dots.every(d=>d.top>Math.max(...data.letters.map(t=>t.bottom))));
 const center=data.dots.reduce((sum,d)=>sum+(d.left+d.right)/2,0)/4;assert.ok(Math.abs(center-(data.svg.left+data.svg.right)/2)<1);
 assert.deepEqual(await lit(page),preview.mask(8,50));report.measurements.push({width,...data});
 await page.screenshot({path:path.join(output,"mirc0-preview-"+width+".png"),fullPage:true,animations:"disabled"});
}
async function main(){
 fs.mkdirSync(output,{recursive:true});const html=fs.readFileSync(path.join(__dirname,"../.pio/build/webpage/index.html"));
 const server=http.createServer((req,res)=>{res.writeHead(req.url==="/"?200:204,{"Content-Type":"text/html; charset=utf-8"});res.end(req.url==="/"?html:undefined);});
 await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));const origin="http://127.0.0.1:"+server.address().port;
 const report={scope:"generated-page preview with simulated peer; not firmware or hardware proof",measurements:[],errors:[],blocked:[],intentionalLegacyColourWrites:[]};let browser,context,socket;
 const peer=peerFor(new URL(origin).host);report.peer=peer;
 try{
  browser=await chromium.launch({headless:true});context=await browser.newContext({locale:"en-US",viewport:{width:320,height:1000},reducedMotion:"reduce"});
  const page=await context.newPage();page.setDefaultTimeout(10000);page.on("pageerror",e=>report.errors.push(e.message));
  await context.route("**/*",route=>{const u=new URL(route.request().url());if(u.origin===origin&&(u.pathname==="/"||u.pathname==="/favicon.ico"))return route.continue();report.blocked.push(u.href);return route.abort();});
  await page.routeWebSocket(/.*/,ws=>{
   socket=ws;peer.route({url:()=>ws.url(),send:value=>ws.send(value),close:args=>ws.close(args),onMessage:fn=>ws.onMessage(message=>{
    const text=String(message);if(/^\d{3}/.test(text)&&Number(text.slice(0,3))<200){report.intentionalLegacyColourWrites.push(text);return;}fn(message);
   })});
  });
  await page.goto(origin+"/",{waitUntil:"load"});await page.locator("#mirc0-preview-panel").waitFor({state:"visible"});
  await page.waitForFunction(()=>document.querySelector("[data-schedule='status']").textContent.includes("loaded"));
  for(const width of [320,480,768,1024,1440]){
   await page.setViewportSize({width,height:1000});await page.locator(".pure-menu-link[data-navigation='settings']").evaluate(e=>e.click());
   await page.locator(".pure-menu-link[data-navigation='main']").evaluate(e=>e.click());await page.locator("#mirc0-preview-panel").waitFor({state:"visible"});
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));await measure(page,width,report);
  }
  assert.equal(report.intentionalLegacyColourWrites.length,0);
  const requests=peer.requests.length;await page.locator("#mirc0-sample-time").fill("08:54");assert.deepEqual(await lit(page),preview.mask(8,54));
  await page.locator("#mirc0-sample-prefix").uncheck();assert.deepEqual(await lit(page),preview.mask(8,54,false));
  await page.locator("#mirc0-sample-prefix").check();assert.equal(report.intentionalLegacyColourWrites.length,0);assert.equal(peer.requests.length,requests);
  socket.send(JSON.stringify({command:"set",prog:1,hsb00:240,hsb01:100,hsb02:50,hsb10:120,hsb11:100,hsb12:20,effectBri:2,effectSpeed:5,hasSpecialWordHappyBirthday:false,bitmapSymbol:7,hasSecondsFrame:false,colortype:1}));
  await page.waitForFunction(()=>document.querySelector("#mirc0-preview-panel [data-led-index='0']").getAttribute("fill").toLowerCase()==="#000080");
  assert.equal(await page.locator("#mirc0-preview-panel [data-led-index='2']").getAttribute("fill"),"#003300");assert.equal(report.intentionalLegacyColourWrites.length,0);
  await page.locator("#colorwheel-background").evaluate(e=>e.click());assert.equal(report.intentionalLegacyColourWrites.length,0);
  const wheel=page.locator("#color-picker svg").first();await wheel.scrollIntoViewIfNeeded();const box=await wheel.boundingBox();assert.ok(box&&box.width>0);
  await page.mouse.click(box.x+box.width*0.75,box.y+box.height*0.35);await until(()=>report.intentionalLegacyColourWrites.length>0);
  assert.equal(report.intentionalLegacyColourWrites.length,1);assert.ok(report.intentionalLegacyColourWrites[0].startsWith("001001"));
  socket.send(JSON.stringify({...configuration(),clockTypeDef:4}));await page.locator("#mirc0-preview-panel").waitFor({state:"hidden"});
  assert.equal(await page.locator(".box-color").evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(" ").length),2);
  socket.send(JSON.stringify(configuration()));await page.locator("#mirc0-preview-panel").waitFor({state:"visible"});
  assert.equal(await page.locator("#mirc0-preview-panel").count(),1);assert.deepEqual(await lit(page),preview.mask(8,54));
  assert.equal(peer.connections,1);assert.ok(peer.requests.every(r=>r.action==="get"));assert.deepEqual(peer.errors,[]);assert.deepEqual(report.errors,[]);assert.deepEqual(report.blocked,[]);
  assert.equal(report.intentionalLegacyColourWrites.length,1);report.status="PASS";
 }catch(error){report.status="FAIL";report.error=error.stack||String(error);throw error;}
 finally{fs.writeFileSync(path.join(output,"mirc0-preview.json"),JSON.stringify(report,null,2));if(context)await context.close();if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
 console.log(JSON.stringify({status:report.status,viewports:report.measurements.length,intentionalMockColourWrites:report.intentionalLegacyColourWrites.length}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
