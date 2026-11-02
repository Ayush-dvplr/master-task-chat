#!/usr/bin/env python3
"""Thornvale cadastral levy engine.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

Reads every survey book (*.svy) and the five policy tables in DATA_DIR,
reconciles parcel revisions, converts each surviving ring into the TVG grid
with exact rational arithmetic, quarantines defective records, settles
overlapping claims to land (the latest book claims first), apportions levy seats between the four districts by the divisor method in force and
splits the levy in whole cents. Nine JSON reports are written to OUT_DIR.

Rules reproduce the ledgers of the retired board engine kept in the archive.
Only the standard library is used and every value is an exact Fraction.
"""

from __future__ import annotations

import heapq
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

DISTRICTS = ("North", "East", "South", "West")
SEGMENTS = ("commercial", "public")


def frac_text(value) -> str:
    return str(Fraction(value))


# ------------------------------------------------------------------ tables


class Datum:
    """An affine map X = a x + b y + c, Y = d x + e y + f with revisions."""

    def __init__(self, row):
        self.base = self._coefficients(row["transform"])
        self.revisions = sorted(
            (int(item["from_book"]), self._coefficients(item["transform"])) for item in row["revisions"]
        )

    @staticmethod
    def _coefficients(block):
        return [Fraction(str(block[key])) for key in ("a", "b", "c", "d", "e", "f")]

    def for_book(self, book_seq):
        # a revision applies from its from_book onward, inclusive.
        chosen = self.base
        for start, coeffs in self.revisions:
            if start <= book_seq:
                chosen = coeffs
        return chosen

    @staticmethod
    def project(coeffs, point):
        a, b, c, d, e, f = coeffs
        x, y = point
        return (a * x + b * y + c, d * x + e * y + f)


class Policy:
    def __init__(self, data_dir: Path):
        load = lambda name: json.loads((data_dir / name).read_text(encoding="utf-8"))
        self.datums = {row["code"]: Datum(row) for row in load("datums.json")["datums"]}
        self.uses = {
            row["code"]: (row["segment"], Fraction(str(row["weight"]))) for row in load("land_use.json")["uses"]
        }
        regions = load("regions.json")
        self.origin = (Fraction(str(regions["origin"]["x"])), Fraction(str(regions["origin"]["y"])))
        self.order = list(regions["order"])
        self.origin_region = regions["origin_region"]
        self.rulesets = load("policy.json")["rulesets"]
        self.precedence = list(load("quality.json")["precedence"])

    def ruleset_for(self, last_book):
        # the ruleset in force is the one with the greatest
        # from_book that does not exceed the highest book in the export.
        candidates = [rs for rs in self.rulesets if int(rs["from_book"]) <= last_book]
        return max(candidates, key=lambda rs: int(rs["from_book"]))


# ------------------------------------------------------------------ books


class Record:
    __slots__ = ("kind", "pid", "rev", "use", "datum", "book", "book_datum", "points", "spoiled")

    def __init__(self, kind, pid, rev, use=None, datum=None):
        self.kind = kind
        self.pid = pid
        self.rev = rev
        self.use = use
        self.datum = datum
        self.book = None
        self.book_datum = None
        self.points = []
        self.spoiled = False

    @property
    def rank(self):
        # equal revisions are settled by the later book.
        return (self.rev, self.book)


DIGITS = frozenset("0123456789")


def _digits(text):
    return bool(text) and set(text) <= DIGITS


def read_number(token):
    """Fraction for a number spelled as the retired engine accepts, None for any other spelling."""
    body = token[1:] if token.startswith("-") else token
    if "/" in body:
        top, bottom = body.split("/", 1)
        if _digits(top) and _digits(bottom) and int(bottom) != 0:
            return Fraction(token)
        return None
    whole, dot, part = body.partition(".")
    if _digits(whole) and (not dot or _digits(part)):
        return Fraction(token)
    return None


class SurveyBook:
    def __init__(self):
        self.seq = None
        self.datum = None
        self.records = []

    def seal(self):
        for rec in self.records:
            rec.book = self.seq
            rec.book_datum = self.datum


