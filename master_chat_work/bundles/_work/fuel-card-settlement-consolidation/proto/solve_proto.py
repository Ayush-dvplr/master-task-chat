"""Prototype settlement consolidation (reference reading of the docs)."""
import argparse
import configparser
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP

PROCS = ["kestrel", "lumen", "marlow", "norvik", "oberon"]
REGIONS = ["central", "east", "north", "south", "west"]
SEGMENTS = ["consumer", "corporate", "enterprise", "smb"]
REASONS = ["superseded_batch", "withdrawn_batch", "pump_test", "void_record", "out_of_period",
           "unknown_product", "unknown_card", "account_closed", "voided", "replaced", "duplicate",
           "orphan_reversal", "ambiguous_reversal"]
US_GAL = Decimal("3.785411784")
IMP_GAL = Decimal("4.54609")
CNG_L_PER_KG = Decimal("1.52")
C2 = Decimal("0.01")
C3 = Decimal("0.001")
FIRE = {}


class InputError(Exception):
    def __init__(self, rel, why):
        super().__init__("%s: %s" % (rel, why))
        self.rel = rel


def fire(key, n=1):
    FIRE[key] = FIRE.get(key, 0) + n


def r2(x):
    v = x.quantize(C2, rounding=ROUND_HALF_EVEN)
    if v != x.quantize(C2, rounding=ROUND_HALF_UP):
        fire("R12 half-even tie (cents)")
    return v


def r3(x):
    v = x.quantize(C3, rounding=ROUND_HALF_EVEN)
    if v != x.quantize(C3, rounding=ROUND_HALF_UP):
        fire("R12 half-even tie (litres)")
    return v


def s2(x):
    x = r2(x)
    return "0.00" if x == 0 else "%s" % x


def s3(x):
    x = r3(x)
    return "0.000" if x == 0 else "%s" % x


def offset(text):
    sign = -1 if text[0] == "-" else 1
    hh, mm = text[1:].split(":")
    return timedelta(minutes=sign * (int(hh) * 60 + int(mm)))


class Data:
    def __init__(self, root):
        self.root = root

    def path(self, rel):
        p = os.path.join(self.root, rel)
        if not os.path.isfile(p):
            raise InputError(rel, "missing")
        return p

    def text(self, rel):
        try:
            with open(self.path(rel), encoding="utf-8", newline="") as fh:
                return fh.read()
        except UnicodeDecodeError as exc:
            raise InputError(rel, "not UTF-8 (%s)" % exc)

    def rows(self, rel, delim=","):
        txt = self.text(rel)
        rows = list(csv.DictReader(txt.splitlines(), delimiter=delim))
        if not rows and not txt.strip():
            raise InputError(rel, "empty")
        return rows


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fire")
    return ap.parse_args()


