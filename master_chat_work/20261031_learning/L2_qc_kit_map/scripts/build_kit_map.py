#!/usr/bin/env python3
"""Read-only inventory of live QC IDs and literal failure mentions."""
import csv
import re
from collections import defaultdict
from pathlib import Path

TB = Path('/Users/mac/Desktop/Terminal Bench')
KIT = TB / 'Terminal_2.0_Harbor_Harness/Input_Bundle_QC'
OUT = Path(__file__).resolve().parents[1]
FILES = [
    ('01_Instruction_QC.md', r'IN-\d+'),
    ('02_Data_Solution_QC.md', r'DS-\d+'),
    ('03_Tests_QC.md', r'TS-\d+'),
    ('04_Judge_QC.md', r'JD-\d+'),
    ('05_Alignment_Integrity_QC.md', r'AL-\d+'),
    ('Final_checklist.md', r'CL-\d+'),
]
EXTRA_PATTERNS = {
    '01_Instruction_QC.md': r'IN-(?:0|F1|L[1-3]|S\d+)',
    '03_Tests_QC.md': r'TS-(?:0|S\d+)',
    '04_Judge_QC.md': r'JD-(?:0|S\d+)',
    '05_Alignment_Integrity_QC.md': r'AL-F0[a-e]',
    'Final_checklist.md': r'(?:F0[a-e]|FC-S\d+)',
}
SCRIPTS = {
    'structure_qc.py': r'[STX]\d+',
    'instruction_qc.py': r'[PC]\d+',
    'tests_qc.py': r'(?:[AWDBKROH]\d+)',
    'judge_qc.py': r'[JG]\d+',
}
MANUAL = {'IN-5','IN-8','IN-9','IN-12','IN-13','IN-14','IN-15','IN-16','IN-17',
          'DS-2','DS-3','DS-4','DS-6','DS-10','DS-14','DS-15','DS-19','DS-20',
          'DS-21','DS-22','DS-24','DS-25','DS-26','DS-27', 'TS-5','TS-7','TS-11',
          'TS-12','TS-13','TS-14','TS-15','TS-16','TS-17','TS-18','TS-19','TS-20',
          'TS-24','TS-25','TS-26','TS-27','TS-28','TS-29','TS-30',
          *[f'JD-{n}' for n in range(5,19)], *[f'AL-{n}' for n in range(1,29)],
          *[f'CL-{n}' for n in range(1,11)]}