def read_books(text: str):
    """Every book in one file; a banner line opens the next book."""
    books = []
    book = None
    open_record = None
    for line in text.splitlines():
        words = line.partition("#")[0].split()
        if not words:
            continue
        head = words[0]
        if head == "THORNVALE":
            book = SurveyBook()
            books.append(book)
        elif head == "BOOK":
            book.seq = int(words[1])
        elif head == "DATUM" and open_record is None:
            book.datum = words[1]
        elif head == "PARCEL":
            fields = dict(zip(words[2::2], words[3::2]))
            open_record = Record("PARCEL", words[1], int(fields["REV"]), fields.get("USE"), fields.get("DATUM"))
        elif head in ("V", "D"):
            pair = [read_number(word) for word in words[1:3]]
            if None in pair:
                open_record.spoiled = True
            if open_record.spoiled:
                continue
            if head == "V" or not open_record.points:
                open_record.points.append(tuple(pair))
            else:
                # a delta is measured from the previous vertex.
                px, py = open_record.points[-1]
                open_record.points.append((px + pair[0], py + pair[1]))
        elif head == "END":
            book.records.append(open_record)
            open_record = None
        elif head == "VOID":
            fields = dict(zip(words[2::2], words[3::2]))
            book.records.append(Record("VOID", words[1], int(fields["REV"])))
    for each in books:
        each.seal()
    return books


# ------------------------------------------------------------------ geometry


class Ring:
    def __init__(self, listed):
        self.listed = list(listed)
        self.closed = len(self.listed) >= 2 and self.listed[0] == self.listed[-1]
        body = self.listed[:-1] if self.closed else list(self.listed)
        clean = []
        for pt in body:
            if clean and clean[-1] == pt:
                continue
            clean.append(pt)
        while len(clean) > 1 and clean[0] == clean[-1]:
            clean.pop()
        self.vertices = clean

    @property
    def dropped(self):
        # repeated vertices are collapsed and counted as repairs.
        return len(self.listed) - 1 - len(self.vertices)

    @staticmethod
    def signed_double_area(pts):
        total = Fraction(0)
        for i, (x0, y0) in enumerate(pts):
            x1, y1 = pts[(i + 1) % len(pts)]
            total += x0 * y1 - x1 * y0
        return total

    @staticmethod
    def _turn(o, a, b):
        cross = (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        return 0 if cross == 0 else (1 if cross > 0 else -1)

    @staticmethod
    def _on_segment(a, b, p):
        return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])

    @classmethod
    def _segments_meet(cls, a, b, c, d):
        t1, t2 = cls._turn(a, b, c), cls._turn(a, b, d)
        t3, t4 = cls._turn(c, d, a), cls._turn(c, d, b)
        if t1 != t2 and t3 != t4 and 0 not in (t1, t2, t3, t4):
            return True
        if t1 == 0 and cls._on_segment(a, b, c):
            return True
        if t2 == 0 and cls._on_segment(a, b, d):
            return True
        if t3 == 0 and cls._on_segment(c, d, a):
            return True
        if t4 == 0 and cls._on_segment(c, d, b):
            return True
        return False

    def self_intersects(self):
        pts = self.vertices
        count = len(pts)
        edges = [(pts[i], pts[(i + 1) % count]) for i in range(count)]
        for i in range(count):
            for j in range(i + 1, count):
                neighbours = j == i + 1 or (i == 0 and j == count - 1)
                if neighbours:
                    continue
                if self._segments_meet(edges[i][0], edges[i][1], edges[j][0], edges[j][1]):
                    return True
        return False

    def defects(self):
        found = set()
        if not self.closed:
            found.add("OPEN_RING")
        if len(self.vertices) < 3:
            found.add("TOO_FEW_VERTICES")
        elif len(self.vertices) >= 4 and self.self_intersects():
            found.add("SELF_INTERSECTING")
        elif self.signed_double_area(self.vertices) == 0:
            found.add("ZERO_AREA")
        return found


def _plain(value):
    """Whole fractions become ints, which keeps the band sweep cheap."""
    if isinstance(value, Fraction) and value.denominator == 1:
        return int(value)
    return value


def _ratio(num, den):
    return _plain(Fraction(num) / den)


