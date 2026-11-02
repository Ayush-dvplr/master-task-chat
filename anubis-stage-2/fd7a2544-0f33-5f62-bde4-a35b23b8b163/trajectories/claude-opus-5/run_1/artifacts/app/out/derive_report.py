#!/usr/bin/env python3
"""Thornvale district levy engine.

Reads a survey export (survey books plus policy tables) and writes the nine
ledger reports.  All arithmetic is exact: every quantity on the path to a
reported number is an integer or a fractions.Fraction.
"""
import bisect
import json
import os
import re
import sys
from fractions import Fraction

REGIONS = ('North', 'South', 'East', 'West')
SEGMENTS = ('commercial', 'public')

DEC_RE = re.compile(r'\A-?[0-9]+(?:\.[0-9]+)?\Z')
FRAC_RE = re.compile(r'\A-?[0-9]+/[0-9]+\Z')


# --------------------------------------------------------------------------
# survey books
# --------------------------------------------------------------------------

def parse_number(tok):
    """Exact value of a book number token, or None when the token is malformed."""
    if FRAC_RE.match(tok):
        num, den = tok.split('/')
        if int(den) == 0:
            return None
        return Fraction(int(num), int(den))
    if DEC_RE.match(tok):
        return Fraction(tok)
    return None


def parse_book_file(path):
    books = []
    book = None
    rec = None
    with open(path) as handle:
        text = handle.read()
    for raw in text.split('\n'):
        cut = raw.find('#')
        if cut >= 0:
            raw = raw[:cut]
        toks = raw.split()
        if not toks:
            continue
        head = toks[0]
        if head == 'THORNVALE':
            book = {'book': None, 'format': None, 'datum': None, 'records': []}
            books.append(book)
            rec = None
        elif head == 'BOOK':
            book['book'] = int(toks[1])
        elif head == 'FORMAT':
            book['format'] = int(toks[1])
        elif head == 'DATUM':
            book['datum'] = toks[1]
        elif head == 'PARCEL':
            fields = dict(zip(toks[2::2], toks[3::2]))
            rec = {'kind': 'PARCEL', 'id': toks[1], 'rev': int(fields['REV']),
                   'use': fields['USE'], 'datum': fields.get('DATUM', book['datum']),
                   'steps': [], 'malformed': False}
            book['records'].append(rec)
        elif head == 'VOID':
            fields = dict(zip(toks[2::2], toks[3::2]))
            book['records'].append({'kind': 'VOID', 'id': toks[1],
                                    'rev': int(fields['REV'])})
            rec = None
        elif head == 'END':
            rec = None
        elif head in ('V', 'D'):
            x = parse_number(toks[1])
            y = parse_number(toks[2])
            if x is None or y is None:
                rec['malformed'] = True
                x = Fraction(0) if x is None else x
                y = Fraction(0) if y is None else y
            rec['steps'].append((head, x, y))
    return books


def load_books(data_dir):
    books = []
    for name in sorted(os.listdir(data_dir)):
        if name.endswith('.svy'):
            books.extend(parse_book_file(os.path.join(data_dir, name)))
    return books


def load_tables(data_dir):
    tables = {}
    for name in ('datums', 'land_use', 'regions', 'policy', 'quality'):
        with open(os.path.join(data_dir, name + '.json')) as handle:
            tables[name] = json.load(handle)
    return tables


# --------------------------------------------------------------------------
# reconciliation
# --------------------------------------------------------------------------

def reconcile(books):
    records = []
    for book in sorted(books, key=lambda b: b['book']):
        for rec in book['records']:
            rec['book'] = book['book']
            rec['seq'] = len(records)
            records.append(rec)
    by_id = {}
    for rec in records:
        by_id.setdefault(rec['id'], []).append(rec)
    winners = {}
    superseded = []
    for pid, group in by_id.items():
        group = sorted(group, key=lambda r: (r['rev'], r['seq']))
        winners[pid] = group[-1]
        superseded.extend(group[:-1])
    return records, winners, superseded


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------

