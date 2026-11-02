"""Seeded stdlib generator for environment/ci data of tariff-engine-audit-repair.

Writes meter_reads.jsonl, accounts.csv, billing_periods.csv, rate_card.json,
regression_cases.jsonl, failing_tests.log, lint_report.json, package_manifest.json
into BUNDLE/environment/ci. api_contract.md and build_config.json are hand written.
Shipped data: calendar-month periods only, no half-cent tie in any line or credited total.
"""
import csv
import io
import json
import os
import random
import sys
import tempfile
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent.parent / "tariff-engine-audit-repair"
CI = BUNDLE / "environment" / "ci"
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BUNDLE / "environment" / "repo" / "src"))
import refengine  # noqa: E402
from tariff import build_invoices as shipped_build  # noqa: E402

SEED = 583917
rng = random.Random(SEED)

CARD = {
    "currency": "EUR",
    "plans": {
        "HOME-A": {"standing_charge": 18.60, "credit_rate": 0.02,
                   "tiers": [{"up_to": 200, "rate": 0.2153}, {"up_to": 600, "rate": 0.1877},
                             {"up_to": None, "rate": 0.1631}]},
        "HOME-B": {"standing_charge": 21.45, "credit_rate": 0.03,
                   "tiers": [{"up_to": 150, "rate": 0.2312}, {"up_to": 500, "rate": 0.2034},
                             {"up_to": None, "rate": 0.1789}]},
        "SME-1": {"standing_charge": 34.20, "credit_rate": 0.05,
                  "tiers": [{"up_to": 400, "rate": 0.1986}, {"up_to": 1200, "rate": 0.1742},
                            {"up_to": None, "rate": 0.1528}]},
        "SME-2": {"standing_charge": 39.90, "credit_rate": 0.06,
                  "tiers": [{"up_to": 300, "rate": 0.2079}, {"up_to": 900, "rate": 0.1833},
                            {"up_to": None, "rate": 0.1611}]},
        "IND-1": {"standing_charge": 52.75, "credit_rate": 0.05,
                  "tiers": [{"up_to": 800, "rate": 0.1714}, {"up_to": None, "rate": 0.1497}]},
        "IND-2": {"standing_charge": 61.30, "credit_rate": 0.06,
                  "tiers": [{"up_to": 1000, "rate": 0.1658}, {"up_to": 3000, "rate": 0.1432},
                            {"up_to": None, "rate": 0.1275}]},
    },
}
PLANS = sorted(CARD["plans"])
MONTHS = [(date(2026, 2, 1), date(2026, 2, 28)), (date(2026, 3, 1), date(2026, 3, 31)),
          (date(2026, 4, 1), date(2026, 4, 30))]
N_ACCOUNTS = 2000


def iso(d):
    return d.isoformat()


def window_for(start, end, r):
    """Meter window relative to a period: open, late start, early end, or idle."""
    if r < 0.80:
        return start - timedelta(days=rng.randint(30, 900)), None
    if r < 0.92:
        return start + timedelta(days=rng.randint(1, (end - start).days)), None
    if r < 0.97:
        return start - timedelta(days=rng.randint(30, 400)), start + timedelta(days=rng.randint(0, (end - start).days - 1))
    return start - timedelta(days=rng.randint(200, 600)), start - timedelta(days=rng.randint(1, 60))


def quantity_text(q):
    return json.dumps(q)


