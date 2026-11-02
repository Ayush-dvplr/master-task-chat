import importlib.util, json, re, subprocess, sys, tempfile, shutil, types
from pathlib import Path

test_path, program, shipped = (Path(x).resolve() for x in sys.argv[1:4])
rewardkit = types.ModuleType('rewardkit')
class Criteria:
    def __getattr__(self, name):
        return lambda **kw: None
rewardkit.criteria = Criteria()
rewardkit.criterion = lambda **kw: lambda f: f
sys.modules['rewardkit'] = rewardkit
spec = importlib.util.spec_from_file_location('snlsq_grader', test_path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
work = Path(tempfile.mkdtemp(prefix='snlsq-local-grade-'))
out = work/'out'; out.mkdir()
shutil.copyfile(program, out/'derive_report.py')
m.OUT = out
m.SCRIPT = out/'derive_report.py'
def run(data, dest):
    try:
        return subprocess.run([sys.executable, str(m.SCRIPT), str(data), str(dest)], cwd='/tmp', timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    except subprocess.TimeoutExpired:
        return -9
m._run_agent_program = run
shipped_code = run(shipped, out)
registrations = {n:int(w) for n,w in re.findall(r'criteria\.(\w+)\(weight=(-?\d+)\)', test_path.read_text())}
checks = [n for n in dir(m) if n.startswith('test_') and callable(getattr(m,n)) and n.removeprefix('test_') in registrations and registrations[n.removeprefix('test_')]>0]
points = 0; result = {}
for name in checks:
    weight = registrations[name.removeprefix('test_')]
    try: getattr(m,name)(); ok=True
    except Exception as e: ok=False; error=type(e).__name__+": "+str(e)
    result[name.removeprefix('test_')] = {'pass':ok,'weight':weight,'error':error if not ok else None}
    if ok: points+=weight
for name,weight in [('test_'+n,w) for n,w in registrations.items() if w<0]:
    try: getattr(m,name)(); ok=True
    except Exception: ok=False
    result[name.removeprefix('test_')]={'pass':ok,'weight':weight}
    if ok: points+=weight
print(json.dumps({'program':str(program),'tests':str(test_path),'shipped_code':shipped_code,'positive':points,'score':points/sum(w for w in registrations.values() if w>0),'checks':result},sort_keys=True))
