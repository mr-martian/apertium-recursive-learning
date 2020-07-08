#!/usr/bin/python3

import requests
import html
import json
import os
from typing import List

TAG_DATA_FILE = os.path.split(os.path.abspath(__file__))[0] + '/tags.json'

category_to_tag = {}
tag_to_category = {}

def flip_tags(dct, key=''):
    '''generate tag_to_category from category_to_tag
    called by scrape_tags() and load_tags(), do not call directly'''
    global tag_to_category
    for k in dct:
        if isinstance(dct[k], str):
            tag_to_category[k] = key
        else:
            flip_tags(dct[k], k)

def scrape_tags():
    '''scrape tag database from Apertium wiki'''
    global category_to_tag
    current = []
    all_tags = {}
    r = requests.get('http://wiki.apertium.org/w/index.php?title=List_of_symbols&action=raw')
    if r.status_code != 200:
        raise Exception('Couldn\'t get wiki page')
    for line in html.unescape(r.content.decode('utf-8')).splitlines():
        #print(line)
        if line.startswith('==') and '<!--' in line:
            name = line.split('<!--')[1].split('-->')[0].strip()
            d = 0
            if line.startswith('==='): d = 1
            if line.startswith('===='): d = 2
            if len(current) == d:
                current.append(name)
            else:
                current = current[:d] + [name]
            if len(current) == 1:
                all_tags[current[0]] = {}
            elif len(current) == 2:
                all_tags[current[0]][current[1]] = {}
            elif len(current) == 3:
                all_tags[current[0]][current[1]][current[2]] = {}
        elif line.startswith('| <code>'):
            tag = line.split('<code>')[1].split('</code>')[0]
            gloss = line.split('||')[1].strip().replace('"', "'")
            if len(current) == 1:
                all_tags[current[0]][tag] = gloss
            elif len(current) == 2:
                all_tags[current[0]][current[1]][tag] = gloss
            elif len(current) == 3:
                all_tags[current[0]][current[1]][current[2]][tag] = gloss
    with open(TAG_DATA_FILE, 'w') as f:
        json.dump(all_tags, f)
    category_to_tag = all_tags
    flip_tags(all_tags)

def load_tags():
    '''load tag database from file'''
    global category_to_tag
    with open(TAG_DATA_FILE) as f:
        try:
            category_to_tag = json.load(f)
        except:
            raise Exception("Tag data file missing or invalid. Please (re)run %s and try again." % os.path.abspath(__file__))
    flip_tags(category_to_tag)

def lookup_tag(tag):
    global tag_to_category
    if len(tag_to_category) == 0:
        load_tags()
    return tag_to_category.get(tag)

class Attribute:
    all_attrs = {}
    def __init__(self, name: str, values: List[str]):
        self.name = name
        self.values = values
        Attribute.all_attrs[name] = self
    def __str__(self):
        return '%s = %s;' % (self.name, ' '.join(self.values))
    def lookup(tag: str):
        if len(Attribute.all_attrs) == 0:
            Attribute.load_all()
        return Attribute.all_attrs.get(lookup_tag(tag))
    def load_all():
        global category_to_tag
        if len(category_to_tag) == 0:
            load_tags()
        def iter_tags(dct, key):
            ls = []
            for tag in dct:
                if isinstance(dct[tag], str):
                    ls.append(tag)
                else:
                    iter_tags(dct[tag], tag)
            if ls:
                if key in Attribute.all_attrs:
                    Attribute.all_attrs[key].values += ls
                else:
                    Attribute(key, ls)
        iter_tags(category_to_tag, '')

if __name__ == '__main__':
    scrape_tags()
