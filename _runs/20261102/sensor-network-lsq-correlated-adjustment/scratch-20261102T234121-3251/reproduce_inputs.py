import ast
import hashlib
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
namespace = {'__name__': 'qc_inspection'}
exec(compile(tree, str(bundle / 'tests/test_output.py'), 'exec'), namespace)
destination = scratch / 'regenerated'
namespace['emit_corpus'](destination, namespace['SAMPLE_SEED'])
for path in sorted((bundle / 'environment/data').iterdir()):
    actual = path.read_bytes()
    generated = (destination / path.name).read_bytes()
    print(path.name, 'IDENTICAL' if actual == generated else 'DIFFERENT', len(actual), hashlib.sha256(actual).hexdigest())
print('ACTUAL_FILES', len(list((bundle / 'environment/data').iterdir())))
print('GENERATED_FILES', len(list(destination.iterdir())))
