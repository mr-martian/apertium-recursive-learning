#!/usr/bin/env python3
from typing import List, Tuple, Optional, Dict, Union
import itertools
import subprocess
import tempfile
from tags import Attribute
from eflomal_wrapper import run_eflomal, postedit_eflomal
from collections import defaultdict

class LU:
    def __init__(self, idx: int, lem: str, tags: List[str], children: List["LU"]):
        self.idx = idx
        self.lem = lem
        self.tags = tags
        self.children = children
        self.align: List[int] = []
        self.children_options: List[List[int]] = []
    def __str__(self):
        return self.__repr__()
    def __repr__(self):
        return '^' + self.lem + ''.join('<%s>' % t for t in self.tags) + '{' + ' '.join(map(str, self.children)) + '}$'
    def fromstring(s: str) -> "LU":
        assert(s[0] == '^')
        assert(s[-1] == '$')
        lem = ''
        tags = []
        children = []
        start = 1
        i = 1
        loc = 'lem'
        depth = 0
        while i < len(s):
            if s[i] == '\\':
                i += 2
                continue
            if loc == 'lem' and s[i] in '</${':
                lem = s[start:i]
                start = i
                if s[i] == '<':
                    start += 1
                    loc = 'tags'
                elif s[i] == '/':
                    loc = 'tl'
                elif s[i] == '$':
                    assert(i == len(s) - 1)
                    break
                elif s[i] == '{':
                    loc = 'children'
                    start = i+1
            elif loc == 'tags' and s[i] == '>':
                tags.append(s[start:i])
                loc = 'none'
            elif loc == 'none' and s[i] == '<':
                start = i + 1
                loc = 'tags'
            elif loc == 'none' and s[i] in '/${':
                if s[i] == '/':
                    loc = 'tl'
                elif s[i] == '$':
                    assert(i == len(s) - 1)
                    break
                elif s[i] == '{':
                    loc = 'children'
                    start = i+1
            elif loc == 'tl' and s[i] in '${':
                if s[i] == '$':
                    assert(i == len(s) - 1)
                    break
                else:
                    loc = 'children'
                    start = i+1
            elif loc == 'children' and s[i] in '^$}':
                if s[i] == '^':
                    depth += 1
                    if depth == 1:
                        start = i
                elif s[i] == '$':
                    depth -= 1
                    if depth == 0:
                        children.append(LU.fromstring(s[start:i+1]))
                elif depth == 0:
                    assert(s[i:] == '}$')
                    break
            i += 1
        return LU(-1, lem, tags, children)
    def iter(self):
        yield self
        for ch in self.children:
            yield from ch.iter()
    def printtree(self, left: bool):
        return ('L' if left else 'R') + str(self.idx) + '[' + ' '.join(str(x.idx) for x in self.children) + '](' + ' '.join(map(str, self.align)) + ')'
    def pattern(self):
        return '"' + self.lem.lower() + '"@' + (self.tags or ['nothing'])[0]

class Rule:
    def __init__(self, parent: str, pat: List[str], order: List[int], inserts: List[str], virtual: bool = False):
        self.parent = parent
        self.pat = pat
        self.order = order
        self.inserts = inserts
        self.virtual = virtual
        self.weight = 0
    def __repr__(self):
        out = []
        for o in self.order:
            if o < len(self.pat):
                out.append(str(o+1))
            else:
                out.append(self.inserts[o - len(self.pat)])
        wgt = ''
        if self.weight > 0:
            wgt = ' %s:' % self.weight
        return '%s ->%s %s { %s } ;' % (self.parent, wgt, ' '.join(self.pat), ' _ '.join(out))
    def conflicts(self, other):
        if self.pat != other.pat:
            return False
        if self.parent == other.parent and self.order == other.order and self.inserts == other.inserts:
            return False
        return True
    def redundant(self, other):
        return self.pat == other.pat and self.parent == other.parent and self.order == other.order and self.inserts == other.inserts

def strls(ls: List[int]) -> str:
    return ' '.join(map(str, ls))

