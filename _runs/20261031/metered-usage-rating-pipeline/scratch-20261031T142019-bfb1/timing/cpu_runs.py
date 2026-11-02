import sys, time, subprocess, resource, glob, os, shutil
solve = sys.argv[1]
for d in sorted(glob.glob(os.path.join(os.environ["TMPDIR"], "qct-*")), key=os.path.getmtime):
    out = os.path.join(d, "out2")
    shutil.rmtree(out, ignore_errors=True)
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    w0 = time.time()
    p = subprocess.run([sys.executable, "-I", solve, "--input", os.path.join(d, "in"), "--output", out], capture_output=True, text=True)
    w1 = time.time()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    lines = sum(1 for _ in open(os.path.join(out, "normalized.jsonl"))) if p.returncode == 0 else -1
    print("%s wall %.2fs cpu %.2fs rc %s lines %d" % (os.path.basename(d), w1 - w0, cpu, p.returncode, lines), flush=True)
print("CPU_DONE", flush=True)
