#!/usr/bin/env python3
"""Prototype reference engine with variant flags (kill test + generator oracle).

CLI: python3 core.py --input DIR --output DIR   (variant via env KILL_VARIANT=k1=v1,k2=v2)
Variants:
  fit       unique | first | best | fixed1
  evidence  paid | withvoid | all
  replay    full | forward
  order     effective | arrival
  cstart    inclusive | halfopen
  expiry    exclusive | inclusive
  sameday   transfers_first | invoices_first
  cap       replayed | posted
  rounding  half_even | half_up
  ncycles   yaml | fixed12
"""
import copy, csv, json, os, sys, datetime as dt
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP

DEFAULT = dict(fit="unique", evidence="paid", replay="full", order="effective", cstart="inclusive",
               expiry="exclusive", sameday="transfers_first", cap="replayed", rounding="half_even",
               ncycles="yaml")
CENT = Decimal("0.01")
ZERO = Decimal(0)
ONE_DAY = dt.timedelta(days=1)
FILES = ["accounts.json", "price_book.json", "legacy_terms.yaml", "entitlement_events.jsonl",
         "invoice_register.tsv", "invoice_lines.csv", "corrections.json", "credit_lots.json",
         "ledger_activity.log"]
REGIONS = ("North", "South", "West", "East")
SEGMENTS = ("commercial", "public")


def variant(s=""):
    V = dict(DEFAULT)
    for kv in filter(None, s.split(",")):
        k, v = kv.split("=")
        V[k] = v
    return V


def s2(x):
    return str(x.quantize(CENT))


def d(s):
    return dt.date.fromisoformat(s)


