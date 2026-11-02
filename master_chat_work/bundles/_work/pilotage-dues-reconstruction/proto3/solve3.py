"""Prototype solver v3 (proto only; never shipped). Parses the design-blind layout.

usage: solve3.py MODE DATA_DIR OUT_DIR
MODE ref  full stated domains (reference)
     K1   one convention everywhere (marks 1, 22:00-06:00, assist reckoned, own calendar, Monday kept)
     K4w  careful natural-wide: marks {1,15,16,30}/{1,5,6,10}, all calendars, whole-hour windows
     K4q  every mark, every calendar, quarter-hour windows only
"""
import csv
import json
import os
import re
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core3 import (TARIFFS, STATIONS, KA_ALL, KD_ALL, fit, n_conventions, true_due)  # noqa: E402

PAID = {"North": "paid_north.csv", "South": "paid_south.jsonl", "West": "paid_west.txt",
        "East": "paid_east.xml"}
DATA_FILES = ["pilot_movements.log", "vessel_register.tsv", "certificates.json", "holidays.json",
              "station_notices.md", "paid_north.csv", "paid_south.jsonl", "paid_west.txt",
              "paid_east.xml", "disputed_batch.csv"]
REASON = "more than one listed tariff reproduces every paid invoice"
MONEY = re.compile(r"^\d+\.\d{2}$")
XML = re.compile(r'^<invoice id="([^"]*)" visit="([^"]*)" date="([^"]*)" amount="([^"]*)"/>$')


def fatal(name):
    sys.stderr.write(f"ERROR unreadable input: {name}\n")
    sys.exit(2)


def money(c):
    s = "-" if c < 0 else ""
    c = abs(c)
    return f"{s}{c // 100}.{c % 100:02d}"


def cents(s):
    a, b = s.split(".")
    return int(a) * 100 + int(b)


def coef(x):
    return f"{x // 100}.{x % 100:02d}"


def okdate(s):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", s or ""):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def read(data, name):
    p = os.path.join(data, name)
    if not os.path.isfile(p):
        fatal(name)
    with open(p, encoding="utf-8") as f:
        return f.read().split("\n")


