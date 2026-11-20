"""Produce a verified build-local WiFiServer accept guard; no installed edits."""
import hashlib
import json
from pathlib import Path

EXPECTED_BLOB = "db21858125b7e8bd8a2c871981b26df020a145a0"
PROFILES = frozenset(("YD_ESP32S3_N16R8_BOARD_ONLY", "YD_ESP32S3_N16R8_RTC_ONLY"))
HELPER = r"""#if !LWIP_SOCKET_SELECT
#error "Diagnostic listener overlay requires LWIP_SOCKET_SELECT"
#endif
extern "C" void wordclockDiagnosticBeforeNetworkWork();
namespace {
bool wordclockDiagnosticAcceptReady(int fd) {
    if (fd >= LWIP_SOCKET_OFFSET && fd < LWIP_SELECT_MAXNFDS) {
        fd_set readable;
        FD_ZERO(&readable);
        FD_SET(fd, &readable);
        timeval timeout = {0, 0};
        const int ready = lwip_select(fd + 1, &readable, nullptr, nullptr, &timeout);
        if (ready == 0) return false;
    }
    // Readiness errors retain the native accept path, protected in black.
    wordclockDiagnosticBeforeNetworkWork();
    return true;
}
} // namespace
"""
PATCHES = (
    ("  else {\n  struct sockaddr_in _client;",
     "  else {\n  if (!wordclockDiagnosticAcceptReady(sockfd)) return WiFiClient();\n  struct sockaddr_in _client;"),
    ("    struct sockaddr_in _client;",
     "    if (!wordclockDiagnosticAcceptReady(sockfd)) return false;\n    struct sockaddr_in _client;"),
    ("  if(client_sock >= 0){\n",
     "  if(client_sock >= 0){\n    wordclockDiagnosticBeforeNetworkWork();\n"),
)

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

def prepare(source, build_dir, profile):
    source = Path(source)
    if profile not in PROFILES:
        return source
    source = source.resolve(strict=True)
    data = source.read_bytes()
    if git_blob(data) != EXPECTED_BLOB:
        raise ValueError("Unverified WiFiServer.cpp; refusing diagnostic overlay")
    text = data.decode("utf-8")
    for before, after in PATCHES:
        if text.count(before) != 1:
            raise ValueError("Listener guard anchor must occur exactly once")
        text = text.replace(before, after, 1)
    anchor = '#include <lwip/netdb.h>\n'
    if text.count(anchor) != 1:
        raise ValueError("Listener helper include anchor must occur exactly once")
    text = text.replace(anchor, anchor + "\n" + HELPER, 1)
    include = '#include "WiFiServer.h"'
    if text.count(include) != 1:
        raise ValueError("Listener local include must occur exactly once")
    header = (source.parent / "WiFiServer.h").resolve(strict=True).as_posix()
    if any(c in header for c in ('"', '\n', '\r')):
        raise ValueError("Unsupported header path")
    text = text.replace(include, '#include "' + header + '"', 1)
    output = text.encode("utf-8")
    build_dir = Path(build_dir).resolve()
    if build_dir == source.parent or build_dir in source.parents:
        raise ValueError("Overlay build directory must not contain installed source")
    folder = build_dir / "onboard-diagnostic-overlay" / "listener"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "WiFiServer.cpp"
    target.write_bytes(output)
    manifest = {
        "profile": profile, "source": str(source),
        "source_git_blob": EXPECTED_BLOB, "output": str(target),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "patches": len(PATCHES),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target
