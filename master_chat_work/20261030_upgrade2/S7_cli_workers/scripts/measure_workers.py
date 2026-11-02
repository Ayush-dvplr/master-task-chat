#!/usr/bin/env python3
"""Read-only measurement of board-linked opencode worker sessions."""
import csv
import json
import sqlite3
import statistics
from pathlib import Path

ROOT = Path('/Users/mac/Desktop/Terminal Bench')
OUT = Path(__file__).resolve().parents[1]
board = json.loads((ROOT / 'master_chat_tasks/board.json').read_text())['rows']
db = sqlite3.connect('file:/Users/mac/.local/share/opencode/opencode.db?mode=ro', uri=True)
db.row_factory = sqlite3.Row
sessions = {r['title']: r for r in db.execute(
    'select title, id, parent_id, time_created, time_updated, tokens_input, '
    'tokens_output, tokens_reasoning, tokens_cache_read, tokens_cache_write, cost '
    'from session where parent_id is null') if len(r['title']) == 7}
rows = []
for b in board:
    step = b['step'].split()[0]
    if step not in ('P2', 'P9', 'P11', 'P12', 'P13') or b['status'] != 'done':
        continue
    s = sessions.get(b['sha'])
    if s is None:
        continue
    rows.append(dict(step=step, sha=b['sha'], slug=b['slug'], issued=b['issued'],
                     started_utc_ms=s['time_created'], updated_utc_ms=s['time_updated'],
                     span_min=round((s['time_updated']-s['time_created'])/60000, 1),
                     input=s['tokens_input'], output=s['tokens_output'],
                     reasoning=s['tokens_reasoning'], cache_read=s['tokens_cache_read'],
                     cache_write=s['tokens_cache_write'], cost_usd=s['cost']))
with (OUT/'worker_measurements.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, rows[0].keys()); w.writeheader(); w.writerows(rows)
def med(rr, key):
    return round(statistics.median(x[key] for x in rr), 2) if rr else None
for period, rr in [('all', rows), ('issued_2026-10-24_onward', [r for r in rows if r['issued'][:10] >= '2026-10-24'])]:
    for step in ('P11','P12','P13','P9','P2'):
        sub = [r for r in rr if r['step']==step]
        print(json.dumps(dict(period=period, step=step, n=len(sub),
              date_min=min((x['issued'] for x in sub), default=None),
              date_max=max((x['issued'] for x in sub), default=None),
              span_min_med=med(sub,'span_min'), output_med=med(sub,'output'),
              reasoning_med=med(sub,'reasoning'), cache_read_med=med(sub,'cache_read'),
              cache_write_med=med(sub,'cache_write'), input_med=med(sub,'input'),
              cost_usd_med=med(sub,'cost_usd'))))
print('board_done_counts', {step:sum(x['step'].split()[0]==step and x['status']=='done' for x in board) for step in ('P11','P12','P13','P9','P2')})
