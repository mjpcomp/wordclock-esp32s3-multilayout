#!/usr/bin/env python3
"""Compile the actual lifecycle module with mocked NVS; no device validation."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
NVS='#pragma once\n#include <stddef.h>\n#include <stdint.h>\ntypedef int32_t esp_err_t;\ntypedef uint32_t nvs_handle_t;\nenum nvs_open_mode_t {NVS_READONLY,NVS_READWRITE};\nconstexpr esp_err_t ESP_OK=0,ESP_FAIL=-1;\nconstexpr esp_err_t ESP_ERR_NVS_NOT_FOUND=0x1102,ESP_ERR_NVS_TYPE_MISMATCH=0x1103;\nesp_err_t nvs_open(const char*,nvs_open_mode_t,nvs_handle_t*);\nesp_err_t nvs_get_blob(nvs_handle_t,const char*,void*,size_t*);\nesp_err_t nvs_set_blob(nvs_handle_t,const char*,const void*,size_t);\nesp_err_t nvs_commit(nvs_handle_t);\nvoid nvs_close(nvs_handle_t);\n'
def main():
 compiler=shutil.which('g++')
 if not compiler:raise SystemExit('g++ is required')
 profiles=[('normal',0,[],False),('board',1,['-DESP32','-DCONFIG_IDF_TARGET_ESP32S3'],True),
  ('rtc',2,['-DESP32','-DCONFIG_IDF_TARGET_ESP32S3'],True),
  ('unsupported',1,['-DESP32'],False)]
 with tempfile.TemporaryDirectory() as folder:
  work=Path(folder)
  for name in ('ClockTestPolicy.h','OnboardIndicatorLifecycle.h'):
   shutil.copyfile(ROOT/'include'/name,work/name)
  (work/'LedStatusPrefix.h').write_text('#pragma once\n#define WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL 0\n')
  (work/'other.cpp').write_text('#include "OnboardIndicatorLifecycle.h"\nonboardIndicatorCommandService::Service* otherService(){return onboardIndicatorLifecycle::commandService();}\n')
  for name,mode,flags,supported in profiles:
   for mock in ('nvs.h','WordClockState.h'):(work/mock).unlink(missing_ok=True)
   if supported:
    (work/'nvs.h').write_text(NVS)
    (work/'WordClockState.h').write_text('#pragma once\nstruct TestGlobal {char timezone[30];};\nextern TestGlobal G;\n')
   module=work/'module.cpp';shutil.copyfile(ROOT/'src/OnboardIndicatorLifecycle.cpp',module)
   binary=work/name
   subprocess.run([compiler,'-std=c++11','-Wall','-Wextra','-Werror',
    '-fsanitize=undefined,bounds','-fno-sanitize-recover=all',
    '-DWORDCLOCK_TEST_MODE='+str(mode),'-DTEST_SUPPORTED='+str(int(supported)),
    '-Dgettimeofday=onboard_test_gettimeofday']+flags+
    ['-I'+str(work),'-I'+str(ROOT/'include'),str(module),
     str(ROOT/'tests/onboard_indicator_lifecycle_test.cpp'),str(work/'other.cpp'),'-o',str(binary)],check=True)
   for scenario in (['missing','always','disabled','scheduled','corrupt','io'] if supported else ['unsupported']):
    subprocess.run([str(binary),scenario],check=True)
 print('PASS: actual lifecycle module, isolated profiles, unsupported/normal no-op, read-only preparation, singleton, TZ readiness, faults and session deferral; NVS mocked.')
if __name__=='__main__':main()
