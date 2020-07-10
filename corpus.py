#!/usr/bin/env python3

import argparse
import os
import subprocess
import math
from tempfile import NamedTemporaryFile
from objects import *

def make_corpus_argparse(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('src_lang', help='language to translate from')
    parser.add_argument('trg_lang', help='language to translate to')
    parser.add_argument('-sp', '--source-path', help='path to directory of source analyzer')
    parser.add_argument('-tp', '--target-path', help='path to directory of target analyzer')
    parser.add_argument('-pp', '--pair-path', help='path to directory of bilingual data')
    parser.add_argument('-c', '--corpus', help='bilingual corpus file')
    parser.add_argument('-s', '--sl-corpus', help='source language corpus file')
    parser.add_argument('-t', '--tl-corpus', help='target language corpus file')
    parser.add_argument('-sep', '--separator', help='divider between source and target sentences if using a bilingual corpus (default |||)', default='|||')
    parser.add_argument('-a', '--aligner', help='what program to use for word-alignment', choices=['eflomal', 'biltrans'], default='eflomal')
    #parser.add_argument('-b', '--biltrans-suggestions', help='file to write possible bilingual dictionary entries to')
    parser.add_argument('-f', '--full-tags', action='append', help='align a part of speech based on full analysis rather than just lemma and first tag, e.g. -f prn')
    return parser

def tokenize(an_file, tok_file, full_tags):
    tok_to_id = {}
    id_to_tok = []
    sents = []
    an_file.seek(0)
    import numpy
    for line in an_file:
        cur = []
        for word in line.split('$'):
            if '^' not in word:
                continue
            an = word.split('^')[-1].split('/')[0]
            if '<' in an and an.split('<')[1][:-1] not in full_tags:
                an = word.split('>')[0] + '>'
            tid = tok_to_id.get(an, -1)
            if tid == -1:
                tok_to_id[an] = len(id_to_tok)
                id_to_tok.append(an)
            cur.append(tid)
        sents.append(numpy.asarray(cur, dtype=numpy.uint32))
    #tok_file.write('%d %d\n' % (len(sents), len(id_to_tok)))
    #for sn in sents:
    #    if len(sn) > 0x400:
    #        tok_file.write('0\n')
    #    else:
    #        tok_file.write(' '.join(str(n) for n in sn) + '\n')
    import eflomal
    eflomal.write_text(tok_file, tuple(sents), len(id_to_tok))
    return len(sents)

def eflomal_ize(sl_file, tl_file, full_tags):
    sl_nums = NamedTemporaryFile('wb+')
    tl_nums = NamedTemporaryFile('wb+')
    n = tokenize(sl_file, sl_nums, full_tags)
    tokenize(tl_file, tl_nums, full_tags)
    align = NamedTemporaryFile('w+')

    # I don't know what this is calculating, but it corresponds to the
    # default arguments in the eflomal python interface
    defaults = ['-m', '3', '-n', '1', '-N', '0.2']
    iters = max(2, int(round(5000.0 / math.sqrt(n))))
    iters4 = max(1, iters//4)
    defaults += ['-1', str(max(2, iters4)), '-2', str(iters4), '-3', str(iters)]

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

def biltrans_align(sl, tl):
    ret = {}
    # segment tl words into equivalence classes
    ls = list(range(len(tl.children)))
    sets = []
    while ls:
        n = ls.pop()
        eq = [n]
        neq = []
        for i in ls:
            if tl.children[i].equiv(tl.children[n]):
                eq.append(i)
            else:
                neq.append(i)
        ls = neq

    for st in sets:
        n = len(x for x in sl.iterchildren() if x.equiv(tl.children[st[0]]))
        possible = [(i, i) for i in st]
        if n < len(st):
            for s in st:
                tl.children[s].skippable = True
            possible.append((-1, -1))
        for i, ch in enumerate(sl.iterchildren()):
            if ch.equiv(tl.children[st[0]]):
                ch.possible = possible
                ret[i] = [x[0] for x in possible]
    return ret

def analyze(args, side, infilename, outfilename):
    using_mono = (not args.pair_path and (args.source_path or args.target_path))
    cmd = ['apertium', '-f', 'none']
    if args.pair_path:
        cmd += ['-d', args.pair_path]
    elif using_mono and side == 'source' and args.source_path:
        cmd += ['-d', args.source_path]
    elif using_mono and side == 'target' and args.target_path:
        cmd += ['-d', args.target_path]
    lang = (args.src_lang if side == 'source' else args.trg_lang)
    if not using_mono:
        lang += '-' + (args.trg_lang if side == 'source' else args.src_lang)
        if args.aligner == 'biltrans' and side == 'source':
            lang += '-biltrans'
        else:
            lang += '-pretransfer'
        subprocess.run(cmd + [lang, infilename, outfilename])
    else:
        lang += '-tagger'
        # TODO: what happens if someone does --aligner=biltrans with monolinguals?
        tmp = NamedTemporaryFile('w+')
        tmp.seek(0)
        subprocess.run(cmd + [lang, infilename, tmp.name])
        subprocess.run(['apertium-pretransfer', tmp.name, outfilename])

def get_corpus(args):
    sl_text = NamedTemporaryFile('w+')
    tl_text = NamedTemporaryFile('w+')
    sl_an = NamedTemporaryFile('w+')
    tl_an = NamedTemporaryFile('w+')
    if args.corpus:
        with open(args.corpus) as infile:
            for i, line in enumerate(infile):
                if not line.strip():
                    continue
                if line.count(args.separator) != 1:
                    # TODO: WARNING - skipping line i+1
                    continue
                sl, tl = line.split(args.separator)
                sl = sl.strip()
                tl = tl.strip()
                if not sl or not tl:
                    # TODO: WARNING - skipping line i+1
                    continue
                sl_text.write(sl + '\n')
                tl_text.write(tl + '\n')
    elif args.sl_corpus and args.tl_corpus:
        sl_lines = []
        tl_lines = []
        with open(args.sl_corpus) as infile:
            sl_lines = infile.readlines()
        with open(args.tl_corpus) as infile:
            tl_lines = infile.readlines()
        if len(sl_lines) != len(tl_lines):
            # TODO: WARNING - skipping some number of lines
            pass
        for i, (sl, tl) in enumerate(zip(sl_lines, tl_lines)):
            sl = sl.strip()
            tl = tl.strip()
            if not sl or not tl:
                # TODO: WARNING - skipping line i+1
                continue
            sl_text.write(sl + '\n')
            tl_text.write(tl + '\n')
    else:
        # TODO: ERROR - must supply sl&tl or bitext
        return
    sl_text.write('.\n')
    tl_text.write('.\n')
    sl_text.seek(0)
    tl_text.seek(0)

    # TODO: suggest bidix entries

    analyze(args, 'source', sl_text.name, sl_an.name)
    analyze(args, 'target', tl_text.name, tl_an.name)

    tl_lus = parse_file(tl_an)
    sl_lus = parse_file(sl_an)
    align = []
    if args.aligner == 'biltrans':
        for s, t in zip(sl_lus, tl_lus):
            align.append(biltrans_align(s, t))
    elif args.aligner == 'eflomal':
        align = eflomal_ize(sl_an, tl_an, args.full_tags or [])
        for tree, flat, alg in zip(sl_lus, tl_lus, align):
            tree.assign_alignment(alg)
            for i, w in enumerate(flat.children):
                if i not in alg.values():
                    w.skippable = True
    else:
        align = [None]*len(sl_lus)
    sens = []
    for sl, tl, alg in zip(sl_lus, tl_lus, align):
        sens.append(Sentence(sl, tl, alg))
    return Corpus(sens)
