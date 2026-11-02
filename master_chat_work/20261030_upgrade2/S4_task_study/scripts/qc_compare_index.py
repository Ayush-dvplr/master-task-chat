#!/usr/bin/env python3
"""Index QC 'Compared with' sections and P12 notes for manual fix-causality review."""
import csv, pathlib, re
TB=pathlib.Path('/Users/mac/Desktop/Terminal Bench')
OUT=pathlib.Path(__file__).resolve().parents[1]
rows=[]
for p in sorted((TB/'QC/reports').glob('*/v*.md')):
    lines=p.read_text(errors='replace').splitlines()
    starts=[i for i,l in enumerate(lines) if l.startswith('## Compared with')]
    if not starts: continue
    a=starts[-1]; b=next((i for i in range(a+1,len(lines)) if lines[i].startswith('## ')),len(lines))
    section=lines[a:b]
    for off,line in enumerate(section):
        if re.search(r'\bnew\b|introduced|regress|still open|fixed',line,re.I):
            rows.append({'kind':'qc_comparison','task':p.parent.name,'source':str(p)+':'+str(a+off+1),'line':line[:700]})
for p in sorted((TB/'master_chat_work').glob('*/p12_fix_*/RECHECK_FIX.md')):
    lines=p.read_text(errors='replace').splitlines()
    for i,line in enumerate(lines):
        if re.search(r'new finding|introduced|regress',line,re.I):
            rows.append({'kind':'p12_note','task':p.parts[-3],'source':str(p)+':'+str(i+1),'line':line[:700]})
with (OUT/'QC_COMPARE_INDEX.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('index rows',len(rows),'QC reports',len({r['source'].split(':')[0] for r in rows if r['kind']=='qc_comparison'}),'P12 notes',len({r['source'].split(':')[0] for r in rows if r['kind']=='p12_note'}))
new=[r for r in rows if r['kind']=='qc_comparison' and re.search(r'\bnew\b|introduced|regress',r['line'],re.I)
     and not re.search(r'new:\s*none|new in v\d+:?\s*$|^\s*### New\s*$',r['line'],re.I)]
for name,pat in [('judge_change',r'JD-|judge|rubric|R\d'),('test_change',r'TS-|test_output|check count'),
                 ('stale_docs',r'DS-22|AL-18|stale|TRUTH'),('coverage_gap',r'AL-27|AL-2|IN-16|CL-10|ungra'),
                 ('budget_or_timeout',r'timeout|concurr|budget|TS-11|AL-17')]:
    n=len({r['source'].split(':')[0] for r in new if re.search(pat,r['line'],re.I)})
    print(name,n,'of',len({r['source'].split(':')[0] for r in new}),'reports with new-mentioned lines; overlapping name/rule-code heuristic')
