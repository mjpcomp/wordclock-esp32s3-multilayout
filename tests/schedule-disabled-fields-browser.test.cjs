/** Disabled-field paint checks with mocked peers; no configuration writes. */
"use strict";
const assert=require("node:assert/strict"),http=require("node:http"),fs=require("node:fs"),path=require("node:path");
const {chromium}=require("playwright"),{setTimeout:pause}=require("node:timers/promises");
const {peerFor}=require("./webpage-layout.test.cjs");
const output=path.join(__dirname,"../layout-evidence");
async function until(fn){const limit=Date.now()+10000;while(!fn()){if(Date.now()>limit)throw new Error("Mock peer condition timed out");await pause(20);}}
async function capture(page,width,phase,report){
 const fields=await page.evaluate(()=>{
  const luminance=text=>(text.match(/[\d.]+/g)||[]).slice(0,3).map(Number).map(c=>{c/=255;return c<=0.04045?c/12.92:Math.pow((c+0.055)/1.055,2.4);}).reduce((s,c,i)=>s+c*[0.2126,0.7152,0.0722][i],0);
  return Array.from(document.querySelectorAll("#schedule-editor input[type='number']:disabled, #schedule-editor input[type='time']:disabled, #schedule-editor select:disabled")).map(e=>{
   const s=getComputedStyle(e),fg=luminance(s.color),bg=luminance(s.backgroundColor);
   return {name:e.dataset.schedule,type:e.type,value:e.value,disabled:e.disabled,color:s.color,textFill:s.webkitTextFillColor,background:s.backgroundColor,opacity:s.opacity,height:e.getBoundingClientRect().height,
    contrast:(Math.max(fg,bg)+0.05)/(Math.min(fg,bg)+0.05)};
  });
 });
 assert.ok(fields.length>0);assert.ok(fields.some(f=>f.name==="all-day"));assert.ok(fields.some(f=>f.name==="end"));
 for(const f of fields){assert.equal(f.disabled,true);assert.equal(f.color,"rgb(82, 97, 113)");assert.equal(f.textFill,"rgb(82, 97, 113)");assert.equal(f.background,"rgb(228, 234, 240)");assert.equal(f.opacity,"1");assert.ok(f.height>0);assert.ok(f.contrast>=4.5);}
 report.measurements.push({width,phase,fields});
 if(phase!=="loading")await page.screenshot({path:path.join(output,"disabled-fields-"+width+"-"+phase+".png"),fullPage:true,animations:"disabled"});
}
async function exercise(browser,origin,width,mode,report){
 const context=await browser.newContext({locale:"en-US",viewport:{width,height:1000},reducedMotion:"reduce"});
 const page=await context.newPage();page.setDefaultTimeout(10000);const peer=peerFor(new URL(origin).host),errors=[],blocked=[];let held=null;
 page.on("pageerror",e=>errors.push(e.message));
 await context.route("**/*",route=>{const u=new URL(route.request().url());if(u.origin===origin&&(u.pathname==="/"||u.pathname==="/favicon.ico"))return route.continue();blocked.push(u.href);return route.abort();});
 await page.routeWebSocket(/.*/,socket=>peer.route({url:()=>socket.url(),close:args=>socket.close(args),onMessage:fn=>socket.onMessage(fn),send:message=>{
  const reply=JSON.parse(String(message));
  if(reply.command==="brightness-schedule"){
   if(mode==="legacy")delete reply.capabilities;
   if(mode==="loading"){held={socket,reply};return;}
  }
  socket.send(JSON.stringify(reply));
 }}));
 try{
  await page.goto(origin+"/",{waitUntil:"load"});await until(()=>peer.requests.some(r=>r.action==="get"));
  if(mode==="loading"){
   await until(()=>held!==null);await capture(page,width,"loading",report);
   held.socket.send(JSON.stringify(held.reply));
   await page.waitForFunction(()=>document.querySelector("[data-schedule='status']").textContent.includes("loaded"));
  }else{
   await page.waitForFunction(mode=>document.querySelector(mode==="legacy"?"[data-schedule='capabilities']":"[data-schedule='status']").textContent.includes(mode==="legacy"?"unavailable":"loaded"),mode);
   await capture(page,width,mode,report);
   if(mode==="loaded"){
    assert.equal(await page.locator("[data-schedule='all-day']").inputValue(),"37");
    await page.locator("[data-schedule='changes']").selectOption("0");
    await page.locator("[data-schedule='curve']").selectOption("instant");
    assert.equal(await page.locator("[data-schedule='end']").inputValue(),"07:30");
    await capture(page,width,"selected-instant",report);
   }else assert.equal(await page.locator("[data-schedule='save']").isDisabled(),true);
  }
  assert.equal(peer.connections,1);assert.ok(peer.requests.every(r=>r.action==="get"));assert.deepEqual(peer.numeric.filter(n=>n<200),[]);
  assert.deepEqual(peer.errors,[]);assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
 }finally{report.sessions.push({width,mode,requests:peer.requests,errors,blocked,peerErrors:peer.errors});await context.close();}
}
async function main(){
 fs.mkdirSync(output,{recursive:true});const html=fs.readFileSync(path.join(__dirname,"../.pio/build/webpage/index.html"));
 const server=http.createServer((req,res)=>{res.writeHead(req.url==="/"?200:204,{"Content-Type":"text/html; charset=utf-8"});res.end(req.url==="/"?html:undefined);});
 await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));const origin="http://127.0.0.1:"+server.address().port,report={scope:"Chromium disabled-field styling with simulated read-only peers; not hardware evidence",measurements:[],sessions:[]};let browser;
 try{browser=await chromium.launch({headless:true});for(const width of [320,1440])for(const mode of ["loaded","legacy","loading"])await exercise(browser,origin,width,mode,report);report.status="PASS";}
 catch(error){report.status="FAIL";report.error=error.stack||String(error);throw error;}
 finally{fs.writeFileSync(path.join(output,"disabled-fields.json"),JSON.stringify(report,null,2));if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
 console.log(JSON.stringify({status:report.status,sessions:report.sessions.length,measurements:report.measurements.length}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
