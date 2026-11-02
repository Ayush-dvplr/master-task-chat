import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

WORK = Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_stage2_calib/replay_A1')
SCRATCH = Path('/Users/mac/Desktop/Terminal Bench/_runs/20261031/stage2-calib/replay-3d517b2')
BASE = Path('/Users/mac/Desktop/Terminal Bench/anubis-stage-2')
IDS = {'billing': '59417607-2254-5165-b703-0d5a4aeb7367', 'pm25': '98ed74c1-19ac-5ec8-adaf-392a172d4600', 'royalty': '75407a55-6665-505e-95d8-5ff9bdb3384f'}
with (WORK / 'CAUSES.csv').open() as handle:
    causes = list(csv.DictReader(handle))
results, runs, integrity = [], [], []
for task, task_id in IDS.items():
    evidence = WORK / 'evidence' / task
    recorded = json.loads((evidence / 'reward-details.json').read_text())
    original = next(item['detail'] for item in recorded['reward']['components'] if item['name'] == 'test_output')
    denominator = sum(item['weight'] for item in original['criteria'] if item['weight'] > 0)
    scores = {}
    for mode in ('oracle', 'replay'):
        paths = list((SCRATCH / 'jobs' / f'a3-{task}-{mode}').glob('*/verifier/reward-details.json'))
        assert len(paths) == 1, (task, mode, paths)
        path = paths[0]
        reward = json.loads(path.read_text())
        component = next(item['detail'] for item in reward['reward']['components'] if item['name'] == 'test_output')
        score = component['score'] / denominator * 100
        scores[mode] = score
        same = {item['name']: item['value'] for item in component['criteria']} == {item['name']: item['value'] for item in original['criteria']}
        assert score == 100 if mode == 'oracle' else same, (task, mode, score, same)
        for filename in ('reward-details.json', 'test-stdout.txt', 'reward.json'):
            shutil.copy2(path.parent / filename, evidence / f'{mode}_{filename}')
        runs.append({'task': task, 'mode': mode, 'tests_percent': score, 'raw_score': component['score'], 'positive_weight': denominator, 'all_criteria_match_recorded': same, 'source': str(path)})
    by_cause = Counter()
    for row in causes:
        if row['task'] == task and float(row['weight']):
            by_cause[row['cause']] += float(row['weight']) / denominator * 100
    recorded_percent = original['score'] / denominator * 100
    assert abs(scores['replay'] - recorded_percent) < 0.5
    assert abs(sum(by_cause.values()) - (100 - recorded_percent)) < 1e-8
    results.append({'task': task, 'recorded_tests': round(recorded_percent, 2), 'replay_tests': round(scores['replay'], 2), 'oracle_tests': round(scores['oracle'], 2), 'lost_test_pts': 100 - recorded_percent, 'by_cause': dict(by_cause)})
    for source in (BASE / task_id).rglob('*'):
        if not source.is_file() or 'trajectories' in source.relative_to(BASE / task_id).parts:
            continue
        relative = source.relative_to(BASE / task_id)
        if str(relative) in ('environment/Dockerfile', 'tests/Dockerfile', 'tests/reward.toml', 'tests/judge.toml'):
            continue
        target = SCRATCH / f'{task}-oracle' / relative
        if target.is_file():
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            assert digest == hashlib.sha256(target.read_bytes()).hexdigest(), source
            integrity.append({'task': task, 'original': str(source), 'snapshot': str(target), 'sha256': digest, 'equal': True})
    payload = BASE / task_id / 'trajectories/claude-opus-5/run_1/artifacts/app'
    for source in payload.rglob('*'):
        if source.is_file():
            target = SCRATCH / f'{task}-replay/solution/payload' / source.relative_to(payload)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            assert digest == hashlib.sha256(target.read_bytes()).hexdigest(), source
            integrity.append({'task': task, 'captured': str(source), 'replay_payload': str(target), 'sha256': digest, 'equal': True})
    original_cases = json.loads((evidence / 'diagnostics_summary.json').read_text())
    fixed_cases = json.loads((evidence / 'counterfactual_summary.json').read_text())
    assert all(item['exception'] is None and item['ok'] for item in original_cases)
    assert all(item['exception'] is None and item['ok'] and item['fields_wrong'] == 0 for item in fixed_cases)
    print(task, 'scores', scores, 'cases', len(original_cases), 'runtime range', min(item['program_seconds'] for item in original_cases), max(item['program_seconds'] for item in original_cases))
(WORK / 'REPLAY_SUMMARY.json').write_text(json.dumps(runs, indent=2) + '\n')
(WORK / 'INTEGRITY.json').write_text(json.dumps(integrity, indent=2) + '\n')
(WORK / 'result_3d517b2.json').write_text(json.dumps({'sha': '3d517b2', 'step': 'stage2-replay', 'status': 'DONE', 'tasks': results, 'report': str(WORK / 'FINDINGS.md')}, indent=2) + '\n')
print('Validated', len(integrity), 'unchanged snapshot/payload files')