def ring_points(rec):
    pts = []
    for kind, x, y in rec['steps']:
        if kind == 'V':
            pts.append((x, y))
        else:
            px, py = pts[-1]
            pts.append((px + x, py + y))
    return pts


def dedupe_cycle(pts):
    """Remove vertices equal to their successor (cyclically); count removals."""
    out = []
    removed = 0
    for p in pts:
        if out and out[-1] == p:
            removed += 1
            continue
        out.append(p)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
        removed += 1
    return out, removed


def shoelace(pts):
    total = 0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[i - 1]
        total += x2 * y1 - x1 * y2
    return total


def _orient(ax, ay, bx, by, cx, cy):
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _on_segment(ax, ay, bx, by, px, py):
    return (min(ax, bx) <= px <= max(ax, bx) and
            min(ay, by) <= py <= max(ay, by))


def segments_meet(a, b, c, d):
    d1 = _orient(a[0], a[1], b[0], b[1], c[0], c[1])
    d2 = _orient(a[0], a[1], b[0], b[1], d[0], d[1])
    d3 = _orient(c[0], c[1], d[0], d[1], a[0], a[1])
    d4 = _orient(c[0], c[1], d[0], d[1], b[0], b[1])
    if d1 == 0 and d2 == 0:
        return (_on_segment(a[0], a[1], b[0], b[1], c[0], c[1]) or
                _on_segment(a[0], a[1], b[0], b[1], d[0], d[1]) or
                _on_segment(c[0], c[1], d[0], d[1], a[0], a[1]) or
                _on_segment(c[0], c[1], d[0], d[1], b[0], b[1]))
    if d1 == 0:
        return _on_segment(a[0], a[1], b[0], b[1], c[0], c[1])
    if d2 == 0:
        return _on_segment(a[0], a[1], b[0], b[1], d[0], d[1])
    if d3 == 0:
        return _on_segment(c[0], c[1], d[0], d[1], a[0], a[1])
    if d4 == 0:
        return _on_segment(c[0], c[1], d[0], d[1], b[0], b[1])
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def self_intersecting(pts):
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if segments_meet(a, b, pts[j], pts[(j + 1) % n]):
                return True
    return False


# --------------------------------------------------------------------------
# datums
# --------------------------------------------------------------------------

def datum_table(datums):
    table = {}
    for entry in datums['datums']:
        steps = [(None, entry['transform'])]
        for rev in entry.get('revisions', []):
            steps.append((rev['from_book'], rev['transform']))
        table[entry['code']] = steps
    return table


def transform_for(table, code, book):
    steps = table[code]
    chosen = steps[0][1]
    best = None
    for from_book, tf in steps[1:]:
        if book >= from_book and (best is None or from_book > best):
            best = from_book
            chosen = tf
    return tuple(Fraction(chosen[k]) for k in ('a', 'b', 'c', 'd', 'e', 'f'))


def apply_transform(tf, pts):
    a, b, c, d, e, f = tf
    return [(a * x + b * y + c, d * x + e * y + f) for x, y in pts]


# --------------------------------------------------------------------------
# overlap apportionment
# --------------------------------------------------------------------------

def _edges_of(poly, tag, out, lo, hi):
    """Append non-vertical edges of ``poly`` overlapping the x-span (lo, hi)."""
    n = len(poly)
    x2, y2 = poly[-1]
    for i in range(n):
        x1, y1 = x2, y2
        x2, y2 = poly[i]
        if x1 == x2:
            continue
        if x1 < x2:
            ax, ay, bx, by = x1, y1, x2, y2
        else:
            ax, ay, bx, by = x2, y2, x1, y1
        if bx <= lo or ax >= hi:
            continue
        slope = (by - ay) / (bx - ax)
        out.append((ax, bx, ay, slope, tag,
                    float(ax), float(bx), float(ay), float(by), float(slope)))


