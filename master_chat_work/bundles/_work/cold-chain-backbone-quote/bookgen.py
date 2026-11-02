"""Seeded quote-book generator shared by datagen.py and (pasted) the hidden-book tests.

An abstract project is {"n": int, "terms": set[pos], "act": {pos: charge}, "edges": {(a, b): cost}}
with positions 0..n (0 = depot), a < b.  The reach of a corridor project (largest position gap of a
non-depot link) is drawn per project; grouped projects shuffle positions, so their gaps are wide.
"""
import json
import random

CORRIDORS = ["harbour", "ringroad", "airport", "mill", "canal", "orchard"]
BANDS = {"B1": (0, 1), "B2": (2, 3), "B3": (5, 2), "B4": (1, 4), "B5": (7, 5), "B6": (3, 1)}
CLASSES = {
    "yard": 4, "yard_east": 7, "blast": 9, "chiller": 3, "freezer": 11, "store": 6,
    "hut": 5, "mast": 14, "kiosk": 2, "shed": 8, "relay_a": 12, "relay_b": 17,
    "junction": 19, "tower": 23, "vault": 27, "dock": 10,
}


def gadget(rng, n, n_terms, n_links, n_depot, pair=True, reach=4):
    """Corridor project with relay hubs; at most n_terms cold rooms and n_links links."""
    act = {}
    edges = {}
    terms = set()
    p = 3
    while p <= n - 3 and len(terms) < n_terms:
        h = p
        k = rng.randint(3, 4)
        cand = [q for q in range(h - 3, h + 4) if 1 <= q <= n and q != h and q not in act and q not in terms]
        rng.shuffle(cand)
        members = sorted(cand[:k])
        hub_charge = rng.randint(10, 20)
        act[h] = hub_charge
        spoke = {}
        for q in members:
            if len(terms) >= n_terms:
                break
            terms.add(q)
            spoke[q] = rng.randint(1, 3)
            edges[(min(h, q), max(h, q))] = spoke[q]
        ms = sorted(spoke)
        hubtree = hub_charge + sum(spoke.values())
        for a, b in zip(ms, ms[1:]):
            if b - a <= max(reach, 2):
                lo = hubtree // max(1, len(ms) - 1) + 1
                hi = hub_charge + spoke[a] + spoke[b] - 1
                edges[(a, b)] = rng.randint(min(lo, hi), max(lo, hi))
        p += rng.randint(6, 9)
    if pair:
        for _ in range(2):
            if len(terms) + 2 > n_terms:
                break
            free = [q for q in range(2, n - 6) if all(x not in act and x not in terms for x in range(q, q + 7))]
            if not free:
                break
            q = rng.choice(free)
            t1, h1, h2, m, t3 = q, q + 1, q + 5, q + 3, q + 6
            charge = rng.randint(6, 12)
            act[h1] = charge
            act[h2] = charge
            act[m] = 2
            terms.update([t1, t3])
            edges[(t1, h1)] = 1
            edges[(h1, h2)] = 1
            edges[(h2, t3)] = 1
            edges[(t1, m)] = charge + 1
            edges[(m, t3)] = charge + 1
    free = [q for q in range(1, n + 1) if q not in terms and q not in act]
    while len(terms) < n_terms:
        q = rng.choice(free)
        free.remove(q)
        terms.add(q)
    for q in range(1, n + 1):
        if q not in act:
            act[q] = rng.randint(2, 12) if q in terms else rng.randint(4, 30)
    act[0] = rng.randint(3, 9)
    for q in range(1, n):
        if (q, q + 1) not in edges and rng.random() < 0.9 and len(edges) < n_links - n_depot:
            edges[(q, q + 1)] = rng.randint(8, 30)
    tries = 0
    while len(edges) < n_links - n_depot and tries < 5000:
        tries += 1
        a = rng.randint(1, n)
        b = a + rng.randint(2, max(2, reach))
        if b <= n and (a, b) not in edges:
            edges[(a, b)] = rng.randint(8, 40)
    for q in rng.sample(range(1, n + 1), n_depot):
        edges[(0, q)] = rng.randint(12, 45)
    assert len(terms) <= n_terms and len(edges) <= n_links, (len(terms), len(edges))
    assert all(a == 0 or b - a <= max(reach, 4) for a, b in edges)
    return {"n": n, "terms": terms, "act": act, "edges": edges}


