#!/usr/bin/env python3
"""Build RECORDS.csv from the read-only field inventory snapshot."""
import csv
import json

evidence={
 'tasks':('tools/status.py:39-67; tools/intake.py:171-175 via status.py','YES: full-file read/modify/write has no lock; issue/status/intake can overlap'),
 'board':('tools/board.py:24-57; tools/issue.py:157-181; tools/intake.py:105-109; auto/auto.py:689-704','YES: board.py rewrites whole file without lock; issue/intake/auto can overlap'),
 'decisions':('tools/decide.py:41-69; tools/issue.py:176-180','YES: two append paths have no common lock'),
 'feedback':('README.md:52,77 (master append; no dedicated tool verified)','UNVERIFIED: master append may overlap another master process'),
 'lessons':('README.md:40,51,66,77 (master append; no dedicated tool verified)','UNVERIFIED: master append may overlap another master process'),
 'scores':('tools/intake.py:159-175','YES: append has no lock; score row and tasks update are separate operations'),
 'ideas':('README.md:54; prompts/templates/P1_chatgpt_ideas_v1.md:3 (master append)','UNVERIFIED: no tool writer located'),
 'log':('README.md:57 (retired/read-only)','NO current writer identified; historic writers UNVERIFIED'),
 'levers':('README.md:54,65 (master overwrite)','UNVERIFIED: no tool writer located; full-file overwrite if concurrent'),
 'peer_tasks':('tools/peer_manifest.py:88-100,150-203','YES: atomic rename prevents torn file but no cross-process lock; lost update possible'),
 'open_questions':('README.md:57 (retired/read-only)','NO current writer identified; historic writers UNVERIFIED'),
 'state':('README.md:45 (master overwrite)','UNVERIFIED: no dedicated writer located'),
 'auto_state':('auto/auto.py:225-248,805-833,1117-1137','MITIGATED: flock at auto/auto.py:227-237 for watcher/commands; audit each save call for lock coverage'),
 'auto_events':('auto/auto.py:219-223','YES: append has no lock; concurrent watcher/commands can interleave'),
 'auto_night_log':('auto/runs/20261025_0048_night/night.py (historic)','UNVERIFIED: historic writer only'),
 'queue_state':('Terminal_2.0_Harbor_Harness/scripts/master_queue.py:148-164,818-821,884-894','MITIGATED: flock + atomic rename; queue owns operational state'),
 'auto_hold':('auto/auto.py:1606-1620','YES: shared temp name and rename; two auto writers could race; expiring advisory hold'),
 'auto_scheduled':('auto/auto.py:858-859,899-914 (currently absent)','YES: whole-file writes without lock; no current file to inspect'),
 'generator_ideas':('prompts/templates/_COMMON_RULES_v5.md:34 (generator memory path)','UNVERIFIED: generator writer/concurrency not traced; working memory outside master state'),
 'fingerprint_qc':('prompts/templates/CHANGELOG.md:40 (fingerprint revision; writer UNVERIFIED)','UNVERIFIED: manual update path; no dedicated writer located'),
 'fingerprint_generator':('knowledge/fingerprints/pl_generator.json (writer UNVERIFIED)','UNVERIFIED: manual update path; no dedicated writer located'),
 'knowledge_intake':('knowledge/archive_md/log.md:8-11 (historic digest/map)','NO current writer identified; historic writer UNVERIFIED'),
 'qc_result':('prompts/templates/P11_full_qc_v3.md:105 (worker writes per SHA)','LOW: distinct SHA file; same-session retry can overwrite; no lock verified'),
 'pending.history':('tools/pending.py:37-49,71-73,126-157','SQLite serializes writes; item and history commit together'),
 'pending.items':('tools/pending.py:37-49,61-68,126-157','YES: next_id SELECT before INSERT can collide across processes; SQLite prevents duplicate PK but second add fails'),
}
paths={
 'tasks':'master_chat_tasks/registry/tasks.json','board':'master_chat_tasks/board.json',
 'decisions':'master_chat_tasks/decisions.jsonl','feedback':'master_chat_tasks/feedback.jsonl',
 'lessons':'master_chat_tasks/lessons.jsonl','scores':'master_chat_tasks/registry/scores.jsonl',
 'ideas':'master_chat_tasks/registry/ideas.jsonl','log':'master_chat_tasks/log.jsonl',
 'levers':'master_chat_tasks/registry/levers.json','peer_tasks':'master_chat_tasks/registry/peer_tasks.json',
 'open_questions':'master_chat_tasks/open_questions.json','state':'master_chat_tasks/state.json',
 'auto_state':'master_chat_tasks/auto/runs/*/state.json',
 'auto_events':'master_chat_tasks/auto/runs/*/events.jsonl',
 'auto_night_log':'master_chat_tasks/auto/runs/*/night_log.jsonl',
 'queue_state':'Terminal_2.0_Harbor_Harness/.master-queue/state.json',
 'auto_hold':'Terminal_2.0_Harbor_Harness/.master-queue/auto_hold.json',
 'auto_scheduled':'master_chat_tasks/auto/SCHEDULED.json',
 'generator_ideas':'master_chat_work/gen_memory/ideas.jsonl',
 'fingerprint_qc':'master_chat_tasks/knowledge/fingerprints/qc.json',
 'fingerprint_generator':'master_chat_tasks/knowledge/fingerprints/pl_generator.json',
 'knowledge_intake':'master_chat_tasks/knowledge/intake/*.json',
 'qc_result':'QC/reports/*/result_*.json',
 'pending.history':'master_chat_tasks/pending.db:history',
 'pending.items':'master_chat_tasks/pending.db:items',
}
with open('RECORDS.csv','w',newline='') as f:
 w=csv.writer(f)
 w.writerow(['record','path_or_pattern','file_count','row_count','fields_seen_with_occurrence_counts','writers_evidence','race_assessment'])
 for line in open('inventory.jsonl'):
  d=json.loads(line); name=d['group'];
  flds=d.get('fields',{})
  parts=[f'{k}={v["count"]}' for k,v in flds.items()]
  for k,v in d.get('nested',{}).items():
   parts.append(k+'[]('+','.join(f'{a}={b["count"]}' for a,b in v['fields'].items())+')')
  if 'columns' in d: parts=[f'{col}={d["rows"]} (column; nullable values not counted)' for col in d['columns']]
  w.writerow([name,paths[name],d.get('files',1),d.get('root_or_rows',d.get('rows')), '; '.join(parts),*evidence[name]])
