#!/usr/bin/env python3
from typing import List, Tuple, Optional, Dict, Union
import itertools
import subprocess
import tempfile
from tags import Attribute

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

class Clip:
    def __init__(self, pos: int, attr: str, val: Optional[Union[str, "Clip"]] = None):
        self.pos = pos
        self.attr = attr
        self.val = val
    def __str__(self):
        ret = ''
        if self.pos == 0:
            ret += '$'
        else:
            ret += str(self.pos) + '.'
        ret += self.attr
        if self.val:
            ret += '=' + str(self.val)
        return ret

class InputNode:
    def __init__(self, tags: Optional[List[str]],
                       lemma: Optional[str] = '',
                       clips: Optional[List[str]] = None):
        self.lemma = lemma
        self.tags = tags
        self.clips = clips or []
    def __str__(self):
        ret = self.lemma + '@' if self.lemma else ''
        return ret + '.'.join(self.tags + ['$' + c for c in self.clips])

class OutputNode:
    def __init__(self, source: int, clips: Dict[str, Union[Clip, str]]):
        self.source = source
        self.clips = clips
        self.value = ''
    def __str__(self):
        args = ['%s=%s' % (name, self.clips[name]) for name in self.clips]
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
    def overlap(self, other: "Rule") -> bool:
        '''determine whether there exists a sequence of tokens which
        both self and other could match part of'''
        for i, o in enumerate(other.inputs):
            if o.tags[0] == self.inputs[0].tags[0]:
                if all(a.tags[0] == b.tags[0] for a,b in zip(other.inputs[i+1:], self.inputs[1:])):
                    return True
        for i, inp in enumerate(self.inputs[1:], 1):
            if inp.tags[0] == other.inputs[0].tags[0]:
                if all(a.tags[0] == b.tags[0] for a,b in zip(other.inputs[1:], self.inputs[i+1:])):
                    return True
        return False

def generate_rule_file(fname: str, rules: Optional[List[Rule]] = None):
    for rl in (rules or Rule.all_rules.values()):
        if rl.parent not in Pattern.all_patterns:
            Pattern(rl.parent)
        for inp in rl.inputs:
            if inp.tags[0] not in Pattern.all_patterns:
                Pattern(inp.tags[0])
    with open(fname, 'w') as f:
        for name, attr in sorted(Attribute.all_attrs.items()):
            f.write(str(attr) + '\n')
        f.write('\n\n')
        for name, pat in sorted(Pattern.all_patterns.items()):
            f.write(str(pat) + '\n')
        f.write('\n\n')
        for rule in (rules or sorted(Rule.all_rules.values())):
            f.write(str(rule) + '\n\n')

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
    def stream(self) -> str:
        sl = self.slem + ''.join('<%s>' % x for x in self.stags)
        tl = self.tlem + ''.join('<%s>' % x for x in self.ttags)
        if sl and tl:
            sl += '/'
        return '^' + sl + tl + '$'
    def equiv(self, other: "LU"):
        if self.tlem != other.tlem:
            return False
        if self.ttags == [] and other.ttags == []:
            return True
        if self.ttags and other.ttags and self.ttags[0] == other.ttags[0]:
            return True
        return False
    def compatible(self, node: InputNode):
        chunk = (len(self.children) > 0)
        if node.lemma:
            if (chunk and self.tlem != node.lemma) or (not chunk and self.slem != node.lemma):
                return False
        def compare_tags(tags: List[str], pat: List[str]):
            if len(pat) == 0:
                return True
            elif pat[0] == '*':
                return any(compare_tags(tags[n:], pat[1:]) for n in range(len(tags)))
            elif len(tags) == 0:
                return False
            elif tags[0] == pat[0]:
                return compare_tags(tags[1:], pat[1:])
            else:
                return False
        if chunk:
            return compare_tags(self.ttags, node.tags)
        else:
            return compare_tags(self.stags, node.tags)
    def assign_alignment(self, align: Dict[int, List[int]], index: Optional[int] = 0) -> int:
        '''set self.possible based on output of word aligner
        align is {source_index: [target_indecies]}
        index is the source index of this node or its left-most terminal descendant
        returns: own source index or that or right-most terminal descendant
        '''
        if len(self.children) == 0:
            if index in align:
                self.possible = [(x, x) for x in align[index]]
                if (-1,-1) in self.possible:
                    self.skippable = True
            else:
                self.skippable = True
            return index
        else:
            n = index - 1
            for ch in self.children:
                n = ch.assign_alignment(align, n+1)
            return n
    def align_tree_to_flat(self, words: List["LU"]):
        if len(self.possible) > 0:
            return self.possible
        ret = []
        if len(self.children) == 0 and not self.skippable:
            for i, w in enumerate(words):
                if self.equiv(w):
                    ret.append((i, i))
            if not ret:
                ret.append((-1,-1))
        else:
            ops = []
            for i, ch in enumerate(self.children):
                ls = [(a,i) for a in ch.align_tree_to_flat(words)]
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
    def match_surface(self) -> Tuple[str, List[str]]:
        if len(self.children) > 0:
            return (self.tlem, self.ttags)
        else:
            return (self.slem, self.stags)
    def possible_constituents(self, tl: List["LU"]) -> List[Tuple[Tuple[int, int], bool]]:
        '''find all adjacent pairs in self (sl) which are either not aligned
        or are aligned with an adjacent pair in tl
        returns sl indecies'''
        if len(self.children) < 2:
            return []
        ret: List[Tuple[Tuple[Tuple[int, int], bool]]] = []
        for i, ch in enumerate(self.children):
            if i == 0:
                continue
            prev = self.children[i-1]
            if prev.skippable or ch.skippable:
                ret.append(((i-1, i), False))
                continue
            for lpos in prev.possible:
                if lpos == (-1, -1):
                    ret.append(((i-1, i), False))
                    break
                for rpos in ch.possible:
                    if rpos == (-1, -1):
                        ret.append(((i-1, i), False))
                        break
                    gapl = 0
                    gapr = 0
                    flip = False
                    if lpos[0] > rpos[1]: # prev moves to the right of ch in tl
                        gapl = rpos[1] + 1
                        gapr = lpos[0]
                        flip = True
                    elif lpos[1] < rpos[0]: # order is maintained in tl
                        gapl = lpos[1] + 1
                        gapr = rpos[0]
                    else: # overlap - not a constituent
                        continue
                    if gapl <= gapr and all(x.skippable for x in tl.children[gapl:gapr]):
                        ret.append(((i-1, i), flip))
        return ret
    def possible_applications(self, rl: Rule) -> List[Tuple[int, ...]]:
        '''return every range over which rl could apply'''
        starts = [i for i, ch in enumerate(self.children) if ch.compatible(rl.inputs[0])]
        ret = []
        for s in starts:
            for i, inp in enumerate(rl.inputs[1:], 1):
                if i+s >= len(self.children) or not self.children[i+s].compatible(inp):
                    break
            else:
                ret.append(tuple(range(s, s+len(rl.inputs))))
        return ret