def small(rng, n, n_terms, n_links):
    """Tiny project for the regression suite (positions 0..n)."""
    act = {0: rng.randint(1, 6)}
    terms = set(rng.sample(range(1, n + 1), n_terms))
    edges = {}
    if n >= 4 and rng.random() < 0.6:
        h = rng.randint(2, n - 1)
        terms.discard(h)
        act[h] = rng.randint(6, 14)
        for q in range(max(1, h - 2), min(n, h + 2) + 1):
            if q != h:
                edges[(min(h, q), max(h, q))] = rng.randint(1, 3)
    for q in range(1, n + 1):
        act.setdefault(q, rng.randint(1, 9) if q in terms else rng.randint(2, 15))
    for q in range(0, n):
        if (q, q + 1) not in edges and rng.random() < 0.85:
            edges[(q, q + 1)] = rng.randint(3, 18)
    tries = 0
    while len(edges) < n_links and tries < 400:
        tries += 1
        a = rng.randint(0, n - 1)
        b = rng.randint(a + 1, n)
        if b <= n and (a, b) not in edges:
            edges[(a, b)] = rng.randint(2, 25)
    if not terms:
        terms.add(n)
    return {"n": n, "terms": terms, "act": act, "edges": edges}


def grouped(rng, n_groups, size, n_terms, density):
    """Project of groups that meet at single sites; positions are shuffled afterwards."""
    act = {0: rng.randint(3, 9)}
    edges = {}
    terms = set()
    placed = [0]
    nxt = 1
    for k in range(n_groups):
        s = rng.randint(*size)
        new = list(range(nxt, nxt + s))
        nxt += s
        top = 0 if k == 0 else rng.choice(placed[1:])
        verts = [top] + new
        hub, spokes = new[0], new[1:3]
        act[hub] = rng.randint(10, 20)
        sp = {}
        for q in spokes:
            terms.add(q)
            sp[q] = rng.randint(1, 3)
            edges[(hub, q)] = sp[q]
        a, b = spokes
        lo = (act[hub] + sp[a] + sp[b]) // 2 + 1
        hi = act[hub] + sp[a] + sp[b] - 1
        edges[(a, b)] = rng.randint(min(lo, hi), max(lo, hi))
        cycle = list(verts)
        rng.shuffle(cycle)
        for x, y in zip(cycle, cycle[1:] + cycle[:1]):
            key = (min(x, y), max(x, y))
            if x != y and key not in edges:
                edges[key] = rng.randint(8, 40)
        want = int(len(verts) * rng.uniform(*density))
        tries = 0
        while sum(1 for e in edges if e[0] in verts and e[1] in verts) < want and tries < 500:
            tries += 1
            x, y = rng.sample(verts, 2)
            key = (min(x, y), max(x, y))
            if 0 not in key or k == 0:
                edges.setdefault(key, rng.randint(8, 40))
        placed += new
    free = [q for q in range(1, nxt) if q not in act and q not in terms]
    rng.shuffle(free)
    while len(terms) < n_terms and free:
        terms.add(free.pop())
    n = nxt - 1
    for q in range(1, n + 1):
        if q not in act:
            act[q] = rng.randint(2, 12) if q in terms else rng.randint(4, 30)
    perm = list(range(1, n + 1))
    rng.shuffle(perm)
    to = {0: 0}
    to.update({q: perm[q - 1] for q in range(1, n + 1)})
    edges = {(min(to[a], to[b]), max(to[a], to[b])): c for (a, b), c in edges.items()}
    return {"n": n, "terms": {to[q] for q in terms}, "act": {to[q]: c for q, c in act.items()}, "edges": edges}


def _cost_parts(rng, cost):
    options = [band for band, (base, per) in BANDS.items() if cost - base >= per and (cost - base) % per == 0]
    band = rng.choice(options)
    base, per = BANDS[band]
    return band, (cost - base) // per


