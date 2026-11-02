#!/usr/bin/env python3
"""Backdated entitlement replay: re-rate invoices with corrections and rebuild credit."""
import argparse
import bisect
import csv
import datetime as dt
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from fractions import Fraction

INPUT_FILES = [
    "accounts.json",
    "price_book.json",
    "legacy_terms.yaml",
    "entitlement_events.jsonl",
    "invoice_register.tsv",
    "invoice_lines.csv",
    "corrections.json",
    "credit_lots.json",
    "ledger_activity.log",
]
REGIONS = ["North", "South", "West", "East"]
SEGMENTS = ["commercial", "public"]
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Malformed(Exception):
    pass


# ---------------------------------------------------------------- helpers

def parse_date(s):
    if not isinstance(s, str) or not DATE_RE.match(s):
        raise Malformed(s)
    return dt.date.fromisoformat(s).toordinal()


def parse_month(s):
    if not isinstance(s, str) or not MONTH_RE.match(s):
        raise Malformed(s)
    y, m = int(s[:4]), int(s[5:])
    if not 1 <= m <= 12:
        raise Malformed(s)
    return y, m


def parse_cents(s):
    if isinstance(s, bool) or not isinstance(s, (str, int)):
        raise Malformed(s)
    try:
        d = Decimal(str(s).strip())
    except InvalidOperation:
        raise Malformed(s)
    if not d.is_finite():
        raise Malformed(s)
    return round(Fraction(d) * 100)


def parse_int(v):
    if isinstance(v, bool):
        raise Malformed(v)
    if isinstance(v, int):
        return v
    if isinstance(v, str) and re.match(r"^-?\d+$", v.strip()):
        return int(v.strip())
    raise Malformed(v)


