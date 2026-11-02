#!/usr/bin/env python3
"""Pilotage dues reconstruction: recover station conventions and tariffs, audit disputes."""
import argparse
import csv
import datetime as dt
import itertools
import json
import os
import re
import sys

STATIONS = ["North", "South", "West", "East"]
SEGMENTS = ["commercial", "public"]
VERDICTS = ["billed_correctly", "overbilled", "underbilled", "cannot_recompute"]
CODES = ["malformed_record", "duplicate_invoice", "unknown_visit", "station_mismatch"]
REASON = "more than one listed tariff reproduces every paid invoice"
REVIEW_START = dt.date(2026, 7, 1)
REVIEW_END = dt.date(2026, 9, 30)

P100 = [180, 195, 210, 225, 240]
PTEN = [250, 300, 350, 400]
FACT = [125, 140, 150]
PTUG = [3500, 5000, 6500]
TARIFFS = list(itertools.product(P100, PTEN, FACT, PTUG))

DATA_FILES = [
    "pilot_movements.log", "vessel_register.tsv", "agents.tsv", "stations.tsv",
    "certificates.json", "holidays.json", "station_notices.md", "paid_north.csv",
    "paid_south.jsonl", "paid_west.txt", "paid_east.xml", "disputed_batch.csv",
]
PAID_FILES = [("North", "paid_north.csv"), ("South", "paid_south.jsonl"),
              ("West", "paid_west.txt"), ("East", "paid_east.xml")]

AMOUNT_RE = re.compile(r"^[0-9]+\.[0-9]{2}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
XML_RE = re.compile(r'^\s*<invoice id="([^"]*)" visit="([^"]*)" date="([^"]*)" amount="([^"]*)"\s*/>\s*$')
LOG_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}) (\S+) (.*)$")


class Fatal(Exception):
    pass


def fatal(name):
    raise Fatal(name)


def read_text(data, name):
    path = os.path.join(data, name)
    if not os.path.isfile(path):
        fatal(name)
    try:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        fatal(name)


