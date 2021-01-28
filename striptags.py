#!/usr/bin/env python3

import sys
surf = len(sys.argv) > 1
for line in sys.stdin:
    for lu_ in line.split('$'):
        if '^' not in lu_: continue
        lu = lu_.split('^')[-1]
        sec = lu
        if '/' in lu:
            sec = lu.split('/')[1 if surf else 0]
        if '><' in sec:
            sec = sec.split('><')[0] + '>'
        sec = sec.replace(' ', '_').lower()
        print(f'^{sec}$', end=' ')
    print('')