def build_main():
    periods, meters, reads = [], [], []
    meter_no = 0
    for i in range(1, N_ACCOUNTS + 1):
        acc = "A%04d" % i
        start, end = rng.choice(MONTHS)
        plan = rng.choice(PLANS)
        periods.append([acc, start, end, plan, None])
        for _ in range(rng.choices([1, 2, 3], [45, 40, 15])[0]):
            meter_no += 1
            met = "M%05d" % meter_no
            frm, to = window_for(start, end, rng.random())
            meters.append([acc, met, frm, to])
            lo = max(frm, start)
            hi = end if to is None else min(to, end)
            if lo > hi:
                days = [start + timedelta(days=rng.randint(0, (end - start).days))]
            else:
                span = (hi - lo).days + 1
                days = sorted(rng.sample(range(span), min(span, rng.randint(2, 4))))
                days = [lo + timedelta(days=d) for d in days]
            scale = {"HOME-A": 120, "HOME-B": 110, "SME-1": 260, "SME-2": 230, "IND-1": 420, "IND-2": 700}[plan]
            for d in days:
                reads.append({"account": acc, "meter": met, "day": iso(d), "q": rng.randint(0, 2 * scale)})
    accounts_by_id = {p[0]: p for p in periods}
    meter_rows = {(m[0], m[1]): m for m in meters}
    extra = []
    for r in list(reads):
        p = accounts_by_id[r["account"]]
        x = rng.random()
        if x < 0.02:
            extra.append(dict(r, q=rng.randint(1, 300)))  # duplicate day
        elif x < 0.04:
            off = rng.randint(1, 20)
            day = p[1] - timedelta(days=off) if rng.random() < 0.5 else p[2] + timedelta(days=off)
            m = meter_rows[(r["account"], r["meter"])]
            if m[2] <= day and (m[3] is None or day <= m[3]):
                extra.append(dict(r, day=iso(day), q=rng.randint(1, 300)))
        elif x < 0.05:
            extra.append(dict(r, meter="M%05d" % rng.randint(meter_no + 1, meter_no + 900), q=rng.randint(1, 300)))
        elif x < 0.065:
            extra.append(dict(r, q=rng.choice(['"%d"', '" %d "', '"%d "']) % rng.randint(5, 300), raw=True))
        elif x < 0.075:
            extra.append(dict(r, q=rng.choice(["true", "false", "null"]), raw=True))
        elif x < 0.085:
            extra.append(dict(r, q=rng.choice(["%d.5", "%d.0", "%de1", "-%d"]) % rng.randint(1, 60), raw=True))
    reads.extend(extra)
    rng.shuffle(reads)
    ids = rng.sample(range(100000, 999999), len(reads))
    for r, n in zip(reads, ids):
        r["read_id"] = "R%06d" % n
        if rng.random() < 0.03:
            key = rng.choice(["account", "meter", "read_id"])
            r[key] = rng.choice([" %s", "%s ", "  %s "]) % r[key]
    return periods, meters, reads


def read_line(r):
    q = r["q"] if r.get("raw") else quantity_text(r["q"])
    return ('{"read_id": %s, "account": %s, "meter": %s, "day": %s, "quantity": %s}'
            % (json.dumps(r["read_id"]), json.dumps(r["account"]), json.dumps(r["meter"]), json.dumps(r["day"]), q))


def texts_of(periods, meters, reads, card=CARD):
    pb = io.StringIO()
    w = csv.writer(pb, lineterminator="\n")
    w.writerow(["account", "start", "end", "plan", "commitment"])
    for acc, s, e, plan, c in periods:
        w.writerow([acc, iso(s), iso(e), plan, c if c is not None else "0.00"])
    ab = io.StringIO()
    w = csv.writer(ab, lineterminator="\n")
    w.writerow(["account", "meter", "active_from", "active_to"])
    for acc, met, frm, to in meters:
        w.writerow([acc, met, iso(frm), iso(to) if to else ""])
    return {
        refengine.READS: "".join(read_line(r) + "\n" for r in reads),
        refengine.ACCOUNTS: ab.getvalue(),
        refengine.PERIODS: pb.getvalue(),
        refengine.CARD: json.dumps(card, indent=2) + "\n",
    }


def money(c):
    return refengine.fmt(c)


def shift_window(m, start, end):
    """Move a partial meter window by one day so its standing line is no tie."""
    if m[2] > start:
        m[2] = m[2] + timedelta(days=1)
    elif m[3] is not None and m[3] < end:
        m[3] = m[3] + timedelta(days=1)


def settle_commitments(periods, meters, reads):
    """Pick commitments from the exact subtotal; remove ties in lines and totals."""
    for p in periods:
        p[4] = "0.00"
    for _ in range(300):
        trace = []
        doc = refengine.evaluate(texts_of(periods, meters, reads), trace)
        bad = {(t[1], t[2]) for t in trace if t[0] == "energy" and refengine.is_tie(t[4])}
        bad_std = {(t[1], t[2]) for t in trace if t[0] == "standing" and refengine.is_tie(t[4])}
        bad_tot = {t[1] for t in trace if t[0] == "total" and refengine.is_tie(t[4])}
        if not bad and not bad_std and not bad_tot and all(p[4] != "0.00" for p in periods):
            return doc
        if bad or bad_std or bad_tot:
            print("ties", len(bad), len(bad_std), len(bad_tot), sorted(bad_std)[:3], sorted(bad_tot)[:3], file=sys.stderr)
            by_acc = {p[0]: p for p in periods}
            for m in meters:
                if (m[0], m[1]) in bad_std:
                    shift_window(m, by_acc[m[0]][1], by_acc[m[0]][2])
            for key in sorted(bad) + sorted((a, None) for a in bad_tot):
                pool = [r for r in reads if not r.get("raw") and r["account"].strip() == key[0]
                        and (key[1] is None or r["meter"].strip() == key[1])]
                if pool:
                    rng.choice(pool)["q"] += 1
            continue
        subs = {inv["account"]: Fraction(inv["subtotal"]) for inv in doc["invoices"]}
        for p in periods:
            sub = subs[p[0]]
            factor = Fraction(rng.choice([60, 75, 85, 95, 100, 105, 120, 140]), 100)
            cents = max(int(sub * factor * 100), 1000)
            if factor == 1:
                cents = int(sub * 100)
            p[4] = money(cents)
    raise SystemExit("tie screening did not converge")