def point_in_poly(pt, poly):
    px, py = pt
    inside = False
    n = len(poly)
    x2, y2 = poly[-1]
    for i in range(n):
        x1, y1 = x2, y2
        x2, y2 = poly[i]
        if (y1 > py) != (y2 > py):
            cross = (x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)
            if (cross > 0) == (y2 > y1):
                inside = not inside
    return inside


def polys_overlap(a, b):
    na = len(a)
    nb = len(b)
    for i in range(na):
        p1 = a[i - 1]
        p2 = a[i]
        alox = p1[0] if p1[0] < p2[0] else p2[0]
        ahix = p1[0] if p1[0] > p2[0] else p2[0]
        aloy = p1[1] if p1[1] < p2[1] else p2[1]
        ahiy = p1[1] if p1[1] > p2[1] else p2[1]
        for j in range(nb):
            q1 = b[j - 1]
            q2 = b[j]
            if (min(q1[0], q2[0]) > ahix or max(q1[0], q2[0]) < alox or
                    min(q1[1], q2[1]) > ahiy or max(q1[1], q2[1]) < aloy):
                continue
            if segments_meet(p1, p2, q1, q2):
                return True
    return point_in_poly(a[0], b) or point_in_poly(b[0], a)


def claim_moments(poly, others):
    """Area and first moments of ``poly`` minus the union of ``others``."""
    lo = min(p[0] for p in poly)
    hi = max(p[0] for p in poly)
    edges = []
    _edges_of(poly, 0, edges, lo, hi)
    for idx, other in enumerate(others):
        _edges_of(other, idx + 1, edges, lo, hi)
    cuts = set((lo, hi))
    scale = 1.0
    for edge in edges:
        if lo < edge[0] < hi:
            cuts.add(edge[0])
        if lo < edge[1] < hi:
            cuts.add(edge[1])
        for v in (edge[5], edge[6], edge[7], edge[8]):
            if v < 0:
                v = -v
            if v > scale:
                scale = v
    tol = 1e-9 * scale
    count = len(edges)
    for i in range(count):
        ax0, ax1, ay, asl, atag, afx0, afx1, afy0, afy1, _afsl = edges[i]
        aflo = afy0 if afy0 < afy1 else afy1
        afhi = afy1 if afy0 < afy1 else afy0
        for j in range(i + 1, count):
            btag = edges[j][4]
            if atag == btag:
                continue
            bfy0 = edges[j][7]
            bfy1 = edges[j][8]
            if bfy0 < bfy1:
                bflo, bfhi = bfy0, bfy1
            else:
                bflo, bfhi = bfy1, bfy0
            if aflo > bfhi + tol or bflo > afhi + tol:
                continue
            bfx0 = edges[j][5]
            bfx1 = edges[j][6]
            fx0 = afx0 if afx0 > bfx0 else bfx0
            fx1 = afx1 if afx1 < bfx1 else bfx1
            if fx0 >= fx1 + tol:
                continue
            bsl = edges[j][3]
            if asl == bsl:
                continue
            bx0 = edges[j][0]
            by = edges[j][2]
            x = (by - bsl * bx0 - ay + asl * ax0) / (asl - bsl)
            if lo < x < hi:
                x0 = ax0 if ax0 > bx0 else bx0
                x1 = ax1 if ax1 < edges[j][1] else edges[j][1]
                if x0 < x < x1:
                    cuts.add(x)
    cuts = sorted(cuts)
    nslab = len(cuts) - 1
    fcuts = [float(c) for c in cuts]
    own_starts = [[] for _ in range(nslab)]
    oth_starts = [[] for _ in range(nslab)]
    own_ends = [0] * nslab
    oth_ends = [0] * nslab
    for x0, x1, y0, slope, tag, fx0, _fx1, fy0, _fy1, fsl in edges:
        a = bisect.bisect_left(cuts, x0)
        b = bisect.bisect_left(cuts, x1)
        if b > nslab:
            b = nslab
        if a >= b:
            continue
        item = (x0, y0, slope, tag, b, fx0, fy0, fsl)
        if tag:
            oth_starts[a].append(item)
            oth_ends[b - 1] += 1
        else:
            own_starts[a].append(item)
            own_ends[b - 1] += 1
    area = Fraction(0)
    mom_x = Fraction(0)
    mom_y = Fraction(0)
    own = []
    oth = []
    ntags = len(others) + 1
    for k in range(nslab):
        xa = cuts[k]
        xb = cuts[k + 1]
        own.extend(own_starts[k])
        oth.extend(oth_starts[k])
        near = []
        plo = phi = None
        for x0, y0, slope, _tag, _last, _fx0, _fy0, _fsl in own:
            ya = y0 + slope * (xa - x0)
            yb = y0 + slope * (xb - x0)
            if ya < yb:
                near.append((ya, yb, 0))
                elo, ehi = ya, yb
            else:
                near.append((ya, yb, 0))
                elo, ehi = yb, ya
            if plo is None or elo < plo:
                plo = elo
            if phi is None or ehi > phi:
                phi = ehi
        if plo is None:
            if own_ends[k] or oth_ends[k]:
                own = [it for it in own if it[4] > k + 1]
                oth = [it for it in oth if it[4] > k + 1]
            continue
        parity = [0] * ntags
        cover = 0
        if oth:
            fxa = fcuts[k]
            fxb = fcuts[k + 1]
            fplo = float(plo)
            fphi = float(phi)
            for x0, y0, slope, tag, _last, fx0, fy0, fsl in oth:
                fya = fy0 + fsl * (fxa - fx0)
                fyb = fy0 + fsl * (fxb - fx0)
                if fya < fyb:
                    flo, fhi = fya, fyb
                else:
                    flo, fhi = fyb, fya
                if fhi < fplo - tol:
                    if parity[tag]:
                        parity[tag] = 0
                        cover -= 1
                    else:
                        parity[tag] = 1
                        cover += 1
                    continue
                if flo > fphi + tol:
                    continue
                ya = y0 + slope * (xa - x0)
                yb = y0 + slope * (xb - x0)
                if ya < yb:
                    elo, ehi = ya, yb
                else:
                    elo, ehi = yb, ya
                if ehi < plo:
                    if parity[tag]:
                        parity[tag] = 0
                        cover -= 1
                    else:
                        parity[tag] = 1
                        cover += 1
                elif elo <= phi:
                    near.append((ya, yb, tag))
        if len(near) > 1:
            near.sort()
            width = xb - xa
            inside_p = 0
            prev = near[0]
            for item in near[1:]:
                tag = prev[2]
                if tag:
                    if parity[tag]:
                        parity[tag] = 0
                        cover -= 1
                    else:
                        parity[tag] = 1
                        cover += 1
                else:
                    inside_p ^= 1
                if inside_p and not cover:
                    b0 = prev[0]
                    b1 = prev[1]
                    t0 = item[0]
                    t1 = item[1]
                    h0 = t0 - b0
                    h1 = t1 - b1
                    if h0 or h1:
                        area += width * (h0 + h1) / 2
                        mom_x += width * (xa * (h0 + h1) / 2
                                          + width * (h0 / 6 + h1 / 3))
                        mom_y += width * (t0 * t0 + t0 * t1 + t1 * t1
                                          - b0 * b0 - b0 * b1 - b1 * b1) / 6
                prev = item
        if own_ends[k]:
            own = [it for it in own if it[4] > k + 1]
        if oth_ends[k]:
            oth = [it for it in oth if it[4] > k + 1]
    return area, mom_x, mom_y


