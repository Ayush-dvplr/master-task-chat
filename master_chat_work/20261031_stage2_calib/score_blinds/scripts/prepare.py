from pathlib import Path
import importlib.util
import json
import shutil

B = Path('/Users/mac/Desktop/Terminal Bench')
W = B / 'master_chat_work/20261031_stage2_calib/score_blinds'
S = B / '_runs/20261031/stage2-calib/score-b366e00'
TASKS = {
    'billing': ('59417607-2254-5165-b703-0d5a4aeb7367', 'blind-billing-20261031T1552-ba10', 'transform.py', 97, 7),
    'pm25': ('98ed74c1-19ac-5ec8-adaf-392a172d4600', 'blind-pm25-20261031T1552-ad2c', 'derive_report.py', 110, 10),
    'pension': ('9bb234eb-e964-5e0b-b8a9-37e9d58b887c', 'blind-pension-20261031T1552-1540', 'calculate_pension.py', 52, 12),
}
spec = importlib.util.spec_from_file_location('qc', B / 'Terminal_2.0_Harbor_Harness/Input_Bundle_QC/exe_copy.py')
qc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qc)
S.mkdir(parents=True, exist_ok=True)
for name, (guid, blind, program, total, opus) in TASKS.items():
    src = B / 'anubis-stage-2' / guid
    raw = S / (name + '-source')
    raw.mkdir()
    for part in ['instruction.md', 'task.toml', 'environment', 'solution', 'tests']:
        a, b = src / part, raw / part
        shutil.copytree(a, b) if a.is_dir() else shutil.copy2(a, b)
    oracle = S / (name + '-oracle')
    assert qc.main([str(raw), str(oracle)]) == 0
    # Public local tag replaces an inaccessible registry only; checks remain byte-identical.
    for area in ['environment', 'tests']:
        f = oracle / area / 'Dockerfile'
        lines = f.read_text().splitlines()
        f.write_text('\n'.join('FROM python:3.12-slim' if x.startswith('FROM ') else x for x in lines) + '\n')
    target = S / (name + '-blind')
    shutil.copytree(oracle, target)
    shutil.rmtree(target / 'solution')
    (target / 'solution').mkdir()
    shutil.copytree(B / '_runs/20261031/stage2-calib' / blind / 'app', target / 'solution/blind-app')
    (target / 'solution/solve.sh').write_text(
        '#!/bin/bash\nset -euo pipefail\nmkdir -p /app/out\n'
        'cp -a /solution/blind-app/. /app/out/\n'
        f'python3 /app/out/{program} /app/data /app/out\n')
    (target / 'solution/solve.sh').chmod(0o755)
    evidence = W / (name + '-recorded')
    shutil.copytree(src / 'trajectories/claude-opus-5/run_1/verifier', evidence)
    shutil.copytree(src / 'trajectories/claude-opus-5/run_1/artifacts/app', S / (name + '-opus-app'))
    shutil.copytree(B / '_runs/20261031/stage2-calib' / blind / 'work', W / (name + '-blind-work'))
    (W / (name + '-contract.json')).write_text(json.dumps({
        'program': '/app/out/' + program, 'command': f'python3 /app/out/{program} /app/data /app/out',
        'positive_total': total, 'opus_raw': opus,
        'test_source_unchanged': (oracle / 'tests/test_output.py').read_bytes() == (src / 'tests/test_output.py').read_bytes(),
        'infrastructure_changes': 'QC exe_copy: tests-only reward, judge removed, public network metadata, unused SDK removed; FROM uses locally available python:3.12-slim',
    }, indent=2) + '\n')
    print(name, 'prepared', flush=True)
shutil.copy2(B / 'master_chat_work/20261031_stage2_calib/replay_A2/scripts/instrument.py', W / 'scripts/reused_A2_instrument.py')
