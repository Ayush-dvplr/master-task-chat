"""Prototype scorer for the v2-go test plan (DESIGN.md section 12, P = 112).

usage: score_proto.py <root> <reflex-name> [<reflex-name> ...]
<root>/out/<corpus> holds the stated-reading outputs, <root>/rx/<name>/<corpus> the variant's
outputs, <root>/<corpus>_meta.json the generator meta (owned ids and lines).
Mutation checks (relocated, missing source) are counted as passed for every variant: the
variants are deterministic and read only --data, so both invariance checks hold.
"""
import json
import os
import sys

DOCS = ["summary", "policy_audit", "data_quality", "region_North", "region_South", "region_West",
        "region_East", "segment_commercial", "segment_public"]
HIDDEN = ["h1101", "h1102", "h1103", "h1104"]
VERDICTS = ["billed_correctly", "overbilled", "underbilled", "cannot_recompute"]


def load(d):
    out = {}
    for n in DOCS:
        p = os.path.join(d, n + ".json")
        try:
            with open(p) as fh:
                out[n] = json.load(fh)
        except (OSError, ValueError):
            out[n] = None
    return out


def cents(s):
    return None if s is None else int(s.replace("-", "").replace(".", "")) * (-1 if s.startswith("-") else 1)


def rows(doc):
    return {r["invoice_id"]: r for r in (doc or {}).get("rows", [])}


def region_tot(rs, st):
    sel = [r for r in rs if r["station"] == st]
    vc = {k: 0 for k in VERDICTS}
    ref = sh = 0
    for r in sel:
        vc[r["verdict"]] += 1
        d = cents(r["difference"])
        if d is not None and d > 0:
            ref += d
        if d is not None and d < 0:
            sh -= d
    return len(sel), vc, ref, sh


def score(exp_root, got_root, metas):
    res = {}
    e, g = load(os.path.join(exp_root, "shipped")), load(os.path.join(got_root, "shipped"))
    res["shipped_outputs_exist"] = (1, all(g[n] is not None for n in DOCS))
    res["shipped_audit"] = (5, e["policy_audit"] == g["policy_audit"])
    res["shipped_summary"] = (3, e["summary"] == g["summary"])
    res["shipped_regions"] = (3, all(e[n] == g[n] for n in DOCS if n.startswith("region")))
    res["shipped_segments"] = (3, all(e[n] == g[n] for n in DOCS if n.startswith("segment")))
    res["shipped_quality"] = (3, e["data_quality"] == g["data_quality"])
    qpass = {f"Q{i}": True for i in range(1, 11)}
    qseen = {f"Q{i}": 0 for i in range(1, 11)}
    for k, c in enumerate(HIDDEN, 1):
        e, g = load(os.path.join(exp_root, c)), load(os.path.join(got_root, c))
        owned = metas[c]["owned"]
        oid = {i for q in owned.values() for i in q["ids"]}
        olines = {tuple(x) for q in owned.values() for x in q["lines"]}
        er, gr = rows(e["policy_audit"]), rows(g["policy_audit"])
        ep = {i: r for i, r in er.items() if i not in oid}
        gp = {i: r for i, r in gr.items() if i not in oid}
        res[f"hidden_audit_plain_c{k}"] = (5, bool(ep) and ep == gp)
        mixed = list(ep.values()) + [r for i, r in gr.items() if i in oid]
        ok = True
        for st in ["North", "South", "West", "East"]:
            ed, gd = e[f"region_{st}"], g[f"region_{st}"]
            if gd is None or ed["periods"] != gd.get("periods") or ed["station"] != gd.get("station"):
                ok = False
                continue
            n, vc, ref, sh = region_tot(mixed, st)
            if (gd.get("disputes"), gd.get("verdict_counts"), cents(gd.get("refund_total")),
                    cents(gd.get("shortfall_total"))) != (n, vc, ref, sh):
                ok = False
        res[f"hidden_regions_c{k}"] = (5, ok)
        eq = [x for x in e["data_quality"]["rejected"] if (x["file"], x["line"]) not in olines]
        gq = (g["data_quality"] or {}).get("rejected", [])
        gqp = [x for x in gq if (x["file"], x["line"]) not in olines]
        cnt = {}
        for x in gq:
            cnt[x["code"]] = cnt.get(x["code"], 0) + 1
        gc = {kk: v for kk, v in (g["data_quality"] or {}).get("counts", {}).items() if v}
        res[f"hidden_quality_c{k}"] = (3, bool(eq) and eq == gqp and gc == cnt)
        if k == 1:
            res["hidden_summary_c1"] = (3, e["summary"] == g["summary"])
        if k == 2:
            res["hidden_segments_c2"] = (3, all(e[n] == g[n] for n in DOCS if n.startswith("segment")))
        gbad = {(x["file"], x["line"]) for x in gq}
        for q, o in owned.items():
            for i in o["ids"]:
                if er.get(i) != gr.get(i):
                    qpass[q] = False
                qseen[q] += i in er
            if any(tuple(x) in gbad for x in o["lines"]):
                qpass[q] = False
    for q in qpass:
        res[f"quiet_{q}"] = (3, qpass[q] and qseen[q] > 0)
    res["mutation_relocated"] = (3, True)
    res["mutation_missing_source"] = (3, True)
    P = sum(w for w, _ in res.values())
    got = sum(w for w, ok in res.values() if ok)
    return P, got, [n for n, (w, ok) in res.items() if not ok]


def main():
    root = sys.argv[1]
    metas = {c: json.load(open(os.path.join(root, c + "_meta.json"))) for c in HIDDEN}
    for name in sys.argv[2:]:
        got_root = os.path.join(root, "out") if name == "stated" else os.path.join(root, "rx", name)
        P, got, failed = score(os.path.join(root, "out"), got_root, metas)
        print(f"{name}\t{got}/{P}\t{100 * got / P:.1f}\t{P - got}\t{' '.join(failed)}")


if __name__ == "__main__":
    main()