def load_refs(d):
    try:
        procs = json.loads(d.text("ref/processors.json"))
        month = procs["settlement_month"]
        pinfo = {p["name"]: p for p in procs["processors"]}
        y, m = int(month[:4]), int(month[5:7])
    except (ValueError, KeyError, TypeError) as exc:
        raise InputError("ref/processors.json", "cannot parse (%s)" % exc)
    for p in PROCS:
        if p not in pinfo:
            raise InputError("ref/processors.json", "no entry for %s" % p)
    try:
        sites = {r["site_id"]: (r["region"], offset(r["utc_offset"]), r["jurisdiction"])
                 for r in d.rows("ref/sites.csv")}
    except (KeyError, ValueError, IndexError) as exc:
        raise InputError("ref/sites.csv", "cannot parse (%s)" % exc)
    try:
        cards = {}
        for r in d.rows("ref/cards.csv"):
            cards.setdefault(r["card_number"], []).append(
                (r["account_id"], date.fromisoformat(r["valid_from"]),
                 date.fromisoformat(r["valid_to"]) if r["valid_to"] else None))
    except (KeyError, ValueError) as exc:
        raise InputError("ref/cards.csv", "cannot parse (%s)" % exc)
    try:
        accts = {}
        closed = {}
        for r in d.rows("ref/accounts.csv"):
            accts.setdefault(r["account_id"], []).append((date.fromisoformat(r["effective_from"]), r["segment"]))
            closed[r["account_id"]] = date.fromisoformat(r["closed_on"]) if r["closed_on"] else None
        for v in accts.values():
            v.sort()
    except (KeyError, ValueError) as exc:
        raise InputError("ref/accounts.csv", "cannot parse (%s)" % exc)
    try:
        cat = ET.fromstring(d.text("ref/products.xml"))
        prods, alias = {}, {p: {} for p in PROCS}
        for e in cat.findall("product"):
            prods[e.get("code")] = (e.get("kind"), e.get("tax_class"), e.get("unit"))
            for a in e.findall("alias"):
                alias.setdefault(a.get("processor"), {})[a.get("code")] = e.get("code")
    except ET.ParseError as exc:
        raise InputError("ref/products.xml", "cannot parse (%s)" % exc)
    ini = configparser.ConfigParser()
    try:
        ini.read_string(d.text("ref/discount_tiers.ini"))
        eligible = [s.strip() for s in ini["eligible"]["segments"].split(",") if s.strip()]
        tiers = []
        for sec in ini.sections():
            if sec.startswith("tier."):
                tiers.append((Decimal(ini[sec]["floor_litres"]), sec[5:], Decimal(ini[sec]["rate_per_litre"])))
        tiers.sort()
        caps = {k: Decimal(v) for k, v in ini["cap"].items()}
    except (configparser.Error, KeyError, ArithmeticError) as exc:
        raise InputError("ref/discount_tiers.ini", "cannot parse (%s)" % exc)
    try:
        tax = {}
        for r in d.rows("ref/tax_rates.tsv", "\t"):
            tax.setdefault((r["jurisdiction"], r["tax_class"]), []).append(
                (date.fromisoformat(r["effective_from"]), Decimal(r["rate"])))
        for v in tax.values():
            v.sort()
    except (KeyError, ValueError, ArithmeticError) as exc:
        raise InputError("ref/tax_rates.tsv", "cannot parse (%s)" % exc)
    try:
        standing, opened_pos = {}, {}
        for i, line in enumerate(d.text("ref/batches.log").splitlines()):
            if not line.strip():
                continue
            _ts, p, b, ev = line.split()
            if ev == "OPENED" and (p, b) not in opened_pos:
                opened_pos[(p, b)] = i
            if ev in ("SUPERSEDED", "WITHDRAWN", "REINSTATED"):
                standing[(p, b)] = ev
    except ValueError as exc:
        raise InputError("ref/batches.log", "cannot parse (%s)" % exc)
    return dict(month=month, y=y, m=m, pinfo=pinfo, sites=sites, cards=cards, accts=accts,
                closed=closed, prods=prods, alias=alias, eligible=eligible, tiers=tiers, caps=caps,
                tax=tax, standing=standing, opened_pos=opened_pos)


def lit(proc, unit, q):
    """Native quantity string -> litres (Decimal, unrounded)."""
    q = Decimal(q)
    if unit == "kg":
        return q * CNG_L_PER_KG
    if proc == "lumen":
        return q / 100 * US_GAL
    if proc == "norvik":
        return q * IMP_GAL
    if proc == "oberon":
        return q / 1000
    return q


def read_exports(d, R):
    lines = []
    for p in PROCS:
        rel = R["pinfo"][p]["export"]
        try:
            lines.extend(globals()["read_" + p](d, rel, R))
        except (ValueError, KeyError, IndexError, ArithmeticError, ET.ParseError) as exc:
            raise InputError(rel, "cannot parse (%s)" % exc)
    return lines


