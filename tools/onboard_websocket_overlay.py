"""Prepare synchronous ESP32 websocket source copies; never register or activate."""
import hashlib
import json
from pathlib import Path
import re

PROFILES=frozenset(("YD_ESP32S3_N16R8_BOARD_ONLY","YD_ESP32S3_N16R8_RTC_ONLY"))
SOURCES={'WebSockets.cpp': ('2d3a2547d17cf7bb904a8bdb5120415d66080d34',
                    ('disconnect', 'write', 'heartbeat')),
 'WebSocketsServer.cpp': ('e11e1cf7c8552531cd3fd681cde4260c27f41944',
                          ('drop', 'cleanup', 'connected', 'data'))}
METHODS={'disconnect': {'signature': 'void WebSockets::clientDisconnect(WSclient_t * client, uint16_t '
                             'code, char * reason, size_t reasonLen) {',
                'sha256': 'f6255d250f4d94fbda460118625fce2d1988352d4fa868042bdd552aadfe5aa0',
                'patches': [('void WebSockets::clientDisconnect(WSclient_t * client, uint16_t '
                             'code, char * reason, size_t reasonLen) {\n',
                             'void WebSockets::clientDisconnect(WSclient_t * client, uint16_t '
                             'code, char * reason, size_t reasonLen) {\n'
                             '    wordclockDiagnosticBeforeNetworkWork();\n')]},
 'write': {'signature': 'size_t WebSockets::write(WSclient_t * client, uint8_t * out, size_t n) '
                        '{',
           'sha256': '9e988cc8a706e7a1e9ca8eec509fd4f29d631902995224751d5a10ce325bef41',
           'patches': [('    unsigned long t = millis();\n',
                        '    if(n > 0) wordclockDiagnosticBeforeNetworkWork();\n'
                        '    unsigned long t = millis();\n')]},
 'heartbeat': {'signature': 'void WebSockets::handleHBTimeout(WSclient_t * client) {',
               'sha256': 'c4dfc3f6433e8304a20971979f94ab397a2a56539f2cd20e3ded181db0d8131b',
               'patches': []},
 'drop': {'signature': 'void WebSocketsServerCore::dropNativeClient(WSclient_t * client) {',
          'sha256': 'addc6d5229ec056080bdc043f02e66e6425dec5c9be447748af6161c2f86baf1',
          'patches': [('    if(client->tcp) {\n',
                       '    if(client->tcp) {\n'
                       '        wordclockDiagnosticBeforeNetworkWork();\n')]},
 'cleanup': {'signature': 'void WebSocketsServerCore::clientDisconnect(WSclient_t * client) {',
             'sha256': 'a1cc9afc3aee1f3420649526d0c35a6247e3871f6a94ed8e2f19f057201fe184',
             'patches': [('void WebSocketsServerCore::clientDisconnect(WSclient_t * client) {\n',
                          'void WebSocketsServerCore::clientDisconnect(WSclient_t * client) {\n'
                          '    wordclockDiagnosticBeforeNetworkWork();\n')]},
 'connected': {'signature': 'bool WebSocketsServerCore::clientIsConnected(WSclient_t * client) {',
               'sha256': '6d37c6bbef4152b43e832e7875e29893791dfc5555dbf8ebc2ddcff785a37218',
               'patches': []},
 'data': {'signature': 'void WebSocketsServerCore::handleClientData(void) {',
          'sha256': '16173fe6fd38ef39961b13df6a9f1b5073a9749848d35a98a6e408299ea5c2fb',
          'patches': [('            if(len > 0) {\n',
                       '            if(len > 0) {\n'
                       '                wordclockDiagnosticBeforeNetworkWork();\n')]}}

def git_blob(data):
 return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def guard_method(key,text):
 spec=METHODS[key]
 if hashlib.sha256(text.encode()).hexdigest()!=spec["sha256"]:
  raise ValueError("Unverified websocket method")
 for before,after in spec["patches"]:
  if text.count(before)!=1:raise ValueError("Websocket anchor must occur exactly once")
  text=text.replace(before,after,1)
 return text

def prepare(source,build_dir,profile):
 source=Path(source)
 if profile not in PROFILES:return source
 if source.name not in SOURCES:raise ValueError("Unsupported websocket source")
 source=source.resolve(strict=True)
 raw=source.read_bytes()
 expected,keys=SOURCES[source.name]
 if git_blob(raw)!=expected:raise ValueError("Unverified websocket source")
 if raw.replace(b"\r\n",b"\n").replace(b"\n",b"\r\n")!=raw:
  raise ValueError("Expected upstream CRLF source")
 text=raw.decode().replace("\r\n","\n")
 for key in keys:
  signature=METHODS[key]["signature"]+"\n"
  if text.count(signature)!=1:raise ValueError("Websocket method must occur exactly once")
  start=text.index(signature)
  end=text.index("\n}\n",start)+3
  original=text[start:end]
  text=text[:start]+guard_method(key,original)+text[end:]
 def include(match):
  header=source.parent/match.group(1)
  if not header.is_file():return match.group(0)
  name=header.resolve().as_posix()
  if any(c in name for c in ('"','\n','\r')):raise ValueError("Unsupported header path")
  return '#include "'+name+'"'
 text=re.sub(r'^#include "([^"\r\n]+)"$',include,text,flags=re.MULTILINE)
 declaration='extern "C" void wordclockDiagnosticBeforeNetworkWork();\n'
 gate='#if !defined(ESP32) || (WEBSOCKETS_NETWORK_TYPE != NETWORK_ESP32)\n#error "Diagnostic websocket overlay requires synchronous ESP32"\n#endif\n'
 # The network macros come from WebSockets.h, so place the gate after that include.
 header=(source.parent/"WebSockets.h").resolve(strict=True).as_posix()
 anchor='#include "'+header+'"\n'
 if text.count(anchor)!=1:raise ValueError("Websocket include must occur exactly once")
 text=text.replace(anchor,anchor+gate+declaration,1)
 build_dir=Path(build_dir).resolve()
 if build_dir==source.parent or build_dir in source.parents:
  raise ValueError("Build directory must not contain installed source")
 folder=build_dir/"onboard-diagnostic-overlay"/"websocket"/source.stem
 folder.mkdir(parents=True,exist_ok=True)
 target=folder/source.name
 output=text.replace("\n","\r\n").encode()
 target.write_bytes(output)
 manifest={"profile":profile,"source":str(source),"source_git_blob":expected,
           "output":str(target),"output_sha256":hashlib.sha256(output).hexdigest(),
           "methods":{key:METHODS[key]["sha256"] for key in keys}}
 (folder/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
 return target
