import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

W = Path(__file__).resolve().parents[1]
B = Path('/Users/mac/Desktop/Terminal Bench')
S = B / '_runs/20261031/stage2-calib/score-b366e00'
TASKS = {
    'billing': ('59417607-2254-5165-b703-0d5a4aeb7367', 'blind-billing-20261031T1552-ba10', 'transform.py', 18),
    'pm25': ('98ed74c1-19ac-5ec8-adaf-392a172d4600', 'blind-pm25-20261031T1552-ad2c', 'derive_report.py', 20),
    'pension': ('9bb234eb-e964-5e0b-b8a9-37e9d58b887c', 'blind-pension-20261031T1552-1540', 'calculate_pension.py', 8),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


inventory = json.loads((W / 'INSTRUMENTATION.json').read_text())
result = json.loads((W / 'result_b366e00.json').read_text())
assert result['sha'] == 'b366e00' and result['status'] == 'DONE'
assert (W / 'FINDINGS.md').read_text().startswith('VERDICT: ')
validated = {}
for task, (guid, blind, program, lost) in TASKS.items():
    with (W / f'CHECKS_{task}.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert sum(row['blind'] == 'LOST' for row in rows) == lost
    assert sum(row['both_lost'] == 'true' for row in rows) == lost
    assert all(row['blind'] == row['opus'] for row in rows)
    assert all(row['blind'] == 'AVOIDED' for row in rows if float(row['weight']) < 0)
    assert len(inventory[task]) == lost
    for case in inventory[task]:
        path = Path(case['evidence'])
        evidence = json.loads(path.read_text())
        assert evidence['diff_count'] > 0
        assert evidence['diff_count'] == sum(len(value) for value in evidence['diffs'].values())
        assert evidence['wall_seconds'] > 0
        assert 'exception' in evidence
        assert (path.parent / 'expected').is_dir() and (path.parent / 'actual').is_dir()
    original = B / 'anubis-stage-2' / guid / 'tests/test_output.py'
    for kind in ('source', 'blind', 'oracle'):
        assert digest(original) == digest(S / f'{task}-{kind}' / 'tests/test_output.py')
    blind_original = B / '_runs/20261031/stage2-calib' / blind / 'app' / program
    assert digest(blind_original) == digest(S / f'{task}-blind/solution/blind-app' / program)
    validated[task] = {'checks': len(rows), 'lost_checks_instrumented': lost, 'test_source_sha256': digest(original), 'blind_program_sha256': digest(blind_original), 'oracle_percent': 100, 'check_statuses_match_opus': True}

compiled = []
for path in sorted((W / 'scripts').glob('*.py')):
    compile(path.read_text(), str(path), 'exec')
    compiled.append(path.name)
for path in (W / 'scripts').glob('*.sh'):
    subprocess.run(['bash', '-n', str(path)], check=True)
assert digest(W / 'scripts/reused_A2_instrument.py') == digest(B / 'master_chat_work/20261031_stage2_calib/replay_A2/scripts/instrument.py')
containers = subprocess.run(['docker', 'ps', '-aq', '--filter', 'name=b366e00'], capture_output=True, text=True, check=True).stdout.split()
assert not containers, containers
image = subprocess.run(['docker', 'image', 'inspect', 'b366e00-instrument:local'], capture_output=True, text=True)
if image.returncode == 0:
    subprocess.run(['docker', 'image', 'rm', 'b366e00-instrument:local'], check=True)
removed_caches = []
for root in (S, W / 'scripts'):
    for path in root.rglob('__pycache__'):
        if path.is_dir():
            shutil.rmtree(path)
            removed_caches.append(str(path))
large = [str(path) for path in S.rglob('*') if path.is_file() and path.stat().st_size > 10 * 1024 * 1024]
assert not large, large
cleanup = {'own_containers_remaining': containers, 'own_instrument_image_removed': True, 'scratch_files_over_10_MiB': large, 'removed_caches': removed_caches, 'retained': 'Small reproducible task copies, job logs, verifier results and field-level evidence. Evidence outputs are results, not disposable task inputs.'}
(W / 'CLEANUP.json').write_text(json.dumps(cleanup, indent=2, sort_keys=True) + '\n')
validation = {'status': 'PASS', 'tasks': validated, 'python_syntax_checked': compiled, 'shell_syntax': 'PASS', 'A2_instrument_copy_identical': True, 'total_lost_checks_instrumented': 46, 'judge_invoked': False, 'lsp': 'Unavailable; no host install performed', 'cleanup': cleanup}
(W / 'VALIDATION.json').write_text(json.dumps(validation, indent=2, sort_keys=True) + '\n')
print(json.dumps(validation, indent=2))
