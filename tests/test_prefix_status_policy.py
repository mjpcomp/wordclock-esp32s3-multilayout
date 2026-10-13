#!/usr/bin/env python3
"""Host-check pure prefix status policy/cache, not the full runtime firmware."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TEST = r"""#include "PrefixStatusPolicy.h"
#include <cassert>
#include <limits>
using namespace prefixStatus;
static bool same(Color a, Color b) { return !(a != b); }
int main() {
    assert(same(choose({false,false,false,false},0), {0,0,4}));
    assert(same(choose({false,false,false,false},500), {0,0,24}));
    assert(same(choose({true,false,true,true},0), {32,0,0}));
    assert(same(choose({true,true,false,true},0), {32,6,0}));
    assert(same(choose({false,true,true,true},0), {16,10,0}));
    assert(same(choose({true,true,true,false},0), {0,12,20}));
    assert(same(choose({true,true,true,true},0), {0,20,0}));
    assert(same(scale({20,10,4},0), {0,0,0}));
    assert(same(scale({20,10,4},0.5f), {10,5,2}));
    assert(same(scale({20,10,4},2), {20,10,4}));
    assert(same(scale({20,10,4},std::numeric_limits<float>::quiet_NaN()), {0,0,0}));
    OutputCache cache;
    int first=0,second=0;
    Color green={0,20,0};
    assert(!cache.due(0,nullptr));
    assert(cache.due(0,&first) && cache.changed(green));
    cache.sent(green);
    assert(!cache.changed(green));
    assert(!cache.due(249,&first));
    assert(cache.due(250,&first));
    assert(cache.changed({32,0,0}));
    assert(cache.due(251,&second) && cache.changed(green));
    cache.sent(green);
    cache.reset(); // Also handles recreation at the same pointer address.
    assert(cache.due(252,&second) && cache.changed(green));
    cache.reset();
    assert(cache.due(UINT32_MAX-100,&first));
    assert(!cache.due(50,&first));
    assert(cache.due(200,&first));
}
"""

def main():
    compiler = shutil.which('g++')
    if not compiler:
        raise SystemExit('g++ is required.')
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        source = work / 'test.cpp'
        source.write_text(TEST)
        executable = work / 'test'
        subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined,bounds', '-I' + str(ROOT / 'include'),
                        str(source), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
    print('PASS: status priority/colors, pulse, brightness, null driver, cache, reset and millis wrap.')

if __name__ == '__main__':
    main()
