#!/bin/bash

to_att () {
    if [[ "$1" == *bin ]]; then
	lt-print -H $1
    else
	hfst-fst2txt $1
    fi
}

to_att $1 | ./strip_symbols.py | hfst-txt2fst | hfst-reverse | hfst-determinize | hfst-reverse | hfst-minimize | hfst-expand | sed 's/+/\n/g' | sed 's/://g' | sort | uniq
