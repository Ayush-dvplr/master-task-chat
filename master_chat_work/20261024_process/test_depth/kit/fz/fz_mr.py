"""Differential fuzz driver for match-replay-desync-audit; runs inside the verifier image.
usage: python3 fz_mr.py <cases.jsonl> <results.jsonl> <workers>
Each case: {"id", "profile", "seed", "tweak", "struct"}; struct in
  none | renamed (corpus under foreign folder name) | cwd (cwd = /) | shuffle (data rows of csv shuffled)
"""
import json, os, random, shutil, sys, tempfile, time
from multiprocessing import Pool
from pathlib import Path
sys.path.insert(0, "/tests")
import test_output as T

AGENT = "/progs/agent/optimize.py"
ORACLE = "/progs/oracle/solve.py"


def tw(x):
    if isinstance(x, list):
        return tuple(x)
    return x


def diffs(p, w, path="$", out=None):
    out = [] if out is None else out
    if isinstance(w, dict) and isinstance(p, dict):
        for k in list(w) + [k for k in p if k not in w]:
            if k not in p or k not in w:
                out.append((path + "." + k, "only-one"))
            else:
                diffs(p[k], w[k], path + "." + k, out)
        return out
    if isinstance(w, list) and isinstance(p, list):
        for i, (a, b) in enumerate(zip(p, w)):
            diffs(a, b, "%s[%d]" % (path, i), out)
        if len(p) != len(w):
            out.append((path, "len %d vs %d" % (len(p), len(w))))
        return out
    if p != w or type(p) is not type(w):
        out.append((path, "%r vs %r" % (p, w)))
    return out


def shuffle_csv(corpus, rng):
    for f in sorted(corpus.glob("*.csv")):
        lines = f.read_text().splitlines(True)
        head, body = lines[:1], lines[1:]
        rng.shuffle(body)
        f.write_text("".join(head + body))


def run(prog, corpus, result, cwd):
    os.makedirs(result, exist_ok=True)
    T._relax(os.path.dirname(str(corpus)))
    os.chmod(result, 0o777)
    t0 = time.time()
    import subprocess, signal
    proc = subprocess.Popen(T._unprivileged() + [sys.executable, "-I", "-S", prog, str(corpus), str(result)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=T.LAUNCH_SECONDS)
    except subprocess.TimeoutExpired:
        T._kill_group(proc)
        out, err = proc.communicate()
        err = (err or "") + "\nran past %d seconds" % T.LAUNCH_SECONDS
    finally:
        T._kill_group(proc)
    return proc.returncode, round(time.time() - t0, 1), (err or "")[-300:]


def one(case):
    seed, tweak, struct = case["seed"], tw(case["tweak"]), case["struct"]
    room = tempfile.mkdtemp(prefix="fz-")
    os.chmod(room, 0o755)
    folder = "data" if struct != "renamed" else "Capture Set (moved)"
    corpus = Path(room) / folder
    try:
        plan = T.replay_plan(seed, tweak)
        T.assert_postconditions(plan)
    except AssertionError as e:
        # tests' _trap_only stages ("only", bit) corpora without postconditions; the presence floor
        # cannot hold for a single-bit corpus, so waive only that check for those tweaks.
        if not (isinstance(tweak, tuple) and tweak[0] == "only" and "presence floor" in str(e)):
            shutil.rmtree(room, ignore_errors=True)
            return {**case, "gen_error": str(e)[:200]}
        case = {**case, "post_waived": str(e)[:80]}
    T._emit_corpus(corpus, plan, T._spec_notes())
    if struct == "shuffle":
        shuffle_csv(corpus, random.Random(seed))
    size = sum(f.stat().st_size for f in corpus.iterdir())
    exp = T.expected_reports(plan)
    cwd = "/" if struct == "cwd" else room
    rec = {**case, "bytes": size, "entries": plan.get("entry_total")}
    for who, prog in (("agent", AGENT), ("oracle", ORACLE)):
        res = Path(room) / (who + "-out")
        code, secs, err = run(prog, corpus, res, cwd)
        rep = {"code": code, "secs": secs}
        if code != 0:
            rep["err"] = err
        dd = {}
        for name, want in exp.items():
            f = res / name
            if not f.exists():
                dd[name] = [["$", "missing"]]
                continue
            try:
                got = json.loads(f.read_text())
            except ValueError:
                dd[name] = [["$", "bad json"]]
                continue
            d = diffs(got, want)
            if d:
                dd[name] = [list(x) for x in d[:40]] + ([["...", "%d more" % (len(d) - 40)]] if len(d) > 40 else [])
        rep["diff"] = dd
        rec[who] = rep
    shutil.rmtree(room, ignore_errors=True)
    return rec


if __name__ == "__main__":
    cases = [json.loads(l) for l in open(sys.argv[1])]
    done = set()
    if os.path.exists(sys.argv[2]):
        done = {json.loads(l)["id"] for l in open(sys.argv[2])}
    todo = [c for c in cases if c["id"] not in done]
    with Pool(int(sys.argv[3])) as pool, open(sys.argv[2], "a") as out:
        for r in pool.imap_unordered(one, todo):
            out.write(json.dumps(r) + "\n")
            out.flush()
