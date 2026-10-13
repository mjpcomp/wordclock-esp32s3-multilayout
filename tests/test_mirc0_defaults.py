#!/usr/bin/env python3
"""Host-check current registry/default headers and UI label; not full firmware."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TEST = r"""#include "WordClockState.h"
#include "Config.h"
#include <cassert>
#ifndef EXPECT_LED
#define EXPECT_LED 3
#define EXPECT_SDA 255
#define EXPECT_SCL 255
#endif
int main() {
 static_assert(Eng10x11Mirc0==36 && ClockTypeDefMax==37,"Mirc0 ID/max");
 static_assert(DEFAULT_LAYOUT==Eng10x11Mirc0,"Mirc0 default");
 static_assert(LED_PIN==EXPECT_LED && SDA_PIN_ESP32==EXPECT_SDA && SCL_PIN_ESP32==EXPECT_SCL,"board pins");
 static_assert(POWER_BUTTON_PIN==255 && MODE_BUTTON_PIN==255 && SPEED_BUTTON_PIN==255,"buttons opt in");
 static_assert(SERNR==440,"do not reset EEPROM");
 const unsigned ids[]={BN9x8,Ch10x11,Ch10x11V2,Eng08x08,Eng10x11,Eng11x12,
 Es08x08Cuarto,Es10x11,Fr10x11,Ger08x08,Ger08x08Viertel,Ger10x11,
 Ger10x11Alternative,Ger10x11AlternativeFrame,Ger10x11bayerisch,Ger10x11Clock,
 Ger10x11Mrrioes,Ger10x11Nero,Ger10x11NeroFrame,Ger10x11schwaebisch,
 Ger11x11,Ger11x11schwaebisch,Ger11x11V2,Ger11x11V3,Ger13x13,Ger16x8,
 Ger16x18,Ger22x11Weather,Hu10x10,It10x11,Nl10x11,Ro10x11,Ru10x11,Se10x11,Tr10x11,Ch10x11ZH};
 for(unsigned i=0;i<36;++i)assert(ids[i]==i);
 for(unsigned i=0;i<=36;++i)assert(isValidClockTypeDef(i));
 assert(!isValidClockTypeDef(37));assert(!isValidClockTypeDef(255));
}
"""
JS_TEST = r"""const fs=require("fs"), vm=require("vm"), assert=require("assert");
let options;
const context={console,TRANSLATION_DE_DE:{},TRANSLATION_NL:{},TRANSLATION_IT:{},TRANSLATION_ES:{},TRANSLATION_HU:{},TRANSLATION_RU:{},window:{i18nextBrowserLanguageDetector:{}},isLocalEnvironment:()=>false,
 i18next:{use(){},init(o){options=o;},on(){}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],"utf8"),context);
vm.runInContext(fs.readFileSync(process.argv[2],"utf8"),context);
assert.deepStrictEqual(Array.from(options.detection.order),["querystring","cookie"]);
assert.deepStrictEqual(Array.from(options.fallbackLng),["en"]);
assert.strictEqual(options.resources.en.translation.view.front["en-10-11-mirc0"],"English 10 x 11 (Mirc0.)");
"""

def main():
    compiler = shutil.which('g++')
    if not compiler:
        raise SystemExit('g++ is required.')
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        for name in ('WordClockState.h', 'Config.h'):
            shutil.copyfile(ROOT / 'include' / name, work / name)
        (work / 'Arduino.h').write_text('#pragma once\n#include <stdint.h>\n')
        (work / 'NeoPixelBus.h').write_text('#pragma once\nstruct HsbColor { float H,S,B; };\n')
        (work / 'version.gen.h').write_text('#define VERSION "host"\n')
        (work / 'test.cpp').write_text(TEST)
        for target in (False, True):
            executable = work / ('test-' + str(target))
            args = [compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=undefined,bounds', '-I' + str(work),
                    str(work / 'test.cpp'), '-o', str(executable)]
            if target:
                args[1:1] = ['-DWORDCLOCK_BOARD_YD_ESP32S3_N16R8=1',
                             '-DEXPECT_LED=5', '-DEXPECT_SDA=8', '-DEXPECT_SCL=9']
            subprocess.run(args, check=True)
            subprocess.run([str(executable)], check=True)
        config = (ROOT / 'include' / 'Config.h').read_text()
        assert len(re.findall(r'^#define DEFAULT_LAYOUT\b', config, re.M)) == 1
        node = shutil.which('node')
        if node:
            english = next(p for p in (ROOT / 'webpage' / 'language').glob('*.js')
                           if 'TRANSLATION_EN_US' in p.read_text())
            ui = ROOT / 'webpage' / 'i18n.js'
            subprocess.run([node, '--check', str(ui)], check=True)
            subprocess.run([node, '-e', JS_TEST, str(english), str(ui)], check=True)
        else:
            print('SKIP: Node unavailable; JavaScript syntax/config checks not run.')
    print('PASS: registry IDs/validation, Mirc0 default, profile GPIOs, buttons disabled and EEPROM signature.')

if __name__ == '__main__':
    main()
