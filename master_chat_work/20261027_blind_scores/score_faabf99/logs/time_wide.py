# Timing diagnostic: runs each program on the verifier's two wide extracts (built by test_output.wide_root) with a cap.
import sys, time, subprocess, os, signal, json, tempfile
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/tests")
import test_output as T
CAP = int(os.environ.get("CAP", "400"))
progs = sys.argv[1:]
def run(prog, k, data):
    out = tempfile.mkdtemp(prefix=f"o-{os.path.basename(prog)}-{k}-")
    t0 = time.monotonic()
    p = subprocess.Popen([sys.executable, prog, str(data), out + "/out"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
    try:
        _, err = p.communicate(timeout=CAP); code = p.returncode
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL); p.communicate(); code = None; err = b""
    dt = time.monotonic() - t0
    return {"prog": os.path.basename(prog), "wide": k, "seconds": round(dt, 2), "exit": code, "timed_out": code is None, "stderr_tail": err.decode()[-300:]}
for k in (0, 1):
    data, _ = T.wide_root(k)
    with ThreadPoolExecutor(len(progs)) as ex:
        for r in ex.map(lambda pr: run(pr, k, data), progs):
            print(json.dumps(r), flush=True)
print("DIAG_DONE", flush=True)
