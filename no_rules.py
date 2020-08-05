#!/usr/bin/python3
from typing import List, Tuple, Optional
import subprocess, tempfile
from objects import *
import corpus

def list_possible_rules(corp: Corpus, prefix: str) -> Tuple[List[Rule], List[List[Tuple[Tuple[int, int], bool]]]]:
    constituents = []
    tag_pairs = set()
    for sen in corp.sens:
        align = sen.sl.possible_constituents(sen.tl)
        constituents.append(align)
        for alg in align:
            # get first tag of each
            # TODO: should this pay attention to --full-tags?
            tag_pairs.add((sen.sl.children[alg[0][0]].match_surface()[1][0],
                           sen.sl.children[alg[0][1]].match_surface()[1][0]))
    rules = [Rule(prefix + '_' + str(i), list(tg)) for i, tg in enumerate(tag_pairs)]
    return (rules, constituents)

def evaluate_rule(corp: Corpus, rl: Rule, constituents: List[List[Tuple[Tuple[int, int], bool]]]) -> Tuple[int, int]:
    '''check a proposed rule against a corpus
    return number of correct and incorrect applications'''
    good = 0
    bad = 0
    for sen, con in zip(corp.sens, constituents):
        ls = sen.sl.possible_applications(rl)
        for l in ls:
            for c in con:
                if l == c[0]:
                    good += 1
                    break
            else:
                bad += 1
    return (good, bad)

def add_rules(corp: Corpus, prefix: str) -> List[Rule]:
    rules, constituents = list_possible_rules(corp, prefix)
    rule_scores = [evaluate_rule(corp, r, constituents) for r in rules]
    rule_ls = list(zip(rules, rule_scores))
    rule_ls.sort(reverse=True, key=lambda x: x[1][0] + x[1][1])
    for r, s in rule_ls:
        print('%s\t%s' % (str(r), s))
    ret = []
    while rule_ls:
        todo = []
        cur = rule_ls[0][0]
        for rl, score in rule_ls[1:]:
            if score[0] + score[1] < (len(corp.sens) / 100.0):
                break
            if not cur.overlap(rl):
                todo.append((rl, score))
        ret.append(cur)
        rule_ls = todo
    return ret

if __name__ == '__main__':
    parser = corpus.make_corpus_argparse('build rules from corresponding word/phrase pairs')
    parser.add_argument('rtx_file', help='file to write generated rules to')
    args = parser.parse_args()
    corp = corpus.get_corpus(args)
    rls = []
    for i in range(10):
        rls += add_rules(corp, 'PHRASE_' + str(i))
        generate_rule_file(args.rtx_file, rls)
        corp.compile_and_retree(args.rtx_file)