def split_lines(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [ln[:-1] if ln.endswith("\r") else ln for ln in lines]


def valid_date(s):
    if not isinstance(s, str) or not DATE_RE.match(s):
        return False
    try:
        dt.date.fromisoformat(s)
    except ValueError:
        return False
    return True


def valid_amount(s):
    return isinstance(s, str) and bool(AMOUNT_RE.match(s))


def cents(s):
    a, b = s.split(".")
    return int(a) * 100 + int(b)


def money(c):
    sign = "-" if c < 0 else ""
    c = abs(c)
    return "%s%d.%02d" % (sign, c // 100, c % 100)


def rhe(n, d):
    """Round n/d half to even (d > 0)."""
    q, r = divmod(n, d)
    if 2 * r > d or (2 * r == d and q % 2 == 1):
        q += 1
    return q


def hm(s):
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def in_hours(minute, start, end):
    if start == end:
        return False
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


def read_tsv(data, name, header):
    lines = split_lines(read_text(data, name))
    if not lines or lines[0].split("\t") != header:
        fatal(name)
    rows = []
    for ln in lines[1:]:
        if ln.strip() == "":
            continue
        parts = ln.split("\t")
        if len(parts) < len(header):
            parts += [""] * (len(header) - len(parts))
        rows.append(dict(zip(header, parts)))
    return rows


def read_json(data, name):
    text = read_text(data, name)
    try:
        obj = json.loads(text)
    except ValueError:
        fatal(name)
    if not isinstance(obj, dict):
        fatal(name)
    return obj


# ---------------------------------------------------------------- inputs

def load_reference(data):
    vessels = {}
    for r in read_tsv(data, "vessel_register.tsv",
                      ["vessel_id", "name", "gross_tonnage", "net_tonnage", "max_draft",
                       "flag", "agent", "segment", "certificate"]):
        vessels[r["vessel_id"].strip()] = r
    agents = {r["agent"].strip(): r for r in
              read_tsv(data, "agents.tsv", ["agent", "name", "office", "opens", "closes"])}
    stations = {r["station"].strip(): r for r in
                read_tsv(data, "stations.tsv", ["station", "watch_from", "watch_to", "opens", "closes"])}
    certs = read_json(data, "certificates.json")
    hol = read_json(data, "holidays.json")
    cal = hol.get("calendars", hol)
    if not isinstance(cal, dict):
        fatal("holidays.json")
    calendars = {}
    for k, v in cal.items():
        if isinstance(v, list):
            calendars[k] = set(str(x) for x in v)
    return vessels, agents, stations, certs, calendars


def load_notices(data):
    lines = split_lines(read_text(data, "station_notices.md"))
    notices = {}
    header_seen = False
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not header_seen:
            if [c.lower() for c in cells[:2]] == ["station", "notice_date"]:
                header_seen = True
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        if len(cells) >= 2 and cells[0] in STATIONS and valid_date(cells[1]):
            notices[cells[0]] = dt.date.fromisoformat(cells[1])
    if not header_seen:
        fatal("station_notices.md")
    return notices


def load_log(data):
    text = read_text(data, "pilot_movements.log")
    orders, boards, releases = {}, {}, {}
    for ln in split_lines(text):
        m = LOG_RE.match(ln.strip())
        if not m:
            continue
        date_s, hh, mm, kind, rest = m.groups()
        try:
            day = dt.date.fromisoformat(date_s)
        except ValueError:
            continue
        t = (day, int(hh) * 60 + int(mm))
        parts = rest.split()
        kv = {}
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                kv[k] = v
        try:
            if kind == "ORDER" and len(parts) >= 2:
                orders.setdefault(parts[1], (t, parts[0], kv.get("draft")))
            elif kind == "BOARD" and len(parts) >= 3:
                if parts[1] not in boards:
                    boards[parts[1]] = {
                        "time": t, "station": parts[0], "vessel": parts[2],
                        "draft": kv.get("draft"), "tugs": int(kv.get("tugs", "0")),
                        "assist": int(kv.get("assist", "0")),
                    }
            elif kind == "RELEASE" and len(parts) >= 1:
                releases.setdefault(parts[0], t)
        except ValueError:
            continue
    return orders, boards, releases


def parse_paid(data, station, name):
    """Return list of (line_no, fields-or-None)."""
    text = read_text(data, name)
    lines = split_lines(text)
    out = []
    if name.endswith(".csv"):
        if not lines or lines[0].strip() != "invoice_id,visit_id,invoice_date,amount":
            fatal(name)
        for i, ln in enumerate(lines[1:], start=2):
            row = next(csv.reader([ln]), [])
            if len(row) != 4:
                out.append((i, None))
                continue
            out.append((i, dict(zip(["invoice_id", "visit_id", "invoice_date", "amount"],
                                    [c.strip() for c in row]))))
    elif name.endswith(".jsonl"):
        for i, ln in enumerate(lines, start=1):
            try:
                obj = json.loads(ln)
            except ValueError:
                out.append((i, None))
                continue
            if not isinstance(obj, dict):
                out.append((i, None))
                continue
            rec = {}
            ok = True
            for k in ["invoice_id", "visit_id", "invoice_date", "amount"]:
                v = obj.get(k)
                if not isinstance(v, str):
                    ok = False
                    break
                rec[k] = v.strip()
            out.append((i, rec if ok else None))
    elif name.endswith(".txt"):
        for i, ln in enumerate(lines, start=1):
            if len(ln.rstrip()) > 40:
                out.append((i, None))
                continue
            rec = {"invoice_id": ln[0:10].strip(), "visit_id": ln[10:18].strip(),
                   "invoice_date": ln[18:28].strip(), "amount": ln[28:40].strip()}
            out.append((i, rec))
    else:
        if len(lines) < 2 or lines[0].strip() != '<paid_invoices station="%s">' % station \
                or lines[-1].strip() != "</paid_invoices>":
            fatal(name)
        for i, ln in enumerate(lines[1:-1], start=2):
            m = XML_RE.match(ln)
            if not m:
                out.append((i, None))
                continue
            out.append((i, dict(zip(["invoice_id", "visit_id", "invoice_date", "amount"],
                                    [g.strip() for g in m.groups()]))))
    return out


def parse_disputed(data):
    name = "disputed_batch.csv"
    lines = split_lines(read_text(data, name))
    if not lines or lines[0].strip() != "invoice_id,visit_id,station,invoice_date,billed":
        fatal(name)
    out = []
    for i, ln in enumerate(lines[1:], start=2):
        row = next(csv.reader([ln]), [])
        if len(row) != 5:
            out.append((i, None))
            continue
        out.append((i, dict(zip(["invoice_id", "visit_id", "station", "invoice_date", "billed"],
                                [c.strip() for c in row]))))
    return out


def well_formed(rec, amount_key):
    if rec is None:
        return False
    for v in rec.values():
        if v == "":
            return False
    return valid_date(rec["invoice_date"]) and valid_amount(rec[amount_key])


def classify(group, amount_key, station_of, visit_known, visit_station):
    """group: list of (file, line, rec, expected_station). Returns codes list (None=accepted)."""
    codes = []
    ids = {}
    for f, ln, rec, st in group:
        ok = well_formed(rec, amount_key)
        codes.append(None if ok else "malformed_record")
        if ok:
            ids[rec["invoice_id"]] = ids.get(rec["invoice_id"], 0) + 1
    for idx, (f, ln, rec, st) in enumerate(group):
        if codes[idx] is not None:
            continue
        if ids[rec["invoice_id"]] > 1:
            codes[idx] = "duplicate_invoice"
        elif not visit_known(rec["visit_id"]):
            codes[idx] = "unknown_visit"
        elif visit_station(rec["visit_id"]) != station_of(rec, st):
            codes[idx] = "station_mismatch"
    return codes


# ---------------------------------------------------------------- conventions

def tenths_over(draft_s):
    if draft_s is None:
        return None
    d = draft_s.strip()
    if not re.match(r"^[0-9]+(\.[0-9]+)?$", d):
        return None
    if "." in d:
        a, b = d.split(".")
    else:
        a, b = d, "0"
    # value in units of 1/10^len(b) metres; tenths rounded up
    scale = 10 ** len(b)
    val = int(a) * scale + int(b)
    num = val * 10
    t = -(-num // scale)
    return max(t - 60, 0)


def convention_space(extended):
    tonnage = ["gross", "net"]
    draft = ["measured", "declared", "max"]
    time = ["order", "board", "release"]
    hours = ["watch", "station_closed", "agent_closed"]
    cals = ["national", "region", "flag", "agent_city"]
    if extended:
        hours = hours + ["station_open", "agent_open", "none"]
        cals = cals + ["none"]
    return list(itertools.product(tonnage, draft, time, hours, cals))


class Visits:
    def __init__(self, orders, boards, releases, vessels, agents, stations, certs, calendars):
        self.o, self.b, self.r = orders, boards, releases
        self.vessels, self.agents, self.stations = vessels, agents, stations
        self.certs, self.cal = certs, calendars

    def known(self, vid):
        b = self.b.get(vid)
        return b is not None and b["vessel"] in self.vessels

    def station(self, vid):
        return self.b[vid]["station"]

    def instant(self, vid):
        return self.b[vid]["time"]

    def exempt(self, vid):
        b = self.b[vid]
        v = self.vessels[b["vessel"]]
        if v["segment"].strip() != "public":
            return False
        cid = v["certificate"].strip()
        if not cid:
            return False
        c = self.certs.get(cid)
        if not isinstance(c, dict) or str(c.get("holder", "")).strip() != b["vessel"]:
            return False
        exp = str(c.get("expiry", ""))
        if not valid_date(exp):
            return False
        return b["time"][0] < dt.date.fromisoformat(exp)

    def components(self, vid, conv):
        """Return (tonnage, excess_tenths, tugs, assist_blocks, surcharged) or None."""
        ton_c, draft_c, time_c, hours_c, cal_c = conv
        b = self.b[vid]
        v = self.vessels[b["vessel"]]
        try:
            ton = int(v["gross_tonnage" if ton_c == "gross" else "net_tonnage"].strip())
        except ValueError:
            return None
        if draft_c == "measured":
            ex = tenths_over(b["draft"])
        elif draft_c == "declared":
            o = self.o.get(vid)
            ex = tenths_over(o[2]) if o else None
        else:
            ex = tenths_over(v["max_draft"])
        if ex is None:
            return None
        if time_c == "board":
            t = b["time"]
        elif time_c == "order":
            o = self.o.get(vid)
            t = o[0] if o else None
        else:
            t = self.r.get(vid)
        if t is None:
            return None
        st = self.stations.get(b["station"])
        ag = self.agents.get(v["agent"].strip())
        try:
            if hours_c == "watch":
                inh = in_hours(t[1], hm(st["watch_from"]), hm(st["watch_to"]))
            elif hours_c == "station_closed":
                inh = in_hours(t[1], hm(st["closes"]), hm(st["opens"]))
            elif hours_c == "station_open":
                inh = in_hours(t[1], hm(st["opens"]), hm(st["closes"]))
            elif hours_c == "agent_closed":
                inh = in_hours(t[1], hm(ag["closes"]), hm(ag["opens"]))
            elif hours_c == "agent_open":
                inh = in_hours(t[1], hm(ag["opens"]), hm(ag["closes"]))
            else:
                inh = False
        except (TypeError, KeyError, ValueError):
            return None
        if cal_c == "national":
            cal = self.cal.get("national")
        elif cal_c == "region":
            cal = self.cal.get(b["station"].lower(), self.cal.get(b["station"]))
        elif cal_c == "flag":
            cal = self.cal.get(v["flag"].strip())
        elif cal_c == "agent_city":
            cal = self.cal.get(ag["office"].strip()) if ag else None
        else:
            cal = set()
        if cal is None:
            cal = set()
        hol = t[0].isoformat() in cal
        blocks = -(-b["assist"] // 30) if b["assist"] > 0 else 0
        return (ton, ex, b["tugs"], blocks, inh or hol)


def due(comp, tariff, exempt):
    if exempt:
        return 0
    ton, ex, tugs, blocks, sur = comp
    p100, pten, fact, ptug = tariff
    l1 = rhe(p100 * ton, 100)
    l2 = pten * ex
    l3 = ptug * tugs
    l4 = 4000 * blocks
    s = l1 + l2 + l3 + l4
    l5 = rhe((fact - 100) * s, 100) if sur else 0
    return s + l5


def period_of(vis, vid, starts):
    d = vis.instant(vid)[0]
    cur = starts[0]
    for s in starts:
        if s <= d:
            cur = s
    return cur


def solve_station(vis, paid, starts, extended):
    """paid: list of (vid, amount_cents). Returns list of (conv, {period: [tariffs]})."""
    by_period = {s: [] for s in starts}
    for vid, amt in paid:
        by_period[period_of(vis, vid, starts)].append((vid, amt, vis.exempt(vid)))
    found = []
    for conv in convention_space(extended):
        comps = {}
        ok = True
        result = {}
        for s in starts:
            items = []
            for vid, amt, ex in by_period[s]:
                c = comps.get(vid)
                if c is None:
                    c = vis.components(vid, conv)
                    comps[vid] = c
                if c is None:
                    ok = False
                    break
                items.append((c, amt, ex))
            if not ok:
                break
            good = [t for t in TARIFFS if all(due(c, t, ex) == amt for c, amt, ex in items)]
            if not good:
                ok = False
                break
            result[s] = good
        if ok:
            found.append((conv, result))
    return found


# ---------------------------------------------------------------- main

def tariff_obj(t):
    return {"per_100_tonnes": money(t[0]), "per_tenth": money(t[1]),
            "surcharge_factor": "%d.%02d" % (t[2] // 100, t[2] % 100), "per_tug": money(t[3])}


def run(data, out):
    for name in DATA_FILES:
        if not os.path.isfile(os.path.join(data, name)):
            fatal(name)
    vessels, agents, stations, certs, calendars = load_reference(data)
    notices = load_notices(data)
    orders, boards, releases = load_log(data)
    vis = Visits(orders, boards, releases, vessels, agents, stations, certs, calendars)

    # paid records
    paid_group = []
    for st, name in PAID_FILES:
        for ln, rec in parse_paid(data, st, name):
            paid_group.append((name, ln, rec, st))
    paid_codes = classify(paid_group, "amount", lambda rec, st: st, vis.known, vis.station)
    disp_raw = parse_disputed(data)
    disp_group = [("disputed_batch.csv", ln, rec, None) for ln, rec in disp_raw]
    disp_codes = classify(disp_group, "billed", lambda rec, st: rec["station"], vis.known, vis.station)

    rejected = []
    for g, codes in ((paid_group, paid_codes), (disp_group, disp_codes)):
        for (f, ln, rec, st), c in zip(g, codes):
            if c is not None:
                rejected.append({"file": f, "line": ln, "code": c})
    rejected.sort(key=lambda r: (r["file"], r["line"]))
    counts = {c: sum(1 for r in rejected if r["code"] == c) for c in CODES}

    # periods
    starts = {}
    for st in STATIONS:
        s = [REVIEW_START]
        n = notices.get(st)
        if n is not None and REVIEW_START < n <= REVIEW_END:
            s.append(n)
        starts[st] = s

    paid_by_station = {st: [] for st in STATIONS}
    for (f, ln, rec, st), c in zip(paid_group, paid_codes):
        if c is None:
            paid_by_station[st].append((rec["visit_id"], cents(rec["amount"])))

    station_info = {}
    for st in STATIONS:
        found = solve_station(vis, paid_by_station[st], starts[st], False)
        if len(found) != 1:
            ext = solve_station(vis, paid_by_station[st], starts[st], True)
            if len(ext) == 1 or (not found and ext):
                found = ext
        conv, tariffs = None, {s: [] for s in starts[st]}
        if found:
            conv, tariffs = found[0]
        periods = {}
        for s in starts[st]:
            good = tariffs.get(s, [])
            periods[s] = good[0] if len(good) == 1 else None
        station_info[st] = (conv, periods)

    # disputed
    rows = []
    for (f, ln, rec, st), c in zip(disp_group, disp_codes):
        if c is not None:
            continue
        vid = rec["visit_id"]
        vst = vis.station(vid)
        conv, periods = station_info[vst]
        ps = period_of(vis, vid, starts[vst])
        tariff = periods[ps]
        vessel = vis.b[vid]["vessel"]
        seg = vessels[vessel]["segment"].strip()
        billed = cents(rec["billed"])
        recomputed = None
        if tariff is not None and conv is not None:
            comp = vis.components(vid, conv)
            if comp is not None:
                recomputed = due(comp, tariff, vis.exempt(vid))
        if recomputed is None:
            verdict = "cannot_recompute"
        elif billed == recomputed:
            verdict = "billed_correctly"
        elif billed > recomputed:
            verdict = "overbilled"
        else:
            verdict = "underbilled"
        rows.append({
            "invoice_id": rec["invoice_id"], "visit_id": vid, "station": vst,
            "period_start": ps.isoformat(), "segment": seg, "vessel": vessel,
            "billed_c": billed, "recomputed_c": recomputed, "verdict": verdict,
        })
    rows.sort(key=lambda r: r["invoice_id"])

    def agg(sel):
        vc = {v: 0 for v in VERDICTS}
        billed = recomputed = refund = short = 0
        for r in sel:
            vc[r["verdict"]] += 1
            billed += r["billed_c"]
            if r["recomputed_c"] is not None:
                recomputed += r["recomputed_c"]
                d = r["billed_c"] - r["recomputed_c"]
                if d > 0:
                    refund += d
                elif d < 0:
                    short += -d
        return vc, billed, recomputed, refund, short

    docs = {}
    vc, b, rc, rf, sh = agg(rows)
    unresolved = []
    for st in STATIONS:
        for s in starts[st]:
            if station_info[st][1][s] is None:
                unresolved.append({"station": st, "period_start": s.isoformat()})
    refunds = [(r["billed_c"] - r["recomputed_c"], r["invoice_id"]) for r in rows
               if r["recomputed_c"] is not None and r["billed_c"] > r["recomputed_c"]]
    largest = None
    if refunds:
        top = max(a for a, _ in refunds)
        iid = min(i for a, i in refunds if a == top)
        largest = {"invoice_id": iid, "amount": money(top)}
    docs["summary.json"] = {
        "disputes": len(rows), "verdict_counts": vc, "billed_total": money(b),
        "recomputed_total": money(rc), "refund_total": money(rf), "shortfall_total": money(sh),
        "unresolved": unresolved, "largest_refund": largest,
    }
    audit = []
    for r in rows:
        rec_c = r["recomputed_c"]
        audit.append({
            "invoice_id": r["invoice_id"], "visit_id": r["visit_id"], "station": r["station"],
            "period_start": r["period_start"], "segment": r["segment"],
            "billed": money(r["billed_c"]),
            "recomputed": None if rec_c is None else money(rec_c),
            "difference": None if rec_c is None else money(r["billed_c"] - rec_c),
            "verdict": r["verdict"],
            "reason": REASON if r["verdict"] == "cannot_recompute" else None,
        })
    docs["policy_audit.json"] = {"rows": audit}
    docs["data_quality.json"] = {"rejected": rejected, "counts": counts}

    for st in STATIONS:
        conv, periods = station_info[st]
        plist = []
        for s in starts[st]:
            n = sum(1 for vid, _ in paid_by_station[st] if period_of(vis, vid, starts[st]) == s)
            t = periods[s]
            plist.append({"period_start": s.isoformat(),
                          "tariff": None if t is None else tariff_obj(t),
                          "reason": REASON if t is None else None,
                          "paid_invoices": n})
        sel = [r for r in rows if r["station"] == st]
        vc, b, rc, rf, sh = agg(sel)
        docs["region_%s.json" % st] = {
            "station": st, "periods": plist, "disputes": len(sel), "verdict_counts": vc,
            "refund_total": money(rf), "shortfall_total": money(sh),
        }
    for seg in SEGMENTS:
        sel = [r for r in rows if r["segment"] == seg]
        vc, b, rc, rf, sh = agg(sel)
        docs["segment_%s.json" % seg] = {
            "segment": seg, "disputes": len(sel), "vessels": len({r["vessel"] for r in sel}),
            "verdict_counts": vc, "billed_total": money(b), "recomputed_total": money(rc),
            "refund_total": money(rf), "shortfall_total": money(sh),
        }

    os.makedirs(out, exist_ok=True)
    for name, obj in docs.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
            fh.write("\n")
    for st in STATIONS:
        conv = station_info[st][0]
        sys.stderr.write("convention %s: %s\n" % (st, ",".join(conv) if conv else "none"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/app/data")
    ap.add_argument("--out", default="/app/out")
    a = ap.parse_args()
    try:
        run(a.data, a.out)
    except Fatal as e:
        sys.stderr.write("ERROR unreadable input: %s\n" % e.args[0])
        sys.exit(2)


if __name__ == "__main__":
    main()
