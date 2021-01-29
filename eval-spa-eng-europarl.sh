#!/bin/bash

morph () {
    apertium -d "../apertium-data/apertium-$1" "$1-tagger" | apertium-pretransfer
}

gen_morph () {
    head europarl-eng-spa/europarl.eng.txt -n 200 > euro.eng.eval.txt
    head europarl-eng-spa/europarl.spa.txt -n 200 > euro.spa.eval.txt
    tail europarl-eng-spa/europarl.eng.txt -n +201 | head -n $1 > euro.eng.txt
    tail europarl-eng-spa/europarl.spa.txt -n +201 | head -n $1 > euro.spa.txt
    cat euro.eng.txt | morph eng > euro.eng.morph.txt
    cat euro.spa.txt | morph spa > euro.spa.morph.txt
}

make_input () {
    cat euro.spa.morph.txt | ./cleanstream.py > euro.spa.morph-clean.txt
    cat euro.spa.morph-clean.txt | ./line-in.py | rtx-proc -m flat -T -z spa-cat.bin | ./line-out.py > euro.spa.tree.txt
    cat euro.eng.morph.txt | ./cleanstream.py | sed -e 's/^/^root<S>{/g' -e 's/$/}$/g' > euro.eng.tree.txt
    cat euro.spa.morph.txt | lt-proc -o ../apertium-data/apertium-eng-spa/spa-eng.autobil.bin > euro.spa.bil.txt
}

run_learner () {
    ./objects2.py euro.spa.tree.txt euro.eng.tree.txt -o euro.eflomal.rtx
    ./objects2.py euro.spa.tree.txt euro.eng.tree.txt -b euro.spa.bil.txt -o euro.bil.rtx
}

rtx_comp () {
    rtx-comp euro.eflomal.rtx euro.eflomal.bin
    rtx-comp euro.bil.rtx euro.bil.bin
}

rtx () {
    cat $1 | ./line-in.py | rtx-proc -F -z $2 | ./line-out.py -n | ./striptags.py
}

rtx_all () {
    rtx euro.bil.txt euro.eflomal.bin > euro.output.eflomal.txt
    rtx euro.bil.txt euro.bil.bin > euro.output.bil.txt
}

eval_one () {
    ~/apertium-eval-translator/apertium-eval-translator-line.pl -t $1 -r $2
}

eval_all () {
    echo "no rtx"
    eval_one euro.output.none.txt euro.eng.ref.txt
    echo "++++++++++++++++++++++++++++++++++++++"
    echo "rtx with eflomal"
    eval_one euro.output.eflomal.txt euro.eng.ref.txt
    echo "++++++++++++++++++++++++++++++++++++++"
    echo "rtx with biltrans"
    eval_one euro.output.bil.txt euro.output.ref.txt
}

gen_data () {
    cat euro.eng.eval.txt | morph eng | ./striptags.py -n > euro.eng.ref.txt
    cat euro.spa.eval.txt | morph spa > euro.spa.test.morph.txt
    cat euro.spa.test.morph.txt | lt-proc -o ../apertium-data/apertium-eng-kaz/kaz-eng.autobil.bin > euro.bil.txt
    cat euro.bil.txt | ./striptags.py -n > euro.output.none.txt
}

rtx-comp spa-cat.rtx spa-cat.bin
echo "gen_morph"
time gen_morph $1
echo "make_input"
time make_input
echo "run_learner"
time run_learner
echo "rtx_comp"
time rtx_comp
echo "gen_data"
time gen_data
echo "rtx_all"
time rtx_all
echo "eval_all"
time eval_all 2>/dev/null
