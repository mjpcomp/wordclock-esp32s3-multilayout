/** Real Chromium; state/contrast checks with intentional saves to a simulated peer only. */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),http=require("node:http"),path=require("node:path");
const {chromium}=require("playwright");
const {setTimeout:pause}=require("node:timers/promises");
const model=require("../webpage/schedule-model.js");
const {peerFor}=require("./webpage-layout.test.cjs");
const output=path.join(__dirname,"../layout-evidence"),selector=name=>"[data-schedule='"+name+"']";
function peer(host,legacy){
 const base=peerFor(host),value={base,requests:[],errors:[],saves:0,hold:false,pending:null,socket:null,
  record:{revision:1,defaultTenths:370,events:[{minute:420,targetTenths:250,fadeMinutes:30},{minute:1425,targetTenths:750,fadeMinutes:30}]}};
 value.route=socket=>{
  value.socket=socket;let numeric;
  base.route({url:()=>socket.url(),close:args=>socket.close(args),send:message=>socket.send(message),onMessage:fn=>{numeric=fn;}});
  socket.onMessage(message=>{
   if(/^\d{3}/.test(String(message))){numeric(message);return;}
   try{
    const request=JSON.parse(String(message));value.requests.push(request);
    assert.equal(request.command,"brightness-schedule");assert.equal(request.schema,1);
    if(request.action==="save"){
     assert.equal(legacy,false);assert.equal(request.expectedRevision,value.record.revision);
     value.record={revision:value.record.revision+1,...model.validate({defaultTenths:request.defaultTenths,events:request.events})};value.saves+=1;
    }else assert.equal(request.action,"get");
    const reply={command:request.command,schema:1,requestId:request.requestId,action:request.action,status:request.action==="save"?"saved":"loaded",...value.record};
    if(!legacy)reply.capabilities={schema:1,configurationProtocol:true,rendererCacheCompiled:false,scheduleOutputCompiled:false};
    if(request.action==="save"&&value.hold)value.pending={socket,reply};else socket.send(JSON.stringify(reply));
   }catch(error){value.errors.push(error.stack||String(error));}
  });
 };
 value.ack=()=>{assert.ok(value.pending);value.pending.socket.send(JSON.stringify(value.pending.reply));value.pending=null;};return value;
}
async function until(predicate){const limit=Date.now()+10000;while(!predicate()){if(Date.now()>limit)throw new Error("Peer condition timed out");await pause(20);}}
async function enabled(page,name,value){await page.waitForFunction(({s,value})=>document.querySelector(s).disabled===!value,{s:selector(name),value});}
async function inspect(page,label,width,report){
 const data=await page.evaluate(()=>{
  const rgb=text=>(text.match(/[\d.]+/g)||[]).map(Number);
  const luminance=color=>rgb(color).slice(0,3).map(c=>{c/=255;return c<=0.04045?c/12.92:Math.pow((c+0.055)/1.055,2.4);}).reduce((sum,c,i)=>sum+c*[0.2126,0.7152,0.0722][i],0);
  const buttons=Array.from(document.querySelectorAll("#schedule-editor button")).map(e=>{
   const s=getComputedStyle(e),r=e.getBoundingClientRect(),fg=luminance(s.color),bg=luminance(s.backgroundColor);
   return {name:e.dataset.schedule,disabled:e.disabled,hidden:e.hidden,width:r.width,height:r.height,opacity:s.opacity,color:s.color,background:s.backgroundColor,backgroundImage:s.backgroundImage,
    contrast:(Math.max(fg,bg)+0.05)/(Math.min(fg,bg)+0.05),alpha:rgb(s.backgroundColor)[3]===undefined?1:rgb(s.backgroundColor)[3]};
  });
  return {buttons,status:document.querySelector("[data-schedule='status']").textContent,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth,
   choiceHeight:document.querySelector("[data-schedule='use-remote']").parentElement.getBoundingClientRect().height};
 });
 assert.equal(data.overflow,false);
 for(const b of data.buttons){
  if(b.hidden){assert.equal(b.height,0);continue;}
  assert.ok(b.height>=43.8,"Touch height lost: "+b.name);
  if(b.disabled){assert.equal(b.opacity,"1");assert.equal(b.alpha,1);assert.equal(b.backgroundImage,"none");assert.ok(b.contrast>=4.5,"Unreadable disabled control: "+b.name);}
 }
 report.measurements.push({label,width,...data});await page.screenshot({path:path.join(output,"action-states-"+width+"-"+label+".png"),fullPage:true,animations:"disabled"});return data;
}
async function exercise(browser,origin,width,legacy,report){
 const context=await browser.newContext({locale:"en-US",viewport:{width,height:1000},reducedMotion:"reduce"});
 const page=await context.newPage();page.setDefaultTimeout(10000);const mock=peer(new URL(origin).host,legacy),errors=[],blocked=[];
 page.on("pageerror",e=>errors.push(e.message));
 await context.route("**/*",route=>{const u=new URL(route.request().url());if(u.origin===origin&&(u.pathname==="/"||u.pathname==="/favicon.ico"))return route.continue();blocked.push(u.href);return route.abort();});
 await page.routeWebSocket(/.*/,mock.route);
 try{
  await page.goto(origin+"/",{waitUntil:"load"});
  await page.waitForFunction(legacy=>document.querySelector(legacy?"[data-schedule='capabilities']":"[data-schedule='status']").textContent.includes(legacy?"unavailable":"loaded"),legacy);
  await page.waitForFunction(()=>document.querySelector("#auto-bright-enabled").value==="0");
  const details=page.locator("#schedule-editor .schedule-build-details");assert.equal(await details.evaluate(e=>e.open),false);
  const clean=await inspect(page,legacy?"legacy":"clean",width,report);assert.equal(clean.choiceHeight,0);
  assert.equal(await page.locator(selector("discard")).isVisible(),false);
  if(legacy){await enabled(page,"save",false);await enabled(page,"apply",false);assert.equal(mock.saves,0);}
  else{
   await enabled(page,"save",true);await enabled(page,"apply",false);
   await page.locator(selector("changes")).selectOption("0");await enabled(page,"apply",true);
   await page.locator(selector("target")).fill("10");await page.locator(selector("apply")).click();
   assert.equal(mock.saves,0);assert.equal(await page.locator(selector("discard")).isVisible(),true);
   await inspect(page,"dirty",width,report);
   mock.hold=true;await page.locator(selector("save")).click();await until(()=>mock.saves===1&&mock.pending!==null);await enabled(page,"save",false);
   assert.equal(mock.saves,1);assert.equal(await page.locator(selector("save")).isVisible(),true);assert.equal(await page.locator(selector("reload")).isVisible(),true);
   assert.ok((await page.locator(selector("status")).textContent()).includes("Saving schedule"));await inspect(page,"saving",width,report);
   mock.ack();mock.hold=false;await enabled(page,"save",true);assert.equal(await page.locator(selector("discard")).isVisible(),false);
   assert.ok((await page.locator(selector("status")).textContent()).includes("saved"));
   await page.locator(selector("target")).fill("1");await page.locator(selector("apply")).click();
   mock.hold=true;await page.locator(selector("save")).click();await until(()=>mock.saves===2&&mock.pending!==null);await enabled(page,"save",false);assert.equal(mock.saves,2);
   await mock.socket.close({code:1001,reason:"Simulated uncertain acknowledgement"});await enabled(page,"save",false);
   await page.locator("#section-connection-lost .status-button").click();await enabled(page,"keep-draft",true);
   assert.equal(mock.base.connections,2);const choice=await inspect(page,"choice",width,report);assert.ok(choice.choiceHeight>=44);
   assert.equal(await page.locator(selector("use-remote")).isVisible(),true);
   await page.locator(selector("keep-draft")).click();await enabled(page,"save",true);
   assert.equal(await page.locator(selector("use-remote")).isVisible(),false);assert.equal(mock.saves,2);
   const restored=await inspect(page,"kept-draft",width,report);assert.equal(restored.choiceHeight,0);
  }
  await details.locator("summary").click();assert.equal(await details.evaluate(e=>e.open),true);
  assert.ok((await page.locator(selector("capabilities")).textContent()).includes(legacy?"unavailable":"Hardware readiness is not verified"));
  assert.deepEqual(mock.base.numeric.filter(n=>n<200),[]);assert.deepEqual(mock.base.errors,[]);assert.deepEqual(mock.errors,[]);assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
 }finally{report.sessions.push({width,legacy,requests:mock.requests,connections:mock.base.connections,saves:mock.saves,errors,blocked,peerErrors:mock.errors,numericErrors:mock.base.errors});await context.close();}
}
async function main(){
 fs.mkdirSync(output,{recursive:true});const html=fs.readFileSync(path.join(__dirname,"../.pio/build/webpage/index.html"));
 const server=http.createServer((req,res)=>{res.writeHead(req.url==="/"?200:204,{"Content-Type":"text/html; charset=utf-8"});res.end(req.url==="/"?html:undefined);});
 await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));const origin="http://127.0.0.1:"+server.address().port,report={scope:"Chromium action states; simulated saves, no device or hardware evidence",measurements:[],sessions:[]};let browser;
 try{browser=await chromium.launch({headless:true});for(const width of [320,1440]){await exercise(browser,origin,width,false,report);await exercise(browser,origin,width,true,report);}report.status="PASS";}
 catch(error){report.status="FAIL";report.error=error.stack||String(error);throw error;}
 finally{fs.writeFileSync(path.join(output,"action-states.json"),JSON.stringify(report,null,2));if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
 console.log(JSON.stringify({status:report.status,sessions:report.sessions.length}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
