/** Real bridge; fake existing sockets/page. No live networking, DOM or firmware. */
"use strict";
const assert=require("node:assert/strict");
const create=require("../webpage/schedule-socket-bridge.js");
let checks=0;
function equal(actual,expected){assert.deepEqual(actual,expected);checks+=1;}
class Socket{
 constructor(state=0){this.readyState=state;this.listeners={};this.sent=[];this.attempts=0;this.onSend=null;this.failure=null;this.closedByBridge=0;}
 addEventListener(type,fn){(this.listeners[type]||(this.listeners[type]=new Set())).add(fn);}
 removeEventListener(type,fn){this.listeners[type].delete(fn);}
 emit(type,data){for(const fn of [...(this.listeners[type]||[])])fn({data});}
 send(value){this.attempts+=1;if(this.failure)throw this.failure;this.sent.push(value);if(this.onSend)this.onSend(value);}
 close(){this.closedByBridge+=1;}
 count(){return Object.values(this.listeners).reduce((sum,set)=>sum+set.size,0);}
}
function fixture(){
 const calls=[];let send,generation=0;
 const bridge=create(value=>{send=value;return {open(){generation+=1;calls.push(["open",generation]);send(JSON.stringify({command:"brightness-schedule",schema:1,requestId:"g"+generation,action:"get"}),generation);return generation;},close(token){calls.push(["close",token]);},receive(token,reply){calls.push(["receive",token,reply]);},snapshot(){return {generation};},refresh(){calls.push(["refresh"]);},destroy(){calls.push(["destroy"]);}};});
 return {bridge,calls,send(value,token){return send(value,token);}};
}
const response={command:"brightness-schedule",schema:1,requestId:"g1",action:"get",status:"missing"};
{
 const test=fixture(),socket=new Socket();equal(test.calls,[]);equal(test.send("{}",1),false);
 const original=()=>{};socket.onmessage=original;
 equal(test.bridge.attach(socket),true);equal(socket.count(),3);equal(test.calls,[]);
 socket.readyState=1;socket.emit("open");equal(test.calls,[["open",1]]);equal(socket.sent.length,1);
 equal(JSON.parse(socket.sent[0]).action,"get");equal(socket.onmessage,original);
 equal(test.bridge.attach(socket),false);socket.emit("open");equal(socket.sent.length,1);
 socket.emit("message",JSON.stringify(response));equal(test.calls[test.calls.length-1],["receive",1,response]);
 const count=test.calls.length;
 for(const value of ["{","null","[]",JSON.stringify({command:"autoBright"}),{}])socket.emit("message",value);
 equal(test.calls.length,count);equal(test.send("{}",2),false);equal(test.send({},1),false);equal(test.send("{}",0),false);equal(test.send("{}",1.5),false);equal(test.send("{}","1"),false);equal(socket.sent.length,1);
 test.bridge.refresh();equal(test.calls[test.calls.length-1],["refresh"]);equal(test.bridge.snapshot(),{generation:1});
 socket.readyState=3;socket.emit("close");equal(test.calls[test.calls.length-1],["close",1]);
 equal(test.send("{}",1),false);const after=test.calls.length;socket.emit("close");equal(test.calls.length,after);
 test.bridge.destroy();equal(socket.count(),0);equal(socket.closedByBridge,0);
}
{
 const test=fixture(),old=new Socket(1),next=new Socket();test.bridge.attach(old);
 const staleOpen=[...old.listeners.open][0],staleClose=[...old.listeners.close][0],staleMessage=[...old.listeners.message][0];
 test.bridge.attach(next);equal(old.count(),0);equal(test.calls,[["open",1],["close",1]]);
 staleOpen({});staleClose({});staleMessage({data:JSON.stringify(response)});equal(test.calls.length,2);
 equal(test.send("{}",1),false);next.readyState=1;next.emit("open");equal(test.calls[test.calls.length-1],["open",2]);
 equal(test.send("{}",1),false);equal(test.send("{}",2),true);equal(next.sent.length,2);equal(old.sent.length,1);
 staleClose({});equal(test.calls[test.calls.length-1],["open",2]);
 equal(test.bridge.detach(),true);equal(next.count(),0);equal(test.calls[test.calls.length-1],["close",2]);equal(test.bridge.detach(),false);
 equal(next.closedByBridge,0);test.bridge.destroy();
}
{
 const test=fixture(),socket=new Socket(1);
 socket.onSend=()=>socket.emit("message",JSON.stringify(response));test.bridge.attach(socket);
 equal(test.calls,[["open",1],["receive",1,response]]);equal(socket.sent.length,1);test.bridge.destroy();
}
{
 const test=fixture(),socket=new Socket(1);
 socket.onSend=()=>{socket.readyState=3;socket.emit("close");};test.bridge.attach(socket);
 equal(test.calls,[["open",1],["close",1]]);equal(test.send("{}",1),false);test.bridge.destroy();
 equal(test.calls,[["open",1],["close",1],["destroy"]]);
}
{
 const test=fixture(),socket=new Socket(1);test.bridge.attach(socket);socket.failure=new Error("send failed");
 assert.throws(()=>test.send("save",1),/send failed/);checks+=1;
 equal(socket.attempts,2);equal(socket.sent.length,1);test.bridge.destroy();
}
{
 const test=fixture(),socket=new Socket(1);test.bridge.attach(socket);
 assert.throws(()=>test.bridge.attach(new Socket(3)),/Connecting or open/);checks+=1;
 equal(socket.count(),3);equal(test.send("{}",1),true);
 socket.readyState=2;socket.emit("message",JSON.stringify(response));equal(test.calls,[["open",1]]);equal(test.send("{}",1),false);
 test.bridge.destroy();test.bridge.destroy();equal(socket.count(),0);equal(test.calls,[["open",1],["close",1],["destroy"]]);
 const after=test.calls.length;test.bridge.refresh();equal(test.calls.length,after);equal(test.send("{}",1),false);
 assert.throws(()=>test.bridge.attach(new Socket()),/destroyed/);checks+=1;
}
{
 const test=fixture(),socket=new Socket();test.bridge.attach(socket);test.bridge.destroy();
 equal(test.calls,[["destroy"]]);equal(socket.count(),0);equal(socket.closedByBridge,0);
}
{
 const test=fixture(),socket=new Socket(1);let legacy=0;
 const owner=()=>{legacy+=1;};socket.addEventListener("message",owner);test.bridge.attach(socket);
 socket.emit("message",JSON.stringify({command:"autoBright"}));equal(legacy,1);equal(test.calls,[["open",1]]);
 test.bridge.destroy();equal(socket.count(),1);socket.emit("message","legacy");equal(legacy,2);equal(socket.closedByBridge,0);
}
{
 const test=fixture(),old=new Socket(1),next=new Socket(1);
 old.onSend=()=>test.bridge.attach(next);test.bridge.attach(old);
 equal(test.calls,[["open",1],["close",1],["open",2]]);equal(old.count(),0);
 next.emit("message",JSON.stringify(response));equal(test.calls[test.calls.length-1],["receive",2,response]);
 equal(test.send("{}",1),false);equal(test.send("{}",2),true);test.bridge.destroy();
}
assert.throws(()=>create(null),/factory/);checks+=1;
assert.throws(()=>create(()=>({})),/Complete page/);checks+=1;
console.log(JSON.stringify({status:"PASS",assertions:checks,scope:"bridge with fake sockets/page; no live network"}));
