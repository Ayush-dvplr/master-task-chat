"""Shrunk corpus N2-016 (seed 11243377, fixes prec env ident): month_load_index rows where oracle, chain-depth mutant and probe-3 program differ, plus the waits behind them."""
import os, subprocess, sys, tempfile, shutil, json, csv
sys.path.insert(0, "/tests"); sys.path.insert(0, "/fz")
import test_output as T
import fz_cm_copy as F
files, _ = T.build_all(11243377)
F.fixtures(files, ["prec", "env", "ident"], 11243377)
tmp = tempfile.mkdtemp(); data = os.path.join(tmp, "data"); F.write(files, data)
outs = {}
for lab in ("oracle", "mut_N2", "agent_p3"):
    o = os.path.join(tmp, lab); os.makedirs(o)
    subprocess.run([sys.executable, "-B", "/progs/%s/reconcile.py" % lab, data, o], check=True, capture_output=True)
    outs[lab] = {tuple(r[:2]): r for r in csv.reader(open(os.path.join(o, "month_load_index.csv")))}
st = T.compute(data)
for k in sorted(outs["oracle"]):
    rows = {l: outs[l].get(k) for l in outs}
    if len({tuple(v) for v in rows.values()}) > 1:
        print("month_load_index", k, {l: v[4] for l, v in rows.items()}, "(reserve_minutes: oracle / chain-depth mutant / probe-3)")
        for b in st["blocked_rows"]:
            w = st["winners"][b["commitment_key"]]
            if (w["commitment_day"][:7], w["obligor_actor"]) == k and st["wait"][b["commitment_key"]] != int(b["chain_depth"]):
                print("   ", b["commitment_key"], "wait", st["wait"][b["commitment_key"]], "chain_depth", b["chain_depth"])
shutil.rmtree(tmp)
