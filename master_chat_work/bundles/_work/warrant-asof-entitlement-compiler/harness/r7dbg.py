import importlib.util, json, sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

spec = importlib.util.spec_from_file_location("solve", "/solution/solve.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
DATA = s.DATA
config = json.loads(Path(sys.argv[1], "config.json").read_text())
delivered = json.loads(Path(sys.argv[1], "profile_prod.json").read_text())


def rows(pattern):
    out = []
    for path in sorted(DATA.glob(pattern)):
        out += [json.loads(l) for l in path.open() if l.strip()]
    return out


import csv


def table(name, d=","):
    return list(csv.DictReader((DATA / name).open(newline=""), delimiter=d))


as_of, cutoff = s._when(config["as_of"]), s._when(config["recorded_cutoff"])
need, hours = int(config["prod.approvals_required"]), int(config["prod.max_grant_hours"])
aliases = {r["alias"].strip().lower() for r in table("directory_aliases.tsv", "\t")}
accounts = defaultdict(list)
for acc in rows("idp_accounts_*.jsonl"):
    accounts[acc["handle"].strip().lower()].append((acc["generation"], acc["subject_ref"]))


def person(h):
    h = h.strip().lower()
    f = sorted(accounts.get(h, []), reverse=True)
    if h in aliases or not f or (len(f) > 1 and f[0][0] == f[1][0]):
        return None
    return s._emp(f[0][1])


busy = set()
for n in ("oncall_assignments.csv", "oncall_swaps.csv"):
    busy |= {v.strip().lower() for r in table(n) for v in r.values() if v}
busy |= {r["subject"].strip().lower() for r in rows("revocations_secops.jsonl")}
moving = set()
for p in sorted(DATA.glob("hr_events_*.csv")):
    moving |= {s._emp(r["employee_no"]) for r in table(p.name) if r["event"] in ("terminate", "leave_start")}
touched = {r["ticket"] for r in rows("grant_corrections.jsonl")} | {r["ticket"] for r in table("revocations_selfservice.csv")}
req = defaultdict(list)
for q in rows("grant_requests_*.jsonl"):
    req[q["ticket"]].append(q)
per = defaultdict(int)
for f in req.values():
    for q in f:
        if q["env"] == "prod":
            per[q["beneficiary"].strip().lower()] += 1
votes = defaultdict(list)
for r in table("grant_approvals.csv"):
    votes[r["ticket"]].append(r)
c = Counter()
for tk, f in sorted(req.items()):
    q = f[0]
    ben = q["beneficiary"].strip().lower()
    pid = person(ben)
    for name, bad in (("multi", len(f) != 1), ("touched", tk in touched), ("env", q["env"] != "prod"),
                      ("role", not q["target"].startswith("perm:")), ("nofrom", not q.get("effective_from")),
                      ("nountil", not q.get("effective_until")), ("nopid", pid is None), ("moving", pid in moving),
                      ("busy", ben in busy)):
        if bad:
            c[name] += 1
            break
    else:
        b = votes.get(tk, [])
        if any(v["decision"] != "approve" or s._when(v["recorded_at"]) > cutoff for v in b):
            c["votes"] += 1
            continue
        c["pass_filters"] += 1
        seen, dec = set(), []
        rp = person(q["requester"])
        for v in sorted(b, key=lambda v: (s._when(v["decided_at"]), v["approval_id"])):
            w = person(v["approver"])
            if w is None or w in (pid, rp) or w in seen or w in moving:
                continue
            seen.add(w)
            dec.append(s._when(v["decided_at"]))
        if len(dec) < need:
            c["fewvotes"] += 1
            continue
        st = max(s._when(q["effective_from"]), dec[need - 1])
        en = min(s._when(q["effective_until"]), st + timedelta(hours=hours))
        key = f"{pid}|{q['target'][5:]}"
        if not st <= as_of < en:
            c["notlive"] += 1
        elif key not in delivered:
            c["notdelivered"] += 1
        else:
            got = s._when(delivered[key])
            c["ok" if got == en else ("later" if got > en else "EARLIER")] += 1
print(dict(c), "need", need, "busy", len(busy), "tickets", len(req))
why = Counter()
for v in table("grant_approvals.csv")[:3000]:
    h = v["approver"].strip().lower()
    f = sorted(accounts.get(h, []), reverse=True)
    why["alias" if h in aliases else "noacc" if not f else "tie" if len(f) > 1 and f[0][0] == f[1][0] else "ctr" if s._emp(f[0][1]) is None else "moving" if s._emp(f[0][1]) in moving else "ok"] += 1
print(dict(why))
print(table("grant_approvals.csv")[:3])
print(list(accounts.items())[:3])
