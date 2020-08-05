#!/bin/sh

# Note that the path given here is specific to my computer - Daniel

#../../basic_rules.py eng spa eng-base.rtx eng-spa.rtx -s corpus-eng.txt -t corpus-spa.txt -pp ~/apertium-data/apertium-eng-spa -a biltrans

../../basic_rules.py eng spa eng-base.rtx eng-spa.rtx -s corpus-eng.txt -t corpus-spa.txt -sp ~/apertium-data/apertium-eng -tp ~/apertium-data/apertium-spa -a eflomal

../../no_rules.py eng spa eng-spa2.rtx -s corpus-eng.txt -t corpus-spa.txt -sp ~/apertium-data/apertium-eng -tp ~/apertium-data/apertium-spa -a eflomal