def bbox_neighbours(boxes):
    """Adjacency of bounding boxes that may overlap, found by an x sweep.

    ``boxes`` are float boxes; the test is deliberately generous so that the
    exact test downstream never loses a genuine overlap.
    """
    scale = 1.0
    for box in boxes:
        for v in box:
            if v < 0:
                v = -v
            if v > scale:
                scale = v
    tol = 1e-9 * scale
    count = len(boxes)
    adj = [[] for _ in range(count)]
    active = []
    for i in sorted(range(count), key=lambda k: boxes[k][0]):
        bx0, by0, _bx1, by1 = boxes[i]
        limit = bx0 - tol
        active = [j for j in active if boxes[j][2] >= limit]
        for j in active:
            other = boxes[j]
            if by0 <= other[3] + tol and other[1] <= by1 + tol:
                adj[i].append(j)
                adj[j].append(i)
        active.append(i)
    return adj


# --------------------------------------------------------------------------
# apportionment
# --------------------------------------------------------------------------

def priority(method, base, seats):
    if method == 'jefferson':
        return base / (seats + 1)
    if method == 'webster':
        return base / (seats + Fraction(1, 2))
    if method == 'huntington_hill':
        if seats == 0:
            return None
        return base * base / (seats * (seats + 1))
    raise ValueError('unknown method %r' % (method,))


