from pathlib import Path
from datetime import datetime
import json

base = Path('/Users/mac/Desktop/Terminal Bench')
run = base / '_runs/20261102/sensor-network-lsq-correlated-adjustment/fixv-20261102T224943'
out = base / 'master_chat_work/20261102_sensor-network-lsq-correlated-adjustment/fix_val1'
assert (run / 'logs/chain2.log').read_text().rstrip().endswith('ALL_DONE exit=0')
expected = {'oracle-1': 86, 'oracle-2': 86, 'oracle-3': 86, 'owner': 86,
            'nop': 0, 'stub': 1, 'forgery': 10, 'paid-fixed': 17}
lanes = {}
for name, points in expected.items():
    assert (run / 'logs' / (name + '.log')).read_text().rstrip().endswith('ALL_DONE exit=0')
    job = run / 'jobs' / name
    stats = json.loads((job / 'result.json').read_text())['stats']
    assert stats['n_errored_trials'] == stats['n_running_trials'] == 0
    files = list(job.glob('*/verifier/reward-details.json'))
    assert len(files) == 1, (name, files)
    file = files[0]
    criteria = json.loads(file.read_text())['reward']['components'][0]['detail']['criteria']
    positive = sum(c['weight'] * c['value'] for c in criteria if c['weight'] > 0)
    fired = [c['name'] for c in criteria if c['weight'] < 0 and c['value']]
    assert positive == points and not fired, (name, positive, fired)
    reward = json.loads((file.parent / 'reward.json').read_text())['reward']
    assert abs(reward - round(points / 86, 4)) < 1e-12, (name, reward)
    verifier = json.loads((file.parent.parent / 'result.json').read_text())['verifier']
    seconds = (datetime.fromisoformat(verifier['finished_at'].replace('Z', '+00:00')) -
               datetime.fromisoformat(verifier['started_at'].replace('Z', '+00:00'))).total_seconds()
    assert 0 < seconds <= 2430, (name, seconds)
    lanes[name] = {'tests_only_reward': reward, 'exact_tests_fraction': points / 86, 'positive_points': positive,
                   'negative_fired': fired, 'verifier_seconds': seconds}
witnesses = {}
for line in (run / 'logs/witness.log').read_text().splitlines():
    if line.startswith('{'):
        witnesses.update(json.loads(line))
assert witnesses['oracle']['fired'] == []
for name, value in witnesses.items():
    if name != 'oracle':
        assert value['fired'] == [name]
(out / 'lanes.json').write_text(json.dumps(lanes, indent=2) + '\n')
(out / 'witnesses.json').write_text(json.dumps(witnesses, indent=2) + '\n')
print(json.dumps({'lanes': lanes, 'witnesses': witnesses}, indent=2))
