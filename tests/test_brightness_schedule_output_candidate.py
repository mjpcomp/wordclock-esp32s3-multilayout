#!/usr/bin/env python3
"""Stage a counted integration candidate only in a disposable checkout.
Host regression extracts actual candidate transition methods; color/geometry,
allocation, runtime handoff and unrelated transition branches are test seams.
The existing suites and six native builds remain required validation.
"""
from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "docs/patches/brightness-schedule-output.json"

def extract(text, signature):
    matches = list(re.finditer(r"^" + signature + r"\s*\{", text, re.M))
    if len(matches) != 1:
        raise ValueError("method drift: " + signature)
    match = matches[0]
    pos, depth = match.end(), 1
    while depth and pos < len(text):
        if text[pos] == "{": depth += 1
        elif text[pos] == "}": depth -= 1
        pos += 1
    if depth: raise ValueError("unbalanced method")
    return text[match.start():pos]

def disabled_projection(text):
    stack, output, skip = [], [], False
    for line in text.splitlines():
        token = line.strip()
        if re.match(r"#\s*(if|ifdef|ifndef)\b", token):
            own = token == "#if WORDCLOCK_ENABLE_SCHEDULE_OUTPUT"
            stack.append((skip, own))
            if not skip and not own: output.append(token)
            skip = skip or own
        elif re.match(r"#\s*endif\b", token):
            previous, own = stack.pop()
            if not skip and not own: output.append(token)
            skip = previous
        elif not skip and token:
            output.append(token)
    if stack: raise ValueError("unbalanced preprocessor blocks")
    return output

def prepare(root):
    manifest = json.loads((root / MANIFEST).read_text())
    replacements = manifest["replacements"]
    names = {item["path"] for item in replacements}
    allowed = {"src/Led.cpp", "src/WordClock.cpp", "include/BrightnessScheduleRendererBinding.h",
               "include/TransitionTypes/Transition.h", "include/TransitionTypes/Transition.hpp"}
    if names != allowed: raise ValueError("candidate scope drift")
    before = {name: (root / name).read_text() for name in names}
    after = dict(before)
    for item in replacements:
        name, old, new = item["path"], item["old"], item["new"]
        if not old or after[name].count(old) != 1:
            raise ValueError("source anchor drift: " + name + " / " + old[:70])
        after[name] = after[name].replace(old, new, 1)
    for name in names:
        candidate = after[name]
        if name == "include/TransitionTypes/Transition.h":
            include = '#include "BrightnessScheduleRendererBinding.h"\n'
            if candidate.count(include) != 1: raise ValueError("gate include drift")
            if candidate.index(include) > candidate.index("#if WORDCLOCK_ENABLE_SCHEDULE_OUTPUT"):
                raise ValueError("gate definitions follow conditional class members")
            candidate = candidate.replace(include, "", 1)
        if disabled_projection(candidate) != disabled_projection(before[name]):
            raise ValueError("schedule-off source projection changed: " + name)
    return after

def regression(candidate):
    compiler = shutil.which("g++")
    if not compiler: raise SystemExit("g++ required")
    text = candidate["include/TransitionTypes/Transition.hpp"]
    signatures = [r"void Transition::fillMatrix\(RgbfColor \*\*matrix, RgbfColor color\)",
                  r"void Transition::copyMatrix\(RgbfColor \*\*dest, RgbfColor \*\*source\)",
                  r"void Transition::analyzeColors\(RgbfColor \*\*dest, RgbfColor \*\*source,\s*RgbfColor &foreground, RgbfColor &background\)",
                  r"void Transition::saveMatrix\(\)", r"void Transition::copy2Stripe\(RgbfColor \*\*source\)",
                  r"void Transition::resetBrightnessPolicy\(\)",
                  r"bool Transition::isOverwrittenByTransition\(WordclockChanges changesInWordMatrix,\s*uint8_t minute\)"]
    bodies = "\n".join(extract(text, signature) for signature in signatures)
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        src = work / "test.cpp"
        src.write_text(CPP.replace("/*EXTRACTED*/", bodies))
        exe = work / "test"
        subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all",
                        "-DWORDCLOCK_ENABLE_SCHEDULE_OUTPUT=1", str(src), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-output", action="store_true")
    args = parser.parse_args()
    candidate = prepare(ROOT)
    regression(candidate)
    if args.stage_output:
        for name, content in candidate.items(): (ROOT / name).write_text(content)
        subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
        print("Staged application-output candidate in disposable checkout; gates unchanged")
    print("PASS: counted source staging, schedule-off projection, extracted transition reset/hold regression")

