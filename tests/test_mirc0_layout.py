#!/usr/bin/env python3
"""Host-check visual letters and physical indices, not the full firmware."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WORDS = {'IT_IS': [0, 1, 3, 4], 'OCLOCK': [99, 100, 101, 102, 103, 104], 'FIVE': [28, 29, 30, 31], 'TEN': [36, 37, 38], 'TWENTY': [22, 23, 24, 25, 26, 27], 'QUARTER': [13, 14, 15, 16, 17, 18, 19], 'HALF': [40, 41, 42, 43], 'PAST': [44, 45, 46, 47], 'TO': [33, 34], 'ONE': [63, 64, 65], 'TWO': [74, 75, 76], 'THREE': [55, 56, 57, 58, 59], 'FOUR': [66, 67, 68, 69], 'FIVE_H': [70, 71, 72, 73], 'SIX': [60, 61, 62], 'SEVEN': [88, 89, 90, 91, 92], 'EIGHT': [83, 84, 85, 86, 87], 'NINE': [51, 52, 53, 54], 'TEN_H': [107, 108, 109], 'ELEVEN': [77, 78, 79, 80, 81, 82], 'TWELVE': [93, 94, 95, 96, 97, 98]}
HOURS = ['TWELVE','ONE','TWO','THREE','FOUR','FIVE_H','SIX','SEVEN','EIGHT','NINE','TEN_H','ELEVEN']
MINUTES = {0:['OCLOCK'],5:['FIVE','PAST'],10:['TEN','PAST'],15:['QUARTER','PAST'],
           20:['TWENTY','PAST'],25:['TWENTY','FIVE','PAST'],30:['HALF','PAST'],
           35:['TWENTY','FIVE','TO'],40:['TWENTY','TO'],45:['QUARTER','TO'],
           50:['TEN','TO'],55:['FIVE','TO']}

def main():
    compiler = shutil.which('g++')
    if not compiler:
        raise SystemExit('g++ is required for this host test.')
    with tempfile.TemporaryDirectory() as folder:
        executable = Path(folder) / 'layout-test'
        subprocess.run([compiler,'-std=c++11','-Wall','-Wextra','-Werror',
                        '-Wno-unused-parameter','-fsanitize=undefined,bounds',
                        '-I'+str(ROOT/'include/WordClockTypes'),
                        str(ROOT/'tests/test_mirc0_layout.cpp'),'-o',str(executable)],check=True)
        lines = subprocess.check_output([str(executable)],text=True).splitlines()
    assert len(lines) == 1440
    for number, line in enumerate(lines):
        h, m, pixels = line.split(':'); h=int(h); m=int(m)
        assert h == number//60 and m == number%60
        rounded = m//5*5
        names = ['IT_IS', HOURS[(h+(rounded>=35))%12]] + MINUTES[rounded]
        expected = set(sum((WORDS[name] for name in names),[])) | set(range(110,110+m%5))
        actual = {int(value) for value in pixels.split(',') if value}
        assert actual == expected, (h,m,sorted(actual),sorted(expected))
    print('PASS: visual letters, 1440 serpentine masks, minute dots and capabilities.')

if __name__ == '__main__':
    main()
