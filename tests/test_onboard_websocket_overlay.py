#!/usr/bin/env python3
"""Pinned websocket excerpts; protocol decoder and ping generator remain mocked."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("ws_overlay",ROOT/"tools/onboard_websocket_overlay.py")
overlay=importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)
FIXTURE=(ROOT/"tests/fixtures/WebSockets-2.4.1-guard-methods.cpp.txt").read_text()
METHODS={key:FIXTURE.split("// BEGIN "+key+"\n",1)[1].split("// END "+key+"\n",1)[0]
         for key in overlay.METHODS}
CPP=r"""#include <cassert>
#include <cstdint>
#include <string>
#include <algorithm>
using String=std::string;
#define ESP32 1
#define NETWORK_ESP32 1
#define NETWORK_ESP8266 2
#define NETWORK_ESP8266_ASYNC 3
#define NETWORK_RP2040 4
#define WEBSOCKETS_NETWORK_TYPE NETWORK_ESP32
#define WEBSOCKETS_SERVER_CLIENT_MAX 2
#define WEBSOCKETS_TCP_TIMEOUT 5
#define DEBUG_WEBSOCKETS(...) do {} while(0)
static uint32_t tick=0;
static bool black=false, pingDue=false;
static int sinkWrites=0, writes=0, stops=0, deletes=0, callbacks=0, frames=0, headers=0, yields=0;
uint32_t millis(){return tick;}
#define WEBSOCKETS_YIELD() (++yields)
extern "C" void wordclockDiagnosticBeforeNetworkWork(){if(!black){black=true;++sinkWrites;}}
struct Tcp {
 bool live=true, tracked=false; int bytes=0; size_t chunk=1;
 bool connected(){return live;}
 int available(){return bytes;}
 String readStringUntil(char){assert(black);return "header";}
 size_t write(const uint8_t*,size_t n){assert(black);++writes;++tick;return std::min(n,chunk);}
 void stop(){assert(black);++stops;live=false;}
 void flush(){assert(black);}
 ~Tcp(){if(tracked){assert(black);++deletes;}}
};
enum {WSC_NOT_CONNECTED,WSC_HEADER,WSC_CONNECTED,WSop_close=8,WStype_DISCONNECTED=9};
struct WSclient_t {
 Tcp *tcp=nullptr,*ssl=nullptr; bool isSSL=false;
 int status=WSC_NOT_CONNECTED,num=0,cVersion=0,cWsRXsize=0;
 bool cIsUpgrade=false,cIsWebsocket=false,pongReceived=false;
 String cUrl,cKey,cProtocol;
 uint32_t pingInterval=0,pongTimeout=0,lastPing=0;
 uint8_t disconnectTimeoutCount=0,pongTimeoutCount=0;
};
class WebSockets {
public:
 virtual ~WebSockets(){}
 virtual void clientDisconnect(WSclient_t*)=0;
 void clientDisconnect(WSclient_t*,uint16_t,char* = nullptr,size_t = 0);
 size_t write(WSclient_t*,uint8_t*,size_t);
 void handleHBTimeout(WSclient_t*);
 void sendFrame(WSclient_t *c,int,uint8_t *p,size_t n){assert(black);write(c,p,n);}
 void handleWebsocket(WSclient_t *c){
  assert(black);++frames;uint8_t pong=0;write(c,&pong,1);
  int previous=sinkWrites;wordclockDiagnosticBeforeNetworkWork();assert(previous==sinkWrites);++callbacks;
 }
};
class WebSocketsServerCore:public WebSockets {
public:
 WSclient_t _clients[WEBSOCKETS_SERVER_CLIENT_MAX];
 void dropNativeClient(WSclient_t*);
 void clientDisconnect(WSclient_t*) override;
 bool clientIsConnected(WSclient_t*);
 void handleClientData();
 void handleHeader(WSclient_t*,String*){assert(black);++headers;++callbacks;}
 void runCbEvent(int,int,void*,size_t){assert(black);++callbacks;}
 void handleHBPing(WSclient_t *c){
  if(pingDue){uint8_t p=0;WebSockets::write(c,&p,1);pingDue=false;}
 }
};
void reset(){tick=0;black=pingDue=false;sinkWrites=writes=stops=deletes=callbacks=frames=headers=yields=0;}
void attach(WebSocketsServerCore &s,int status=WSC_CONNECTED){
 auto &c=s._clients[0];c.tcp=new Tcp;c.tcp->tracked=true;c.status=status;
}
"""
MAIN=r"""int main(){
 reset();WebSocketsServerCore empty;empty.handleClientData();assert(sinkWrites==0&&yields==2);
 reset();WebSocketsServerCore idle;attach(idle);idle.handleClientData();assert(sinkWrites==0&&callbacks==0);
 idle.clientDisconnect(&idle._clients[0]);assert(sinkWrites==1&&deletes==1);
 reset();WebSocketsServerCore header;attach(header,WSC_HEADER);header._clients[0].tcp->bytes=1;
 header.handleClientData();assert(sinkWrites==1&&headers==1);header.clientDisconnect(&header._clients[0]);
 reset();WebSocketsServerCore data;attach(data);data._clients[0].tcp->bytes=1;
 data.handleClientData();assert(sinkWrites==1&&frames==1&&writes==1&&callbacks==1);data.clientDisconnect(&data._clients[0]);
 reset();WebSocketsServerCore invalid;attach(invalid,99);invalid._clients[0].tcp->bytes=1;
 invalid.handleClientData();assert(sinkWrites==1&&deletes==1&&callbacks==1);
 reset();WebSocketsServerCore lost;attach(lost);lost._clients[0].tcp->live=false;
 lost.handleClientData();assert(sinkWrites==1&&deletes==1&&stops==0&&callbacks==1);
 reset();WebSocketsServerCore ping;attach(ping);pingDue=true;ping.handleClientData();
 assert(sinkWrites==1&&writes==1&&frames==0);ping.clientDisconnect(&ping._clients[0]);
 reset();WebSocketsServerCore timeout;attach(timeout);auto &t=timeout._clients[0];
 t.pingInterval=100;t.pongTimeout=10;t.disconnectTimeoutCount=1;tick=10;
 timeout.handleClientData();assert(sinkWrites==0&&t.pongTimeoutCount==0);
 tick=11;timeout.handleClientData();assert(sinkWrites==1&&deletes==1&&callbacks==1);
 reset();WebSocketsServerCore count;attach(count);auto &c=count._clients[0];c.pingInterval=100;c.pongTimeout=10;
 tick=11;count.handleClientData();assert(sinkWrites==0&&c.pongTimeoutCount==1);
 c.pongReceived=true;count.handleClientData();assert(sinkWrites==0&&c.pongTimeoutCount==0);count.clientDisconnect(&c);
 reset();WebSocketsServerCore close;attach(close);close.WebSockets::clientDisconnect(&close._clients[0],1000);
 assert(sinkWrites==1&&writes==2&&deletes==1&&callbacks==1);
 reset();WebSocketsServerCore tls;attach(tls);tls._clients[0].isSSL=true;tls._clients[0].ssl=tls._clients[0].tcp;
 tls.clientDisconnect(&tls._clients[0]);assert(sinkWrites==1&&stops==1&&deletes==1);
 reset();WebSocketsServerCore raw;attach(raw);uint8_t b[10]={0};
 assert(raw.write(nullptr,b,3)==0&&raw.write(&raw._clients[0],nullptr,3)==0);
 assert(raw.write(&raw._clients[0],b,0)==0&&sinkWrites==0);
 assert(raw.write(&raw._clients[0],b,10)==10&&writes==10&&sinkWrites==1);
 black=false;assert(raw.write(&raw._clients[0],b,1)==1&&sinkWrites==2);raw.clientDisconnect(&raw._clients[0]);
 reset();WebSocketsServerCore stalled;attach(stalled);stalled._clients[0].tcp->chunk=0;
 assert(stalled.write(&stalled._clients[0],b,1)==0&&writes==6&&sinkWrites==1);
 stalled.clientDisconnect(&stalled._clients[0]);
 reset();WebSocketsServerCore orphan;attach(orphan,WSC_NOT_CONNECTED);orphan.handleClientData();assert(sinkWrites==1&&deletes==1);
 reset();WebSocketsServerCore wrap;attach(wrap);auto &w=wrap._clients[0];w.pingInterval=100;w.pongTimeout=20;
 w.lastPing=UINT32_MAX-5;tick=5;wrap.handleClientData();assert(sinkWrites==0);wrap.clientDisconnect(&w);
}
"""
class WebsocketTests(unittest.TestCase):
 def test_pinned_excerpts(self):
  for key,text in METHODS.items():
   self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),overlay.METHODS[key]["sha256"])
   guarded=overlay.guard_method(key,text)
   for before,after in overlay.METHODS[key]["patches"]:self.assertIn(after,guarded)
   with self.assertRaisesRegex(ValueError,"Unverified"):overlay.guard_method(key,text+"// changed\n")

 def test_normal_passthrough(self):
  with tempfile.TemporaryDirectory() as folder:
   for profile in ("ESP8266","ESP32","ESP32C3","YD_ESP32S3_N16R8"):
    source=Path(folder)/"missing.cpp";build=Path(folder)/"build"
    self.assertEqual(overlay.prepare(source,build,profile),source)
    self.assertFalse(build.exists())

 def test_file_gate_and_crlf_output(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   for name,(blob,keys) in overlay.SOURCES.items():
    installed=root/Path(name).stem;installed.mkdir()
    header=installed/"WebSockets.h";header.write_text("// host header\n")
    source=installed/name
    body=('#include "WebSockets.h"\n'+''.join(METHODS[k]+"\n" for k in keys)).replace("\n","\r\n").encode()
    source.write_bytes(body);build=root/("build-"+source.stem)
    with self.assertRaisesRegex(ValueError,"Unverified"):overlay.prepare(source,build,next(iter(overlay.PROFILES)))
    self.assertFalse(build.exists())
    # Partial wrapper only: override whole-file hash; keep all real method hashes.
    with patch.dict(overlay.SOURCES,{name:(overlay.git_blob(body),keys)}):
     for profile in sorted(overlay.PROFILES):
      output=overlay.prepare(source,build,profile);first=output.read_bytes()
      self.assertEqual(overlay.prepare(source,build,profile).read_bytes(),first)
      self.assertEqual(source.read_bytes(),body)
      self.assertEqual(first.replace(b"\r\n",b"\n").replace(b"\n",b"\r\n"),first)
      manifest=json.loads((output.parent/"manifest.json").read_text())
      self.assertEqual(manifest["profile"],profile)
      self.assertEqual(manifest["output_sha256"],hashlib.sha256(first).hexdigest())
     with self.assertRaisesRegex(ValueError,"installed"):
      overlay.prepare(source,installed,next(iter(overlay.PROFILES)))

 def test_source_derived_paths(self):
  compiler=shutil.which("g++")
  if not compiler:self.fail("g++ is required")
  with tempfile.TemporaryDirectory() as folder:
   work=Path(folder)
   code=CPP+''.join(overlay.guard_method(key,text) for key,text in METHODS.items())+MAIN
   (work/"test.cpp").write_text(code)
   subprocess.run([compiler,"-std=c++11","-Wall","-Wextra","-Werror",
    "-fsanitize=undefined,bounds","-fno-sanitize-recover=all",str(work/"test.cpp"),"-o",str(work/"test")],check=True)
   subprocess.run([str(work/"test")],check=True)
if __name__=="__main__":unittest.main()
