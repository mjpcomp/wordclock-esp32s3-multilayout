#!/usr/bin/env python3
"""Execute actual migrated UI functions in Node VM; not a full browser test."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
JS=r'''const fs=require("fs"),vm=require("vm"),assert=require("assert"),crypto=require("crypto");
const root=process.argv[1],path=require("path");
const script=fs.readFileSync(path.join(root,"webpage/script.js"),"utf8");
const ui=fs.readFileSync(path.join(root,"webpage/i18n.js"),"utf8");
const english=fs.readFileSync(path.join(root,"webpage/language/en.js"),"utf8");
const german=fs.readFileSync(path.join(root,"webpage/language/de.js"),"utf8");
for(const text of [script,ui,english])new vm.Script(text);
assert(!script.includes('"Verbinden"')&&!script.includes('"Verbinden ..."'));
assert(!script.includes('WLAN Netzwerke werden gesucht'));
assert(script.includes('btn.addEventListener("click", handleConnectionButton)'));
assert(script.includes('" change requested."'));
assert(script.includes('initValsBtn.addEventListener("click", () => sendColorData(CMD.SET_INITIAL_VALUES))'));
assert(script.includes('resetBtn.addEventListener("click", () => sendCmd(CMD.RESET))'));
const command=script.match(/const CMD = \{[\s\S]*?\n\};/)[0];
assert.strictEqual(crypto.createHash("sha256").update(command).digest("hex"),"05ee8afe361d96bbc92b6ace7ed1bce7c6dc0453bf1317a53f3d68a24e5ce8f3");
const classes=new Set();const status={value:"",classList:{toggle(k,v){v?classes.add(k):classes.delete(k);}}};
const buttons=[{value:"0",textContent:"",closest(){return {}; }},{value:"0",textContent:"",closest(){return null;}}];
const menu={getAttribute(){return "false";},setAttribute(){}};
let options,lang="en",sent=[],created=0;const events={};
const c={console,window:{i18nextBrowserLanguageDetector:{}},isLocalEnvironment:()=>false,
 TRANSLATION_NL:{},TRANSLATION_ES:{},TRANSLATION_IT:{},TRANSLATION_HU:{},TRANSLATION_RU:{},
 document:{getElementById(id){return id==="status"?status:{style:{}};},
 querySelectorAll(q){return q===".status-button"?buttons:[];},getElementsByClassName(){return [menu];}},
 ipEsp:"ws://example.invalid",CMD:{REQ_COLOR_VALUES:201,REQ_TRANSITION:204,REQ_CONFIG_VALUES:200},
 sendCmd(n){sent.push(n);},debugMessage(){},autoBrightStop(){},
 WebSocket:class {constructor(){this.readyState=0;created++;}close(){this.readyState=2;}}};
c.i18next={isInitialized:true,use(){},init(o){options=o;},on(n,fn){events[n]=fn;},
 t(key,o={}){let v=options.resources[lang].translation;for(const k of key.split('.'))v=v&&v[k];return typeof v==="string"?v:(o.defaultValue||key);}};
vm.createContext(c);vm.runInContext(english,c);vm.runInContext(german,c);vm.runInContext(ui,c);
assert.strictEqual(options.resources.en.translation.functions.mode.scrollingtext,"Scrolling text");
assert.strictEqual(options.resources.en.translation.settings.restart.restart,"Save current settings");
assert.strictEqual(options.resources.en.translation.view.language['it-is-quarterly'],"Every 15 minutes");
assert.strictEqual(options.resources.en.translation.view.front['en-10-11-mirc0'],"English 10 x 11 (Mirc0.)");
assert.deepStrictEqual(Array.from(options.detection.order),["querystring","cookie"]);
const helpers=script.slice(script.indexOf('function connectionText('),script.indexOf('function initWebsocket()'));
const init=script.slice(script.indexOf('function initWebsocket()'),script.indexOf('\nfunction changeColor('));
vm.runInContext('let websocket;\n'+helpers+init,c);
vm.runInContext('initWebsocket()',c);assert.strictEqual(created,1);assert.strictEqual(status.value,"Connecting…");
vm.runInContext('websocket.readyState=1;websocket.onopen({})',c);
assert.strictEqual(status.value,"Connected");assert.strictEqual(buttons[0].textContent,"Disconnect");
assert.strictEqual(buttons[0].value,"1");assert.deepStrictEqual(sent,[201,204,200]);
vm.runInContext('handleConnectionButton.call(document.querySelectorAll(".status-button")[0])',c);
assert.strictEqual(status.value,"Disconnecting…");
vm.runInContext('websocket.readyState=3;websocket.onclose({code:1000})',c);
assert.strictEqual(status.value,"Disconnected");assert.strictEqual(buttons[0].textContent,"Reconnect");assert.strictEqual(buttons[1].textContent,"Connect");
lang="de";events.languageChanged();assert.strictEqual(buttons[0].textContent,options.resources.de.translation['connection-lost'].button);
lang="en";events.languageChanged();assert.strictEqual(buttons[0].textContent,"Reconnect");
assert.strictEqual(buttons[0].value,"0");
vm.runInContext('handleConnectionButton.call(document.querySelectorAll(".status-button")[0])',c);assert.strictEqual(created,2);
assert.strictEqual(status.value,"Connecting…");assert.deepStrictEqual(sent,[201,204,200]);
c.i18next.isInitialized=false;vm.runInContext('websocket.readyState=3;refreshConnectionText()',c);
assert.strictEqual(status.value,"Disconnected");assert.strictEqual(buttons[0].textContent,"Reconnect");
console.log('PASS: real helper/handler VM tests, English/German refresh, fallback, connection states, unchanged requests and save command semantics.');
'''
def main():
 node=shutil.which('node')
 if not node:raise SystemExit('Node is required for UI regression tests')
 for name in ('script.js','i18n.js','language/en.js'):
  subprocess.run([node,'--check',str(ROOT/'webpage'/name)],check=True)
 subprocess.run([node,'-e',JS,str(ROOT)],check=True)
if __name__=='__main__':main()
