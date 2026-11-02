"""Try 2: stated-invocation variants through the existing generator family.
usage: python3 -B variants.py <tests_dir> <program_root> <outdir> <seed_name|int>
Compares each variant run with the reference documents; prints per variant the
documents that differ beyond the plain run of the same program."""
import sys, os, shutil, subprocess, json, stat
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import test_output as T

prog = Path(sys.argv[2]); outdir = Path(sys.argv[3]); outdir.mkdir(parents=True, exist_ok=True)
nm = sys.argv[4]
seed = getattr(T, nm) if not nm.isdigit() else int(nm)
data = Path(T._corpus(seed)); ref = T._reference(seed)
env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": str(prog / "src"),
       "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/tmp", "LC_ALL": "C"}


def run(args, cwd):
    p = subprocess.run([sys.executable, "-m", "slwopt"] + args, capture_output=True, text=True,
                       env=env, cwd=str(cwd), timeout=600)
    return p.returncode, p.stderr[-200:]


def wrong(dest):
    return sorted(n[:2] for n in T.ARTIFACT_NAMES if not (dest / n).is_file() or (dest / n).read_bytes() != ref[n])


base = outdir / "v_plain"; shutil.rmtree(base, ignore_errors=True)
res = {"plain": (run(["--out", str(base), "--data", str(data)], "/tmp"), wrong(base))}
work = outdir / "work"; shutil.rmtree(work, ignore_errors=True); work.mkdir()
# relative paths, cwd = work
shutil.copytree(data, work / "papers")
res["relative"] = (run(["--data", "papers", "--out", "o1"], work), wrong(work / "o1"))
# spaces and odd directory name
sp = work / "dir with space" / "x y"; shutil.copytree(data, sp)
res["spaces"] = (run(["--out", str(work / "o 2" / "deep"), "--data", str(sp)], "/"), wrong(work / "o 2" / "deep"))
# papers read only
ro = work / "ro"; shutil.copytree(data, ro)
for r, ds, fs in os.walk(ro):
    for f in fs:
        os.chmod(os.path.join(r, f), 0o444)
for r, ds, fs in os.walk(ro, topdown=False):
    os.chmod(r, 0o555)
res["readonly"] = (run(["--data", str(ro), "--out", str(work / "o3")], "/tmp"), wrong(work / "o3"))
# out dir pre-existing with a stale document
pre = work / "o4"; pre.mkdir(); (pre / "18_final_selection.json").write_text("{}\n")
res["stale_out"] = (run(["--data", str(data), "--out", str(pre)], "/tmp"), wrong(pre))
# cwd inside the papers
c5 = work / "c5"; shutil.copytree(data, c5)
res["cwd_papers"] = (run(["--out", str(work / "o5"), "--data", "."], c5), wrong(work / "o5"))
# trailing slash on paths
res["slash"] = (run(["--data", str(data) + "/", "--out", str(work / "o6") + "/"], "/tmp"), wrong(work / "o6"))
for k, v in res.items():
    print(k, json.dumps(v), flush=True)
print("ALL_DONE")
