#!/usr/bin/env python3
"""Collect build provenance, never declare hardware/flash readiness."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys

MODES={'YD_ESP32S3_N16R8_BOARD_ONLY':'1','YD_ESP32S3_N16R8_RTC_ONLY':'2'}

def definitions(entry):
    args=entry.get('arguments') or shlex.split(entry['command'])
    result={};i=0
    while i<len(args):
        token=args[i]
        if token=='-D':
            i+=1;value=args[i]
        elif token.startswith('-D'):value=token[2:]
        else:i+=1;continue
        name,sep,value=value.partition('=')
        result.setdefault(name,[]).append(value if sep else '1');i+=1
    return result

def record(path):
    data=path.read_bytes()
    return {'name':path.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def collect_command(dest,name,args):
    run=subprocess.run(args,capture_output=True,text=True)
    (dest/name).write_text(run.stdout,encoding='utf-8')
    error_file=dest/(name+'.stderr.txt')
    error_file.write_text(run.stderr,encoding='utf-8')
    if run.returncode:
        detail=run.stderr.strip() or run.stdout.strip() or '(no diagnostic output)'
        raise SystemExit(f'Report command failed ({run.returncode}): {shlex.join(args)}\n{detail}\nSaved output: {dest/name}; stderr: {error_file}')
    return run.stdout

def collect_json(dest,name,args):
    text=collect_command(dest,name,args)
    try:return json.loads(text)
    except json.JSONDecodeError as error:
        raise SystemExit(f'Invalid JSON in {dest/name}: {error}') from error

def main():
    parser=argparse.ArgumentParser();parser.add_argument('environment',choices=MODES)
    env=parser.parse_args().environment;dest=Path('build-evidence')/env;dest.mkdir(parents=True,exist_ok=True)
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if os.environ.get('GITHUB_SHA',sha)!=sha:raise SystemExit('Checkout SHA mismatch')
    entries=json.loads(Path('compile_commands.json').read_text())
    main_entries=[e for e in entries if e['file'].replace(chr(92),'/').endswith('src/WordClock.cpp')]
    if not main_entries:raise SystemExit('No WordClock compile command')
    expected={'WORDCLOCK_TEST_MODE':MODES[env],'WORDCLOCK_EXPECT_TEST_MODE':MODES[env],
              'WORDCLOCK_BOARD_YD_ESP32S3_N16R8':'1','BOARD_HAS_PSRAM':'1',
              'WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL':'0','WORDCLOCK_ENABLE_ONBOARD_STATUS_LED':'1'}
    for entry in main_entries:
        actual=definitions(entry)
        for key,value in expected.items():
            if actual.get(key)!=[value]:raise SystemExit('Missing/conflicting compiled define: '+key)
    build=Path('.pio/build')/env;artifacts=[]
    for name in ('firmware.bin','firmware.elf','bootloader.bin','partitions.bin'):
        source=build/name
        if not source.exists():
            if name in ('firmware.bin','firmware.elf'):raise SystemExit('Missing '+name)
            continue
        if source.stat().st_size==0:raise SystemExit('Empty '+name)
        shutil.copyfile(source,dest/name);artifacts.append(record(dest/name))
    shutil.copyfile('compile_commands.json',dest/'compile_commands.json')
    pio=[sys.executable,'-m','platformio']
    package_args=pio+['pkg','list','-e',env]
    package_text=collect_command(dest,'resolved-packages.txt',package_args)
    if not package_text.strip():raise SystemExit('Empty installed-package report')
    packages={'format':'text','command':package_args,'report_file':'resolved-packages.txt',
              'sha256':record(dest/'resolved-packages.txt')['sha256'],'text':package_text}
    config=collect_json(dest,'project-config.json',pio+['project','config','--json-output'])
    versions={}
    for name,args in {'platformio':pio+['--version'],'node':['node','--version'],'npm':['npm','--version']}.items():
        versions[name]=collect_command(dest,name+'-version.txt',args).strip()
    versions['python']=sys.version
    generated=[]
    for name in ('ClockType.gen.h','version.gen.h','WebPageContent.gen.inc'):
        source=Path('include')/name
        if not source.is_file() or source.stat().st_size==0:raise SystemExit('Missing generated source: '+name)
        generated.append(record(source))
    report={'commit':sha,'environment':env,'test_mode':int(MODES[env]),'verified_main_defines':expected,
            'flash_ready':False,'validation':'Build only; hardware, GPIO48 diagnostics and UI/time validation still pending',
            'versions':versions,'resolved_packages':packages,'project_config':config,
            'generated_sources':generated,'artifacts':artifacts,
            'input_files':[record(Path('platformio.ini')),record(Path('package-lock.json'))],
            'working_tree_status':subprocess.check_output(['git','status','--porcelain'],text=True)}
    (dest/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Captured build evidence for '+env+'; NOT flash-ready')

if __name__=='__main__':main()
