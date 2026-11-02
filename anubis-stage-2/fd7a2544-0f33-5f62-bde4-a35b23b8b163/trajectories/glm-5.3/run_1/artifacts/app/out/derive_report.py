#!/usr/bin/env python3
"""Thornvale district levy engine.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

Reads a survey export (survey books plus policy tables) from DATA_DIR and
writes the nine ledger reports into OUT_DIR.  All arithmetic is exact.
"""
import sys
import os
import re
import json
from fractions import Fraction as F

ZERO = F(0)

# ---------------------------------------------------------------- parsing

_DECIMAL = re.compile(r'\A-?[0-9]+(\.[0-9]+)?\Z')
_BAD = re.compile(r'[eE+_]')


def parse_number(tok):
    """Exact value of a coordinate token, or None when it is malformed."""
    if _BAD.search(tok):
        return None
    if '/' in tok:
        if tok.count('/') != 1:
            return None
        num, den = tok.split('/')
        if not _DECIMAL.match(num) or not _DECIMAL.match(den):
            return None
        if F(den) == 0:
            return None
        return F(num) / F(den)
    if not _DECIMAL.match(tok):
        return None
    return F(tok)


class Record(object):
    __slots__ = ('kind', 'pid', 'rev', 'book', 'use', 'datum', 'fmt',
                 'raw', 'book_datum')


def _content_key(rec):
    """Name-independent tie-break for records that are otherwise identical."""
    return (rec.use or '', rec.datum or '', rec.book_datum or '',
            tuple(rec.raw))


def _int(tok, idx, default=0):
    try:
        return int(tok[idx])
    except (IndexError, ValueError):
        return default


def read_books(data_dir):
    """All records from every survey book under data_dir (ledger ignored)."""
    records = []
    names = sorted(n for n in os.listdir(data_dir)
                   if n.endswith('.svy') and os.path.isfile(os.path.join(data_dir, n)))
    for name in names:
        path = os.path.join(data_dir, name)
        book = 0
        fmt = None
        bdatum = None
        cur = None
        with open(path, 'r') as fh:
            for raw in fh:
                line = raw.split('#', 1)[0].strip()
                if not line:
                    continue
                tok = line.split()
                key = tok[0]
                if key == 'THORNVALE':
                    continue
                if key == 'BOOK':
                    book = _int(tok, 1, 0)
                    continue
                if key == 'FORMAT':
                    fmt = _int(tok, 1, 0)
                    continue
                if key == 'DATUM':
                    if len(tok) > 1:
                        bdatum = tok[1]
                    continue
                if key in ('PARCEL', 'VOID'):
                    if len(tok) < 2:
                        continue
                    cur = Record()
                    cur.kind = key
                    cur.pid = tok[1]
                    cur.book = book
                    cur.fmt = fmt
                    cur.book_datum = bdatum
                    cur.use = None
                    cur.datum = None
                    cur.raw = []
                    cur.rev = _int(tok, tok.index('REV') + 1, 0) if 'REV' in tok else 0
                    if 'USE' in tok:
                        i = tok.index('USE') + 1
                        if i < len(tok):
                            cur.use = tok[i]
                    if 'DATUM' in tok:
                        i = tok.index('DATUM') + 1
                        if i < len(tok):
                            cur.datum = tok[i]
                    records.append(cur)
                    continue
                if key == 'END':
                    cur = None
                    continue
                if key in ('V', 'D') and cur is not None:
                    if len(tok) < 3:
                        cur.raw.append((key, '', ''))
                    else:
                        cur.raw.append((key, tok[1], tok[2]))
    return records


def load_table(data_dir, name):
    with open(os.path.join(data_dir, name), 'r') as fh:
        return json.load(fh)


# ------------------------------------------------------------- geometry

def points_of(rec):
    """Absolute vertices, or None if any coordinate is malformed."""
    out = []
    cx = cy = None
    for kind, xt, yt in rec.raw:
        fx = parse_number(xt)
        fy = parse_number(yt)
        if fx is None or fy is None:
            return None
        if kind == 'V' or rec.fmt == 1 or cx is None:
            out.append((fx, fy))
            cx, cy = fx, fy
        else:
            cx = cx + fx
            cy = cy + fy
            out.append((cx, cy))
    return out


