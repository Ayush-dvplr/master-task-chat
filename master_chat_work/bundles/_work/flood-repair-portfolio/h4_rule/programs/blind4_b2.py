#!/usr/bin/env python3
"""Flood repair funding book report: implements data/contract.md.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""
import configparser
import csv
import io
import json
import os
import re
import sys

ROUND_FILES = ("proposals.csv", "segment_codes.tsv", "permits.csv", "exclusions.json")
RISK_CLASSES = ("A", "B", "C", "D")
PERMIT_STATUSES = ("held", "applied", "withdrawn")
REGIONS = ("North", "South", "West", "East")
SEGMENT_DOCS = ("commercial", "public")
SHARED_CAP = 4
HOUSEHOLDS_RE = re.compile(r"[0-9]+")


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    if text.startswith("\ufeff"):
        text = text[1:]
    return text


def data_rows(text, delimiter):
    """Return data rows (after header) of a CSV/TSV text, skipping empty lines,
    padded to at least the header width."""
    lines = text.splitlines()
    if not lines:
        return []
    width = len(lines[0].split(delimiter)) if delimiter == "\t" else len(next(csv.reader([lines[0]])))
    rows = []
    for line in lines[1:]:
        if line.strip() == "":
            continue
        if delimiter == "\t":
            fields = line.split("\t")
        else:
            fields = next(csv.reader([line]))
        if len(fields) < width:
            fields = fields + [""] * (width - len(fields))
        rows.append(fields)
    return rows


def popcount(x):
    return bin(x).count("1")


# ----------------------------------------------------------------------------
# Exact maximum weight independent set with shared-crew capacity groups.
# Weights are unique per subset (tie-break bits embedded), so the optimum is
# unique and equals the contract's chosen portfolio.
# ----------------------------------------------------------------------------
class Solver:
    def __init__(self, weights, adj, groups, vgroup):
        self.w = weights          # list of int
        self.adj = adj            # list of int bitmasks
        self.gm = groups          # list of int bitmasks (shared crews with > cap members)
        self.vg = vgroup          # vertex -> group index or -1
        self.exact = {}
        self.fail = {}
        self.order = sorted(range(len(weights)), key=lambda i: -weights[i])

    def normalize(self, mask, caps):
        # Apply capacities: remove members of exhausted groups, drop slack groups.
        changed = True
        while changed:
            changed = False
            for g, c in list(caps.items()):
                m = self.gm[g] & mask
                if m == 0:
                    del caps[g]
                    continue
                if c <= 0:
                    mask &= ~m
                    del caps[g]
                    changed = True
                    continue
                if popcount(m) <= c:
                    del caps[g]
        return mask, caps

    def upper_bound(self, mask):
        cliques = []
        total = 0
        w = self.w
        adj = self.adj
        for v in self.order:
            if not (mask >> v) & 1:
                continue
            placed = False
            for k in range(len(cliques)):
                if cliques[k] & ~adj[v] == 0:
                    cliques[k] |= 1 << v
                    placed = True
                    break
            if not placed:
                cliques.append(1 << v)
                total += w[v]
        return total

    def components(self, mask, caps):
        comps = []
        rest = mask
        adj = self.adj
        while rest:
            low = rest & -rest
            comp = low
            frontier = low
            while frontier:
                nxt = 0
                f = frontier
                while f:
                    b = f & -f
                    v = b.bit_length() - 1
                    nxt |= adj[v]
                    g = self.vg[v]
                    if g >= 0 and g in caps:
                        nxt |= self.gm[g]
                    f ^= b
                nxt &= mask & ~comp
                comp |= nxt
                frontier = nxt
            comps.append(comp)
            rest &= ~comp
        return comps

    def dp(self, mask):
        """Exact optimum over `mask` (no capacity groups) by bucket elimination
        with a min-fill order; tables hold only independent subsets."""
        adj = self.adj
        w = self.w
        filled = {}
        m = mask
        while m:
            b = m & -m
            v = b.bit_length() - 1
            m ^= b
            filled[v] = adj[v] & mask
        factors = []          # list of (scope_mask, table)
        const_val = 0
        const_set = 0
        remaining = mask
        while remaining:
            # min-fill choice (ties: smaller degree, then lower index)
            best = None
            for v, nb in filled.items():
                fill = 0
                t = nb
                while t:
                    ub = t & -t
                    u = ub.bit_length() - 1
                    t ^= ub
                    fill += popcount(nb & ~filled[u] & ~ub)
                key = (fill, popcount(nb), v)
                if best is None or key < best:
                    best = key
            v = best[2]
            vb = 1 << v
            nb = filled.pop(v)
            t = nb
            while t:
                ub = t & -t
                u = ub.bit_length() - 1
                t ^= ub
                filled[u] = (filled[u] | nb) & ~ub & ~vb
            remaining &= ~vb
            fs = []
            rest = []
            for f in factors:
                (fs if f[0] & vb else rest).append(f)
            scope = nb
            for f in fs:
                scope |= f[0]
            scope &= ~vb
            subsets = [0]
            t = scope
            while t:
                ub = t & -t
                u = ub.bit_length() - 1
                t ^= ub
                au = adj[u]
                subsets += [s | ub for s in subsets if not au & s]
            av = adj[v]
            wv = w[v]
            table = {}
            for s in subsets:
                v0 = 0
                c0 = 0
                for fsc, ft in fs:
                    e = ft[s & fsc]
                    v0 += e[0]
                    c0 |= e[1]
                if not av & s:
                    v1 = wv
                    c1 = vb
                    for fsc, ft in fs:
                        e = ft[(s & fsc) | vb]
                        v1 += e[0]
                        c1 |= e[1]
                    if v1 > v0:
                        v0 = v1
                        c0 = c1
                table[s] = (v0, c0)
            if scope:
                rest.append((scope, table))
            else:
                e = table[0]
                const_val += e[0]
                const_set |= e[1]
            factors = rest
        return const_val, const_set

    def solve(self, mask, caps, need):
        """Return the exact optimum (value, setmask) of the subproblem when its
        value exceeds `need`; otherwise return None (optimum <= need)."""
        mask, caps = self.normalize(mask, dict(caps))
        if mask == 0:
            return (0, 0) if need < 0 else None
        key = (mask, tuple(sorted(caps.items())))
        hit = self.exact.get(key)
        if hit is not None:
            return hit if hit[0] > need else None
        f = self.fail.get(key)
        if f is not None and f >= need:
            return None
        res = None
        if not caps:
            res = self.dp(mask)
            if res[0] <= need:
                res = None
            comps = ()
        else:
            comps = self.components(mask, caps)
        if not caps:
            pass
        elif len(comps) > 1:
            comps.sort(key=popcount)
            ubs = [self.upper_bound(c) for c in comps]
            rem = sum(ubs)
            if rem > need:
                tv = 0
                ts = 0
                ok = True
                for comp, u in zip(comps, ubs):
                    rem -= u
                    sub = {g: c for g, c in caps.items() if self.gm[g] & comp}
                    r = self.solve(comp, sub, need - tv - rem)
                    if r is None:
                        ok = False
                        break
                    tv += r[0]
                    ts |= r[1]
                if ok:
                    res = (tv, ts)
        else:
            res = self.solve_component(mask, caps, need)
        if res is None:
            if f is None or need > f:
                self.fail[key] = need
            return None
        self.exact[key] = res
        return res

    def solve_component(self, mask, caps, need):
        w = self.w
        adj = self.adj
        if mask & (mask - 1) == 0:
            v = mask.bit_length() - 1
            return (w[v], mask) if w[v] > need else None
        best_v = -1
        best_deg = -1
        m = mask
        while m:
            b = m & -m
            v = b.bit_length() - 1
            m ^= b
            nb = adj[v] & mask
            g = self.vg[v]
            free = not (g >= 0 and g in caps)
            if free:
                # simplicial rule: neighbourhood is a clique of lighter vertices
                simplicial = True
                t = nb
                while t:
                    ub_ = t & -t
                    u = ub_.bit_length() - 1
                    t ^= ub_
                    if w[u] > w[v] or (nb & ~ub_ & ~adj[u]):
                        simplicial = False
                        break
                if simplicial:
                    r = self.solve(mask & ~b & ~nb, caps, need - w[v])
                    if r is None:
                        return None
                    return (r[0] + w[v], r[1] | b)
                # domination: N[v] within N[u] and v heavier -> drop u
                cv = nb | b
                t = nb
                while t:
                    ub_ = t & -t
                    u = ub_.bit_length() - 1
                    t ^= ub_
                    if w[v] > w[u] and cv & ~((adj[u] & mask) | ub_) == 0:
                        return self.solve(mask & ~ub_, caps, need)
            deg = popcount(nb)
            if not free:
                deg += 1000
            if deg > best_deg:
                best_deg = deg
                best_v = v
        if self.upper_bound(mask) <= need:
            return None
        v = best_v
        b = 1 << v
        best = None
        cur = need
        inc_caps = dict(caps)
        g = self.vg[v]
        if g >= 0 and g in inc_caps:
            inc_caps[g] -= 1
        r = self.solve(mask & ~b & ~adj[v], inc_caps, need - w[v])
        if r is not None:
            best = (r[0] + w[v], r[1] | b)
            cur = best[0]
        r = self.solve(mask & ~b, caps, cur)
        if r is not None:
            best = r
        return best


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    sys.setrecursionlimit(100000)

    manifest = json.loads(read_text(os.path.join(data_dir, "manifest.json")))
    book = manifest.get("book")
    declared = list(manifest.get("files", []))
    for name in declared:
        if not os.path.isfile(os.path.join(data_dir, name)):
            sys.stderr.write("ERROR MISSING_FILE %s\n" % name)
            return 1

    def path(name):
        return os.path.join(data_dir, name)

    # --- shared registers ---
    sites = {}
    for line in read_text(path("sites.jsonl")).splitlines():
        if line.strip() == "":
            continue
        obj = json.loads(line)
        sites[str(obj["site"])] = obj
    regions = {}
    for r in data_rows(read_text(path("region_codes.csv")), ","):
        regions[r[0]] = r[1]
    crews = {}
    for r in data_rows(read_text(path("crews.tsv")), "\t"):
        crews[r[0]] = r[1]
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    cp.read_string(read_text(path("benefits.ini")))
    seg_rate = {k: int(v.strip()) for k, v in cp.items("segment_rate")} if cp.has_section("segment_rate") else {}
    risk_uplift = {k: int(v.strip()) for k, v in cp.items("risk_uplift")} if cp.has_section("risk_uplift") else {}

    # --- round-scoped files, with whole-file row numbers ---
    per_file = {}
    prop_rows = []
    for i, r in enumerate(data_rows(read_text(path("proposals.csv")), ","), 1):
        prop_rows.append((i, r))
    seg_rows = []
    for i, r in enumerate(data_rows(read_text(path("segment_codes.tsv")), "\t"), 1):
        seg_rows.append((i, r))
    permit_rows = []
    for i, r in enumerate(data_rows(read_text(path("permits.csv")), ","), 1):
        permit_rows.append((i, r))
    excl_rows = []
    for i, e in enumerate(json.loads(read_text(path("exclusions.json"))), 1):
        excl_rows.append((i, e))

    def group_by_round(rows, getter):
        out = {}
        for i, r in rows:
            out.setdefault(getter(r), []).append((i, r))
        return out

    props_by = group_by_round(prop_rows, lambda r: r[0])
    segs_by = group_by_round(seg_rows, lambda r: r[0])
    permits_by = group_by_round(permit_rows, lambda r: r[0])
    excl_by = group_by_round(excl_rows, lambda e: str(e.get("round")))
    per_file = {
        "proposals.csv": props_by,
        "segment_codes.tsv": segs_by,
        "permits.csv": permits_by,
        "exclusions.json": excl_by,
    }
    order = [n for n in declared if n in ROUND_FILES]
    for n in ROUND_FILES:
        if n not in order:
            order.append(n)

    round_ids = sorted(props_by.keys())
    results = {}

    for rid in round_ids:
        prows = props_by.get(rid, [])
        prop_ids = set(r[1] for _, r in prows)
        prop_sites = set(r[2] for _, r in prows)
        fault = None
        for fname in order:
            seen = set()
            for i, r in per_file[fname].get(rid, []):
                code = None
                if fname == "proposals.csv":
                    if r[1] in seen:
                        code = "DUPLICATE_PROPOSAL"
                    else:
                        hh = r[4]
                        if not (HOUSEHOLDS_RE.fullmatch(hh) and 1 <= int(hh) <= 60):
                            code = "INVALID_INPUT"
                        elif r[2] not in sites:
                            code = "INVALID_INPUT"
                        elif r[3] not in crews:
                            code = "INVALID_INPUT"
                        elif r[5] != "" and r[5] not in RISK_CLASSES:
                            code = "INVALID_INPUT"
                    seen.add(r[1])
                elif fname == "segment_codes.tsv":
                    if r[1] not in prop_ids:
                        code = "UNKNOWN_PROPOSAL"
                    elif r[2] not in seg_rate:
                        code = "INVALID_INPUT"
                elif fname == "permits.csv":
                    if r[2] not in prop_ids:
                        code = "UNKNOWN_PROPOSAL"
                    elif r[3] not in PERMIT_STATUSES:
                        code = "INVALID_INPUT"
                else:
                    a = str(r.get("first"))
                    b = str(r.get("second"))
                    if (a not in prop_ids and a not in prop_sites) or (b not in prop_ids and b not in prop_sites):
                        code = "UNKNOWN_PROPOSAL"
                    elif a == b:
                        code = "INVALID_INPUT"
                if code is not None:
                    fault = {"round": rid, "code": code, "file": fname, "row": i}
                    break
            if fault:
                break
        if fault:
            results[rid] = {"status": "rejected", "fault": fault, "nrows": len(prows)}
            continue

        # valuing
        segment_of = {}
        for _, r in segs_by.get(rid, []):
            segment_of[r[1]] = r[2]
        info = {}
        for i, r in prows:
            pid, site, crew, hh, ovr = r[1], r[2], r[3], int(r[4]), r[5]
            seg = segment_of.get(pid)
            rate = seg_rate.get(seg, 0)
            rc = ovr if ovr != "" else str(sites[site].get("risk_class"))
            up = risk_uplift.get(rc, 0)
            prem = int(sites[site].get("premium"))
            benefit = hh * (rate + up) + prem
            info[pid] = {
                "row": i, "site": site, "crew": crew, "households": hh,
                "segment": seg, "segment_rate": rate, "risk_class": rc,
                "risk_uplift": up, "premium": prem, "benefit": benefit,
            }
        bad = None
        for i, r in prows:
            if info[r[1]]["benefit"] < 1:
                bad = i
                break
        if bad is not None:
            results[rid] = {"status": "rejected", "nrows": len(prows),
                            "fault": {"round": rid, "code": "NONPOSITIVE_BENEFIT",
                                      "file": "proposals.csv", "row": bad}}
            continue

        # conflicts
        ids = sorted(info.keys())
        idx = {p: k for k, p in enumerate(ids)}
        n = len(ids)

        def pair(x, y):
            return (x, y) if x < y else (y, x)

        crew_pairs = set()
        by_crew = {}
        for p in ids:
            by_crew.setdefault(info[p]["crew"], []).append(p)
        for c, members in by_crew.items():
            if crews.get(c) == "exclusive":
                for a in range(len(members)):
                    for b in range(a + 1, len(members)):
                        crew_pairs.add(pair(members[a], members[b]))
        permit_pairs = set()
        withdrawn = 0
        by_permit = {}
        for _, r in permits_by.get(rid, []):
            if r[3] == "withdrawn":
                withdrawn += 1
                continue
            lst = by_permit.setdefault(r[1], [])
            if r[2] not in lst:
                lst.append(r[2])
        for members in by_permit.values():
            for a in range(len(members)):
                for b in range(a + 1, len(members)):
                    if members[a] != members[b]:
                        permit_pairs.add(pair(members[a], members[b]))
        by_site = {}
        for p in ids:
            by_site.setdefault(info[p]["site"], []).append(p)

        def expand(name):
            if name in info:
                return [name]
            return by_site.get(name, [])

        excl_pairs = set()
        for _, e in excl_by.get(rid, []):
            for x in expand(str(e.get("first"))):
                for y in expand(str(e.get("second"))):
                    if x != y:
                        excl_pairs.add(pair(x, y))
        all_pairs = crew_pairs | permit_pairs | excl_pairs

        adj = [0] * n
        for x, y in all_pairs:
            adj[idx[x]] |= 1 << idx[y]
            adj[idx[y]] |= 1 << idx[x]
        groups = []
        vgroup = [-1] * n
        for c, members in sorted(by_crew.items()):
            if crews.get(c) == "shared" and len(members) > SHARED_CAP:
                gmask = 0
                for p in members:
                    gmask |= 1 << idx[p]
                    vgroup[idx[p]] = len(groups)
                groups.append(gmask)
        weights = [(info[p]["benefit"] << n) | (1 << (n - 1 - k)) for k, p in enumerate(ids)]
        solver = Solver(weights, adj, groups, vgroup)
        caps = {g: SHARED_CAP for g in range(len(groups))}
        _, sel = solver.solve((1 << n) - 1, caps, -1)
        selected = [ids[k] for k in range(n) if (sel >> k) & 1]
        total = sum(info[p]["benefit"] for p in selected)
        results[rid] = {
            "status": "planned", "nrows": len(prows), "info": info,
            "selected": selected, "selset": set(selected), "total": total,
            "crew_pairs": crew_pairs, "permit_pairs": permit_pairs,
            "excl_pairs": excl_pairs, "all_pairs": all_pairs, "withdrawn": withdrawn,
        }

    # --- summary ---
    rounds_out = []
    for rid in round_ids:
        res = results[rid]
        if res["status"] == "planned":
            rounds_out.append({"round": rid, "status": "planned", "proposals": res["nrows"],
                               "selected": res["selected"], "total_benefit": res["total"]})
        else:
            rounds_out.append({"round": rid, "status": "rejected", "proposals": res["nrows"],
                               "selected": [], "total_benefit": 0})
    planned = [rid for rid in round_ids if results[rid]["status"] == "planned"]
    rejected = [rid for rid in round_ids if results[rid]["status"] == "rejected"]
    summary = {
        "book": book,
        "rounds": rounds_out,
        "planned_rounds": len(planned),
        "rejected_rounds": len(rejected),
        "selected_proposals": sum(len(r["selected"]) for r in rounds_out),
        "total_benefit": sum(r["total_benefit"] for r in rounds_out),
    }

    # --- policy audit ---
    audit_rows = []
    lines = read_text(path("audit_queries.txt")).splitlines()
    for ln, line in enumerate(lines, 1):
        if line.strip() == "":
            continue
        parts = line.split()
        kind = parts[0]
        rid = parts[1] if len(parts) > 1 else ""
        res = results.get(rid)
        status = res["status"] if res else "rejected"
        row = {"line": ln, "kind": kind, "round": rid, "status": status}
        if res and status == "planned":
            info = res["info"]
            if kind == "VALUE":
                p = parts[2]
                d = info[p]
                row.update({
                    "proposal": p, "segment": d["segment"], "segment_rate": d["segment_rate"],
                    "risk_class": d["risk_class"], "risk_uplift": d["risk_uplift"],
                    "households": d["households"], "premium": d["premium"],
                    "benefit": d["benefit"], "selected": p in res["selset"],
                })
            elif kind == "PAIR":
                a, b = parts[2], parts[3]
                pr = (a, b) if a < b else (b, a)
                sources = []
                if a != b:
                    if pr in res["crew_pairs"]:
                        sources.append("crew")
                    if pr in res["permit_pairs"]:
                        sources.append("permit")
                    if pr in res["excl_pairs"]:
                        sources.append("exclusion")
                row.update({
                    "first": a, "second": b, "sources": sources, "conflict": bool(sources),
                    "first_selected": a in res["selset"], "second_selected": b in res["selset"],
                })
        audit_rows.append(row)
    policy = {"book": book, "rows": audit_rows}

    # --- data quality ---
    dq = {
        "book": book,
        "rejected": [results[rid]["fault"] for rid in rejected],
        "planned_rounds": len(planned),
        "rejected_rounds": len(rejected),
        "conflict_pairs": sum(len(results[rid]["all_pairs"]) for rid in planned),
        "conflicts_by_source": {
            "crew": sum(len(results[rid]["crew_pairs"]) for rid in planned),
            "permit": sum(len(results[rid]["permit_pairs"]) for rid in planned),
            "exclusion": sum(len(results[rid]["excl_pairs"]) for rid in planned),
        },
        "withdrawn_permit_rows": sum(results[rid]["withdrawn"] for rid in planned),
    }

    docs = {"summary.json": summary, "policy_audit.json": policy, "data_quality.json": dq}

    def slice_doc(key, value, pred):
        rr = []
        for rid in planned:
            res = results[rid]
            sel = [p for p in res["selected"] if pred(res["info"][p])]
            rr.append({"round": rid, "selected": sel,
                       "benefit": sum(res["info"][p]["benefit"] for p in sel)})
        return {"book": book, key: value, "rounds": rr,
                "selected_proposals": sum(len(r["selected"]) for r in rr),
                "total_benefit": sum(r["benefit"] for r in rr)}

    for reg in REGIONS:
        docs["region_%s.json" % reg] = slice_doc(
            "region", reg, lambda d, reg=reg: regions.get(d["site"]) == reg)
    for seg in SEGMENT_DOCS:
        docs["segment_%s.json" % seg] = slice_doc(
            "segment", seg, lambda d, seg=seg: d["segment"] == seg)

    os.makedirs(out_dir, exist_ok=True)
    for name, doc in docs.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
