from pathlib import Path
import hashlib
import re

bundle = Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sensor-network-lsq-correlated-adjustment')
truth = bundle / 'solution/TRUTH.md'
text = truth.read_text()
for key, name in (('fix_patch_sha256', 'solve.sh'), ('solve_py_sha256', 'solve.py')):
    digest = hashlib.sha256((bundle / 'solution' / name).read_bytes()).hexdigest()
    text, count = re.subn(rf'(?m)^{key}: [0-9a-f]{{64}}$', key + ': ' + digest, text)
    assert count == 1
    print(key, digest)
truth.write_text(text)