def L(p, src, batch, kind, utc=None, local_date=None, site=None, card=None, alias=None, qty=None,
      amount=None, incl=True, ref=None, **kw):
    x = dict(p=p, src=src, batch=batch, kind=kind, utc=utc, local_date=local_date, site=site, card=card,
             alias=alias, qty=qty, amount=amount, incl=incl, ref=ref)
    x.update(kw)
    return x


def read_kestrel(d, rel, R):
    out = []
    pt = R["pinfo"]["kestrel"]["pump_test_type"]
    for i, r in enumerate(d.rows(rel)):
        t = r["type"]
        kind = "pump" if t == pt else {"SALE": "sale", "REV": "rev"}[t]
        utc = datetime.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        out.append(L("kestrel", r["txn_id"], r["batch"], kind, utc=utc, site=r["site"], card=r["card"],
                     alias=r["product"], qty=r["quantity"], amount=Decimal(r["amount"]), incl=True,
                     ref=r["orig_txn"] or None, pos=i))
    return out


def read_lumen(d, rel, R):
    lay = R["pinfo"]["lumen"]["layout"]
    out = []
    for i, line in enumerate(d.text(rel).splitlines()):
        if not line.strip():
            continue
        f = {e["field"]: line[e["start"] - 1:e["start"] - 1 + e["width"]] for e in lay}
        src = "%d-%d" % (int(f["txn"]), int(f["line"]))
        card = f["card"][-16:]
        stamp = f["stamp"][-10:]
        local = datetime.strptime("20" + stamp, "%Y%m%d%H%M")
        kind = "pump" if set(f["card"]) == {"0"} else ("rev" if f["sign"] == "-" else "sale")
        out.append(L("lumen", src, f["batch"].strip(), kind, local_date=local.date(),
                     site=str(int(f["site"])), card=card, alias=f["product"].strip(),
                     qty=str(int(f["quantity"])), amount=Decimal(int(f["amount"])) / 100, incl=False,
                     ref=f["ref"].strip() or None, pos=i))
    return out


def read_marlow(d, rel, R):
    ho = offset(R["pinfo"]["marlow"]["head_office_offset"])
    out = []
    for i, line in enumerate(d.text(rel).splitlines()):
        if not line.strip():
            continue
        o = json.loads(line)
        utc = (datetime.strptime(o["at"], "%Y-%m-%d %H:%M:%S") - ho).replace(tzinfo=timezone.utc)
        kind = "void" if o["kind"] == "void" else ("pump" if o["test"] else "sale")
        out.append(L("marlow", str(o["id"]), o["batch"], kind, utc=utc, site=o["site"], card=o["card"],
                     alias=o["product"], qty=o["quantity"], amount=Decimal(o["amount"]), incl=False,
                     ref=o.get("voids"), resub=o.get("resubmission_of"), pos=i))
    return out


def read_norvik(d, rel, R):
    root = ET.fromstring(d.text(rel))
    out = []
    for i, e in enumerate(root.findall("record")):
        utc = datetime.fromisoformat(e.findtext("time")).astimezone(timezone.utc)
        rev = e.find("reverses")
        purpose = e.findtext("purpose")
        kind = "pump" if purpose == "calibration" else ("rev" if rev is not None else "sale")
        if purpose == "calibration":
            fire("Q13 norvik calibration")
        out.append(L("norvik", e.get("id"), e.get("batch"), kind, utc=utc, site=e.findtext("site"),
                     card=e.findtext("card"), alias=e.findtext("product"),
                     qty=e.findtext("quantity").lstrip("-"), amount=abs(Decimal(e.findtext("amount"))),
                     incl=True, ref=rev.text if rev is not None else None, pos=i))
    return out


