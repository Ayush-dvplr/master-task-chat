from pathlib import Path

ROOT = Path('/Users/mac/Desktop/Terminal Bench/_runs/20261031/stage2-calib/replay-3d517b2')
for task, denominator in (('billing', 97), ('pm25', 110), ('royalty', 52)):
    for mode in ('oracle', 'replay'):
        tests = ROOT / f'{task}-{mode}' / 'tests'
        (tests / 'judge.toml').rename(tests / 'judge.toml.disabled')
        (tests / 'reward.toml').write_text('[[reward]]\nname = "reward"\naggregation = "weighted-sum"\nweights = { test_output = ' + str(1 / denominator) + ' }\n\n[scoring.test_output]\naggregation = "weighted-sum"\n')
        print(task, mode, 'Only judge discovery and outer normalization changed; test_output.py unchanged.')
