#!/usr/bin/env python3
"""Host regression for extracted renderer methods and real English adapters.
Run: python tests/test_english_renderer.py [checkout]
Scope: reset language defaults, LED4x, 1440 times per face. Not full firmware,
GPIO isolation, all persisted settings, or hardware. Mirc0 has a physical-index
oracle; other faces have word-request and minute-mask checks only.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
NAMES = ('determineWhichMinuteVariant showSpecialWordBeen '
         'checkIfClockHasMinuteInWordsAndItIsSet showMinuteInWords showMinute '
         'checkForValidLanguageVariant getFrontWordForNum checkTwentyUsage '
         'hasTwentyAndCheckForUsage hasDreiviertelAndCheckForUsage '
         'setMinute setHour isMidnight').split()
FACES = [('EN10x11.mirc0.hpp', 'Mirc0En10x11_t', 36),
         ('EN08x08.hpp', 'En08x08_t', 3), ('EN10x11.hpp', 'En10x11_t', 4),
         ('EN11x12.hpp', 'En11x12_t', 5)]
SPEC = [('uhr',), ('min_5','nach'), ('min_10','nach'), ('viertel','v_nach'),
        ('min_20','nach'), ('min_25','nach'), ('halb','nach'), ('min_25','vor'),
        ('min_20','vor'), ('viertel','v_vor'), ('min_10','vor'), ('min_5','vor')]
RANGES = {'es_ist':[0,1,3,4], 'uhr':list(range(99,105)),
          'min_5':list(range(28,32)), 'min_10':list(range(36,39)),
          'min_20':list(range(22,28)), 'min_25':list(range(22,32)),
          'viertel':list(range(13,20)), 'halb':list(range(40,44)),
          'nach':list(range(44,48)), 'v_nach':list(range(44,48)),
          'vor':[33,34], 'v_vor':[33,34]}
for h, start, count in [(1,63,3),(2,74,3),(3,55,5),(4,66,4),(5,70,4),(6,60,3),
                        (7,88,5),(8,83,5),(9,51,4),(10,107,3),(11,77,6),(12,93,6)]:
    RANGES['hour_'+str(h)] = list(range(start,start+count))
PRE = r"""
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>
#include <algorithm>
uint32_t frontMatrix[22]={};
enum class BuildTypeDef{Normal,DoubleResM1};
enum class MinuteVariant{Off,LED4x,LED7x,Corners,InWords};
enum{FlipHorzVert,MeanderRows,ExtraLedPerRow};
enum{ItIs15,ItIs20,ItIs40,ItIs45,EN_ShowAQuarter};
// Distinct mock IDs match the real registry wherever this test selects a face.
enum{Eng08x08=3,Eng10x11=4,Es08x08Cuarto=6,Es10x11=7,Fr10x11=8,
     It10x11=10,Ro10x11=11,Ru10x11=12,Tr10x11=34};
