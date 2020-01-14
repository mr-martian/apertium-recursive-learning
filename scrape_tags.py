#!/usr/bin/python3

import requests
import html

def scrape_tags():
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
    return all_tags

if __name__ == '__main__':
    import sys, json
    if len(sys.argv) != 2:
        print('Usage: %s output_file' % sys.argv[0])
    f = open(sys.argv[1], 'w')
    blob = scrape_tags()
    json.dump(blob, f)
    f.close()