class Footprint:
    """A simple counter-clockwise polygon on the grid."""

    def __init__(self, pts, frame=None):
        self.pts = [(_plain(x), _plain(y)) for x, y in pts]
        xs = [p[0] for p in self.pts]
        ys = [p[1] for p in self.pts]
        self.box = (min(xs), max(xs), min(ys), max(ys))
        # (datum coefficients, footprint of the ring as surveyed) when known
        self.frame = frame

    def meets(self, other):
        a, b = self.box, other.box
        return a[0] <= b[1] and b[0] <= a[1] and a[2] <= b[3] and b[2] <= a[3]

    def whole(self):
        """Area and centroid of the polygon when nothing overlaps it."""
        double = mx = my = 0
        count = len(self.pts)
        for i in range(count):
            (x0, y0), (x1, y1) = self.pts[i], self.pts[(i + 1) % count]
            cross = x0 * y1 - x1 * y0
            double += cross
            mx += (x0 + x1) * cross
            my += (y0 + y1) * cross
        return Fraction(double) / 2, (Fraction(mx) / (3 * double), Fraction(my) / (3 * double))

    def rectangle(self):
        """(left, right, bottom, top) when the polygon is an upright rectangle."""
        if len(self.pts) != 4:
            return None
        for i in range(4):
            p, q = self.pts[i], self.pts[(i + 1) % 4]
            if p[0] != q[0] and p[1] != q[1]:
                return None
        return self.box

    def slanted_edges(self, rank):
        """Edges that are not horizontal, as (low y, high y, x at low y, dx per dy, rank)."""
        out = []
        count = len(self.pts)
        for i in range(count):
            p, q = self.pts[i], self.pts[(i + 1) % count]
            if p[1] == q[1]:
                continue
            if p[1] > q[1]:
                p, q = q, p
            out.append((p[1], q[1], p[0], _ratio(q[0] - p[0], q[1] - p[1]), rank))
        return out


def _x_on(edge, y):
    if edge[3] == 0:
        return edge[2]
    return edge[2] + edge[3] * (y - edge[0])


class StallSweep:
    """Settles a cluster of upright rectangles, listed in claim order.

    A line sweeps upward. The x axis is cut at every rectangle side; each cut
    cell belongs to the earliest rectangle covering it at the current height,
    and every rectangle collects the width it owns between events lazily.
    """

    def __init__(self, boxes):
        self.unit = math.lcm(*(Fraction(v).denominator for box in boxes for v in box))
        self.boxes = [tuple(int(v * self.unit) for v in box) for box in boxes]

    def run(self):
        boxes = self.boxes
        count = len(boxes)
        cuts = sorted({v for box in boxes for v in box[:2]})
        index = {v: i for i, v in enumerate(cuts)}
        width = [cuts[i + 1] - cuts[i] for i in range(len(cuts) - 1)]
        squares = [cuts[i + 1] ** 2 - cuts[i] ** 2 for i in range(len(cuts) - 1)]
        holder = [None] * len(width)
        waiting = [[] for _ in width]
        open_now = [False] * count
        held = [0] * count
        held_sq = [0] * count
        mark = [0] * count
        totals = [[0, 0, 0] for _ in range(count)]

        def settle_to(rank, y):
            step = y - mark[rank]
            if step and held[rank]:
                total = totals[rank]
                total[0] += held[rank] * step
                total[1] += held_sq[rank] * step
                total[2] += held[rank] * (y * y - mark[rank] * mark[rank])
            mark[rank] = y

        def move(cell, old, new, y):
            if old is not None:
                settle_to(old, y)
                held[old] -= width[cell]
                held_sq[old] -= squares[cell]
            if new is not None:
                settle_to(new, y)
                held[new] += width[cell]
                held_sq[new] += squares[cell]
            holder[cell] = new

        events = [(box[2], 1, rank) for rank, box in enumerate(boxes)]
        events += [(box[3], 0, rank) for rank, box in enumerate(boxes)]
        for y, opening, rank in sorted(events):
            box = boxes[rank]
            cells = range(index[box[0]], index[box[1]])
            if opening:
                open_now[rank] = True
                mark[rank] = y
                for cell in cells:
                    heapq.heappush(waiting[cell], rank)
                    if holder[cell] is None or rank < holder[cell]:
                        move(cell, holder[cell], rank, y)
                continue
            open_now[rank] = False
            for cell in cells:
                if holder[cell] != rank:
                    continue
                queue = waiting[cell]
                while queue and not open_now[queue[0]]:
                    heapq.heappop(queue)
                move(cell, rank, queue[0] if queue else None, y)
        unit = self.unit
        out = []
        for area, sq, ysq in totals:
            if area == 0:
                out.append((Fraction(0), None))
                continue
            out.append((Fraction(area, unit * unit),
                        (Fraction(sq, 2 * area * unit), Fraction(ysq, 2 * area * unit))))
        return out