def short(s):
    s = re.sub(r'[`*]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # Keep the entire first sentence if possible; long rules are clipped to one line.
    m = re.search(r'(?<!\b[A-Z])\.\s', s)
    if m and m.start() > 24:
        s = s[:m.start()+1]
    return s[:240].rstrip(' ,;:')

def failure_counts():
    by_id = defaultdict(set)
    reports = list((TB/'QC/reports').glob('*/v*.md'))
    # L1's finding rows point back to the versioned report line and avoid
    # counting historical mentions, pass checkboxes and cross-references.
    parsed = TB/'master_chat_work/20261031_learning/L1_qc_fixes/QC_FINDINGS.csv'
    if parsed.exists():
        for row in csv.DictReader(parsed.open()):
            if row['severity'] == '❌' and row['check_id'] != 'UNVERIFIED':
                by_id[row['check_id']].add(row['task'])
    else:
        for p in reports:
            for line in p.read_text(errors='replace').splitlines():
                if '❌' not in line: continue
                for ident in set(re.findall(r'\b(?:IN|DS|TS|JD|AL|CL)-\d+\b',line)):
                    by_id[ident].add(p.parent.name)
    return by_id, len(reports)

def iter_rows():
    for fn, pat in FILES:
        for n, line in enumerate((KIT/fn).read_text().splitlines(),1):
            m = re.match(r'^- (?:\[ \] )?('+pat+r')\b[ .-]*(.*)', line)
            if m:
                yield m.group(1), fn, n, short(m.group(2))
    for fn, pat in EXTRA_PATTERNS.items():
        for n, line in enumerate((KIT/fn).read_text().splitlines(),1):
            m = re.match(r'^- (?:\[ \] )?('+pat+r')\b\s*(.*)', line)
            if m:
                ident=m.group(1)
                # A checklist range inherits each script check separately.
                if line.startswith(('- [ ] '+ident+'..','- '+ident+'..')):
                    continue
                yield ident, fn, n, short(m.group(2))
        if fn == 'Final_checklist.md':
            for n,line in enumerate((KIT/fn).read_text().splitlines(),1):
                m=re.match(r'^- (FC-S\d+)\b\s*(.*)',line)
                if m: yield m.group(1),fn,n,short(m.group(2))
    for fn, pat in SCRIPTS.items():
        for n, line in enumerate((KIT/fn).read_text().splitlines(),1):
            m = re.match(r'^  ('+pat+r')\s{1,}(.*)', line)
            if m and len(m.group(2)) > 12:
                yield m.group(1), fn, n, short(m.group(2))

def action(ident, fn, demand):
    if fn.endswith('.py'):
        return f'Run {fn} on the bundle; inspect any {ident} finding and correct the named file or value.'
    if ident == 'IN-10': return 'No check: leave the online-lookup sentence decision to the tasker.'
    if ident == 'AL-27': return 'Create a graded fixture for each rule; for precedence, include both conditions, then show a one-rule mutant loses points.'
    if ident == 'DS-22': return 'Regenerate TRUTH.md digests, counts and examples from the final shipped bytes after every other edit.'
    if ident in {'AL-2','CL-1'}: return 'List each instruction action or promise and name the test or criterion that directly observes it.'
    if ident in {'IN-8','DS-21','TS-19','AL-1','CL-10','F0e','AL-F0e'}:
        return 'For every graded fact, cite a prompt sentence or a determinate copied-input fact; prove no hidden-only convention is required.'
    if ident in {'CL-2','F0c','AL-F0c'}:
        return 'Score a hand-written plausible forgery and empty stub; list the positive checks they earn and why.'
    if ident == 'CL-4': return 'Change exactly one independent output fact and report the score; state exact whole-document grading if that is intended.'
    if ident in {'JD-7','AL-6'}: return 'Trace each criterion against actual oracle behaviour and its final artifact; correct contradictions.'
    return f'At build time, verify this exact requirement in the named files: {demand}'

def breakage(ident):
    if ident in {'IN-8','DS-21','DS-25','TS-19','AL-1','CL-5','CL-10'}:
        return 'Adding hidden assertions or renaming output keys can make a graded fact unreachable.'
    if ident in {'IN-17','IN-9','DS-4','AL-13','CL-3'}:
        return 'A contract fix can reveal the answer or a discoverable trap.'
    if ident in {'TS-13','TS-20','TS-25','TS-26','JD-8','JD-14','AL-28','CL-2','CL-4'}:
        return 'Adding or combining checks can pay twice, reward a fake, or create a one-fact score cliff.'
    if ident in {'AL-27','AL-2','CL-1'}:
        return 'A new promise or branch can remain untriggered by every graded fixture.'
    if ident in {'JD-7','AL-5','DS-22','CL-8'}:
        return 'Changing the oracle or data can stale the judge, tests or TRUTH provenance.'
    if ident in {'TS-24','TS-28','TS-30','AL-12','CL-9'}:
        return 'Verifier hardening can make owner-only agent files unreadable or let setup supply the answer.'
    return 'A related edit can stale paths, weights, wording, or copied bundle facts; rerun this check.'

def main():
    fails, nreports = failure_counts()
    rows=[]; seen=set()
    for ident, fn, line, demand in iter_rows():
        key=(fn,ident)
        if key in seen: continue
        seen.add(key)
        auto='yes' if fn.endswith('.py') else ('no' if ident in MANUAL else 'partly')
        rows.append({'id':ident,'file_line':f'Terminal_2.0_Harbor_Harness/Input_Bundle_QC/{fn}:{line}',
                     'demand':demand,'automatable':auto,'failed_tasks':len(fails[ident]),
                     'build_action':action(ident,fn,demand),'fix_can_break':breakage(ident)})
    with (OUT/'KIT_MAP.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    print(f'{len(rows)} rows; {nreports} reports; {len(set(p.parent.name for p in (TB/"QC/reports").glob("*/v*.md")))} task slugs')
    print('top failures:',sorted(((k,len(v)) for k,v in fails.items() if '-' in k),key=lambda x:-x[1])[:20])

if __name__=='__main__': main()
