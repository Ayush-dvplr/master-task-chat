import sys, csv, io, datetime as dt
sys.path.insert(0, sys.argv[1])
import ref_core as rc
D = sys.argv[2]
files = {n: open(D + "/" + n, "rb").read() for n in rc.REF_INPUTS}
par = {}
for row in csv.DictReader(io.StringIO(files["accounts.csv"].decode())):
    par[rc.ref_canon(row["account_id"])] = rc.ref_canon(row["parent"] or "")
def depth(a):
    n = 1
    while par.get(a):
        a = par[a]; n += 1
    return n
dist = {}
for a in par:
    d = depth(a); dist[d] = dist.get(d, 0) + 1
print("chain length per account", sorted(dist.items()))
usage = {}
for region in rc.REF_REGIONS:
    for rid, ts, acct, prod, units, kind in rc._ref_records(region, files[rc.REF_FILES[region]]):
        usage.setdefault(rc.ref_canon(acct), []).append(ts)
UTC = dt.timezone.utc
tot = known = before = 0
for ln in rc._ref_lines(files["plan_changes.log"].decode()):
    tot += 1
    p = ln.strip().split()
    ts = dt.datetime.strptime(p[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    kv = dict(x.split("=", 1) for x in p[2:])
    a = rc.ref_canon(kv["account"])
    if a not in par: continue
    known += 1
    if any(t >= ts for t in usage.get(a, [])): before += 1
print("plan changes", tot, "known account", known, "precede a later usage line of the account", before)
out = rc.ref_compute(files)
print(type(out), list(out)[:20] if isinstance(out, dict) else "")
import json
for r in rc.REF_REGIONS:
    print(r, out["region_%s.json" % r].decode()[:400] if isinstance(out["region_%s.json" % r], bytes) else str(out["region_%s.json" % r])[:400])