def read_oberon(d, rel, R):
    out = []
    for i, r in enumerate(d.rows(rel, "\t")):
        kind = {"S": "sale", "R": "rev", "T": "pump"}[r["entry"]]
        utc = datetime.fromtimestamp(int(r["epoch"]), tz=timezone.utc)
        if r["tender"] != "1":
            fire("Q14 oberon split tender line")
        out.append(L("oberon", "%s/%s" % (r["txn_id"], r["tender"]), r["batch"], kind, utc=utc,
                     site=r["site"], card=r["card"], alias=r["product"], qty=r["ml"],
                     amount=Decimal(int(r["amount_cents"])) / 100, incl=True, ref=r["ref"] or None, pos=i))
    return out


def holder(R, card, day):
    for acct, f, t in R["cards"].get(card, []):
        if f <= day and (t is None or day <= t):
            return acct
    return None


def segment_on(R, acct, day):
    seg = None
    for eff, s in R["accts"].get(acct, []):
        if eff <= day:
            seg = s
    if seg is None:
        fire("GAP no segment row on date")
    return seg


def rate_on(R, jur, cls, day):
    rate = None
    for eff, r in R["tax"].get((jur, cls), []):
        if eff <= day:
            rate = r
    if rate is None:
        raise InputError("ref/tax_rates.tsv", "no rate for %s %s on %s" % (jur, cls, day))
    return rate


