#!/usr/bin/env python3
"""Extract literal filesystem-looking strings from move-sensitive control sources."""
import csv
import pathlib
import re

ROOT = pathlib.Path('/Users/mac/Desktop/Terminal Bench')
M = ROOT/'master_chat_tasks'
OUT = pathlib.Path(__file__).resolve().parent.parent
TARGETS = [M/'tools',M/'auto',M/'prompts'/'templates',M/'auto'/'AUTO_POLICY.md',ROOT/'Terminal_2.0_Harbor_Harness'/'scripts']
QUOTED = re.compile(r'''(?P<q>['"`])(?P<s>[^'"`\n]{1,500})(?P=q)''')
PATHBITS = re.compile(r'(?:/Users/|/tmp/|~/|\$\{?\w+\}?/|\.\.?/|master_chat_tasks/|master_chat_work/|Terminal_2\.0_Harbor_Harness/|QC/|Tasks_INPUT/|Output_RFP/|jobs/|bundles/|registry/|prompts/|knowledge/|tools/|auto/|scripts/)')
URL = re.compile(r'^(?:https?://|file://|sqlite://)')

def files():
    seen=set()
    for t in TARGETS:
        found=[t] if t.is_file() else t.rglob('*')
        for p in found:
            if p in seen or not p.is_file() or p.suffix not in {'.py','.sh','.md','.toml','.json','.yaml','.yml','.txt'}:
                continue
            if '__pycache__' in p.parts or '.venv' in p.parts: continue
            seen.add(p)
            yield p

def main():
    rows=[]
    for p in files():
        try: lines=p.read_text(errors='replace').splitlines()
        except OSError: continue
        for i,line in enumerate(lines,1):
            found=[]
            for m in QUOTED.finditer(line):
                s=m.group('s').strip()
                if PATHBITS.search(s) and not URL.match(s):
                    found.append(s)
            for s in dict.fromkeys(found):
                if len(s)>250: continue
                cls='absolute' if s.startswith(('/','~')) else 'variable' if s.startswith('$') else 'relative'
                rows.append((f'{p.relative_to(ROOT)}:{i}',s,cls,'may break if referenced target moves; validate caller'))
    with (OUT/'PATH_REFS.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['source_line','path_string','kind','move_impact']);w.writerows(rows)
    print(f'{len(rows)} path string references across {len(set(x[0].split(":")[0] for x in rows))} files')

if __name__=='__main__': main()
