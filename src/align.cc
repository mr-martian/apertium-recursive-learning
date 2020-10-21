#include "align.h"

Yield
getYield(int n, const Tree& nodes)
{
  Yield ret;
  if(nodes[n]->children.empty()) {
    ret.insert(n);
  } else {
    for(auto ch : nodes[n]->children) {
      Yield tmp = getYield(ch, nodes);
      ret.insert(tmp.begin(), tmp.end());
    }
  }
  return ret;
}

bool
alignedWith(int n, const Yield& y, const Tree& nodes)
{
  if(nodes[n]->align.empty()) return true;
  for(auto a : nodes[n]->align) {
    if(y.find(a) != y.end()) return true;
  }
  return false;
}

bool
yieldContains(const Yield& small, const Yield& large, const Tree& nodes)
{
  for(auto it : small) {
    if(!alignedWith(it, large, nodes)) return false;
  }
  return true;
}

Yield
getLowest(const Yield& yl, const Tree& nodes)
{
  Yield ret;
  for(auto it : yl) {
    bool any = false;
    for(auto ch : nodes[it]->children) {
      if(yl.find(ch) != yl.end()) {
        any = true;
        break;
      }
    }
    if(!any) ret.insert(it);
  }
  return ret;
}

Yield
getHighest(const Yield& yl, const Tree& nodes)
{
  Yield ret;
  for(auto it : yl) {
    if(yl.find(nodes[it]->parent) == yl.end()) ret.insert(it);
  }
  return ret;
}

bool
isContiguousSubset(std::vector<int>& ch, const Yield& rch)
{
  while(!ch.empty() && rch.find(ch[0]) == rch.end()) {
    ch.erase(ch.begin());
  }
  while(!ch.empty() && rch.find(ch.back()) == rch.end()) {
    ch.pop_back();
  }
  for(auto it : ch) {
    if(rch.find(it) == rch.end()) return false;
  }
  for(auto it : rch) {
    bool found = false;
    for(auto c : ch) {
      if(c == it) {
        found = true;
        break;
      }
    }
    if(!found) return false;
  }
  return true;
}

void
getAlignments(std::vector<Node*>& nodes)
{
  std::vector<std::pair<int, Yield>> left, right;
  for(auto& it : nodes) {
    if(it->isLeft) {
      left.push_back(std::make_pair(it->id, getYield(it->id, nodes)));
    } else {
      right.push_back(std::make_pair(it->id, getYield(it->id, nodes)));
    }
  }
  std::vector<std::vector<bool>> linr(left.size(), std::vector<bool>(right.size(), false));
  std::vector<std::vector<bool>> rinl(left.size(), std::vector<bool>(right.size(), false));
  for(size_t l = 0; l < left.size(); l++) {
    for(size_t r = 0; r < right.size(); r++) {
      if(yieldContains(left[l].second, right[r].second, nodes)) {
        linr[l][r] = true;
      }
      if(yieldContains(right[r].second, left[l].second, nodes)) {
        rinl[l][r] = true;
      }
      if(linr[l][r] && rinl[l][r]) {
        nodes[left[l].first]->align.insert(right[r].first);
        nodes[right[r].first]->align.insert(left[l].first);
      }
    }
  }
  std::vector<size_t> ltodo, rtodo;
  for(size_t i = 0; i < left.size(); i++) {
    if(!nodes[left[i].first]->children.empty() &&
       nodes[left[i].first]->align.empty()) {
      ltodo.push_back(i);
    }
  }
  for(size_t i = 0; i < right.size(); i++) {
    if(!nodes[right[i].first]->children.empty() &&
       nodes[right[i].first]->align.empty()) {
      rtodo.push_back(i);
    }
  }
  for(auto l : ltodo) {
    Yield rch_all; // all descendants of potential virtual node
    Yield rpar_all; // all ancestors of potential virtual node
    for(size_t i = 0; i < right.size(); i++) {
      if(rinl[l][i]) rch_all.insert(i);
      if(linr[l][i]) rpar_all.insert(i);
    }
    Yield rch = getHighest(rch_all, nodes);
    Yield rpar = getLowest(rpar_all, nodes);
    if(rpar.size() == 1) {
      int par = *rpar.begin();
      std::vector<int> ch = nodes[par]->children;
      if(isContiguousSubset(ch, rch)) {
        Node* v = new Node;
        v->id = nodes.size();
        v->isLeft = false;
        v->isVirtual = true;
        v->parent = par;
        v->children = ch;
        v->align.insert(left[l].first);
        nodes.push_back(v);
        nodes[left[l].first]->align.insert(v->id);
      }
    }
  }
  for(auto r : rtodo) {
    Yield lch_all; // all descendants of potential virtual node
    Yield lpar_all; // all ancestors of potential virtual node
    for(size_t i = 0; i < left.size(); i++) {
      if(linr[i][r]) lch_all.insert(i);
      if(rinl[i][r]) lpar_all.insert(i);
    }
    Yield lch = getHighest(lch_all, nodes);
    Yield lpar = getLowest(lpar_all, nodes);
    if(lpar.size() == 1) {
      int par = *lpar.begin();
      std::vector<int> ch = nodes[par]->children;
      if(isContiguousSubset(ch, lch)) {
        Node* v = new Node;
        v->id = nodes.size();
        v->isLeft = true;
        v->isVirtual = true;
        v->parent = par;
        v->children = ch;
        v->align.insert(right[r].first);
        nodes.push_back(v);
        nodes[right[r].first]->align.insert(v->id);
      }
    }
  }
  // TODO: virtual nodes aligned to virtual nodes
  // TODO: how to handle conflicting bracketing
}

