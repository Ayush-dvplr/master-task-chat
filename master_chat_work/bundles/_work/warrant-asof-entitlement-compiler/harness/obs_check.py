import sys, random, time
sys.path.insert(0, "/h")
import load_t
t = load_t.load()
from pathlib import Path
root = Path(sys.argv[1]); n = int(sys.argv[2]); mode = sys.argv[3] if len(sys.argv) > 3 else "a"
D = t.load(root)
cfg, _, _ = t.settle_config(D)
rows = [r for _, r in D["att"]]
print("rows", len(rows), "distinct reviewed_at", len({r["reviewed_at"] for r in rows}))
rnd = random.Random(5)
import os
ids = os.environ.get("IDS")
sample = [r for r in rows if r["attestation_id"] in ids.split(",")] if ids else rnd.sample(rows, min(n, len(rows)))
ok = bad = skip = 0
t0 = time.time()
for r in sample:
    try:
        at = t.stamp(r["reviewed_at"])
    except t.Bad:
        skip += 1; continue
    c = dict(cfg)
    c["as_of"] = t.utc(at); c["recorded_cutoff"] = t.utc(at)
    if mode == "b":
        D2 = dict(D); D2["site"] = {k: dict(v) for k, v in D["site"].items()}
        D2["site"]["anchor"]["as_of"] = t.utc(at); D2["site"]["anchor"]["recorded_cutoff"] = t.utc(at)
        c, _, _ = t.settle_config(D2)
    for e in ("dev", "prod"):
        c[e + ".attestation_required"] = False; c[e + ".sod_enforced"] = False
    Wd = t.World(D, c)
    s = Wd.who(r["subject"])
    prof = Wd.profile(r["env"])
    got = "in_effect" if (s and (s + "|" + r["permission"]) in prof["keys"]) else "not_in_effect"
    if got == r["observed_state"]: ok += 1
    else:
        bad += 1; print("MISMATCH", r["attestation_id"], r["reviewed_at"], r["observed_state"], got)
print("ok", ok, "bad", bad, "skip", skip, "secs", round(time.time() - t0, 1))
