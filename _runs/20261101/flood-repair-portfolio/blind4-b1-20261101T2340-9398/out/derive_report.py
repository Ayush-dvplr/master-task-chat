#!/usr/bin/env python3
"""Flood repair funding book report: python3 derive_report.py DATA_DIR OUT_DIR"""
import json
import os
import re
import sys
from collections import defaultdict

STD_FILES = ["proposals.csv", "segment_codes.tsv", "sites.jsonl", "region_codes.csv",
             "crews.tsv", "permits.csv", "exclusions.json", "benefits.ini", "audit_queries.txt"]
ROUND_FILES = ["proposals.csv", "segment_codes.tsv", "permits.csv", "exclusions.json"]
REGIONS = ["North", "South", "West", "East"]
SEGMENTS = ["commercial", "public"]
RISK = ("A", "B", "C", "D")
DIGITS = re.compile(r"[0-9]+\Z")
SHARED_CAP = 4


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def read_table(path, sep):
    """Return list of (row_number, fields) for data rows (non-empty lines after header)."""
    lines = read_text(path).splitlines()
    rows = []
    n = 0
    for line in lines[1:]:
        if line.strip() == "":
            continue
        n += 1
        rows.append((n, line.split(sep)))
    return rows


def field(fields, i):
    return fields[i] if i < len(fields) else ""


def as_id(x):
    if isinstance(x, str):
        return x
    if x is None:
        return ""
    return str(x)


def read_ini(path):
    sections = defaultdict(dict)
    cur = None
    for line in read_text(path).splitlines():
        s = line.strip()
        if not s or s.startswith(";") or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1].strip()
            continue
        if cur is None:
            continue
        if "=" in s:
            k, v = s.split("=", 1)
        elif ":" in s:
            k, v = s.split(":", 1)
        else:
            continue
        sections[cur][k.strip()] = int(v.strip())
    return sections


def popcount(m):
    return bin(m).count("1")


# ---------------------------------------------------------------------------
# Exact max-weight portfolio solver (independent set + shared crew capacity)
# ---------------------------------------------------------------------------