def settle(R, lines):
    y, m = R["y"], R["m"]
    first = date(y, m, 1)
    last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
    for x in lines:
        site = R["sites"].get(x["site"])
        if site is None:
            raise InputError(R["pinfo"][x["p"]]["export"], "unknown site %s" % x["site"])
        x["region"], off, x["jur"] = site
        if x["local_date"] is None:
            x["local_date"] = (x["utc"] + off).date()
            if (first <= x["local_date"] <= last) != (first <= x["utc"].date() <= last):
                fire("Q1 period differs between local and UTC date")
        x["reason"] = None
    # checks 1-7
    for x in lines:
        st = R["standing"].get((x["p"], x["batch"]))
        if st == "SUPERSEDED":
            x["reason"] = "superseded_batch"
        elif st == "WITHDRAWN":
            x["reason"] = "withdrawn_batch"
        elif x["kind"] == "pump":
            x["reason"] = "pump_test"
        elif x["kind"] == "void":
            x["reason"] = "void_record"
        elif not (first <= x["local_date"] <= last):
            x["reason"] = "out_of_period"
        elif x["kind"] == "sale":
            code = R["alias"].get(x["p"], {}).get(x["alias"])
            if code is None:
                x["reason"] = "unknown_product"
                continue
            x["code"] = code
            acct = holder(R, x["card"], x["local_date"])
            if acct is None:
                x["reason"] = "unknown_card"
                continue
            x["acct"] = acct
            cl = R["closed"].get(acct)
            if cl is not None and x["local_date"] > cl:
                x["reason"] = "account_closed"
        if st == "REINSTATED" and x["reason"] is None:
            fire("Q10 line in reinstated batch")
    # check 8: voided / replaced (named by live records)
    by_src = {}
    for x in lines:
        by_src.setdefault((x["p"], x["src"]), []).append(x)
    for x in lines:
        if R["standing"].get((x["p"], x["batch"])) in ("SUPERSEDED", "WITHDRAWN"):
            continue
        if x["kind"] == "void" and x["ref"]:
            for t in by_src.get((x["p"], x["ref"]), []):
                if t["reason"] is None:
                    t["reason"] = "voided"
        if x["kind"] == "sale" and x.get("resub"):
            for t in by_src.get((x["p"], x["resub"]), []):
                if t["reason"] is None:
                    t["reason"] = "replaced"
                    fire("Q12 replaced")
    # check 9: duplicates
    for key, group in by_src.items():
        alive = [x for x in group if x["reason"] is None]
        if len(alive) > 1:
            alive.sort(key=lambda x: R["opened_pos"].get((x["p"], x["batch"]), 10 ** 9))
            for x in alive[1:]:
                x["reason"] = "duplicate"
                if x["pos"] < alive[0]["pos"]:
                    fire("Q15 rejected copy earlier in file")
    # sale rows
    rows = []
    sale_rows = {}
    for x in lines:
        if x["reason"] is None and x["kind"] == "sale":
            kind, cls, unit = R["prods"][x["code"]]
            if unit == "kg":
                fire("Q11 CNG line settled")
            litres = r3(lit(x["p"], unit, x["qty"])) if kind == "fuel" else Decimal("0.000")
            rate = rate_on(R, x["jur"], cls, x["local_date"])
            if rate != rate_on(R, x["jur"], cls, first):
                fire("Q4 rate differs from month start")
            if x["incl"]:
                net = r2(x["amount"] / (1 + rate))
                tax = x["amount"] - net
            else:
                net = x["amount"]
                tax = r2(net * rate)
            seg = segment_on(R, x["acct"], x["local_date"])
            if seg != segment_on(R, x["acct"], last):
                fire("Q3 segment differs from month end")
            if holder(R, x["card"], first) not in (None, x["acct"]) or holder(R, x["card"], last) not in (None, x["acct"]):
                fire("Q2 card holder changes in month")
            row = dict(ledger_id="%s:%s" % (x["p"], x["src"]), processor=x["p"], source_id=x["src"],
                       entry="sale", business_date=x["local_date"], account_id=x["acct"], segment=seg,
                       region=x["region"], site_id=x["site"], product=x["code"], kind=kind,
                       litres=litres, net=net, tax=tax)
            row["line"] = x
            rows.append(row)
            sale_rows[(x["p"], x["src"])] = row
    # check 10: reversals (11.2-11.5)
    WRONG = set(os.environ.get("FC_WRONG", "").split(","))
    taken = set()

    def emit(x, orig):
        row = dict(orig)
        row.update(ledger_id="%s:%s" % (x["p"], x["src"]), processor=x["p"], source_id=x["src"],
                   entry="reversal", business_date=x["local_date"], litres=-orig["litres"],
                   net=-orig["net"], tax=-orig["tax"], orig=orig)
        if "q16recompute" in WRONG and orig["line"]["incl"] is not None:
            ol = orig["line"]
            kind, cls, unit = R["prods"][ol["code"]]
            rate = rate_on(R, ol["jur"], cls, x["local_date"])
            if ol["incl"]:
                net = r2(ol["amount"] / (1 + rate)); tax = ol["amount"] - net
            else:
                net = ol["amount"]; tax = r2(net * rate)
            row.update(net=-net, tax=-tax)
        if rate_on(R, orig["line"]["jur"], R["prods"][orig["product"]][1], x["local_date"]) != \
                rate_on(R, orig["line"]["jur"], R["prods"][orig["product"]][1], orig["business_date"]):
            fire("Q16 reversal after a tax change")
        rows.append(row)
        taken.add(id(orig))

    revs = [x for x in lines if x["reason"] is None and x["kind"] == "rev"]
    refd = [x for x in revs if x["ref"]]
    unref = [x for x in revs if not x["ref"]]
    if "filestream" in WRONG:
        unref.sort(key=lambda x: (PROCS.index(x["p"]), x["pos"]))
    else:
        unref.sort(key=lambda x: (x["local_date"], "%s:%s" % (x["p"], x["src"])))

    def do_ref(x):
        ref = x["ref"]
        tp, ts = (ref.split(":", 1) if ":" in ref else (x["p"], ref))
        orig = sale_rows.get((tp, ts))
        if orig is None:
            x["reason"] = "orphan_reversal"
            if (tp, ts) in by_src:
                fire("Q8 orphan: original present but rejected")
            return
        if tp != x["p"]:
            fire("Q7 cross-processor reversal settled")
        emit(x, orig)

    sale_lines = {}
    for y in lines:
        if y["kind"] == "sale":
            sale_lines.setdefault(y["p"], []).append(y)

    def fits(x, settled_only):
        out = []
        for y in sale_lines.get(x["p"], []):
            if (y["card"], y["alias"], y["qty"], y["amount"]) != (x["card"], x["alias"], x["qty"], x["amount"]):
                continue
            if "nowindow" not in WRONG and not (x["local_date"] - timedelta(days=6) <= y["local_date"] <= x["local_date"]):
                continue
            row = sale_rows.get((y["p"], y["src"]))
            if settled_only and (y["reason"] is not None or row is None):
                continue
            if row is not None and id(row) in taken and (y["reason"] is None or "allparsed" in WRONG):
                continue
            out.append(y)
        return out

    def do_unref(x):
        good = fits(x, True)
        pool = fits(x, "allparsed" not in WRONG)
        if len(fits(x, False)) != len(good):
            fire("U3 rejected line would fit")
        cand = pool
        if "firstfit" in WRONG and cand:
            cand = sorted(cand, key=lambda y: y["pos"])[:1]
        if len(cand) == 1:
            y = cand[0]
            row = sale_rows.get((y["p"], y["src"])) if (y["reason"] is None or "allparsed" in WRONG) else None
            if row is None:
                x["reason"] = "orphan_reversal"
                return
            fire("R43 unreferenced reversal matched")
            emit(x, row)
        elif not cand:
            x["reason"] = "orphan_reversal"
        else:
            x["reason"] = "ambiguous_reversal"
            fire("U1 ambiguous_reversal")

    if "refnotfirst" in WRONG:
        for x in unref:
            do_unref(x)
        for x in refd:
            do_ref(x)
    else:
        for x in refd:
            do_ref(x)
        for x in unref:
            do_unref(x)
    for x in lines:
        if x["reason"] == "account_closed":
            fire("Q9 account_closed")
    rows.sort(key=lambda r: (r["business_date"], r["ledger_id"]))
    # tier volume
    vol = {r["account_id"]: Decimal("0") for r in rows}
    for r in rows:
        if r["kind"] == "fuel":
            vol[r["account_id"]] = vol.get(r["account_id"], Decimal("0")) + r["litres"]
    tier_of = {}
    for a, v in vol.items():
        best = None
        for floor, name, rate in R["tiers"]:
            if floor <= v:
                best = (name, rate)
            if floor == v and floor > 0:
                fire("Q5 tier volume exactly on a floor")
        tier_of[a] = best
    running, capped = {}, set()
    for r in rows:
        if r["entry"] == "sale":
            if r["kind"] == "fuel" and r["segment"] in R["eligible"] and tier_of.get(r["account_id"]):
                name, rate = tier_of[r["account_id"]]
                disc = r2(r["litres"] * rate)
                cap = R["caps"][r["segment"]]
                run = running.get(r["account_id"], Decimal("0"))
                if run + disc > cap:
                    disc = max(Decimal("0.00"), cap - run)
                    capped.add(r["account_id"])
                    fire("Q6 cap reduced a discount")
                running[r["account_id"]] = run + disc
                r["tier"], r["disc"] = name, disc
            else:
                r["tier"], r["disc"] = "none", Decimal("0.00")
    for r in rows:
        if r["entry"] == "reversal":
            r["tier"], r["disc"] = r["orig"]["tier"], -r["orig"]["disc"]
    for r in rows:
        r["settled"] = r["net"] + r["tax"] - r["disc"]
    return rows, vol, tier_of, capped, first, last


