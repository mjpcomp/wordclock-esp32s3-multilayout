"""Prepare paired HTTP dispatch and client-probe cleanup overlays; no activation."""
import hashlib
import json
from pathlib import Path
import re

PROFILES = frozenset(("YD_ESP32S3_N16R8_BOARD_ONLY", "YD_ESP32S3_N16R8_RTC_ONLY"))
SOURCES = {'WebServer.cpp': {'blob': 'd296ce716b0bacdce36f0b97ee71dabe9a49bbdf',
                   'start': 'void WebServer::handleClient() {',
                   'end': '\nvoid WebServer::close() {',
                   'method_sha256': 'cf076dc792cef8575c2725ceb51dc239f99c285baba944d5222472a130ddf1a6',
                   'patches': (('  if (_currentStatus == HC_NONE) {\n',
                                '  if (_currentStatus == HC_NONE) {\n'
                                '    if (_currentClient.fd() >= 0) '
                                'wordclockDiagnosticBeforeNetworkWork();\n'),
                               ('      if (_currentClient.available()) {\n',
                                '      if (_currentClient.available()) {\n'
                                '        wordclockDiagnosticBeforeNetworkWork();\n'),
                               ('  if (!keepCurrentClient) {\n',
                                '  if (!keepCurrentClient) {\n'
                                '    wordclockDiagnosticBeforeNetworkWork();\n'))},
 'WiFiClient.cpp': {'blob': 'a4301ad0e09e2d460db158ce620a26cf46cc0e73',
                    'start': 'int WiFiClient::available()\n{',
                    'end': '\n// Though flushing means',
                    'method_sha256': 'a97bbf54dccefff322da84271b6884054fbc470bc7a950f5ae74426c4e2b399b',
                    'patches': (('    if(_rxBuffer->failed()) {\n',
                                 '    if(_rxBuffer->failed()) {\n'
                                 '        wordclockDiagnosticBeforeNetworkWork();\n'),)}}

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

def guard_method(name, method):
    spec = SOURCES[name]
    if hashlib.sha256(method.encode("utf-8")).hexdigest() != spec["method_sha256"]:
        raise ValueError("Unverified HTTP/client method")
    for before, after in spec["patches"]:
        if method.count(before) != 1:
            raise ValueError("HTTP guard anchor must occur exactly once")
        method = method.replace(before, after, 1)
    return method

def prepare(source, build_dir, profile):
    source = Path(source)
    if profile not in PROFILES:
        return source
    if source.name not in SOURCES:
        raise ValueError("Unsupported HTTP overlay source")
    source = source.resolve(strict=True)
    spec = SOURCES[source.name]
    data = source.read_bytes()
    if git_blob(data) != spec["blob"]:
        raise ValueError("Unverified HTTP overlay source")
    text = data.decode("utf-8")
    if text.count(spec["start"]) != 1:
        raise ValueError("HTTP method start must occur exactly once")
    start = text.index(spec["start"])
    end = text.index(spec["end"], start)
    method = text[start:end].rstrip("\n") + "\n"
    text = text[:start] + guard_method(source.name, method) + text[start+len(method):]
    def include(match):
        header = source.parent / match.group(1)
        if not header.is_file():
            return match.group(0)
        name = header.resolve().as_posix()
        if any(c in name for c in ('"', '\n', '\r')):
            raise ValueError("Unsupported header path")
        return '#include "' + name + '"'
    text = re.sub(r'^#include "([^"\r\n]+)"$', include, text, flags=re.MULTILINE)
    text = 'extern "C" void wordclockDiagnosticBeforeNetworkWork();\n' + text
    build_dir = Path(build_dir).resolve()
    if build_dir == source.parent or build_dir in source.parents:
        raise ValueError("Overlay build directory must not contain installed source")
    folder = build_dir / "onboard-diagnostic-overlay" / "http" / source.stem
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / source.name
    output = text.encode("utf-8")
    target.write_bytes(output)
    manifest = {
        "profile": profile, "source": str(source), "source_git_blob": spec["blob"],
        "method_sha256": spec["method_sha256"], "output": str(target),
        "output_sha256": hashlib.sha256(output).hexdigest(), "patches": len(spec["patches"]),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target