def solve_portfolio(n, W, adj, crew_masks, crew_of):
    """W: big-int weights (unique optimum), adj: bitmask adjacency,
    crew_masks: member masks of shared crews with more than SHARED_CAP members,
    crew_of: index into crew_masks or -1. Returns chosen bitmask."""
    k = len(crew_masks)
    order = sorted(range(n), key=lambda i: -W[i])
    memo = {}
    upper = {}

    def components(S, rel):
        comps = []
        rem = S
        while rem:
            seed = rem & -rem
            comp = seed
            frontier = seed
            while frontier:
                nb = 0
                f = frontier
                while f:
                    b = f & -f
                    i = b.bit_length() - 1
                    f ^= b
                    nb |= adj[i]
                    j = crew_of[i]
                    if j >= 0 and (rel >> j) & 1:
                        nb |= crew_masks[j]
                nb &= rem & ~comp
                comp |= nb
                frontier = nb
            comps.append(comp)
            rem &= ~comp
        return comps

    def clique_bound(S):
        cl = []
        ub = 0
        for v in order:
            if not (S >> v) & 1:
                continue
            for idx in range(len(cl)):
                c = cl[idx]
                if (c >> v) & 1:
                    cl[idx] = c & adj[v]
                    break
            else:
                cl.append(adj[v] & S)
                ub += W[v]
        return ub

    def solve(S, caps, lb):
        tw = 0
        taken = 0
        caps = list(caps)
        while True:
            changed = False
            relmask = 0
            relbits = 0
            for j in range(k):
                m = S & crew_masks[j]
                if m:
                    if caps[j] <= 0:
                        S &= ~m
                        changed = True
                    elif popcount(m) > caps[j]:
                        relmask |= m
                        relbits |= 1 << j
            f = S
            while f:
                b = f & -f
                v = b.bit_length() - 1
                f ^= b
                if not S & b or relmask & b:
                    continue
                nb = adj[v] & S
                wv = W[v]
                s = 0
                g = nb
                while g and s <= wv:
                    c = g & -g
                    g ^= c
                    s += W[c.bit_length() - 1]
                if wv >= s:
                    tw += wv
                    taken |= b
                    S &= ~(nb | b)
                    f &= S
                    j = crew_of[v]
                    if j >= 0:
                        caps[j] -= 1
                    changed = True
                    continue
                closed = nb | b
                g = nb
                while g:
                    c = g & -g
                    g ^= c
                    u = c.bit_length() - 1
                    if W[u] <= wv and not (closed & ~(adj[u] | c)):
                        S &= ~c
                        f &= S
                        changed = True
                        nb &= ~c
                        closed = nb | b
            if not changed:
                break
        if S == 0:
            if lb is not None and tw <= lb:
                return None
            return (tw, taken)
        relbits = 0
        for j in range(k):
            m = S & crew_masks[j]
            if m and popcount(m) > caps[j]:
                relbits |= 1 << j
        capkey = tuple((j, caps[j]) for j in range(k) if (relbits >> j) & 1)
        key = (S, capkey)
        lb2 = None if lb is None else lb - tw
        hit = memo.get(key)
        if hit is not None:
            if lb2 is not None and hit[0] <= lb2:
                return None
            return (tw + hit[0], taken | hit[1])
        if lb2 is not None:
            u = upper.get(key)
            if u is not None and u <= lb2:
                return None
        comps = components(S, relbits)
        if len(comps) > 1:
            total = 0
            mask = 0
            for c in sorted(comps, key=popcount):
                r = solve(c, caps, None)
                total += r[0]
                mask |= r[1]
            memo[key] = (total, mask)
            if lb2 is not None and total <= lb2:
                return None
            return (tw + total, taken | mask)
        if lb2 is not None:
            ub = clique_bound(S)
            if ub <= lb2:
                old = upper.get(key)
                if old is None or ub < old:
                    upper[key] = ub
                return None
        # branch on a max degree vertex
        bv = -1
        bd = -1
        f = S
        while f:
            b = f & -f
            v = b.bit_length() - 1
            f ^= b
            d = popcount(adj[v] & S)
            if d > bd:
                bd = d
                bv = v
        v = bv
        b = 1 << v
        best = None
        cur = lb2
        caps1 = list(caps)
        if crew_of[v] >= 0:
            caps1[crew_of[v]] -= 1
        r = solve(S & ~(adj[v] | b), caps1, None if cur is None else cur - W[v])
        if r is not None:
            best = (W[v] + r[0], r[1] | b)
            cur = best[0]
        r2 = solve(S & ~b, caps, cur)
        if r2 is not None:
            best = r2
        if best is None:
            old = upper.get(key)
            if old is None or lb2 < old:
                upper[key] = lb2
            return None
        memo[key] = best
        return (tw + best[0], taken | best[1])

    order, bags, width = elimination_order(n, adj, crew_masks)
    if width <= DP_MAX_WIDTH:
        return solve_dp(n, W, adj, crew_masks, crew_of, order, bags)
    full = (1 << n) - 1
    res = solve(full, tuple([SHARED_CAP] * k), None)
    return res[1]


DP_MAX_WIDTH = 24


def elimination_order(n, adj, crew_masks):
    """Min-fill elimination order on conflict graph plus shared crew cliques."""
    g = list(adj)
    for m in crew_masks:
        f = m
        while f:
            b = f & -f
            f ^= b
            i = b.bit_length() - 1
            g[i] |= m & ~b
    alive = (1 << n) - 1

    def fill(v):
        nb = g[v]
        c = 0
        f = nb
        while f:
            b = f & -f
            f ^= b
            u = b.bit_length() - 1
            c += popcount(nb & ~g[u] & ~b)
        return c // 2

    fills = [fill(v) for v in range(n)]
    order = []
    bags = [0] * n
    width = 0
    remaining = set(range(n))
    while remaining:
        v = min(remaining, key=lambda x: (fills[x], popcount(g[x]), x))
        nb = g[v]
        bags[v] = nb
        width = max(width, popcount(nb))
        vb = 1 << v
        f = nb
        while f:
            b = f & -f
            f ^= b
            u = b.bit_length() - 1
            g[u] = (g[u] | nb) & ~b & ~vb
        remaining.discard(v)
        alive &= ~vb
        g[v] = 0
        order.append(v)
        aff = nb
        f = nb
        while f:
            b = f & -f
            f ^= b
            aff |= g[b.bit_length() - 1]
        aff &= alive
        f = aff
        while f:
            b = f & -f
            f ^= b
            u = b.bit_length() - 1
            fills[u] = fill(u)
    return order, bags, width


