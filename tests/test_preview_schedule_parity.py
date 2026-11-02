#!/usr/bin/env python3
"""Compare valid-time JS samples with the host C++ evaluator; no GPIO/firmware."""
import json
from pathlib import Path
import random
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DAY_MS = 86400000


def cases():
    profiles = [
        {"defaultTenths": 0, "events": []},
        {"defaultTenths": 1000, "events": []},
        {"defaultTenths": 900, "events": [{"minute": 600, "targetTenths": 50, "fadeMinutes": 60}]},
        {"defaultTenths": 400, "events": [{"minute": 420, "targetTenths": 800, "fadeMinutes": 10}, {"minute": 1430, "targetTenths": 200, "fadeMinutes": 20}]},
        {"defaultTenths": 500, "events": [{"minute": 1, "targetTenths": 0, "fadeMinutes": 0}, {"minute": 1439, "targetTenths": 1000, "fadeMinutes": 2}]},
        {"defaultTenths": 100, "events": [{"minute": 0, "targetTenths": 1000, "fadeMinutes": 30}, {"minute": 30, "targetTenths": 0, "fadeMinutes": 0}]},
    ]
    rng = random.Random(731)
    for _ in range(18):
        times = sorted(rng.sample(range(1440), rng.randint(1, 16)))
        events = []
        for index, minute in enumerate(times):
            gap = 1440 if len(times) == 1 else (times[(index + 1) % len(times)] - minute) % 1440
            events.append({"minute": minute, "targetTenths": rng.randrange(1001), "fadeMinutes": rng.randrange(min(gap, 1439) + 1)})
        profiles.append({"defaultTenths": rng.randrange(1001), "events": events})
    result = []
    for profile in profiles:
        samples = set(range(0, DAY_MS, 60000)) | {0, 1, DAY_MS - 1}
        for event in profile["events"]:
            start = event["minute"] * 60000
            duration = event["fadeMinutes"] * 60000
            for center in [start, start + duration // 2, start + duration]:
                samples.update((center + delta) % DAY_MS for delta in [-1, 0, 1])
        result.append({"schedule": profile, "samplesMs": sorted(samples)})
    return result


def main():
    node, compiler = shutil.which("node"), shutil.which("g++")
    if not node or not compiler:
        raise SystemExit("node and g++ are required; parity was not run")
    values = cases()
    js = "const fs=require('node:fs'),m=require(process.argv[1]);const c=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(c.flatMap(x=>x.samplesMs.map(t=>m.sampleTenths(x.schedule,t/60000)/10))));"
    actual = json.loads(subprocess.check_output([node, "-e", js, str(ROOT / "webpage/schedule-model.js")], input=json.dumps(values), text=True))
    source = r'''#include "BrightnessSchedule.h"
#include <iostream>
#include <iomanip>
int main() {
    unsigned total;
    if (!(std::cin >> total)) return 2;
    std::cout << std::setprecision(9);
    for (unsigned n=0; n<total; ++n) {
        brightnessSchedule::Schedule schedule = {};
        unsigned count;
        std::cin >> schedule.defaultTenths >> count;
        if (count > brightnessSchedule::MAX_EVENTS) return 3;
        schedule.count = static_cast<uint8_t>(count);
        for (unsigned i=0; i<count; ++i)
            std::cin >> schedule.events[i].minute >> schedule.events[i].targetTenths >> schedule.events[i].fadeMinutes;
        if (!brightnessSchedule::valid(schedule)) return 4;
        unsigned samples; std::cin >> samples;
        for (unsigned i=0; i<samples; ++i) {
            uint32_t ms; std::cin >> ms;
            if (!std::cin || ms >= brightnessSchedule::DAY_MS) return 5;
            std::cout << brightnessSchedule::percent(schedule,ms,true) << '\n';
        }
    }
    return 0;
}
'''
    rows = [str(len(values))]
    for value in values:
        profile = value["schedule"]
        rows.append(str(profile["defaultTenths"]) + " " + str(len(profile["events"])))
        rows.extend("{minute} {targetTenths} {fadeMinutes}".format(**event) for event in profile["events"])
        rows.extend([str(len(value["samplesMs"])), " ".join(map(str, value["samplesMs"]))])
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        (work / "parity.cpp").write_text(source)
        subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-fsanitize=undefined,bounds", "-fno-sanitize-recover=all", "-I" + str(ROOT / "include"), str(work / "parity.cpp"), "-o", str(work / "parity")], check=True)
        expected = [float(line) for line in subprocess.check_output([str(work / "parity")], input="\n".join(rows) + "\n", text=True).splitlines()]
    assert len(actual) == len(expected) == sum(len(value["samplesMs"]) for value in values)
    errors = [abs(a - b) for a, b in zip(actual, expected)]
    assert max(errors) <= 0.0001, max(errors)
    print(json.dumps({"status": "PASS", "profiles": len(values), "samples": len(actual), "maxPercentError": max(errors), "tolerancePercentPoints": 0.0001, "scope": "valid-time schedule evaluator parity only; no clock-fault policy, firmware output, GPIO or hardware proof"}))


if __name__ == "__main__":
    main()
