#!/usr/bin/env python3

import numpy
import eflomal
from tempfile import NamedTemporaryFile
import subprocess
from typing import List, Tuple, Dict
import math

def run_eflomal(sents: List[Tuple[List[int], List[int]]]) -> List[Dict[int, int]]:
    sl_nums = NamedTemporaryFile('wb+')
    sl = tuple([numpy.asarray(x[0], dtype=numpy.uint32) for x in sents])
    eflomal.write_text(sl_nums, sl, max(map(lambda x: max(x[0]), sents)))
    tl_nums = NamedTemporaryFile('wb+')
    tl = tuple([numpy.asarray(x[1], dtype=numpy.uint32) for x in sents])
    eflomal.write_text(tl_nums, tl, max(map(lambda x: max(x[1]), sents)))

    # I don't know what this is calculating, but it corresponds to the
    # default arguments in the eflomal python interface
    defaults = ['-m', '3', '-n', '1', '-N', '0.2']
    iters = max(2, int(round(5000.0 / math.sqrt(len(sents)))))
    iters4 = max(1, iters//4)
    defaults += ['-1', str(max(2, iters4)), '-2', str(iters4), '-3', str(iters)]

    align = NamedTemporaryFile('w+')
    subprocess.run(['eflomal', '-s', sl_nums.name, '-t', tl_nums.name,
                    '-f', align.name, '-q'] + defaults)
    align.seek(0)
    ret = []
    for line in align:
        dct = {}
        for nums in line.split():
            sl, tl = nums.split('-')
            dct[int(sl)] = [int(tl)]
        ret.append(dct)
    return ret

