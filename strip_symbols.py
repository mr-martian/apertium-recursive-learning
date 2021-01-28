#!/usr/bin/env python3

import sys
while True:
    line = sys.stdin.readline()
    if not line.strip():
        sys.stdout.write(line)
        break
    ls = line.split('\t')
    if len(ls) < 3:
        sys.stdout.write(line)
        continue
    if not ls[2] or ls[2][0] not in '+<':
        ls[2] = '@0@'
    if not ls[3] or ls[3][0] not in '+<':
        ls[3] = '@0@'
    sys.stdout.write('\t'.join(ls))
