#!/usr/bin/env python3

import argparse
import os

def make_corpus_argparse(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('src_lang', help='language to translate from')
    parser.add_argument('trg_lang', help='language to translate to')
    parser.add_argument('-sp', '--source-path', help='path to directory of source analyzer')
    parser.add_argument('-tp', '--target-path', help='path to directory of target analyzer')
    parser.add_argument('-pp', '--pair-path', help='path to directory of bilingual data')
    parser.add_argument('-c', '--corpus', help='bilingual corpus file')
    parser.add_arugment('-s', '--sl-corpus', help='source language corpus file')
    parser.add_argument('-t', '--tl-corpus', help='target language corpus file')
    parser.add_argument('-sep', '--separator', help='divider between source and target sentences if using a bilingual corpus (default |||)', default='|||')
    aligner = parser.add_mutually_exclusive_group()
    aligner.add_argument('-E', '--no-eflomal', help="don't use eflomal for aligning", action='store_true')
    aligner.add_argument('-B', '--no-biltrans', help="don't use biltrans for aligning", action='store_true')
    parser.add_argument('-b', '--biltrans-suggestions', help='file to write possible bilingual dictionary entries to')
    return parser

def validate_arguments(
