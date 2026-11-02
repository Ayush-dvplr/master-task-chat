from pathlib import Path
from collections import Counter
import ast
import hashlib
import json

base = Path('/Users/mac/Desktop/Terminal Bench')
bundle = base / 'master_chat_work/bundles/sensor-network-lsq-correlated-adjustment'
original = base / 'Terminal_2.0_Harbor_Harness/Tasks_INPUT/sensor-network-lsq-correlated-adjustment'
out = base / 'master_chat_work/20261102_sensor-network-lsq-correlated-adjustment/fix_val1'
before = dict((line.split('  ', 1)[1], line.split('  ', 1)[0]) for line in (out / 'digests_before.txt').read_text().splitlines())
after = {'./' + str(p.relative_to(bundle)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(bundle.rglob('*')) if p.is_file()}
changed = [name[2:] for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]
assert changed == ['solution/TRUTH.md', 'tests/reward.toml', 'tests/test_output.py'], changed
(out / 'digests_after.txt').write_text(''.join(f'{digest}  {name}\n' for name, digest in after.items()))
(out / 'changed_digests.json').write_text(json.dumps({name: {'before': before['./' + name], 'after': after['./' + name]} for name in changed}, indent=2) + '\n')
old_source = (original / 'tests/test_output.py').read_text()
new_source = (bundle / 'tests/test_output.py').read_text()
assert old_source.split('import ast as _ast')[0] == new_source.split('import ast as _ast')[0]
old_tree, new_tree = ast.parse(old_source), ast.parse(new_source)
old_functions = {n.name: ast.dump(n) for n in old_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
new_functions = {n.name: ast.dump(n) for n in new_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
modified = [name for name, value in old_functions.items() if value != new_functions.get(name)]
assert modified == ['_run_agent_program'], modified
for kind in (ast.Assign, ast.AnnAssign, ast.Expr, ast.Import, ast.ImportFrom):
    old = Counter(ast.dump(n) for n in old_tree.body if isinstance(n, kind))
    new = Counter(ast.dump(n) for n in new_tree.body if isinstance(n, kind))
    assert not old - new, (kind.__name__, old - new)
assert not list(bundle.rglob('__pycache__'))
result = {'changed_files': changed, 'old_functions_unchanged_except': modified,
          'generator_reader_reference_bytes_unchanged': True,
          'all_existing_assignments_imports_and_registrations_retained': True,
          'positive_weights_total': 86, 'paid_predictions_low_mid_high': [29.1, 33.0, 40.7]}
(out / 'preservation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
