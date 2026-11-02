import hashlib
import json
from pathlib import Path

root = Path('/Users/mac/Desktop/Terminal Bench')
for name in ('pl_generator', 'qc'):
    spec = json.loads((root / 'master_chat_tasks/knowledge/fingerprints' / f'{name}.json').read_text())
    bad = [rel for rel, sha in spec['files'].items()
           if hashlib.sha256((Path(spec['source']) / rel).read_bytes()).hexdigest() != sha]
    print(name, len(spec['files']), 'differences', bad)
    assert not bad
