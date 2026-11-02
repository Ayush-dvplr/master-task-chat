import csv
import json
from pathlib import Path
import shutil

BASE = Path('/Users/mac/Desktop/Terminal Bench')
WORK = BASE / 'master_chat_work/20261031_stage2_calib/replay_A2'
SCRATCH = BASE / '_runs/20261031/stage2-calib/replay-4e9d595'
GUIDS = {'pension': '9bb234eb-e964-5e0b-b8a9-37e9d58b887c', 'spectrum': 'fa7c65bd-ff01-50e7-b3ba-34fbd5df860d'}
with (WORK / 'CAUSES.csv').open(newline='') as stream:
    causes = list(csv.DictReader(stream))
with (WORK / 'JUDGE_LOSS.csv').open(newline='') as stream:
    judges = list(csv.DictReader(stream))
assert len(causes) == 51 and len(judges) == 20
assert sum(float(r['weight']) for r in judges if r['class'] == 'PROBE-SKIPPED') == 70
assert sum(float(r['weight']) for r in judges if r['class'] == 'PROCESS-SKIPPED') == 18
checks = {}
tasks = []
for task, guid in GUIDS.items():
    original = BASE / 'anubis-stage-2' / guid
    recorded = json.loads((WORK / (task + '-recorded/reward-details.json')).read_text())['reward']
    recorded_tests = next(c['detail'] for c in recorded['components'] if c['name'] == 'test_output')
    assert recorded['score'] == 0.2225
    lost = {c['name']: c['weight'] for c in recorded_tests['criteria'] if c['weight'] > 0 and not c['value']}
    assert len(lost) == 8 and sum(lost.values()) == 40
    assert all(not c['value'] for c in recorded_tests['criteria'] if c['weight'] < 0)
    primary = {(r['task'], r['check']): float(r['weight']) for r in causes if r['task'] == task and r['cause'] == 'UNFAIR'}
    assert {key[1]: value for key, value in primary.items()} == lost
    assert sum(float(r['weight']) for r in judges if r['task'] == task) == 44
    scores = {}
    for mode in ('oracle', 'replay'):
        copy = SCRATCH / (task + '-' + mode)
        assert (original / 'tests/test_output.py').read_bytes() == (copy / 'tests/test_output.py').read_bytes()
        job = SCRATCH / 'jobs' / ('a2-local-' + task + '-' + mode)
        trial = next(path for path in job.iterdir() if path.is_dir() and (path / 'verifier/reward-details.json').exists())
        target = WORK / 'replay-results' / (task + '-' + mode)
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(trial / 'verifier', target / 'verifier', dirs_exist_ok=True)
        for path in (job / 'result.json', trial / 'result.json'):
            if path.exists():
                shutil.copy2(path, target / (path.parent.name + '-result.json'))
        detail = json.loads((trial / 'verifier/reward-details.json').read_text())['reward']
        component = detail['components'][0]['detail']
        scores[mode] = 100 * component['score'] / 52
        if mode == 'replay':
            assert [(c['name'], c['value'], c['weight']) for c in component['criteria']] == [(c['name'], c['value'], c['weight']) for c in recorded_tests['criteria']]
    assert scores['oracle'] == 100 and abs(scores['replay'] - 100 * 12 / 52) < 1e-9
    cases = json.loads((WORK / (task + '-instrument/summary.json')).read_text())
    for case in cases:
        assert case['oracle_hash_verified'] and case['one_fact_wrong_fails']
        assert case['exception'] == {'type': 'AssertionError', 'message': ''}
        directory = WORK / (task + '-instrument') / case['scenario']
        difference = json.loads((directory / 'diff.json').read_text())
        for name, fields in difference['diffs'].items():
            if not fields:
                assert (directory / 'expected' / name).read_bytes() == (directory / 'actual' / name).read_bytes()
    probe = json.loads((WORK / (task + '-instrument/trigger-probe.json')).read_text())
    assert all(not r['changed_reports'] for r in probe['results'])
    tasks.append({'task': task, 'recorded_tests': 23.08, 'replay_tests': round(scores['replay'], 2),
                  'oracle_tests': scores['oracle'], 'lost_test_pts': 100 * 40 / 52,
                  'by_cause': {'UNFAIR': 100 * 40 / 52}, 'lost_test_raw': 40,
                  'secondary_nonadditive': {'AMPLIFIED': 100 * 40 / 52}})
    checks[task] = {'failed_checks': sorted(lost), 'raw_lost_tests': 40, 'raw_lost_judge': 44,
                    'grading_module_unchanged': True, 'replay_criteria_match_recorded': True,
                    'frozen_hashes_recovered': 8, 'one_fact_counterexamples': 8,
                    'trigger_mutants_unchanged': 8, 'no_negative_fired': True}
for script in (WORK / 'scripts').glob('*.py'):
    compile(script.read_text(), str(script), 'exec')
assert (WORK / 'FINDINGS.md').read_text().startswith('VERDICT: ')
result = {'sha': '4e9d595', 'step': 'stage2-replay', 'status': 'DONE', 'tasks': tasks,
          'report': str(WORK / 'FINDINGS.md'), 'score_units': 'percent, test channel only',
          'runtime_caveat': 'Private pinned ECR base inaccessible (401); used recorded local Python 3.12-slim image. Grading code unchanged.'}
(WORK / 'result_4e9d595.json').write_text(json.dumps(result, indent=2) + '\n')
(WORK / 'validation.json').write_text(json.dumps({'checks': checks, 'cause_rows': len(causes), 'judge_rows': len(judges), 'scripts_syntax_valid': True}, indent=2) + '\n')
print(json.dumps(result, indent=2))
print('VALIDATED: 16 failed checks, 80 raw test loss; 20 judge criteria, 88 raw judge loss; all scripts compile')
