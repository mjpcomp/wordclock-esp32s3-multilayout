#!/usr/bin/env python3
"""Test pinned HTTP/client method excerpts; platform I/O and callbacks mocked."""
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
spec=importlib.util.spec_from_file_location("http_overlay",ROOT/"tools/onboard_http_overlay.py")
overlay=importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)
FIXTURES={
 "WebServer.cpp":"WebServer-2.0.17-handleClient.cpp.txt",
 "WiFiClient.cpp":"WiFiClient-2.0.17-available.cpp.txt",
}
METHODS={name:(ROOT/"tests/fixtures"/path).read_text().split("// BEGIN PINNED METHOD\n",1)[1]
         for name,path in FIXTURES.items()}
CPP=r"""#include <cassert>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <memory>
#include <string>
static uint32_t nowMs=0;
static int sinks=0, delays=0, yields=0, parses=0, handlers=0, stops=0, resets=0;
static bool black=false, parseOk=true;
static std::string events;
extern "C" void wordclockDiagnosticBeforeNetworkWork() {
 events += "B"; if(!black) { black=true; ++sinks; }
}
uint32_t millis() { return nowMs; }
void delay(int n) { delays+=n; }
void yield() { ++yields; }
#define log_v(...) do {} while(0)
#define log_e(...) do {} while(0)
struct Rx {
 int count; bool fault;
 int available() { return count; }
 bool failed() { return fault; }
};
class WiFiClient {
 int socket=-1;
 bool live=false;
public:
 std::shared_ptr<Rx> _rxBuffer;
 WiFiClient() {}
 WiFiClient(int fd, bool connected, int count=0, bool failed=false):socket(fd),live(connected),_rxBuffer(new Rx{count,failed}) {}
 WiFiClient(const WiFiClient&)=default;
 WiFiClient& operator=(const WiFiClient &other) {
  if(socket>=0) { assert(black); events+="R"; }
  socket=other.socket;live=other.live;_rxBuffer=other._rxBuffer;return *this;
 }
 int fd() const { return socket; }
 bool connected() const { return live; }
 explicit operator bool() const { return live; }
 int available();
 void stop() { assert(black);++stops;socket=-1;live=false;_rxBuffer.reset(); }
 void setTimeout(uint32_t) { assert(black);events+="T"; }
};
struct FakeServer {
 WiFiClient incoming;
 WiFiClient available() {
  if(incoming.fd()>=0) wordclockDiagnosticBeforeNetworkWork();
  return incoming;
 }
};
struct Resettable { void reset() { assert(black);++resets; } };
enum Status { HC_NONE, HC_WAIT_READ, HC_WAIT_CLOSE };
constexpr uint32_t HTTP_MAX_DATA_WAIT=5000, HTTP_MAX_CLOSE_WAIT=2000, HTTP_MAX_SEND_WAIT=5000;
constexpr size_t CONTENT_LENGTH_NOT_SET=size_t(-1);
struct WebServer {
 Status _currentStatus=HC_NONE;
 WiFiClient _currentClient;
 FakeServer _server;
 bool _nullDelay=true;
 uint32_t _statusChange=0;
 size_t _contentLength=0;
 Resettable _currentUpload, _currentRaw;
 bool _parseRequest(WiFiClient&) {
  assert(black);++parses;events+="P";
  int previous=sinks;wordclockDiagnosticBeforeNetworkWork();assert(previous==sinks);
  return parseOk;
 }
 void _handleRequest() {
  assert(black);++handlers;events+="H";
  int previous=sinks;wordclockDiagnosticBeforeNetworkWork();assert(previous==sinks);
 }
 void handleClient();
};
void reset() {
 nowMs=0;sinks=delays=yields=parses=handlers=stops=resets=0;
 black=false;parseOk=true;events.clear();
}
void seed(WebServer &s, Status status, bool connected, int bytes=0, bool failed=false) {
 black=true;s._currentClient=WiFiClient(7,connected,bytes,failed);
 s._currentStatus=status;black=false;events.clear();sinks=0;
}
"""
MAIN=r"""int main() {
 reset(); WebServer idle; idle.handleClient();
 assert(sinks==0 && delays==1 && yields==0 && resets==0);
 reset(); WebServer noDelay;noDelay._nullDelay=false;noDelay.handleClient();assert(delays==0&&sinks==0);
 reset(); WebServer wait;seed(wait,HC_WAIT_READ,true);nowMs=HTTP_MAX_DATA_WAIT;
 wait.handleClient();assert(sinks==0&&yields==1&&wait._currentStatus==HC_WAIT_READ);
 nowMs++;wait.handleClient();assert(sinks==1&&resets==2&&wait._currentStatus==HC_NONE);
 reset(); WebServer close;seed(close,HC_WAIT_CLOSE,true);nowMs=HTTP_MAX_CLOSE_WAIT;
 close.handleClient();assert(sinks==0&&yields==1);
 nowMs++;close.handleClient();assert(sinks==1&&resets==2);
 reset(); WebServer gone;seed(gone,HC_WAIT_READ,false);gone.handleClient();
 assert(sinks==1&&resets==2&&parses==0&&gone._currentStatus==HC_NONE);
 reset(); WebServer request;seed(request,HC_WAIT_READ,true,5);request.handleClient();
 assert(parses==1&&handlers==1&&sinks==1&&resets==2);
 assert(events.find('B')<events.find('P')&&events.find('P')<events.find('H'));
 reset(); parseOk=false;WebServer bad;seed(bad,HC_WAIT_READ,true,5);bad.handleClient();
 assert(parses==1&&handlers==0&&sinks==1&&resets==2);
 reset(); WebServer probe;seed(probe,HC_WAIT_READ,true,0,true);probe.handleClient();
 assert(sinks==1&&stops==1&&parses==0&&yields==1);
 black=false;probe.handleClient();assert(sinks==2&&resets==2);
 reset(); WebServer stale;seed(stale,HC_NONE,false);stale.handleClient();assert(sinks==1&&delays==1);
 reset(); WebServer fresh;
 black=true;fresh._server.incoming=WiFiClient(9,true,5);black=false;
 fresh.handleClient();assert(sinks==1&&parses==1&&handlers==1);
 reset(); WebServer wrap;seed(wrap,HC_WAIT_READ,true);
 wrap._statusChange=UINT32_MAX-10;nowMs=5;wrap.handleClient();assert(sinks==0&&yields==1);
 reset(); WiFiClient empty;assert(empty.available()==0&&sinks==0);
 reset(); WiFiClient normal(3,true,4);assert(normal.available()==4&&sinks==0);
 reset(); WiFiClient failed(3,true,0,true);assert(failed.available()==0&&sinks==1&&stops==1);
}
"""

