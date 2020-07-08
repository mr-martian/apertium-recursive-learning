#!/usr/bin/env python3
from typing import List, Tuple, Optional, Dict
import itertools

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
    def assign_alignment(self, align: Dict[int, int], index: Optional[int] = 0) -> int:
        '''set self.possible based on output of word aligner
        align is {source_index: target_index}
        index is the source index of this node or its left-most terminal descendant
        returns: own source index or that or right-most terminal descendant
        '''
        if len(self.children) == 0:
            if index in align:
                self.possible = [(align[index], align[index])]
            else:
                self.skippable = True
            return index
        else:
            n = index - 1
            for ch in self.children:
                n = ch.assign_alignment(align, n+1)
            return n
    def align(self, words: List["LU"]):
        if len(self.possible) > 0:
            return self.possible
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

class Sentence:
    def __init__(self, sltext, tltext):
        pass