class Sentence:
    def __init__(self, sl: LU, tl: LU):
        self.sl = sl
        self.tl = tl
        self.left_virtual: List[int] = []
        self.right_virtual: List[int] = []
        self.nodes = list(sl.iter()) + list(tl.iter())
        for i, n in enumerate(self.nodes):
            n.idx = i
        self.left_leaves = []
        self.right_leaves = []
        for n in self.nodes:
            n.children_options.append([x.idx for x in n.children])
            if len(n.children) == 0:
                if n.idx < self.tl.idx:
                    self.left_leaves.append(n.idx)
                else:
                    self.right_leaves.append(n.idx)
    def printtree(self):
        return str(len(self.nodes)) + ' ' + ' '.join(x.printtree(x.idx < self.tl.idx) for x in self.nodes)
    def getwords(self) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        left = [(self.nodes[i].lem.lower(), (self.nodes[i].tags or [''])[0]) for i in self.left_leaves]
        right = [(self.nodes[i].lem.lower(), (self.nodes[i].tags or [''])[0]) for i in self.right_leaves]
        return (left, right)
    def setwordalignments(self, alg: Dict[int, int]):
        for k in alg:
            s = self.left_leaves[k]
            v = alg[k] if isinstance(alg[k], list) else [alg[k]]
            for i in v:
                t = self.right_leaves[i]
                self.nodes[s].align.append(t)
                self.nodes[t].align.append(s)
    def addtreealignments(self, alg: str):
        #print(self.printtree())
        #print(alg)
        tok = alg.split()
        node = -1
        i = 0
        #print('len = %s' % len(self.nodes))
        for t in tok:
            if t[0] in 'LR':
                n = int(t[1:])
                self.nodes.append(LU(node, '', [], []))
                if t[0] == 'L':
                    self.left_virtual.append(n)
                else:
                    self.right_virtual.append(n)
        #print('len = %s' % len(self.nodes))
        while i < len(tok):
            if tok[i] == '(':
                i += 1
                while tok[i] != ')':
                    self.nodes[node].align.append(int(tok[i]))
                    i += 1
            elif tok[i] == '[':
                i += 1
                #print(node)
                self.nodes[node].children_options.append([])
                while tok[i] != ']':
                    self.nodes[node].children.append(self.nodes[int(tok[i])])
                    self.nodes[node].children_options[0].append(int(tok[i]))
                    i += 1
            elif tok[i][0] in 'LR':
                node = int(tok[i][1:])
            else:
                node = int(tok[i])
            i += 1
        for n in self.left_virtual + self.right_virtual:
            self.nodes[n].tags.append('_'.join((x.tags or ['*'])[0] for x in self.nodes[n].children))
            for i, nd in enumerate(self.nodes):
                if i == n: continue
                newops = []
                for op1 in self.nodes[n].children_options:
                    s1 = strls(op1)
                    for op2 in nd.children_options:
                        s2 = strls(op2)
                        if s1 in s2:
                            l, r = s2.split(s1, 1)
                            newops.append([int(x) for x in l.strip().split()] + [n] +
                                          [int(x) for x in r.strip().split()])
                nd.children_options += newops
    def getrules(self) -> List[Rule]:
        ret = []
        #print(self.printtree())
        for n in (list(range(self.tl.idx)) + self.left_virtual):
            sl = self.nodes[n]
            if len(sl.children) == 0 or sl.tags == ['UNKNOWN:INTERNAL']:
                continue
            for o in self.nodes[n].align:
                #print('  trying %s -- %s' % (n, o))
                tl = self.nodes[o]
                alltl = set()
                for op in tl.children_options:
                    alltl.update(op)
                for slch in sl.children_options:
                    allsl = set()
                    for s in slch:
                        for c in self.nodes[s].iter():
                            allsl.update(c.align)
                    for tlch in tl.children_options:
                        #print('    L%s%s -- R%s%s' % (n, slch, o, tlch))
                        alltl = set()
                        for t in tlch:
                            for c in self.nodes[t].iter():
                                if len(c.children) == 0:
                                    alltl.add(c.idx)
                        if allsl.isdisjoint(alltl):
                            #print('      no aligned terminals')
                            continue
                        order = []
                        inserts = []
                        for t in tlch:
                            if all(len(x.align) == 0 for x in self.nodes[t].iter()):
                                order.append(len(slch) + len(inserts))
                                inserts.append(self.nodes[t].pattern())
                                continue
                            for i, s in enumerate(slch):
                                if s in self.nodes[t].align:
                                    order.append(i)
                                    break
                            else:
                                # found a TL that isn't an unaligned terminal
                                # so give up
                                break
                        else:
                            parent = (sl.tags or ['?'])[0]
                            virtual = not (set(slch + [n]).isdisjoint(set(self.left_virtual)) or
                                           set(tlch + [o]).isdisjoint(set(self.right_virtual)))
                            pat = []
                            for x in slch:
                                if self.nodes[x].tags and self.nodes[x].tags != ['UNKNOWN:INTERNAL']:
                                    pat.append(self.nodes[x].tags[0])
                                else:
                                    pat.append('*')
                            ret.append(Rule(parent, pat, order, inserts, virtual))
        return ret

