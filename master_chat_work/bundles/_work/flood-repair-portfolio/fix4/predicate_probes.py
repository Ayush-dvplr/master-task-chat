import ast
import json
import threading
from pathlib import Path
from typing import Any


source = Path('/bundle/tests/test_output.py').read_text()
names = {'first_difference', '_assert_same', 'delivered', '_holds',
         '_check_reruns_identical', '_check_negative_hardcoded_sample_answers'}
tree = ast.parse(source)
selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
assert len(selected) == len(names)
ns = {'Any': Any, 'json': json, '_LOCK': threading.RLock(), '_RUNS': {}}
exec(compile(ast.Module(body=selected, type_ignores=[]), '<actual verifier functions>', 'exec'), ns)
results = {}


def record(name, actual, wanted):
    assert actual is wanted, (name, actual, wanted)
    results[name] = actual


def no_new_run(*args):
    raise AssertionError('cached hidden run unexpectedly repeated')


shipped = {'total_benefit': 110, 'rounds': [{'round': 'S', 'selected': ['P1', 'P2']}]}
hidden = {'total_benefit': 220, 'rounds': [{'round': 'H', 'selected': ['Q1', 'Q2']}]}
ns['expected'] = lambda name: {'summary.json': hidden if name == 'H1' else shipped}
ns['_run_copy'] = no_new_run
cases = {
    'correct_hidden': (hidden, False),
    'shipped_echo': (shipped, True),
    'wrong_without_echo': ({'total_benefit': 999, 'rounds': [{'round': 'H', 'selected': ['WRONG']}]}, False),
    'shipped_list_only': ({'total_benefit': 999, 'rounds': [{'round': 'H', 'selected': ['P1', 'P2']}]}, True),
    'shipped_total_only': ({'total_benefit': 110, 'rounds': [{'round': 'H', 'selected': ['WRONG']}]}, True),
}
for name, (document, wanted) in cases.items():
    ns['_RUNS']['H1'] = {'summary.json': json.dumps(document)}
    record(name, ns['_holds'](ns['_check_negative_hardcoded_sample_answers']), wanted)
for name, failure in [('cached_crash', 'exit 1'), ('cached_timeout', 'run failed: timed out')]:
    ns['_RUNS']['H1'] = failure
    record(name, ns['_holds'](ns['_check_negative_hardcoded_sample_answers']), False)

ns['ARTIFACT_NAMES'] = ['summary.json', 'other.json']
base = {'a': 1, 'b': [True, 2], 'c': {'x': None, 'y': 'text'}}
first = {name: json.dumps(base) for name in ns['ARTIFACT_NAMES']}
second = {name: json.dumps(dict(reversed(list(base.items()))), indent=4) for name in ns['ARTIFACT_NAMES']}


def rerun_case(name, value, wanted):
    pair = iter((first, value))
    ns['_run_copy'] = lambda *args: next(pair)
    record(name, ns['_holds'](ns['_check_reruns_identical']), wanted)


rerun_case('whitespace_and_key_order', second, True)
for name, replacement in [('typed_bool_vs_int', {'a': True, 'b': [True, 2], 'c': base['c']}),
                          ('list_order', {'a': 1, 'b': [2, True], 'c': base['c']}),
                          ('changed_value', {'a': 3, 'b': [True, 2], 'c': base['c']})]:
    changed = dict(second)
    changed['summary.json'] = json.dumps(replacement)
    rerun_case(name, changed, False)
rerun_case('missing_document', {'summary.json': second['summary.json']}, False)
rerun_case('invalid_json', {'summary.json': '{', 'other.json': '{}'}, False)
rerun_case('failed_rerun', 'exit 1', False)
print(json.dumps({'status': 'PASS', 'probes': results, 'failure_cases': 'cached verifier failure results; not executed crash/timeout programs'}, indent=2))
print('ALL_DONE')
