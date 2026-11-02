from pathlib import Path

scratch = Path('/Users/mac/Desktop/Terminal Bench/_runs/20261031/stage2-calib/replay-4e9d595')
for task in ('pension-oracle', 'pension-replay', 'spectrum-oracle', 'spectrum-replay'):
    for role in ('environment', 'tests'):
        path = scratch / task / role / 'Dockerfile'
        lines = path.read_text().splitlines()
        lines = ['FROM python:3.12-slim' if line.startswith('FROM ') else line for line in lines]
        path.write_text('\n'.join(lines) + '\n')
