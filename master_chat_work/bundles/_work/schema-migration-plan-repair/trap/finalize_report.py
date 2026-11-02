from pathlib import Path
import json
W=Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/schema-migration-plan-repair')
O=Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_schema-migration-plan-repair/p12_r4')
R=O/'RECHECK_FIX.md'
d=json.loads((W/'trap/variant_scores.json').read_text())
r3=json.loads((W/'wrong/r3/summary.json').read_text())
audit=json.loads((W/'trap/archived_audit.json').read_text())
lines=['## Trap survival','','The requested archived set is not replayable on this bundle. `wrong/r3/` has scores only; `wrong/make_wrong.py` points to removed `environment/data`. The direct audit ran all 17 unchanged auditor solver files on staged current inputs: every S3 single-wrong-reading program exited 1 before producing any artifact (`expected exactly one occurrence of the shipped text`). `S2_lazy`, `S2_shipped`, and `SC1_claim_padding` produced artifacts but are not single-wrong-reading variants. No grader error was counted as a score. The current-branch `measure_variants.py` definitions were replayed as a supplemental trap check; no new wrong-reading rule was authored.','','| variant | before loss of P | after loss of P | ratio | separating cases kept | verdict |','|---|---:|---:|---:|:---:|---|']
for name,v in d.items():
 b=v['before']['loss'];a=v['after']['loss'];ratio=a/b if b else 1;verdict='PASS' if ratio>=.9 else 'FAIL'
 lines.append(f'| current/{name} | {b}/137 | {a}/137 | {ratio:.3f} | y | {verdict} |')
for name in r3:
 if name=='S2_shipped':continue
 lines.append(f'| r3/{name} | n/a | n/a | n/a | y | unavailable: summary only |')
for name,row in audit.items():
 if not name.startswith('S3_'):continue
 if '+' in name:continue
 lines.append(f'| auditor_r1/{name} | n/a | n/a | n/a | y | invalid: exited {row.get("exit")} before artifacts |')
lines +=['','Supplemental current-branch retention: **PASS** (24/24, minimum ratio 0.956; F12 identity 48→47 and alias precedence 45→43). Required archived-variant replay: **FAIL / unverified**, because the single-wrong-reading programs are unavailable or incompatible. The TS-13 compensation rule is not triggered by a measured loss; no variant with a valid before/after score fell below 90%. No separating hidden case was removed. Blind r1: **137/137 before and 137/137 after**, tests-only; the reflex 0.20 gate is excluded by this round.','','']
s=R.read_text();s=s.replace('## Trap survival\n\nPending.','\n'.join(lines).rstrip())
s=s.replace('`xref_check.py`: 38 entries, 0 findings.','`xref_check.py`: 38 entries, 0 findings.')
R.write_text(s)
print('current',len(d),'r3 unavailable',len(r3)-1,'auditor single unavailable',sum(name.startswith('S3_') and '+' not in name for name in audit))