def _better(new, old):
    if new[0] != old[0]:
        return new[0] < old[0]
    if new[0] == 0:
        return new[2:] > old[2:]
    return new[1:] > old[1:]


def apportion(method, house_size, minimum_seats, bases, order):
    eligible = [r for r in order if bases[r] > 0]
    seats = {r: 0 for r in order}
    for region in eligible:
        seats[region] = minimum_seats
    rank = {r: i for i, r in enumerate(order)}
    awards = []
    for n in range(house_size - minimum_seats * len(eligible)):
        best = None
        for region in eligible:
            pri = priority(method, bases[region], seats[region])
            key = (0 if pri is None else 1, pri, bases[region], -rank[region])
            if best is None or _better(key, best[0]):
                best = (key, region, pri)
        if best is None:
            break
        region = best[1]
        seats[region] += 1
        awards.append({'priority': 'inf' if best[2] is None else str(best[2]),
                       'region': region,
                       'seat': n + 1,
                       'seats_after': seats[region]})
    return eligible, seats, awards


def largest_remainder(total, weights, keys, rank):
    """Split integer ``total`` across ``keys`` in proportion to ``weights``."""
    denom = sum(weights[k] for k in keys)
    out = {k: 0 for k in keys}
    if denom == 0 or total == 0:
        return out
    fracs = []
    assigned = 0
    for k in keys:
        exact = Fraction(weights[k]) * total / denom
        whole = exact.numerator // exact.denominator
        out[k] = whole
        assigned += whole
        fracs.append((exact - whole, k))
    fracs.sort(key=lambda t: (-t[0], rank[t[1]]))
    for _frac, k in fracs[:total - assigned]:
        out[k] += 1
    return out


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------

def region_of(dx, dy, origin_region):
    if dx == 0 and dy == 0:
        return origin_region
    adx = dx if dx >= 0 else -dx
    ady = dy if dy >= 0 else -dy
    if adx > ady:
        return 'East' if dx > 0 else 'West'
    if ady > adx:
        return 'North' if dy > 0 else 'South'
    if dx > 0:
        return 'East' if dy > 0 else 'South'
    return 'West' if dy < 0 else 'North'


