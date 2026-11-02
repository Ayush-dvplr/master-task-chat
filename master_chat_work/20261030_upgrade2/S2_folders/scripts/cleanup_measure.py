#!/usr/bin/env python3
"""Read-only age and disk-use measurements; age alone never authorizes deletion."""
import os
import pathlib
import subprocess
import time

R=pathlib.Path('/Users/mac/Desktop/Terminal Bench')
W=R/'master_chat_work'
H=R/'Terminal_2.0_Harbor_Harness'
NOW=time.time()

def children(p):
    return [x for x in p.iterdir() if x.is_dir()] if p.exists() else []

def gate_runs():
    return [p for p in W.rglob('gate_run_a*') if p.is_dir()]

def newest(p):
    ts=0
    for base,dirs,files in os.walk(p):
        for f in files:
            try: ts=max(ts,(pathlib.Path(base)/f).stat().st_mtime)
            except OSError: pass
    return ts or p.stat().st_mtime

def kib(p):
    s=subprocess.run(['du','-sk',str(p)],capture_output=True,text=True).stdout
    return int(s.split('\t')[0]) if s else 0

def report(name,paths):
    items=[(p,kib(p),(NOW-newest(p))/86400) for p in paths]
    total=sum(x[1] for x in items)
    seven=[x for x in items if x[2]>=7]
    fourteen=[x for x in items if x[2]>=14]
    thirty=[x for x in items if x[2]>=30]
    print(f'{name}: count={len(items)} total_kib={total} age7_count={len(seven)} age7_kib={sum(x[1] for x in seven)} age14_count={len(fourteen)} age14_kib={sum(x[1] for x in fourteen)} age30_count={len(thirty)} age30_kib={sum(x[1] for x in thirty)}')

report('jobs',children(H/'jobs'))
report('gate_runs',gate_runs())
report('qc_copies',children(R/'QC'/'copies'))
report('tmp_oracle',children(pathlib.Path('/tmp/oracle-qc')))
report('tmp_harbor',children(pathlib.Path('/tmp/harbor-jobs-qc')))
report('bundle_work',children(W/'bundles'/'_work'))
report('issued_prompts',children(R/'master_chat_tasks'/'prompts'/'issued'))
