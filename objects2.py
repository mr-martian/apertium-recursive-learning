#!/usr/bin/env python3
from typing import List, Tuple, Optional, Dict, Union
import itertools
import subprocess
import tempfile
from tags import Attribute

class LU:
    def __init__(self, idx: int, lem: str, tags: List[str], children: List["LU"]):
        self.idx = idx
        self.lem = lem
        self.tags = tags
        self.children = children
        self.align: List[int] = []
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
                out.append(self.inserts(o - len(self.pat)))
        return '%s -> %s { %s }' % (self.parent, ' '.join(self.pat), ' _ '.join(out))

class Sentence:
    def __init__(self, sl: LU, tl: LU):
        self.sl = sl
        self.tl = tl
        self.left_virtual: List[int] = []
        self.right_virtual: List[int] = []
        self.nodes = list(sl.iter()) + list(tl.iter())
        for i, n in enumerate(self.nodes):
            n.idx = i
    def printtree(self):
        return ' '.join(x.printtree(x.idx < self.tl.idx) for x in self.nodes)
    def addalignments(self, alg: str):
        tok = str.split()
        node = -1
        i = 0
        while i < len(tok):
            if tok[i] == '(':
                i += 1
                while tok[i] != ')':
                    self.nodes[node].align.append(int(tok[i]))
            elif tok[i] == '[':
                i += 1
                while tok[i] != ']':
                    self.nodes[node].children.append(self.nodes[int(tok[i])])
            elif tok[i][0] in 'LR':
                node = int(tok[i][1:])
                self.left_virtual.append(node)
                self.nodes.append(LU(node, '', [], []))
            else:
                node = int(tok[i])
            i += 1
        for n in self.left_virtual + self.right_virtual:
            self.nodes[n].tags.append('_'.join(x.tags[0] for x in self.nodes[n].children))
    def getrules(self) -> List[Rule]:
        ret = []

class Corpus:
    def __init__(self, sents: List[Sentence]):
        self.sents = sents
