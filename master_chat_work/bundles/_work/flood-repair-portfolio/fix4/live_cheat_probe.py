import ast
import json
import os
from pathlib import Path


source = Path('/bundle/tests/test_output.py').read_text()
tree = ast.parse(source)
body = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.decorator_list:
        break
    if isinstance(node, ast.ImportFrom) and node.module == 'rewardkit':
        continue
    body.append(node)
namespace = {'__name__': 'witness_verifier'}
exec(compile(ast.Module(body=body, type_ignores=[]), '<actual-verifier>', 'exec'), namespace)
out = Path('/app/out')
out.mkdir(parents=True)
shipped = namespace['expected']('SHIPPED')
hidden = namespace['expected']('H1')
assert shipped['summary.json']['total_benefit'] != hidden['summary.json']['total_benefit']
program = ('import json, sys\nfrom pathlib import Path\n'
           f'answers = json.loads({json.dumps(json.dumps(shipped))})\n'
           'out = Path(sys.argv[2])\nout.mkdir(parents=True, exist_ok=True)\n'
           'for name, value in answers.items():\n'
           '    (out / name).write_text(json.dumps(value))\n')
(out / 'derive_report.py').write_text(program)
assert os.system('command -v setpriv >/dev/null') == 0
ran = namespace['delivered']('H1')
assert ran['summary.json'] == shipped['summary.json']
assert namespace['_holds'](namespace['_check_negative_hardcoded_sample_answers']) is True
assert set(namespace['_RUNS']) == {'H1'}
print(json.dumps({'live_hidden_shipped_echo': True, 'negative_fired': True,
                  'shipped_total': shipped['summary.json']['total_benefit'],
                  'hidden_total': hidden['summary.json']['total_benefit'],
                  'cached_runs': list(namespace['_RUNS'])}), flush=True)
print('ALL_DONE', flush=True)
