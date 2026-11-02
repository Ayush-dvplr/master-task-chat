import ast
import json
import subprocess
import sys
from pathlib import Path

bundle = Path('/Users/mac/Desktop/Terminal Bench/QC/copies/ffd3a8e/sensor-network-lsq-correlated-adjustment')
scratch = Path(__file__).parent
tree = ast.parse((bundle / 'tests/test_output.py').read_text())
tree.body = [node for node in tree.body if not (
    isinstance(node, ast.ImportFrom) and node.module == 'rewardkit'
    or isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    and isinstance(node.value.func, ast.Attribute)
    and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == 'criteria'
)]
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        node.decorator_list = []
ns = {'__name__': 'qc_probe'}
exec(compile(tree, str(bundle / 'tests/test_output.py'), 'exec'), ns)
data, out = scratch / 'type-input', scratch / 'type-output'
ns['emit_corpus'](data, ns['CHALLENGE_SEED'])
subprocess.run([sys.executable, str(bundle / 'solution/solve.py'), str(data), str(out)], check=True)
ref = ns['solve'](data)
ns['_hidden'] = lambda name: {'code': 0, 'ref': ref, 'out': out, 'root': data}
ns['_check_unknowns']('challenge')
print('BASELINE_UNKNOWN_CHECK=PASS')
path = out / 'datum_transformation.json'
document = json.loads(path.read_text())
assert document['shifted_corrections_micrometres']['EAGLE.x'] == 0
document['shifted_corrections_micrometres']['EAGLE.x'] = False
path.write_text(json.dumps(document, sort_keys=True, indent=2) + '\n')
ns['_check_unknowns']('challenge')
print('INVALID_BOOLEAN_FOR_INTEGER_UNKNOWN_CHECK=PASS')
print('MUTATION=datum_transformation.json shifted_corrections_micrometres.EAGLE.x: 0 -> false')
document['shifted_corrections_micrometres']['EAGLE.x'] = 0
path.write_text(json.dumps(document, sort_keys=True, indent=2) + '\n')
path = out / 'residuals.tsv'
lines = path.read_text().splitlines()
assert lines[0] == 'obs_id\tresidual_micrometres'
path.write_text('WRONG_HEADER\n' + '\n'.join(lines[1:]) + '\n')
ns['_check_residuals']('challenge')
print('INVALID_TSV_HEADER_RESIDUAL_CHECK=PASS')

path = out / 'datum_transformation.json'
document = json.loads(path.read_text())
document['undeclared_extra_field'] = 123
path.write_text(json.dumps(document, sort_keys=True, indent=2) + '\n')
ns['_check_unknowns']('challenge')
ns['_check_control_values']()
ns['_check_canonical_serialization']()
print('UNDECLARED_DATUM_KEY_ALL_RELEVANT_HIDDEN_CHECKS=PASS')

data, out = scratch / 'shipped-coverage-input', scratch / 'shipped-coverage-output'
ns['emit_corpus'](data, ns['SAMPLE_SEED'])
subprocess.run([sys.executable, str(bundle / 'solution/solve.py'), str(data), str(out)], check=True)
(out / 'derive_report.py').write_bytes((bundle / 'solution/solve.py').read_bytes())
ref = ns['solve'](data)
ns['OUT'], ns['SCRIPT'] = out, out / 'derive_report.py'
ns['_shipped_reference'] = lambda: ref
path = out / 'model_test.json'
document = json.loads(path.read_text())
document['degrees_of_freedom'] = -999
path.write_text(json.dumps(document, sort_keys=True, indent=2) + '\n')
for name in ('test_artifact_set_exists_and_parses', 'test_traverse_closure_rows_shipped',
             'test_centring_chain_rows_shipped', 'test_district_rollups_shipped'):
    ns[name]()
print('INVALID_SHIPPED_MODEL_DOF_ALL_FOUR_SHIPPED_POSITIVES=PASS')
