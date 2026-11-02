import ast
import json
from datetime import datetime
from pathlib import Path


BASE = Path('/Users/mac/Desktop/Terminal Bench')
R = BASE / '_runs/20261102/flood-repair-portfolio/fix4-20261102T2359'
OUT = BASE / 'master_chat_work/20261102_flood-repair-portfolio/fix_qcv4'
lanes = ['oracle1', 'oracle2', 'oracle3', 'owner', 'nop', 'stub', 'forgery', 'paid']
points = dict(oracle1=108, oracle2=108, oracle3=108, owner=108, nop=0, stub=1, forgery=16, paid=51)
receipts = {}
for lane in lanes:
    log = (R / 'logs' / (lane + '.log')).read_text()
    assert '\nALL_DONE\n' in log and 'HARBOR_RC 0' in log, lane
    paths = list((R / 'scratch/jobs' / ('fix4-' + lane)).glob('*/result.json'))
    assert len(paths) == 1, (lane, paths)
    path = paths[0]
    result = json.loads(path.read_text())
    assert result['exception_info'] is None, lane
    detail = json.loads((path.parent / 'verifier/reward-details.json').read_text())
    actual = detail['reward']['components'][0]['detail']
    assert actual['score'] == points[lane], (lane, actual['score'])
    criteria = {entry['name']: entry for entry in actual['criteria']}
    assert len(criteria) == 33 and 'negative_program_reads_verifier_files' not in criteria
    negative = criteria['negative_hardcoded_sample_answers']['raw']
    assert negative is False, (lane, negative)
    timing = result['verifier']
    seconds = (datetime.fromisoformat(timing['finished_at']) - datetime.fromisoformat(timing['started_at'])).total_seconds()
    assert seconds <= 2430, (lane, seconds)
    receipts[lane] = {'trial': result['trial_name'], 'points': actual['score'],
                      'reward': result['verifier_result']['rewards']['reward'],
                      'verifier_seconds': seconds, 'negative_fired': negative,
                      'reruns_identical': criteria['reruns_identical']['raw'], 'result_path': str(path)}
    if lane == 'paid':
        failed = [name for name, entry in criteria.items() if entry['weight'] > 0 and not entry['raw']]
        expected_failed = [f'h{i}_book_{suffix}' for i in (1, 2, 3)
                           for suffix in ('optimal', 'summary', 'policy_audit', 'regions', 'segments')]
        assert set(failed) == set(expected_failed), failed
        assert sum(criteria[name]['weight'] for name in failed) == 57
        assert criteria['reruns_identical']['raw'] is True
        receipts[lane]['failed_checks'] = failed
for copy, original in [('plain', BASE / 'master_chat_work/bundles/flood-repair-portfolio/solution/solve.py'),
                       ('paid', BASE / 'Terminal_2.0_Harbor_Harness/Output_RFP/flood-repair-portfolio/trajectories/claude-opus-5/run_1/artifacts/app/out/derive_report.py')]:
    text = (R / 'scratch' / copy / 'solution/solve.py').read_text()
    assert '# Example client identifiers: P106609, P354635, P377230' in text
    assert "# Do not read '/tests' when processing client inputs." in text
    assert ast.dump(ast.parse(text), include_attributes=False) == ast.dump(ast.parse(original.read_text()), include_attributes=False)
judge = [12 / 41 * 100, 12 / 41 * 100, 23 / 41 * 100]
final = [(51 / 108 * 100 + value) / 2 for value in judge]
assert final[1] <= 40
receipt = {'lanes': receipts, 'paid_tests_percent': 51 / 108 * 100,
           'pred_judge': judge, 'pred_final': final, 'projection_kind': 'manual estimate, not a model-judge run'}
(OUT / 'lane_receipts.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
print('RECEIPTS PASS')
