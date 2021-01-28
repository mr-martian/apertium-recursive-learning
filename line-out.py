#!/usr/bin/env python3

import sys
txt = sys.stdin.read().split('\0')
if len(sys.argv) == 2:
    print('\n'.join(txt))
else:
    for l in txt:
        print('^root<S>{%s}$' % l)
