import json
import shutil
from pathlib import Path

BASE = Path('/Users/mac/Desktop/Terminal Bench')
WORK = BASE / 'master_chat_work/20261031_stage2_calib/replay_A1'
SCRATCH = BASE / '_runs/20261031/stage2-calib/replay-3d517b2'
TASKS = {'billing': '59417607-2254-5165-b703-0d5a4aeb7367',
         'pm25': '98ed74c1-19ac-5ec8-adaf-392a172d4600',
         'royalty': '75407a55-6665-505e-95d8-5ff9bdb3384f'}

for short, uuid in TASKS.items():
    source = BASE / 'anubis-stage-2' / uuid
    run = source / 'trajectories/claude-opus-5/run_1'
    evidence = WORK / 'evidence' / short
    evidence.mkdir(parents=True, exist_ok=True)
    for name in ['reward-details.json', 'score.json', 'ctrf.json', 'test-stdout.txt']:
        shutil.copy2(run / 'verifier' / name, evidence / name)
    shutil.copy2(source / 'trajectories/claude-opus-5/pass_summary.json', evidence)
    trajectory = json.loads((run / 'agent/trajectory.json').read_text())
    (evidence / 'trajectory_shape.json').write_text(json.dumps({k: type(v).__name__ for k, v in trajectory.items()}, indent=2))
    with (evidence / 'steps.txt').open('w') as handle:
        for index, step in enumerate(trajectory.get('steps', [])):
            handle.write(f'\nSTEP_INDEX {index}\n{json.dumps(step, ensure_ascii=True)}\n')
    for mode in ['oracle', 'replay']:
        target = SCRATCH / f'{short}-{mode}'
        target.mkdir(exist_ok=True)
        for name in ['environment', 'tests', 'solution']:
            shutil.copytree(source / name, target / name, dirs_exist_ok=True)
        for name in ['instruction.md', 'task.toml']:
            shutil.copy2(source / name, target / name)
        if mode == 'replay':
            shutil.copytree(run / 'artifacts/app', target / 'solution/payload', dirs_exist_ok=True)
            (target / 'solution/solve.sh').write_text('#!/bin/sh\nset -eu\ncp -a "${SOLUTION_ROOT:-/solution}/payload/." /app/\n')
    score = json.loads((evidence / 'score.json').read_text())
    summary = json.loads((evidence / 'pass_summary.json').read_text())
    print(short, {k: v for k, v in score.items() if k not in ['rubric']}, summary['per_run'])