class HttpTests(unittest.TestCase):
 def test_method_identity_and_rejection(self):
  for name,method in METHODS.items():
   self.assertEqual(hashlib.sha256(method.encode()).hexdigest(),overlay.SOURCES[name]["method_sha256"])
   guarded=overlay.guard_method(name,method)
   for before,after in overlay.SOURCES[name]["patches"]:
    self.assertIn(after,guarded)
   with self.assertRaisesRegex(ValueError,"Unverified"):
    overlay.guard_method(name,method+"// changed\n")

 def test_normal_profiles_do_not_read_sources(self):
  for profile in ("ESP8266","ESP32","ESP32C3","YD_ESP32S3_N16R8"):
   self.assertEqual(overlay.prepare("missing.cpp","missing-build",profile),Path("missing.cpp"))

 def test_file_gate_and_output_contract(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   for name,method in METHODS.items():
    installed=root/name.removesuffix(".cpp")
    installed.mkdir()
    source=installed/name
    header=installed/(name.removesuffix(".cpp")+".h")
    header.write_text("// host header\n")
    body='#include "'+header.name+'"\n'+method+overlay.SOURCES[name]["end"]+"\n}\n"
    source.write_text(body)
    build=root/("build-"+source.stem)
    with self.assertRaisesRegex(ValueError,"Unverified"):
     overlay.prepare(source,build,"YD_ESP32S3_N16R8_BOARD_ONLY")
    self.assertFalse(build.exists())
    # File I/O uses a partial fixture wrapper: only this test overrides the whole-file blob.
    # The real method fingerprint stays enforced by production guard_method().
    fixture_spec=dict(overlay.SOURCES[name],blob=overlay.git_blob(source.read_bytes()))
    with patch.dict(overlay.SOURCES,{name:fixture_spec}):
     for profile in sorted(overlay.PROFILES):
      output=overlay.prepare(source,build,profile)
      first=output.read_bytes()
      self.assertEqual(overlay.prepare(source,build,profile).read_bytes(),first)
      self.assertEqual(source.read_text(),body)
      self.assertIn('#include "'+header.resolve().as_posix()+'"',first.decode())
      manifest=json.loads((output.parent/"manifest.json").read_text())
      self.assertEqual(manifest["profile"],profile)
      self.assertEqual(manifest["method_sha256"],fixture_spec["method_sha256"])
      self.assertEqual(manifest["output_sha256"],hashlib.sha256(first).hexdigest())

 def test_source_derived_control_flow(self):
  compiler=shutil.which("g++")
  if not compiler:self.fail("g++ is required")
  with tempfile.TemporaryDirectory() as folder:
   work=Path(folder)
   code=CPP+overlay.guard_method("WiFiClient.cpp",METHODS["WiFiClient.cpp"])
   code+=overlay.guard_method("WebServer.cpp",METHODS["WebServer.cpp"])+MAIN
   (work/"test.cpp").write_text(code)
   subprocess.run([compiler,"-std=c++11","-Wall","-Wextra","-Werror",
    "-fsanitize=undefined,bounds","-fno-sanitize-recover=all",
    str(work/"test.cpp"),"-o",str(work/"test")],check=True)
   subprocess.run([str(work/"test")],check=True)

if __name__=="__main__":unittest.main()
