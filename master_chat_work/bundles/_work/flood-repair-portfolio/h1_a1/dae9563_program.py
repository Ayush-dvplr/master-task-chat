#!/usr/bin/env python3
"""Flood repair funding book report: implements contract.md.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""
import configparser
import csv
import io
import json
import os
import re
import sys
from collections import defaultdict

ROUND_FILES = ("proposals.csv", "segment_codes.tsv", "permits.csv", "exclusions.json")
REGIONS = ("North", "South", "West", "East")
SEGMENT_DOCS = ("commercial", "public")
RISK = ("A", "B", "C", "D")
STATUSES = ("held", "applied", "withdrawn")
DIGITS = re.compile(r"[0-9]+")


def read_text(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return fh.read()


def read_table(path, delim):
    """Return list of dicts (header -> value) for the data rows, in file order.

    Data rows are the non-empty lines after the header; row numbers are the
    1-based index in the returned list.
    """
    lines = read_text(path).splitlines()
    if not lines:
        return []
    header = next(csv.reader([lines[0]], delimiter=delim))
    header = [h.strip() for h in header]
    data_lines = [ln for ln in lines[1:] if ln.strip() != ""]
    rows = []
    if delim == "\t":
        parsed = [ln.split("\t") for ln in data_lines]
    else:
        parsed = list(csv.reader(io.StringIO("\n".join(data_lines) + "\n"), delimiter=delim))
        if len(parsed) != len(data_lines):
            parsed = [next(csv.reader([ln], delimiter=delim), []) for ln in data_lines]
    for fields in parsed:
        row = {}
        for i, h in enumerate(header):
            row[h] = fields[i] if i < len(fields) else ""
        rows.append(row)
    return rows


def popcount(x):
    return bin(x).count("1")


def bits(x):
    while x:
        low = x & -x
        yield low.bit_length() - 1
        x ^= low


class MWIS:
    """Exact maximum weight independent set; weights are distinct so the optimum is unique.

    Memoised branch and reduce: reductions (isolated vertex, neighbourhood
    weight, domination), connected-component splitting, and branching on
    vertices in reverse min-degree elimination order so that the search
    follows a tree decomposition of the conflict graph.
    """

    def __init__(self, n, adj, weight):
        self.n = n
        self.adj = adj
        self.w = weight
        self.memo = {}
        nbr = [set(bits(a)) for a in adj]
        alive = set(range(n))
        self.rank = [0] * n
        k = 0
        while alive:
            v = min(alive, key=lambda x: (len(nbr[x]), x))
            nb = nbr[v]
            for a in nb:
                nbr[a] |= nb
                nbr[a].discard(a)
                nbr[a].discard(v)
            alive.discard(v)
            self.rank[v] = k
            k += 1

    def components(self, mask):
        adj = self.adj
        comps = []
        rest = mask
        while rest:
            low = rest & -rest
            reach = low
            frontier = low
            while frontier:
                nb = 0
                for v in bits(frontier):
                    nb |= adj[v]
                nb &= rest & ~reach
                reach |= nb
                frontier = nb
            comps.append(reach)
            rest &= ~reach
        return comps

    def reduce(self, mask):
        adj = self.adj
        w = self.w
        taken = 0
        tw = 0
        changed = True
        while changed:
            changed = False
            for v in bits(mask):
                if not (mask >> v) & 1:
                    continue
                nv = adj[v] & mask
                if nv == 0:
                    taken |= 1 << v
                    tw += w[v]
                    mask &= ~(1 << v)
                    changed = True
                    continue
                wv = w[v]
                sw = 0
                for u in bits(nv):
                    sw += w[u]
                if wv > sw:
                    # heavier than its whole neighbourhood: v is in the optimum
                    taken |= 1 << v
                    tw += wv
                    mask &= ~(nv | (1 << v))
                    changed = True
                    continue
                cv = nv | (1 << v)
                for u in bits(nv):
                    if w[u] > wv and ((adj[u] & mask) | (1 << u)) & ~cv == 0:
                        # N[u] subset of N[v] and u heavier: v is not in the optimum
                        mask &= ~(1 << v)
                        changed = True
                        break
        return mask, taken, tw

    def solve(self, mask):
        """Return (weight, set_mask) of the optimum independent set inside mask."""
        if mask == 0:
            return (0, 0)
        r = self.memo.get(mask)
        if r is not None:
            return r
        m, taken, tw = self.reduce(mask)
        if m != mask:
            sub = self.solve(m)
            r = (sub[0] + tw, sub[1] | taken)
        else:
            comps = self.components(m)
            if len(comps) > 1:
                tot = 0
                sel = 0
                for c in comps:
                    sub = self.solve(c)
                    tot += sub[0]
                    sel |= sub[1]
                r = (tot, sel)
            else:
                rank = self.rank
                v = max(bits(m), key=lambda x: rank[x])
                inc = self.solve(m & ~(self.adj[v] | (1 << v)))
                inc = (inc[0] + self.w[v], inc[1] | (1 << v))
                exc = self.solve(m & ~(1 << v))
                r = inc if inc[0] > exc[0] else exc
        self.memo[mask] = r
        return r


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    sys.setrecursionlimit(100000)

    man_path = os.path.join(data_dir, "manifest.json")
    if not os.path.isfile(man_path):
        sys.stderr.write("ERROR MISSING_FILE manifest.json\n")
        return 1
    manifest = json.loads(read_text(man_path))
    book = manifest.get("book")
    declared = list(manifest.get("files", []))
    for name in declared:
        if not os.path.isfile(os.path.join(data_dir, name)):
            sys.stderr.write("ERROR MISSING_FILE %s\n" % name)
            return 1

    def path(name):
        return os.path.join(data_dir, name)

    proposals = read_table(path("proposals.csv"), ",")
    segments = read_table(path("segment_codes.tsv"), "\t")
    permits = read_table(path("permits.csv"), ",")
    exclusions = json.loads(read_text(path("exclusions.json")))
    if not isinstance(exclusions, list):
        exclusions = []
    crews_rows = read_table(path("crews.tsv"), "\t")
    regions_rows = read_table(path("region_codes.csv"), ",")

    sites = {}
    for ln in read_text(path("sites.jsonl")).splitlines():
        if ln.strip() == "":
            continue
        obj = json.loads(ln)
        s = obj.get("site")
        if isinstance(s, str) and s not in sites:
            sites[s] = obj

    crews = {}
    for r in crews_rows:
        if r.get("crew") not in crews:
            crews[r.get("crew")] = r.get("mode")

    site_region = {}
    for r in regions_rows:
        if r.get("site") not in site_region:
            site_region[r.get("site")] = r.get("region")

    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read_string(read_text(path("benefits.ini")))
    seg_rate = {}
    if cp.has_section("segment_rate"):
        for k, v in cp.items("segment_rate"):
            seg_rate[k] = int(v.strip())
    risk_uplift = {}
    if cp.has_section("risk_uplift"):
        for k, v in cp.items("risk_uplift"):
            risk_uplift[k] = int(v.strip())

    # group rows per round, keeping file row numbers
    rounds = []
    prop_by_round = defaultdict(list)
    for i, r in enumerate(proposals, 1):
        rd = r.get("round")
        if rd not in prop_by_round:
            rounds.append(rd)
        prop_by_round[rd].append((i, r))
    round_set = set(prop_by_round)
    seg_by_round = defaultdict(list)
    for i, r in enumerate(segments, 1):
        if r.get("round") in round_set:
            seg_by_round[r.get("round")].append((i, r))
    perm_by_round = defaultdict(list)
    for i, r in enumerate(permits, 1):
        if r.get("round") in round_set:
            perm_by_round[r.get("round")].append((i, r))
    excl_by_round = defaultdict(list)
    for i, e in enumerate(exclusions, 1):
        if isinstance(e, dict) and isinstance(e.get("round"), str) and e.get("round") in round_set:
            excl_by_round[e["round"]].append((i, e))

    order = [f for f in declared if f in ROUND_FILES]
    for f in ROUND_FILES:
        if f not in order:
            order.append(f)

    results = {}
    for rd in sorted(round_set):
        prows = prop_by_round[rd]
        ids = set(r.get("proposal") for _, r in prows)
        site_props = defaultdict(set)
        for _, r in prows:
            site_props[r.get("site")].add(r.get("proposal"))

        def names(x):
            out = set()
            if x in ids:
                out.add(x)
            if x in site_props:
                out |= site_props[x]
            return out

        fault = None
        for fname in order:
            if fault:
                break
            if fname == "proposals.csv":
                seen = set()
                for i, r in prows:
                    p = r.get("proposal")
                    if p in seen:
                        fault = ("DUPLICATE_PROPOSAL", fname, i)
                        break
                    seen.add(p)
                    hh = r.get("households", "")
                    ro = r.get("risk_override", "")
                    if (not DIGITS.fullmatch(hh) or not (1 <= int(hh) <= 60)
                            or r.get("site") not in sites
                            or r.get("crew") not in crews
                            or (ro != "" and ro not in RISK)):
                        fault = ("INVALID_INPUT", fname, i)
                        break
            elif fname == "segment_codes.tsv":
                for i, r in seg_by_round[rd]:
                    if r.get("proposal") not in ids:
                        fault = ("UNKNOWN_PROPOSAL", fname, i)
                        break
                    if r.get("segment") not in seg_rate:
                        fault = ("INVALID_INPUT", fname, i)
                        break
            elif fname == "permits.csv":
                for i, r in perm_by_round[rd]:
                    if r.get("proposal") not in ids:
                        fault = ("UNKNOWN_PROPOSAL", fname, i)
                        break
                    if r.get("status") not in STATUSES:
                        fault = ("INVALID_INPUT", fname, i)
                        break
            elif fname == "exclusions.json":
                for i, e in excl_by_round[rd]:
                    a, b = e.get("first"), e.get("second")
                    if not names(a) or not names(b):
                        fault = ("UNKNOWN_PROPOSAL", fname, i)
                        break
                    if a == b:
                        fault = ("INVALID_INPUT", fname, i)
                        break

        info = {"round": rd, "proposals": len(prows), "fault": fault}
        results[rd] = info
        if fault:
            continue

        seg_of = {}
        for _, r in seg_by_round[rd]:
            seg_of.setdefault(r.get("proposal"), r.get("segment"))
        pinfo = {}
        bad_row = None
        for i, r in prows:
            p = r.get("proposal")
            site = sites[r.get("site")]
            rc = r.get("risk_override") or site.get("risk_class")
            seg = seg_of.get(p)
            hh = int(r.get("households"))
            rate = seg_rate.get(seg, 0)
            upl = risk_uplift.get(rc, 0)
            prem = int(site.get("premium", 0))
            ben = hh * (rate + upl) + prem
            pinfo[p] = {
                "segment": seg, "segment_rate": rate, "risk_class": rc,
                "risk_uplift": upl, "households": hh, "premium": prem,
                "benefit": ben, "site": r.get("site"), "crew": r.get("crew"),
            }
            if ben < 1 and bad_row is None:
                bad_row = i
        if bad_row is not None:
            info["fault"] = ("NONPOSITIVE_BENEFIT", "proposals.csv", bad_row)
            continue

        # conflicts
        def pair(a, b):
            return (a, b) if a < b else (b, a)

        crew_e, permit_e, excl_e = set(), set(), set()
        crew_groups = defaultdict(list)
        for _, r in prows:
            if crews.get(r.get("crew")) == "exclusive":
                crew_groups[r.get("crew")].append(r.get("proposal"))
        for g in crew_groups.values():
            for x in range(len(g)):
                for y in range(x + 1, len(g)):
                    if g[x] != g[y]:
                        crew_e.add(pair(g[x], g[y]))
        permit_groups = defaultdict(set)
        withdrawn = 0
        for _, r in perm_by_round[rd]:
            st = r.get("status")
            if st == "withdrawn":
                withdrawn += 1
            elif st in ("held", "applied"):
                permit_groups[r.get("permit")].add(r.get("proposal"))
        for g in permit_groups.values():
            g = sorted(g)
            for x in range(len(g)):
                for y in range(x + 1, len(g)):
                    permit_e.add((g[x], g[y]))
        for _, e in excl_by_round[rd]:
            for a in names(e.get("first")):
                for b in names(e.get("second")):
                    if a != b:
                        excl_e.add(pair(a, b))
        all_e = crew_e | permit_e | excl_e

        # planning: exact MWIS with tie-break encoded in weights
        order_ids = sorted(ids)
        n = len(order_ids)
        idx = {p: k for k, p in enumerate(order_ids)}
        weight = [(pinfo[p]["benefit"] << n) | (1 << (n - 1 - k)) for k, p in enumerate(order_ids)]
        adj = [0] * n
        for a, b in all_e:
            ia, ib = idx[a], idx[b]
            adj[ia] |= 1 << ib
            adj[ib] |= 1 << ia
        solver = MWIS(n, adj, weight)
        res = solver.solve((1 << n) - 1)
        chosen = sorted(order_ids[k] for k in bits(res[1]))
        total = sum(pinfo[p]["benefit"] for p in chosen)

        info.update({
            "pinfo": pinfo, "selected": chosen, "selset": set(chosen), "total": total,
            "crew_e": crew_e, "permit_e": permit_e, "excl_e": excl_e, "all_e": all_e,
            "withdrawn": withdrawn,
        })

    rids = sorted(round_set)
    planned = [rd for rd in rids if not results[rd]["fault"]]
    rejected = [rd for rd in rids if results[rd]["fault"]]

    summary_rounds = []
    for rd in rids:
        r = results[rd]
        if r["fault"]:
            summary_rounds.append({"round": rd, "status": "rejected", "proposals": r["proposals"],
                                   "selected": [], "total_benefit": 0})
        else:
            summary_rounds.append({"round": rd, "status": "planned", "proposals": r["proposals"],
                                   "selected": r["selected"], "total_benefit": r["total"]})
    summary = {
        "book": book,
        "rounds": summary_rounds,
        "planned_rounds": len(planned),
        "rejected_rounds": len(rejected),
        "selected_proposals": sum(len(x["selected"]) for x in summary_rounds),
        "total_benefit": sum(x["total_benefit"] for x in summary_rounds),
    }

    audit_rows = []
    qlines = read_text(path("audit_queries.txt")).splitlines()
    for ln_no, ln in enumerate(qlines, 1):
        if ln.strip() == "":
            continue
        parts = ln.split()
        kind = parts[0]
        rd = parts[1] if len(parts) > 1 else None
        r = results.get(rd)
        status = "rejected" if (r is None or r["fault"]) else "planned"
        row = {"line": ln_no, "kind": kind, "round": rd, "status": status}
        if status == "planned":
            if kind == "VALUE":
                p = parts[2]
                pi = r["pinfo"][p]
                row.update({
                    "proposal": p, "segment": pi["segment"], "segment_rate": pi["segment_rate"],
                    "risk_class": pi["risk_class"], "risk_uplift": pi["risk_uplift"],
                    "households": pi["households"], "premium": pi["premium"],
                    "benefit": pi["benefit"], "selected": p in r["selset"],
                })
            elif kind == "PAIR":
                a, b = parts[2], parts[3]
                sources = []
                if a != b:
                    pr = (a, b) if a < b else (b, a)
                    if pr in r["crew_e"]:
                        sources.append("crew")
                    if pr in r["permit_e"]:
                        sources.append("permit")
                    if pr in r["excl_e"]:
                        sources.append("exclusion")
                row.update({
                    "first": a, "second": b, "sources": sources, "conflict": bool(sources),
                    "first_selected": a in r["selset"], "second_selected": b in r["selset"],
                })
        audit_rows.append(row)
    policy_audit = {"book": book, "rows": audit_rows}

    rej_list = []
    for rd in rejected:
        code, fname, row = results[rd]["fault"]
        rej_list.append({"round": rd, "code": code, "file": fname, "row": row})
    data_quality = {
        "book": book,
        "rejected": rej_list,
        "planned_rounds": len(planned),
        "rejected_rounds": len(rejected),
        "conflict_pairs": sum(len(results[rd]["all_e"]) for rd in planned),
        "conflicts_by_source": {
            "crew": sum(len(results[rd]["crew_e"]) for rd in planned),
            "permit": sum(len(results[rd]["permit_e"]) for rd in planned),
            "exclusion": sum(len(results[rd]["excl_e"]) for rd in planned),
        },
        "withdrawn_permit_rows": sum(results[rd]["withdrawn"] for rd in planned),
    }

    def breakdown(key, value, pred):
        rows = []
        for rd in planned:
            r = results[rd]
            sel = [p for p in r["selected"] if pred(r["pinfo"][p])]
            rows.append({"round": rd, "selected": sel,
                         "benefit": sum(r["pinfo"][p]["benefit"] for p in sel)})
        return {"book": book, key: value, "rounds": rows,
                "selected_proposals": sum(len(x["selected"]) for x in rows),
                "total_benefit": sum(x["benefit"] for x in rows)}

    docs = {
        "summary.json": summary,
        "policy_audit.json": policy_audit,
        "data_quality.json": data_quality,
    }
    for reg in REGIONS:
        docs["region_%s.json" % reg] = breakdown(
            "region", reg, lambda pi, reg=reg: site_region.get(pi["site"]) == reg)
    for seg in SEGMENT_DOCS:
        docs["segment_%s.json" % seg] = breakdown(
            "segment", seg, lambda pi, seg=seg: pi["segment"] == seg)

    os.makedirs(out_dir, exist_ok=True)
    for name, doc in docs.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