def ring_of(pts):
    """(vertices, collapsed_count) - collapse repeats and the closing vertex."""
    out = []
    n = 0
    for p in pts:
        if out and out[-1] == p:
            n += 1
            continue
        out.append(p)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out, n


def shoelace(pts):
    if len(pts) < 3:
        return ZERO
    s = ZERO
    px, py = pts[-1]
    for qx, qy in pts:
        s += px * qy - qx * py
        px, py = qx, qy
    return s / 2


def centroid_of(pts):
    """(Cx, Cy) of a polygon with area, else None."""
    a = ZERO
    cx = ZERO
    cy = ZERO
    px, py = pts[-1]
    for qx, qy in pts:
        cr = px * qy - qx * py
        a += cr
        cx += (px + qx) * cr
        cy += (py + qy) * cr
        px, py = qx, qy
    if a == 0:
        return None
    return cx / (3 * a), cy / (3 * a)


def _on_seg(p, a, b):
    return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and
            min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def self_intersects(pts):
    n = len(pts)
    if n < 3:
        return False
    for i in range(n):
        ax, ay = pts[i]
        j0 = (i + 1) % n
        bx, by = pts[j0]
        for j in range(i + 1, n):
            if j == j0:
                continue
            if (j + 1) % n == i:
                continue
            cx, cy = pts[j]
            k1 = (j + 1) % n
            dx, dy = pts[k1]
            d1 = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
            d2 = (bx - ax) * (dy - ay) - (by - ay) * (dx - ax)
            d3 = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx)
            d4 = (dx - cx) * (by - cy) - (dy - cy) * (bx - cx)
            if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
                if d1 and d2 and d3 and d4:
                    return True
            if d1 == 0 and _on_seg(pts[j], pts[i], pts[j0]):
                return True
            if d2 == 0 and _on_seg(pts[k1], pts[i], pts[j0]):
                return True
            if d3 == 0 and _on_seg(pts[i], pts[j], pts[k1]):
                return True
            if d4 == 0 and _on_seg(pts[j0], pts[j], pts[k1]):
                return True
    return False


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


def bbox_hit(a, b):
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


class Trafo(object):
    __slots__ = ('a', 'b', 'c', 'd', 'e', 'f')

    def __init__(self, spec):
        self.a, self.b, self.c, self.d, self.e, self.f = \
            [F(spec[k]) for k in ('a', 'b', 'c', 'd', 'e', 'f')]

    def __call__(self, pts):
        a, b, c, d, e, f = self.a, self.b, self.c, self.d, self.e, self.f
        return [(a * x + b * y + c, d * x + e * y + f) for x, y in pts]


def trafo_for(datums, book, code):
    spec = datums[code]
    best = None
    for fb, rev in spec['revs']:
        if fb <= book and (best is None or fb > best[0]):
            best = (fb, rev)
    return Trafo(best[1] if best else spec['base'])


# ------------------------------------------------- overlap resolution

def _approx_dir(fx, fy):
    """Small coprime integers pointing roughly along the float vector."""
    a = float(fx)
    b = float(fy)
    if a == 0.0 and b == 0.0:
        return None
    if abs(a) >= abs(b):
        if a == 0.0:
            return None
        r = F(b / a).limit_denominator(600)
        p = r.denominator
        q = r.numerator
    else:
        r = F(a / b).limit_denominator(600)
        q = r.denominator
        p = r.numerator
    if p == 0 and q == 0:
        return None
    if p < 0:
        p = -p
        q = -q
    if p == 0 and q < 0:
        q = -q
    return (p, q)


def _convex(pts):
    n = len(pts)
    if n < 3:
        return True
    pos = False
    neg = False
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        cx, cy = pts[(i + 2) % n]
        cr = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if cr > 0:
            pos = True
        elif cr < 0:
            neg = True
    return not (pos and neg)


