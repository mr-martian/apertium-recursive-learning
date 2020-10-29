#!/usr/bin/env python3
from typing import List, Tuple, Optional, Dict, Union
import itertools
import subprocess
import tempfile
from tags import Attribute
from eflomal_wrapper import run_eflomal

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

class Rule:
    def __init__(self, parent: str, pat: List[str], order: List[int], inserts: List[str], virtual: bool = False):
        self.parent = parent
        self.pat = pat
        self.order = order
        self.inserts = inserts
        self.virtual = virtual
    def __repr__(self):
        out = []
        for o in self.order:
            if o < len(self.pat):
                out.append(str(o+1))
            else:
                out.append(self.inserts[o - len(self.pat)])
        return '%s -> %s { %s }' % (self.parent, ' '.join(self.pat), ' _ '.join(out))
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
        left = [(self.nodes[i].lem, (self.nodes[i].tags or [''])[0]) for i in self.left_leaves]
        right = [(self.nodes[i].lem, (self.nodes[i].tags or [''])[0]) for i in self.right_leaves]
        return (left, right)
    def setwordalignments(self, alg: Dict[int, int]):
        for k in alg:
            s = self.left_leaves[k]
            t = self.right_leaves[alg[k]]
            self.nodes[s].align.append(t)
            self.nodes[t].align.append(s)
    def addtreealignments(self, alg: str):
        tok = alg.split()
        node = -1
        i = 0
        while i < len(tok):
            if tok[i] == '(':
                i += 1
                while tok[i] != ')':
                    self.nodes[node].align.append(int(tok[i]))
                    i += 1
            elif tok[i] == '[':
                i += 1
                self.nodes[node].children_options.append([])
                while tok[i] != ']':
                    self.nodes[node].children.append(self.nodes[int(tok[i])])
                    self.nodes[node].children_options[0].append(int(tok[i]))
                    i += 1
            elif tok[i][0] in 'LR':
                node = int(tok[i][1:])
                self.left_virtual.append(node)
                self.nodes.append(LU(node, '', [], []))
            else:
                node = int(tok[i])
            i += 1
        for n in self.left_virtual + self.right_virtual:
            self.nodes[n].tags.append('_'.join(x.tags[0] for x in self.nodes[n].children))
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
        for n in (list(range(self.tl.idx)) + self.left_virtual):
            sl = self.nodes[n]
            for o in self.nodes[n].align:
                tl = self.nodes[o]
                alltl = set()
                for op in tl.children_options:
                    alltl.update(op)
                for slch in sl.children_options:
                    for tlch in tl.children_options:
                        if any(set(self.nodes[x].align).isdisjoint(set(tlch)) for x in slch):
                            continue
                        order = []
                        # TODO: there's probably several things wrong here w.r.t. unaligned terminals
                        for t in tlch:
                            for i, s in enumerate(slch):
                                if s in self.nodes[t].align:
                                    order.append(i)
                                    break
                        virtual = not (set(slch + [n]).isdisjoint(set(self.left_virtual)) or
                                       set(tlch + [o]).isdisjoint(set(self.right_virtual)))
                        parent = (sl.tags or ['?'])[0]
                        pat = [(self.nodes[x].tags or ['*'])[0] for x in slch]
                        inserts = []
                        ret.append(Rule(parent, pat, order, inserts, virtual))
        return ret

class Corpus:
    def __init__(self, sents: List[Sentence]):
        self.sents = sents
    def wordalign(self):
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
        algs = run_eflomal(toks)
        for s, a in zip(self.sents, algs):
            s.setwordalignments(a)
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
            print('    done with one')
    def getrules(self):
        rules = []
        for s in self.sents:
            rules += s.getrules()
        non_conflict = []
        non_redundant = []
        for r in rules:
            if not any(r.conflicts(x) for x in rules) and not any(r.redundant(x) for x in non_conflict):
                non_conflict.append(r)
            if not any(r.redundant(x) for x in non_redundant):
                non_redundant.append(r)
        #return non_conflict
        #return rules
        return non_redundant

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print('Usage: %s sl_trees tl_trees' % sys.argv[0])
    else:
        sl = []
        tl = []
        print('reading...')
        with open(sys.argv[1]) as f:
            sl = [LU.fromstring(l) for l in f.read().splitlines() if l.strip()]
        with open(sys.argv[2]) as f:
            tl = [LU.fromstring(l) for l in f.read().splitlines() if l.strip()]
        c = Corpus([Sentence(a, b) for a,b in zip(sl, tl)])
        print('eflomalizing...')
        c.wordalign()
        print('tree-aligning...')
        c.treealign()
        print('finding rules...')
        for rl in c.getrules():
            print(rl)

