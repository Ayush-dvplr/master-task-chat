"""Diagnose: reference vs a program over the four existing seeds.
usage: python3 -B diag.py <tests_dir> <program_root> <outdir> [seed_name ...]"""
import sys, time, os, subprocess, difflib, json
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import test_output as T

prog = Path(sys.argv[2])
outdir = Path(sys.argv[3]); outdir.mkdir(parents=True, exist_ok=True)
names = sys.argv[4:] or ["SAMPLE_SEED", "EVAL_SEED", "CHALLENGE_SEED", "PROBE_SEED"]
summary = {}
for nm in names:
    legacy = ()
    if ":" in nm:
        head, tail = nm.split(":")
        seed = int(head); legacy = tuple(x for x in tail.split(",") if x)
    else:
        seed = getattr(T, nm) if not nm.isdigit() else int(nm)
    t0 = time.time()
    try:
        if legacy:
            import tempfile
            data = Path(tempfile.mkdtemp(prefix="held")); T.write_corpus(data, seed, legacy); t1 = time.time()
            rdir = Path(tempfile.mkdtemp(prefix="heldref")); T.ref_publish(data, rdir, ())
            ref = {n: (rdir / n).read_bytes() for n in T.ARTIFACT_NAMES}; t2 = time.time()
        else:
            data = T._corpus(seed); t1 = time.time()
            ref = T._reference(seed); t2 = time.time()
    except (SystemExit, Exception) as exc:
        summary[nm] = {"skipped": repr(exc)[:200]}
        print(nm, "SKIPPED", repr(exc)[:200], flush=True)
        continue
    dest = outdir / ("run_" + nm.replace(":", "_").replace(",", "+"))
    if dest.exists():
        import shutil; shutil.rmtree(dest)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": str(prog / "src"),
           "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/tmp", "LC_ALL": "C"}
    opts = ["--data", str(data), "--out", str(dest)] if seed == T.PROBE_SEED else ["--out", str(dest), "--data", str(data)]
    p = subprocess.run([sys.executable, "-m", "slwopt"] + opts, capture_output=True, text=True, env=env, cwd="/tmp", timeout=600)
    t3 = time.time()
    rec = {"corpus_s": round(t1 - t0, 2), "ref_s": round(t2 - t1, 2), "prog_s": round(t3 - t2, 2), "rc": p.returncode,
           "stderr": p.stderr[-300:], "wrong": []}
    if p.returncode == 0:
        for name in T.ARTIFACT_NAMES:
            f = dest / name
            if not f.is_file():
                rec["wrong"].append(name + " absent"); continue
            if f.read_bytes() != ref[name]:
                rec["wrong"].append(name)
                a = ref[name].decode(errors="replace").splitlines()
                b = f.read_bytes().decode(errors="replace").splitlines()
                d = list(difflib.unified_diff(a, b, "reference", "program", n=0, lineterm=""))
                (outdir / (nm.replace(":", "_").replace(",", "+") + "__" + name + ".diff")).write_text("\n".join(d[:80]) + "\n")
    summary[nm] = rec
    print(nm, json.dumps(rec), flush=True)
(outdir / "summary.json").write_text(json.dumps(summary, indent=1))
print("ALL_DONE")
