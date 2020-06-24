#!/bin/sh
rtx-comp -s $1 /tmp/blah.bin 2>$2
cat $2 | grep "\->" | sed -E "s/\"[^\"]+\": //g" | sort | uniq > $2
