import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

bundle = Path('/Users/mac/Desktop/Terminal Bench/QC/copies/688700c/flood-repair-portfolio')
scratch = Path(__file__).parent
out = scratch / 'negative-probe-output'
out.mkdir(exist_ok=True)
original = (bundle / 'solution/solve.py').read_text(encoding='utf-8')
program = out / 'derive_report.py'
program.write_text(original, encoding='utf-8')
proc = subprocess.run([sys.executable, str(program), str(bundle / 'environment/data'), str(out)], capture_output=True, text=True, timeout=20)
print('ORIGINAL_RUN_EXIT', proc.returncode)
assert proc.returncode == 0, proc.stderr
summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
ids = [p for row in summary['rounds'] for p in row['selected']][:3]
assert len(set(ids)) == 3
tree = ast.parse((bundle / 'tests/test_output.py').read_text(encoding='utf-8'))
names = {'_check_negative_program_reads_verifier_files', '_check_negative_hardcoded_sample_answers', '_holds'}
extracted = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
scope = {'OUT': out, 'expected': lambda _: {'summary.json': summary}, 're': re}
exec(compile(extracted, '<unchanged negative helpers>', 'exec'), scope)
for label, comment in [('baseline', ''), ('honest_verifier_comment', "\n# Do not read '/tests' when processing client inputs.\n"), ('honest_sample_comment', '\n# Example client identifiers: ' + ', '.join(ids) + '\n')]:
    candidate = original + comment
    program.write_text(candidate, encoding='utf-8')
    assert ast.dump(ast.parse(candidate)) == ast.dump(ast.parse(original))
    verdicts = {name: scope['_holds'](scope[name]) for name in sorted(names - {'_holds'})}
    print(label, json.dumps(verdicts, sort_keys=True), 'AST_IDENTICAL=True')
program.write_text(original, encoding='utf-8')
canonical = json.dumps(summary, sort_keys=True)
alternate = json.dumps(summary, indent=2)
print('SAME_JSON_DIFFERENT_BYTES', json.loads(canonical) == json.loads(alternate), canonical != alternate)
print('PROGRAM_SHA256', hashlib.sha256(original.encode()).hexdigest())
print('COMMENT_SAMPLE_IDS', ids)
