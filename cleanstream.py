#!/usr/bin/env python3

import sys
for line in sys.stdin:
    for lu_ in line.split('$'):
        if '^' not in lu_: continue
        lu = lu_.split('^')[-1]
        sec = lu
        if '/' in lu:
            sec = lu.split('/')[1]
        print(f'^{sec}/{sec}$', end=' ')
    print('')
