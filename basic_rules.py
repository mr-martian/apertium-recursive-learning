#!/usr/bin/python3
from typing import List, Tuple, Optional
import subprocess, tempfile, itertools

class Attribute:
    all_attrs = {}
    def __init__(self, name: str, values: List[str]):
        self.name = name
        self.values = values
        Attribute.all_attrs[name] = self
    def __str__(self):
        return '%s = %s;' % (self.name, ' '.join(self.values))

class Pattern:
    all_patterns = {}
    def __init__(self, pos_tag):
        self.pos_tag = pos_tag
        self.tags = []
        # TODO: conditionals (i.e. <vblex><pres><p1><sg> vs <vblex><inf>)
        Pattern.all_patterns[pos_tag] = self
    def __str__(self):
        tg = '.'.join(self.tags)
        if tg:
            tg = '.' + tg
        return f'{self.pos_tag}: _{tg};'

class InputNode:
    def __init__(self, tags: Optional[List[str]],
                       clips: Optional[List[str]] = None):
        self.tags = tags
        self.clips = clips or []
    def __str__(self):
        return '.'.join(self.tags + ['$' + c for c in self.clips])

class OutputNode:
    def __init__(self, source: int, clips: List[Tuple[int, str]]):
        self.source = source
        self.clips = clips
        self.value = ''
    def __str__(self):
        args = []
        for name, src in self.clips:
            if src == 0:
                args.append(f'{name}=${name}')
            else:
                args.append(f'{name}={src}.{name}')
        s = ', '.join(args)
        if s:
            s = '[' + s + ']'
        return f'{self.source}{s}'

class Rule:
    all_rules = {}
    def __init__(self, parent: str, children: List[str]):
        self.parent = parent
        self.inputs = [InputNode([tag]) for tag in children]
        self.outputs = [OutputNode(i+1, []) for i in range(len(self.inputs))]
        self.instances = []
        self.name = (parent + '_' + '_'.join(children)).lower()
        Rule.all_rules[self.name] = self
    def __str__(self):
        ins = ' '.join(map(str, self.inputs))
        outs = ' _ '.join(map(str, self.outputs))
        return '%s -> %s [$lem=%s] { %s } ;' % (self.parent, ins, self.name, outs)
        # TODO: don't want [$lem] in final output

class LU:
    def __init__(self, slem: str, stags: List[str], tlem: str, ttags: List[str], children):
        self.slem = slem
        self.stags = stags if stags != [''] else []
        self.tlem = tlem
        self.ttags = ttags if ttags != [''] else []
        self.children = children
        self.skippable = False
        self.reorder = None # data type?
        self.tag_gain = [] # data type?
                                # [ ( self_align [ ( align, child) ] ) ]
        self.children_possible: List[Tuple[Tuple[int, int], List[Tuple[Tuple[int, int], int]]]] = []
        self.possible: List[Tuple[int, int]] = []
        self.idx = []
        if self.tlem in Rule.all_rules:
            Rule.all_rules[self.tlem].instances.append(self)
    def __str__(self):
        sl = self.slem + ''.join('<%s>' % x for x in self.stags)
        tl = self.tlem + ''.join('<%s>' % x for x in self.ttags)
        if sl and tl:
            sl += '/'
        return '^%s%s{ %s }%s$' % (sl, tl, ' '.join(map(str, self.children)), self.possible)
    def equiv(self, other):
        if self.tlem != other.tlem:
            return False
        if self.ttags == [] and other.ttags == []:
            return True
        if self.ttags and other.ttags and self.ttags[0] == other.ttags[0]:
            return True
        return False
    def align(self, words: List["LU"]):
        ret = []
        if len(self.children) == 0:
            for i, w in enumerate(words):
                if self.equiv(w):
                    ret.append((i, i))
            if not ret:
                ret.append((-1,-1))
        else:
            ops = []
            for i, ch in enumerate(self.children):
                ls = [(a,i) for a in ch.align(words)]
                if ls or len(ch.children) > 0:
                    ops.append(ls)
            for op in itertools.product(*ops):
                ls = list(op)
                ls.sort()
                for i in range(len(ls)-1):
                    l = ls[i][0][1]
                    r = ls[i+1][0][0]
                    if l == -1:
                        continue
                    if not all(x.skippable for x in words[l+1:r]):
                        break
                else:
                    ls2 = [l for l in ls if l[0][0] != -1]
                    ap = None
                    if ls2:
                        ap = (ls2[0][0][0], ls2[-1][0][1])
                    else:
                        ap = (-1, -1)
                    if ap not in ret:
                        ret.append(ap)
                    self.children_possible.append((ret[-1], ls))
        self.possible = ret
        return ret
    def filter_align(self, ok):
        pos = [x for x in self.possible if x in ok]
        self.possible = []
        # this loop makes us prefer narrower alignments
        for p in pos:
            for q in pos:
                if p[0] <= q[0] and p[1] >= q[1] and p != q:
                    break
            else:
                self.possible.append(p)
        self.children_possible = [x for x in self.children_possible if x[0] in self.possible]
        for i, ch in enumerate(self.children):
            pos = []
            for cp in self.children_possible:
                for op in cp[1]:
                    if op[1] == i and op[0] not in pos:
                        pos.append(op[0])
            ch.filter_align(pos)
        if len(self.possible) > 1:
            print(self)
    def iterchildren(self):
        if len(self.children) == 0:
            yield self
        else:
            for ch in self.children:
                yield from ch.iterchildren()
    def suggest_rules(self, idx, words):
        self.idx = idx
        for i, ch in enumerate(self.children):
            ch.suggest_rules(idx + [i], words)
        if not self.children:
            return
        if not self.stags and not self.ttags:
            return
        pos_tag = (self.stags + self.ttags)[0]
        child_tags = [(x.stags + x.ttags or [''])[0] for x in self.children]
        # TODO:
        # - compute reordering
        # -- need to deal with what level to put inserted words on
        # --- maybe try all and rely on majority
        # --- or at highest node?
        # --- initial insertion hard to track
        # - pass to Rule
        # - Rule handles suggestions
        # -- Rule with 0 suggestions -> warning, use input order
        # -- Rule with 1 distinct suggestion -> done
        # -- Rule with >1 suggestions
        # --- maybe try to resolve? - possibly too complicated
        # --- emit warning about conflicting sentences and go with majority?
        # -------------
        # - encode rule id (output-intput joined with _?) in node lemma
        # - align() attaches the node to the corresponding rule
        # - loop back and forth between trees and rules
        # -- if a rule can be selected, delete conflicting alignments
        # --- what about gridlock?
        # ---- alert user and just go with majority?

