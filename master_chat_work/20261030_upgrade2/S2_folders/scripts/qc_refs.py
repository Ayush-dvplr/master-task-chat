#!/usr/bin/env python3
"""Count QC copy IDs mentioned in reports and master JSON/JSONL, read-only."""
from pathlib import Path

R=Path('/Users/mac/Desktop/Terminal Bench')
reports='\n'.join(p.read_text(errors='replace') for p in (R/'QC/reports').rglob('*') if p.is_file() and p.stat().st_size<1_000_000)
records='\n'.join(p.read_text(errors='replace') for p in (R/'master_chat_tasks').glob('*.json*') if p.is_file() and p.stat().st_size<1_000_000)
items=[p for p in (R/'QC/copies').iterdir() if p.is_dir()]
print('copy_dirs',len(items),'in_reports',sum(p.name in reports for p in items),'in_master_records',sum(p.name in records for p in items),'in_neither',sum(p.name not in reports and p.name not in records for p in items))
