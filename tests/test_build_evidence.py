#!/usr/bin/env python3
"""Command-specific capture tests; synthetic files are not real firmware."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('capture',ROOT/'tools/capture_isolated_build.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
SHA='a'*40

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.before=Path.cwd();os.chdir(self.temp.name);self.addCleanup(os.chdir,self.before)
        Path('include').mkdir()
        for name in ('ClockType.gen.h','version.gen.h','WebPageContent.gen.inc'):
            (Path('include')/name).write_text('synthetic generated fixture')
        Path('platformio.ini').write_text('[platformio]\n');Path('package-lock.json').write_text('{}')
        self.commands=[];self.package_error=False;self.bad_config=False;self.empty_packages=False
        self.configure(next(iter(c.MODES)))
    def configure(self,env):
        self.env=env;mode=c.MODES[env];build=Path('.pio/build')/env;build.mkdir(parents=True,exist_ok=True)
        for name in ('firmware.bin','firmware.elf','bootloader.bin','partitions.bin'):
            (build/name).write_bytes(b'synthetic firmware fixture')
        defines={'WORDCLOCK_TEST_MODE':mode,'WORDCLOCK_EXPECT_TEST_MODE':mode,
                 'WORDCLOCK_BOARD_YD_ESP32S3_N16R8':'1','BOARD_HAS_PSRAM':'1',
                 'WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL':'0','WORDCLOCK_ENABLE_ONBOARD_STATUS_LED':'1'}
        self.entry={'file':'src/WordClock.cpp','arguments':['g++']+['-D'+k+'='+v for k,v in defines.items()]}
        Path('compile_commands.json').write_text(json.dumps([self.entry]))
    def run_command(self,args,**kwargs):
        self.commands.append(args)
        pio=[sys.executable,'-m','platformio'];code=0;error=''
        if args==pio+['pkg','list','-e',self.env]:
            text='' if self.empty_packages else 'Platform espressif32 @ 6.9.0\nLibraries: RTClib @ 1.14.2\n'
            if self.package_error:code=2;error='fixture package failure'
        elif args==pio+['project','config','--json-output']:
            text='not-json' if self.bad_config else '[]'
        elif args==pio+['--version']:text='PlatformIO Core, version 6.1.18\n'
        elif args==['node','--version']:text='fixture-node\n'
        elif args==['npm','--version']:text='fixture-npm\n'
        else:raise AssertionError('Unsupported or unexpected report command: '+repr(args))
        return subprocess.CompletedProcess(args,code,stdout=text,stderr=error)
    def git_output(self,args,**kwargs):
        if args==['git','rev-parse','HEAD']:return SHA
        if args==['git','status','--porcelain']:return ''
        raise AssertionError(args)
    def invoke(self):
        with patch.object(c.subprocess,'run',side_effect=self.run_command),patch.object(c.subprocess,'check_output',side_effect=self.git_output),patch.object(sys,'argv',['capture',self.env]),patch.dict(os.environ,{'GITHUB_SHA':SHA}),patch('builtins.print'):
            c.main()
    def test_both_modes_capture_text_packages(self):
        for env in c.MODES:
            self.configure(env);self.invoke();dest=Path('build-evidence')/env
            data=json.loads((dest/'manifest.json').read_text())
            self.assertFalse(data['flash_ready']);self.assertEqual(data['commit'],SHA)
            self.assertEqual(data['test_mode'],int(c.MODES[env]));self.assertEqual(len(data['artifacts']),4)
            self.assertEqual(data['resolved_packages']['format'],'text')
            self.assertEqual(data['resolved_packages']['text'],(dest/'resolved-packages.txt').read_text())
            self.assertEqual(data['resolved_packages']['sha256'],c.record(dest/'resolved-packages.txt')['sha256'])
    def test_missing_binary_fails_closed(self):
        (Path('.pio/build')/self.env/'firmware.bin').unlink()
        with self.assertRaisesRegex(SystemExit,'Missing firmware.bin'):self.invoke()
    def test_conflicting_mode_fails_closed(self):
        self.entry['arguments'].append('-DWORDCLOCK_TEST_MODE=2')
        Path('compile_commands.json').write_text(json.dumps([self.entry]))
        with self.assertRaisesRegex(SystemExit,'Missing/conflicting compiled define'):self.invoke()
    def test_command_error_exposes_stderr(self):
        self.package_error=True
        with self.assertRaisesRegex(SystemExit,'fixture package failure'):self.invoke()
        dest=Path('build-evidence')/self.env
        self.assertEqual((dest/'resolved-packages.txt.stderr.txt').read_text(),'fixture package failure')
        self.assertFalse((dest/'manifest.json').exists())
    def test_invalid_config_json_fails_closed(self):
        self.bad_config=True
        with self.assertRaisesRegex(SystemExit,'Invalid JSON in'):self.invoke()
        self.assertFalse((Path('build-evidence')/self.env/'manifest.json').exists())
    def test_empty_package_report_fails_closed(self):
        self.empty_packages=True
        with self.assertRaisesRegex(SystemExit,'Empty installed-package report'):self.invoke()

if __name__=='__main__':unittest.main(argv=[sys.argv[0]])
