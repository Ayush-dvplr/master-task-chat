#!/usr/bin/env python3
"""Prototype reference for pilotage-dues-reconstruction (design stage only).

--reflex takes a comma list of wrong readings to inject:
  fit       first fitting combination in list order (H8)
  pinv      period by invoice_date
  pstrict   notice period starts the day after the notice date
  prel      period and surcharge by release instant
  exall     public visit wholly exempt when boarded before the expiry midnight, else full
  exincl    certificate covers the expiry date itself
  exonce    pro-rate the summed due once instead of each line
--fire FILE writes branch counters (json).
"""
import argparse
import itertools
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

STATIONS = ["North", "South", "West", "East"]
SEGMENTS = ["commercial", "public"]
VERDICTS = ["billed_correctly", "overbilled", "underbilled", "cannot_recompute"]
CODES = ["malformed_record", "duplicate_invoice", "unknown_visit", "station_mismatch"]
LISTS = {"base_per_100gt": [180, 195, 210, 225, 240], "draft_per_dm": [250, 300, 350, 400],
         "night_factor": [125, 140, 150], "per_tug": [3500, 5000, 6500]}
COMBOS = list(itertools.product(*LISTS.values()))
NOFIT = "no listed tariff reproduces every paid invoice"
MULTI = "more than one listed tariff reproduces every paid invoice"
FILES = ["pilot_movements.log", "vessel_register.tsv", "holidays.json", "station_notices.md",
         "paid_north.csv", "paid_south.jsonl", "paid_west.txt", "paid_east.xml", "disputed_batch.csv"]
AMT = re.compile(r"^\d+\.\d{2}$")
TS = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})"
BOARD = re.compile(TS + r" BOARD (North|South|West|East) (\S+) (\S+) draft_dm=(\d+) tugs=(\d+)$")
RELEASE = re.compile(TS + r" RELEASE (\S+)$")
NOTE = re.compile(TS + r" NOTE ")
XML = re.compile(r'^<invoice id="([^"\s]+)" visit="([^"\s]+)" date="([^"]+)" amount="([^"]+)"/>$')


class Fatal(Exception):
    pass


def rhe(num, den):
    q, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and q % 2):
        q += 1
    return q


def money(c):
    return ("-" if c < 0 else "") + f"{abs(c) // 100}.{abs(c) % 100:02d}"


def cents(s):
    return int(s.replace(".", ""))


def pdate(s):
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return None
        return date.fromisoformat(s)
    except ValueError:
        return None