def parse_tree(line: str, side: str = 'both') -> LU:
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
                    children.append(parse_tree(sub[l:i+1], side))
    ls = label.split('/')
    sl = ''
    tl = ''
    if side == 'both':
        if len(ls) == 1:
            tl = ls[0]
        else:
            sl = ls[0]
            tl = ls[1]
    else:
        idx = 1
        if len(ls) == 1 or '<' in ls[0]:
            idx = 0
        if side == 'sl':
            sl = ls[idx]
        else:
            tl = ls[idx]
    slem, stags = sl.split('<', 1) if '<' in sl else (sl, '')
    tlem, ttags = tl.split('<', 1) if '<' in tl else (tl, '')
    return LU(slem.lower(), stags.strip('<>').split('><'),
              tlem.lower(), ttags.strip('<>').split('><'),
              children)

def parse_file(file, sep='\n', side: str = 'both') -> List[LU]:
    file.seek(0)
    ret = []
    txt = file.read()
    ls = txt.split(sep)
    for line in ls:
        ret.append(parse_tree('^root{ ' + line.strip() + ' }$', side))
    return ret

class Sentence:
    def __init__(self, sl: LU, tl: LU, align: Optional[Dict[int, List[int]]] = None):
        self.sl = sl
        self.tl = tl
        self.align = align
        if self.align:
            self.sl.assign_alignment(align)
    def source_text(self) -> str:
        return ' '.join(l.stream() for l in self.sl.iterchildren())
    def update_sl(self, new_sl: LU):
        self.sl = new_sl
        if self.align:
            self.sl.assign_alignment(self.align)
            self.sl.align_tree_to_flat(self.tl.children)

class Corpus:
    def __init__(self, sens: List[Sentence]):
        self.sens: List[Sentence] = sens
    def retree(self, rtx_bin_filename: str):
        txt = '\n\0'.join(s.source_text() for s in self.sens)
        proc = subprocess.run(['rtx-proc', '-z', '-T', '-m', 'flat', rtx_bin_filename],
                              input=txt, encoding='utf-8', stdout=subprocess.PIPE)
        for sen, line in zip(self.sens, proc.stdout.split('\0')):
            sen.update_sl(parse_tree('^root{ ' + line.strip() + ' }$'))
    def compile_and_retree(self, rtx_filename: str):
        binfile = tempfile.NamedTemporaryFile()
        subprocess.run(['rtx-comp', rtx_filename, binfile.name])
        self.retree(binfile.name)