def encode(rng, pid, P, used_links, corrupt=None):
    """Rows for one project: (site rows, layout rows, link rows, closed ids, overrides).

    corrupt: None or a tuple of codes from DUP, UNKNOWN, NONET, CLOSED_UNKNOWN.
    """
    corrupt = corrupt or ()
    n = P["n"]
    ids = ["S%03d" % x for x in rng.sample(range(100, 1000), n + 1)]
    names = sorted(rng.sample(CORRIDORS, rng.randint(2, min(5, n))), key=CORRIDORS.index)
    cuts = sorted(rng.sample(range(2, n + 1), len(names) - 1))
    bounds = [1] + cuts + [n + 1]
    layout = []
    corridor_of = {}
    for k, name in enumerate(names):
        slot = rng.randint(2, 9)
        for q in range(bounds[k], bounds[k + 1]):
            layout.append([pid, ids[q], name, str(slot)])
            corridor_of[q] = name
            slot += rng.randint(1, 6)
    by_charge = {}
    for name, charge in CLASSES.items():
        by_charge.setdefault(charge, []).append(name)
    sites = []
    overrides = []
    for q in range(n + 1):
        role = "depot" if q == 0 else "cold_room" if q in P["terms"] else "relay"
        charge = P["act"][q]
        if charge in by_charge and rng.random() < 0.7:
            cls = rng.choice(by_charge[charge])
        else:
            cls = rng.choice([c for c, v in CLASSES.items() if v != charge])
            overrides.append(("%s/%s" % (pid, ids[q]), charge))
        sites.append([pid, ids[q], role, cls])
    links = []
    closed = []
    for (a, b), cost in sorted(P["edges"].items()):
        lid = _fresh_link(rng, used_links)
        band, km = _cost_parts(rng, cost)
        ends = [ids[a], ids[b]]
        rng.shuffle(ends)
        links.append({"project": pid, "link": lid, "a": ends[0], "b": ends[1], "band": band, "km": km})
    extra = []
    for _ in range(rng.randint(1, 3)):
        a = rng.randint(1, n - 1)
        b = rng.randint(a + 1, n)
        if (a, b) not in P["edges"]:
            extra.append((a, b, rng.randint(1, 3)))
    if "NONET" in corrupt:
        cold = sorted(P["terms"])
        target = rng.choice(cold)
        for row, ((a, b), _c) in zip(links, sorted(P["edges"].items())):
            if target in (a, b):
                closed.append(row["link"])
    for a, b, cost in extra:
        lid = _fresh_link(rng, used_links)
        band, km = _cost_parts(rng, cost)
        links.append({"project": pid, "link": lid, "a": ids[a], "b": ids[b], "band": band, "km": km})
        closed.append(lid)
    if "UNKNOWN" in corrupt or "CLOSED_UNKNOWN" in corrupt:
        stranger = "S%03d" % rng.choice([x for x in range(100, 1000) if "S%03d" % x not in ids])
        lid = _fresh_link(rng, used_links)
        links.append({"project": pid, "link": lid, "a": ids[rng.randint(1, n)], "b": stranger, "band": "B6", "km": rng.randint(5, 20)})
        if "CLOSED_UNKNOWN" in corrupt:
            closed.append(lid)
    if "DUP" in corrupt:
        q = rng.randint(1, n)
        sites.append([pid, ids[q], sites[q][2], rng.choice(sorted(CLASSES))])
    return sites, layout, links, closed, overrides


def _fresh_link(rng, used):
    while True:
        lid = "L%05d" % rng.randint(10000, 99999)
        if lid not in used:
            used.add(lid)
            return lid


def render(projects_rows, rng):
    """projects_rows: list of encode() results -> {file name: text}."""
    sites, layout, links, closed, overrides = [], [], [], [], []
    for s, l, k, c, o in projects_rows:
        sites += s
        layout += l
        links += k
        closed += c
        overrides += o
    rng.shuffle(sites)
    rng.shuffle(layout)
    rng.shuffle(links)
    files = {}
    files["sites.csv"] = "project,site,role,class\n" + "".join(",".join(r) + "\n" for r in sites)
    files["layout.tsv"] = "project\tsite\tcorridor\tslot\n" + "".join("\t".join(r) + "\n" for r in layout)
    files["links.jsonl"] = "".join(json.dumps(r) + "\n" for r in links)
    toml = ["[corridors]", "order = [" + ", ".join('"%s"' % c for c in CORRIDORS) + "]", ""]
    for band, (base, per) in BANDS.items():
        toml += ["[tariff.%s]" % band, "base = %d" % base, "per_km = %d" % per, ""]
    toml += ["[closed]", "links = ["] + ['    "%s",' % lid for lid in sorted(closed)] + ["]"]
    files["access_rules.toml"] = "\n".join(toml) + "\n"
    ini = ["[classes]"] + ["%s = %d" % kv for kv in CLASSES.items()] + ["", "[overrides]"]
    ini += ["%s = %d" % kv for kv in sorted(overrides)]
    files["activation.ini"] = "\n".join(ini) + "\n"
    return files


def new_rng(seed):
    return random.Random(seed)