def _moments(pts):
    """(signed area, integral of y, integral of x) of a polygon."""
    a = ZERO
    mx = ZERO
    my = ZERO
    px, py = pts[-1]
    for qx, qy in pts:
        cr = px * qy - qx * py
        a += cr
        mx += (py + qy) * cr
        my += (px + qx) * cr
        px, py = qx, qy
    return a / 2, mx / 6, my / 6


def _outside(poly, convex_ccw):
    """True if poly lies fully outside one edge half-plane of a ccw polygon."""
    n = len(convex_ccw)
    for i in range(n):
        ax, ay = convex_ccw[i]
        bx, by = convex_ccw[(i + 1) % n]
        ux = bx - ax
        uy = by - ay
        for (px, py) in poly:
            if ux * (py - ay) - uy * (px - ax) > 0:
                break
        else:
            return True
    return False


def _clip(subject, clip_ccw):
    """subject clipped by the convex counter-clockwise polygon."""
    out = list(subject)
    n = len(clip_ccw)
    for i in range(n):
        if not out:
            return out
        ax, ay = clip_ccw[i]
        bx, by = clip_ccw[(i + 1) % n]
        ux = bx - ax
        uy = by - ay
        res = []
        cx, cy = out[-1]
        cside = ux * (cy - ay) - uy * (cx - ax)
        for cur in out:
            dx, dy = cur
            dside = ux * (dy - ay) - uy * (dx - ax)
            if dside >= 0:
                if cside < 0:
                    t = cside / (cside - dside)
                    res.append((cx + t * (dx - cx), cy + t * (dy - cy)))
                res.append(cur)
            elif cside >= 0:
                t = cside / (cside - dside)
                res.append((cx + t * (dx - cx), cy + t * (dy - cy)))
            cx, cy = dx, dy
            cside = dside
        out = res
    return out


