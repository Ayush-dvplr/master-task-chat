"""Instance families for the premortem survey. Returns (n, w, cliques, pairs)."""
import random


def band(rng, n, bw=10, crew_max=3, permits_per=0.5, pairs_per=0.6, wlo=60, whi=140, p_excl=0.8):
    cliques, pairs = [], []
    i = 0
    while i < n:
        k = rng.randint(1, crew_max)
        grp = list(range(i, min(n, i + k)))
        if rng.random() < p_excl and len(grp) > 1:
            cliques.append(grp)
        i += k
    for _ in range(int(n * permits_per)):
        s = rng.randrange(n)
        win = list(range(s, min(n, s + bw)))
        k = min(len(win), rng.randint(2, 3))
        cliques.append(rng.sample(win, k))
    for _ in range(int(n * pairs_per)):
        a = rng.randrange(n)
        b = a + rng.randint(1, bw)
        if b < n:
            pairs.append((a, b))
    w = [rng.randint(wlo, whi) for _ in range(n)]
    return n, w, cliques, pairs


def ring(rng, n, **kw):
    """Band closed into a cycle (doubles path width)."""
    n_, w, cliques, pairs = band(rng, n, **kw)
    bw = kw.get("bw", 10)
    extra = []
    for _ in range(int(n * kw.get("pairs_per", 0.6) * bw / n) + 3):
        a = rng.randrange(n - bw, n)
        b = rng.randrange(0, bw)
        extra.append((a, b))
    return n, w, cliques, pairs + extra


def grid(rng, n, rows=6, wlo=60, whi=140, diag=0.5, crew_frac=0.3, tri=0):
    """rows x cols king-ish grid: pathwidth ~ rows (+diag)."""
    cols = (n + rows - 1) // rows
    idx = lambda r, c: c * rows + r
    pairs, cliques = [], []
    for c in range(cols):
        for r in range(rows):
            v = idx(r, c)
            if v >= n:
                continue
            for dr, dc in ((1, 0), (0, 1)):
                u = idx(r + dr, c + dc)
                if r + dr < rows and u < n:
                    pairs.append((v, u))
            if rng.random() < diag:
                for dr in ((1,) if tri else (1, -1)):
                    if 0 <= r + dr < rows:
                        u = idx(r + dr, c + 1)
                        if u < n:
                            pairs.append((v, u))
    w = [rng.randint(wlo, whi) for _ in range(n)]
    return n, w, cliques, pairs


def motifs(rng, n, k=12, dens=0.35, ports=3, links=4, wlo=60, whi=140):
    pairs = []
    m = n // k
    groups = [list(range(i * k, (i + 1) * k)) for i in range(m)]
    if m * k < n:
        groups[-1] += list(range(m * k, n))
    for g in groups:
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                if rng.random() < dens:
                    pairs.append((g[i], g[j]))
    for a in range(m - 1):
        pa = rng.sample(groups[a], ports)
        pb = rng.sample(groups[a + 1], ports)
        for _ in range(links):
            pairs.append((rng.choice(pa), rng.choice(pb)))
    w = [rng.randint(wlo, whi) for _ in range(n)]
    return n, w, [], pairs


def random_sparse(rng, n, deg=6, wlo=60, whi=140):
    pairs = set()
    while len(pairs) < n * deg // 2:
        a, b = rng.sample(range(n), 2)
        pairs.add((min(a, b), max(a, b)))
    w = [rng.randint(wlo, whi) for _ in range(n)]
    return n, w, [], list(pairs)