def solve_dp(n, W, adj, crew_masks, crew_of, order, bags):
    """Exact variable elimination over the elimination order."""
    factors = []  # list of [scope_mask, table]
    for v in order:
        vb = 1 << v
        bucket = [f for f in factors if f[0] & vb]
        factors = [f for f in factors if not f[0] & vb]
        scope = bags[v]
        verts = []
        f = scope
        while f:
            b = f & -f
            f ^= b
            verts.append(b.bit_length() - 1)
        subsets = [0]
        for u in verts:
            ub = 1 << u
            au = adj[u]
            j = crew_of[u]
            if j >= 0:
                cm = crew_masks[j]
                subsets += [X | ub for X in subsets
                            if not (au & X) and popcount(X & cm) < SHARED_CAP]
            else:
                subsets += [X | ub for X in subsets if not (au & X)]
        av = adj[v]
        jv = crew_of[v]
        cmv = crew_masks[jv] if jv >= 0 else 0
        wv = W[v]
        table = {}
        for X in subsets:
            best = None
            # x_v = 0
            val = 0
            ch = 0
            ok = True
            for sm, tb in bucket:
                e = tb.get(X & sm)
                if e is None:
                    ok = False
                    break
                val += e[0]
                ch |= e[1]
            if ok:
                best = (val, ch)
            # x_v = 1
            if not (av & X) and (jv < 0 or popcount(X & cmv) < SHARED_CAP):
                Xv = X | vb
                val = wv
                ch = vb
                ok = True
                for sm, tb in bucket:
                    e = tb.get(Xv & sm)
                    if e is None:
                        ok = False
                        break
                    val += e[0]
                    ch |= e[1]
                if ok and (best is None or val > best[0]):
                    best = (val, ch)
            if best is not None:
                table[X] = best
        factors.append((scope, table))
    chosen = 0
    for sm, tb in factors:
        chosen |= tb[0][1]
    return chosen


# ---------------------------------------------------------------------------


