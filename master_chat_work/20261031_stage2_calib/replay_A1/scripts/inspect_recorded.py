import json
from pathlib import Path

WORK = Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_stage2_calib/replay_A1')
BASE = Path('/Users/mac/Desktop/Terminal Bench/anubis-stage-2')
TASKS = {'billing': '59417607-2254-5165-b703-0d5a4aeb7367', 'pm25': '98ed74c1-19ac-5ec8-adaf-392a172d4600', 'royalty': '75407a55-6665-505e-95d8-5ff9bdb3384f'}
for name, uuid in TASKS.items():
    folder = WORK / 'evidence' / name
    details = json.loads((folder / 'reward-details.json').read_text())
    print(name, json.dumps(details, indent=2)[:1800])
    trajectory = json.loads((BASE / uuid / 'trajectories/claude-opus-5/run_1/agent/trajectory.json').read_text())
    with (folder / 'trajectory_readable.txt').open('w') as out:
        for index, step in enumerate(trajectory['steps']):
            out.write(f'\nSTEP_INDEX={index} step_id={step.get("step_id")} source={step.get("source")}\n')
            out.write(str(step.get('message', '')) + '\n')
            for call in step.get('tool_calls', []):
                out.write(json.dumps(call, indent=2) + '\n')
            for result in step.get('observation', {}).get('results', []):
                out.write(str(result.get('content', '')) + '\n')
