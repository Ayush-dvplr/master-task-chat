import csv
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path('/Users/mac/Desktop/Terminal Bench/master_chat_tasks')
OUT = Path(__file__).resolve().parents[1]
tasks = json.loads((ROOT/'registry/tasks.json').read_text())['tasks']
rows = json.loads((ROOT/'board.json').read_text())['rows']
family = {
 'vendor-archive-roundtrip-recovery':'format recovery; stated rules',
 'schema-migration-plan-repair':'held-out large gated graphs; repair',
 'metered-usage-rating-pipeline':'stated rating rules; later hidden scale',
 'tariff-engine-audit-repair':'stated tariff rules; later hidden scale',
 'data-product-config-compiler':'stated config rules',
 'cold-chain-backbone-quote':'Steiner/optimization hidden scale',
 'cleanroom-window-schedule':'interval DP',
 'counter-page-crash-recovery':'WAL replay',
 'flood-repair-portfolio':'tree-decomposition DP',
 'batch-lease-scheduler-replay':'stateful replay',
 'fuel-card-settlement-consolidation':'stated settlement; redesign planned',
 'pilotage-dues-reconstruction':'stated reconstruction; redesign planned',
 'outage-window-replan':'hidden optimization lanes',
 'warrant-asof-entitlement-compiler':'held-out conventions; intake build',
}
reasons = {
 'vendor-archive-roundtrip-recovery':'killed: real run 100/100/100',
 'schema-migration-plan-repair':'pushed: a7 32.12; gated worlds; all 390 lost test pts WRONG',
 'metered-usage-rating-pipeline':'pushed by Ayush at 44.05; misses general <40 gate',
 'tariff-engine-audit-repair':'pushed by Ayush at 47.84; misses general <40 gate',
 'data-product-config-compiler':'parked: fresh blind 19/19 right; no credible lever',
 'cold-chain-backbone-quote':'pushed: a5 29.06; 57.5% crash/timeout allowance',
 'cleanroom-window-schedule':'parked: blind 3/3 ~100',
 'counter-page-crash-recovery':'parked: blind 3/3 95/95',
 'flood-repair-portfolio':'parked: only 1/3 blind miss; two found DP',
 'batch-lease-scheduler-replay':'parked: blind 3/3 139/139',
 'fuel-card-settlement-consolidation':'parked: design blind exact; redesign requested',
 'pilotage-dues-reconstruction':'parked: design blind exact; redesign requested',
 'outage-window-replan':'pushed: a1 34.78; 74 test pts WRONG in paid run',
 'warrant-asof-entitlement-compiler':'pushed: a2 37.66; held-out convention',
}
with (OUT/'BUILDS.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['slug','kind','idea_lever_family_INFERRED','first_observed','last_observed','calendar_days_inclusive','board_rows_all','board_rows_done','harden_or_redesign_rows_observed','qc_rows_observed','outcome','pushed_final','reason','evidence'])
 w.writeheader()
 for i,t in enumerate(tasks):
  s=t['slug']
  if s not in family: continue
  rr=[r for r in rows if r.get('slug')==s]
  dates=[x.get('issued','')[:10] for x in rr if re.match(r'2026-10-\d\d',x.get('issued',''))]
  created=t.get('created_ist') or ''
  if re.match(r'2026-10-\d\d',created):dates.append(created[:10])
  stage_since=t.get('pipeline',{}).get('stage_since','')
  if re.match(r'2026-10-\d\d',stage_since): dates.append(stage_since[:10])
  elif re.match(r'10-\d\d',t.get('pipeline',{}).get('updated','')): dates.append('2026-'+t['pipeline']['updated'][:5])
  lo=min(dates) if dates else '';hi=max(dates) if dates else ''
  p=t.get('pipeline',{})
  w.writerow(dict(slug=s,kind=p.get('kind',''),idea_lever_family_INFERRED=family[s],first_observed=lo,last_observed=hi,calendar_days_inclusive=(date.fromisoformat(hi)-date.fromisoformat(lo)).days+1 if lo else '',board_rows_all=len(rr),board_rows_done=sum(r.get('status')=='done' for r in rr),harden_or_redesign_rows_observed=sum(bool(re.search(r'harden|redesign|rebuild',r.get('step',''),re.I)) for r in rr),qc_rows_observed=sum(bool(re.search(r'\bP11\b|\bQC\b',r.get('step',''),re.I)) for r in rr),outcome=p.get('stage',''),pushed_final=p.get('traj_overall','') if p.get('stage')=='pushed' else '',reason=reasons[s],evidence=f'registry/tasks.json $.tasks[{i}].pipeline; board.json $.rows[slug={s}]'))
