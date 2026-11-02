from pathlib import Path
import shutil

base = Path('/Users/mac/Desktop/Terminal Bench/_runs/20261031/stage2-calib')
scratch = base / 'score-b366e00'
folders = {'billing': 'blind-billing-20261031T1552-ba10', 'pm25': 'blind-pm25-20261031T1552-ad2c', 'pension': 'blind-pension-20261031T1552-1540'}
for task, folder in folders.items():
    shutil.copytree(base / folder / 'out', scratch / (task + '-blind-app/out'))
    for program in (base / folder / 'app').iterdir():
        assert (scratch / (task + '-blind-app/out') / program.name).read_bytes() == program.read_bytes()
    print(task, 'captured frozen program and reports')
