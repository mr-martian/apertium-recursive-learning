#include "align.h"
#include <lttoolbox/lt_locale.h>
#include <lttoolbox/compression.h>
#include <getopt.h>
#include <libgen.h>
#include <iostream>
#include <fstream>
#include <cstring>
#include <cstdio>

void endProgram(char *name)
{
  cout << basename(name) << ": align a pair of trees, inserting virtual nodes if necessary" << endl;
  cout << "USAGE: " << basename(name) << " [ -h ] [input_file [output_file]]" << endl;
  cout << "Options:" << endl;
#if HAVE_GETOPT_LONG
  cout << "  -e, --error:  exit with error if trees cannot be fully aligned" << endl;
  cout << "  -h, --help:   show this help" << endl;
#else
  cout << "  -e: exit with error if trees cannot be fully aligned" << endl;
  cout << "  -h: show this help" << endl;
#endif
  exit(EXIT_FAILURE);
}

int main(int argc, char *argv[])
{
  bool error = false;

#if HAVE_GETOPT_LONG
  static struct option long_options[]=
    {
      {"error",             0, 0, 'e'},
      {"help",              0, 0, 'h'}
    };
#endif

  while(true)
  {
#if HAVE_GETOPT_LONG
    int option_index;
    int c = getopt_long(argc, argv, "eh", long_options, &option_index);
#else
    int c = getopt(argc, argv, "eh");
#endif

    if(c == -1)
    {
      break;
    }

    switch(c)
    {
    case 'e':
      error = true;
      break;

    case 'h':
    default:
      endProgram(argv[0]);
      break;
    }
  }

  LtLocale::tryToSetLocale();

  if(optind < (argc - 2))
  {
    endProgram(argv[0]);
  }

  FILE *in = stdin, *out = stdout;

  if(optind <= (argc - 1))
  {
    in = fopen(argv[optind], "rb");
    if(in == NULL)
    {
      wcerr << L"Error: could not open file " << argv[optind] << " for reading." << endl;
      exit(EXIT_FAILURE);
    }
  }
  if(optind <= (argc - 2))
  {
    out = fopen(argv[optind+1], "wb");
    if(out == NULL)
    {
      wcerr << L"Error: could not open file " << argv[optind+1] << " for writing." << endl;
      exit(EXIT_FAILURE);
    }
  }

  while(!feof(in)) {
    Tree nodes = readTrees(in);
    if(nodes.empty()) break;
    getAlignments(nodes);
    writeTrees(out, nodes);
    for(size_t i = 0; i < nodes.size(); i++) {
      delete nodes[i];
    }
  }

  fclose(in);
  fclose(out);
  return EXIT_SUCCESS;
}