def write_json(out_dir, name, obj):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    sys.setrecursionlimit(20000)

    manifest = json.loads(read_text(os.path.join(data_dir, "manifest.json")))
    book = manifest.get("book")
    declared = [as_id(x) for x in manifest.get("files", [])]
    for name in declared:
        if not os.path.isfile(os.path.join(data_dir, name)):
            sys.stderr.write("ERROR MISSING_FILE %s\n" % name)
            return 1

    p = lambda name: os.path.join(data_dir, name)

    # --- registers
    sites = {}
    for line in read_text(p("sites.jsonl")).splitlines():
        if line.strip() == "":
            continue
        o = json.loads(line)
        sites[as_id(o.get("site"))] = (as_id(o.get("risk_class")), int(o.get("premium")))
    region_of = {}
    for _, f in read_table(p("region_codes.csv"), ","):
        region_of[field(f, 0)] = field(f, 1)
    crew_mode = {}
    for _, f in read_table(p("crews.tsv"), "\t"):
        crew_mode[field(f, 0)] = field(f, 1)
    ini = read_ini(p("benefits.ini"))
    seg_rate = ini.get("segment_rate", {})
    risk_uplift = ini.get("risk_uplift", {})

    # --- round-scoped data
    prop_rows = defaultdict(list)  # round -> [(rowno, proposal, site, crew, households, override)]
    for rn, f in read_table(p("proposals.csv"), ","):
        prop_rows[field(f, 0)].append((rn, field(f, 1), field(f, 2), field(f, 3), field(f, 4), field(f, 5)))
    seg_rows = defaultdict(list)
    for rn, f in read_table(p("segment_codes.tsv"), "\t"):
        seg_rows[field(f, 0)].append((rn, field(f, 1), field(f, 2)))
    permit_rows = defaultdict(list)
    for rn, f in read_table(p("permits.csv"), ","):
        permit_rows[field(f, 0)].append((rn, field(f, 1), field(f, 2), field(f, 3)))
    excl_rows = defaultdict(list)
    excl = json.loads(read_text(p("exclusions.json")))
    for i, e in enumerate(excl, 1):
        excl_rows[as_id(e.get("round"))].append((i, as_id(e.get("first")), as_id(e.get("second"))))

    rounds = sorted(prop_rows)
    check_order = [n for n in declared if n in ROUND_FILES]
    for n in ROUND_FILES:
        if n not in check_order:
            check_order.append(n)

    results = {}  # round -> dict

    for rd in rounds:
        prows = prop_rows[rd]
        pset = set(r[1] for r in prows)
        psites = set(r[2] for r in prows)
        fault = None
        for fname in check_order:
            if fault:
                break
            if fname == "proposals.csv":
                seen = set()
                for rn, pid, site, crew, hh, ov in prows:
                    if pid in seen:
                        fault = ("DUPLICATE_PROPOSAL", fname, rn)
                        break
                    seen.add(pid)
                    bad = (not DIGITS.match(hh) or not (1 <= int(hh) <= 60)
                           or site not in sites or crew not in crew_mode
                           or not (ov == "" or ov in RISK))
                    if bad:
                        fault = ("INVALID_INPUT", fname, rn)
                        break
            elif fname == "segment_codes.tsv":
                for rn, pid, seg in seg_rows.get(rd, []):
                    if pid not in pset:
                        fault = ("UNKNOWN_PROPOSAL", fname, rn)
                        break
                    if seg not in seg_rate:
                        fault = ("INVALID_INPUT", fname, rn)
                        break
            elif fname == "permits.csv":
                for rn, permit, pid, status in permit_rows.get(rd, []):
                    if pid not in pset:
                        fault = ("UNKNOWN_PROPOSAL", fname, rn)
                        break
                    if status not in ("held", "applied", "withdrawn"):
                        fault = ("INVALID_INPUT", fname, rn)
                        break
            elif fname == "exclusions.json":
                for rn, a, b in excl_rows.get(rd, []):
                    if (a not in pset and a not in psites) or (b not in pset and b not in psites):
                        fault = ("UNKNOWN_PROPOSAL", fname, rn)
                        break
                    if a == b:
                        fault = ("INVALID_INPUT", fname, rn)
                        break
        if fault:
            results[rd] = {"status": "rejected", "fault": fault, "n": len(prows)}
            continue

        # --- value
        seg_of = {}
        for rn, pid, seg in seg_rows.get(rd, []):
            seg_of[pid] = seg
        info = {}
        for rn, pid, site, crew, hh, ov in prows:
            rc = ov if ov != "" else sites[site][0]
            seg = seg_of.get(pid)
            rate = seg_rate[seg]
            upl = risk_uplift[rc]
            h = int(hh)
            prem = sites[site][1]
            ben = h * (rate + upl) + prem
            info[pid] = {"rn": rn, "site": site, "crew": crew, "households": h, "segment": seg,
                         "segment_rate": rate, "risk_class": rc, "risk_uplift": upl,
                         "premium": prem, "benefit": ben}
            if ben < 1 and not fault:
                fault = ("NONPOSITIVE_BENEFIT", "proposals.csv", rn)
        if fault:
            results[rd] = {"status": "rejected", "fault": fault, "n": len(prows)}
            continue

        # --- conflicts
        ids = sorted(pset)
        n = len(ids)
        idx = {pid: i for i, pid in enumerate(ids)}
        sources = defaultdict(set)  # (i,j) i<j -> set of source names

        def join(a, b, src):
            if a == b:
                return
            if a > b:
                a, b = b, a
            sources[(a, b)].add(src)

        by_crew = defaultdict(list)
        for pid in ids:
            by_crew[info[pid]["crew"]].append(idx[pid])
        for crew, members in by_crew.items():
            if crew_mode.get(crew) == "exclusive":
                for x in range(len(members)):
                    for y in range(x + 1, len(members)):
                        join(members[x], members[y], "crew")
        by_permit = defaultdict(set)
        withdrawn = 0
        for rn, permit, pid, status in permit_rows.get(rd, []):
            if status == "withdrawn":
                withdrawn += 1
            elif status in ("held", "applied"):
                by_permit[permit].add(idx[pid])
        for permit, members in by_permit.items():
            ml = sorted(members)
            for x in range(len(ml)):
                for y in range(x + 1, len(ml)):
                    join(ml[x], ml[y], "permit")
        by_site = defaultdict(list)
        for pid in ids:
            by_site[info[pid]["site"]].append(idx[pid])

        def expand(name):
            out = set()
            if name in idx:
                out.add(idx[name])
            for i in by_site.get(name, ()):
                out.add(i)
            return out

        for rn, a, b in excl_rows.get(rd, []):
            A = expand(a)
            B = expand(b)
            for x in A:
                for y in B:
                    join(x, y, "exclusion")

        adj = [0] * n
        for (a, b) in sources:
            adj[a] |= 1 << b
            adj[b] |= 1 << a
        shift = n
        W = [info[ids[i]]["benefit"] * (1 << shift) + (1 << (n - 1 - i)) for i in range(n)]
        crew_masks = []
        crew_of = [-1] * n
        for crew, members in sorted(by_crew.items()):
            if crew_mode.get(crew) == "shared" and len(members) > SHARED_CAP:
                j = len(crew_masks)
                m = 0
                for i in members:
                    m |= 1 << i
                    crew_of[i] = j
                crew_masks.append(m)
        chosen_mask = solve_portfolio(n, W, adj, crew_masks, crew_of)
        selected = [ids[i] for i in range(n) if (chosen_mask >> i) & 1]
        total = sum(info[pid]["benefit"] for pid in selected)
        results[rd] = {"status": "planned", "n": len(prows), "selected": selected,
                       "total": total, "info": info, "idx": idx, "sources": sources,
                       "withdrawn": withdrawn, "ids": ids}

    os.makedirs(out_dir, exist_ok=True)

    # --- summary
    srounds = []
    planned = rejected = sel_count = tot = 0
    for rd in rounds:
        r = results[rd]
        if r["status"] == "planned":
            planned += 1
            sel_count += len(r["selected"])
            tot += r["total"]
            srounds.append({"round": rd, "status": "planned", "proposals": r["n"],
                            "selected": r["selected"], "total_benefit": r["total"]})
        else:
            rejected += 1
            srounds.append({"round": rd, "status": "rejected", "proposals": r["n"],
                            "selected": [], "total_benefit": 0})
    write_json(out_dir, "summary.json", {"book": book, "rounds": srounds, "planned_rounds": planned,
                                         "rejected_rounds": rejected, "selected_proposals": sel_count,
                                         "total_benefit": tot})

    # --- policy audit
    arows = []
    for ln, line in enumerate(read_text(p("audit_queries.txt")).splitlines(), 1):
        parts = line.split()
        if not parts:
            continue
        kind = parts[0]
        rd = parts[1] if len(parts) > 1 else ""
        r = results.get(rd)
        status = r["status"] if r else "rejected"
        row = {"line": ln, "kind": kind, "round": rd, "status": status}
        if r and status == "planned":
            info = r["info"]
            sel = set(r["selected"])
            if kind == "VALUE":
                pid = parts[2]
                d = info[pid]
                row.update({"proposal": pid, "segment": d["segment"], "segment_rate": d["segment_rate"],
                            "risk_class": d["risk_class"], "risk_uplift": d["risk_uplift"],
                            "households": d["households"], "premium": d["premium"],
                            "benefit": d["benefit"], "selected": pid in sel})
            elif kind == "PAIR":
                a, b = parts[2], parts[3]
                ia, ib = r["idx"][a], r["idx"][b]
                srcs = set()
                if ia != ib:
                    srcs = r["sources"].get((min(ia, ib), max(ia, ib)), set())
                sl = [s for s in ("crew", "permit", "exclusion") if s in srcs]
                row.update({"first": a, "second": b, "sources": sl, "conflict": bool(sl),
                            "first_selected": a in sel, "second_selected": b in sel})
        arows.append(row)
    write_json(out_dir, "policy_audit.json", {"book": book, "rows": arows})

    # --- data quality
    rej = []
    pairs = 0
    by_src = {"crew": 0, "permit": 0, "exclusion": 0}
    wd = 0
    for rd in rounds:
        r = results[rd]
        if r["status"] == "rejected":
            code, fname, rn = r["fault"]
            rej.append({"round": rd, "code": code, "file": fname, "row": rn})
        else:
            pairs += len(r["sources"])
            for srcs in r["sources"].values():
                for s in srcs:
                    by_src[s] += 1
            wd += r["withdrawn"]
    write_json(out_dir, "data_quality.json", {"book": book, "rejected": rej, "planned_rounds": planned,
                                              "rejected_rounds": rejected, "conflict_pairs": pairs,
                                              "conflicts_by_source": by_src, "withdrawn_permit_rows": wd})

    # --- region / segment
    def slice_doc(key, value, pred):
        rr = []
        cnt = 0
        tb = 0
        for rd in rounds:
            r = results[rd]
            if r["status"] != "planned":
                continue
            sel = [pid for pid in r["selected"] if pred(r["info"][pid])]
            b = sum(r["info"][pid]["benefit"] for pid in sel)
            rr.append({"round": rd, "selected": sel, "benefit": b})
            cnt += len(sel)
            tb += b
        return {"book": book, key: value, "rounds": rr, "selected_proposals": cnt, "total_benefit": tb}

    for reg in REGIONS:
        write_json(out_dir, "region_%s.json" % reg,
                   slice_doc("region", reg, lambda d, reg=reg: region_of.get(d["site"]) == reg))
    for seg in SEGMENTS:
        write_json(out_dir, "segment_%s.json" % seg,
                   slice_doc("segment", seg, lambda d, seg=seg: d["segment"] == seg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
