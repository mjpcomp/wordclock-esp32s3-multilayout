"""Generate an isolated, verified MQTT source overlay; never edit dependencies."""
import hashlib
import json
from pathlib import Path

EXPECTED_BLOB = "2b48d2b6b8ff28f5be7ad46a06c2e4f3f389aeae"
PROFILES = frozenset(("YD_ESP32S3_N16R8_BOARD_ONLY", "YD_ESP32S3_N16R8_RTC_ONLY"))
HOOK = "wordclockDiagnosticBeforeNetworkWork();"
PATCHES = (
    ("        if ((t - lastInActivity > this->keepAlive*1000UL) || (t - lastOutActivity > this->keepAlive*1000UL)) {\n",
     "            " + HOOK + "\n"),
    ("        if (_client->available()) {\n", "            " + HOOK + "\n"),
    ("            if (this->_state == MQTT_CONNECTED) {\n", "                " + HOOK + "\n"),
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
        raise ValueError("Unverified PubSubClient.cpp; refusing diagnostic overlay")
    text = data.decode("utf-8")
    for anchor, addition in PATCHES:
        if text.count(anchor) != 1:
            raise ValueError("MQTT guard anchor must occur exactly once: " + anchor.strip())
        text = text.replace(anchor, anchor + addition, 1)
    include = '#include "PubSubClient.h"'
    if text.count(include) != 1:
        raise ValueError("MQTT local include must occur exactly once")
    header = (source.parent / "PubSubClient.h").resolve(strict=True)
    header_name = header.as_posix()
    if any(c in header_name for c in ('"', '\n', '\r')):
        raise ValueError("Unsupported header path")
    text = text.replace(include, '#include "' + header_name + '"', 1)
    declaration = 'extern "C" void wordclockDiagnosticBeforeNetworkWork();\n'
    text = declaration + text
    output = text.encode("utf-8")
    build_dir = Path(build_dir).resolve()
    if build_dir == source.parent or build_dir in source.parents:
        raise ValueError("Overlay build directory must not contain installed source")
    folder = build_dir / "onboard-diagnostic-overlay" / "mqtt"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "PubSubClient.cpp"
    target.write_bytes(output)
    manifest = {
        "profile": profile,
        "source": str(source),
        "source_git_blob": EXPECTED_BLOB,
        "output": str(target),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "guard_insertions": len(PATCHES),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target
