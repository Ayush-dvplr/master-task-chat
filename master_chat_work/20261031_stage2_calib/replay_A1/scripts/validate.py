import csv
import json
from collections import Counter
from pathlib import Path

WORK = Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_stage2_calib/replay_A1')
with (WORK / 'CAUSES.csv').open() as handle:
    reader = csv.DictReader(handle)
    assert reader.fieldnames == 'task,check,weight,cause,root_fact,doc_ref,agent_ref,expected,actual,fields_wrong,notes'.split(',')
    causes = list(reader)
with (WORK / 'JUDGE_LOSS.csv').open() as handle:
    reader = csv.DictReader(handle)
    assert reader.fieldnames == 'task,criterion,weight,class,what_it_asks,what_agent_did'.split(',')
    judges = list(reader)
summary = {'cause_rows': len(causes), 'judge_rows': len(judges), 'tasks': []}
for task in ('billing', 'pm25', 'royalty'):
    components = json.loads((WORK / 'evidence' / task / 'reward-details.json').read_text())['reward']['components']
    tests = next(component['detail'] for component in components if component['name'] == 'test_output')
    judge = next(component['detail'] for component in components if component['name'] == 'judge')
    expected_tests = {item['name']: item['weight'] for item in tests['criteria'] if item['weight'] > 0 and not item['value']}
    actual_tests = Counter()
    for row in causes:
        if row['task'] == task:
            actual_tests[row['check']] += float(row['weight'])
            assert row['doc_ref'] and row['agent_ref'] and row['expected'] and row['actual']
    assert dict(actual_tests) == expected_tests, (task, actual_tests, expected_tests)
    expected_judges = {item['id'] + ' ' + item['name']: abs(item['weight']) for item in judge['criteria'] if (item['weight'] > 0 and not item['value']) or (item['weight'] < 0 and item['value'])}
    actual_judges = {row['criterion']: float(row['weight']) for row in judges if row['task'] == task}
    assert actual_judges == expected_judges
    assert len(actual_judges) == sum(row['task'] == task for row in judges)
    summary['tasks'].append({'task': task, 'failed_test_checks': len(expected_tests), 'lost_test_raw_weight': sum(actual_tests.values()), 'lost_judge_criteria': len(actual_judges), 'lost_judge_raw_weight': sum(actual_judges.values())})
    card = (WORK / f'TASK_{task}.md').read_text()
    assert all(gate in card for gate in ('IN-8', 'IN-17', 'AL-1', 'AL-27', 'CL-4'))
result = json.loads((WORK / 'result_3d517b2.json').read_text())
assert result['sha'] == '3d517b2' and result['status'] == 'DONE'
assert Path(result['report']).read_text().startswith('VERDICT: ')
assert all(task['oracle_tests'] == 100 and abs(task['recorded_tests'] - task['replay_tests']) < 0.5 for task in result['tasks'])
assert all(abs(sum(task['by_cause'].values()) - task['lost_test_pts']) < 1e-8 for task in result['tasks'])
assert len(causes) == 66 and len(judges) == 32
assert sum(float(row['weight']) for row in causes) == 230
assert sum(float(row['weight']) for row in judges) == 138
assert '- [ ]' not in (WORK / 'TODO.md').read_text()
summary['status'] = 'PASS'
(WORK / 'VALIDATION.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