def uncovered(target, blockers):
    """Exact area and first moments of the part of target no blocker covers.

    blockers: list of (pid, polygon) whose bounding boxes already overlap.
    """
    n = len(target)
    ids = {}
    blockers = [(ids.setdefault(pid, len(ids) + 1), blk) for pid, blk in blockers]
    # ---- candidate sweep directions ---------------------------------
    cands = [(1, 0), (0, 1)]
    longest = None
    for i in range(n):
        p = target[i]
        q = target[(i + 1) % n]
        dx = q[0] - p[0]
        dy = q[1] - p[1]
        if dx == 0 and dy == 0:
            continue
        ln = dx * dx + dy * dy
        if longest is None or ln > longest[0]:
            longest = (ln, dx, dy)
    if longest is not None:
        d = _approx_dir(float(longest[1]), float(longest[2]))
        if d is not None:
            for c in (d, (-d[1], d[0])):
                if c not in cands:
                    cands.append(c)
    # ---- float proxy for picking the cheapest direction ---------------
    fpts = [[(float(x), float(y)) for x, y in target]]
    for _pid, blk in blockers:
        fpts.append([(float(x), float(y)) for x, y in blk])
    best = None
    for (p, q) in cands:
        texts = []
        tot = 0.0
        for poly in fpts:
            s = [p * x + q * y for x, y in poly]
            texts.append(max(s) - min(s))
        for poly in fpts:
            m = len(poly)
            for i in range(m):
                ax, ay = poly[i]
                bx, by = poly[(i + 1) % m]
                tot += abs(p * (bx - ax) + q * (by - ay))
        if texts[0] <= 0:
            continue
        cost = tot / texts[0]
        if best is None or cost < best[0]:
            best = (cost, p, q)
    p, q = best[1], best[2]
    # ---- fast path: disjoint blockers over convex shapes --------------
    if _convex(target):
        live = []
        ok = True
        for _pid, blk in blockers:
            if not _convex(blk):
                ok = False
                break
            if not _outside(blk, target):
                live.append(blk)
        if ok:
            spans = []
            for blk in live:
                ss = [p * x + q * y for x, y in blk]
                spans.append((min(ss), max(ss)))
            spans.sort()
            for i in range(len(spans) - 1):
                if spans[i][1] >= spans[i + 1][0]:
                    ok = False
                    break
        if ok:
            area, mx, my = _moments(target)
            for blk in live:
                sub = blk if _moments(blk)[0] > 0 else blk[::-1]
                inter = _clip(sub, target)
                if len(inter) >= 3:
                    a, m1, m2 = _moments(inter)
                    area -= a
                    mx -= m1
                    my -= m2
            if area <= 0:
                return ZERO, None, None
            return area, my / area, mx / area
    # ---- map every edge into the sweep frame --------------------------
    scale = p * p + q * q

    def tr(x, y):
        return (p * x + q * y, -q * x + p * y)

    tpts = [tr(x, y) for x, y in target]
    svals = [s for s, t in tpts]
    s0 = min(svals)
    s1 = max(svals)
    info = []                      # (lo, hi, sa, ta, slope, pid, ds, dt)
    for i in range(n):
        a = tpts[i]
        b = tpts[(i + 1) % n]
        if a[0] == b[0]:
            continue
        lo = a[0] if a[0] < b[0] else b[0]
        hi = b[0] if a[0] < b[0] else a[0]
        info.append((lo, hi, a[0], a[1], (b[1] - a[1]) / (b[0] - a[0]), 0,
                     b[0] - a[0], b[1] - a[1]))
    for pid, blk in blockers:
        tp = [tr(x, y) for x, y in blk]
        m = len(tp)
        for i in range(m):
            a = tp[i]
            b = tp[(i + 1) % m]
            if a[0] == b[0]:
                continue
            lo = a[0] if a[0] < b[0] else b[0]
            hi = b[0] if a[0] < b[0] else a[0]
            if hi < s0 or lo > s1:
                continue
            info.append((lo, hi, a[0], a[1], (b[1] - a[1]) / (b[0] - a[0]),
                         pid, b[0] - a[0], b[1] - a[1]))
    cuts = [s0, s1]
    for (lo, hi, sa, ta, sl, pid, ds, dt) in info:
        if s0 < sa < s1:
            cuts.append(sa)
        if s0 < sa + ds < s1:
            cuts.append(sa + ds)
    # ---- crossings, pruned by sweep-interval overlap -----------------
    finfo = []
    for (lo, hi, sa, ta, sl, pid, ds, dt) in info:
        flo = float(lo)
        fhi = float(hi)
        tlo = float(ta)
        thi = float(ta + dt)
        if tlo > thi:
            tlo, thi = thi, tlo
        finfo.append((flo, fhi, tlo, thi))
    order = sorted(range(len(info)), key=lambda i: info[i][0])
    active = []
    for pos in order:
        e = info[pos]
        fe = finfo[pos]
        lo = e[0]
        if active:
            keep = []
            for a in active:
                if a[1] >= lo:
                    keep.append(a)
            active = keep
        for a in active:
            if a[5] == e[5]:
                continue
            fa = finfo[a[4]]
            if fa[0] > fe[1] or fe[0] > fa[1]:
                continue
            if fa[2] > fe[3] or fe[2] > fa[3]:
                continue
            den = a[6] * e[7] - a[7] * e[6]
            if den == 0:
                continue
            wx = e[2] - a[2]
            wy = e[3] - a[3]
            t = (wx * e[7] - wy * e[6]) / den
            if t < 0 or t > 1:
                continue
            u = (wx * a[7] - wy * a[6]) / den
            if u < 0 or u > 1:
                continue
            ix = a[2] + t * a[6]
            if s0 < ix < s1:
                cuts.append(ix)
        active.append((e[0], e[1], e[2], e[3], pos, e[5], e[6], e[7]))
    cuts.sort()
    info.sort(key=lambda e: e[0])
    # ---- sweep the strips ---------------------------------------------
    area = ZERO
    mx = ZERO
    my = ZERO
    nblk = len(blockers)
    ptr = 0
    m = len(info)
    live = []
    for k in range(len(cuts) - 1):
        sa = cuts[k]
        sb = cuts[k + 1]
        if sa == sb:
            continue
        while ptr < m and info[ptr][0] <= sa:
            live.append(info[ptr])
            ptr += 1
        if live:
            dead = False
            for e in live:
                if e[1] < sb:
                    dead = True
                    break
            if dead:
                live = [e for e in live if e[1] >= sb]
        if not live:
            continue
        ds = sb - sa
        lst = [(e[3] + (sa - e[2]) * e[4],
                e[3] + (sb - e[2]) * e[4], e[5]) for e in live]
        lst.sort()
        inside = [False] * (nblk + 1)
        nb = 0
        for idx in range(len(lst) - 1):
            y0, y1, pid = lst[idx]
            if inside[pid]:
                inside[pid] = False
                if pid:
                    nb -= 1
            else:
                inside[pid] = True
                if pid:
                    nb += 1
            if not inside[0] or nb:
                continue
            t0, t1, _tp = lst[idx + 1]
            alpha = t0 - y0
            beta = (t1 - y1) - alpha
            a = alpha * ds + beta * ds / 2
            if a == 0:
                continue
            gam = t0 + y0
            dlt = (t1 + y1) - gam
            area += a
            mx += (alpha * gam * ds + (alpha * dlt + beta * gam) * ds / 2
                   + beta * dlt * ds / 3) / 2
            my += sa * a + alpha * ds * ds / 2 + beta * ds * ds / 3
    if area == 0:
        return ZERO, None, None
    cs = my / area
    ct = mx / area
    return (area / scale,
            (p * cs - q * ct) / scale,
            (q * cs + p * ct) / scale)


