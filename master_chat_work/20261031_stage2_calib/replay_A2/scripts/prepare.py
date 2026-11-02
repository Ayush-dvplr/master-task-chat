from pathlib import Path
import importlib.util
import json
import shutil

BASE = Path('/Users/mac/Desktop/Terminal Bench')
WORK = BASE / 'master_chat_work/20261031_stage2_calib/replay_A2'
SCRATCH = BASE / '_runs/20261031/stage2-calib/replay-4e9d595'
TASKS = {'pension': '9bb234eb-e964-5e0b-b8a9-37e9d58b887c',
         'spectrum': 'fa7c65bd-ff01-50e7-b3ba-34fbd5df860d'}
spec = importlib.util.spec_from_file_location('exe_copy', BASE / 'Terminal_2.0_Harbor_Harness/Input_Bundle_QC/exe_copy.py')
qc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qc)
for name, guid in TASKS.items():
    source = BASE / 'anubis-stage-2' / guid
    raw = SCRATCH / (name + '-source')
    raw.mkdir()
    for item in ['instruction.md', 'task.toml', 'environment', 'solution', 'tests']:
        origin, target = source / item, raw / item
        shutil.copytree(origin, target) if origin.is_dir() else shutil.copy2(origin, target)
    assert qc.main([str(raw), str(SCRATCH / (name + '-oracle'))]) == 0
    replay = SCRATCH / (name + '-replay')
    shutil.copytree(SCRATCH / (name + '-oracle'), replay)
    captured = source / 'trajectories/claude-opus-5/run_1/artifacts/app'
    shutil.copytree(captured, replay / 'solution/captured-app')
    (replay / 'solution/solve.sh').write_text('#!/bin/bash\nset -euo pipefail\ncp -a /solution/captured-app/. /app/\n')
    run = source / 'trajectories/claude-opus-5/run_1'
    evidence = WORK / (name + '-recorded')
    evidence.mkdir()
    for f in (run / 'verifier').iterdir():
        if f.is_file():
            shutil.copy2(f, evidence / f.name)
    shutil.copy2(source / 'trajectories/claude-opus-5/pass_summary.json', evidence)
    trajectory = json.loads((run / 'agent/trajectory.json').read_text())
    with (evidence / 'trajectory-steps.txt').open('w') as out:
        for step in trajectory['steps']:
            out.write(json.dumps(step, indent=2) + '\n')
    print(name, 'prepared; steps', len(trajectory['steps']))
