"""Seeded generator of flood repair books (standard library only).

make_book(seed, spec) -> (files, meta); files maps a file name to its text.
"""
import json

_M = (1 << 64) - 1


class _Rng:
    def __init__(self, seed):
        self.x = ((seed * 0x9E3779B97F4A7C15) + 0x2545F4914F6CDD1D) & _M or 1
        for _ in range(4):
            self.next()

    def next(self):
        x = self.x
        x ^= x >> 12
        x ^= (x << 25) & _M
        x ^= x >> 27
        self.x = x
        return (x * 0x2545F4914F6CDD1D) & _M

    def randint(self, lo, hi):
        return lo + self.next() % (hi - lo + 1)

    def random(self):
        return (self.next() >> 11) / float(1 << 53)

    def choice(self, seq):
        return seq[self.next() % len(seq)]

    def shuffle(self, a):
        for i in range(len(a) - 1, 0, -1):
            j = self.next() % (i + 1)
            a[i], a[j] = a[j], a[i]

    def sample(self, seq, k):
        a = list(seq)
        self.shuffle(a)
        return a[:k]


SEGMENTS = ("commercial", "public", "residential")
CLASSES = ("A", "B", "C", "D")
REGIONS = ("North", "South", "West", "East")
DATA_FILES = ("proposals.csv", "segment_codes.tsv", "sites.jsonl", "region_codes.csv", "crews.tsv",
              "permits.csv", "exclusions.json", "benefits.ini", "audit_queries.txt")
LIMITS = {"rounds": 200, "proposals": 160, "records": 900, "households": (1, 60), "rate": (5, 60),
          "uplift": (-10, 30), "premium": (0, 800)}
FAULT_KINDS = ("dup", "dup_invalid", "households", "site", "crew", "override", "seg_unknown",
               "seg_invalid", "permit_unknown", "permit_status", "permit_both", "excl_unknown_pid",
               "excl_unknown_site", "excl_same", "nonpositive", "two_files", "two_files_b",
               "two_rows_excl", "nonpositive_and_file")


def _codes(rng, n, prefix, digits, taken):
    out = []
    lo, hi = 10 ** (digits - 1), 10 ** digits - 1
    while len(out) < n:
        c = prefix + str(rng.randint(lo, hi))
        if c not in taken:
            taken.add(c)
            out.append(c)
    return out


def _pair(a, b):
    return (a, b) if a < b else (b, a)


def _lattice(rng, n, rows, pdiag):
    edges = set()
    cols = (n + rows - 1) // rows
    for c in range(cols):
        for r in range(rows):
            v = c * rows + r
            if v >= n:
                continue
            if r + 1 < rows and v + 1 < n:
                edges.add((v, v + 1))
            if v + rows < n:
                edges.add((v, v + rows))
            if r + 1 < rows and v + rows + 1 < n and rng.random() < pdiag:
                edges.add((v, v + rows + 1))
    return edges


def _random_graph(rng, n, p):
    return {(a, b) for a in range(n) for b in range(a + 1, n) if rng.random() < p}


