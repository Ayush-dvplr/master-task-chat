#!/usr/bin/env python3
"""Reconstruct station pilotage tariffs from paid invoices and audit a disputed batch.

Usage: python3 derive_report.py --data <data dir> --out <output dir>
Standard library only.
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction
from itertools import product

STATIONS = ["North", "South", "West", "East"]
PAID_FILES = {
    "North": "paid_north.csv",
    "South": "paid_south.jsonl",
    "West": "paid_west.txt",
    "East": "paid_east.xml",
}
DATA_FILES = [
    "pilot_movements.log", "vessel_register.tsv", "certificates.json", "holidays.json",
    "station_notices.md", "paid_north.csv", "paid_south.jsonl", "paid_west.txt",
    "paid_east.xml", "disputed_batch.csv",
]
NORTH_HEADER = "invoice_id,visit_id,invoice_date,amount"
DISPUTED_HEADER = "invoice_id,visit_id,station,invoice_date,billed"
REGISTER_HEADER = "vessel_id\tname\tgross_tonnage\tsegment\tcertificate"
EAST_FIRST = '<paid_invoices station="East">'
EAST_LAST = "</paid_invoices>"

# listed values in cents (night factor in hundredths)
BASES = [180, 195, 210, 225, 240]
DRAFTS = [250, 300, 350, 400]
NIGHTS = [125, 140, 150]
TUGS = [3500, 5000, 6500]
TARIFFS = list(product(range(len(BASES)), range(len(DRAFTS)), range(len(NIGHTS)), range(len(TUGS))))
DRAFT_MARKS = range(1, 11)
ASSIST_MARKS = range(1, 31)
REVIEW_START = dt.date(2026, 7, 1)
UNRESOLVED_REASON = "more than one listed tariff reproduces every paid invoice"
VERDICTS = ["billed_correctly", "overbilled", "underbilled", "cannot_recompute"]
CODES = ["malformed_record", "duplicate_invoice", "unknown_visit", "station_mismatch"]
DAY = 1440

AMOUNT_RE = re.compile(r"^[0-9]+\.[0-9]{2}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
BOARD_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}) BOARD (\S+) (\S+) (\S+) draft=(\d+)\.(\d{2}) tugs=(\d+)(?: assist=(\d+))?\s*$"
)
NOTICE_RE = re.compile(r"^\|\s*([A-Za-z]+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*$")


class Fatal(Exception):
    pass


def money(cents):
    sign = "-" if cents < 0 else ""
    c = abs(cents)
    return f"{sign}{c // 100}.{c % 100:02d}"


def coef(v):
    return f"{v // 100}.{v % 100:02d}"


def rhe(frac):
    """Round a Fraction half to even to an int."""
    return round(frac)


def valid_date(s):
    if not isinstance(s, str) or not DATE_RE.match(s):
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def valid_amount(s):
    if not isinstance(s, str) or not AMOUNT_RE.match(s):
        return None
    whole, frac = s.split(".")
    return int(whole) * 100 + int(frac)


def read_text(data, name):
    path = os.path.join(data, name)
    try:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        raise Fatal(name)


def lines_of(text):
    return text.splitlines()


# ---------------------------------------------------------------- loading


def load_all(data):
    texts = {}
    for name in DATA_FILES:
        texts[name] = read_text(data, name)
    for name in ("certificates.json", "holidays.json"):
        try:
            texts[name] = json.loads(texts[name])
        except ValueError:
            raise Fatal(name)
    for name, header in (("vessel_register.tsv", REGISTER_HEADER),
                         ("paid_north.csv", NORTH_HEADER),
                         ("disputed_batch.csv", DISPUTED_HEADER)):
        ls = lines_of(texts[name])
        if not ls or ls[0] != header:
            raise Fatal(name)
    ls = lines_of(texts["paid_east.xml"])
    if len(ls) < 2 or ls[0] != EAST_FIRST or ls[-1] != EAST_LAST:
        raise Fatal("paid_east.xml")
    if not isinstance(texts["certificates.json"], dict):
        raise Fatal("certificates.json")
    hol = texts["holidays.json"]
    if not isinstance(hol, dict) or not isinstance(hol.get("calendars"), dict):
        raise Fatal("holidays.json")
    return texts


def parse_log(text):
    visits = {}
    for line in lines_of(text):
        m = BOARD_RE.match(line)
        if not m:
            continue
        d = valid_date(m.group(1))
        hh, mm = int(m.group(2)), int(m.group(3))
        if d is None or hh > 23 or mm > 59:
            continue
        vid = m.group(5)
        if vid in visits:
            continue
        visits[vid] = {
            "date": d,
            "minute": hh * 60 + mm,
            "station": m.group(4),
            "vessel": m.group(6),
            "draft_cm": int(m.group(7)) * 100 + int(m.group(8)),
            "tugs": int(m.group(9)),
            "assist": int(m.group(10)) if m.group(10) is not None else 0,
        }
    return visits


def parse_register(text):
    vessels = {}
    for line in lines_of(text)[1:]:
        parts = line.split("\t")
        if len(parts) != 5:
            continue
        vid, _name, gt, seg, cert = (p.strip() for p in parts)
        if not vid or not re.match(r"^[0-9]+$", gt):
            continue
        if vid not in vessels:
            vessels[vid] = {"gt": int(gt), "segment": seg, "certificate": cert}
    return vessels


def parse_notices(text):
    notices = {}
    for line in lines_of(text):
        m = NOTICE_RE.match(line.strip())
        if not m or m.group(1) not in STATIONS:
            continue
        d = valid_date(m.group(2))
        if d is None:
            continue
        notices.setdefault(m.group(1), d)
    return notices


def parse_calendars(hol):
    cals = {}
    for name, days in hol["calendars"].items():
        s = set()
        if isinstance(days, list):
            for x in days:
                d = valid_date(x)
                if d is not None:
                    s.add(d)
        cals[name] = s
    return cals


# ---------------------------------------------------------------- records


def paid_records(texts):
    """Yield (file, line_no, station, fields-or-None). fields = (inv, visit, date, amount)."""
    out = []
    # North CSV
    name = "paid_north.csv"
    for i, line in enumerate(lines_of(texts[name]), start=1):
        if i == 1:
            continue
        row = next(csv.reader([line]), [])
        if len(row) != 4:
            out.append((name, i, "North", None))
        else:
            out.append((name, i, "North", tuple(row)))
    # South JSONL
    name = "paid_south.jsonl"
    for i, line in enumerate(lines_of(texts[name]), start=1):
        fields = None
        try:
            obj = json.loads(line)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            vals = [obj.get(k) for k in ("invoice_id", "visit_id", "invoice_date", "amount")]
            if all(isinstance(v, str) for v in vals):
                fields = tuple(vals)
        out.append((name, i, "South", fields))
    # West fixed width
    name = "paid_west.txt"
    for i, line in enumerate(lines_of(texts[name]), start=1):
        fields = None
        if len(line) >= 29 and not line[40:].strip():
            fields = (line[0:10].rstrip(), line[10:18].rstrip(), line[18:28].rstrip(), line[28:40].strip())
            if line[0:10].startswith(" ") or line[10:18].startswith(" ") or line[18:28].startswith(" "):
                fields = None
        out.append((name, i, "West", fields))
    # East XML
    name = "paid_east.xml"
    ls = lines_of(texts[name])
    for i, line in enumerate(ls, start=1):
        if i == 1 or i == len(ls):
            continue
        fields = None
        try:
            el = ET.fromstring(line)
        except ET.ParseError:
            el = None
        if el is not None and el.tag == "invoice":
            vals = [el.get(k) for k in ("id", "visit", "date", "amount")]
            if all(v is not None for v in vals):
                fields = tuple(vals)
        out.append((name, i, "East", fields))
    return out


def disputed_records(text):
    out = []
    name = "disputed_batch.csv"
    for i, line in enumerate(lines_of(text), start=1):
        if i == 1:
            continue
        row = next(csv.reader([line]), [])
        out.append((name, i, row if len(row) == 5 else None))
    return out


def classify(records, visits, vessels):
    """records: list of dict with keys file,line,fields(inv,visit,date,amount,station_claim or None).
    Sets rec['code'] (None when accepted)."""
    for r in records:
        f = r["fields"]
        ok = f is not None and all(isinstance(x, str) and x != "" for x in f)
        if ok:
            r["inv"], r["visit"] = f[0], f[1]
            r["inv_date"] = valid_date(f[2])
            r["amount"] = valid_amount(f[3])
            ok = r["inv_date"] is not None and r["amount"] is not None
        r["code"] = None if ok else "malformed_record"
    counts = {}
    for r in records:
        if r["code"] is None:
            counts[r["inv"]] = counts.get(r["inv"], 0) + 1
    for r in records:
        if r["code"] is not None:
            continue
        if counts[r["inv"]] > 1:
            r["code"] = "duplicate_invoice"
            continue
        v = visits.get(r["visit"])
        if v is None or v["vessel"] not in vessels:
            r["code"] = "unknown_visit"
            continue
        if v["station"] != r["station"]:
            r["code"] = "station_mismatch"


# ---------------------------------------------------------------- dues


class VisitCalc:
    __slots__ = ("date", "minute", "ton", "whole", "left", "tugs", "assist", "exempt")

    def __init__(self, v, vessel, certs):
        self.date = v["date"]
        self.minute = v["minute"]
        gt = vessel["gt"]
        self.ton = [rhe(Fraction(b * gt, 100)) for b in BASES]
        self.whole = v["draft_cm"] // 10
        self.left = v["draft_cm"] % 10
        self.tugs = v["tugs"]
        self.assist = v["assist"]
        self.exempt = False
        if vessel["segment"] == "public" and vessel["certificate"]:
            c = certs.get(vessel["certificate"])
            if isinstance(c, dict) and c.get("holder") == v["vessel"]:
                exp = valid_date(c.get("expiry"))
                if exp is not None and v["date"] < exp:
                    self.exempt = True

    def excess(self, dmark):
        t = self.whole + (1 if self.left >= dmark else 0)
        return t - 60 if t > 60 else 0

    def assist_cents(self, amark):
        blocks, rem = divmod(self.assist, 30)
        return 4000 * blocks + (4000 if rem > 0 and rem >= amark else 0)


def lines_for(vc, tariff, dmark, amark, aib):
    b, d, n, t = tariff
    base = vc.ton[b] + DRAFTS[d] * vc.excess(dmark) + TUGS[t] * vc.tugs
    a = vc.assist_cents(amark)
    sbase = base + (a if aib else 0)
    sur = rhe(Fraction((NIGHTS[n] - 100) * sbase, 100))
    return base + a, sur


def in_window(minute, win):
    s, e = win
    if s < e:
        return s <= minute < e
    return minute >= s or minute < e


def holiday_set(cal, monday):
    s = set(cal)
    if monday:
        for d in cal:
            if d.weekday() == 6:
                s.add(d + dt.timedelta(days=1))
    return s


def due(vc, tariff, conv):
    if vc.exempt:
        return 0
    dmark, amark, aib, hset, win = conv
    plain, sur = lines_for(vc, tariff, dmark, amark, aib)
    if vc.date in hset or (win is not None and in_window(vc.minute, win)):
        return plain + sur
    return plain


def arc_options(ins, outs):
    """Return (starts, ends) ranges as lists, or None if no arc [s,e) holds every `ins`
    minute and no `outs` minute."""
    if ins & outs:
        return None
    if not ins:
        if len(outs) >= DAY:
            return None
        return ([], [])  # unconstrained: no surcharge-hour minute observed
    if not outs:
        lo = min(ins)
        return ([lo], [(max(ins) + 1) % DAY])
    so = sorted(outs)
    # find the gap holding the first in-minute
    ref = min(ins)
    prev = None
    for o in so:
        if o < ref:
            prev = o
    if prev is None:
        prev = so[-1]
    nxt = None
    for o in so:
        if o > prev:
            nxt = o
            break
    if nxt is None:
        nxt = so[0]
    length = (nxt - prev) % DAY or DAY
    offs = [(x - prev) % DAY for x in ins]
    if any(o <= 0 or o >= length for o in offs):
        return None
    first, last = min(offs), max(offs)
    starts = [(prev + k) % DAY for k in range(1, first + 1)]
    ends = [(prev + k) % DAY for k in range(last + 1, length + 1)]
    return (starts, ends)


# ---------------------------------------------------------------- recovery


def recover_station(invs, n_periods, cals):
    """invs: list of (VisitCalc, amount_cents, period_index).
    Returns conventions tuple (dmark, amark, aib, hset, win, calname, monday) or None."""
    by_period = [[] for _ in range(n_periods)]
    for vc, amt, p in invs:
        by_period[p].append((vc, amt))
    solutions = []
    cal_items = sorted(cals.items())
    for dmark in DRAFT_MARKS:
        for amark in ASSIST_MARKS:
            for aib in (False, True):
                per_period = []
                dead = False
                for items in by_period:
                    feas = []
                    for tariff in TARIFFS:
                        labels = []
                        good = True
                        for vc, amt in items:
                            if vc.exempt:
                                if amt != 0:
                                    good = False
                                    break
                                labels.append("E")
                                continue
                            plain, sur = lines_for(vc, tariff, dmark, amark, aib)
                            if amt == plain:
                                labels.append("E" if sur == 0 else "N")
                            elif amt == plain + sur:
                                labels.append("S")
                            else:
                                good = False
                                break
                        if good:
                            feas.append((tariff, labels))
                    if not feas:
                        dead = True
                        break
                    per_period.append(feas)
                if dead:
                    continue
                for calname, cal in cal_items:
                    for monday in (False, True):
                        hset = holiday_set(cal, monday)
                        options = []
                        for p, feas in enumerate(per_period):
                            items = by_period[p]
                            opts = set()
                            for _tariff, labels in feas:
                                ins, outs, ok = set(), set(), True
                                for (vc, _amt), lab in zip(items, labels):
                                    hol = vc.date in hset
                                    if lab == "N":
                                        if hol:
                                            ok = False
                                            break
                                        outs.add(vc.minute)
                                    elif lab == "S" and not hol:
                                        ins.add(vc.minute)
                                if ok:
                                    opts.add((frozenset(ins), frozenset(outs)))
                            if not opts:
                                break
                            options.append(opts)
                        else:
                            for combo in product(*options):
                                ins = frozenset().union(*[c[0] for c in combo])
                                outs = frozenset().union(*[c[1] for c in combo])
                                arc = arc_options(ins, outs)
                                if arc is not None:
                                    solutions.append((dmark, amark, aib, calname, monday, arc))
                                    break
    if not solutions:
        return None, 0
    dmark, amark, aib, calname, monday, (starts, ends) = solutions[0]
    if starts and ends:
        win = (starts[-1], ends[0])  # tightest arc around the observed surcharge minutes
        if win[0] == win[1]:
            win = (starts[0], ends[-1])
    else:
        win = None
    if len(solutions) > 1 or len(starts) > 1 or len(ends) > 1:
        print(f"warning: {len(solutions)} convention choices, window starts={len(starts)} ends={len(ends)}",
              file=sys.stderr)
    return (dmark, amark, aib, holiday_set(cals[calname], monday), win, calname, monday), len(solutions)


# ---------------------------------------------------------------- main


def run(data, out):
    texts = load_all(data)
    visits = parse_log(texts["pilot_movements.log"])
    vessels = parse_register(texts["vessel_register.tsv"])
    certs = texts["certificates.json"]
    cals = parse_calendars(texts["holidays.json"])
    notices = parse_notices(texts["station_notices.md"])

    periods = {}
    for s in STATIONS:
        ps = [REVIEW_START]
        if s in notices and notices[s] > REVIEW_START:
            ps.append(notices[s])
        periods[s] = ps

    def period_of(station, d):
        ps = periods[station]
        idx = 0
        for k, p in enumerate(ps):
            if d >= p:
                idx = k
        return idx

    paid = []
    for name, line, station, fields in paid_records(texts):
        paid.append({"file": name, "line": line, "station": station, "fields": fields})
    classify(paid, visits, vessels)

    disputed = []
    for name, line, row in disputed_records(texts["disputed_batch.csv"]):
        fields = None
        if row is not None:
            fields = (row[0], row[1], row[3], row[4], row[2])
        disputed.append({"file": name, "line": line, "station": row[2] if row else None,
                         "fields": fields})
    for r in disputed:
        if r["fields"] is not None and r["fields"][4] == "":
            r["fields"] = None
    classify(disputed, visits, vessels)

    calc_cache = {}

    def calc(vid):
        if vid not in calc_cache:
            v = visits[vid]
            calc_cache[vid] = VisitCalc(v, vessels[v["vessel"]], certs)
        return calc_cache[vid]

    # recover conventions and tariffs per station
    station_result = {}
    for s in STATIONS:
        invs = []
        counts = [0] * len(periods[s])
        for r in paid:
            if r["code"] is None and r["station"] == s:
                vc = calc(r["visit"])
                p = period_of(s, vc.date)
                counts[p] += 1
                invs.append((vc, r["amount"], p))
        conv, _n = recover_station(invs, len(periods[s]), cals)
        tariffs = []
        for p in range(len(periods[s])):
            if conv is None:
                tariffs.append(None)
                continue
            fits = []
            items = [(vc, amt) for vc, amt, q in invs if q == p]
            for tariff in TARIFFS:
                c5 = conv[:5]
                if all(due(vc, tariff, c5) == amt for vc, amt in items):
                    fits.append(tariff)
            tariffs.append(fits[0] if len(fits) == 1 else None)
        station_result[s] = {"conv": conv, "tariffs": tariffs, "counts": counts}

    # disputed verdicts
    rows = []
    for r in disputed:
        if r["code"] is not None:
            continue
        v = visits[r["visit"]]
        s = v["station"]
        vc = calc(r["visit"])
        p = period_of(s, vc.date)
        sr = station_result[s]
        tariff = sr["tariffs"][p]
        billed = r["amount"]
        row = {
            "invoice_id": r["inv"],
            "visit_id": r["visit"],
            "station": s,
            "period_start": periods[s][p].isoformat(),
            "segment": vessels[v["vessel"]]["segment"],
            "billed": billed,
            "vessel": v["vessel"],
        }
        if tariff is None:
            row.update(recomputed=None, difference=None, verdict="cannot_recompute",
                       reason=UNRESOLVED_REASON)
        else:
            rec = due(vc, tariff, sr["conv"][:5])
            diff = billed - rec
            verdict = "billed_correctly" if diff == 0 else ("overbilled" if diff > 0 else "underbilled")
            row.update(recomputed=rec, difference=diff, verdict=verdict, reason=None)
        rows.append(row)
    rows.sort(key=lambda x: x["invoice_id"])

    def totals(sel):
        vc = {k: 0 for k in VERDICTS}
        billed = recomputed = refund = shortfall = 0
        for x in sel:
            vc[x["verdict"]] += 1
            billed += x["billed"]
            if x["recomputed"] is not None:
                recomputed += x["recomputed"]
            if x["verdict"] == "overbilled":
                refund += x["difference"]
            elif x["verdict"] == "underbilled":
                shortfall += -x["difference"]
        return vc, billed, recomputed, refund, shortfall

    docs = {}
    vcounts, billed, recomputed, refund, shortfall = totals(rows)
    unresolved = []
    for s in STATIONS:
        for p, t in enumerate(station_result[s]["tariffs"]):
            if t is None:
                unresolved.append({"station": s, "period_start": periods[s][p].isoformat()})
    refunds = [x for x in rows if x["verdict"] == "overbilled"]
    largest = None
    if refunds:
        best = min(refunds, key=lambda x: (-x["difference"], x["invoice_id"]))
        largest = {"invoice_id": best["invoice_id"], "amount": money(best["difference"])}
    docs["summary.json"] = {
        "disputes": len(rows),
        "verdict_counts": vcounts,
        "billed_total": money(billed),
        "recomputed_total": money(recomputed),
        "refund_total": money(refund),
        "shortfall_total": money(shortfall),
        "unresolved": unresolved,
        "largest_refund": largest,
    }

    def m_or_none(c):
        return None if c is None else money(c)

    docs["policy_audit.json"] = {"rows": [{
        "invoice_id": x["invoice_id"], "visit_id": x["visit_id"], "station": x["station"],
        "period_start": x["period_start"], "segment": x["segment"], "billed": money(x["billed"]),
        "recomputed": m_or_none(x["recomputed"]), "difference": m_or_none(x["difference"]),
        "verdict": x["verdict"], "reason": x["reason"],
    } for x in rows]}

    rejected = [r for r in paid + disputed if r["code"] is not None]
    rejected.sort(key=lambda r: (r["file"], r["line"]))
    docs["data_quality.json"] = {
        "rejected": [{"file": r["file"], "line": r["line"], "code": r["code"]} for r in rejected],
        "counts": {c: sum(1 for r in rejected if r["code"] == c) for c in CODES},
    }

    for s in STATIONS:
        sr = station_result[s]
        plist = []
        for p, t in enumerate(sr["tariffs"]):
            plist.append({
                "period_start": periods[s][p].isoformat(),
                "tariff": None if t is None else {
                    "base_per_100gt": coef(BASES[t[0]]),
                    "draft_per_dm": coef(DRAFTS[t[1]]),
                    "night_factor": coef(NIGHTS[t[2]]),
                    "per_tug": coef(TUGS[t[3]]),
                },
                "reason": UNRESOLVED_REASON if t is None else None,
                "paid_invoices": sr["counts"][p],
            })
        sel = [x for x in rows if x["station"] == s]
        vcs, _b, _r, rf, sh = totals(sel)
        docs[f"region_{s}.json"] = {
            "station": s, "periods": plist, "disputes": len(sel), "verdict_counts": vcs,
            "refund_total": money(rf), "shortfall_total": money(sh),
        }

    for seg in ("commercial", "public"):
        sel = [x for x in rows if x["segment"] == seg]
        vcs, b, rc, rf, sh = totals(sel)
        docs[f"segment_{seg}.json"] = {
            "segment": seg, "disputes": len(sel), "vessels": len({x["vessel"] for x in sel}),
            "verdict_counts": vcs, "billed_total": money(b), "recomputed_total": money(rc),
            "refund_total": money(rf), "shortfall_total": money(sh),
        }

    os.makedirs(out, exist_ok=True)
    for name, doc in docs.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
            fh.write("\n")

    # conventions to stderr for the operator
    for s in STATIONS:
        conv = station_result[s]["conv"]
        if conv is None:
            print(f"{s}: no conventions found", file=sys.stderr)
        else:
            d, a, aib, _h, win, cal, mon = conv
            w = "none" if win is None else f"{win[0] // 60:02d}:{win[0] % 60:02d}-{win[1] // 60:02d}:{win[1] % 60:02d}"
            print(f"{s}: draft_mark={d} assist_mark={a} assist_in_base={aib} hours={w} "
                  f"calendar={cal} monday={mon}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    try:
        run(args.data, args.out)
    except Fatal as e:
        sys.stderr.write(f"ERROR unreadable input: {e.args[0]}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
