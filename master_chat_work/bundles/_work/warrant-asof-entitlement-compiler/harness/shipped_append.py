"""Append the minimum dev-env evidence rows to the shipped access_attestations.csv so that
the decided start reading is the only one of the start rivals that reproduces every observation.
Usage: shipped_append.py <shipped data dir (ro)> <out dir>   (REF env = reference module path)"""
import csv, io, os, random, shutil, sys, time
from pathlib import Path
sys.path.insert(0, "/h")
import load_t

t = load_t.load(os.environ.get("REF", "/w/proto_ref/test_output.py"))
src, out = Path(sys.argv[1]), Path(sys.argv[2])
root = Path("/tmp/shipped_copy")
if root.exists():
    shutil.rmtree(root)
shutil.copytree(src, root)
t0 = time.time()
conv = dict(t.SHIPPED_CONV)
r = random.Random(7)  # observe() stream for seed 0: seed * 13 + 7
path = root / "access_attestations.csv"
rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
fields = list(rows[0])
offsets = sorted({0, 60, 120, -240, -300, -420, 330, 600, 660, 540, -180})
D = t.load(root)
cfg, _, _ = t.settle_config(D)
cfg = dict(cfg)
for e in t.GATE_ENVS:
    cfg[e + ".attestation_required"] = False
    cfg[e + ".sod_enforced"] = False
W0 = t.World(D, cfg, conv)
E, R = W0.E, W0.R
live = sorted(p for p, s in W0.profile("prod")["status"].items() if s == "eligible" and p.startswith("emp:"))
hand = {p: sorted(h) for p, h in W0.mine.items()}
seq = max(int(x["attestation_id"].split("-")[1]) for x in rows)
memo = {}
rivals = ["recorded", "latest"]
kills = {a: 0 for a in rivals}
new = []
Ws = {s: t.World(D, cfg, dict(conv, start=s)) for s in ["decided"] + rivals}
lo_lim, hi_lim = E - 300 * t.DAY, min(E, R) - 2 * t.HOUR
cands = []
for rid in sorted(W0.tk):
    ts_ = [Ws[s].tk[rid] for s in Ws]
    if any(x.get("state") != "approved" for x in ts_) or W0.tk[rid]["ben"] not in hand or W0.tk[rid]["env"] != "dev":
        continue
    ends = sorted({x["end"] for x in ts_})
    if len(ends) < 2 or ends[0] - 2 * t.HOUR < lo_lim or ends[-1] + 2 * t.HOUR > hi_lim:
        continue
    cands.append(rid)
r.shuffle(cands)
print("candidate dev tickets", len(cands), flush=True)
tried = 0
for rid in cands:
    if all(kills[a] >= 2 for a in rivals) or tried >= 80:
        break
    tried += 1
    tk = W0.tk[rid]
    ends = sorted({Ws[s].tk[rid]["end"] for s in Ws})
    perm = sorted(tk["perms"])[0]
    ats = sorted({(a + b) // 2 for a, b in zip(ends, ends[1:])})
    probe = [{"subject": hand[tk["ben"]][0], "permission": perm, "env": "dev", "reviewed_at": t.iso_z(at)} for at in ats]
    base = t.gateway_states(D, probe, conv, memo)
    for i, at in enumerate(ats):
        hit = [a for a in rivals if kills[a] < 2 and t.gateway_states(D, [probe[i]], dict(conv, start=a), memo)[0] != base[i]]
        if not hit:
            continue
        for a in hit:
            kills[a] += 1
        pid = tk["ben"]
        rev = r.choice([p for p in live if p != pid and hand.get(p)])
        seq += 1
        new.append({"attestation_id": f"AT-{seq:06d}", "reviewer": r.choice(hand[rev]), "subject": r.choice(hand[pid]),
                    "permission": perm, "env": "dev", "reviewed_at": t.iso_off(at, r.choice(offsets)), "decision": "keep",
                    "observed_state": "", "recorded_at": t.iso_z(min(at + 600, R - 1))})
        print("row", rid, perm, t.iso_z(at), "kills", hit, flush=True)
# label the appended rows only (old rows keep their bytes)
for row, st in zip(new, t.gateway_states(D, new, conv, memo)):
    row["observed_state"] = st
for a in rivals:
    st = t.gateway_states(D, new, dict(conv, start=a), memo)
    print("rival", a, "mismatching appended rows", sum(1 for x, y in zip(new, st) if x["observed_state"] != y), flush=True)
buf = io.StringIO()
w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
for row in new:
    w.writerow(row)
old = path.read_text(encoding="utf-8")
assert old.endswith("\n")
out.mkdir(parents=True, exist_ok=True)
(out / "access_attestations.csv").write_text(old + buf.getvalue(), encoding="utf-8")
print("appended", len(new), "kills", kills, "secs %.1f" % (time.time() - t0), flush=True)
# reference outputs before/after on profiles
before = t.everything(src)
(root / "access_attestations.csv").write_text(old + buf.getvalue(), encoding="utf-8")
after = t.everything(root)
print("profiles identical", before[1] == after[1], "audit identical except self_check",
      {k: before[2][k] == after[2][k] for k in before[2]}, flush=True)