def run(data_dir, out_dir):
    tables = load_tables(data_dir)
    books = load_books(data_dir)
    records, winners, superseded = reconcile(books)

    uses = {u['code']: u for u in tables['land_use']['uses']}
    datums = datum_table(tables['datums'])
    precedence = tables['quality']['precedence']
    prec_rank = {c: i for i, c in enumerate(precedence)}
    order = list(tables['regions']['order'])
    origin_region = tables['regions']['origin_region']
    ox = Fraction(tables['regions']['origin']['x'])
    oy = Fraction(tables['regions']['origin']['y'])

    quarantined = []
    collapsed = 0
    reoriented = 0
    clean = []
    for pid in sorted(winners):
        rec = winners[pid]
        if rec['kind'] != 'PARCEL':
            continue
        flags = []
        if rec['malformed']:
            flags.append('MALFORMED_NUMBER')
        if rec['use'] not in uses:
            flags.append('UNKNOWN_USE')
        if rec['datum'] not in datums:
            flags.append('UNKNOWN_DATUM')
        ring = None
        removed = 0
        if not rec['malformed']:
            pts = ring_points(rec)
            if len(pts) < 2 or pts[0] != pts[-1]:
                flags.append('OPEN_RING')
            else:
                pts = pts[:-1]
            pts, removed = dedupe_cycle(pts)
            if len(pts) < 3:
                flags.append('TOO_FEW_VERTICES')
            elif self_intersecting(pts):
                flags.append('SELF_INTERSECTING')
            elif shoelace(pts) == 0:
                flags.append('ZERO_AREA')
            else:
                ring = pts
        if flags:
            quarantined.append({'book': rec['book'],
                                'code': min(flags, key=lambda c: prec_rank[c]),
                                'id': pid, 'rev': rec['rev']})
            continue
        collapsed += removed
        ring = apply_transform(transform_for(datums, rec['datum'], rec['book']),
                               ring)
        if shoelace(ring) < 0:
            reoriented += 1
            ring.reverse()
        clean.append({'id': pid, 'rec': rec, 'ring': ring})

    ranked = sorted(clean, key=lambda it: (-it['rec']['book'], it['id']))
    boxes = []
    for item in ranked:
        xs = [float(p[0]) for p in item['ring']]
        ys = [float(p[1]) for p in item['ring']]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    adj = bbox_neighbours(boxes)

    parcels = []
    eclipsed = []
    for rank, item in enumerate(ranked):
        pid = item['id']
        mine = item['ring']
        others = [ranked[j]['ring'] for j in sorted(adj[rank]) if j < rank
                  and polys_overlap(mine, ranked[j]['ring'])]
        claimed, mom_x, mom_y = claim_moments(mine, others)
        if claimed == 0:
            eclipsed.append(pid)
            continue
        use = uses[item['rec']['use']]
        centroid = (mom_x / claimed, mom_y / claimed)
        parcels.append({
            'id': pid,
            'book': item['rec']['book'],
            'rev': item['rec']['rev'],
            'use': item['rec']['use'],
            'segment': use['segment'],
            'area': abs(shoelace(mine)) / 2,
            'claimed': claimed,
            'base': claimed * Fraction(use['weight']),
            'centroid': centroid,
            'region': region_of(centroid[0] - ox, centroid[1] - oy,
                                origin_region),
        })
    parcels.sort(key=lambda p: p['id'])
    eclipsed.sort()

    book_numbers = sorted({b['book'] for b in books})
    latest = book_numbers[-1]
    ruleset = None
    for rules in tables['policy']['rulesets']:
        if rules['from_book'] <= latest:
            if ruleset is None or rules['from_book'] > ruleset['from_book']:
                ruleset = rules
    method = ruleset['method']
    house_size = ruleset['house_size']
    levy_total = ruleset['levy_total_cents']

    region_base = {r: Fraction(0) for r in REGIONS}
    region_area = {r: Fraction(0) for r in REGIONS}
    for parcel in parcels:
        region_base[parcel['region']] += parcel['base']
        region_area[parcel['region']] += parcel['claimed']

    eligible, seats, awards = apportion(method, house_size,
                                        ruleset['minimum_seats'],
                                        region_base, order)
    rank = {r: i for i, r in enumerate(order)}
    region_levy = largest_remainder(levy_total, seats, order, rank)
    quotas = {r: Fraction(levy_total * seats[r], house_size) for r in order}

    parcel_levy = {}
    for region in order:
        members = sorted(p['id'] for p in parcels if p['region'] == region)
        weights = {p['id']: p['base'] for p in parcels
                   if p['region'] == region}
        parcel_levy.update(largest_remainder(
            region_levy[region], weights, members,
            {m: i for i, m in enumerate(members)}))

    os.makedirs(out_dir, exist_ok=True)

    def write(name, payload):
        with open(os.path.join(out_dir, name), 'w') as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write('\n')

    write('summary.json', {
        'active': len(parcels),
        'books': book_numbers,
        'eclipsed': len(eclipsed),
        'house_size': house_size,
        'levy_cents': {r: region_levy[r] for r in order},
        'method': method,
        'quarantined': len(quarantined),
        'records': len(records),
        'ruleset': ruleset['id'],
        'seats': {r: seats[r] for r in order},
        'superseded': len(superseded),
        'total_area': str(sum((region_area[r] for r in REGIONS), Fraction(0))),
        'total_base': str(sum((region_base[r] for r in REGIONS), Fraction(0))),
        'voided': sum(1 for pid in winners if winners[pid]['kind'] == 'VOID'),
    })

    write('policy_audit.json', {
        'awards': awards,
        'eligible': eligible,
        'house_size': house_size,
        'levy_total_cents': levy_total,
        'method': method,
        'minimum_seats': ruleset['minimum_seats'],
        'region_quotas': {r: str(quotas[r]) for r in order},
        'ruleset': ruleset['id'],
    })

    counts = {code: 0 for code in precedence}
    for item in quarantined:
        counts[item['code']] += 1
    write('data_quality.json', {
        'counts': counts,
        'eclipsed': eclipsed,
        'quarantined': sorted(quarantined, key=lambda q: q['id']),
        'repairs': {'collapsed_vertices': collapsed, 'reoriented': reoriented},
        'superseded': sorted(
            [{'book': r['book'], 'id': r['id'], 'kind': r['kind'],
              'rev': r['rev']} for r in superseded],
            key=lambda r: (r['id'], r['book'], r['rev'])),
        'voided': sorted(pid for pid in winners
                         if winners[pid]['kind'] == 'VOID'),
    })

    for region in REGIONS:
        members = [p for p in parcels if p['region'] == region]
        write('region_%s.json' % region, {
            'area': str(region_area[region]),
            'base': str(region_base[region]),
            'levy_cents': region_levy[region],
            'parcels': [{
                'area': str(p['area']),
                'base': str(p['base']),
                'book': p['book'],
                'centroid': [str(p['centroid'][0]), str(p['centroid'][1])],
                'claimed': str(p['claimed']),
                'id': p['id'],
                'levy_cents': parcel_levy[p['id']],
                'rev': p['rev'],
                'segment': p['segment'],
                'use': p['use'],
            } for p in members],
            'region': region,
            'seats': seats[region],
        })

    for segment in SEGMENTS:
        members = [p for p in parcels if p['segment'] == segment]
        by_region = {}
        for region in REGIONS:
            part = [p for p in members if p['region'] == region]
            by_region[region] = {
                'base': str(sum((p['base'] for p in part), Fraction(0))),
                'levy_cents': sum(parcel_levy[p['id']] for p in part),
                'parcels': len(part),
            }
        write('segment_%s.json' % segment, {
            'area': str(sum((p['claimed'] for p in members), Fraction(0))),
            'base': str(sum((p['base'] for p in members), Fraction(0))),
            'by_region': by_region,
            'levy_cents': sum(parcel_levy[p['id']] for p in members),
            'parcel_count': len(members),
            'segment': segment,
        })


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: derive_report.py DATA_DIR OUT_DIR\n')
        return 2
    run(argv[1], argv[2])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