CPP = r'''#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstring>
struct RgbColor {
    uint8_t R,G,B;
    RgbColor(uint8_t v=0):R(v),G(v),B(v){}
    RgbColor(uint8_t r,uint8_t g,uint8_t b):R(r),G(g),B(b){}
};
struct HsbColor { RgbColor value; explicit HsbColor(RgbColor p):value(p){} };
struct RgbfColor:RgbColor {
    uint8_t Flags=0;
    RgbfColor(uint8_t v=0):RgbColor(v){}
    RgbfColor(RgbColor p):RgbColor(p){}
    bool operator==(const RgbfColor &p) const { return R==p.R&&G==p.G&&B==p.B; }
    void setForeground(bool v) { if(v)Flags|=1;else Flags&=~1; }
    void setOverlay(bool v) { if(v)Flags|=2;else Flags&=~2; }
};
enum class WordclockChanges { Parameters, Minute, Words, Layout };
constexpr unsigned NO_TRANSITION=0;
struct { uint8_t buildTypeDef=1; } G;
uint8_t getLedsPerLetter(uint8_t n) { return n; }
struct Face { uint16_t getFrontMatrixIndex(uint8_t,uint8_t c) { return c; } } face;
Face *usedClockType=&face;
struct Led {
    RgbColor pixels[2]; unsigned writes=0;
    RgbColor getPixel(uint16_t i) { assert(i<2);return pixels[i]; }
    void setPixel(uint8_t,uint8_t c,HsbColor p) { assert(c<2);pixels[c]=p.value;++writes; }
} led;
#define STRIPE NULL
bool brightnessScheduleSyncOutput();
class Transition {
public:
    uint8_t maxRows=1,maxCols=2; uint16_t sizeofColumn=sizeof(RgbfColor)*2;
    RgbfColor oldData[2],actData[2],workData[2];
    RgbfColor *old[1]={oldData},*act[1]={actData},*work[1]={workData};
    RgbfColor foreground,background;RgbColor foregroundMinute;
    uint16_t phase=7;uint32_t nextActionTime=100;bool matrixChanged=false,brightnessPolicyPending_=false;
    unsigned transitionType=1;uint8_t lastMinute=0;
    void fillMatrix(RgbfColor**,RgbfColor);
    void copyMatrix(RgbfColor**,RgbfColor**);
    void analyzeColors(RgbfColor**,RgbfColor**,RgbfColor&,RgbfColor&);
    void saveMatrix();void copy2Stripe(RgbfColor**);void resetBrightnessPolicy();
    bool isOverwrittenByTransition(WordclockChanges,uint8_t);
    bool isColorization() { return false; }
    void colorize(RgbfColor**) { assert(false); }
    bool hasMinuteChanged() { return false; }
    void initTransitionStart() { phase=1; }
    bool changeBrightness() { assert(false);return false; }
    bool isIdle() { return phase==0; }
} transition;
bool changed=false;
bool brightnessScheduleSyncOutput() {
    if(changed) {
        transition.resetBrightnessPolicy();
        led.pixels[0]=RgbColor(0);led.pixels[1]=RgbColor(0);
        changed=false;
    }
    return true;
}
/*EXTRACTED*/
int main() {
    for(unsigned repeat=0;repeat<3;++repeat) {
        transition.work[0][0]=RgbfColor(RgbColor(200,100,50));
        led.pixels[0]=RgbColor(80,40,20);changed=true;
        const unsigned before=led.writes;
        transition.copy2Stripe(transition.work);
        assert(transition.brightnessPolicyPending_&&transition.phase==0);
        assert(led.writes==before&&led.pixels[0].R==0);
        assert(transition.old[0][0].R==0&&transition.act[0][0].R==0&&transition.work[0][0].R==0);
        led.pixels[0]=RgbColor(60,30,15);led.pixels[1]=RgbColor(0);
        assert(transition.isOverwrittenByTransition(WordclockChanges::Parameters,0));
        assert(!transition.brightnessPolicyPending_&&transition.phase==0&&!transition.matrixChanged);
        assert(transition.old[0][0].R==60&&transition.act[0][0].R==60&&transition.work[0][0].R==60);
        transition.copy2Stripe(transition.work);
        assert(led.pixels[0].R==60&&led.pixels[1].R==0);
    }
}
'''

if __name__ == "__main__":
    main()