struct{void println(const char*){};void printf(const char*,...){};}Serial;
struct{int clockTypeDef=36;bool languageVariant[5]={};bool layoutVariant[6]={};
BuildTypeDef buildTypeDef=BuildTypeDef::Normal;MinuteVariant minuteVariant=MinuteVariant::LED4x;}G;
"""
POST = r"""
std::vector<FrontWord> requested;
template<class Base>struct Recording:Base{
 unsigned depth=0;
 void show(FrontWord w)override{if(depth++==0)requested.push_back(w);Base::show(w);--depth;}
};
ClockType*usedClockType=nullptr;
uint16_t minutePixelArray[4]={};uint8_t minuteArray=0;
"""
MAIN = r"""
int main(){Recording<FACE> face;usedClockType=&face;G.clockTypeDef=LAYOUT;
G.layoutVariant[MeanderRows]=true;ClockWork clock;clock.checkForValidLanguageVariant();
for(int h=0;h<24;++h)for(int m=0;m<60;++m){
 requested.clear();std::memset(frontMatrix,0,sizeof(frontMatrix));uint8_t offset=0;bool full=false;
 clock.setMinute(m,offset,full);clock.setHour(h+offset,full);face.show(FrontWord::es_ist);
 std::cout<<h<<":"<<m<<":"<<int(minuteArray)<<":";
 std::sort(requested.begin(),requested.end());for(auto w:requested)std::cout<<int(w)<<",";
 std::cout<<":";
 for(unsigned r=0;r<face.rowsWordMatrix();++r)for(unsigned c=0;c<face.colsWordMatrix();++c)
  if(face.getFrontMatrixPixel(r,c))std::cout<<face.getFrontMatrixIndex(r,c)<<",";
 for(unsigned i=0;i<4;++i)if(minuteArray&(1U<<i))std::cout<<minutePixelArray[i]<<",";
 std::cout<<"\n";
}}
"""

def extract(text, name):
    match = re.search(r'^(?:void|bool|uint8_t|FrontWord) ClockWork::'+name+r'\([^)]*\)\s*\{', text, re.M)
    assert match, name
    pos, depth = match.end(), 1
    while depth:
        if text[pos] == '{': depth += 1
        elif text[pos] == '}': depth -= 1
        pos += 1
    return text[match.start():pos]

def main():
    src = (ROOT/'include/ClockWork.hpp').read_text()
    ct = (ROOT/'include/WordClockTypes/ClockType.hpp').read_text()
    words = [w.strip() for w in re.search(r'enum class FrontWord\s*\{(.*?)\};',ct,re.S).group(1).split(',') if w.strip()]
    values = {w:i for i,w in enumerate(words)}
    methods = [extract(src,n) for n in NAMES]
    declarations = '\n'.join(m[:m.index('{')].replace('ClockWork::','').strip()+';' for m in methods)
    total = 0
    for filename, cls, layout in FACES:
        code = PRE+'\n#include "'+filename+'"\n'+POST
        code += 'class ClockWork{public:\n'+declarations+'\n};\n'+'\n'.join(methods)
        code += MAIN.replace('FACE',cls).replace('LAYOUT',str(layout))
        with tempfile.TemporaryDirectory() as folder:
            cpp, exe = Path(folder)/'test.cpp', Path(folder)/'test'
            cpp.write_text(code)
            subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror',
                            '-Wno-unused-parameter','-fsanitize=undefined,bounds',
                            '-fno-sanitize-recover=all','-I'+str(ROOT/'include/WordClockTypes'),
                            str(cpp),'-o',str(exe)],check=True)
            lines = subprocess.check_output([str(exe)],text=True).splitlines()
        assert len(lines) == 1440
        failures = []
        for ix, line in enumerate(lines):
            hs, ms, dots, ws, ps = line.split(':'); h,m = int(hs),int(ms)
            assert (h,m) == divmod(ix,60)
            names = list(SPEC[m//5])+['hour_'+str(((h+(m>=35))%12) or 12),'es_ist']
            expected = sorted(values[n] for n in names)
            actual = [int(v) for v in ws.split(',') if v]
            expected_dots = ((1<<(m%5-1)) if m%5 else 0) if layout==5 else (1<<(m%5))-1
            bad = actual!=expected or int(dots)!=expected_dots
            if layout == 36:
                pixels = {int(v) for v in ps.split(',') if v}
                expected_pixels = set(sum((RANGES[n] for n in names),[]))|set(range(110,110+m%5))
                bad |= pixels != expected_pixels
            if bad: failures.append(f'{h:02}:{m:02}')
        print(f'{filename}: {1440-len(failures)}/1440 passed; first failures: {failures[:5]}')
        total += len(failures)
    if total: raise SystemExit(f'FAIL: {total}/5760 layout/time cases')
    print('PASS: 5760 cases, including 1440 independent Mirc0 physical masks.')

if __name__ == '__main__':
    main()