def read_rules(fname):
    f = open(fname)
    rules = f.read().splitlines()
    f.close()
    pos_tags = set()
    for rule in rules:
        l, r = rule.split(' -> ')
        rl = r.split()
        pos_tags.add(l)
        pos_tags.update(rl)
        Rule(l, rl)
    for tag in pos_tags:
        Pattern(tag)

def generate_file(fname):
    f = open(fname, 'w')
    for name, attr in sorted(Attribute.all_attrs.items()):
        f.write(str(attr) + '\n')
    f.write('\n\n')
    for name, pat in sorted(Pattern.all_patterns.items()):
        f.write(str(pat) + '\n')
    f.write('\n\n')
    for name, rule in sorted(Rule.all_rules.items()):
        f.write(str(rule) + '\n\n')
    f.close()

def get_trees(rulefile, datafile):
    binfile = tempfile.NamedTemporaryFile()
    treefile = tempfile.NamedTemporaryFile(mode='w+')
    subprocess.run(['rtx-comp', rulefile, binfile.name])
    subprocess.run(['rtx-proc', '-T', '-m', 'flat', binfile.name, datafile, treefile.name])
    treefile.seek(0)
    return treefile.read().splitlines()

def parse_tree(line):
    assert(line[0] == '^')
    assert(line[-1] == '$')
    loc = line.find('{')
    children = []
    label = line[1:loc]
    if loc != -1:
        sub = line[loc:-2]
        n = 0
        l = 0
        for i, c in enumerate(sub):
            if c == '^':
                if n == 0:
                    l = i
                n += 1
            elif c == '$':
                n -= 1
                if n == 0:
                    children.append(parse_tree(sub[l:i+1]))
    ls = label.split('/')
    sl = ''
    tl = ''
    if len(ls) == 1:
        tl = ls[0]
    else:
        sl = ls[0]
        tl = ls[1]
    slem, stags = sl.split('<', 1) if '<' in sl else (sl, '')
    tlem, ttags = tl.split('<', 1) if '<' in tl else (tl, '')
    return LU(slem.lower(), stags.strip('<>').split('><'),
              tlem.lower(), ttags.strip('<>').split('><'),
              children)

def align_corpus(trees, lexfile):
    f = open(lexfile)
    lexlines = f.read().splitlines()
    f.close()
    pairs = []
    for tr, lx in zip(trees, lexlines):
        pairs.append((parse_tree('^root{ ' + tr + ' }$'), parse_tree('^root{' + lx + '}$')))
    for i, (a, b) in enumerate(pairs):
        ls = list(range(len(b.children)))
        sets = []
        print('---------------------')
        while ls:
            n = ls.pop()
            sets.append([n] + [x for x in ls if b.children[x].equiv(b.children[n])])
            ls = [x for x in ls if not b.children[x].equiv(b.children[n])]
        for st in sets:
            n = len([x for x in a.iterchildren() if x.equiv(b.children[st[0]])])
            if n < len(st):
                for s in st:
                    b.children[s].skippable = True
        al = a.align(b.children)
        a.filter_align(al)
        a.suggest_rules([i], b.children)
        print(al)
        print(a)
        print(b)

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 5:
        print('%s cfg_rules rtx_filename sl_text tl_analyzed')
    else:
        read_rules(sys.argv[1])
        generate_file(sys.argv[2])
        align_corpus(get_trees(sys.argv[2], sys.argv[3]), sys.argv[4])
