import ast
import hashlib
import json
import re
import tomllib
from pathlib import Path

HERE = Path(__file__).parent
B = HERE.parents[2] / 'flood-repair-portfolio'
before = HERE / 'before'
source = (B / 'tests/test_output.py').read_text()
old = (before / 'tests/test_output.py').read_text()
functions = lambda text: {n.name: ast.dump(n, include_attributes=False)
                          for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
changed = {k for k in functions(old) if functions(old)[k] != functions(source).get(k)}
assert changed == {'_check_reruns_identical', '_check_negative_program_reads_verifier_files',
                   '_check_negative_hardcoded_sample_answers', 'reruns_identical',
                   'negative_program_reads_verifier_files', 'negative_hardcoded_sample_answers'}, changed
for p in before.rglob('*'):
    if p.is_file() and str(p.relative_to(before)) not in {'tests/test_output.py', 'tests/judge.toml', 'solution/TRUTH.md'}:
        assert p.read_bytes() == (B / p.relative_to(before)).read_bytes(), p
previous = tomllib.loads((before / 'tests/judge.toml').read_text())
current = tomllib.loads((B / 'tests/judge.toml').read_text())
assert current['criterion'][:15] == previous['criterion']
assert current['criterion'][15]['id'] == 'R16'
assert sum(c['weight'] for c in current['criterion'] if c['weight'] > 0) == 41
truth = B / 'solution/TRUTH.md'
text = truth.read_text()
for key, name in [('fix_patch_sha256', 'solve.sh'), ('solve_py_sha256', 'solve.py')]:
    value = hashlib.sha256((B / 'solution' / name).read_bytes()).hexdigest()
    text, count = re.subn(key + r': [0-9a-f]{64}', key + ': ' + value, text)
    assert count == 1
assert not re.search(r'\br6\b|harden_r6|Harbor tests-only oracle lanes', text)
truth.write_text(text)
(HERE / 'scope_proof.json').write_text(json.dumps({'changed_functions': sorted(changed),
    'protected_files': 'byte-identical', 'judge_R1_R15': 'identical', 'positive_judge': 41}, indent=2) + '\n')
print('SCOPE PASS; TRUTH digest bindings refreshed by script as last bundle edit')
