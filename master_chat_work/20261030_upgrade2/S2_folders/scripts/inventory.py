#!/usr/bin/env python3
"""Read-only inventory of Terminal Bench root and selected second levels."""
import csv
import os
import pathlib
import subprocess
from datetime import datetime

ROOT = pathlib.Path('/Users/mac/Desktop/Terminal Bench')
OUT = pathlib.Path(__file__).resolve().parent.parent
SECOND = {'master_chat_tasks', 'master_chat_work', 'QC', 'Terminal_2.0_Harbor_Harness'}
SOURCES = [ROOT/'master_chat_tasks', ROOT/'Terminal_2.0_Harbor_Harness'/'scripts']

def source_files():
    for root in SOURCES:
        for base, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', '.venv'}]
            for name in files:
                p = pathlib.Path(base)/name
                if p.stat().st_size <= 2_000_000 and p.suffix.lower() in {'.py','.sh','.md','.json','.jsonl','.toml','.yaml','.yml','.txt'}:
                    yield p

def ref_index(entries):
    # Match full root-relative paths first; basename matches are informational only.
    refs = {str(p): [] for p in entries}
    for src in source_files():
        try:
            lines = src.read_text(errors='replace').splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            for p in entries:
                rel = str(p.relative_to(ROOT))
                if rel in line or str(p) in line:
                    refs[str(p)].append(f'{src.relative_to(ROOT)}:{n}')
    return refs

def stats(p):
    count = 0
    oldest = newest = None
    if p.is_dir():
        for base, dirs, files in os.walk(p, followlinks=False):
            dirs[:] = [d for d in dirs if not (pathlib.Path(base)/d).is_symlink()]
            for name in files:
                f = pathlib.Path(base)/name
                try:
                    st = f.stat(follow_symlinks=False)
                except OSError:
                    continue
                count += 1
                oldest = st.st_mtime if oldest is None else min(oldest, st.st_mtime)
                newest = st.st_mtime if newest is None else max(newest, st.st_mtime)
    else:
        st = p.stat(follow_symlinks=False)
        count, oldest, newest = 1, st.st_mtime, st.st_mtime
    du = subprocess.run(['du','-sk',str(p)],capture_output=True,text=True).stdout.split('\t')[0]
    return count, int(du) if du.isdigit() else None, oldest, newest

def purpose(p):
    name = p.name
    if p.parent == ROOT:
        return {'master_chat_tasks':'master control, state, tools, prompts','master_chat_work':'session outputs and bundle work','QC':'QC reports and frozen copies','Terminal_2.0_Harbor_Harness':'separate harness clone, runs and task staging','anubis-stage-1':'teammate task repository','anubis-stage-2':'teammate task repository','Anubis_Tasks_Samples':'teammate samples','beta-task-generator':'task generator repository','harness_master_tasks':'older harness master records','master_chat':'older master records'}.get(name,'other project, backup, or personal folder (ownership unverified)')
    if p.parent.name == 'master_chat_work':
        return 'dated session output' if name[:8].isdigit() else 'bundle/QL/research working area'
    if p.parent.name == 'master_chat_tasks':
        return {'auto':'automation','prompts':'prompt templates and issued prompts','registry':'task and lever registry','tools':'control scripts','knowledge':'curated rules and playbooks'}.get(name,'master control record')
    if p.parent.name == 'QC':
        return {'copies':'frozen QC task copies','reports':'QC result reports','notes':'QC notes'}.get(name,'QC migration record or map')
    if p.parent.name == 'Terminal_2.0_Harbor_Harness':
        return {'jobs':'harness run jobs and trajectories','Tasks_INPUT':'staged task bundles','Output_RFP':'run outputs','Input_Bundle_QC':'QC kit','scripts':'harness scripts'}.get(name,'harness clone component or run artifact')
    return ''

def writer(p):
    rel=str(p.relative_to(ROOT))
    if rel.startswith('master_chat_tasks/auto/runs'): return 'auto.py runtime; INFERRED'
    if rel.startswith('master_chat_tasks/prompts/issued'): return 'tools/issue.py and master; INFERRED'
    if rel.startswith('master_chat_tasks/registry'): return 'tools/intake.py, issue.py, master; INFERRED'
    if rel.startswith('master_chat_tasks'): return 'master and master_chat_tasks tools; INFERRED'
    if rel.startswith('master_chat_work'): return 'worker sessions and master; INFERRED'
    if rel.startswith('QC'): return 'QC sessions and master; INFERRED'
    if rel.startswith('Terminal_2.0_Harbor_Harness'): return 'harness scripts or external harness project; INFERRED'
    if rel.startswith(('anubis-stage-','Anubis_Tasks_Samples','Aakrsh tasks','QC assigned','help others','job-search-skill')): return 'other owner/teammate; UNVERIFIED'
    return 'UNVERIFIED'

def active_ref(loc):
    return loc.startswith(('master_chat_tasks/tools/','Terminal_2.0_Harbor_Harness/scripts/')) or loc.startswith('master_chat_tasks/auto/auto.py:')

def main():
    entries = sorted(ROOT.iterdir())
    for parent in [ROOT/x for x in SECOND]:
        entries.extend(sorted(parent.iterdir()))
    refs = ref_index(entries)
    with (OUT/'INVENTORY.csv').open('w',newline='') as f:
        w=csv.writer(f)
        w.writerow(['path','level','type','du_kib','du_human','file_count','oldest_file_mtime','newest_file_mtime','purpose','writer_inferred','reference_locations','reader_status'])
        for p in entries:
            count,kib,old,new=stats(p)
            rel=str(p.relative_to(ROOT))
            level=1 if p.parent==ROOT else 2
            matched=refs[str(p)]
            w.writerow([rel,level,'dir' if p.is_dir() else 'file',kib,subprocess.run(['du','-sh',str(p)],capture_output=True,text=True).stdout.split('\t')[0],count,
                        datetime.fromtimestamp(old).isoformat(timespec='seconds') if old else '',datetime.fromtimestamp(new).isoformat(timespec='seconds') if new else '',
                        purpose(p),writer(p),';'.join(matched[:30]),
                        'active tool/script static reference (runtime read UNVERIFIED)' if any(active_ref(x) for x in matched) else 'historical/template static reference (runtime read UNVERIFIED)' if matched else 'no static reference in scan (reader UNVERIFIED)'])

if __name__=='__main__':
    main()
