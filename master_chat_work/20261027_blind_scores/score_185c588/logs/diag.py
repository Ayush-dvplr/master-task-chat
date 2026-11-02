import ast, sys, time
from pathlib import Path
sys.path.insert(0, '/tests')
import test_output as t
src = Path('/tests/test_output.py').read_text()
bodies = {n.name: n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
rec = {}
def holds(check, *a):
    try:
        check(*a)
        return True
    except BaseException as e:
        m = str(e).strip()
        rec['exc'] = f"{type(e).__name__}: {m.splitlines()[0][:300] if m else ''}"
        return False
t._holds = holds
for n in sys.argv[1:]:
    rec.clear()
    fn = bodies[n]
    fn.decorator_list = []
    fn.name = '_diag_' + n
    mod = ast.Module(body=[fn], type_ignores=[])
    exec(compile(ast.fix_missing_locations(mod), 'diag', 'exec'), t.__dict__)
    s = time.time()
    try:
        r = t.__dict__['_diag_' + n](Path('/app'))
    except BaseException as e:
        r = f"RAISED {type(e).__name__}: {e}"
    print(f"DIAG\t{n}\t{r}\t{time.time()-s:.1f}s\t{rec.get('exc','')}", flush=True)