def shipped_total(texts):
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in texts.items():
            Path(tmp, name).write_text(text, encoding="utf-8")
        doc = shipped_build(tmp)
    return {inv["account"]: "%.2f" % inv["total"] for inv in doc["invoices"]}


def build_cases():
    cases = []
    for i in range(1, 2001):
        start, end = rng.choice(MONTHS)
        plan = rng.choice(PLANS)
        acc = "C%04d" % i
        tiers = CARD["plans"][plan]["tiers"]
        mets = []
        reads = []
        for k in range(rng.choice([1, 1, 2])):
            met = "N%04d%d" % (i, k)
            frm, to = window_for(start, end, rng.random())
            mets.append({"meter": met, "active_from": iso(frm), "active_to": iso(to) if to else ""})
            lo = max(frm, start)
            hi = end if to is None else min(to, end)
            if lo > hi:
                continue
            span = (hi - lo).days + 1
            target = rng.choice([rng.randint(10, 900), tiers[0]["up_to"]])
            days = sorted(rng.sample(range(span), min(span, 3)))
            parts = [target // len(days)] * len(days)
            parts[0] += target - sum(parts)
            for d, q in zip(days, parts):
                reads.append({"read_id": "%s-%02d" % (acc, len(reads) + 1), "account": acc, "meter": met,
                              "day": iso(lo + timedelta(days=d)), "q": q})
            x = rng.random()
            if x < 0.25:
                reads.append({"read_id": "%s-%02d" % (acc, len(reads) + 1), "account": acc, "meter": met,
                              "day": iso(lo), "q": rng.choice(["2.5", "14.5", "40.0"]), "raw": True})
            elif x < 0.45:
                reads.append({"read_id": "%s-%02d" % (acc, len(reads) + 1), "account": acc, "meter": met,
                              "day": iso(end + timedelta(days=rng.randint(1, 9))), "q": rng.randint(20, 200)})
        cases.append({"acc": acc, "start": start, "end": end, "plan": plan, "meters": mets, "reads": reads,
                      "commit": None})
    return cases


def case_texts(c):
    periods = [[c["acc"], c["start"], c["end"], c["plan"], c["commit"] or "0.00"]]
    meters = [[c["acc"], m["meter"], date.fromisoformat(m["active_from"]),
               date.fromisoformat(m["active_to"]) if m["active_to"] else None] for m in c["meters"]]
    return texts_of(periods, meters, c["reads"])


def finish_cases(cases):
    out = []
    for c in cases:
        for _ in range(40):
            trace = []
            doc = refengine.evaluate(case_texts(c), trace)
            ties = [t for t in trace if refengine.is_tie(t[4])]
            if ties:
                for t in ties:
                    if t[0] == "standing":
                        for m in c["meters"]:
                            if m["meter"] == t[2]:
                                row = [c["acc"], m["meter"], date.fromisoformat(m["active_from"]),
                                       date.fromisoformat(m["active_to"]) if m["active_to"] else None]
                                shift_window(row, c["start"], c["end"])
                                m["active_from"], m["active_to"] = iso(row[2]), iso(row[3]) if row[3] else ""
                    else:
                        pool = [r for r in c["reads"] if not r.get("raw") and (t[2] is None or r["meter"] == t[2])]
                        if pool:
                            rng.choice(pool)["q"] += 1
                continue
            sub = Fraction(doc["invoices"][0]["subtotal"])
            if c["commit"] is None:
                c["commit"] = money(max(int(sub * Fraction(rng.choice([70, 90, 101, 110, 130]), 100) * 100), 500))
                continue
            break
        else:
            raise SystemExit("case tie screening did not converge")
        right = doc["invoices"][0]["total"]
        disputed = shipped_total(case_texts(c))[c["acc"]]
        claim = right
        if right != disputed and rng.random() < 0.4:
            claim = rng.choice([disputed, money(int(Fraction(right) * 100) + rng.choice([-150, -40, 25, 90]))])
        out.append({"c": c, "right": right, "disputed": disputed, "claim": claim})
    return out


def case_line(i, row):
    c = row["c"]
    reads = [json.loads(read_line(r)) for r in c["reads"]]
    return json.dumps({
        "name": "dispute_%04d" % i, "account": c["acc"],
        "period": {"start": iso(c["start"]), "end": iso(c["end"])}, "plan": c["plan"],
        "commitment": c["commit"], "meters": c["meters"], "reads": reads,
        "disputed_total": row["disputed"], "customer_claim": row["claim"]})


def failing_log(rows):
    head = "$ cd repo && PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v"
    lines, detail = [head], []
    for i, row in enumerate(rows, 1):
        name = "test_dispute_%04d" % i
        label = "%s (test_regressions.DisputeReplays.%s)" % (name, name)
        if rng.random() < 0.03:
            lines.append(label + " ... ERROR")
            detail += ["=" * 70, "ERROR: " + label, "-" * 70, "Traceback (most recent call last):",
                       '  File "tests/test_regressions.py", line 41, in replay',
                       "TimeoutError: replay exceeded 5.0 s", ""]
        elif row["disputed"] != row["claim"]:
            lines.append(label + " ... FAIL")
            detail += ["=" * 70, "FAIL: " + label, "-" * 70, "Traceback (most recent call last):",
                       '  File "tests/test_regressions.py", line 44, in replay',
                       "    self.assertEqual(invoice['total'], case['customer_claim'])",
                       "AssertionError: '%s' != '%s'" % (row["disputed"], row["claim"]), ""]
        else:
            lines.append(label + " ... ok")
    nfail = sum(1 for l in lines if l.endswith(" ... FAIL"))
    nerr = sum(1 for l in lines if l.endswith(" ... ERROR"))
    tail = ["-" * 70, "Ran %d tests in 412.336s" % len(rows), "", "FAILED (failures=%d, errors=%d)" % (nfail, nerr)]
    return "\n".join(lines + [""] + detail + tail) + "\n"


def lint_report():
    sizes = {"tariff": 6, "tariff.__main__": 14, "tariff.parser": 87, "tariff.core": 47, "tariff.report": 86}
    codes = [("C0116", "info", "Missing function or method docstring"),
             ("W0212", "warning", "Access to a protected member of a client class"),
             ("R1705", "info", "Unnecessary \"else\" after \"return\""),
             ("W0621", "warning", "Redefining name from outer scope"),
             ("E1136", "error", "Value is unsubscriptable"),
             ("E0602", "error", "Undefined variable"),
             ("W0611", "warning", "Unused import"),
             ("C0301", "info", "Line too long (104/100)")]
    issues = []
    for _ in range(380):
        mod = rng.choice(sorted(sizes))
        code, sev, msg = rng.choice(codes)
        issues.append({"module": mod, "line": rng.randint(1, sizes[mod]), "code": code, "severity": sev,
                       "message": msg})
    issues.sort(key=lambda x: (x["module"], x["line"], x["code"]))
    return json.dumps({"tool": "pylint 3.2", "issues": issues}, indent=2) + "\n"


def main():
    periods, meters, reads = build_main()
    doc = settle_commitments(periods, meters, reads)
    texts = texts_of(periods, meters, reads)
    for name, text in texts.items():
        (CI / name).write_text(text, encoding="utf-8")
    rows = finish_cases(build_cases())
    (CI / "regression_cases.jsonl").write_text("".join(case_line(i, r) + "\n" for i, r in enumerate(rows, 1)),
                                               encoding="utf-8")
    (CI / "failing_tests.log").write_text(failing_log(rows), encoding="utf-8")
    (CI / "lint_report.json").write_text(lint_report(), encoding="utf-8")
    (CI / "package_manifest.json").write_text(json.dumps({
        "package": "tariff", "version": "2.4.1", "requires_python": ">=3.12", "layout": "src",
        "stdlib_only": True, "public_api": ["VERSION", "build_invoices", "render"]}, indent=2) + "\n",
        encoding="utf-8")
    # report
    total = 0
    for p in sorted(CI.iterdir()):
        n = p.read_text(encoding="utf-8").count("\n")
        total += n
        flag = ""
        if p.suffix in (".csv", ".tsv", ".jsonl", ".txt", ".log") and n < 2000:
            flag = "  BELOW 2000"
        print("%-24s %7d lines%s" % (p.name, n, flag))
    print("TOTAL", total, "lines (A5 needs >= 20000)")
    reasons = {}
    for e in doc["exceptions"]:
        reasons[e["reason"]] = reasons.get(e["reason"], 0) + 1
    print("exceptions", reasons)
    credited = sum(1 for inv in doc["invoices"] if inv["credit"] != "0.00")
    print("invoices", len(doc["invoices"]), "credited", credited,
          "claims right", sum(1 for r in rows if r["claim"] == r["right"]),
          "disputed==right", sum(1 for r in rows if r["disputed"] == r["right"]))


if __name__ == "__main__":
    main()
