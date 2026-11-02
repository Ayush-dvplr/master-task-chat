#!/usr/bin/env python3
"""Measure proposed master-only repo and report possible secrets by location only."""
import pathlib
import re
from collections import Counter

ROOT=pathlib.Path('/Users/mac/Desktop/Terminal Bench/master_chat_tasks')
EXCLUDE={'pending.db','log.jsonl','.DS_Store'}
EXCLUDE_PARTS={'__pycache__','.git','.venv'}
PAT=re.compile(r'key|token|secret|password|sk-',re.I)

def files():
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.name in EXCLUDE or any(x in EXCLUDE_PARTS for x in p.parts): continue
        if p.is_relative_to(ROOT/'auto'/'runs'): continue
        yield p

def main():
    hits=[]; total=0; count=0; cats=Counter()
    for p in files():
        count+=1; total+=p.stat().st_size
        cats[p.relative_to(ROOT).parts[0]]+=p.stat().st_size
        if p.stat().st_size>2_000_000: continue
        try:
            with p.open('r',errors='replace') as f:
                for i,line in enumerate(f,1):
                    if PAT.search(line): hits.append(f'{p.relative_to(ROOT)}:{i}')
        except (OSError,UnicodeError): continue
    print(f'candidate files={count} bytes={total} possible-secret-line-locations={len(hits)}')
    print('category bytes:',dict(cats))

if __name__=='__main__': main()