void
attachParents(Tree& nodes)
{
  for(auto& it : nodes) {
    for(auto ch : it->children) {
      nodes[ch]->parent = it->id;
    }
  }
}

int
readInt(FILE* in, char* c)
{
  if(feof(in)) return -1;
  std::string n;
  while(isdigit(*c)) {
    n += *c;
    *c = fgetc(in);
  }
  if(n.empty()) return -1;
  return stoi(n);
}

Tree
readTrees(FILE* in)
{
  char c = fgetc(in);
  int count = readInt(in, &c);
  if(count == -1) return Tree();
  Tree ret(count, NULL);

  const int NONE = 0, ALIGN = 1, CHILDREN = 2;
  int cur_node = -1;
  int loc = NONE;
  
  while(!feof(in)) {
    char c = fgetc(in);
    if(c == ' ') continue;
    if(loc == NONE) {
      if(c == '\n') break;
      if(c == 'L' || c == 'R') {
        Node* n = new Node;
        n->isLeft = (c == 'L');
        n->isVirtual = false;
        n->parent = -1;
        c = fgetc(in);
        n->id = readInt(in, &c);
        ret[n->id] = n;
        cur_node = n->id;
      }
      if(c == '(') loc = ALIGN;
      if(c == '[') loc = CHILDREN;
    } else if(loc == ALIGN) {
      if(isdigit(c)) {
        ret[cur_node]->align.insert(readInt(in, &c));
      }
      if(c == ')') loc = NONE;
    } else if(loc == CHILDREN) {
      if(isdigit(c)) {
        ret[cur_node]->children.push_back(readInt(in, &c));
      }
      if(c == ']') loc = NONE;
    }
  }
  attachParents(ret);
  return ret;
}

void
writeTrees(FILE* out, Tree& nodes)
{
  for(auto& it : nodes) {
    if(it->children.empty()) continue;
    if(it->isVirtual) {
      if(it->isLeft) {
        fprintf(out, "L");
      } else {
        fprintf(out, "R");
      }
      fprintf(out, "%d [ ", it->id);
      for(auto ch : it->children) {
        fprintf(out, "%d ", ch);
      }
      fprintf(out, "] ");
    }
    fprintf(out, "%d ( ", it->id);
    for(auto a : it->align) {
      fprintf(out, "%d ", a);
    }
    fprintf(out, ") ");
  }
  fprintf(out, "\n");
}
