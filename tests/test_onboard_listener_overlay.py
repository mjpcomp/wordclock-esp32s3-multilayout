#!/usr/bin/env python3
"""Host checks of guarded, source-derived accept methods; sockets are mocked."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("listener_overlay", ROOT / "tools/onboard_listener_overlay.py")
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)
SOURCE = (ROOT / "tests/fixtures/WiFiServer-2.0.17.cpp.txt").read_text(encoding="utf-8")
CPP = r"""#include <cassert>
#include <cerrno>
#include <string>
#include <sys/select.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#define LWIP_SOCKET_SELECT 1
#define LWIP_SOCKET_OFFSET 54
#define LWIP_SELECT_MAXNFDS 64
#define ESP_IDF_VERSION_MAJOR 4
#define ESP_OK 0
static std::string events;
static int readiness=0, acceptResult=42, queries=0, accepts=0, options=0, sinkWrites=0, expectedFd=55;
static bool latched=false, arriveAfterPoll=false;
extern "C" void wordclockDiagnosticBeforeNetworkWork() {
 events += "B";
 if (!latched) { latched=true; ++sinkWrites; }
}
int fakeSelect(int n, fd_set *r, fd_set *w, fd_set *x, timeval *t) {
 ++queries; events += "S";
 assert(n == expectedFd+1 && FD_ISSET(expectedFd,r));
 assert(!w && !x && t && t->tv_sec==0 && t->tv_usec==0);
 const int result=readiness;
 if (arriveAfterPoll) { readiness=1; arriveAfterPoll=false; }
 if (result==0) FD_ZERO(r);
 if (result<0) errno=EIO;
 return result;
}
int fakeAccept(int, sockaddr *, socklen_t *) {
 assert(latched); events += "A"; ++accepts;
 if (acceptResult<0) errno=EAGAIN;
 return acceptResult;
}
int fakeSetOption(int, int, int, const void *, socklen_t) {
 assert(latched); events += "O"; ++options; return 0;
}
#define lwip_select fakeSelect
#define lwip_accept fakeAccept
#define setsockopt fakeSetOption
struct WiFiClient {
 int socket;
 WiFiClient():socket(-1) {}
 explicit WiFiClient(int s):socket(s) {}
};
class WiFiServer {
 int sockfd, _accepted_sockfd=-1;
 bool _listening, _noDelay=false;
public:
 explicit WiFiServer(int fd=55, bool listening=true):sockfd(fd),_listening(listening) {}
 void seed(int fd) { _accepted_sockfd=fd; }
 int cached() const { return _accepted_sockfd; }
 WiFiClient available();
 bool hasClient();
};
void reset() {
 events.clear(); readiness=0; acceptResult=42; queries=accepts=options=sinkWrites=0;
 latched=false; arriveAfterPoll=false; expectedFd=55;
}
"""
MAIN = r"""int main() {
 reset(); WiFiServer idle;
 assert(!idle.hasClient()); assert(idle.available().socket==-1);
 assert(queries==2 && accepts==0 && sinkWrites==0);
 reset(); readiness=1; WiFiServer cache;
 assert(cache.hasClient() && cache.cached()==42);
 assert(events=="SBA" && accepts==1 && sinkWrites==1);
 const auto previous=events; assert(cache.hasClient() && events==previous);
 readiness=0; assert(cache.available().socket==42 && cache.cached()==-1);
 assert(queries==1 && accepts==1 && options==2 && sinkWrites==1);
 reset(); WiFiServer cached; cached.seed(42);
 assert(cached.hasClient() && queries==0 && sinkWrites==0);
 assert(cached.available().socket==42 && accepts==0 && options==2 && sinkWrites==1);
 reset(); readiness=1; WiFiServer direct;
 assert(direct.available().socket==42 && accepts==1 && options==2 && sinkWrites==1);
 assert(events.find('B') < events.find('A'));
 reset(); readiness=-1; acceptResult=-1; WiFiServer error;
 assert(!error.hasClient() && accepts==1 && sinkWrites==1 && errno==EAGAIN);
 assert(events=="SBA");
 reset(); readiness=1; acceptResult=-1; WiFiServer raced;
 assert(!raced.hasClient() && accepts==1 && sinkWrites==1);
 reset(); arriveAfterPoll=true; WiFiServer arrival;
 assert(!arrival.hasClient() && accepts==0 && sinkWrites==0);
 assert(arrival.hasClient() && accepts==1 && sinkWrites==1);
 reset(); WiFiServer closed(55,false);
 assert(closed.available().socket==-1 && queries==0 && accepts==0 && sinkWrites==0);
 reset(); acceptResult=-1; WiFiServer invalid(-1);
 assert(!invalid.hasClient() && queries==0 && accepts==1 && sinkWrites==1);
 reset(); acceptResult=-1; WiFiServer outside(64);
 assert(!outside.hasClient() && queries==0 && accepts==1 && sinkWrites==1);
 reset(); readiness=1; expectedFd=54; WiFiServer offset(54);
 assert(offset.hasClient() && queries==1 && accepts==1 && sinkWrites==1);
}
"""

def method(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{": depth += 1
        if source[i] == "}": depth -= 1
        if depth == 0:
            return source[start:i+1] + "\n"
    raise AssertionError("Unterminated pinned-source method")

class ListenerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "installed/WiFiServer.cpp"
        self.source.parent.mkdir()
        self.source.write_text(SOURCE, encoding="utf-8")
        (self.source.parent / "WiFiServer.h").write_text("// host fixture header\n")
        self.build = self.root / "build"

    def test_reference_identity_and_normal_passthrough(self):
        self.assertEqual(overlay.git_blob(SOURCE.encode()), overlay.EXPECTED_BLOB)
        for profile in ("ESP8266", "ESP32", "ESP32C3", "YD_ESP32S3_N16R8"):
            missing = self.root / "missing.cpp"
            self.assertEqual(overlay.prepare(missing, self.build, profile), missing)
        self.assertFalse(self.build.exists())

    def test_mismatch_rejected_before_writes(self):
        self.source.write_text(SOURCE + "// changed\n")
        with self.assertRaisesRegex(ValueError, "Unverified"):
            overlay.prepare(self.source, self.build, "YD_ESP32S3_N16R8_BOARD_ONLY")
        self.assertFalse(self.build.exists())

    def test_both_profiles_preserve_input_and_manifest(self):
        for profile in sorted(overlay.PROFILES):
            target = overlay.prepare(self.source, self.build, profile)
            first = target.read_bytes()
            self.assertEqual(overlay.prepare(self.source, self.build, profile).read_bytes(), first)
            self.assertEqual(self.source.read_text(), SOURCE)
            manifest = json.loads((target.parent / "manifest.json").read_text())
            self.assertEqual(manifest["profile"], profile)
            self.assertEqual(manifest["source_git_blob"], overlay.EXPECTED_BLOB)
            self.assertIn('Server.cpp - Server class for Raspberry Pi', first.decode())
            for before, after in overlay.PATCHES:
                self.assertIn(after, first.decode())

    def test_anchor_validation(self):
        for anchor, _ in overlay.PATCHES:
            for text in (SOURCE.replace(anchor,""), SOURCE+anchor):
                self.source.write_text(text)
                with patch.object(overlay, "EXPECTED_BLOB", overlay.git_blob(text.encode())):
                    with self.assertRaisesRegex(ValueError, "exactly once"):
                        overlay.prepare(self.source, self.build, "YD_ESP32S3_N16R8_BOARD_ONLY")
        self.assertFalse(self.build.exists())

    def test_native_method_order_with_mocked_socket_calls(self):
        compiler = shutil.which("g++")
        if not compiler:
            self.fail("g++ is required")
        target = overlay.prepare(self.source, self.build, "YD_ESP32S3_N16R8_BOARD_ONLY")
        transformed = target.read_text()
        code = CPP + overlay.HELPER
        code += method(transformed, "WiFiClient WiFiServer::available()")
        code += method(transformed, "bool WiFiServer::hasClient()") + MAIN
        (self.root / "test.cpp").write_text(code)
        subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all",
                        str(self.root / "test.cpp"), "-o", str(self.root / "test")], check=True)
        subprocess.run([str(self.root / "test")], check=True)

if __name__ == "__main__":
    unittest.main()
