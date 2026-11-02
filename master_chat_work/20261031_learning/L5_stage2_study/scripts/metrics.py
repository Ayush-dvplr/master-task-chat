#!/usr/bin/env python3
"""Rebuild L5 cohort metrics from read-only inventory and pushed registry."""
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median

OUT=Path(__file__).resolve().parents[1]
ROOT=Path('/Users/mac/Desktop/Terminal Bench')
rows=sorted(json.loads((OUT/'run_evidence.json').read_text()),key=lambda x:x['final'])[:10]
data_sizes={d['id']:sum(p.stat().st_size for p in (ROOT/'anubis-stage-2'/d['id']/'environment/data').rglob('*') if p.is_file()) for d in rows}
registry=json.loads((ROOT/'master_chat_tasks/registry/tasks.json').read_text())['tasks']
pushed=[r['slug'] for r in registry if r.get('pipeline',{}).get('stage')=='pushed']
out={
    'top10_ids':[d['id'] for d in rows],
    'median_final':median(d['final'] for d in rows),
    'median_tests':median(d['tests'] for d in rows),
    'median_rubric':median(d['rubric'] for d in rows),
    'median_test_checks':median(d['check_count'] for d in rows),
    'median_judge_criteria':median(d['judge_count'] for d in rows),
    'test_checks_range':[min(d['check_count'] for d in rows),max(d['check_count'] for d in rows)],
    'judge_criteria_range':[min(d['judge_count'] for d in rows),max(d['judge_count'] for d in rows)],
    'judge_loss_share_mean':mean((100-d['rubric'])/(2*(100-d['final'])) for d in rows),
    'category_counts':dict(Counter(d['category'] for d in rows)),
    'shipped_data_bytes':data_sizes,
    'shipped_data_bytes_range':[min(data_sizes.values()),max(data_sizes.values())],
    'shipped_data_bytes_median':median(data_sizes.values()),
    'pushed_count':len(pushed),
    'pushed_slugs':pushed,
}
(OUT/'metrics.json').write_text(json.dumps(out,indent=2)+'\n')
print('top10',len(rows),'pushed',len(pushed),'median_final',out['median_final'],'data_range',out['shipped_data_bytes_range'])
