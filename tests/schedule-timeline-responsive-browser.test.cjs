/** Real Chromium: readable SVG, hidden-panel resize, local-only pointer edits. */
"use strict";
const assert=require("node:assert/strict"),http=require("node:http"),fs=require("node:fs"),path=require("node:path");
const {chromium}=require("playwright");
const {peerFor}=require("./webpage-layout.test.cjs");
const output=path.join(__dirname,"../layout-evidence");
async function ready(page){
 await page.waitForFunction(()=>{const s=document.querySelector(".schedule-chart"),b=s.getBoundingClientRect(),v=s.viewBox.baseVal;return b.width>120&&Math.abs(b.width-v.width)<1.1&&v.height===(b.width<600?224:248);});
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
}
async function inspect(page,width){
 const result=await page.evaluate(()=>{
  const svg=document.querySelector(".schedule-chart"),matrix=svg.getScreenCTM();
  const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};};
  const texts=Array.from(svg.querySelectorAll("text")).map(e=>({text:e.textContent,anchor:e.getAttribute("text-anchor"),fontPx:parseFloat(getComputedStyle(e).fontSize)*Math.hypot(matrix.c,matrix.d),...rect(e)}));
  const form=document.querySelector("#schedule-editor form"),style=getComputedStyle(form);
  return {bounds:rect(svg),texts,targets:Array.from(svg.querySelectorAll("[data-kind='target']")).map(rect),
   form:{height:style.height,rows:style.gridTemplateRows,rowGap:style.rowGap,alignContent:style.alignContent,
    children:Array.from(form.children).map(e=>({tag:e.tagName,slot:e.dataset.schedule||"",display:getComputedStyle(e).display,...rect(e),
     buttons:Array.from(e.querySelectorAll("button")).map(b=>({text:b.textContent,disabled:b.disabled,display:getComputedStyle(b).display,visibility:getComputedStyle(b).visibility,opacity:getComputedStyle(b).opacity,...rect(b)}))}))}};
 });
 for(const t of result.texts){assert.ok(t.fontPx>=11.8,"Tiny axis text at "+width);assert.ok(t.left>=result.bounds.left-1&&t.right<=result.bounds.right+1,"Clipped horizontal label at "+width);assert.ok(t.top>=result.bounds.top-1&&t.bottom<=result.bounds.bottom+1,"Clipped vertical label at "+width);}
 const ticks=result.texts.filter(t=>t.anchor==="middle").sort((a,b)=>a.left-b.left);
 for(let i=1;i<ticks.length;i+=1)assert.ok(ticks[i-1].right+3<=ticks[i].left,"Overlapping ticks at "+width);
 assert.ok(result.targets.length>0);for(const t of result.targets)assert.ok(t.width>=15.8,"Shrunk marker at "+width);
 assert.ok(result.bounds.height>=192&&result.bounds.height<=249);return {viewport:width,...result};
}
async function main(){
 fs.mkdirSync(output,{recursive:true});const html=fs.readFileSync(path.join(__dirname,"../.pio/build/webpage/index.html"));
 const server=http.createServer((req,res)=>{res.writeHead(req.url==="/"?200:204,{"Content-Type":"text/html; charset=utf-8"});res.end(req.url==="/"?html:undefined);});
 await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));const origin="http://127.0.0.1:"+server.address().port;
 const report={scope:"real Chromium with simulated peer; not hardware evidence",measurements:[],errors:[],blocked:[]};let browser,context;
 try{
  browser=await chromium.launch({headless:true});context=await browser.newContext({locale:"en-US",viewport:{width:1440,height:1000},reducedMotion:"reduce"});
  const page=await context.newPage();page.setDefaultTimeout(10000);const peer=peerFor(new URL(origin).host);report.peer=peer;
  page.on("pageerror",e=>report.errors.push(e.message));
  await context.route("**/*",route=>{const u=new URL(route.request().url());if(u.origin===origin&&(u.pathname==="/"||u.pathname==="/favicon.ico"))return route.continue();report.blocked.push(u.href);return route.abort();});
  await page.routeWebSocket(/.*/,peer.route);await page.goto(origin+"/",{waitUntil:"load"});
  await page.waitForFunction(()=>document.querySelector("[data-schedule='status']").textContent.includes("loaded"));
  for(const width of [320,480,768,1024,1440]){
   await page.locator("[data-navigation='settings'].pure-menu-link").evaluate(e=>e.click());await page.setViewportSize({width,height:1000});
   await page.locator("[data-navigation='main'].pure-menu-link").evaluate(e=>e.click());await ready(page);
   report.measurements.push(await inspect(page,width));await page.screenshot({path:path.join(output,"timeline-responsive-"+width+".png"),fullPage:true,animations:"disabled"});
   const target=page.locator(".schedule-chart [data-kind='target'][data-index='0']");await target.scrollIntoViewIfNeeded();const b=await target.boundingBox();assert.ok(b);
   const before=peer.requests.length;await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2,b.y+b.height/2-20,{steps:3});await page.mouse.up();
   await page.waitForFunction(()=>document.querySelector("[data-schedule='status']").textContent.includes("Unsaved changes"));assert.equal(peer.requests.length,before);
  }
  const target=page.locator(".schedule-chart [data-kind='target'][data-index='0']");await target.scrollIntoViewIfNeeded();const b=await target.boundingBox();assert.ok(b);
  const level=await page.locator("[data-schedule='target']").inputValue();await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2,b.y+b.height/2-10);
  await page.setViewportSize({width:1024,height:1000});await ready(page);await page.mouse.up();assert.equal(await page.locator("[data-schedule='target']").inputValue(),level,"Resize committed a stale drag");
  assert.equal(peer.connections,1);assert.deepEqual(peer.numeric.filter(n=>n<200),[]);assert.ok(peer.requests.every(r=>r.action==="get"));
  assert.deepEqual(peer.errors,[]);assert.deepEqual(report.errors,[]);assert.deepEqual(report.blocked,[]);report.status="PASS";
 }catch(error){report.status="FAIL";report.error=error.stack||String(error);throw error;}
 finally{fs.writeFileSync(path.join(output,"timeline-responsive.json"),JSON.stringify(report,null,2));if(context)await context.close();if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
 console.log(JSON.stringify({status:report.status,viewports:report.measurements.length}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
