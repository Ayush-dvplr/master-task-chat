import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

task = sys.argv[1]
root = Path('/evidence') / (task + '-instrument')
source = Path('/oracle/solve.py').read_text()
original, replacement = {
    'pension': ('(item[0], item[1], item[3])', '(item[0], item[1])'),
    'spectrum': ('(row["priority"], row["source"], row["party"])', '(row["priority"], row["source"])'),
}[task]
assert source.count(original) == 1
results = []
with tempfile.TemporaryDirectory() as temporary:
    mutant = Path(temporary) / 'mutant.py'
    mutant.write_text(source.replace(original, replacement))
    for item in json.loads((root / 'summary.json').read_text()):
        case = root / item['scenario']
        output = Path(temporary) / item['scenario']
        subprocess.run([sys.executable, '-I', '-S', str(mutant), str(case / 'data'), str(output)], check=True, timeout=120)
        changed = [p.name for p in (case / 'expected').glob('*.json') if p.read_bytes() != (output / p.name).read_bytes()]
        results.append({'scenario': item['scenario'], 'changed_reports': changed})
record = {'task': task, 'removed_tiebreak': original, 'replacement': replacement,
          'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'results': results}
(root / 'trigger-probe.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