class Patchwork:
    """Settles the claims of footprints listed in claim order.

    Footprints whose boxes touch form a cluster, and each cluster is cut into
    horizontal bands once. Every stretch of a band belongs to the earliest
    footprint covering it, so later footprints only keep what nobody before
    them holds.
    """

    def __init__(self, footprints):
        self.footprints = footprints

    def clusters(self):
        shapes = self.footprints
        parent = list(range(len(shapes)))

        def root(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        live = []
        for i in sorted(range(len(shapes)), key=lambda k: shapes[k].box[2]):
            low = shapes[i].box[2]
            live = [j for j in live if shapes[j].box[3] >= low]
            for j in live:
                if root(i) != root(j) and shapes[i].meets(shapes[j]):
                    parent[root(i)] = root(j)
            live.append(i)
        groups = {}
        for i in range(len(shapes)):
            groups.setdefault(root(i), []).append(i)
        return list(groups.values())

    def settle(self):
        """One (claimed area, claimed centroid or None) per footprint, in claim order."""
        result = [None] * len(self.footprints)
        for members in self.clusters():
            uprights = [self.footprints[m].rectangle() for m in members]
            if len(members) == 1:
                result[members[0]] = self.footprints[members[0]].whole()
            elif all(uprights):
                for rank, value in zip(members, StallSweep(uprights).run()):
                    result[rank] = value
            elif self._shared_frame(members):
                for rank, value in zip(members, self._in_frame(members)):
                    result[rank] = value
            else:
                for rank, value in self._bands(members).items():
                    result[rank] = value
        return result

    def _shared_frame(self, members):
        """True when every member was surveyed on one datum as an upright rectangle."""
        frames = [self.footprints[m].frame for m in members]
        if any(frame is None for frame in frames):
            return False
        coeffs = frames[0][0]
        return all(frame[0] == coeffs and frame[1].rectangle() for frame in frames)

    def _in_frame(self, members):
        # An affine map keeps overlaps, differences and area ratios, so the
        # cluster is settled where it was surveyed and mapped onto the grid.
        coeffs = self.footprints[members[0]].frame[0]
        a, b, _, d, e, _ = coeffs
        scale = abs(a * e - b * d)
        settled = StallSweep([self.footprints[m].frame[1].rectangle() for m in members]).run()
        out = []
        for area, centre in settled:
            if centre is None:
                out.append((area * scale, None))
            else:
                out.append((area * scale, Datum.project(coeffs, centre)))
        return out

    def _levels(self, members, edges):
        levels = {p[1] for rank in members for p in self.footprints[rank].pts}
        by_slope = {}
        for edge in edges:
            by_slope.setdefault(edge[3], []).append(edge)
        slopes = list(by_slope)
        for i, ke in enumerate(slopes):
            for kf in slopes[i + 1:]:
                for e in by_slope[ke]:
                    for f in by_slope[kf]:
                        if e[4] == f[4] or e[1] < f[0] or f[1] < e[0]:
                            continue
                        y = _ratio(f[2] - e[2] + ke * e[0] - kf * f[0], ke - kf)
                        if max(e[0], f[0]) <= y <= min(e[1], f[1]):
                            levels.add(y)
        return sorted(levels)

    def _bands(self, members):
        edges = []
        for rank in members:
            edges.extend(self.footprints[rank].slanted_edges(rank))
        levels = self._levels(members, edges)
        edges.sort(key=lambda e: e[0])
        sums = {rank: [0, 0, 0] for rank in members}
        active = []
        nxt = 0
        for y0, y1 in zip(levels, levels[1:]):
            while nxt < len(edges) and edges[nxt][0] <= y0:
                active.append(edges[nxt])
                nxt += 1
            active = [e for e in active if e[1] > y0]
            mid = _plain(Fraction(y0 + y1) / 2)
            height = y1 - y0
            rows = sorted(((_x_on(e, mid), e) for e in active), key=lambda row: row[0])
            inside = set()
            queue = []
            for i in range(len(rows) - 1):
                rank = rows[i][1][4]
                if rank in inside:
                    inside.discard(rank)
                else:
                    inside.add(rank)
                    heapq.heappush(queue, rank)
                while queue and queue[0] not in inside:
                    heapq.heappop(queue)
                width_mid = rows[i + 1][0] - rows[i][0]
                if not queue or width_mid == 0:
                    continue
                left, right = rows[i][1], rows[i + 1][1]
                l0, r0 = _x_on(left, y0), _x_on(right, y0)
                l1, r1 = _x_on(left, y1), _x_on(right, y1)
                lm, rm = rows[i][0], rows[i + 1][0]
                acc = sums[queue[0]]
                acc[0] += height * width_mid
                acc[1] += height * (y0 * (r0 - l0) + 2 * (y0 + y1) * width_mid + y1 * (r1 - l1))
                acc[2] += height * (r0 * r0 - l0 * l0 + 4 * (rm * rm - lm * lm) + r1 * r1 - l1 * l1)
        out = {}
        for rank, (area, my6, mx12) in sums.items():
            area = Fraction(area)
            if area == 0:
                out[rank] = (area, None)
            else:
                out[rank] = (area, (Fraction(mx12) / 12 / area, Fraction(my6) / 6 / area))
        return out


class Parcel:
    def __init__(self, record, coeffs, policy: Policy):
        self.record = record
        ring = Ring(record.points)
        grid = [Datum.project(coeffs, pt) for pt in ring.vertices]
        double = Ring.signed_double_area(grid)
        self.reoriented = double < 0
        if self.reoriented:
            grid = grid[::-1]
            double = -double
        self.dropped = ring.dropped
        self.area = double / 2
        self.footprint = Footprint(grid, (list(coeffs), Footprint(ring.vertices)))
        self.segment, self.weight = policy.uses[record.use]
        self.claimed = Fraction(0)
        self.base = Fraction(0)
        self.centroid = None
        self.district = None
        self.cents = 0

    def settle(self, claimed, centroid, policy: Policy):
        self.claimed = claimed
        self.base = claimed * self.weight
        self.centroid = centroid
        self.district = self._district(policy)

    def _district(self, policy: Policy):
        dx = self.centroid[0] - policy.origin[0]
        dy = self.centroid[1] - policy.origin[1]
        if dx == 0 and dy == 0:
            return policy.origin_region
        if abs(dy) > abs(dx):
            return "North" if dy > 0 else "South"
        if abs(dx) > abs(dy):
            return "East" if dx > 0 else "West"
        # exact diagonals turn clockwise to the next district.
        diagonal = {(1, 1): "East", (1, -1): "South", (-1, -1): "West", (-1, 1): "North"}
        return diagonal[(1 if dx > 0 else -1, 1 if dy > 0 else -1)]

    def row(self):
        rec = self.record
        return {
            "id": rec.pid,
            "rev": rec.rev,
            "book": rec.book,
            "use": rec.use,
            "segment": self.segment,
            "area": frac_text(self.area),
            "claimed": frac_text(self.claimed),
            "base": frac_text(self.base),
            "centroid": [frac_text(self.centroid[0]), frac_text(self.centroid[1])],
            "levy_cents": self.cents,
        }


# ------------------------------------------------------------------ apportionment


def hamilton(total_cents, weights, tie_rank):
    """Largest remainder split of an integer total in proportion to weights."""
    whole = sum(weights.values(), Fraction(0))
    if whole == 0:
        return {key: 0 for key in weights}
    shares = {key: total_cents * w / whole for key, w in weights.items()}
    result = {key: share.numerator // share.denominator for key, share in shares.items()}
    remaining = total_cents - sum(result.values())
    ranking = sorted(weights, key=lambda key: (result[key] - shares[key], tie_rank(key)))
    for key in ranking[:remaining]:
        result[key] += 1
    return result


class Apportioner:
    INFINITE = "inf"

    def __init__(self, method, house, minimum, bases, order):
        self.method = method
        self.house = house
        self.minimum = minimum
        self.bases = bases
        self.order = order
        self.eligible = [name for name in order if bases[name] > 0]
        self.seats = {name: 0 for name in DISTRICTS}
        for name in self.eligible:
            self.seats[name] = minimum
        self.awards = []

    def priority(self, name):
        held = self.seats[name]
        base = self.bases[name]
        if self.method == "jefferson":
            return False, base / (held + 1)
        if self.method == "webster":
            return False, base / (Fraction(2 * held + 1, 2))
        if held == 0:
            return True, None
        return False, base * base / (held * (held + 1))

    def _beats(self, left, right):
        (inf_l, val_l, name_l), (inf_r, val_r, name_r) = left, right
        if inf_l != inf_r:
            return inf_l
        if not inf_l and val_l != val_r:
            return val_l > val_r
        if self.bases[name_l] != self.bases[name_r]:
            return self.bases[name_l] > self.bases[name_r]
        return self.order.index(name_l) < self.order.index(name_r)

    def run(self):
        if not self.eligible:
            return self
        free = self.house - self.minimum * len(self.eligible)
        for number in range(1, max(0, free) + 1):
            leader = None
            for name in self.eligible:
                is_inf, value = self.priority(name)
                entry = (is_inf, value, name)
                if leader is None or self._beats(entry, leader):
                    leader = entry
            is_inf, value, name = leader
            self.seats[name] += 1
            self.awards.append(
                {
                    "seat": number,
                    "region": name,
                    "priority": self.INFINITE if is_inf else frac_text(value),
                    "seats_after": self.seats[name],
                }
            )
        return self


# ------------------------------------------------------------------ engine


class LevyEngine:
    def __init__(self, data_dir: Path):
        self.policy = Policy(data_dir)
        self.books = [book for path in sorted(data_dir.glob("*.svy")) for book in read_books(path.read_text(encoding="utf-8"))]

    def reconcile(self):
        latest = {}
        losers = []
        all_records = [rec for book in self.books for rec in book.records]
        for rec in all_records:
            held = latest.get(rec.pid)
            if held is None or rec.rank > held.rank:
                if held is not None:
                    losers.append(held)
                latest[rec.pid] = rec
            else:
                losers.append(rec)
        losers.sort(key=lambda r: (r.pid, r.book, r.rev))
        return all_records, latest, losers

    def classify(self, rec):
        # a misspelt number spoils the vertex list, so no ring check can run on it
        problems = {"MALFORMED_NUMBER"} if rec.spoiled else Ring(rec.points).defects()
        effective = rec.datum or rec.book_datum
        if effective not in self.policy.datums:
            problems.add("UNKNOWN_DATUM")
        if rec.use not in self.policy.uses:
            problems.add("UNKNOWN_USE")
        for code in self.policy.precedence:
            if code in problems:
                return code
        return None

    def build(self):
        pol = self.policy
        all_records, latest, losers = self.reconcile()
        voided = sorted(pid for pid, rec in latest.items() if rec.kind == "VOID")
        held_back = []
        tally = {code: 0 for code in pol.precedence}
        parcels = []
        for pid in sorted(latest):
            rec = latest[pid]
            if rec.kind == "VOID":
                continue
            code = self.classify(rec)
            if code is not None:
                tally[code] += 1
                held_back.append({"id": pid, "rev": rec.rev, "book": rec.book, "code": code})
                continue
            coeffs = pol.datums[rec.datum or rec.book_datum].for_book(rec.book)
            parcels.append(Parcel(rec, coeffs, pol))

        # claims run from the highest book down, then by identifier.
        claim_order = sorted(parcels, key=lambda p: (-p.record.book, p.record.pid))
        settled = Patchwork([p.footprint for p in claim_order]).settle()
        eclipsed = []
        for parcel, (claimed, centroid) in zip(claim_order, settled):
            if claimed == 0:
                eclipsed.append(parcel.record.pid)
            else:
                parcel.settle(claimed, centroid, pol)
        standing = parcels
        parcels = [p for p in standing if p.claimed > 0]
        eclipsed.sort()

        book_seqs = sorted(book.seq for book in self.books)
        ruleset = pol.ruleset_for(book_seqs[-1])
        method = ruleset["method"]
        house = int(ruleset["house_size"])
        minimum = int(ruleset["minimum_seats"])
        levy = int(ruleset["levy_total_cents"])

        per_district = {name: [p for p in parcels if p.district == name] for name in DISTRICTS}
        bases = {name: sum((p.base for p in rows), Fraction(0)) for name, rows in per_district.items()}
        areas = {name: sum((p.claimed for p in rows), Fraction(0)) for name, rows in per_district.items()}
        app = Apportioner(method, house, minimum, bases, pol.order).run()
        seats = app.seats

        district_cents = hamilton(levy, {name: Fraction(seats[name]) for name in DISTRICTS}, pol.order.index)
        for name, rows in per_district.items():
            if not rows:
                continue
            split = hamilton(district_cents[name], {p.record.pid: p.base for p in rows}, lambda pid: pid)
            for p in rows:
                p.cents = split[p.record.pid]

        reports = {}
        reports["summary.json"] = {
            "books": book_seqs,
            "ruleset": ruleset["id"],
            "method": method,
            "house_size": house,
            "records": len(all_records),
            "superseded": len(losers),
            "voided": len(voided),
            "quarantined": len(held_back),
            "active": len(parcels),
            "eclipsed": len(eclipsed),
            "total_area": frac_text(sum((p.claimed for p in parcels), Fraction(0))),
            "total_base": frac_text(sum((p.base for p in parcels), Fraction(0))),
            "seats": {name: seats[name] for name in DISTRICTS},
            "levy_cents": {name: district_cents[name] for name in DISTRICTS},
        }
        reports["policy_audit.json"] = {
            "ruleset": ruleset["id"],
            "method": method,
            "house_size": house,
            "minimum_seats": minimum,
            "levy_total_cents": levy,
            "eligible": app.eligible,
            "awards": app.awards,
            "region_quotas": {name: frac_text(Fraction(levy * seats[name], house)) for name in DISTRICTS},
        }
        reports["data_quality.json"] = {
            "quarantined": held_back,
            "counts": tally,
            "repairs": {
                "reoriented": sum(1 for p in standing if p.reoriented),
                "collapsed_vertices": sum(p.dropped for p in standing),
            },
            "voided": voided,
            "eclipsed": eclipsed,
            "superseded": [{"id": r.pid, "rev": r.rev, "book": r.book, "kind": r.kind} for r in losers],
        }
        for name in DISTRICTS:
            rows = per_district[name]
            reports["region_%s.json" % name] = {
                "region": name,
                "seats": seats[name],
                "levy_cents": district_cents[name],
                "area": frac_text(areas[name]),
                "base": frac_text(bases[name]),
                "parcels": [p.row() for p in rows],
            }
        for seg in SEGMENTS:
            rows = [p for p in parcels if p.segment == seg]
            breakdown = {}
            for name in DISTRICTS:
                part = [p for p in rows if p.district == name]
                breakdown[name] = {
                    "parcels": len(part),
                    "base": frac_text(sum((p.base for p in part), Fraction(0))),
                    "levy_cents": sum(p.cents for p in part),
                }
            reports["segment_%s.json" % seg] = {
                "segment": seg,
                "parcel_count": len(rows),
                "area": frac_text(sum((p.claimed for p in rows), Fraction(0))),
                "base": frac_text(sum((p.base for p in rows), Fraction(0))),
                "by_region": breakdown,
                "levy_cents": sum(p.cents for p in rows),
            }
        return reports


def main(argv) -> int:
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = Path(argv[1]), Path(argv[2])
    reports = LevyEngine(data_dir).build()
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(reports):
        text = json.dumps(reports[name], indent=2, sort_keys=True) + "\n"
        (out_dir / name).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