def main():
    mode, data, out = sys.argv[1], sys.argv[2], sys.argv[3]
    for n in DATA_FILES:
        if not os.path.isfile(os.path.join(data, n)):
            fatal(n)
    try:
        certs = json.loads("\n".join(read(data, "certificates.json")))
    except ValueError:
        fatal("certificates.json")
    try:
        hol = json.loads("\n".join(read(data, "holidays.json")))
        cals = {k: {date.fromisoformat(x) for x in v} for k, v in hol["calendars"].items()}
    except (ValueError, KeyError, TypeError):
        fatal("holidays.json")
    reg_lines = read(data, "vessel_register.tsv")
    if reg_lines[0] != "vessel_id\tname\tgross_tonnage\tsegment\tcertificate":
        fatal("vessel_register.tsv")
    reg = {}
    for ln in reg_lines[1:]:
        if ln:
            p = ln.split("\t")
            reg[p[0]] = {"gt": int(p[2]), "segment": p[3], "cert": p[4]}
    visits = {}
    for ln in read(data, "pilot_movements.log"):
        p = ln.split()
        if len(p) >= 7 and p[2] == "BOARD":
            kv = dict(x.split("=", 1) for x in p[6:])
            m, cm = kv["draft"].split(".")
            visits[p[4]] = {"station": p[3], "vessel": p[5], "day": date.fromisoformat(p[0]),
                            "minute": int(p[1][:2]) * 60 + int(p[1][3:]), "cm": int(m) * 100 + int(cm),
                            "tugs": int(kv["tugs"]), "assist": int(kv.get("assist", "0"))}
    known = {k: v for k, v in visits.items() if v["vessel"] in reg}
    for v in known.values():
        r = reg[v["vessel"]]
        v["gt"] = r["gt"]
        v["segment"] = r["segment"]
        c = certs.get(r["cert"]) if r["cert"] else None
        v["exempt"] = bool(r["segment"] == "public" and c and v["day"] < date.fromisoformat(c["expiry"]))
    notices = {}
    for ln in read(data, "station_notices.md"):
        m = re.match(r"^\|\s*(North|South|West|East)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|", ln)
        if m:
            notices[m.group(1)] = date.fromisoformat(m.group(2))

    # paid records: (file, line, station, fields or None)
    paid = []
    L = read(data, "paid_north.csv")
    if L[0] != "invoice_id,visit_id,invoice_date,amount":
        fatal("paid_north.csv")
    for i, ln in enumerate(L[1:], 2):
        if ln:
            p = ln.split(",")
            paid.append(("paid_north.csv", i, "North", p if len(p) == 4 else None))
    for i, ln in enumerate(read(data, "paid_south.jsonl"), 1):
        if ln:
            try:
                o = json.loads(ln)
                p = [o["invoice_id"], o["visit_id"], o["invoice_date"], o["amount"]]
                p = p if all(isinstance(x, str) for x in p) else None
            except (ValueError, KeyError, TypeError):
                p = None
            paid.append(("paid_south.jsonl", i, "South", p))
    for i, ln in enumerate(read(data, "paid_west.txt"), 1):
        if ln:
            p = [ln[0:10].strip(), ln[10:18].strip(), ln[18:28].strip(), ln[28:40].strip()]
            paid.append(("paid_west.txt", i, "West", p if all(p) else None))
    L = read(data, "paid_east.xml")
    while L and L[-1] == "":
        L.pop()
    if not L or L[0] != '<paid_invoices station="East">' or L[-1] != "</paid_invoices>":
        fatal("paid_east.xml")
    for i, ln in enumerate(L[1:-1], 2):
        m = XML.match(ln)
        paid.append(("paid_east.xml", i, "East", list(m.groups()) if m else None))
    L = read(data, "disputed_batch.csv")
    if L[0] != "invoice_id,visit_id,station,invoice_date,billed":
        fatal("disputed_batch.csv")
    disp = []
    for i, ln in enumerate(L[1:], 2):
        if ln:
            p = ln.split(",")
            disp.append(("disputed_batch.csv", i, None, p if len(p) == 5 else None))

    rejected = []

    def screen(recs, amt_idx, st_idx):
        good = []
        for r in recs:
            p = r[3]
            if p is None or any(x == "" for x in p) or not okdate(p[2 if st_idx is None else 3]) \
                    or not MONEY.match(p[amt_idx]):
                rejected.append((r[0], r[1], "malformed_record"))
            else:
                good.append(r)
        cnt = {}
        for r in good:
            cnt[r[3][0]] = cnt.get(r[3][0], 0) + 1
        acc = []
        for r in good:
            p = r[3]
            st = r[2] if st_idx is None else p[st_idx]
            if cnt[p[0]] > 1:
                code = "duplicate_invoice"
            elif p[1] not in known:
                code = "unknown_visit"
            elif known[p[1]]["station"] != st:
                code = "station_mismatch"
            else:
                acc.append((st, p))
                continue
            rejected.append((r[0], r[1], code))
        return acc

    acc_paid = screen(paid, 3, None)
    acc_disp = screen(disp, 4, 2)

    def period(st, v):
        return 1 if st in notices and v["day"] >= notices[st] else 0

    def starts(st):
        return [date(2026, 7, 1)] + ([notices[st]] if st in notices else [])

    convs, tariffs = {}, {}
    for st in STATIONS:
        groups = [[] for _ in starts(st)]
        for s2, p in acc_paid:
            if s2 == st:
                v = known[p[1]]
                if not v["exempt"]:
                    groups[period(st, v)].append({**v, "amount": cents(p[3])})
        kw = {}
        if mode == "K1":
            kw = dict(domA=[1], domD=[1], domB=[True], domH=[st.lower()], domS=[True],
                      win_filter=lambda s, e: (s, e) == (1320, 360))
        elif mode == "K4w":
            kw = dict(domA=[1, 15, 16, 30], domD=[1, 5, 6, 10], win_filter=lambda s, e: s % 60 == 0 and e % 60 == 0)
        elif mode == "K4q":
            kw = dict(win_filter=lambda s, e: s % 15 == 0 and e % 15 == 0)
        res = fit(groups, cals, **kw)
        if mode == "ref":
            assert n_conventions(res) == 1, (st, n_conventions(res))
        res = [x for x in res if x[1] is not None]
        if res:
            c, per = res[0]
            convs[st] = c
            tariffs[st] = [x[0] if len(x) == 1 else None for x in per]
        else:
            convs[st] = None
            tariffs[st] = [None for _ in groups]

    rows = []
    for st, p in acc_disp:
        v = known[p[1]]
        k = period(st, v)
        t = tariffs[st][k]
        billed = cents(p[4])
        row = {"invoice_id": p[0], "visit_id": p[1], "station": st,
               "period_start": starts(st)[k].isoformat(), "segment": v["segment"], "billed": billed}
        if t is None:
            row.update(recomputed=None, difference=None, verdict="cannot_recompute", reason=REASON)
        else:
            rc = true_due(t, v, convs[st], cals)
            row.update(recomputed=rc, difference=billed - rc, reason=None,
                       verdict="billed_correctly" if billed == rc else
                       ("overbilled" if billed > rc else "underbilled"))
        rows.append(row)
    rows.sort(key=lambda r: r["invoice_id"])
    VERD = ["billed_correctly", "overbilled", "underbilled", "cannot_recompute"]

    def agg(rs):
        vc = {k: 0 for k in VERD}
        for r in rs:
            vc[r["verdict"]] += 1
        return {"disputes": len(rs), "verdict_counts": vc,
                "billed_total": money(sum(r["billed"] for r in rs)),
                "recomputed_total": money(sum(r["recomputed"] for r in rs if r["recomputed"] is not None)),
                "refund_total": money(sum(r["difference"] for r in rs if r["verdict"] == "overbilled")),
                "shortfall_total": money(-sum(r["difference"] for r in rs if r["verdict"] == "underbilled"))}

    os.makedirs(out, exist_ok=True)

    def w(name, obj):
        with open(os.path.join(out, name), "w") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")

    s = agg(rows)
    refunds = [r for r in rows if r["verdict"] == "overbilled"]
    lr = None
    if refunds:
        best = min(refunds, key=lambda r: (-r["difference"], r["invoice_id"]))
        lr = {"invoice_id": best["invoice_id"], "amount": money(best["difference"])}
    unres = [{"station": st, "period_start": starts(st)[k].isoformat()}
             for st in STATIONS for k, t in enumerate(tariffs[st]) if t is None]
    w("summary.json", {**s, "unresolved": unres, "largest_refund": lr})

    def m(x):
        return None if x is None else money(x)

    w("policy_audit.json", {"rows": [{**r, "billed": money(r["billed"]), "recomputed": m(r["recomputed"]),
                                      "difference": m(r["difference"])} for r in rows]})
    rejected.sort(key=lambda x: (x[0], x[1]))
    codes = ["malformed_record", "duplicate_invoice", "unknown_visit", "station_mismatch"]
    w("data_quality.json", {"rejected": [{"file": a, "line": b, "code": c} for a, b, c in rejected],
                            "counts": {c: sum(1 for x in rejected if x[2] == c) for c in codes}})
    for st in STATIONS:
        pers = []
        for k, d0 in enumerate(starts(st)):
            t = tariffs[st][k]
            n = sum(1 for s2, p in acc_paid if s2 == st and period(st, known[p[1]]) == k)
            pers.append({"period_start": d0.isoformat(),
                         "tariff": None if t is None else dict(zip(
                             ["base_per_100gt", "draft_per_dm", "night_factor", "per_tug"],
                             [coef(t[0]), coef(t[1]), coef(t[2]), coef(t[3])])),
                         "reason": REASON if t is None else None, "paid_invoices": n})
        a = agg([r for r in rows if r["station"] == st])
        w(f"region_{st}.json", {"station": st, "periods": pers, "disputes": a["disputes"],
                                "verdict_counts": a["verdict_counts"], "refund_total": a["refund_total"],
                                "shortfall_total": a["shortfall_total"]})
    for seg in ("commercial", "public"):
        rs = [r for r in rows if r["segment"] == seg]
        w(f"segment_{seg}.json", {"segment": seg, **{k: v for k, v in agg(rs).items()},
                                  "vessels": len({known[r["visit_id"]]["vessel"] for r in rs})})


if __name__ == "__main__":
    main()
