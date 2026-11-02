import hashlib
import json
import shutil
from pathlib import Path

BASE = Path('/Users/mac/Desktop/Terminal Bench')
BUNDLE = BASE / 'master_chat_work/bundles/flood-repair-portfolio'
HERE = Path(__file__).parent
OUT = BASE / 'master_chat_work/20261102_flood-repair-portfolio/fix_qcv4'
RUN = BASE / '_runs/20261102/flood-repair-portfolio/fix4-20261102T2359'
OUT.mkdir(exist_ok=True)
for child in ('scratch', 'logs'):
    (RUN / child).mkdir(parents=True, exist_ok=True)
snapshot = HERE / 'before'
assert not snapshot.exists(), 'do not overwrite baseline'
shutil.copytree(BUNDLE, snapshot)
digests = {str(p.relative_to(BUNDLE)): hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted(BUNDLE.rglob('*')) if p.is_file()}
(HERE / 'before_digests.json').write_text(json.dumps(digests, indent=2) + '\n')
print('BASELINE', len(digests), 'files; RUN', RUN, 'OUT', OUT)