def totals(rows):
    t = dict(lines=len(rows), litres=Decimal("0"), net_amount=Decimal("0"), tax_amount=Decimal("0"),
             discount_amount=Decimal("0"), settled_amount=Decimal("0"))
    for r in rows:
        t["litres"] += r["litres"]
        t["net_amount"] += r["net"]
        t["tax_amount"] += r["tax"]
        t["discount_amount"] += r["disc"]
        t["settled_amount"] += r["settled"]
    return {"lines": t["lines"], "litres": s3(t["litres"]), "net_amount": s2(t["net_amount"]),
            "tax_amount": s2(t["tax_amount"]), "discount_amount": s2(t["discount_amount"]),
            "settled_amount": s2(t["settled_amount"])}


def dump(out, name, doc):
    with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=2, sort_keys=True) + "\n")


def write_outputs(out, R, lines, rows, vol, tier_of, capped, last):
    os.makedirs(out, exist_ok=True)
    month = R["month"]
    with open(os.path.join(out, "normalized.jsonl"), "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps({
                "ledger_id": r["ledger_id"], "processor": r["processor"], "source_id": r["source_id"],
                "entry": r["entry"], "business_date": r["business_date"].isoformat(),
                "account_id": r["account_id"], "segment": r["segment"], "region": r["region"],
                "site_id": r["site_id"], "product": r["product"], "kind": r["kind"],
                "litres": s3(r["litres"]), "net_amount": s2(r["net"]), "tax_amount": s2(r["tax"]),
                "discount_amount": s2(r["disc"]), "settled_amount": s2(r["settled"]), "tier": r["tier"]}) + "\n")
    accts = sorted({r["account_id"] for r in rows})
    acc_docs = []
    for a in accts:
        ar = [r for r in rows if r["account_id"] == a]
        t = tier_of.get(a)
        acc_docs.append({"account_id": a, "segment": segment_on(R, a, last),
                         "tier_volume": s3(vol.get(a, Decimal("0"))), "tier": t[0] if t else "none",
                         "discount_amount": s2(sum((r["disc"] for r in ar), Decimal("0"))),
                         "capped": a in capped})
    dump(out, "summary.json", {"month": month, "ledger_rows": len(rows), "totals": totals(rows),
                               "accounts": acc_docs})
    procs = {}
    for p in PROCS:
        pl = [x for x in lines if x["p"] == p]
        rej = sum(1 for x in pl if x["reason"])
        procs[p] = {"rows_read": len(pl), "rows_settled": len(pl) - rej, "rows_rejected": rej}
    rejected = sorted(({"processor": x["p"], "source_id": x["src"], "reason": x["reason"]}
                       for x in lines if x["reason"]),
                      key=lambda e: (e["processor"], e["source_id"], e["reason"]))
    counts = {k: 0 for k in REASONS}
    for e in rejected:
        counts[e["reason"]] += 1
    dump(out, "data_quality.json", {"month": month, "processors": procs, "rejected": rejected,
                                    "reason_counts": counts})
    prods = {}
    for code, (kind, _c, _u) in R["prods"].items():
        t = totals([r for r in rows if r["product"] == code])
        t["kind"] = kind
        prods[code] = t
    dump(out, "product_summary.json", {"month": month, "products": prods})
    for reg in REGIONS:
        rr = [r for r in rows if r["region"] == reg]
        dump(out, "region_%s.json" % reg, {"month": month, "region": reg, "totals": totals(rr),
                                            "by_processor": {p: totals([r for r in rr if r["processor"] == p])
                                                             for p in PROCS}})
    tiers = [name for _f, name, _r in R["tiers"]] + ["none"]
    for seg in SEGMENTS:
        sr = [r for r in rows if r["segment"] == seg]
        dump(out, "segment_%s.json" % seg, {"month": month, "segment": seg, "totals": totals(sr),
                                             "by_tier": {t: totals([r for r in sr if r["tier"] == t])
                                                         for t in tiers}})


def main():
    a = parse_args()
    d = Data(a.data)
    try:
        R = load_refs(d)
        lines = read_exports(d, R)
        rows, vol, tier_of, capped, first, last = settle(R, lines)
    except InputError as exc:
        sys.stderr.write("transform: %s\n" % exc)
        return 2
    write_outputs(a.out, R, lines, rows, vol, tier_of, capped, last)
    if a.fire:
        with open(a.fire, "w") as fh:
            json.dump(FIRE, fh, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
