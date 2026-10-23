#!/usr/bin/env python3
"""Use the PlatformIO-resolved NeoPixelBus color sources, never mock color math.
Requires the selected environment's dependencies to be installed first.
Host Arduino/PROGMEM glue only; not wire-order, physical LED or full firmware validation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("RgbColor.cpp", "RgbwColor.cpp", "RgbColorBase.cpp", "HsbColor.cpp", "HslColor.cpp")

# Match the color part of upstream NeoColors without unrelated gamma/diagnostics.
COLOR_HEADERS = (
    "internal/NeoSettings.h",
    "internal/colors/NeoHueBlend.h",
    "internal/colors/RgbColorBase.h",
    "internal/colors/RgbColor.h",
    "internal/colors/Rgb16Color.h",
    "internal/colors/Rgb48Color.h",
    "internal/colors/HslColor.h",
    "internal/colors/HsbColor.h",
    "internal/colors/HtmlColor.h",
    "internal/colors/RgbwColor.h",
    "internal/colors/Rgbw64Color.h",
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", required=True)
    args = parser.parse_args()
    if args.environment not in ("YD_ESP32S3_N16R8_BOARD_ONLY", "YD_ESP32S3_N16R8_RTC_ONLY"):
        raise SystemExit("Select a reviewed isolated environment")
    compiler = shutil.which("g++")
    if not compiler: raise SystemExit("g++ required")
    library = ROOT / ".pio/libdeps" / args.environment / "NeoPixelBus"
    manifest_path = library / "library.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("name") not in ("NeoPixelBus", "NeoPixelBus by Makuna") or not manifest.get("version"):
        raise SystemExit("Unrecognized resolved NeoPixelBus manifest")
    print("Real-color check:", args.environment, "NeoPixelBus", manifest["version"], flush=True)
    src = library / "src"
    color_sources = [src / "internal/colors" / name for name in SOURCES]
    for path in [src / name for name in COLOR_HEADERS] + color_sources:
        if not path.is_file(): raise SystemExit("Resolved color source layout changed: " + str(path))
    led = (ROOT / "src/Led.cpp").read_text()
    begin = led.index("const uint8_t whiteAdjR[3]")
    conversion = led[begin:led.index("} // namespace",begin)]
    test = (ROOT / "tests/brightness_schedule_real_colors_test.cpp").read_text()
    if test.count("/*NATIVE_CONVERSION*/") != 1: raise SystemExit("Conversion marker drift")
    test = test.replace("/*NATIVE_CONVERSION*/", "using std::min;\nenum WhiteType { Warm, Neutral, Cool };\n" + conversion)
    project_headers = ("BrightnessScheduleRendererCache.h", "BrightnessScheduleOutputBuffer.h", "BrightnessScheduleRuntimeModel.h", "BrightnessSchedule.h")
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        for name in project_headers: shutil.copyfile(ROOT / "include" / name,work / name)
        (work / "Arduino.h").write_text(ARDUINO)
        (work / "pgmspace.h").write_text('#include "Arduino.h"\n')
        (work / "avr").mkdir()
        (work / "avr/pgmspace.h").write_text('#include "Arduino.h"\n')
        # Real color/settings declarations only: no gamma, Serial or drivers.
        (work / "NeoPixelBus.h").write_text('#pragma once\n#include "Arduino.h"\n' +
            ''.join('#include "' + name + '"\n' for name in COLOR_HEADERS))
        (work / "test.cpp").write_text(test)
        binary = work / "real-colors"
        subprocess.run([compiler,"-std=c++11","-UNDEBUG","-Wall","-Wextra",
                        "-ffunction-sections","-fdata-sections","-Wl,--gc-sections",
                        "-fsanitize=undefined,bounds","-fno-sanitize-recover=all",
                        "-I",str(work),"-I",str(src),str(work / "test.cpp")]
                       + [str(p) for p in color_sources] + ["-o",str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
    files = [manifest_path] + sorted(src.rglob("*.h")) + color_sources
    evidence = {"environment":args.environment,"NeoPixelBus":manifest["version"],
                "scope":"648 real color/cache cases; host only; no LED driver",
                "sha256":{str(p.relative_to(library)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                "project_sha256":{n:hashlib.sha256((ROOT / "include" / n).read_bytes()).hexdigest() for n in project_headers}}
    print(json.dumps(evidence,sort_keys=True))

ARDUINO = '#pragma once\n#include <stdint.h>\n#include <stddef.h>\n#include <ctype.h>\n#include <cmath>\n#include <cstring>\n#include <cstdlib>\n#include <cstdio>\n#include <algorithm>\n#include <limits>\n#include <type_traits>\nusing std::min;\nusing std::max;\nusing byte = uint8_t;\n// Declarations only: HtmlColor\'s unused overload needs this Arduino interface.\n// No string behavior or color conversion is substituted by the host shim.\nclass String { public: const char* c_str() const; size_t length() const; };\n#define PROGMEM\n#define PGM_P const char*\n#define PSTR(s) (s)\ntemplate<class T> T hostRead(const void* p) { T v; std::memcpy(&v,p,sizeof(v)); return v; }\n#define pgm_read_byte(p) hostRead<uint8_t>(p)\n#define pgm_read_byte_near(p) hostRead<uint8_t>(p)\n#define pgm_read_word(p) hostRead<uint16_t>(p)\n#define pgm_read_dword(p) hostRead<uint32_t>(p)\n#define pgm_read_float(p) hostRead<float>(p)\n#define pgm_read_ptr(p) hostRead<const void*>(p)\n#define memcpy_P std::memcpy\n#define strlen_P std::strlen\n#define strcmp_P std::strcmp\n#define strncpy_P std::strncpy\n#define snprintf_P std::snprintf\n// No pin, SPI, RMT, timing or LED-driver functions are provided.\n'

if __name__ == "__main__":
    main()
