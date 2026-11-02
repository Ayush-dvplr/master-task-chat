import csv
import json
import re
from pathlib import Path

ROOT = Path('/Users/mac/Desktop/Terminal Bench/master_chat_tasks')
OUT = Path(__file__).resolve().parents[1]
substantive = {
 391:'regrade',396:'regrade',455:'crash_timeout',458:'crash_timeout',464:'crash_timeout',
 479:'crash_timeout',504:'gate',506:'gate',508:'gate',514:'gate',525:'crash_timeout',
 542:'crash_timeout',544:'crash_timeout',
}
task_for_line = {
 391:'sentinel-policy-recompute',396:'sentinel-policy-recompute',
 455:'tariff-engine-audit-repair',458:'schema-migration-plan-repair',464:'schema-migration-plan-repair',479:'schema-migration-plan-repair',
 504:'tariff-engine-audit-repair;warrant-asof-entitlement-compiler',506:'warrant-asof-entitlement-compiler',508:'tariff-engine-audit-repair',514:'metered-usage-rating-pipeline',
 525:'outage-window-replan',542:'outage-window-replan',544:'cold-chain-backbone-quote',
}
rows=[]
for line_no,line in enumerate((ROOT/'decisions.jsonl').read_text().splitlines(),1):
 d=json.loads(line)
 decision=d.get('decision','')
 m=re.search(r'cap override for ([\w-]+)\s+(\w+)',decision)
 if m:
  rows.append(dict(source=f'decisions.jsonl:{line_no}',ist=d.get('ist',d.get('ts','')),task=m.group(1),category='administrative_'+m.group(2),decision=decision))
 elif line_no in substantive:
  task=task_for_line[line_no]
  rows.append(dict(source=f'decisions.jsonl:{line_no}',ist=d.get('ist',d.get('ts','')),task=task,category=substantive[line_no],decision=decision))
with (OUT/'EXCEPTIONS.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['source','ist','task','category','decision']);w.writeheader();w.writerows(rows)
print(f'{len(rows)} exception decision rows ({sum(x["category"].startswith("administrative") for x in rows)} administrative)')