def pts(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def read_lines(path, name):
    if not os.path.isfile(path):
        raise Fatal(name)
    with open(path, encoding="utf-8") as fh:
        return fh.read().split("\n")[:-1]


class Solver:
    def __init__(self, data, reflex):
        self.data = data
        self.rx = reflex
        self.rejected = []
        self.fire = {}

    def bump(self, k, n=1):
        self.fire[k] = self.fire.get(k, 0) + n

    def lines(self, name):
        return read_lines(os.path.join(self.data, name), name)

    def load(self):
        for f in FILES:
            if not os.path.isfile(os.path.join(self.data, f)):
                raise Fatal(f)
        # holidays
        try:
            with open(os.path.join(self.data, "holidays.json"), encoding="utf-8") as fh:
                hol = json.load(fh)
        except ValueError:
            raise Fatal("holidays.json")
        if not isinstance(hol, dict):
            raise Fatal("holidays.json")
        self.hol = {s: set(hol.get(s, [])) for s in STATIONS}
        # notices
        self.notice = {}
        for ln in self.lines("station_notices.md"):
            m = re.fullmatch(r"\|\s*(North|South|West|East)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|", ln.strip())
            if m:
                self.notice[m.group(1)] = date.fromisoformat(m.group(2))
        # log
        boards, releases = {}, {}
        for i, ln in enumerate(self.lines("pilot_movements.log"), 1):
            if not ln or (NOTE.match(ln) and pts(ln[:16])):
                continue
            m = BOARD.fullmatch(ln)
            if m and pts(m.group(1)):
                boards[m.group(3)] = (pts(m.group(1)), m.group(2), m.group(4), int(m.group(5)), int(m.group(6)))
                continue
            m = RELEASE.fullmatch(ln)
            if m and pts(m.group(1)):
                releases[m.group(2)] = pts(m.group(1))
                continue
            self.reject("pilot_movements.log", i)
        # register
        reg = self.lines("vessel_register.tsv")
        if not reg or reg[0] != "vessel_id\tname\tgross_tonnage\tsegment\texemption_expiry":
            raise Fatal("vessel_register.tsv")
        self.vessels = {}
        for i, ln in enumerate(reg[1:], 2):
            if not ln:
                continue
            f = ln.split("\t")
            ok = len(f) == 5 and f[2].isdigit() and (
                (f[3] == "commercial" and f[4] == "-") or (f[3] == "public" and pdate(f[4])))
            if not ok:
                self.reject("vessel_register.tsv", i)
                continue
            self.vessels[f[0]] = (int(f[2]), f[3], pdate(f[4]) if f[3] == "public" else None)
        self.visits = {}
        for vid, (b, st, ves, dr, tg) in boards.items():
            if vid in releases and ves in self.vessels:
                self.visits[vid] = {"id": vid, "board": b, "release": releases[vid], "station": st,
                                    "vessel": ves, "draft": dr, "tugs": tg}
        # paid
        paid = []
        north = self.lines("paid_north.csv")
        if not north or north[0] != "invoice_id,visit_id,invoice_date,amount":
            raise Fatal("paid_north.csv")
        for i, ln in enumerate(north[1:], 2):
            if ln:
                f = ln.split(",")
                paid.append(("paid_north.csv", i, "North", f if len(f) == 4 else None))
        for i, ln in enumerate(self.lines("paid_south.jsonl"), 1):
            if not ln:
                continue
            try:
                o = json.loads(ln)
                ok = isinstance(o, dict) and sorted(o) == sorted(["invoice_id", "visit_id", "invoice_date", "amount"]) \
                    and all(isinstance(x, str) for x in o.values())
                f = [o["invoice_id"], o["visit_id"], o["invoice_date"], o["amount"]] if ok else None
            except ValueError:
                f = None
            paid.append(("paid_south.jsonl", i, "South", f))
        for i, ln in enumerate(self.lines("paid_west.txt"), 1):
            if not ln:
                continue
            f = None
            if len(ln) == 40:
                f = [ln[0:10].rstrip(), ln[10:18].rstrip(), ln[18:28].rstrip(), ln[28:40].lstrip()]
                if any((not x) or " " in x for x in f):
                    f = None
            paid.append(("paid_west.txt", i, "West", f))
        east = self.lines("paid_east.xml")
        if len(east) < 2 or east[0] != '<paid_invoices station="East">' or east[-1] != "</paid_invoices>":
            raise Fatal("paid_east.xml")
        for i, ln in enumerate(east[1:-1], 2):
            if ln:
                m = XML.fullmatch(ln)
                paid.append(("paid_east.xml", i, "East", list(m.groups()) if m else None))
        disp_lines = self.lines("disputed_batch.csv")
        if not disp_lines or disp_lines[0] != "invoice_id,visit_id,station,invoice_date,billed":
            raise Fatal("disputed_batch.csv")
        disp = []
        for i, ln in enumerate(disp_lines[1:], 2):
            if ln:
                f = ln.split(",")
                ok = len(f) == 5 and f[2] in STATIONS
                disp.append(("disputed_batch.csv", i, f[2] if ok else None, [f[0], f[1], f[3], f[4]] if ok else None))
        self.paid = self.screen(paid, file_station=True)
        self.disp = self.screen(disp, file_station=False)

    def reject(self, f, i, code="malformed_record"):
        self.rejected.append({"file": f, "line": i, "code": code})

    def screen(self, recs, file_station):
        good = []
        for f, i, st, fl in recs:
            if fl is None or not fl[0] or not fl[1] or not pdate(fl[2]) or not AMT.match(fl[3]):
                self.reject(f, i)
                continue
            good.append((f, i, st, fl))
        cnt = {}
        for g in good:
            cnt[g[3][0]] = cnt.get(g[3][0], 0) + 1
        out = []
        for f, i, st, fl in good:
            if cnt[fl[0]] > 1:
                self.reject(f, i, "duplicate_invoice")
            elif fl[1] not in self.visits:
                self.reject(f, i, "unknown_visit")
            elif self.visits[fl[1]]["station"] != st:
                self.reject(f, i, "station_mismatch")
            else:
                out.append({"id": fl[0], "visit": self.visits[fl[1]], "date": pdate(fl[2]),
                            "amount": cents(fl[3]), "station": st})
        return out

    # ---------- rules
    def instant(self, inv):
        v = inv["visit"]
        if "prel" in self.rx:
            return v["release"]
        return v["board"]

    def period(self, inv):
        st = inv["station"]
        d = self.notice.get(st)
        if d is None:
            return date(2026, 7, 1)
        if "pinv" in self.rx:
            return d if inv["date"] >= d else date(2026, 7, 1)
        t = self.instant(inv)
        if "pstrict" in self.rx:
            return d if t.date() > d else date(2026, 7, 1)
        return d if t >= datetime(d.year, d.month, d.day) else date(2026, 7, 1)

    def night(self, inv):
        t = self.instant(inv)
        return t.hour >= 22 or t.hour < 6 or t.date().isoformat() in self.hol[inv["station"]]

    def minutes(self, v):
        onboard = int((v["release"] - v["board"]).total_seconds() // 60)
        gt, seg, exp = self.vessels[v["vessel"]]
        if seg == "commercial":
            return onboard, onboard
        cut = datetime(exp.year, exp.month, exp.day)
        if "exincl" in self.rx:
            cut += timedelta(days=1)
        if "exall" in self.rx:
            return onboard, (0 if v["board"] < cut else onboard)
        if v["release"] <= cut:
            return onboard, 0
        return onboard, int((v["release"] - max(v["board"], cut)).total_seconds() // 60)

    def due(self, inv, combo):
        v = inv["visit"]
        b, d, n, t = combo
        gt = self.vessels[v["vessel"]][0]
        l1 = rhe(b * gt, 100)
        l2 = d * max(0, v["draft"] - 60)
        l3 = t * v["tugs"]
        l4 = rhe((n - 100) * (l1 + l2 + l3), 100) if self.night(inv) else 0
        onboard, billed = inv["min"]
        if billed == onboard:
            return l1 + l2 + l3 + l4
        if billed == 0:
            return 0
        if "exonce" in self.rx:
            return rhe((l1 + l2 + l3 + l4) * billed, onboard)
        return sum(rhe(x * billed, onboard) for x in (l1, l2, l3, l4))

    def run(self):
        self.load()
        for inv in self.paid + self.disp:
            inv["min"] = self.minutes(inv["visit"])
            inv["period"] = self.period(inv)
        groups = {}
        for s in STATIONS:
            groups[(s, date(2026, 7, 1))] = []
            if s in self.notice:
                groups[(s, self.notice[s])] = []
        for p in self.paid:
            groups.setdefault((p["station"], p["period"]), []).append(p)
        self.tariff = {}
        for key, ps in sorted(groups.items(), key=lambda kv: (STATIONS.index(kv[0][0]), kv[0][1])):
            fits = [c for c in COMBOS if all(self.due(p, c) == p["amount"] for p in ps)]
            self.bump(f"fits {key[0]} {key[1]}={len(fits)}")
            if "fit" in self.rx and fits:
                fits = fits[:1]
            self.tariff[key] = fits[0] if len(fits) == 1 else (NOFIT if not fits else MULTI)
        rows = []
        for inv in sorted(self.disp, key=lambda x: x["id"]):
            v = inv["visit"]
            t = self.tariff.get((inv["station"], inv["period"]))
            if t is None:
                t = NOFIT
            onboard, billed = inv["min"]
            self.fire_disp(inv, t)
            if isinstance(t, str):
                rec, diff, verdict, reason = None, None, "cannot_recompute", t
            else:
                rec = self.due(inv, t)
                diff = inv["amount"] - rec
                verdict = "billed_correctly" if diff == 0 else ("overbilled" if diff > 0 else "underbilled")
                reason = None
            rows.append({"invoice_id": inv["id"], "visit_id": v["id"], "station": inv["station"],
                         "period_start": inv["period"].isoformat(), "segment": self.vessels[v["vessel"]][1],
                         "billed": inv["amount"], "recomputed": rec, "difference": diff, "verdict": verdict,
                         "reason": reason, "onboard_minutes": onboard, "billed_minutes": billed})
        self.rows = rows

    def fire_disp(self, inv, t):
        v = inv["visit"]
        st = inv["station"]
        if t == MULTI:
            self.bump("LV-1 multi-fit disputed")
        if t == NOFIT:
            self.bump("LV-1 no-fit disputed")
        d = self.notice.get(st)
        if d is not None:
            d0 = datetime(d.year, d.month, d.day)
            if v["board"].date() == d:
                self.bump("LV-2 boarding on notice date")
            if v["board"] < d0 < v["release"]:
                self.bump("LV-2 eve boarding released after notice midnight")
            if v["board"] < d0 and inv["date"] >= d:
                self.bump("LV-2 boarded before, invoiced on/after notice")
        b = v["board"]
        nt, hd = b.hour >= 22 or b.hour < 6, b.date().isoformat() in self.hol[st]
        if nt or hd:
            self.bump("plain " + ("night+holiday" if nt and hd else "night" if nt else "holiday"))
        onboard, billed = inv["min"]
        if self.vessels[v["vessel"]][1] == "public":
            self.bump("plain public " + ("0 billed" if billed == 0 else "full" if billed == onboard else "partial"))
            exp = self.vessels[v["vessel"]][2]
            if 0 < billed < onboard:
                self.bump("LV-3 partial (across expiry midnight)")
            if v["board"].date() == exp:
                self.bump("LV-3 wholly on expiry date")
            if billed == 0 and v["release"].date() >= exp - timedelta(days=1):
                self.bump("LV-3 ends at or before expiry midnight (adjacent)")

    def write(self, out):
        os.makedirs(out, exist_ok=True)

        def agg(rs):
            vc = {k: 0 for k in VERDICTS}
            for r in rs:
                vc[r["verdict"]] += 1
            return {"disputes": len(rs), "verdict_counts": vc,
                    "billed_total": money(sum(r["billed"] for r in rs)),
                    "recomputed_total": money(sum(r["recomputed"] for r in rs if r["recomputed"] is not None)),
                    "refund_total": money(sum(r["difference"] for r in rs if r["verdict"] == "overbilled")),
                    "shortfall_total": money(-sum(r["difference"] for r in rs if r["verdict"] == "underbilled"))}

        def dump(name, obj):
            with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
                json.dump(obj, fh, indent=2)
                fh.write("\n")

        dump("summary.json", agg(self.rows))
        audit = []
        for r in self.rows:
            a = dict(r)
            for k in ("billed", "recomputed", "difference"):
                a[k] = None if a[k] is None else money(a[k])
            audit.append(a)
        dump("policy_audit.json", {"rows": audit})
        rej = sorted(self.rejected, key=lambda x: (x["file"], x["line"]))
        dump("data_quality.json", {"rejected": rej, "counts": {c: sum(1 for x in rej if x["code"] == c) for c in CODES}})
        for s in STATIONS:
            periods = []
            for (st, ps), t in sorted(self.tariff.items(), key=lambda kv: kv[0][1]):
                if st != s:
                    continue
                tar = None if isinstance(t, str) else {k: money(x) if k == "per_tug" else f"{x // 100}.{x % 100:02d}"
                                                      for k, x in zip(LISTS, t)}
                periods.append({"period_start": ps.isoformat(), "tariff": tar,
                                "reason": t if isinstance(t, str) else None,
                                "paid_invoices": sum(1 for p in self.paid if p["station"] == s and p["period"] == ps)})
            a = agg([r for r in self.rows if r["station"] == s])
            dump(f"region_{s}.json", {"station": s, "periods": periods, "disputes": a["disputes"],
                                      "verdict_counts": a["verdict_counts"], "refund_total": a["refund_total"],
                                      "shortfall_total": a["shortfall_total"]})
        for g in SEGMENTS:
            rs = [r for r in self.rows if r["segment"] == g]
            doc = {"segment": g}
            doc.update(agg(rs))
            doc["exempt_minutes"] = sum(r["onboard_minutes"] - r["billed_minutes"] for r in rs)
            dump(f"segment_{g}.json", doc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--reflex", default="")
    ap.add_argument("--fire")
    a = ap.parse_args()
    s = Solver(a.data, set(x for x in a.reflex.split(",") if x))
    try:
        s.run()
    except Fatal as e:
        sys.stderr.write(f"ERROR unreadable input: {e}\n")
        return 2
    s.write(a.out)
    if a.fire:
        with open(a.fire, "w") as fh:
            json.dump(s.fire, fh, indent=2, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