class _Book:
    def __init__(self, seed, spec):
        self.rng = rng = _Rng(seed)
        self.spec = spec
        self.taken = set()
        while True:
            rates = {"commercial": rng.randint(5, 60), "public": rng.randint(5, 60),
                     "residential": rng.randint(5, 8)}
            uplifts = {c: rng.randint(-10, 30) for c in CLASSES}
            neg = rng.choice(CLASSES)
            uplifts[neg] = rng.randint(-10, -(rates["residential"] + 1))
            best = max(rates[s] + uplifts[c] for s in SEGMENTS for c in CLASSES)
            if best >= 25 and len({rates[s] + uplifts[c] for s in SEGMENTS for c in CLASSES if rates[s] + uplifts[c] > 0}) >= 6:
                break
        self.rates, self.uplifts, self.neg = rates, uplifts, neg
        self.book_id = "B" + str(rng.randint(1000, 9999))
        self.sites = []
        for sid in _codes(rng, spec["sites"], "S", 5, self.taken):
            self.sites.append({"site": sid, "risk_class": rng.choice(CLASSES),
                               "premium": rng.randint(0, 800), "region": rng.choice(REGIONS)})
        self.site_by_id = {s["site"]: s for s in self.sites}
        self.crews = [(c, "exclusive" if rng.random() < 0.6 else "shared")
                      for c in _codes(rng, spec["crews"], "C", 4, self.taken)]
        self.exclusive = [c for c, m in self.crews if m == "exclusive"]
        self.shared = [c for c, m in self.crews if m == "shared"]
        self.permits = _codes(rng, spec["permits"], "M", 5, self.taken)
        self.rounds = []
        self.all_pids = []

    def new_pids(self, n):
        out = _codes(self.rng, n, "P", 6, self.taken)
        self.all_pids += out
        return out

    # valuation -------------------------------------------------------------
    def value_large(self, site, lo, hi):
        rng = self.rng
        for _ in range(400):
            seg = rng.choice(SEGMENTS)
            cls = site["risk_class"]
            override = ""
            if rng.random() < 0.27:
                override = rng.choice([c for c in CLASSES if c != cls])
                cls = override
            m = self.rates[seg] + self.uplifts[cls]
            if m <= 0:
                continue
            hlo = max(1, -(-(lo - site["premium"]) // m))
            hhi = min(60, (hi - site["premium"]) // m)
            if hlo <= hhi:
                return seg, override, rng.randint(hlo, hhi)
        raise ValueError("no valuation in window")

    def value_small(self, site):
        rng = self.rng
        while True:
            seg = rng.choice(SEGMENTS)
            cls = site["risk_class"]
            override = ""
            r = rng.random()
            if r < 0.25:
                override = rng.choice([c for c in CLASSES if c != cls])
                cls = override
            elif r < 0.3:
                override = cls
            h = rng.randint(1, 60)
            if h * (self.rates[seg] + self.uplifts[cls]) + site["premium"] >= 1:
                return seg, override, h

    def benefit(self, site, seg, override, h):
        cls = override or site["risk_class"]
        return h * (self.rates[seg] + self.uplifts[cls]) + site["premium"]

    # one round -------------------------------------------------------------
    def build_round(self, n, edges, large, gadgets=()):
        rng = self.rng
        adj = [set() for _ in range(n)]
        for a, b in edges:
            adj[a].add(b)
            adj[b].add(a)
        tris = [(a, b, c) for (a, b) in sorted(edges) for c in sorted(adj[a] & adj[b]) if c > b]
        elist = sorted(edges)
        ne = max(1, len(edges))
        # exclusive crews: vertex-disjoint cliques
        cand = [t for t in tris] + [e for e in elist]
        rng.shuffle(cand)
        crew_groups, used, crew_cov = [], set(), set()
        for g in cand:
            if len(crew_cov) >= 0.27 * ne:
                break
            if any(v in used for v in g) or rng.random() < 0.3:
                continue
            used |= set(g)
            crew_groups.append(g)
            for i in range(len(g)):
                for j in range(i + 1, len(g)):
                    crew_cov.add(_pair(g[i], g[j]))
        # site exclusions on triangles u, v (one site) and p
        site_groups, site_used, site_cov, site_excl = [], set(), set(), []
        tr = list(tris)
        rng.shuffle(tr)
        for (a, b, c) in tr:
            if len(site_cov) >= 0.16 * ne:
                break
            trio = [a, b, c]
            rng.shuffle(trio)
            u, v, p = trio
            if u in site_used or v in site_used or p in site_used:
                continue
            site_used |= {u, v, p}
            gi = len(site_groups)
            site_groups.append([u, v])
            site_groups.append([p])
            site_excl.append((gi, gi + 1, rng.choice(("SP", "PS", "SS"))))
            site_cov |= {_pair(u, p), _pair(v, p)}
        rest = [v for v in range(n) if v not in site_used]
        rng.shuffle(rest)
        i = 0
        while i < len(rest):
            r = rng.random()
            k = 1 if r < 0.7 else (2 if r < 0.95 else 3)
            site_groups.append(rest[i:i + k])
            i += k
        # permits: cliques touching uncovered edges, plus decoys
        uncovered = set(edges) - crew_cov - site_cov
        cand = [t for t in tris] + [e for e in elist]
        rng.shuffle(cand)
        permit_groups, perm_cov = [], set()
        for g in cand:
            if len(perm_cov) >= 0.36 * ne:
                break
            prs = {_pair(g[i], g[j]) for i in range(len(g)) for j in range(i + 1, len(g))}
            if not (prs & uncovered) or rng.random() < 0.3:
                continue
            permit_groups.append([(v, rng.choice(("held", "applied"))) for v in g])
            perm_cov |= prs
        non_edges = [(a, b) for a in range(n) for b in range(a + 1, n) if (a, b) not in edges]
        decoys = []
        n_decoy = max(2, len(edges) // 12) if large else rng.randint(1, 3)
        for _ in range(n_decoy):
            if not non_edges:
                break
            a, b = rng.choice(non_edges)
            sa, sb = rng.choice((("held", "withdrawn"), ("withdrawn", "applied"), ("withdrawn", "withdrawn")))
            permit_groups.append([(a, sa), (b, sb)])
            decoys.append((a, b))
        for _ in range(max(1, n // 20)):
            permit_groups.append([(rng.randint(0, n - 1), rng.choice(("held", "applied", "withdrawn")))])
        uncovered -= perm_cov
        excl = []
        for (a, b) in sorted(uncovered):
            excl.append(("P", a, "P", b) if rng.random() < 0.5 else ("P", b, "P", a))
        for (a, b) in rng.sample(elist, min(len(elist), max(1, len(elist) // 15))):
            excl.append(("P", a, "P", b))
        # crews for every vertex
        crew_of = {}
        assert len(self.exclusive) >= len(crew_groups) + n and len(self.shared) >= n, "crew register too small"
        ex_pool = rng.sample(self.exclusive, len(crew_groups) + n)
        k = 0
        for g in crew_groups:
            for v in g:
                crew_of[v] = ex_pool[k]
            k += 1
        free = [v for v in range(n) if v not in crew_of]
        rng.shuffle(free)
        sh_pool = rng.sample(self.shared, max(1, n))
        s = 0
        while free:
            v = free.pop()
            if rng.random() < 0.45 and free:
                partner = [u for u in free if u not in adj[v]]
                group = [v] + partner[:rng.randint(1, 2)]
                for u in group[1:]:
                    free.remove(u)
                    decoys.append(_pair(v, u))
                for u in group:
                    crew_of[u] = sh_pool[s]
                s += 1
            elif rng.random() < 0.5:
                crew_of[v] = ex_pool[k]
                k += 1
            else:
                crew_of[v] = sh_pool[s]
                s += 1
        # sites, valuation and ids
        sites = rng.sample(self.sites, len(site_groups))
        site_of = {}
        for gi, g in enumerate(site_groups):
            for v in g:
                site_of[v] = sites[gi]
        pids = self.new_pids(n)
        lo = hi = 0
        if large:
            t = rng.randint(1000, 1300)
            lo, hi = t * 92 // 100, t * 108 // 100
        val = {}
        for v in range(n):
            st = site_of[v]
            val[v] = self.value_large(st, lo, hi) if large else self.value_small(st)
        for kind, a, b in gadgets:
            st = site_of[a]
            if kind == "twin":
                site_of[b] = st
                val[b] = val[a]
        rid = _codes(rng, 1, "R", 5, self.taken)[0]
        rnd = {"round": rid, "n": n, "pids": pids, "edges": set(edges), "decoys": decoys, "large": large,
               "site_of": site_of, "val": val, "crew_of": crew_of}
        rnd["prop_rows"] = [[pids[v], site_of[v]["site"], crew_of[v], str(val[v][2]), val[v][1]] for v in range(n)]
        rnd["seg_rows"] = [[pids[v], val[v][0]] for v in range(n)]
        prow = []
        permits = rng.sample(self.permits, len(permit_groups))
        for gi, g in enumerate(permit_groups):
            for v, stt in g:
                prow.append([permits[gi], pids[v], stt])
        rnd["permit_rows"] = prow
        erow = []
        for kind_a, a, kind_b, b in excl:
            erow.append([pids[a], pids[b]])
        for ga, gb, kind in site_excl:
            sa = site_of[site_groups[ga][0]]["site"]
            p = site_groups[gb][0]
            if kind == "SP":
                erow.append([sa, pids[p]])
            elif kind == "PS":
                erow.append([pids[p], sa])
            else:
                erow.append([sa, site_of[p]["site"]])
        rnd["excl_rows"] = erow
        rnd["sources"] = {"crew": crew_cov, "site": site_cov, "permit": perm_cov}
        for key in ("prop_rows", "seg_rows", "permit_rows", "excl_rows"):
            rng.shuffle(rnd[key])
        got = self.derive(rnd)
        want = {_pair(pids[a], pids[b]) for a, b in edges}
        assert got == want, (rid, len(got ^ want))
        return rnd

    def derive(self, rnd):
        pids = set(r[0] for r in rnd["prop_rows"])
        at_site = {}
        crew_members = {}
        for pid, site, crew, _, _ in rnd["prop_rows"]:
            at_site.setdefault(site, []).append(pid)
            crew_members.setdefault(crew, []).append(pid)
        out = set()
        mode = dict(self.crews)
        for crew, mem in crew_members.items():
            if mode.get(crew) == "exclusive":
                out |= {_pair(a, b) for a in mem for b in mem if a != b}
        live = {}
        for permit, pid, status in rnd["permit_rows"]:
            if status != "withdrawn":
                live.setdefault(permit, []).append(pid)
        for mem in live.values():
            out |= {_pair(a, b) for a in mem for b in mem if a != b}
        for first, second in rnd["excl_rows"]:
            fa = [first] if first in pids else at_site.get(first, [])
            sb = [second] if second in pids else at_site.get(second, [])
            out |= {_pair(a, b) for a in fa for b in sb if a != b}
        return out

    # faults ----------------------------------------------------------------
    def plant(self, rnd, kind):
        rng = self.rng
        P, S, X, E = rnd["prop_rows"], rnd["seg_rows"], rnd["permit_rows"], rnd["excl_rows"]
        pids = [r[0] for r in P]

        def ins(rows, row):
            rows.insert(rng.randint(0, len(rows)), row)

        def other_pid():
            mine = set(pids)
            pool = [p for p in self.all_pids if p not in mine]
            return rng.choice(pool) if pool else _codes(rng, 1, "P", 6, self.taken)[0]

        if kind in ("dup", "dup_invalid"):
            src = rng.choice(P)
            row = list(src)
            row[4] = rng.choice(("", "A", "C"))
            if kind == "dup_invalid":
                row[3] = rng.choice(("0", "61", "4.5"))
            pos = rng.randint(P.index(src) + 1, len(P))
            P.insert(pos, row)
            ins(S, [row[0], rng.choice(SEGMENTS)])
        elif kind == "households":
            rng.choice(P)[3] = rng.choice(("0", "61", "75", "4.5", "-3", "x"))
        elif kind == "site":
            rng.choice(P)[1] = _codes(rng, 1, "S", 5, self.taken)[0]
        elif kind == "crew":
            rng.choice(P)[2] = _codes(rng, 1, "C", 4, self.taken)[0]
        elif kind == "override":
            rng.choice(P)[4] = rng.choice(("E", "a", "AB", "0"))
        elif kind == "seg_unknown":
            ins(S, [other_pid(), rng.choice(SEGMENTS)])
        elif kind == "seg_invalid":
            rng.choice(S)[1] = rng.choice(("industrial", "civic", "mixed"))
        elif kind == "permit_unknown":
            ins(X, [rng.choice(self.permits), other_pid(), rng.choice(("held", "applied"))])
        elif kind == "permit_status":
            if X:
                rng.choice(X)[2] = rng.choice(("revoked", "pending", "Held"))
            else:
                ins(X, [rng.choice(self.permits), rng.choice(pids), "revoked"])
        elif kind == "permit_both":
            ins(X, [rng.choice(self.permits), other_pid(), rng.choice(("revoked", "expired"))])
        elif kind == "excl_unknown_pid":
            ins(E, [rng.choice(pids), other_pid()] if rng.random() < 0.5 else [other_pid(), rng.choice(pids)])
        elif kind == "excl_unknown_site":
            mine = {r[1] for r in P}
            st = rng.choice([s["site"] for s in self.sites if s["site"] not in mine])
            ins(E, [st, rng.choice(pids)] if rng.random() < 0.5 else [rng.choice(pids), st])
        elif kind == "excl_same":
            name = rng.choice(pids) if rng.random() < 0.6 else rng.choice(P)[1]
            ins(E, [name, name])
        elif kind == "nonpositive":
            self.make_nonpositive(rnd, boundary=True)
        elif kind == "two_files":
            self.plant(rnd, rng.choice(("permit_unknown", "permit_status")))
            self.plant(rnd, rng.choice(("households", "seg_invalid", "excl_same")))
        elif kind == "two_files_b":
            self.plant(rnd, rng.choice(("seg_unknown", "site")))
            self.plant(rnd, rng.choice(("excl_unknown_pid", "permit_status")))
        elif kind == "two_rows_excl":
            self.plant(rnd, "excl_same")
            self.plant(rnd, "excl_unknown_pid")
        elif kind == "nonpositive_and_file":
            self.make_nonpositive(rnd)
            self.plant(rnd, rng.choice(("excl_unknown_site", "permit_status", "seg_unknown")))
        else:
            raise ValueError(kind)
        rnd["fault"] = rnd.get("fault", ()) + (kind,)

    def make_nonpositive(self, rnd, boundary=False):
        rng = self.rng
        m = self.rates["residential"] + self.uplifts[self.neg]
        rows = rnd["prop_rows"]
        cand = [r for r in rows if r[1] in self.site_by_id and self.site_by_id[r[1]]["premium"] < -m * 60 - 1]
        if not cand:
            st = rng.choice([s for s in self.sites if s["premium"] < -m * 60 - 1])
            r = rng.choice(rows)
            r[1] = st["site"]
            cand = [r]
        r = rng.choice(cand)
        prem = self.site_by_id[r[1]]["premium"]
        hmin = (prem + 1 + (-m) - 1) // (-m)
        if prem - hmin * (-m) >= 1:
            hmin += 1
        r[3] = str(rng.randint(max(1, hmin), 60))
        r[4] = self.neg
        for s in rnd["seg_rows"]:
            if s[0] == r[0]:
                s[1] = "residential"
        if not boundary:
            return
        # Benefit exactly 0 on one row and below 0 on the next row of the round:
        # the boundary of "below 1" and "the first such row" both decide the reported row.
        zero = next((s for s in self.sites if 0 < s["premium"] <= 60 * -m and s["premium"] % -m == 0), None)
        assert zero is not None, "no site for a zero benefit"
        low = next(s for s in self.sites if s["premium"] < -m * 60 - 1)
        k = min(rows.index(r), len(rows) - 2)
        for row, site, h in ((rows[k], zero, zero["premium"] // -m), (rows[k + 1], low, 60)):
            row[1], row[3], row[4] = site["site"], str(h), self.neg
            for s in rnd["seg_rows"]:
                if s[0] == row[0]:
                    s[1] = "residential"


def _small_graph(book, kind):
    rng = book.rng
    n = rng.randint(10, 15)
    edges = _random_graph(rng, n, 0.12 + 0.25 * rng.random())
    gadgets = []
    if kind == "twin":
        a, b = n, n + 1
        edges.add((a, b))
        n += 2
        gadgets.append(("twin", a, b))
    return n, edges, gadgets


def _path_tie(book, rnd):
    """Append an isolated path a-b-c whose middle benefit equals the ends together."""
    rng = book.rng
    named = {r[1] for r in rnd["prop_rows"]} | {x for e in rnd["excl_rows"] for x in e}
    free_sites = [s for s in book.sites if s["site"] not in named]
    for _ in range(2000):
        sa, sc = rng.sample(free_sites, 2)
        va, vc = book.value_small(sa), book.value_small(sc)
        target = book.benefit(sa, *va) + book.benefit(sc, *vc)
        sb = rng.choice(free_sites)
        seg = rng.choice(SEGMENTS)
        override = "" if rng.random() < 0.6 else rng.choice(CLASSES)
        m = book.rates[seg] + book.uplifts[override or sb["risk_class"]]
        if m <= 0 or (target - sb["premium"]) % m:
            continue
        h = (target - sb["premium"]) // m
        if 1 <= h <= 60:
            break
    else:
        return False
    a, b, c = book.new_pids(3)
    for pid, st, (sg, ov, hh) in ((a, sa, va), (b, sb, (seg, override, h)), (c, sc, vc)):
        rnd["prop_rows"].insert(rng.randint(0, len(rnd["prop_rows"])), [pid, st["site"], rng.choice(book.shared), str(hh), ov])
        rnd["seg_rows"].insert(rng.randint(0, len(rnd["seg_rows"])), [pid, sg])
    used = {r[0] for r in rnd["permit_rows"]}
    m1, m2 = rng.sample([m for m in book.permits if m not in used], 2)
    for row in ([m1, a, "held"], [m1, b, "applied"], [m2, b, "held"], [m2, c, "held"]):
        rnd["permit_rows"].insert(rng.randint(0, len(rnd["permit_rows"])), row)
    n = rnd["n"]
    rnd["pids"] = rnd["pids"] + [a, b, c]
    rnd["edges"] |= {(n, n + 1), (n + 1, n + 2)}
    rnd["n"] = n + 3
    got = book.derive(rnd)
    want = {_pair(rnd["pids"][x], rnd["pids"][y]) for x, y in rnd["edges"]}
    assert got == want, "path tie changed conflicts"
    rnd["tie"] = rnd.get("tie", ()) + ("path",)
    return True


def _audit(book, rnd, k):
    rng = book.rng
    pids = rnd["pids"]
    lines = []
    edges = sorted(rnd["edges"])
    for _ in range(k):
        r = rng.random()
        if r < 0.45:
            lines.append("VALUE %s %s" % (rnd["round"], rng.choice(pids)))
            continue
        if r < 0.7 and edges:
            a, b = rng.choice(edges)
        elif r < 0.85 and rnd["decoys"]:
            a, b = rng.choice(rnd["decoys"])
        else:
            a, b = rng.sample(range(len(pids)), 2)
        if rng.random() < 0.5:
            a, b = b, a
        lines.append("PAIR %s %s %s" % (rnd["round"], pids[a], pids[b]))
    return lines


def make_book(seed, spec):
    book = _Book(seed, spec)
    rng = book.rng
    rounds = []
    for n, rows in spec["large"]:
        while True:
            edges = _lattice(rng, n, rows, 0.7)
            try:
                rounds.append(book.build_round(n, edges, True))
                break
            except ValueError:
                continue
    kinds = list(FAULT_KINDS)
    rng.shuffle(kinds)
    faults = [kinds[i % len(kinds)] for i in range(spec["faults"])]
    for i in range(spec["small"]):
        tie = "twin" if i < spec["ties"] // 2 else ""
        n, edges, gadgets = _small_graph(book, tie)
        rnd = book.build_round(n, edges, False, gadgets)
        if gadgets:
            rnd["tie"] = ("twin",)
        if spec["ties"] // 2 <= i < spec["ties"]:
            assert _path_tie(book, rnd), "path tie not placed"
        rounds.append(rnd)
    small = [r for r in rounds if not r["large"] and "tie" not in r]
    for kind, rnd in zip(faults, rng.sample(small, len(faults))):
        book.plant(rnd, kind)
    for rnd in rounds:
        rnd["audit"] = _audit(book, rnd, spec["audit_large"] if rnd["large"] else spec["audit_small"])
    return _assemble(book, rounds)


def _check_bounds(book, rounds):
    lo, hi = LIMITS["rate"]
    assert all(lo <= v <= hi for v in book.rates.values())
    lo, hi = LIMITS["uplift"]
    assert all(lo <= v <= hi for v in book.uplifts.values())
    lo, hi = LIMITS["premium"]
    assert all(lo <= s["premium"] <= hi for s in book.sites)
    assert len(rounds) <= LIMITS["rounds"]
    for rnd in rounds:
        assert len(rnd["prop_rows"]) <= LIMITS["proposals"]
        assert len(rnd["permit_rows"]) + len(rnd["excl_rows"]) <= LIMITS["records"]
        if "fault" not in rnd:
            for row in rnd["prop_rows"]:
                assert 1 <= int(row[3]) <= 60


def _assemble(book, rounds):
    rng = book.rng
    _check_bounds(book, rounds)
    order = list(DATA_FILES)
    if book.spec.get("order") == "shuffle":
        while order == list(DATA_FILES):
            rng.shuffle(order)

    def by_round(key, fmt):
        seq = list(rounds)
        rng.shuffle(seq)
        return [fmt(r["round"], row) for r in seq for row in r[key]]

    files = {}
    files["manifest.json"] = json.dumps({"book": book.book_id, "files": order}, indent=2) + "\n"
    files["proposals.csv"] = "round,proposal,site,crew,households,risk_override\n" + "".join(
        by_round("prop_rows", lambda rid, r: "%s,%s,%s,%s,%s,%s\n" % (rid, r[0], r[1], r[2], r[3], r[4])))
    files["segment_codes.tsv"] = "round\tproposal\tsegment\n" + "".join(
        by_round("seg_rows", lambda rid, r: "%s\t%s\t%s\n" % (rid, r[0], r[1])))
    sites = list(book.sites)
    rng.shuffle(sites)
    files["sites.jsonl"] = "".join(json.dumps({"site": s["site"], "risk_class": s["risk_class"],
                                               "premium": s["premium"]}) + "\n" for s in sites)
    rng.shuffle(sites)
    files["region_codes.csv"] = "site,region\n" + "".join("%s,%s\n" % (s["site"], s["region"]) for s in sites)
    crews = list(book.crews)
    rng.shuffle(crews)
    files["crews.tsv"] = "crew\tmode\n" + "".join("%s\t%s\n" % c for c in crews)
    files["permits.csv"] = "round,permit,proposal,status\n" + "".join(
        by_round("permit_rows", lambda rid, r: "%s,%s,%s,%s\n" % (rid, r[0], r[1], r[2])))
    ex = by_round("excl_rows", lambda rid, r: json.dumps({"round": rid, "first": r[0], "second": r[1]}))
    files["exclusions.json"] = "[\n" + ",\n".join("  " + e for e in ex) + "\n]\n"
    lines = ["[segment_rate]"] + ["%s = %d" % (s, book.rates[s]) for s in SEGMENTS] + [""]
    lines += ["[risk_uplift]"] + ["%s = %d" % (c, book.uplifts[c]) for c in CLASSES]
    files["benefits.ini"] = "\n".join(lines) + "\n"
    blank = book.spec.get("blank_row")
    if blank:
        # An empty line after data row `blank`: a data row is any later non-empty line.
        for name in ("proposals.csv", "permits.csv"):
            text = files[name].splitlines(keepends=True)
            files[name] = "".join(text[:blank + 1] + ["\n"] + text[blank + 1:])
    audit = [line for r in rounds for line in r["audit"]]
    rng.shuffle(audit)
    # A blank line after every 97th query: line numbers count every line of the file.
    files["audit_queries.txt"] = "".join(line + "\n" + ("\n" if i % 97 == 96 else "") for i, line in enumerate(audit))
    meta = {"book": book.book_id, "order": order,
            "large": [{"round": r["round"], "n": r["n"], "edges": len(r["edges"]),
                       "share": {k: round(len(v) / max(1, len(r["edges"])), 3) for k, v in r["sources"].items()}}
                      for r in rounds if r["large"]],
            "faults": {r["round"]: list(r["fault"]) for r in rounds if "fault" in r},
            "ties": {r["round"]: list(r["tie"]) for r in rounds if "tie" in r}}
    return files, meta
