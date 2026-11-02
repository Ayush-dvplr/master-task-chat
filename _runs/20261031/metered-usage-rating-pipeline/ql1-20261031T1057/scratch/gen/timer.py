import os, resource, shutil, subprocess, sys, tempfile, time
# usage: timer.py PROGRAM CAP_S MONTHS_ROOT LABEL...
prog, cap, root = sys.argv[1], float(sys.argv[2]), sys.argv[3]
for lab in sys.argv[4:]:
    work = tempfile.mkdtemp(prefix="t-")
    inp = os.path.join(work, "extract"); out = os.path.join(work, "reports")
    shutil.copytree(os.path.join(root, lab), inp); os.mkdir(out)
    r0 = resource.getrusage(resource.RUSAGE_CHILDREN); t0 = time.perf_counter()
    try:
        rc = subprocess.run([sys.executable, "-I", prog, "--input", inp, "--output", out],
                            cwd=work, timeout=cap, capture_output=True).returncode
    except subprocess.TimeoutExpired:
        rc = "TIMEOUT"
    w = time.perf_counter() - t0; r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    print("%s wall_s=%.2f user_s=%.2f sys_s=%.2f rc=%s outfiles=%d" % (
        lab, w, r1.ru_utime - r0.ru_utime, r1.ru_stime - r0.ru_stime, rc, len(os.listdir(out))), flush=True)
    shutil.rmtree(work)
