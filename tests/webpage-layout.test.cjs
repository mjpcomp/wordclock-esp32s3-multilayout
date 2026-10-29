/** Chromium measurements of generated UI; simulated peer, no clock connection.
 * Baseline diagnostics: overflow is recorded, not declared fixed by this test.
 * CI fails on page/protocol errors or any settings mutation, not known spacing.
 */
"use strict";
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const output = path.join(__dirname, "../layout-evidence");
const capabilities = {schema:1, configurationProtocol:true, rendererCacheCompiled:false, scheduleOutputCompiled:false};
const schedule = {revision:1, defaultTenths:370, events:[
    {minute:420, targetTenths:250, fadeMinutes:30},
    {minute:1425, targetTenths:750, fadeMinutes:30}
]};
function configuration() {
    const value = {command:"config", ssid:"Fixture network", timeserver:"pool.ntp.org",
        timezone:"PST8PDT,M3.2.0,M11.1.0", hostname:"WordClock", scrollingText:"HELLO WORLD",
        itIsVariant:0, effectBri:2, effectSpeed:5, secondVariant:0, minuteVariant:1,
        supportedMinuteVariants:3, apiKey:"", cityid:"", clockTypeDef:36, buildtype:0,
        wType:1, colortype:1, bitmapSymbol:7, ledPin:5, powerButtonPin:255,
        modeButtonPin:255, speedButtonPin:255, i2cSdaPin:255, i2cSclPin:255,
        bootLedBlink:false, bootLedSweep:false, bootShowWifi:true, bootShowIP:false,
        hasSecondsFrame:false, isRomanLanguage:false, hasDreiviertel:false,
        hasTwenty:true, hasWeatherLayout:false, hasSpecialWordHappyBirthday:false,
        autoBrightEnabled:0};
    for (const hour of [6,8,12,16,18,20,22,24]) value["h"+hour] = 100;
    for (let index=0; index<5; index+=1) value["langVar"+index] = index===1 || index===2 ? 1 : 0;
    for (let index=0; index<6; index+=1) value["layVar"+index] = index===5;
    return value;
}
function peerFor(host) {
    const peer = {errors:[], numeric:[], requests:[], connections:0};
    peer.route = socket => {
        peer.connections+=1;
        if (new URL(socket.url()).host!==host) {
            peer.errors.push("Blocked unexpected socket target");
            void socket.close({code:1008}); return;
        }
        socket.onMessage(message => {
            try {
                const text = String(message);
                if (/^\d{3}/.test(text)) {
                    const command = Number(text.slice(0,3)); peer.numeric.push(command);
                    assert.ok(command>=200, "Settings mutation attempted: "+command);
                    let reply;
                    if (command===200) reply=configuration();
                    else if (command===201) reply={command:"set", prog:1, hsb00:120, hsb01:100,
                        hsb02:50, hsb10:0, hsb11:0, hsb12:0, effectBri:2, effectSpeed:5,
                        hasSpecialWordHappyBirthday:false, bitmapSymbol:7, hasSecondsFrame:false, colortype:1};
                    else if (command===204) reply={command:"transition", transitionType:0,
                        transitionDuration:2, transitionSpeed:30, transitionColorize:0, transitionDemo:false};
                    else if (command===203) reply={command:"autoBright", autoBrightEnabled:0,
                        autoBrightSource:"Disabled fixture", autoBrightSensor:0, autoBrightGain:100};
                    else if (command===206) reply={command:"birthdays", hasSpecialWordHappyBirthday:false};
                    else if (command===205) reply={command:"mqtt", MQTT_State:0, MQTT_Port:1883,
                        MQTT_Server:"", MQTT_User:"", MQTT_Pass:"", MQTT_ClientId:"fixture", MQTT_Topic:"fixture"};
                    else throw new Error("Unexpected numeric read: "+command);
                    socket.send(JSON.stringify(reply)); return;
                }
                const request=JSON.parse(text); peer.requests.push(request);
                assert.equal(request.command,"brightness-schedule");
                assert.equal(request.schema,1); assert.equal(request.action,"get");
                socket.send(JSON.stringify({command:request.command, schema:1,
                    requestId:request.requestId, action:"get", status:"loaded", capabilities, ...schedule}));
            } catch (error) { peer.errors.push(error.message); }
        });
    };
    return peer;
}
async function settle(page) {
    await page.evaluate(() => { window.scrollTo(0,0); return new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
}
async function measure(page, label) {
    return page.evaluate(label => {
        function box(selector) {
            const element=typeof selector==="string"?document.querySelector(selector):selector; if (!element) return null;
            const rect=element.getBoundingClientRect();
            return {left:rect.left, right:rect.right, width:rect.width, height:rect.height,
                client:element.clientWidth, scroll:element.scrollWidth};
        }
        return {label, viewport:innerWidth, documentClient:document.documentElement.clientWidth,
            documentScroll:document.documentElement.scrollWidth,
            main:box(".main"), section:box(".section-main"),
            activeSection:box(Array.from(document.querySelectorAll(".section")).find(element=>getComputedStyle(element).display!=="none")), color:box(".box-color"),
            picker:box("#color-picker"), editor:box("#schedule-editor"), chart:box(".schedule-chart")};
    }, label);
}
async function main() {
    const {chromium}=require("playwright");
    fs.mkdirSync(output,{recursive:true});
    const report={scope:"generated page, real Chromium, simulated peer; measurements are not a layout-fix pass", measurements:[]};
    const html=fs.readFileSync(path.join(__dirname,"../.pio/build/webpage/index.html"));
    const server=http.createServer((request,response) => {
        response.writeHead(request.url==="/"?200:204,{"Content-Type":"text/html; charset=utf-8"});
        response.end(request.url==="/"?html:undefined);
    });
    await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
    const origin="http://127.0.0.1:"+server.address().port;
    let browser, context;
    try {
        browser=await chromium.launch({headless:true});
        context=await browser.newContext({locale:"en-US",viewport:{width:1440,height:1000},reducedMotion:"reduce"});
        const page=await context.newPage(); page.setDefaultTimeout(10000);
        const errors=[], blocked=[], peer=peerFor(new URL(origin).host);
        report.errors=errors; report.blocked=blocked; report.peer=peer;
        page.on("pageerror",error=>errors.push(error.message));
        await context.route("**/*",route => {
            const url=new URL(route.request().url());
            if (url.origin===origin && (url.pathname==="/" || url.pathname==="/favicon.ico")) return route.continue();
            blocked.push(url.href); return route.abort();
        });
        // Fully mocked before navigation: never connectToServer or a device URL.
        await page.routeWebSocket(/.*/,peer.route);
        await page.goto(origin+"/",{waitUntil:"load"});
        await page.waitForFunction(()=>document.querySelector("[data-schedule='status']").textContent.includes("loaded"));
        await page.waitForFunction(()=>document.querySelector("#auto-bright-enabled").value==="0");
        for (const width of [320,480,768,1024,1440]) {
            await page.setViewportSize({width,height:1000}); await settle(page);
            for (const mode of ["visible","chart-hidden","editor-hidden"]) {
                await page.evaluate(mode => {
                    document.querySelector(".schedule-chart").style.display=mode==="chart-hidden"?"none":"block";
                    document.querySelector("#schedule-editor").style.display=mode==="editor-hidden"?"none":"";
                },mode);
                await settle(page);
                report.measurements.push(await measure(page,width+"/"+mode));
                if (mode==="visible") await page.screenshot({path:path.join(output,"colors-"+width+".png"),fullPage:true,animations:"disabled"});
            }
            await page.evaluate(()=>{document.querySelector("#schedule-editor").style.display="";});
            for (const navigation of ["functions","frontoptions","settings","smart-home","about","main"]) {
                await page.locator(".pure-menu-link[data-navigation='"+navigation+"']").evaluate(element=>element.click());
                await settle(page);
                report.measurements.push(await measure(page,width+"/navigation-"+navigation));
            }
            // Always compare the same restored chart state after navigation.
            assert.equal(await page.locator(".schedule-chart").evaluate(element=>getComputedStyle(element).display),"block");
        }
        assert.equal(peer.connections,1); assert.ok(peer.requests.length>0);
        assert.deepEqual(peer.numeric.filter(command=>command<200),[]);
        assert.deepEqual(peer.errors,[]); assert.deepEqual(errors,[]); assert.deepEqual(blocked,[]);
        report.status="PASS_DIAGNOSTICS_ONLY";
    } catch (error) {
        report.status="FAIL"; report.error=error.stack||String(error); throw error;
    } finally {
        fs.writeFileSync(path.join(output,"layout-report.json"),JSON.stringify(report,null,2));
        if (context) await context.close(); if (browser) await browser.close();
        await new Promise(resolve=>server.close(resolve));
    }
    console.log(JSON.stringify({status:report.status,measurements:report.measurements.length,report:"layout-evidence/layout-report.json"}));
}
module.exports={configuration,peerFor};
if (require.main===module) main().catch(error=>{console.error(error);process.exitCode=1;});
