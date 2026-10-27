#!/usr/bin/env python3
"""Configure/verify isolated schedule test artifacts; never upload to a device."""
from pathlib import Path
import argparse
import configparser
import hashlib
import json
import runpy
import subprocess

SOURCE = "55c18061ace3e48272f6879d2775bba984d6dec6"
ENV = "YD_ESP32S3_N16R8_BOARD_ONLY"
VARIANTS = {"control": ("0", "0"), "schedule-enabled": ("1", "1")}
FROZEN = ("include/BrightnessScheduleRendererBinding.h", "include/TransitionTypes/Transition.h",
          "include/TransitionTypes/Transition.hpp", "src/Led.cpp", "src/WordClock.cpp",
          "include/ClockTestPolicy.h", "include/ClockWorkLedFactory.hpp", "platformio.ini",
          "src/IsolatedBuildCheck.cpp", "tools/capture_isolated_build.py")

def require_defaults():
    text = Path("include/BrightnessScheduleRendererBinding.h").read_text()
    for name in ("RENDERER_CACHE", "SCHEDULE_OUTPUT"):
        assert text.count("#define WORDCLOCK_ENABLE_" + name + " 0") == 1

def parser():
    value = configparser.ConfigParser(interpolation=None)
    value.optionxform = str
    value.read("platformio.ini")
    return value

def snapshot(value):
    return {section: dict(value.items(section, raw=True)) for section in value.sections()}

def configure(variant):
    require_defaults()
    assert not subprocess.check_output(["git", "diff", "--name-only"])
    assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"])
    for name in FROZEN:
        assert Path(name).read_bytes() == subprocess.check_output(["git", "show", SOURCE + ":" + name]), "Unreviewed source: " + name
    value = parser()
    before, defaults = snapshot(value), dict(value.defaults())
    section = "env:" + ENV
    original = value.get(section, "build_flags", raw=True)
    for flags in (value.get(s, "build_flags", raw=True, fallback="") for s in value.sections()):
        assert "WORDCLOCK_ENABLE_RENDERER_CACHE" not in flags and "WORDCLOCK_ENABLE_SCHEDULE_OUTPUT" not in flags
    cache, output = VARIANTS[variant]
    updated = original + "\n-DWORDCLOCK_ENABLE_RENDERER_CACHE=" + cache + "\n-DWORDCLOCK_ENABLE_SCHEDULE_OUTPUT=" + output
    value.set(section, "build_flags", updated)
    with open("platformio.ini", "w") as stream: value.write(stream)
    expected = {name: dict(items) for name, items in before.items()}
    expected[section]["build_flags"] = updated
    reread = parser()
    assert snapshot(reread) == expected and dict(reread.defaults()) == defaults
    assert subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines() == ["platformio.ini"]
    check = Path("src/ScheduleArtifactCompileCheck.cpp")
    assert not check.exists()
    check.write_text('#include <Arduino.h>\n#include <NeoPixelBus.h>\n#include "Config.h"\n'
                     '#include "WordClockState.h"\n#include "ClockTestPolicy.h"\n'
                     '#include "BrightnessScheduleRendererCache.h"\n#include "BrightnessScheduleRendererBinding.h"\n'
                     'static_assert(clockTestPolicy::MODE==1 && !clockTestPolicy::RTC,"Board-only mode required");\n'
                     'static_assert(!clockTestPolicy::MATRIX_OUTPUT && !clockTestPolicy::PREFIX_OUTPUT,"No external LED output");\n'
                     'static_assert(!clockTestPolicy::BUTTON_INPUTS && !clockTestPolicy::BRIGHTNESS_SENSORS,"No external inputs");\n'
                     'static_assert(clockTestPolicy::ONBOARD_OUTPUT && clockTestPolicy::ONBOARD_GPIO==48,"Onboard diagnostics only");\n'
                     'static_assert(WORDCLOCK_ENABLE_RENDERER_CACHE==' + cache + ',"Wrong cache gate");\n'
                     'static_assert(WORDCLOCK_ENABLE_SCHEDULE_OUTPUT==' + output + ',"Wrong schedule gate");\n'
                     'static_assert(sizeof(brightnessScheduleRenderer::Cache<1200>)<=10000,"Cache budget");\n')

def verify(variant):
    require_defaults()
    for name in FROZEN:
        if name != "platformio.ini":
            assert Path(name).read_bytes() == subprocess.check_output(["git", "show", SOURCE + ":" + name]), "Source changed during build: " + name
    capture = runpy.run_path("tools/capture_isolated_build.py")
    entries = json.loads(Path("compile_commands.json").read_text())
    source_dir = (Path.cwd() / "src").resolve()
    project = []
    for entry in entries:
        file = Path(entry["file"])
        if not file.is_absolute(): file = Path(entry.get("directory", str(Path.cwd()))) / file
        if file.resolve().is_relative_to(source_dir): project.append(entry)
    names = {Path(e["file"]).name for e in project}
    assert {"WordClock.cpp", "IsolatedBuildCheck.cpp", "ScheduleArtifactCompileCheck.cpp"} <= names
    cache, output = VARIANTS[variant]
    expected = {"WORDCLOCK_TEST_MODE": "1", "WORDCLOCK_EXPECT_TEST_MODE": "1",
                "WORDCLOCK_BOARD_YD_ESP32S3_N16R8": "1", "BOARD_HAS_PSRAM": "1",
                "WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL": "0", "WORDCLOCK_ENABLE_ONBOARD_STATUS_LED": "1",
                "WORDCLOCK_ENABLE_RENDERER_CACHE": cache, "WORDCLOCK_ENABLE_SCHEDULE_OUTPUT": output}
    for entry in project:
        definitions = capture["definitions"](entry)
        assert all(definitions.get(name) == [value] for name, value in expected.items()), "Missing/conflicting project flags: " + entry["file"]
    dest = Path("build-evidence") / ENV
    manifest = json.loads((dest / "manifest.json").read_text())
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert manifest["commit"] == sha and manifest["environment"] == ENV
    assert manifest["test_mode"] == 1 and manifest["flash_ready"] is False
    for item in manifest["artifacts"]:
        data = (dest / item["name"]).read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    report = {"build_commit": sha, "validated_source_checkpoint": SOURCE, "variant": variant,
              "environment": ENV, "compiled_project_defines": expected, "project_units_checked": len(project),
              "expected_external_strip_backend": "virtual", "rtc_capability": False,
              "onboard_diagnostic_gpio": 48, "source_gate_defaults_changed": False,
              "device_upload_target_invoked": False, "flash_ready": False,
              "runtime_and_hardware_validation": "pending",
              "test_assertion_source": capture["record"](Path("src/ScheduleArtifactCompileCheck.cpp")),
              "firmware_artifacts": manifest["artifacts"]}
    (dest / "schedule-test.json").write_text(json.dumps(report, indent=2) + "\n")

def main():
    arguments = argparse.ArgumentParser()
    arguments.add_argument("command", choices=("configure", "verify"))
    arguments.add_argument("variant", choices=VARIANTS)
    args = arguments.parse_args()
    (configure if args.command == "configure" else verify)(args.variant)

if __name__ == "__main__": main()