class Corpus:
    def __init__(self, sents: List[Sentence]):
        self.sents = sents
    def wordalign(self, fname=None):
        sl_ids = {}
        tl_ids = {}
        toks = []
        for s in self.sents:
            sl, tl = s.getwords()
            sli = []
            for w in sl:
                k = len(sl_ids)
                if w not in sl_ids:
                    sl_ids[w] = k
                sli.append(sl_ids[w])
            tli = []
            for w in tl:
                k = len(tl_ids)
                if w not in tl_ids:
                    tl_ids[w] = k
                tli.append(tl_ids[w])
            toks.append((sli, tli))
        algs = []
        if fname:
            algs = postedit_eflomal(fname)
        else:
            algs = run_eflomal(toks)
        for s, a in zip(self.sents, algs):
            s.setwordalignments(a)
    def biltrans_align(self, fname):
        def lemtag(s):
            l = s.split('<')
            lem = l[0].lower()
            tg = ''
            if len(l) > 1:
                tg = l[1][:-1]
            return (lem, tg)
        trans = defaultdict(list)
        with open(fname) as f:
            s = f.read()
            i = 0
            while '^' in s[i:]:
                i = s.index('^', i)
                e = s.index('$', i)
                lus = s[i+1:e].split('/')
                sl = lemtag(lus[0])
                for tl in lus[1:]:
                    trans[sl].append(lemtag(tl))
                i = e
        for s in self.sents:
            sl, tl = s.getwords()
            for i, w in enumerate(sl):
                if w not in trans:
                    continue
                for j, v in enumerate(tl):
                    if v in trans[w]:
                        s.setwordalignments({i: j})
    def treealign(self):
        print('  running align-tree...')
        tmp1 = tempfile.NamedTemporaryFile('w+')
        tmp2 = tempfile.NamedTemporaryFile('w+')
        tmp1.write('\n'.join(s.printtree() for s in self.sents))
        tmp1.seek(0)
        subprocess.run(['src/align-tree', tmp1.name, tmp2.name])
        tmp2.seek(0)
        txt = tmp2.read()
        print('  processing alignments...')
        for l, s in zip(txt.splitlines(), self.sents):
            s.addtreealignments(l.strip())
            #print('    done with one')
    def getrules(self):
        rules = []
        for s in self.sents:
            rules += s.getrules()
        non_conflict = []
        non_redundant = []
        for r in rules:
            if not any(r.conflicts(x) for x in rules) and not any(r.redundant(x) for x in non_conflict):
                non_conflict.append(r)
            for other in non_redundant:
                if r.redundant(other):
                    other.weight += 1
                    break
            else:
                non_redundant.append(r)
        #return non_conflict
        #return rules
        return non_redundant

def read_tree_file(fname):
    with open(fname) as f:
        return [LU.fromstring(l) for l in f.read().splitlines() if l.strip()]
    
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser('Generate RTX rules')
    parser.add_argument('sl_trees', help="file to read source language trees from")
    parser.add_argument('tl_trees', help="file to read target language trees from")
    parser.add_argument('--biltrans', '-b', help="file to read biltrans alignment data from", action='store')
    parser.add_argument('--align', '-a', help="file to read post-editted eflomal data from", action='store')
    parser.add_argument('--output', '-o', help="output file", action='store')
    args = parser.parse_args()

    sl = read_tree_file(args.sl_trees)
    tl = read_tree_file(args.tl_trees)
    c = Corpus([Sentence(a, b) for a,b in zip(sl, tl)])
    if args.biltrans:
        c.biltrans_align(args.biltrans)
    elif args.align:
        c.wordalign(args.align)
    else:
        c.wordalign()
    c.treealign()
    c.treealign()
    rls = c.getrules()
    tags = set()
    for rl in rls:
        tags.add(rl.parent)
        tags.update(rl.pat)
    if args.output:
        with open(args.output, 'w') as f:
            for t in sorted(tags):
                if t != '*':
                    print('%s: _;' % t, file=f)
            print('\n', file=f)
            for rl in rls:
                print(rl, file=f)

