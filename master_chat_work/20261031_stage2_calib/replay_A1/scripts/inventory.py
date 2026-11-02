import csv
import json
from pathlib import Path

WORK = Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_stage2_calib/replay_A1')
rows = []
for task in ('billing', 'pm25', 'royalty'):
    root = WORK / 'evidence' / task
    details = json.loads((root / 'reward-details.json').read_text())
    for number, component in enumerate(details['reward']['components']):
        for index, criterion in enumerate(component['detail']['criteria']):
            weight, value = criterion['weight'], criterion['value']
            lost = weight * (1 - value) if weight > 0 else -weight * value
            rows.append({'task': task, 'component': component['name'], 'check': criterion.get('id', criterion['name']), 'name': criterion['name'], 'weight': weight, 'value': value, 'lost_raw_weight': lost, 'description': criterion['description'], 'reason': criterion.get('reasoning', ''), 'json_path': f'$.reward.components[{number}].detail.criteria[{index}]'})
    score = json.loads((root / 'score.json').read_text())
    print(task, json.dumps(score), 'summary=', (root / 'pass_summary.json').read_text())
with (WORK / 'RECORDED_CHECKS.csv').open('w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

summary = []
for path in sorted((WORK / 'evidence' / 'billing').glob('case_*.json')):
    item = json.loads(path.read_text())
    item['reports'].pop('__stdout__', None)
    item['fields_wrong'] = sum(report.get('fields_wrong', 1) for report in item['reports'].values())
    item['reports_wrong'] = [name for name, report in item['reports'].items() if not report.get('byte_equal', False)]
    path.write_text(json.dumps(item, indent=2, sort_keys=True) + '\n')
    summary.append({key: value for key, value in item.items() if key not in ('reports', 'clock_truth')})
(WORK / 'evidence' / 'billing' / 'diagnostics_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