# --------------------------------------------------------- spatial index

class Grid(object):
    """Bucket index over bounding boxes (float coordinates).

    Shapes far larger than a cell are kept in a short side list instead of
    being spilled across thousands of buckets.
    """

    def __init__(self, cell):
        self.cell = cell
        self.buckets = {}
        self.big = []

    def _cells(self, bb):
        c = self.cell
        x0 = int(bb[0] // c)
        x1 = int(bb[1] // c)
        y0 = int(bb[2] // c)
        y1 = int(bb[3] // c)
        if (x1 - x0 + 1) * (y1 - y0 + 1) > 1024:
            return None
        return [(ix, iy) for ix in range(x0, x1 + 1)
                for iy in range(y0, y1 + 1)]

    def add(self, key, bb):
        cells = self._cells(bb)
        if cells is None:
            self.big.append(key)
            return
        for cell in cells:
            self.buckets.setdefault(cell, []).append(key)

    def query(self, bb):
        cells = self._cells(bb)
        out = list(self.big)
        if cells is None:
            return out
        seen = set(out)
        for cell in cells:
            for key in self.buckets.get(cell, ()):
                if key not in seen:
                    seen.add(key)
                    out.append(key)
        return out


# ------------------------------------------------------------ reporting

def rat(v):
    return str(v)


def main():
    if len(sys.argv) != 3:
        sys.stderr.write('usage: derive_report.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    records = read_books(data_dir)
    policy = load_table(data_dir, 'policy.json')
    regions = load_table(data_dir, 'regions.json')
    land_use = load_table(data_dir, 'land_use.json')
    quality = load_table(data_dir, 'quality.json')
    datums_raw = load_table(data_dir, 'datums.json')

    use_info = {}
    for u in land_use['uses']:
        use_info[u['code']] = (u['segment'], F(u['weight']))
    datums = {}
    for d in datums_raw['datums']:
        datums[d['code']] = {
            'base': d['transform'],
            'revs': [(r['from_book'], r['transform'])
                     for r in d.get('revisions', [])]}
    precedence = quality['precedence']

    ox = F(regions['origin']['x'])
    oy = F(regions['origin']['y'])
    order = list(regions['order'])
    origin_region = regions.get('origin_region')

    # -------------------------------------------------- reconciliation
    by_id = {}
    for rec in records:
        by_id.setdefault(rec.pid, []).append(rec)

    current = {}
    for pid, recs in by_id.items():
        cur = recs[0]
        ck = _content_key(cur)
        for r in recs[1:]:
            key = _content_key(r)
            if (r.rev, r.book, key) > (cur.rev, cur.book, ck):
                cur = r
                ck = key
        current[pid] = cur

    superseded = []
    for pid, recs in by_id.items():
        cur = current[pid]
        for r in recs:
            if r is not cur:
                superseded.append(r)
    superseded.sort(key=lambda r: (r.pid, r.rev, r.book, r.kind))

    voided_ids = set()
    quarantined = []
    valid = []
    for pid in sorted(current):
        rec = current[pid]
        if rec.kind == 'VOID':
            voided_ids.add(pid)
            continue
        codes = set()
        if rec.use is None or rec.use not in use_info:
            codes.add('UNKNOWN_USE')
        dcode = rec.datum if rec.datum is not None else rec.book_datum
        if dcode is None or dcode not in datums:
            codes.add('UNKNOWN_DATUM')
        pts = points_of(rec)
        if pts is None:
            codes.add('MALFORMED_NUMBER')
        else:
            if len(pts) < 3 or pts[0] != pts[-1]:
                codes.add('OPEN_RING')
            ring, _c = ring_of(pts)
            if len(ring) < 3:
                codes.add('TOO_FEW_VERTICES')
            else:
                if self_intersects(ring):
                    codes.add('SELF_INTERSECTING')
                elif shoelace(ring) == 0:
                    codes.add('ZERO_AREA')
        code = None
        for c in precedence:
            if c in codes:
                code = c
                break
        if code is not None:
            quarantined.append({'book': rec.book, 'code': code,
                                'id': pid, 'rev': rec.rev})
        else:
            valid.append(rec)
    quarantined.sort(key=lambda q: q['id'])

    # -------------------------------------------------------- geometry
    collapsed = 0
    reoriented = 0
    parcels = []
    for rec in valid:
        pts = points_of(rec)
        ring, ncoll = ring_of(pts)
        collapsed += ncoll
        dcode = rec.datum if rec.datum is not None else rec.book_datum
        grid = trafo_for(datums, rec.book, dcode)(ring)
        if shoelace(grid) < 0:
            grid = grid[::-1]
            reoriented += 1
        seg, weight = use_info[rec.use]
        parcels.append({'id': rec.pid, 'book': rec.book, 'rev': rec.rev,
                        'use': rec.use, 'segment': seg, 'weight': weight,
                        'poly': grid, 'area': abs(shoelace(grid)),
                        'bb': bbox(grid)})

    # ---------------------------------------------- overlap waterfall
    parcels.sort(key=lambda p: (-p['book'], p['id']))
    fbb = []
    for p in parcels:
        b = p['bb']
        fbb.append((float(b[0]), float(b[1]), float(b[2]), float(b[3])))
    span = 1.0
    if fbb:
        lo = min(b[0] for b in fbb)
        hi = max(b[1] for b in fbb)
        vlo = min(b[2] for b in fbb)
        vhi = max(b[3] for b in fbb)
        span = max(hi - lo, vhi - vlo, 1.0)
        ext = sorted(max(b[1] - b[0], b[3] - b[2], 1e-9) for b in fbb)
        cell = max(ext[len(ext) // 2], span / 1024.0)
    else:
        cell = 1.0
    index = Grid(cell)
    for k, p in enumerate(parcels):
        bb = p['bb']
        f = fbb[k]
        blockers = []
        for c in index.query(f):
            q = parcels[c]
            if bbox_hit(bb, q['bb']):
                blockers.append((len(blockers) + 1, q['poly']))
        index.add(k, f)
        if blockers:
            area, cx, cy = uncovered(p['poly'], blockers)
        else:
            area = p['area']
            cx, cy = centroid_of(p['poly'])
        if area == 0:
            p['eclipsed'] = True
            p['claimed'] = ZERO
            p['centroid'] = None
        else:
            p['eclipsed'] = False
            p['claimed'] = area
            p['centroid'] = (cx, cy)

    eclipsed = sorted(p['id'] for p in parcels if p['eclipsed'])
    active = [p for p in parcels if not p['eclipsed']]
    for p in active:
        p['base'] = p['claimed'] * p['weight']

    def region_of(cx, cy):
        dx = cx - ox
        dy = cy - oy
        adx = dx if dx > 0 else -dx
        ady = dy if dy > 0 else -dy
        if adx == ady == 0:
            return origin_region
        if adx > ady or (adx == ady and dx * dy > 0):
            return 'East' if dx > 0 else 'West'
        return 'North' if dy > 0 else 'South'

    for p in active:
        p['region'] = region_of(p['centroid'][0], p['centroid'][1])

    books = sorted(set(r.book for r in records))

    # ------------------------------------------------------ ruleset
    top = books[-1] if books else 0
    best = None
    for rs in policy['rulesets']:
        if rs['from_book'] <= top and (best is None or rs['from_book'] > best['from_book']):
            best = rs
    if best is None:
        for rs in policy['rulesets']:
            if best is None or rs['from_book'] < best['from_book']:
                best = rs
    method = best['method']
    house = best['house_size']
    min_seats = best['minimum_seats']
    levy_total = best['levy_total_cents']

    reg_base = dict((r, ZERO) for r in order)
    reg_area = dict((r, ZERO) for r in order)
    reg_parcels = dict((r, []) for r in order)
    for p in active:
        reg_base[p['region']] += p['base']
        reg_area[p['region']] += p['claimed']
        reg_parcels[p['region']].append(p)
    for r in order:
        reg_parcels[r].sort(key=lambda p: p['id'])

    total_area = ZERO
    total_base = ZERO
    for p in active:
        total_area += p['claimed']
        total_base += p['base']

    # --------------------------------------------------------- seats
    eligible = [r for r in order if reg_base[r] > 0]
    seats = dict((r, 0) for r in order)
    for r in eligible:
        seats[r] = min_seats
    awards = []
    for s in range(1, house - min_seats * len(eligible) + 1):
        if not eligible:
            break
        pick = None
        pkey = None
        for r in eligible:
            n = seats[r]
            b = reg_base[r]
            if method == 'jefferson':
                key = (True, b / (n + 1))
            elif method == 'webster':
                key = (True, b / F(2 * n + 1, 2))
            elif n == 0:
                key = (False, b)
            else:
                key = (True, b * b / (n * (n + 1)))
            if pkey is None:
                pick, pkey = r, key
                continue
            if key[0] != pkey[0]:
                if not key[0]:
                    pick, pkey = r, key
                continue
            if key[1] != pkey[1]:
                if key[1] > pkey[1]:
                    pick, pkey = r, key
                continue
            if b > reg_base[pick]:
                pick, pkey = r, key
        seats[pick] += 1
        n = seats[pick]
        b = reg_base[pick]
        if method == 'huntington_hill':
            pr = 'inf' if n == 1 else rat(b * b / ((n - 1) * n))
        elif method == 'webster':
            pr = rat(b / F(2 * (n - 1) + 1, 2))
        else:
            pr = rat(b / n)
        awards.append({'priority': pr, 'region': pick, 'seat': s,
                       'seats_after': n})

    reg_quota = dict((r, ZERO) for r in order)
    if house:
        for r in order:
            reg_quota[r] = F(levy_total) * seats[r] / house

    reg_levy = {}
    floors = {}
    for r in order:
        q = reg_quota[r]
        floors[r] = q.numerator // q.denominator if q.denominator else 0
    left = levy_total - sum(floors.values())
    if left > 0:
        rank = sorted(order, key=lambda r: (-(reg_quota[r] - floors[r]),
                                            order.index(r)))
        for r in rank[:left]:
            floors[r] += 1
    for r in order:
        reg_levy[r] = floors[r]

    for r in order:
        pool = reg_levy[r]
        plist = reg_parcels[r]
        if not plist:
            continue
        tot = reg_base[r]
        if tot == 0:
            for p in plist:
                p['levy'] = 0
            continue
        quotas = {}
        fl = {}
        for p in plist:
            q = F(pool) * p['base'] / tot
            quotas[p['id']] = q
            fl[p['id']] = q.numerator // q.denominator
        left = pool - sum(fl.values())
        if left > 0:
            rank = sorted(plist, key=lambda p: (-(quotas[p['id']] - fl[p['id']]),
                                                p['id']))
            for p in rank[:left]:
                fl[p['id']] += 1
        for p in plist:
            p['levy'] = fl[p['id']]

    # ------------------------------------------------------- reports
    def write(name, obj):
        with open(os.path.join(out_dir, name), 'w') as fh:
            json.dump(obj, fh, indent=2, sort_keys=True)
            fh.write('\n')

    summary = {
        'active': len(active),
        'books': books,
        'eclipsed': len(eclipsed),
        'house_size': house,
        'levy_cents': dict((r, reg_levy[r]) for r in order),
        'method': method,
        'quarantined': len(quarantined),
        'records': len(records),
        'ruleset': best['id'],
        'seats': dict((r, seats[r]) for r in order),
        'superseded': len(superseded),
        'total_area': rat(total_area),
        'total_base': rat(total_base),
        'voided': len(voided_ids),
    }
    write('summary.json', summary)

    audit = {
        'awards': awards,
        'eligible': eligible,
        'house_size': house,
        'levy_total_cents': levy_total,
        'method': method,
        'minimum_seats': min_seats,
        'region_quotas': dict((r, rat(reg_quota[r])) for r in order),
        'ruleset': best['id'],
    }
    write('policy_audit.json', audit)

    counts = {}
    for c in precedence:
        counts[c] = 0
    for q in quarantined:
        counts[q['code']] = counts.get(q['code'], 0) + 1
    write('data_quality.json', {
        'counts': counts,
        'eclipsed': eclipsed,
        'quarantined': quarantined,
        'repairs': {'collapsed_vertices': collapsed,
                    'reoriented': reoriented},
        'superseded': [{'book': r.book, 'id': r.pid, 'kind': r.kind,
                        'rev': r.rev} for r in superseded],
        'voided': sorted(voided_ids),
    })

    for r in order:
        plist = reg_parcels[r]
        write('region_%s.json' % r, {
            'area': rat(reg_area[r]),
            'base': rat(reg_base[r]),
            'levy_cents': reg_levy[r],
            'parcels': [{'area': rat(p['area']),
                         'base': rat(p['base']),
                         'book': p['book'],
                         'centroid': [rat(p['centroid'][0]),
                                      rat(p['centroid'][1])],
                         'claimed': rat(p['claimed']),
                         'id': p['id'],
                         'levy_cents': p['levy'],
                         'rev': p['rev'],
                         'segment': p['segment'],
                         'use': p['use']} for p in plist],
            'region': r,
            'seats': seats[r],
        })

    segs = []
    for p in active:
        if p['segment'] not in segs:
            segs.append(p['segment'])
    for s in ('commercial', 'public'):
        if s not in segs:
            segs.append(s)
    for s in sorted(segs):
        plist = [p for p in active if p['segment'] == s]
        area = ZERO
        base = ZERO
        levy = 0
        by_region = {}
        for r in order:
            sub = [p for p in plist if p['region'] == r]
            b = ZERO
            lv = 0
            for p in sub:
                b += p['base']
                lv += p['levy']
                area += p['claimed']
            base += b
            levy += lv
            by_region[r] = {'base': rat(b), 'levy_cents': lv,
                            'parcels': len(sub)}
        write('segment_%s.json' % s, {
            'area': rat(area),
            'base': rat(base),
            'by_region': by_region,
            'levy_cents': levy,
            'parcel_count': len(plist),
            'segment': s,
        })
    return 0


if __name__ == '__main__':
    sys.exit(main())