def madd(m, k):
    y, mo = int(m[:4]), int(m[5:7]) - 1 + k
    return "%04d-%02d" % (y + mo // 12, mo % 12 + 1)


def mstart(m, a):
    return dt.date(int(m[:4]), int(m[5:7]), a)


def die(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(2)


def parse(inp):
    for f in FILES:
        if not os.path.isfile(os.path.join(inp, f)):
            die("missing input: " + f)
    P = lambda f: os.path.join(inp, f)
    acc = json.load(open(P("accounts.json")))
    D = dict(extract_id=acc["extract_id"], first=acc["first_statement_month"], last=acc["last_statement_month"],
             accounts={a["account_id"]: a for a in acc["accounts"]})
    D["prices"] = {k: Decimal(v) for k, v in json.load(open(P("price_book.json")))["items"].items()}
    D["ncyc"] = None
    for line in open(P("legacy_terms.yaml")):
        line = line.split("#")[0].strip()
        if line.startswith("credit_expiry_cycles:"):
            D["ncyc"] = int(line.split(":", 1)[1])
    D["events"] = [json.loads(l) for l in open(P("entitlement_events.jsonl")) if l.strip()]
    D["reg"] = list(csv.DictReader(open(P("invoice_register.tsv")), delimiter="\t"))
    lines = {}
    for r in csv.DictReader(open(P("invoice_lines.csv"))):
        lines.setdefault(r["invoice_id"], []).append(
            (int(r["line_no"]), r["kind"], r["item"], int(r["quantity"]), Decimal(r["amount"])))
    D["lines"] = {k: [t[1:] for t in sorted(v)] for k, v in lines.items()}
    D["corr"] = json.load(open(P("corrections.json")))
    D["lots"] = json.load(open(P("credit_lots.json")))
    pays, transfers = {}, []
    for raw in open(P("ledger_activity.log")):
        parts = raw.split()
        if len(parts) < 3:
            continue
        kv = dict(p.split("=", 1) for p in parts[2:] if "=" in p)
        if parts[1] == "PAYMENT":
            pays[kv["invoice"]] = pays.get(kv["invoice"], ZERO) + Decimal(kv["amount"])
        elif parts[1] == "TRANSFER":
            transfers.append(dict(id=kv["transfer"], frm=kv["from"], to=kv["to"], req=Decimal(kv["requested"]),
                                  posted=Decimal(kv["posted"]), date=d(parts[0][:10]), ts=parts[0]))
    D["pays"], D["transfers"] = pays, transfers
    return D


class Timeline:
    def __init__(self):
        self.e = {}

    def add(self, item, date, key, qty):
        self.e.setdefault(item, []).append((date, key, qty))

    def finish(self):
        for k in self.e:
            self.e[k].sort()
        return self

    def q(self, item, day):
        v = 0
        for date, _k, qty in self.e.get(item, []):
            if date <= day:
                v = qty
            else:
                break
        return v

    def changes(self, lo, hi):
        out = []
        for item, es in self.e.items():
            for day in sorted({x[0] for x in es if lo <= x[0] <= hi}):
                if self.q(item, day) != self.q(item, day - ONE_DAY):
                    out.append((day, item))
        return sorted(out)


def rate(tl, m, a, basis, prices, V):
    rnd = ROUND_HALF_EVEN if V["rounding"] == "half_even" else ROUND_HALF_UP
    s0, sp = mstart(m, a), mstart(madd(m, -1), a)
    out = []
    samp = s0 if V["cstart"] == "inclusive" else s0 - ONE_DAY
    for item in sorted(tl.e):
        qn = tl.q(item, samp)
        if qn > 0:
            out.append(("recurring", item, qn, (prices[item] * qn).quantize(CENT, rounding=rnd)))
    if V["cstart"] == "inclusive":
        ch = tl.changes(sp + ONE_DAY, s0 - ONE_DAY)
    else:
        ch = tl.changes(sp, s0 - ONE_DAY)
    L = (s0 - sp).days if basis == "actual" else 30
    for day, item in ch:
        delta = tl.q(item, day) - tl.q(item, day - ONE_DAY)
        r = (s0 - day).days
        out.append(("proration", item, delta, (prices[item] * delta * r / L).quantize(CENT, rounding=rnd)))
    return out


def original_timelines(D):
    orig = {k: Timeline() for k in D["accounts"]}
    for i, e in enumerate(D["events"]):
        if e["account_id"] in orig:
            orig[e["account_id"]].add(e["item"], d(e["date"]), (0, i), int(e["quantity"]))
    return {k: t.finish() for k, t in orig.items()}


CANDS = [(an, b) for an in range(1, 29) for b in ("actual", "thirty")]


def fitting(D, orig, acct, V, inv_by):
    keep = {"paid": ("paid",), "withvoid": ("paid", "void"), "all": ("paid", "void", "open")}[V["evidence"]]
    ev = [r for r in inv_by.get(acct, []) if r["status"] in keep]
    ok, scores = [], []
    for c in CANDS:
        miss = 0
        for r in ev:
            if rate(orig[acct], r["statement_month"], c[0], c[1], D["prices"], V) != D["lines"].get(r["invoice_id"], []):
                miss += 1
                if V["fit"] != "best":
                    break
        scores.append((miss, c))
        if miss == 0:
            ok.append(c)
            if V["fit"] == "first":
                break
    return ok, scores


def engine(D, V, fit_override=None, pay_fn=None):
    first, last = D["first"], D["last"]
    A = D["accounts"]
    prices = D["prices"]
    ncyc = 12 if V["ncycles"] == "fixed12" else D["ncyc"]
    orig = original_timelines(D)
    inv_by, void = {}, []
    for r in D["reg"]:
        if r["status"] == "void":
            void.append(r["invoice_id"])
        inv_by.setdefault(r["account_id"], []).append(r)

    fit, unresolved = {}, []
    for acct in sorted(A):
        if fit_override is not None:
            fit[acct] = fit_override[acct]
            continue
        if V["fit"] == "fixed1":
            fit[acct] = (1, "actual")
            continue
        ok, scores = fitting(D, orig, acct, V, inv_by)
        if V["fit"] == "best":
            fit[acct] = min(scores)[1]
        elif V["fit"] == "first":
            fit[acct] = ok[0] if ok else (1, "actual")
        elif len(ok) == 1:
            fit[acct] = ok[0]
        else:
            unresolved.append(dict(account_id=acct, reason="anchor_none" if not ok else "anchor_ambiguous",
                                   candidates_fitting=len(ok)))
    unres = {u["account_id"] for u in unresolved}

    accepted, rejected, seen = [], [], set()
    for c in sorted(D["corr"], key=lambda c: c["arrival_seq"]):
        acct = c["account_id"]
        if acct not in A:
            why = "unknown_account"
        elif c["item"] not in prices:
            why = "unknown_item"
        elif c["correction_id"] in seen:
            why = "duplicate_id"
        elif acct in unres:
            why = "account_unresolved"
        elif d(c["effective_date"]) < mstart(first, fit[acct][0]):
            why = "before_window"
        else:
            why = None
        seen.add(c["correction_id"])
        if why:
            rejected.append(dict(correction_id=c["correction_id"], account_id=acct, reason=why))
        else:
            accepted.append(c)

    corrected = {}
    for acct in A:
        if acct in unres:
            continue
        t = Timeline()
        for item, es in orig[acct].e.items():
            for x in es:
                t.add(item, *x)
        mine = [c for c in accepted if c["account_id"] == acct]
        if V["order"] == "arrival":
            for c in sorted(mine, key=lambda c: c["arrival_seq"]):
                cd = d(c["effective_date"])
                t.e[c["item"]] = [x for x in t.e.get(c["item"], []) if x[0] < cd]
                t.add(c["item"], cd, (1, c["arrival_seq"]), int(c["quantity"]))
        else:
            for c in mine:
                t.add(c["item"], d(c["effective_date"]), (1, c["arrival_seq"]), int(c["quantity"]))
        corrected[acct] = t.finish()

    def first_aff(c):
        an = fit[c["account_id"]][0]
        cd = d(c["effective_date"])
        m = first
        while mstart(m, an) < cd:
            m = madd(m, 1)
        return m

    invs = {}
    for acct in sorted(A):
        if acct in unres:
            continue
        an, b = fit[acct]
        aff = {first_aff(c) for c in accepted if c["account_id"] == acct}
        for r in sorted(inv_by.get(acct, []), key=lambda r: r["statement_month"]):
            if r["status"] == "void":
                continue
            ot = sum((x[3] for x in D["lines"].get(r["invoice_id"], [])), ZERO)
            if V["replay"] == "forward" and r["statement_month"] not in aff:
                ct = ot
            else:
                ct = sum((x[3] for x in rate(corrected[acct], r["statement_month"], an, b, prices, V)), ZERO)
            invs.setdefault(acct, []).append(dict(invoice_id=r["invoice_id"], statement_month=r["statement_month"],
                                                  status=r["status"], original_total=ot, corrected_total=ct))

    L = []
    LB = {}

    def addlot(l):
        L.append(l)
        LB.setdefault(l["account_id"], []).append(l)
    for x in D["lots"]:
        if x["account_id"] in A and x["account_id"] not in unres:
            addlot(dict(lot_id=x["lot_id"], account_id=x["account_id"], amount=Decimal(x["amount"]),
                          created_on=d(x["created_on"]), expires_on=d(x["expires_on"])))

    def usable(acct, day):
        if V["expiry"] == "exclusive":
            ok = lambda l: l["created_on"] <= day < l["expires_on"]
        else:
            ok = lambda l: l["created_on"] <= day <= l["expires_on"]
        return sorted([l for l in LB.get(acct, []) if l["amount"] > 0 and ok(l)],
                      key=lambda l: (l["expires_on"], l["lot_id"]))

    tf = 0 if V["sameday"] == "transfers_first" else 1
    acts = []
    for acct, lst in invs.items():
        an = fit[acct][0]
        for inv in lst:
            acts.append((mstart(inv["statement_month"], an), 1 - tf, acct, 0, "inv", inv))
    rej_t, done_t = [], []
    for i, t in enumerate(D["transfers"]):
        if t["frm"] not in A or t["to"] not in A:
            rej_t.append(dict(transfer_id=t["id"], reason="unknown_account"))
        elif A[t["frm"]]["parent_id"] != A[t["to"]]["parent_id"]:
            rej_t.append(dict(transfer_id=t["id"], reason="different_parent"))
        elif t["frm"] in unres or t["to"] in unres:
            rej_t.append(dict(transfer_id=t["id"], reason="account_unresolved"))
        else:
            acts.append((t["date"], tf, "", i, "tr", t))
    acts.sort(key=lambda x: x[:4])
    stats = {k: dict(issued=ZERO, tin=ZERO, tout=ZERO) for k in invs}
    trace = []
    for day, _o, acct, _i, kind, obj in acts:
        if kind == "inv":
            inv = obj
            need = inv["corrected_total"]
            applied = ZERO
            for l in usable(acct, day):
                take = min(l["amount"], need - applied)
                if take <= 0:
                    break
                l["amount"] -= take
                applied += take
            due = need - applied
            paid = pay_fn(inv, due) if pay_fn else D["pays"].get(inv["invoice_id"], ZERO)
            over = paid - due
            if over > 0:
                addlot(dict(lot_id=inv["invoice_id"] + "-OP", account_id=acct, amount=over, created_on=day,
                              expires_on=mstart(madd(inv["statement_month"], ncyc), fit[acct][0])))
                stats[acct]["issued"] += over
            inv.update(credit_applied=applied, paid=paid, balance_due=max(due - paid, ZERO))
        else:
            t = obj
            avail = usable(t["frm"], day)
            want = t["req"] if V["cap"] == "replayed" else t.get("posted", t["req"])
            moved, k = ZERO, 0
            for l in avail:
                if moved >= want:
                    break
                take = min(l["amount"], want - moved)
                l["amount"] -= take
                moved += take
                k += 1
                addlot(dict(lot_id="%s-%d" % (t["id"], k), account_id=t["to"], amount=take, created_on=day,
                              expires_on=l["expires_on"]))
            if V["cap"] == "posted":
                moved = want
            trace.append((t["id"], moved))
            stats[t["frm"]]["tout"] += moved
            stats[t["to"]]["tin"] += moved
            done_t.append(dict(transfer_id=t["id"], from_account=t["frm"], to_account=t["to"],
                               date=t["date"].isoformat(), requested=s2(t["req"]), moved=s2(moved)))

    expiries, region_rows = [], {}
    for acct in sorted(invs):
        E = mstart(madd(last, 1), fit[acct][0]) - ONE_DAY
        mine = [l for l in LB.get(acct, []) if l["amount"] > 0]
        exp = sorted([l for l in mine if l["expires_on"] <= E], key=lambda l: (l["expires_on"], l["lot_id"]))
        opn = sorted([l for l in mine if l["expires_on"] > E], key=lambda l: (l["expires_on"], l["lot_id"]))
        for l in exp:
            expiries.append(dict(lot_id=l["lot_id"], account_id=acct, expires_on=l["expires_on"].isoformat(),
                                 amount=s2(l["amount"])))
        a0 = A[acct]
        region_rows[acct] = dict(
            account_id=acct, parent_id=a0["parent_id"], segment=a0["segment"], anchor_day=fit[acct][0],
            basis=fit[acct][1],
            invoices=[dict(invoice_id=i["invoice_id"], statement_month=i["statement_month"], status=i["status"],
                           original_total=s2(i["original_total"]), corrected_total=s2(i["corrected_total"]),
                           credit_applied=s2(i["credit_applied"]), paid=s2(i["paid"]),
                           balance_due=s2(i["balance_due"])) for i in invs[acct]],
            credits_issued=s2(stats[acct]["issued"]), credits_expired=s2(sum((l["amount"] for l in exp), ZERO)),
            transferred_in=s2(stats[acct]["tin"]), transferred_out=s2(stats[acct]["tout"]),
            open_lots=[dict(lot_id=l["lot_id"], amount=s2(l["amount"]), expires_on=l["expires_on"].isoformat())
                       for l in opn],
            closing_credit=s2(sum((l["amount"] for l in opn), ZERO)))

    def agg(rows):
        Dd = lambda k: sum((Decimal(r[k]) for r in rows), ZERO)
        I = lambda k: sum((Decimal(i[k]) for r in rows for i in r["invoices"]), ZERO)
        return dict(original_billed=s2(I("original_total")), corrected_billed=s2(I("corrected_total")),
                    credit_applied=s2(I("credit_applied")), balance_due=s2(I("balance_due")),
                    credits_issued=s2(Dd("credits_issued")), credits_expired=s2(Dd("credits_expired")),
                    closing_credit=s2(Dd("closing_credit")))
    out = {}
    for R in REGIONS:
        rows = [region_rows[k] for k in sorted(region_rows) if A[k]["region"] == R]
        out["region_%s.json" % R] = dict(region=R, accounts=rows, totals=agg(rows))
    for S in SEGMENTS:
        rows = [region_rows[k] for k in sorted(region_rows) if A[k]["segment"] == S]
        out["segment_%s.json" % S] = dict(segment=S, accounts_resolved=len(rows),
                                          account_ids=[r["account_id"] for r in rows], **agg(rows))
    allrows = [region_rows[k] for k in sorted(region_rows)]
    rerated = sum(1 for r in allrows for i in r["invoices"] if i["original_total"] != i["corrected_total"])
    out["summary.json"] = dict(extract_id=D["extract_id"], accounts_total=len(A), accounts_resolved=len(allrows),
                               accounts_unresolved=len(unresolved), corrections_applied=len(accepted),
                               corrections_rejected=len(rejected), invoices_rerated=rerated, **agg(allrows))
    corr_rows = [dict(correction_id=c["correction_id"], account_id=c["account_id"], item=c["item"],
                      quantity=int(c["quantity"]), effective_date=c["effective_date"],
                      first_affected_statement_month=first_aff(c))
                 for c in sorted(accepted, key=lambda c: (c["effective_date"], c["account_id"], c["arrival_seq"]))]
    out["policy_audit.json"] = dict(corrections=corr_rows, transfers=done_t,
                                    expiries=sorted(expiries, key=lambda e: (e["expires_on"], e["lot_id"])))
    out["data_quality.json"] = dict(unresolved_accounts=unresolved,
                                    rejected_corrections=sorted(rejected, key=lambda r: r["correction_id"]),
                                    rejected_transfers=sorted(rej_t, key=lambda r: r["transfer_id"]),
                                    void_invoices_ignored=sorted(void))
    return out, dict(fit=fit, unresolved=unresolved, trace=trace)


def dumps(obj):
    return json.dumps(obj, indent=2) + "\n"


def write(out, outd):
    os.makedirs(outd, exist_ok=True)
    for name, obj in out.items():
        with open(os.path.join(outd, name), "w") as f:
            f.write(dumps(obj))


def main():
    a = sys.argv
    inp, outd = a[a.index("--input") + 1], a[a.index("--output") + 1]
    out, _ = engine(parse(inp), variant(os.environ.get("KILL_VARIANT", "")))
    write(out, outd)


if __name__ == "__main__":
    main()
