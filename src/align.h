#ifndef __RTXLEARN_ALIGN_H__
#define __RTXLEARN_ALIGN_H__

#include <string>
#include <vector>
#include <set>
#include <cstdio>

struct Node {
  int id;
  int parent;
  bool isVirtual;
  bool isLeft;
  std::vector<int> children;
  std::set<int> align;
};

typedef std::set<int> Yield;
typedef std::vector<Node*> Tree;

void getAlignments(Tree& nodes);

Tree readTrees(FILE* in);
void writeTrees(FILE* out, Tree& nodes);

#endif
