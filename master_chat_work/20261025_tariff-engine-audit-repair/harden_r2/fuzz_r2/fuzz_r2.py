"""Differential fuzz, round 2: new-generator corpora (one lever planted per corpus, or none)
run through the probe-2 agent program and compared with the test file's reference ledger.
Usage: python3 fuzz_r1.py N_PER_FAMILY OUT_JSON"""
import importlib.util, json, os, random, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
WORK = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/tariff-engine-audit-repair")
AGENT = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261025_tariff-engine-audit-repair/harden_r2/agent_program/repo/src")
sys.path.insert(0, str(WORK / "rewardkit_stub"))
spec = importlib.util.spec_from_file_location("T", WORK / "test_output.src.py")
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
FAMILIES = {"none": frozenset(), "N1": frozenset({"N1"}), "N2": frozenset({"N2"}), "N3": frozenset({"N3"})}

def one(job):
    fam, seed, size = job
    try:
        texts, info = T._corpus(seed, size, (), FAMILIES[fam])
    except Exception as e:  # generator refused the draw; recorded, not compared
        return {"fam": fam, "seed": seed, "gen_error": f"{type(e).__name__}: {e}"[:120]}
    d = Path(tempfile.mkdtemp(prefix="dd7fz-"))
    T._write_texts(texts, d)
    env = dict(os.environ, PYTHONPATH=str(AGENT), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-m", "tariff", str(d)], capture_output=True, text=True, env=env, timeout=120)
    if p.returncode:
        return {"fam": fam, "seed": seed, "differ": True, "why": "exit %d" % p.returncode}
    got = json.loads(p.stdout); exp = T._Ledger(texts).document()
    bad = sorted({k for g, e in zip(got["invoices"], exp["invoices"]) for k in ("lines", "subtotal", "credit", "total") if g.get(k) != e.get(k)})
    return {"fam": fam, "seed": seed, "differ": got != exp, "keys": bad,
            "accounts_differ": sum(g != e for g, e in zip(got["invoices"], exp["invoices"])), "accounts": len(exp["invoices"])}

if __name__ == "__main__":
    n, out = int(sys.argv[1]), sys.argv[2]
    rng = random.Random(0x0DD7A8C)
    jobs = [(f, rng.randrange(1, 10**9), rng.choice([12, 24, 30, 45])) for f in FAMILIES for _ in range(n)]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(one, jobs))
    summ = {}
    for f in FAMILIES:
        rs = [r for r in res if r["fam"] == f and "gen_error" not in r]
        summ[f] = {"valid": len(rs), "gen_error": sum(1 for r in res if r["fam"] == f and "gen_error" in r),
                   "differ": sum(r["differ"] for r in rs),
                   "share": round(sum(r["differ"] for r in rs) / max(len(rs), 1), 4),
                   "accounts_differ_share": round(sum(r.get("accounts_differ", 0) for r in rs) / max(sum(r.get("accounts", 0) for r in rs), 1), 4)}
    json.dump({"summary": summ, "results": res}, open(out, "w"), indent=1)
    print(json.dumps(summ, indent=1)); print("ALL_DONE")