def fmt(c):
    sign = "-" if c < 0 else ""
    c = abs(c)
    return "%s%d.%02d" % (sign, c // 100, c % 100)


def iso(o):
    return dt.date.fromordinal(o).isoformat()


def add_months(ym, n):
    y, m = ym
    t = y * 12 + (m - 1) + n
    return t // 12, t % 12 + 1


def month_str(ym):
    return "%04d-%02d" % ym


def day_of(ym, a):
    return dt.date(ym[0], ym[1], a).toordinal()


# ---------------------------------------------------------------- loading

def load_inputs(inp):
    for name in INPUT_FILES:
        if not os.path.isfile(os.path.join(inp, name)):
            sys.stderr.write("missing input: %s\n" % name)
            sys.exit(2)
    data = {}
    loaders = {
        "accounts.json": load_accounts,
        "price_book.json": load_prices,
        "legacy_terms.yaml": load_legacy,
        "entitlement_events.jsonl": load_events,
        "invoice_register.tsv": load_register,
        "invoice_lines.csv": load_lines,
        "corrections.json": load_corrections,
        "credit_lots.json": load_lots,
        "ledger_activity.log": load_ledger,
    }
    for name in INPUT_FILES:
        try:
            with open(os.path.join(inp, name), encoding="utf-8", newline="") as f:
                data[name] = loaders[name](f)
        except (Malformed, ValueError, KeyError, TypeError, IndexError,
                AttributeError, InvalidOperation, UnicodeDecodeError, csv.Error):
            sys.stderr.write("malformed input: %s\n" % name)
            sys.exit(2)
    return data


def load_accounts(f):
    j = json.load(f)
    if not isinstance(j, dict) or not isinstance(j["accounts"], list):
        raise Malformed()
    first = parse_month(j["first_statement_month"])
    last = parse_month(j["last_statement_month"])
    if last < first:
        raise Malformed()
    accts = {}
    for a in j["accounts"]:
        aid = a["account_id"]
        if not isinstance(aid, str) or aid in accts:
            raise Malformed()
        accts[aid] = {
            "account_id": aid,
            "parent_id": a["parent_id"],
            "region": a["region"],
            "segment": a["segment"],
        }
    return {"extract_id": j["extract_id"], "first": first, "last": last, "accounts": accts}


def load_prices(f):
    j = json.load(f)
    items = j["items"]
    if not isinstance(items, dict):
        raise Malformed()
    return {k: parse_cents(v) for k, v in items.items()}


def load_legacy(f):
    vals = {}
    for line in f:
        s = line.split("#", 1)[0].strip()
        if not s:
            continue
        if ":" not in s:
            raise Malformed()
        k, v = s.split(":", 1)
        vals[k.strip()] = v.strip().strip("'\"")
    n = parse_int(vals["credit_expiry_cycles"])
    if n < 0:
        raise Malformed()
    return {"credit_expiry_cycles": n}


def load_events(f):
    out = []
    for line in f:
        if not line.strip():
            continue
        e = json.loads(line)
        out.append((e["account_id"], e["item"], parse_int(e["quantity"]), parse_date(e["date"])))
    return out


def load_register(f):
    rows = list(csv.DictReader(f, delimiter="\t"))
    out = []
    seen = set()
    for r in rows:
        st = r["status"].strip()
        if st not in ("paid", "open", "void"):
            raise Malformed()
        iid = r["invoice_id"].strip()
        if iid in seen:
            raise Malformed()
        seen.add(iid)
        sm = r["statement_month"].strip()
        out.append({"invoice_id": iid, "account_id": r["account_id"].strip(),
                    "statement_month": sm, "ym": parse_month(sm), "status": st})
    return out


def load_lines(f):
    out = {}
    for r in csv.DictReader(f):
        iid = r["invoice_id"].strip()
        out.setdefault(iid, []).append(
            (parse_int(r["line_no"]), r["kind"].strip(), r["item"].strip(),
             parse_int(r["quantity"]), parse_cents(r["amount"])))
    for iid in out:
        out[iid].sort(key=lambda t: t[0])
    return out


def load_corrections(f):
    j = json.load(f)
    if not isinstance(j, list):
        raise Malformed()
    out = []
    for c in j:
        out.append({"correction_id": c["correction_id"], "account_id": c["account_id"],
                    "item": c["item"], "quantity": parse_int(c["quantity"]),
                    "effective_date": parse_date(c["effective_date"]),
                    "arrival_seq": parse_int(c["arrival_seq"])})
    return out


def load_lots(f):
    j = json.load(f)
    if not isinstance(j, list):
        raise Malformed()
    out = []
    for l in j:
        out.append({"lot_id": l["lot_id"], "account_id": l["account_id"],
                    "amount": parse_cents(l["amount"]),
                    "created_on": parse_date(l["created_on"]),
                    "expires_on": parse_date(l["expires_on"])})
    return out


def load_ledger(f):
    payments = {}
    transfers = []
    for idx, line in enumerate(f):
        s = line.strip()
        if not s:
            continue
        parts = s.split()
        ts, kind = parts[0], parts[1]
        day = parse_date(ts[:10])
        kv = {}
        for tok in parts[2:]:
            k, v = tok.split("=", 1)
            kv[k] = v
        if kind == "PAYMENT":
            payments[kv["invoice"]] = payments.get(kv["invoice"], 0) + parse_cents(kv["amount"])
        elif kind == "TRANSFER":
            transfers.append({"transfer_id": kv["transfer"], "from": kv["from"], "to": kv["to"],
                              "date": day, "requested": parse_cents(kv["requested"]), "seq": idx})
    return {"payments": payments, "transfers": transfers}


# ---------------------------------------------------------------- rating

def build_timelines(entries):
    """entries: list of (account, item, date, rank, qty). Returns {acct: {item: (dates, qtys)}}."""
    entries = sorted(entries, key=lambda e: (e[0], e[1], e[2], e[3]))
    out = {}
    for acct, item, d, _rank, q in entries:
        items = out.setdefault(acct, {})
        dates, qtys = items.setdefault(item, ([], []))
        if dates and dates[-1] == d:
            qtys[-1] = q
        else:
            dates.append(d)
            qtys.append(q)
    return out


def rate(timeline, prices, anchor, basis, ym):
    cur = day_of(ym, anchor)
    prev = day_of(add_months(ym, -1), anchor)
    basis_days = (cur - prev) if basis == "actual" else 30
    lines = []
    pror = []
    for item in sorted(timeline):
        dates, qtys = timeline[item]
        price = prices[item]
        i = bisect.bisect_right(dates, cur) - 1
        q = qtys[i] if i >= 0 else 0
        if q > 0:
            lines.append(("recurring", item, q, q * price))
        lo = bisect.bisect_right(dates, prev)
        hi = bisect.bisect_left(dates, cur)
        for k in range(lo, hi):
            old = qtys[k - 1] if k > 0 else 0
            new = qtys[k]
            if new != old:
                d = dates[k]
                amt = round(Fraction(price * (new - old) * (cur - d), basis_days))
                pror.append((d, item, ("proration", item, new - old, amt)))
    pror.sort(key=lambda t: (t[0], t[1]))
    lines.extend(p[2] for p in pror)
    return lines


# ---------------------------------------------------------------- main logic

def compute(data):
    A = data["accounts.json"]
    accts = A["accounts"]
    first, last = A["first"], A["last"]
    prices = data["price_book.json"]
    N = data["legacy_terms.yaml"]["credit_expiry_cycles"]
    register = data["invoice_register.tsv"]
    lines = data["invoice_lines.csv"]
    corrections = data["corrections.json"]
    lots_in = data["credit_lots.json"]
    ledger = data["ledger_activity.log"]

    events = data["entitlement_events.jsonl"]
    orig_entries = []
    for idx, (acct, item, q, d) in enumerate(events):
        if item not in prices:
            continue
        orig_entries.append((acct, item, d, (0, idx), q))
    orig_tl = build_timelines(orig_entries)

    inv_by_acct = {}
    for r in register:
        inv_by_acct.setdefault(r["account_id"], []).append(r)

    # --- anchor/basis recovery
    pairs = [(a, b) for a in range(1, 29) for b in ("actual", "thirty")]
    resolved = {}
    unresolved = {}
    for aid in sorted(accts):
        tl = orig_tl.get(aid, {})
        paid = [r for r in inv_by_acct.get(aid, []) if r["status"] == "paid"]
        recorded = [(r["ym"], [t[1:] for t in lines.get(r["invoice_id"], [])]) for r in paid]
        fits = []
        for a, b in pairs:
            ok = True
            for ym, rec in recorded:
                if rate(tl, prices, a, b, ym) != rec:
                    ok = False
                    break
            if ok:
                fits.append((a, b))
        if len(fits) == 1:
            resolved[aid] = fits[0]
        else:
            unresolved[aid] = ("anchor_none" if not fits else "anchor_ambiguous", len(fits))

    # --- corrections screening
    applied = []
    rejected = []
    seen_ids = set()
    for c in sorted(corrections, key=lambda c: c["arrival_seq"]):
        cid, aid = c["correction_id"], c["account_id"]
        reason = None
        if aid not in accts:
            reason = "unknown_account"
        elif c["item"] not in prices:
            reason = "unknown_item"
        elif cid in seen_ids:
            reason = "duplicate_id"
        elif aid in unresolved:
            reason = "account_unresolved"
        elif c["effective_date"] < day_of(first, resolved[aid][0]):
            reason = "before_window"
        seen_ids.add(cid)
        if reason:
            rejected.append({"correction_id": cid, "account_id": aid, "reason": reason,
                             "_seq": c["arrival_seq"]})
        else:
            applied.append(c)

    corr_entries = list(orig_entries)
    for c in applied:
        corr_entries.append((c["account_id"], c["item"], c["effective_date"],
                             (1, c["arrival_seq"]), c["quantity"]))
    corr_tl = build_timelines(corr_entries)

    window_months = []
    ym = first
    while ym <= last:
        window_months.append(ym)
        ym = add_months(ym, 1)

    audit_corrections = []
    for c in sorted(applied, key=lambda c: (c["effective_date"], c["account_id"], c["arrival_seq"])):
        a = resolved[c["account_id"]][0]
        fam = None
        for wm in window_months:
            if day_of(wm, a) >= c["effective_date"]:
                fam = month_str(wm)
                break
        audit_corrections.append({
            "correction_id": c["correction_id"], "account_id": c["account_id"],
            "item": c["item"], "quantity": c["quantity"],
            "effective_date": iso(c["effective_date"]),
            "first_affected_statement_month": fam,
        })

    # --- replay invoices
    inv_rows = {}  # invoice_id -> row dict (internal)
    schedule = {}  # date -> list of invoice ids
    for aid, (a, b) in resolved.items():
        tl = corr_tl.get(aid, {})
        for r in inv_by_acct.get(aid, []):
            if r["status"] not in ("paid", "open"):
                continue
            orig_total = sum(t[4] for t in lines.get(r["invoice_id"], []))
            corr_total = sum(t[3] for t in rate(tl, prices, a, b, r["ym"]))
            issue = day_of(r["ym"], a)
            inv_rows[r["invoice_id"]] = {
                "invoice_id": r["invoice_id"], "account_id": aid,
                "statement_month": r["statement_month"], "ym": r["ym"], "status": r["status"],
                "original_total": orig_total, "corrected_total": corr_total,
                "credit_applied": 0, "paid": ledger["payments"].get(r["invoice_id"], 0),
                "balance_due": 0, "issue": issue,
            }
            schedule.setdefault(issue, []).append(r["invoice_id"])

    # --- credit
    lots = {aid: [] for aid in resolved}
    for l in lots_in:
        if l["account_id"] in lots and l["amount"] > 0:
            lots[l["account_id"]].append({"lot_id": l["lot_id"], "account_id": l["account_id"],
                                          "rem": l["amount"], "created_on": l["created_on"],
                                          "expires_on": l["expires_on"]})

    def usable(aid, day):
        return sorted((l for l in lots[aid]
                       if l["created_on"] <= day < l["expires_on"] and l["rem"] > 0),
                      key=lambda l: (l["expires_on"], l["lot_id"]))

    tr_by_day = {}
    for t in ledger["transfers"]:
        tr_by_day.setdefault(t["date"], []).append(t)

    issued = {aid: 0 for aid in resolved}
    t_in = {aid: 0 for aid in resolved}
    t_out = {aid: 0 for aid in resolved}
    accepted_tr = []
    rejected_tr = []
    for day in sorted(set(tr_by_day) | set(schedule)):
        for t in sorted(tr_by_day.get(day, []), key=lambda t: t["seq"]):
            fa, ta = t["from"], t["to"]
            if fa not in accts or ta not in accts:
                reason = "unknown_account"
            elif accts[fa]["parent_id"] != accts[ta]["parent_id"]:
                reason = "different_parent"
            elif fa in unresolved or ta in unresolved:
                reason = "account_unresolved"
            else:
                reason = None
            if reason:
                rejected_tr.append({"transfer_id": t["transfer_id"], "reason": reason})
                continue
            src = usable(fa, day)
            want = min(t["requested"], sum(l["rem"] for l in src))
            moved = 0
            k = 0
            for l in src:
                if want - moved <= 0:
                    break
                take = min(l["rem"], want - moved)
                if take <= 0:
                    continue
                l["rem"] -= take
                moved += take
                k += 1
                lots[ta].append({"lot_id": "%s-%d" % (t["transfer_id"], k), "account_id": ta,
                                 "rem": take, "created_on": day, "expires_on": l["expires_on"]})
            t_out[fa] += moved
            t_in[ta] += moved
            accepted_tr.append({"transfer_id": t["transfer_id"], "from_account": fa,
                                "to_account": ta, "date": iso(day),
                                "requested": fmt(t["requested"]), "moved": fmt(moved)})
        for iid in sorted(schedule.get(day, []),
                          key=lambda i: (inv_rows[i]["account_id"], inv_rows[i]["statement_month"], i)):
            row = inv_rows[iid]
            aid = row["account_id"]
            need = max(row["corrected_total"], 0)
            applied_c = 0
            for l in usable(aid, day):
                if need - applied_c <= 0:
                    break
                take = min(l["rem"], need - applied_c)
                l["rem"] -= take
                applied_c += take
            row["credit_applied"] = applied_c
            due = row["corrected_total"] - applied_c
            if row["paid"] > due:
                amt = row["paid"] - due
                lots[aid].append({"lot_id": "%s-OP" % iid, "account_id": aid, "rem": amt,
                                  "created_on": day,
                                  "expires_on": day_of(add_months(row["ym"], N), resolved[aid][0])})
                issued[aid] += amt
            row["balance_due"] = max(due - row["paid"], 0)

    # --- expiry / closing
    after_last = add_months(last, 1)
    expired = {aid: 0 for aid in resolved}
    open_lots = {aid: [] for aid in resolved}
    expiries = []
    for aid in resolved:
        wend = day_of(after_last, resolved[aid][0]) - 1
        for l in lots[aid]:
            if l["rem"] <= 0:
                continue
            if l["expires_on"] <= wend:
                expired[aid] += l["rem"]
                expiries.append(l)
            else:
                open_lots[aid].append(l)
    expiries.sort(key=lambda l: (l["expires_on"], l["lot_id"]))

    # --- account rows
    rows = {}
    for aid in sorted(resolved):
        invs = sorted((r for r in inv_rows.values() if r["account_id"] == aid),
                      key=lambda r: (r["statement_month"], r["invoice_id"]))
        if not invs:
            continue
        a, b = resolved[aid]
        ol = sorted(open_lots[aid], key=lambda l: (l["expires_on"], l["lot_id"]))
        rows[aid] = {
            "account_id": aid,
            "parent_id": accts[aid]["parent_id"],
            "segment": accts[aid]["segment"],
            "anchor_day": a,
            "basis": b,
            "_invs": invs,
            "credits_issued": issued[aid],
            "credits_expired": expired[aid],
            "transferred_in": t_in[aid],
            "transferred_out": t_out[aid],
            "_open": ol,
            "closing_credit": sum(l["rem"] for l in ol),
            "_region": accts[aid]["region"],
        }

    def totals(rs):
        invs = [i for r in rs for i in r["_invs"]]
        return {
            "original_billed": fmt(sum(i["original_total"] for i in invs)),
            "corrected_billed": fmt(sum(i["corrected_total"] for i in invs)),
            "credit_applied": fmt(sum(i["credit_applied"] for i in invs)),
            "balance_due": fmt(sum(i["balance_due"] for i in invs)),
            "credits_issued": fmt(sum(r["credits_issued"] for r in rs)),
            "credits_expired": fmt(sum(r["credits_expired"] for r in rs)),
            "closing_credit": fmt(sum(r["closing_credit"] for r in rs)),
        }

    def out_row(r):
        return {
            "account_id": r["account_id"],
            "parent_id": r["parent_id"],
            "segment": r["segment"],
            "anchor_day": r["anchor_day"],
            "basis": r["basis"],
            "invoices": [{
                "invoice_id": i["invoice_id"],
                "statement_month": i["statement_month"],
                "status": i["status"],
                "original_total": fmt(i["original_total"]),
                "corrected_total": fmt(i["corrected_total"]),
                "credit_applied": fmt(i["credit_applied"]),
                "paid": fmt(i["paid"]),
                "balance_due": fmt(i["balance_due"]),
            } for i in r["_invs"]],
            "credits_issued": fmt(r["credits_issued"]),
            "credits_expired": fmt(r["credits_expired"]),
            "transferred_in": fmt(r["transferred_in"]),
            "transferred_out": fmt(r["transferred_out"]),
            "open_lots": [{"lot_id": l["lot_id"], "amount": fmt(l["rem"]),
                           "expires_on": iso(l["expires_on"])} for l in r["_open"]],
            "closing_credit": fmt(r["closing_credit"]),
        }

    docs = {}
    region_rows_all = []
    for reg in REGIONS:
        rs = [rows[a] for a in sorted(rows) if rows[a]["_region"] == reg]
        region_rows_all.extend(rs)
        d = {"region": reg, "accounts": [out_row(r) for r in rs]}
        d["totals"] = totals(rs)
        docs["region_%s.json" % reg] = d
    for seg in SEGMENTS:
        rs = [rows[a] for a in sorted(rows) if rows[a]["segment"] == seg
              and rows[a]["_region"] in REGIONS]
        d = {"segment": seg, "accounts_resolved": len(rs),
             "account_ids": [r["account_id"] for r in rs]}
        d.update(totals(rs))
        docs["segment_%s.json" % seg] = d

    region_rows_all.sort(key=lambda r: r["account_id"])
    rerated = sum(1 for r in region_rows_all for i in r["_invs"]
                  if i["corrected_total"] != i["original_total"])
    summary = {
        "extract_id": A["extract_id"],
        "accounts_total": len(accts),
        "accounts_resolved": len(region_rows_all),
        "accounts_unresolved": len(unresolved),
        "corrections_applied": len(applied),
        "corrections_rejected": len(rejected),
        "invoices_rerated": rerated,
    }
    summary.update(totals(region_rows_all))
    docs["summary.json"] = summary

    docs["policy_audit.json"] = {
        "corrections": audit_corrections,
        "transfers": accepted_tr,
        "expiries": [{"lot_id": l["lot_id"], "account_id": l["account_id"],
                      "expires_on": iso(l["expires_on"]), "amount": fmt(l["rem"])}
                     for l in expiries],
    }
    docs["data_quality.json"] = {
        "unresolved_accounts": [{"account_id": a, "reason": unresolved[a][0],
                                 "candidates_fitting": unresolved[a][1]}
                                for a in sorted(unresolved)],
        "rejected_corrections": [{"correction_id": r["correction_id"],
                                  "account_id": r["account_id"], "reason": r["reason"]}
                                 for r in sorted(rejected,
                                                 key=lambda r: (r["correction_id"], r["_seq"]))],
        "rejected_transfers": sorted(rejected_tr, key=lambda r: r["transfer_id"]),
        "void_invoices_ignored": sorted(r["invoice_id"] for r in register
                                        if r["status"] == "void"),
    }
    return docs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    data = load_inputs(args.input)
    docs = compute(data)
    os.makedirs(args.output, exist_ok=True)
    order = ["summary.json", "policy_audit.json", "data_quality.json"] + \
        ["region_%s.json" % r for r in REGIONS] + ["segment_%s.json" % s for s in SEGMENTS]
    for name in order:
        with open(os.path.join(args.output, name), "w", encoding="utf-8") as f:
            f.write(json.dumps(docs[name], indent=2) + "\n")


if __name__ == "__main__":
    main()
