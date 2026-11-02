from pathlib import Path

root = Path('/Users/mac/Desktop/Terminal Bench/_runs/20261031/stage2-calib/replay-3d517b2')
old = '426628337772.dkr.ecr.ap-south-1.amazonaws.com/anubis:python-3.12-slim@'
new = 'public.ecr.aws/docker/library/python@'
for path in root.glob('*-*/**/Dockerfile'):
    path.write_text(path.read_text().replace(old, new))
