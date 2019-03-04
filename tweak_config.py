#!/usr/bin/env python
# -*- coding:utf-8 -*-
import os, sys, re, codecs, locale, shutil

PAT_EMAIL = r"^SRC_EMAIL\s*=\s*[\"\']([\w@\.-]+)[\"\'](.*)"

def Main():
    cfg_file = os.path.join(os.path.dirname(__file__), 'config.py')
    
    if not os.path.exists(cfg_file):
        print("Not exist 'config.py' or it's invalid, please download KindleEar again.")
        return 1

    slcfg = [] #string buffer for config.py
    with codecs.open(cfg_file, 'r', 'utf-8') as fcfg:
        slcfg = fcfg.read().split('\n')


    # modify config.py
    for index, line in enumerate(slcfg):
        mt = re.match(PAT_EMAIL, line)
        if mt:
            slcfg[index] = 'SRC_EMAIL = "%s"' % os.environ['SRC_EMAIL'] + mt.group(2)
            continue
    with codecs.open(cfg_file, 'w', 'utf-8') as fcfg:
        fcfg.write('\n'.join(slcfg))

    
if __name__ == '__main__':
    ret = Main()
    if ret:
        import sys
        sys.exit(ret)
        