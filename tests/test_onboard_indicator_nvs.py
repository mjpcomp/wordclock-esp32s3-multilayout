#!/usr/bin/env python3
"""Host adapter fault tests; SDK-shaped stub is not target flash validation."""
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
constexpr esp_err_t ESP_ERR_NVS_NOT_INITIALIZED = 0x1101;
constexpr esp_err_t ESP_ERR_NVS_NOT_FOUND = 0x1102;
constexpr esp_err_t ESP_ERR_NVS_TYPE_MISMATCH = 0x1103;
constexpr esp_err_t ESP_ERR_NVS_INVALID_LENGTH = 0x110c;
esp_err_t nvs_open(const char *, nvs_open_mode_t, nvs_handle_t *);
esp_err_t nvs_get_blob(nvs_handle_t, const char *, void *, size_t *);
esp_err_t nvs_set_blob(nvs_handle_t, const char *, const void *, size_t);
esp_err_t nvs_commit(nvs_handle_t);
void nvs_close(nvs_handle_t);
'''
def main():
    compiler = shutil.which('g++')
    if not compiler:
        raise SystemExit('g++ is required')
    with tempfile.TemporaryDirectory() as folder:
        temp = Path(folder)
        for name, defines in [('portable', []), ('nvs-stub', ['-DESP32'])]:
            if defines:
                (temp / 'nvs.h').write_text(STUB)
            binary = temp / name
            subprocess.run([compiler, '-std=c++11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all'] + defines +
                           ['-I', str(temp), '-I', str(ROOT / 'include'),
                            str(ROOT / 'tests/onboard_indicator_nvs_test.cpp'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
            print('PASS: onboard-indicator ' + name)
if __name__ == '__main__':
    main()
