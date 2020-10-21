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
yieldsMatch(const Yield& ly, const Yield& ry, const Tree& nodes)
{
  for(auto l : ly) {
    if(!alignedWith(l, ry, nodes)) return false;
  }
  for(auto r : ry) {
    if(!alignedWith(r, ly, nodes)) return false;
  }
  return true;
}

void
getAlignments(std::vector<Node*>& nodes)
{
  std::vector<std::pair<int, Yield>> left, right;
  for(auto& it : nodes) {
    if(it->children.empty()) continue;
    if(it->isLeft) {
      left.push_back(std::make_pair(it->id, getYield(it->id, nodes)));
    } else {
      right.push_back(std::make_pair(it->id, getYield(it->id, nodes)));
    }
  }
  for(auto& l : left) {
    for(auto& r : right) {
      if(yieldsMatch(l.second, r.second, nodes)) {
        nodes[l.first]->align.insert(r.first);
        nodes[r.first]->align.insert(l.first);
      }
    }
  }
  std::vector<size_t> ltodo, rtodo;
  for(size_t i = 0; i < left.size(); i++) {
    if(nodes[left[i].first]->align.size() != 1) {
      ltodo.push_back(i);
    }
  }
  for(size_t i = 0; i < right.size(); i++) {
    if(nodes[right[i].first]->align.size() != 1) {
      rtodo.push_back(i);
    }
  }
  // TODO: virtual nodes for things in ltodo and rtodo
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
