#!/usr/bin/env python3
"""Host fault tests; fake NVS is not proof of target flash behavior."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
STUB = r'''#pragma once
#include <stddef.h>
#include <stdint.h>
typedef int32_t esp_err_t;
typedef uint32_t nvs_handle_t;
enum nvs_open_mode_t { NVS_READONLY, NVS_READWRITE };
constexpr esp_err_t ESP_OK = 0;
constexpr esp_err_t ESP_FAIL = -1;
constexpr esp_err_t ESP_ERR_NVS_NOT_FOUND = 0x1102;
constexpr esp_err_t ESP_ERR_NVS_TYPE_MISMATCH = 0x1103;
esp_err_t nvs_open(const char *, nvs_open_mode_t, nvs_handle_t *);
esp_err_t nvs_get_blob(nvs_handle_t, const char *, void *, size_t *);
esp_err_t nvs_set_blob(nvs_handle_t, const char *, const void *, size_t);
esp_err_t nvs_commit(nvs_handle_t);
void nvs_close(nvs_handle_t);
'''
def main():
    compiler = shutil.which('g++')
    if not compiler:
        raise SystemExit('g++ is required for schedule-storage host tests')
    with tempfile.TemporaryDirectory() as folder:
        temp = Path(folder)
        (temp / 'nvs.h').write_text(STUB)
        for name, defines in [('core', []), ('native-stub', ['-DESP32'])]:
            binary = temp / name
            subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror'] + defines +
                           ['-I', str(temp), '-I', str(ROOT / 'include'),
                            str(ROOT / 'tests/brightness_schedule_storage_test.cpp'),
                            '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
            print('PASS: schedule-storage ' + name)
if __name__ == '__main__':
    main()
