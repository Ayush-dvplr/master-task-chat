#!/usr/bin/env python3
"""Prototype reference v2 for pilotage-dues-reconstruction (design stage only).

--reflex takes a comma list of wrong readings to inject:
  indep     each period fitted alone (no joint space over unnamed coefficients)
  fit       first fitting combination instead of the uniqueness rule
  pinv      period by invoice_date
  pstrict   notice period starts the day after the notice date
  prel      period and surcharge by release instant
  exvessel  allowance per vessel instead of per certificate
  exinv     only invoiced visits draw on the allowance
  exorder   ties drawn in log line order
  excap     allowance cap ignored
  exincl    certificate covers the expiry date itself
  q1..q10   skip quiet rule Qn (see DESIGN.md section 12)
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
CODES = ["malformed_record", "duplicate_invoice", "unknown_visit", "station_mismatch",
         "early_invoice", "already_paid"]
COEF = ["base_per_100gt", "draft_per_dm", "night_factor", "per_tug"]
LISTS = {"base_per_100gt": [180, 195, 210, 225, 240], "draft_per_dm": [250, 300, 350, 400],
         "night_factor": [125, 140, 150], "per_tug": [3500, 5000, 6500]}
COMBOS = list(itertools.product(*LISTS.values()))
NOFIT = "no listed tariff reproduces every paid invoice"
MULTI = "more than one listed tariff reproduces every paid invoice"
FILES = ["pilot_movements.log", "vessel_register.tsv", "certificates.json", "holidays.json",
         "station_notices.md", "paid_north.csv", "paid_south.jsonl", "paid_west.txt", "paid_east.xml",
         "disputed_batch.csv"]
D0 = date(2026, 7, 1)
AMT = re.compile(r"^\d+\.\d{2}$")
TS = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})"
ST = r"(North|South|West|East)"
BOARD = re.compile(TS + r" BOARD " + ST + r" (\S+) (\S+) (draft_dm=\d+|draft_m=\d+\.\d{2}) tugs=(\d+)( assist=\d+)?$")
RELEASE = re.compile(TS + r" RELEASE (\S+)$")
CANCEL = re.compile(TS + r" CANCEL " + ST + r" (\S+) (\S+)$")
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


def pdate(s):
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def pts(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def midnight(d):
    return datetime(d.year, d.month, d.day)


class Solver:
    def __init__(self, data, reflex):
        self.data = data
        self.rx = reflex
        self.rejected = []
        self.fire = {}

    def bump(self, k, n=1):
        self.fire[k] = self.fire.get(k, 0) + n

    def lines(self, name):
        with open(os.path.join(self.data, name), encoding="utf-8") as fh:
            return fh.read().split("\n")[:-1]

    def jobj(self, name):
        try:
            with open(os.path.join(self.data, name), encoding="utf-8") as fh:
                o = json.load(fh)
        except ValueError:
            raise Fatal(name)
        if not isinstance(o, dict):
            raise Fatal(name)
        return o

    def reject(self, f, i, code="malformed_record", inv=None):
        self.rejected.append({"file": f, "line": i, "code": code, "_id": inv})

    # ---------------------------------------------------------------- load
    def load(self):
        for f in FILES:
            if not os.path.isfile(os.path.join(self.data, f)):
                raise Fatal(f)
        hol = self.jobj("holidays.json")
        self.certs = self.jobj("certificates.json")
        self.hol = {}
        for s in STATIONS:
            days = set(hol.get(s, []))
            if "q10" not in self.rx:
                days |= set(hol.get("all", []))
            if "q3" not in self.rx:
                for d in list(days):
                    pd = pdate(d)
                    if pd and pd.weekday() == 6:
                        days.add((pd + timedelta(days=1)).isoformat())
            self.hol[s] = days
        self.hol_all = set(hol.get("all", []))
        self.notice, self.named, self.fee, self.minimum = {}, {}, {}, {}
        for ln in self.lines("station_notices.md"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) != 3 or cells[0] not in STATIONS:
                continue
            if pdate(cells[1]):
                self.notice[cells[0]] = pdate(cells[1])
                self.named[cells[0]] = {c.strip() for c in cells[2].split(",")}
            elif AMT.match(cells[1]) and AMT.match(cells[2]):
                self.fee[cells[0]] = int(cells[1].replace(".", ""))
                self.minimum[cells[0]] = int(cells[2].replace(".", ""))
        # log
        boards, releases, cancels = {}, {}, {}
        for i, ln in enumerate(self.lines("pilot_movements.log"), 1):
            if not ln or (NOTE.match(ln) and pts(ln[:16])):
                continue
            m = BOARD.fullmatch(ln)
            if m and pts(m.group(1)) and not ("q1" in self.rx and m.group(7)) \
                    and not ("q2" in self.rx and m.group(5).startswith("draft_m")):
                dr = m.group(5)
                if dr.startswith("draft_dm="):
                    dm = int(dr[9:])
                else:
                    cm = int(dr[8:].replace(".", ""))
                    dm = -(-cm // 10)
                    self.bump("Q2 draft_m board")
                assist = int(m.group(7)[8:]) if m.group(7) else 0
                boards[m.group(3)] = {"board": pts(m.group(1)), "station": m.group(2), "vessel": m.group(4),
                                      "draft": dm, "tugs": int(m.group(6)), "assist": assist, "line": i}
                continue
            m = RELEASE.fullmatch(ln)
            if m and pts(m.group(1)):
                releases[m.group(2)] = pts(m.group(1))
                continue
            m = CANCEL.fullmatch(ln)
            if m and pts(m.group(1)) and "q4" not in self.rx:
                cancels[m.group(3)] = {"board": pts(m.group(1)), "station": m.group(2), "vessel": m.group(4),
                                       "line": i}
                continue
            self.reject("pilot_movements.log", i)
        # register
        reg = self.lines("vessel_register.tsv")
        if not reg or reg[0] != "vessel_id\tname\tgross_tonnage\tsegment\tcertificate\tmeasured_from":
            raise Fatal("vessel_register.tsv")
        self.rows = {}
        for i, ln in enumerate(reg[1:], 2):
            if not ln:
                continue
            f = ln.split("\t")
            ok = len(f) == 6 and f[2].isdigit() and (f[5] == "-" or pdate(f[5])) and (
                (f[3] == "commercial" and f[4] == "-") or (f[3] == "public" and f[4] != ""))
            if ok and "q7" in self.rx and f[3] == "public" and f[4] == "-":
                ok = False
            if not ok:
                self.reject("vessel_register.tsv", i)
                continue
            self.rows.setdefault(f[0], []).append(
                {"gt": int(f[2]), "seg": f[3], "cert": f[4], "mfrom": pdate(f[5]) if f[5] != "-" else None})
        self.visits = {}
        for vid, b in boards.items():
            if vid in releases and b["vessel"] in self.rows:
                self.visits[vid] = dict(b, id=vid, release=releases[vid], cancel=False)
        for vid, c in cancels.items():
            if c["vessel"] in self.rows and vid not in self.visits:
                self.visits[vid] = dict(c, id=vid, release=c["board"], draft=0, tugs=0, assist=0, cancel=True)
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
        dl = self.lines("disputed_batch.csv")
        if not dl or dl[0] != "invoice_id,visit_id,station,invoice_date,billed,supersedes":
            raise Fatal("disputed_batch.csv")
        disp = []
        for i, ln in enumerate(dl[1:], 2):
            if not ln:
                continue
            f = ln.split(",")
            ok = len(f) == 6 and f[2] in STATIONS
            if ok and re.fullmatch(r"\d+c", f[4]) and "q9" not in self.rx:
                f[4] = money(int(f[4][:-1]))
                self.bump("Q9 cents billed")
            disp.append(("disputed_batch.csv", i, f[2] if ok else None,
                         [f[0], f[1], f[3], f[4], f[5]] if ok else None))
        self.paid = self.screen(paid)
        paid_visits = {p["visit"]["id"] for p in self.paid}
        self.disp = self.screen(disp, paid_visits)
        # superseded
        sup = {d["sup"] for d in self.disp if d["sup"]}
        if "q8" in self.rx:
            sup = set()
        self.bump("Q8 superseded", sum(1 for d in self.disp if d["id"] in sup))
        self.disp = [d for d in self.disp if d["id"] not in sup]
        self.rejected = [r for r in self.rejected if not (r["file"] == "disputed_batch.csv" and r["_id"] in sup)]

    def screen(self, recs, paid_visits=None):
        good = []
        for f, i, st, fl in recs:
            if fl is None or not fl[0] or not fl[1] or not pdate(fl[2]) or not AMT.match(fl[3]):
                self.reject(f, i, inv=fl[0] if fl else None)
                continue
            good.append((f, i, st, fl))
        cnt = {}
        for g in good:
            cnt[g[3][0]] = cnt.get(g[3][0], 0) + 1
        out = []
        for f, i, st, fl in good:
            v = self.visits.get(fl[1])
            code = None
            if cnt[fl[0]] > 1:
                code = "duplicate_invoice"
            elif v is None:
                code = "unknown_visit"
            elif v["station"] != st:
                code = "station_mismatch"
            elif pdate(fl[2]) < v["board"].date():
                code = "early_invoice"
            elif paid_visits is not None and v["id"] in paid_visits:
                code = "already_paid"
            if code:
                self.reject(f, i, code, inv=fl[0])
                continue
            out.append({"id": fl[0], "visit": v, "date": pdate(fl[2]), "amount": int(fl[3].replace(".", "")),
                        "station": st, "sup": fl[4] if len(fl) > 4 else ""})
        return out

    # ---------------------------------------------------------------- rules
    def row(self, v):
        rows = self.rows[v["vessel"]]
        base = [r for r in rows if r["mfrom"] is None] or rows[:1]
        if "q6" in self.rx:
            return base[0]
        d = v["board"].date()
        cand = [r for r in rows if r["mfrom"] is not None and r["mfrom"] <= d]
        return max(cand, key=lambda r: r["mfrom"]) if cand else base[0]

    def instant(self, v):
        return v["release"] if "prel" in self.rx else v["board"]

    def period(self, inv):
        st, v = inv["station"], inv["visit"]
        d = self.notice.get(st)
        if d is None:
            return D0
        if "pinv" in self.rx:
            return d if inv["date"] >= d else D0
        t = self.instant(v)
        if "pstrict" in self.rx:
            return d if t.date() > d else D0
        return d if t >= midnight(d) else D0

    def night(self, v):
        if v["cancel"]:
            return False
        t = self.instant(v)
        return t.hour >= 22 or t.hour < 6 or t.date().isoformat() in self.hol[v["station"]]

    def cover(self):
        """covered minutes per visit id (LV-3)."""
        self.covered = {}
        self.draws = {}
        invoiced = {p["visit"]["id"] for p in self.paid} | {d["visit"]["id"] for d in self.disp}
        pools = {}
        for v in self.visits.values():
            r = self.rows[v["vessel"]][0]
            if r["seg"] != "public" or r["cert"] == "-" or r["cert"] not in self.certs:
                continue
            if "exinv" in self.rx and v["id"] not in invoiced:
                continue
            key = (r["cert"], v["vessel"]) if "exvessel" in self.rx else (r["cert"],)
            pools.setdefault(key, []).append(v)
        for key, vs in pools.items():
            c = self.certs[key[0]]
            exp = pdate(c["expiry"])
            cut = midnight(exp) + (timedelta(days=1) if "exincl" in self.rx else timedelta(0))
            left = c["allowance_minutes"]
            if "exorder" in self.rx:
                vs.sort(key=lambda v: (v["board"], v["line"]))
            else:
                vs.sort(key=lambda v: (v["board"], v["id"]))
            if len({v["vessel"] for v in vs}) > 1:
                self.bump("LV-3 shared certificate pool")
            for v in vs:
                pre = 0 if v["cancel"] else max(0, int((min(v["release"], cut) - v["board"]).total_seconds() // 60))
                cov = pre if "excap" in self.rx else min(pre, left)
                if cov < pre:
                    self.bump("LV-3 cap hit")
                left -= cov
                self.covered[v["id"]] = cov
                if v["id"] not in invoiced and cov:
                    self.bump("LV-3 uninvoiced draw")

    def minutes(self, v):
        if v["cancel"]:
            return 0, 0
        onboard = int((v["release"] - v["board"]).total_seconds() // 60)
        return onboard, onboard - self.covered.get(v["id"], 0)

    def feats(self, inv):
        v = inv["visit"]
        r = self.row(v)
        onboard, billed = self.minutes(v)
        return {"cancel": v["cancel"], "station": v["station"], "gt": r["gt"], "seg": r["seg"],
                "draft": v["draft"], "tugs": v["tugs"], "assist": v["assist"], "night": self.night(v),
                "onboard": onboard, "billed": billed}

    def due(self, f, combo):
        if f["cancel"]:
            return self.fee[f["station"]]
        b, d, n, t = combo
        l1 = rhe(b * f["gt"], 100)
        l2 = d * max(0, f["draft"] - 60)
        l3 = t * f["tugs"]
        l4 = 4000 * (-(-f["assist"] // 30))
        l5 = rhe((n - 100) * (l1 + l2 + l3), 100) if f["night"] else 0
        lines = (l1, l2, l3, l4, l5)
        if f["billed"] == f["onboard"]:
            s = sum(lines)
        elif f["billed"] == 0:
            s = 0
        else:
            s = sum(rhe(x * f["billed"], f["onboard"]) for x in lines)
        if f["seg"] == "commercial" and "q5" not in self.rx:
            s = max(s, self.minimum[f["station"]])
        return s

    # ---------------------------------------------------------------- run
    def run(self):
        self.load()
        self.cover()
        for inv in self.paid + self.disp:
            inv["f"] = self.feats(inv)
            inv["period"] = self.period(inv)
        self.periods = {s: [D0] + ([self.notice[s]] if s in self.notice else []) for s in STATIONS}
        groups = {(s, p): [] for s in STATIONS for p in self.periods[s]}
        for p in self.paid:
            groups.setdefault((p["station"], p["period"]), []).append(p)
        alone = {}
        for key, ps in groups.items():
            alone[key] = [c for c in COMBOS if all(self.due(p["f"], c) == p["amount"] for p in ps)]
            self.bump(f"fits alone {key[0]} {key[1]}={len(alone[key])}")
        self.tariff = {}
        for s in STATIONS:
            ps = self.periods[s]
            if len(ps) == 1 or "indep" in self.rx:
                proj = {p: alone[(s, p)] for p in ps}
            else:
                fixed = [i for i, k in enumerate(COEF) if k not in self.named[s]]
                a, b = alone[(s, ps[0])], alone[(s, ps[1])]
                keys_b = {tuple(c[i] for i in fixed) for c in b}
                keys_a = {tuple(c[i] for i in fixed) for c in a}
                proj = {ps[0]: [c for c in a if tuple(c[i] for i in fixed) in keys_b],
                        ps[1]: [c for c in b if tuple(c[i] for i in fixed) in keys_a]}
            for p, fits in proj.items():
                self.bump(f"fits joint {s} {p}={len(fits)}")
                if "fit" in self.rx and fits:
                    fits = fits[:1]
                self.tariff[(s, p)] = fits[0] if len(fits) == 1 else (NOFIT if not fits else MULTI)
        rows = []
        for inv in sorted(self.disp, key=lambda x: x["id"]):
            v, f = inv["visit"], inv["f"]
            t = self.tariff[(inv["station"], inv["period"])]
            self.fire_disp(inv, t)
            if isinstance(t, str):
                rec, diff, verdict, reason = None, None, "cannot_recompute", t
            else:
                rec = self.due(f, t)
                diff = inv["amount"] - rec
                verdict = "billed_correctly" if diff == 0 else ("overbilled" if diff > 0 else "underbilled")
                reason = None
            rows.append({"invoice_id": inv["id"], "visit_id": v["id"], "station": inv["station"],
                         "period_start": inv["period"].isoformat(), "segment": f["seg"],
                         "billed": inv["amount"], "recomputed": rec, "difference": diff, "verdict": verdict,
                         "reason": reason, "onboard_minutes": f["onboard"], "billed_minutes": f["billed"],
                         "_vessel": v["vessel"]})
        self.out_rows = rows

    def fire_disp(self, inv, t):
        v, f = inv["visit"], inv["f"]
        st = inv["station"]
        if t == MULTI:
            self.bump("LV-1 multi-fit disputed")
        if t == NOFIT:
            self.bump("LV-1 no-fit disputed")
        d = self.notice.get(st)
        if d is not None:
            d0 = midnight(d)
            if v["board"].date() == d:
                self.bump("LV-2 boarding on notice date")
            if v["board"] < d0 < v["release"]:
                self.bump("LV-2 eve boarding released after notice midnight")
            if v["board"] < d0 and inv["date"] >= d:
                self.bump("LV-2 boarded before, invoiced on/after notice")
        if f["seg"] == "public":
            if 0 < f["billed"] < f["onboard"]:
                self.bump("LV-3 partial")
            r = self.rows[v["vessel"]][0]
            if r["cert"] == "-":
                self.bump("Q7 public without certificate")
        if f["assist"]:
            self.bump("Q1 assist")
        if f["cancel"]:
            self.bump("Q4 cancelled booking")
        b = v["board"]
        ds = b.date().isoformat()
        if not f["cancel"] and ds in self.hol[st] and (b.date() - timedelta(days=1)).isoformat() in self.hol[st] \
                and (b.date() - timedelta(days=1)).weekday() == 6:
            self.bump("Q3 Monday after Sunday holiday")
        if not f["cancel"] and ds in self.hol_all:
            self.bump("Q10 holiday of every station")
        if len(self.rows[v["vessel"]]) > 1:
            self.bump("Q6 re-measured vessel")
        if not isinstance(t, str) and f["seg"] == "commercial" and not f["cancel"]:
            raw = self.due(dict(f, seg="public"), t)
            if raw < self.minimum[st]:
                self.bump("Q5 minimum due raised")

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

        rows = self.out_rows
        summ = agg(rows)
        over = [r for r in rows if r["verdict"] == "overbilled"]
        best = min(over, key=lambda r: (-r["difference"], r["invoice_id"])) if over else None
        summ["largest_refund"] = {"invoice_id": best["invoice_id"], "amount": money(best["difference"])} if best else None
        dump("summary.json", summ)
        audit = []
        for r in rows:
            a = {k: x for k, x in r.items() if not k.startswith("_")}
            for k in ("billed", "recomputed", "difference"):
                a[k] = None if a[k] is None else money(a[k])
            audit.append(a)
        dump("policy_audit.json", {"rows": audit})
        rej = sorted(({k: x for k, x in r.items() if not k.startswith("_")} for r in self.rejected),
                     key=lambda x: (x["file"], x["line"]))
        dump("data_quality.json", {"rejected": rej,
                                   "counts": {c: sum(1 for x in rej if x["code"] == c) for c in CODES}})
        for s in STATIONS:
            periods = []
            for p in self.periods[s]:
                t = self.tariff[(s, p)]
                tar = None if isinstance(t, str) else {k: money(x) for k, x in zip(COEF, t)}
                if tar:
                    for k in ("base_per_100gt", "draft_per_dm", "night_factor"):
                        tar[k] = f"{t[COEF.index(k)] // 100}.{t[COEF.index(k)] % 100:02d}"
                periods.append({"period_start": p.isoformat(), "tariff": tar,
                                "reason": t if isinstance(t, str) else None,
                                "paid_invoices": sum(1 for x in self.paid if x["station"] == s and x["period"] == p)})
            a = agg([r for r in rows if r["station"] == s])
            dump(f"region_{s}.json", {"station": s, "periods": periods, "disputes": a["disputes"],
                                      "verdict_counts": a["verdict_counts"], "refund_total": a["refund_total"],
                                      "shortfall_total": a["shortfall_total"]})
        for g in SEGMENTS:
            rs = [r for r in rows if r["segment"] == g]
            a = agg(rs)
            doc = {"segment": g, "disputes": a["disputes"], "vessels": len({r["_vessel"] for r in rs})}
            doc.update({k: a[k] for k in ("verdict_counts", "billed_total", "recomputed_total", "refund_total",
                                          "shortfall_total")})
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
