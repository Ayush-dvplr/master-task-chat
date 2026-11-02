#!/usr/bin/env python3
"""Grading suite for caldermoor-commitment-closure.

The verifier owns its own extract generator and its own implementation of the
protocol. It rebuilds the shipped extract from its seed, recomputes every
deliverable, and compares the delivered bytes against that. It also builds
three further extracts from seeds that exist only in this file and runs the
delivered program against them, so a figure lifted from the shipped extract
fails on inputs the agent never saw.

Nothing here reads the agent corpus directory. Every extract this file grades
against is written into a temporary directory it creates itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import unicodedata
import threading
from pathlib import Path
from rewardkit import criteria, criterion

# ---------------------------------------------------------------- time

_CUM = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 366]  # 2032 leap


def ymd_to_day(y: int, m: int, d: int) -> int:
    """Days since 2032-01-01. Only 2031..2033 are ever needed."""
    total = 0
    for yy in range(2032, y):
        total += 366 if _is_leap(yy) else 365
    for yy in range(y, 2032):
        total -= 366 if _is_leap(yy) else 365
    cum = (
        _CUM
        if _is_leap(y)
        else [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]
    )
    return total + cum[m - 1] + (d - 1)


def _is_leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def day_to_ymd(n: int) -> tuple[int, int, int]:
    y = 2032
    while True:
        span = 366 if _is_leap(y) else 365
        if n < 0:
            y -= 1
            n += 366 if _is_leap(y) else 365
            continue
        if n >= span:
            n -= span
            y += 1
            continue
        break
    cum = (
        _CUM
        if _is_leap(y)
        else [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]
    )
    m = 1
    for i in range(12):
        if cum[i] <= n < cum[i + 1]:
            m = i + 1
            break
    return y, m, n - cum[m - 1] + 1


def mk(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> int:
    """Instant in minutes since 2032-01-01T00:00Z."""
    return ymd_to_day(y, m, d) * 1440 + hh * 60 + mm


def fmt_instant(t: int) -> str:
    n, rem = divmod(t, 1440)
    y, m, d = day_to_ymd(n)
    return f"{y:04d}-{m:02d}-{d:02d}T{rem // 60:02d}:{rem % 60:02d}Z"


def parse_instant(s: str) -> int | None:
    s = (s or "").strip()
    if (
        len(s) != 17
        or s[4] != "-"
        or s[7] != "-"
        or s[10] != "T"
        or s[13] != ":"
        or s[16] != "Z"
    ):
        return None
    try:
        y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
        hh, mi = int(s[11:13]), int(s[14:16])
    except ValueError:
        return None
    if not (1 <= m <= 12 and 1 <= d <= 31 and 0 <= hh <= 23 and 0 <= mi <= 59):
        return None
    return mk(y, m, d, hh, mi)


def fmt_day(n: int) -> str:
    y, m, d = day_to_ymd(n)
    return f"{y:04d}-{m:02d}-{d:02d}"


# The commitment day boundary sits at 04:00Z, not UTC midnight.
DAY_OFFSET_MIN = 240


def commitment_day(t: int) -> int:
    return (t - DAY_OFFSET_MIN) // 1440


# ---------------------------------------------------------------- window

WINDOW_START = mk(2032, 3, 1)
WINDOW_END = mk(2032, 12, 1)

# ---------------------------------------------------------------- vocabularies

SOURCE_CLASSES = (
    "vault",
    "desk",
    "bridge",
    "partner",
    "mirror",
    "import",
    "relay",
    "legacy",
)

CLASS_RANK = {
    "vault": 6,
    "desk": 5,
    "bridge": 4,
    "partner": 3,
    "mirror": 2,
    "import": 1,
    "relay": 1,
    "legacy": 0,
}

# The one class whose state assertions resolve by the earliest instant inside
# its rank rather than the latest.
EARLIEST_CLASS = "desk"
# The journal class inverts wherever it competes. The bridge class is filed by a
# nightly sweep that walks its spool backwards, so it inverts for state rows
# and keeps the ordinary direction for commitment rows.
STATE_ONLY_EARLIEST = "bridge"

STATES = ("OPEN", "SETTLED", "DEFERRED", "WITHDRAWN")

LEGAL_TRANSITIONS = {
    ("OPEN", "SETTLED"),
    ("OPEN", "DEFERRED"),
    ("OPEN", "WITHDRAWN"),
    ("DEFERRED", "OPEN"),
    ("DEFERRED", "WITHDRAWN"),
}

EDGE_DROP_REASONS = ("EDGE_DANGLING", "EDGE_OUT_OF_SCOPE", "EDGE_SELF")

EFFORT_UNITS = {"minutes": 1, "hours": 60, "halfdays": 240}

EFFORT_FLOOR = 15
EFFORT_CEIL = 480

CATEGORIES = ("admin", "care", "errand", "finance", "study", "work")


# ---------------------------------------------------------------- normalization

_STRIP = ".-_'"


def fold(handle: str) -> str:
    """The documented comparison fold for principal and project references."""
    s = unicodedata.normalize("NFC", handle or "")
    s = s.strip().casefold()
    out = []
    prev_space = False
    for ch in s:
        if ch in _STRIP:
            continue
        if ch.isspace():
            if not prev_space:
                out.append(" ")
            prev_space = True
            continue
        prev_space = False
        out.append(ch)
    return "".join(out).strip()


def derive(seed: int, salt: str) -> int:
    h = hashlib.blake2b(f"{seed}:{salt}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "big")


# ---------------------------------------------------------------- universe

_GIVEN = (
    "alethea",
    "bramwell",
    "calder",
    "dorrity",
    "ellery",
    "fenwick",
    "gowan",
    "harlow",
    "isolde",
    "jarrow",
    "kesteven",
    "lorrimer",
    "merrick",
    "nessa",
    "orvald",
    "pemberly",
    "quillon",
    "rowan",
    "sable",
    "thurloe",
    "ulric",
    "verity",
    "wendell",
    "yarrow",
)

_FAMILY = (
    "ashcombe",
    "barrowfield",
    "clevedon",
    "dunmore",
    "eastmere",
    "fallowden",
    "gracehill",
    "hollinger",
    "inglewood",
    "jessamy",
    "kirkbride",
    "linthwaite",
    "marchbank",
    "netherby",
    "oakhanger",
    "pyrford",
    "quenby",
    "ravensworth",
    "sowerby",
    "tarrington",
)


def build_universe(seed: int) -> dict:
    """Actors, projects, cadences and the scoped alias graph."""
    rng = random.Random(derive(seed, "universe"))

    n_actors = 48
    actors = []
    used = set()
    for i in range(n_actors):
        while True:
            g = rng.choice(_GIVEN)
            f = rng.choice(_FAMILY)
            canon = f"{g}.{f}"
            if canon not in used:
                used.add(canon)
                break
        actors.append(
            {
                "actor_id": f"ACT-{i + 1:04d}",
                "canonical_handle": canon,
                "given": g,
                "family": f,
            }
        )

    # ---- projects, with a rename lineage and a two level hierarchy
    n_roots = 12
    roots = [f"PRJ-{100 + i}" for i in range(n_roots)]
    projects = {}
    for r in roots:
        projects[r] = {"code": r, "parent": "", "root": r}
    children = []
    for i, r in enumerate(roots):
        for k in range(rng.randint(2, 4)):
            c = f"PRJ-{200 + i * 10 + k}"
            projects[c] = {"code": c, "parent": r, "root": r}
            children.append(c)

    # Renames: old_code -> new_code effective at an instant inside the window.
    # A project reference resolves against the renames effective at or before
    # the observation instant, so a pre rename reference keeps the old code.
    renames = []
    rename_sources = rng.sample(children, 9)
    for idx, old in enumerate(rename_sources):
        new = f"PRJ-{400 + idx}"
        eff = WINDOW_START + rng.randrange(30 * 1440, 210 * 1440)
        projects[new] = {
            "code": new,
            "parent": projects[old]["parent"],
            "root": projects[old]["root"],
        }
        renames.append({"old_code": old, "new_code": new, "effective_at": eff})
    # one chained rename, so the lineage walk has to iterate rather than
    # look up a single hop
    first = renames[0]
    chained_new = "PRJ-450"
    projects[chained_new] = {
        "code": chained_new,
        "parent": projects[first["new_code"]]["parent"],
        "root": projects[first["new_code"]]["root"],
    }
    renames.append(
        {
            "old_code": first["new_code"],
            "new_code": chained_new,
            "effective_at": first["effective_at"] + 40 * 1440,
        }
    )
    renames.sort(key=lambda r: (r["effective_at"], r["old_code"]))

    # ---- scoped aliases
    aliases = []
    ambiguous_handles = []

    def add_alias(surface, target, start, end, cls, asserted_at):
        aliases.append(
            {
                "surface": surface,
                "target": target,
                "scope_start": start,
                "scope_end": end,
                "source_class": cls,
                "asserted_at": asserted_at,
            }
        )

    full_start, full_end = WINDOW_START, WINDOW_END

    for a in actors:
        canon = a["canonical_handle"]
        g, f = a["given"], a["family"]
        cls_pool = ("desk", "vault", "partner", "mirror", "import")

        # a whole window alias: behaves the same under both readings, so it is
        # a decoy for a solver that concludes scope never matters
        add_alias(
            f"{g[0]}.{f}", canon, full_start, full_end, rng.choice(cls_pool), full_start
        )

        # an email surface, also whole window
        add_alias(
            f"{g}.{f}@caldermoor.example",
            canon,
            full_start,
            full_end,
            rng.choice(cls_pool),
            full_start,
        )

        # a genuinely scoped alias: valid only for part of the window
        if rng.random() < 0.62:
            s = full_start + rng.randrange(0, 150 * 1440)
            e = s + rng.randrange(25 * 1440, 120 * 1440)
            e = min(e, full_end)
            add_alias(f"{f}.{g}", canon, s, e, rng.choice(cls_pool), s)

        # a retired historical handle: valid only early, and later reassigned
        if rng.random() < 0.30:
            e = full_start + rng.randrange(40 * 1440, 110 * 1440)
            add_alias(
                f"old-{f[:4]}{g[:2]}",
                canon,
                full_start,
                e,
                rng.choice(cls_pool),
                full_start,
            )

    # Historical handle reassignment. The same surface points at one actor
    # early and a different actor later, with the two scopes disjoint. Merging
    # globally fuses two real people into one.
    reassigned = []
    pool = list(range(n_actors))
    rng.shuffle(pool)
    for k in range(10):
        i, j = pool[2 * k], pool[2 * k + 1]
        surface = f"seat-{k + 1:02d}"
        cut = full_start + rng.randrange(60 * 1440, 180 * 1440)
        add_alias(
            surface, actors[i]["canonical_handle"], full_start, cut, "desk", full_start
        )
        add_alias(surface, actors[j]["canonical_handle"], cut, full_end, "desk", cut)
        reassigned.append(
            {
                "surface": surface,
                "early": actors[i]["actor_id"],
                "late": actors[j]["actor_id"],
                "cut": cut,
            }
        )

    # Genuinely ambiguous surfaces: two alias assertions with OVERLAPPING
    # scopes pointing at two different canonical handles, and no rule separates
    # them. Every reference observed inside the overlap is unresolvable.
    for k in range(6):
        i, j = pool[20 + 2 * k], pool[21 + 2 * k]
        surface = f"shared-{k + 1:02d}"
        s1 = full_start + rng.randrange(10 * 1440, 60 * 1440)
        e1 = s1 + 120 * 1440
        s2 = s1 + 30 * 1440
        e2 = s2 + 120 * 1440
        add_alias(
            surface, actors[i]["canonical_handle"], s1, min(e1, full_end), "partner", s1
        )
        add_alias(
            surface, actors[j]["canonical_handle"], s2, min(e2, full_end), "mirror", s2
        )
        ambiguous_handles.append(
            {
                "surface": surface,
                "overlap_start": s2,
                "overlap_end": min(e1, e2, full_end),
            }
        )

    # Two hop chains: surface -> intermediate -> canonical, where the two hops
    # carry different scopes, so the chain only resolves in the intersection.
    chains = []
    for k in range(30):
        a = actors[pool[(30 + k) % n_actors]]
        mid = f"mid-{k + 1:02d}"
        surface = f"ref-{k + 1:02d}"
        s1 = full_start + rng.randrange(0, 90 * 1440)
        e1 = s1 + rng.randrange(90 * 1440, 180 * 1440)
        s2 = s1 + rng.randrange(5 * 1440, 45 * 1440)
        e2 = s2 + rng.randrange(60 * 1440, 150 * 1440)
        add_alias(surface, mid, s1, min(e1, full_end), "import", s1)
        add_alias(mid, a["canonical_handle"], s2, min(e2, full_end), "vault", s2)
        chains.append(
            {
                "surface": surface,
                "mid": mid,
                "actor": a["actor_id"],
                "live_start": max(s1, s2),
                "live_end": min(e1, e2, full_end),
            }
        )

    # A cycle that reaches nothing canonical.
    add_alias("loop-a", "loop-b", full_start, full_end, "relay", full_start)
    add_alias("loop-b", "loop-c", full_start, full_end, "relay", full_start)
    add_alias("loop-c", "loop-a", full_start, full_end, "relay", full_start)

    aliases.sort(key=lambda r: (r["surface"], r["scope_start"], r["target"]))

    # ---- cadences
    cadences = []
    for k in range(24):
        a = actors[rng.randrange(n_actors)]
        period = rng.choice((7, 14, 21, 28))
        anchor = WINDOW_START + rng.randrange(0, 20) * 1440
        cadences.append(
            {
                "cadence_id": f"CAD-{k + 1:03d}",
                "period_days": period,
                "anchor_at": anchor,
                "obligor": a["canonical_handle"],
                "actor_id": a["actor_id"],
                "project": rng.choice(roots),
            }
        )

    return {
        "seed": seed,
        "actors": actors,
        "by_id": {a["actor_id"]: a for a in actors},
        "projects": projects,
        "roots": roots,
        "children": children,
        "renames": renames,
        "aliases": aliases,
        "reassigned": reassigned,
        "ambiguous": ambiguous_handles,
        "chains": chains,
        "cadences": cadences,
    }


# ---------------------------------------------------------------- resolution


class Resolver:
    """Scope bounded identity, project lineage and precedence resolution."""

    def __init__(self, aliases, roster_handles, projects, renames):
        self.by_surface: dict[str, list] = {}
        for a in aliases:
            self.by_surface.setdefault(fold(a["surface"]), []).append(a)
        for v in self.by_surface.values():
            v.sort(key=lambda r: (r["scope_start"], r["target"]))
        self.canonical = {fold(h): h for h in roster_handles}
        self.projects = projects
        self.renames = sorted(renames, key=lambda r: (r["effective_at"], r["old_code"]))

    def resolve_handle(self, surface: str, at: int):
        """Return (canonical_handle, hops) or (None, reason).

        Every hop is tested for scope membership at the SAME instant, and the
        interval is half open, so an assertion whose scope_end equals `at` does
        not apply.
        """
        start = fold(surface)
        if not start:
            return None, "UNKNOWN_PRINCIPAL", []
        if start in self.canonical:
            return self.canonical[start], "", [start]
        frontier = [(start, (start,))]
        seen_paths = set()
        reached: dict[str, tuple] = {}
        while frontier:
            node, path = frontier.pop(0)
            for a in self.by_surface.get(node, ()):
                if not (a["scope_start"] <= at < a["scope_end"]):
                    continue
                tgt = fold(a["target"])
                if tgt in path:
                    continue
                npath = path + (tgt,)
                if tgt in self.canonical:
                    reached.setdefault(self.canonical[tgt], npath)
                    continue
                key = (tgt, npath)
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                frontier.append((tgt, npath))
        if len(reached) == 1:
            h, path = next(iter(reached.items()))
            return h, "", list(path)
        if len(reached) > 1:
            return None, "AMBIGUOUS_IDENTITY", sorted(reached)
        return None, "UNKNOWN_PRINCIPAL", []

    def resolve_project(self, ref: str, at: int):
        """Walk the rename lineage using only renames effective at or before
        `at`. A reference observed before its rename keeps the old code."""
        code = (ref or "").strip()
        if not code:
            return None
        seen = set()
        moved = True
        while moved:
            moved = False
            for r in self.renames:
                if r["effective_at"] > at:
                    continue
                if r["old_code"] == code and code not in seen:
                    seen.add(code)
                    code = r["new_code"]
                    moved = True
                    break
        return code if code in self.projects else None

    def root_of(self, code: str) -> str:
        p = self.projects.get(code)
        return p["root"] if p else code


def precedence_key(
    source_class: str,
    observed_at: int,
    ident: str,
    earliest_class: str = EARLIEST_CLASS,
    kind: str = "commitment",
    state_only_class: str | None = STATE_ONLY_EARLIEST,
):
    """Sort key for choosing a winner among competing assertions.

    Higher rank wins. Inside a rank the latest instant wins, except for the
    journal class, which inverts wherever it competes, and the sweep class,
    which inverts for state rows alone.
    """
    rank = CLASS_RANK.get(source_class, -1)
    inverted = source_class == earliest_class or (
        kind == "state" and state_only_class is not None
        and source_class == state_only_class
    )
    if inverted:
        return (rank, -observed_at, ident)
    return (rank, observed_at, ident)


def clamp_effort(minutes: int) -> int:
    """Clamped per commitment, before any aggregation."""
    if minutes <= 0:
        return 0
    return max(EFFORT_FLOOR, min(EFFORT_CEIL, minutes))


def largest_remainder(weights: dict, total: int):
    """Distribute `total` across `weights` by largest remainder, breaking a
    remainder tie by ascending key."""
    if total <= 0 or not weights:
        return {k: 0 for k in weights}
    wsum = sum(weights.values())
    if wsum <= 0:
        return {k: 0 for k in weights}
    base = {}
    rema = {}
    for k, w in weights.items():
        num = w * total
        base[k] = num // wsum
        rema[k] = num - base[k] * wsum
    left = total - sum(base.values())
    order = sorted(weights, key=lambda k: (-rema[k], k))
    for k in order[:left]:
        base[k] += 1
    return base


# Which source class each commitment feed file carries, and in which format.
# The legacy and relay layouts carry no effort_unit column at all; the record
# layout document declares that both express effort in hours.
COMMITMENT_FILES = [
    ("commitments_vault_01.kv", "vault", "kv"),
    ("commitments_vault_02.kv", "vault", "kv"),
    ("commitments_desk_01.csv", "desk", "csv"),
    ("commitments_desk_02.csv", "desk", "csv"),
    ("commitments_bridge_01.xml", "bridge", "xml"),
    ("commitments_bridge_02.xml", "bridge", "xml"),
    ("commitments_partner_01.psv", "partner", "psv"),
    ("commitments_partner_02.psv", "partner", "psv"),
    ("commitments_mirror_01.tsv", "mirror", "tsv"),
    ("commitments_mirror_02.tsv", "mirror", "tsv"),
    ("commitments_import_01.jsonl", "import", "jsonl"),
    ("commitments_import_02.jsonl", "import", "jsonl"),
    ("commitments_relay_01.rec", "relay", "rec"),
    ("commitments_relay_02.rec", "relay", "rec"),
    ("commitments_legacy_01.fixed", "legacy", "fixed"),
    ("commitments_legacy_02.fixed", "legacy", "fixed"),
]

STATE_FILES = [
    ("states_vault_01.kv", "vault", "kv"),
    ("states_desk_01.csv", "desk", "csv"),
    ("states_bridge_01.xml", "bridge", "xml"),
    ("states_partner_01.psv", "partner", "psv"),
    ("states_mirror_01.tsv", "mirror", "tsv"),
    ("states_import_01.jsonl", "import", "jsonl"),
    ("states_relay_01.rec", "relay", "rec"),
    ("states_legacy_01.fixed", "legacy", "fixed"),
]

EDGE_FILES = [
    ("edges_desk_01.csv", "desk", "csv"),
    ("edges_desk_02.csv", "desk", "csv"),
    ("edges_bridge_01.xml", "bridge", "xml"),
    ("edges_partner_01.psv", "partner", "psv"),
    ("edges_mirror_01.tsv", "mirror", "tsv"),
    ("edges_import_01.jsonl", "import", "jsonl"),
]

ALIAS_FILES = [
    ("aliases_vault.kv", "kv"),
    ("aliases_desk.csv", "csv"),
    ("aliases_partner.psv", "psv"),
    ("aliases_mirror.tsv", "tsv"),
    ("aliases_import.jsonl", "jsonl"),
]

ROSTER_FILES = [
    ("roster_desk.csv", "csv"),
    ("roster_mirror.tsv", "tsv"),
    ("roster_vault.jsonl", "jsonl"),
]

# Fixed width column spec for the .fixed layouts, documented in
# record-layouts.md. Widths are chosen so no field ever overflows.
FIXED_COMMITMENT = [
    ("assertion_id", 12),
    ("commitment_key", 12),
    ("obligor", 40),
    ("obligee", 40),
    ("project_ref", 10),
    ("due_at", 18),
    ("effort", 8),
    ("cadence_ref", 10),
    ("observed_at", 18),
]
FIXED_STATE = [
    ("state_id", 12),
    ("commitment_key", 12),
    ("to_state", 12),
    ("observed_at", 18),
]


# ------------------------------------------------------------------ writers


def _pad(value: str, width: int) -> str:
    v = str(value)
    return v[:width].ljust(width)


def write_fixed(rows, cols) -> str:
    out = []
    for r in rows:
        out.append("".join(_pad(r.get(c, ""), w) for c, w in cols).rstrip())
    return "\n".join(out) + "\n"


def write_delim(rows, cols, sep) -> str:
    out = [sep.join(cols)]
    for r in rows:
        out.append(sep.join(str(r.get(c, "")) for c in cols))
    return "\n".join(out) + "\n"


def write_jsonl(rows, cols) -> str:
    out = []
    for r in rows:
        out.append(
            json.dumps(
                {c: r.get(c, "") for c in cols}, sort_keys=True, separators=(",", ":")
            )
        )
    return "\n".join(out) + "\n"


def write_kv(rows, cols) -> str:
    blocks = []
    for r in rows:
        blocks.append("\n".join(f"{c}: {r.get(c, '')}" for c in cols))
    return "\n\n".join(blocks) + "\n"


def _xml_escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_xml(rows, cols, root, item) -> str:
    out = [f"<{root}>"]
    for r in rows:
        attrs = " ".join(f'{c}="{_xml_escape(r.get(c, ""))}"' for c in cols)
        out.append(f"  <{item} {attrs}/>")
    out.append(f"</{root}>")
    return "\n".join(out) + "\n"


def write_rec(rows, cols) -> str:
    out = []
    for r in rows:
        out.append(";".join(f"{c}={r.get(c, '')}" for c in cols))
    return "\n".join(out) + "\n"


def emit(rows, cols, fmt, *, root="records", item="record"):
    if fmt == "csv":
        return write_delim(rows, cols, ",")
    if fmt == "tsv":
        return write_delim(rows, cols, "\t")
    if fmt == "psv":
        return write_delim(rows, cols, "|")
    if fmt == "jsonl":
        return write_jsonl(rows, cols)
    if fmt == "kv":
        return write_kv(rows, cols)
    if fmt == "xml":
        return write_xml(rows, cols, root, item)
    if fmt == "rec":
        return write_rec(rows, cols)
    raise ValueError(fmt)


COMMIT_COLS = (
    "assertion_id",
    "commitment_key",
    "obligor",
    "obligee",
    "project_ref",
    "due_at",
    "effort",
    "effort_unit",
    "cadence_ref",
    "observed_at",
)
COMMIT_COLS_NOUNIT = (
    "assertion_id",
    "commitment_key",
    "obligor",
    "obligee",
    "project_ref",
    "due_at",
    "effort",
    "cadence_ref",
    "observed_at",
)
STATE_COLS = ("state_id", "commitment_key", "to_state", "observed_at")
EDGE_COLS = ("edge_id", "dependent_key", "blocker_key", "asserted_at")
ALIAS_COLS = ("surface", "target", "scope_start", "scope_end", "asserted_at")
ROSTER_COLS = ("actor_id", "canonical_handle", "line_from", "line_to")

N_COMMITMENTS = 2600
N_CADENCES = 60

FEED_CLASSES = (
    "vault",
    "desk",
    "bridge",
    "partner",
    "mirror",
    "import",
    "relay",
    "legacy",
)


def build_world(seed: int) -> dict:
    u = build_universe(seed)
    rng = random.Random(derive(seed, "world"))
    actors = u["actors"]
    roots = u["roots"]
    children = u["children"]
    projects = u["projects"]

    # ---------------- cadences (rebuilt at the larger count)
    cadences = []
    for k in range(N_CADENCES):
        a = actors[rng.randrange(len(actors))]
        cadences.append(
            {
                "cadence_id": f"CAD-{k + 1:03d}",
                "period_days": rng.choice((7, 14, 21, 28)),
                "anchor_at": WINDOW_START + rng.randrange(0, 20) * 1440,
                "obligor": a["canonical_handle"],
                "actor_id": a["actor_id"],
                "project": rng.choice(roots),
            }
        )
    u["cadences"] = cadences

    # ---------------- surface handle pool per actor
    # Every surface a feed may write for an actor, with the instants at which
    # that surface actually resolves. Built from the alias table so the corpus
    # and the resolution rules cannot drift apart.
    surfaces_for = {a["actor_id"]: [] for a in actors}
    canon_to_id = {a["canonical_handle"]: a["actor_id"] for a in actors}
    for a in u["aliases"]:
        tid = canon_to_id.get(a["target"])
        if tid is not None:
            surfaces_for[tid].append(a)

    chains_by_actor = {}
    for c in u["chains"]:
        chains_by_actor.setdefault(c["actor"], []).append(c)

    def pick_surface(actor_id, at, rng):
        """A surface for this actor that genuinely resolves at `at`, or the
        canonical handle when nothing scoped covers the instant."""
        live = [
            a
            for a in surfaces_for.get(actor_id, ())
            if a["scope_start"] <= at < a["scope_end"]
        ]
        for c in chains_by_actor.get(actor_id, ()):
            if c["live_start"] <= at < c["live_end"]:
                live.append({"surface": c["surface"]})
        canon = u["by_id"][actor_id]["canonical_handle"]
        if live and rng.random() < 0.66:
            return rng.choice(live)["surface"]
        return canon

    # A cadence obligor is written as a surface like any other reference, so
    # it has to be resolved at the cadence anchor. A few name a surface that
    # stood for the principal at some other instant and stands for nobody at
    # the anchor, and the debt those cadences raise reaches no principal.
    for cad in cadences:
        anchor = cad["anchor_at"]
        roll = rng.random()
        if roll < 0.58:
            cad["obligor"] = pick_surface(cad["actor_id"], anchor, rng)
        elif roll < 0.70:
            lapsed = [
                a["surface"]
                for a in surfaces_for.get(cad["actor_id"], ())
                if not (a["scope_start"] <= anchor < a["scope_end"])
            ]
            if lapsed:
                cad["obligor"] = lapsed[rng.randrange(len(lapsed))]
        cad["stale_obligor"] = pick_surface(
            actors[rng.randrange(len(actors))]["actor_id"], anchor, rng
        )

    # ---------------- commitments
    commitments = []
    for i in range(N_COMMITMENTS):
        ob = actors[rng.randrange(len(actors))]
        oe = actors[rng.randrange(len(actors))]
        due = WINDOW_START + rng.randrange(0, (WINDOW_END - WINDOW_START))
        due -= due % 5
        proj = rng.choice(children + roots)
        eff_min = rng.choice(
            (
                15,
                20,
                30,
                45,
                60,
                90,
                120,
                150,
                180,
                240,
                300,
                360,
                420,
                480,
                540,
                600,
                720,
            )
        )
        cad = None
        commitments.append(
            {
                "key": f"CMT-{i + 1:05d}",
                "obligor_id": ob["actor_id"],
                "obligee_id": oe["actor_id"],
                "project": proj,
                "due_at": due,
                "effort_min": eff_min,
                "category": rng.choice(CATEGORIES),
                "cadence": cad,
                "kind": "plain",
            }
        )

    # attach cadence discharges: some commitments discharge a standing cadence
    by_key = {c["key"]: c for c in commitments}
    cad_pool = [c for c in commitments if rng.random() < 0.34]
    for c in cad_pool:
        cad = cadences[rng.randrange(len(cadences))]
        c["cadence"] = cad["cadence_id"]
        c["obligor_id"] = cad["actor_id"]
        c["kind"] = "cadence"

    # ---------------- commitment assertions (duplicates across feeds)
    assertions = []
    aid = 0
    for c in commitments:
        n = 1
        r = rng.random()
        if r < 0.46:
            n = 2
        elif r < 0.74:
            n = 3
        elif r < 0.84:
            n = 4
        classes = rng.sample(FEED_CLASSES, n)
        # the winner is decided by class rank, then by instant, so the payload
        # written by the losing feeds is deliberately different
        for j, cls in enumerate(classes):
            aid += 1
            obs = WINDOW_START + rng.randrange(0, WINDOW_END - WINDOW_START)
            authoritative = j == 0
            eff = c["effort_min"]
            due = c["due_at"]
            proj = c["project"]
            if not authoritative:
                # a plausible but different payload from a lower ranked feed
                eff = max(15, eff + rng.choice((-60, -30, -15, 15, 30, 60, 90)))
                if rng.random() < 0.35:
                    due = due + rng.choice((-1440, -720, 720, 1440))
                if rng.random() < 0.20:
                    proj = rng.choice(children + roots)
            unit = "minutes"
            if rng.random() < 0.24:
                if eff % 60 == 0:
                    unit = "hours"
                    eff_out = eff // 60
                else:
                    eff_out = eff
            else:
                eff_out = eff
            if unit == "minutes" and rng.random() < 0.07 and eff % 240 == 0:
                unit = "halfdays"
                eff_out = eff // 240
            assertions.append(
                {
                    "assertion_id": f"ASR-{aid:06d}",
                    "key": c["key"],
                    "obligor_id": c["obligor_id"],
                    "obligee_id": c["obligee_id"],
                    "project_ref": proj,
                    "due_at": due,
                    "effort_raw": str(eff_out),
                    "effort_unit": unit,
                    "cadence_ref": c["cadence"] or "",
                    "observed_at": obs,
                    "source_class": cls,
                    "authoritative": authoritative,
                    "flaw": None,
                }
            )

    # ---------------- state assertions
    states = []
    sid = 0
    settled_keys = set()
    holding = []
    for c in commitments:
        r = rng.random()
        if r < 0.30:
            path = []
        elif r < 0.62:
            path = ["SETTLED"]
        elif r < 0.76:
            path = ["DEFERRED"]
        elif r < 0.86:
            path = ["DEFERRED", "SETTLED"]
        elif r < 0.94:
            path = ["WITHDRAWN"]
        else:
            path = ["DEFERRED", "OPEN"]
        t = WINDOW_START + rng.randrange(0, WINDOW_END - WINDOW_START)
        for st in path:
            sid += 1
            t += rng.randrange(60, 20000)
            cls = rng.choice(FEED_CLASSES)
            states.append(
                {
                    "state_id": f"STA-{sid:06d}",
                    "key": c["key"],
                    "to_state": st,
                    "observed_at": min(t, WINDOW_END - 1),
                    "source_class": cls,
                    "flaw": None,
                }
            )
        if "SETTLED" in path:
            settled_keys.add(c["key"])
        if not path or path == ["DEFERRED"] or path == ["DEFERRED", "OPEN"]:
            holding.append(c["key"])

    # competing state assertions: a second feed claims a different terminal
    # state for the same commitment, and the precedence charter decides
    contested = rng.sample(commitments, 640)
    contested_keys = {c["key"] for c in contested}
    holding = [k for k in holding if k not in contested_keys]
    for c in contested:
        for _ in range(rng.randint(1, 2)):
            sid += 1
            states.append(
                {
                    "state_id": f"STA-{sid:06d}",
                    "key": c["key"],
                    "to_state": rng.choice(("SETTLED", "DEFERRED", "WITHDRAWN")),
                    "observed_at": WINDOW_START
                    + rng.randrange(0, WINDOW_END - WINDOW_START),
                    "source_class": rng.choice(FEED_CLASSES),
                    "flaw": None,
                }
            )

    # commitments whose state is decided inside the journal class, so the
    # ordering inversion inside that rank is exercised at real incidence
    journal = rng.sample(commitments, 460)
    for c in journal:
        t0 = WINDOW_START + rng.randrange(0, WINDOW_END - WINDOW_START - 60000)
        for st in rng.sample(["SETTLED", "DEFERRED", "WITHDRAWN"], 2):
            sid += 1
            t0 += rng.randrange(2000, 40000)
            states.append(
                {
                    "state_id": f"STA-{sid:06d}",
                    "key": c["key"],
                    "to_state": st,
                    "observed_at": min(t0, WINDOW_END - 1),
                    "source_class": "desk",
                    "flaw": None,
                }
            )

    # commitments whose state is decided inside the sweep class, so the
    # inversion that applies to state rows alone is exercised at real incidence
    sweep = rng.sample(commitments, 260)
    for c in sweep:
        t0 = WINDOW_START + rng.randrange(0, WINDOW_END - WINDOW_START - 60000)
        for st in rng.sample(["SETTLED", "DEFERRED", "WITHDRAWN"], 2):
            sid += 1
            t0 += rng.randrange(2000, 40000)
            states.append(
                {
                    "state_id": f"STA-{sid:06d}",
                    "key": c["key"],
                    "to_state": st,
                    "observed_at": min(t0, WINDOW_END - 1),
                    "source_class": "bridge",
                    "flaw": None,
                }
            )

    # ---------------- dependency edges
    edges = []
    eid = 0
    keys = [c["key"] for c in commitments]
    for _ in range(1150):
        eid += 1
        dep = rng.choice(keys)
        blk = rng.choice(keys)
        edges.append(
            {
                "edge_id": f"EDG-{eid:06d}",
                "dependent": dep,
                "blocker": blk,
                "asserted_at": WINDOW_START
                + rng.randrange(0, WINDOW_END - WINDOW_START),
                "source_class": rng.choice(FEED_CLASSES),
                "flaw": None,
            }
        )

    # deliberate chains, so a transitive closure is genuinely required
    for _ in range(70):
        chain = rng.sample(keys, rng.randint(3, 6))
        base = WINDOW_START + rng.randrange(0, (WINDOW_END - WINDOW_START) // 2)
        for a, b in zip(chain, chain[1:]):
            eid += 1
            edges.append(
                {
                    "edge_id": f"EDG-{eid:06d}",
                    "dependent": a,
                    "blocker": b,
                    "asserted_at": base + rng.randrange(0, 40 * 1440),
                    "source_class": rng.choice(FEED_CLASSES),
                    "flaw": None,
                }
            )

    # deliberate cycles, which the protocol declares unresolvable
    cycles = []
    for _ in range(26):
        if len(holding) < 4:
            break
        ring = rng.sample(holding, rng.randint(2, 4))
        base = WINDOW_START + rng.randrange(0, (WINDOW_END - WINDOW_START) // 2)
        for a, b in zip(ring, ring[1:] + ring[:1]):
            eid += 1
            edges.append(
                {
                    "edge_id": f"EDG-{eid:06d}",
                    "dependent": a,
                    "blocker": b,
                    "asserted_at": base + rng.randrange(0, 20 * 1440),
                    "source_class": rng.choice(FEED_CLASSES),
                    "flaw": None,
                }
            )
        cycles.append(ring)

    # self edges, which are dropped
    for _ in range(24):
        eid += 1
        k = rng.choice(keys)
        edges.append(
            {
                "edge_id": f"EDG-{eid:06d}",
                "dependent": k,
                "blocker": k,
                "asserted_at": WINDOW_START
                + rng.randrange(0, WINDOW_END - WINDOW_START),
                "source_class": rng.choice(FEED_CLASSES),
                "flaw": None,
            }
        )

    # dangling edges, naming a key no assertion ever creates
    for _ in range(40):
        eid += 1
        edges.append(
            {
                "edge_id": f"EDG-{eid:06d}",
                "dependent": rng.choice(keys),
                "blocker": f"CMT-{rng.randrange(90000, 99999):05d}",
                "asserted_at": WINDOW_START
                + rng.randrange(0, WINDOW_END - WINDOW_START),
                "source_class": rng.choice(FEED_CLASSES),
                "flaw": None,
            }
        )

    # ---------------- waivers
    waivers = []
    wid = 0
    for cad in cadences:
        span = (WINDOW_END - cad["anchor_at"]) // (cad["period_days"] * 1440)
        for p in range(max(0, span)):
            if rng.random() < 0.31:
                wid += 1
                waivers.append(
                    {
                        "waiver_id": f"WVR-{wid:05d}",
                        "cadence_id": cad["cadence_id"],
                        "period_index": p,
                        "reason": rng.choice(
                            ("AWAY", "BLOCKED", "AGREED", "SUPERSEDED")
                        ),
                        "source_class": rng.choice(FEED_CLASSES),
                        "flaw": None,
                    }
                )

    # ---------------- budgets
    budgets = []
    for a in actors:
        for m in range(3, 12):
            budgets.append(
                {
                    "actor_id": a["actor_id"],
                    "handle": a["canonical_handle"],
                    "year_month": f"2032-{m:02d}",
                    "monthly_minutes": rng.choice(
                        (900, 1200, 1500, 1800, 2100, 2400, 3000)
                    ),
                }
            )
    overrides = []
    seen_ov = set()
    for _ in range(400):
        a = actors[rng.randrange(len(actors))]
        m = rng.randrange(3, 12)
        if (a["actor_id"], m) in seen_ov:
            continue
        seen_ov.add((a["actor_id"], m))
        overrides.append(
            {
                "actor_id": a["actor_id"],
                "year_month": f"2032-{m:02d}",
                "monthly_minutes": rng.choice((0, 300, 600, 750, 1050, 2700, 3300)),
            }
        )
    # keep one override per (actor, day); a later duplicate is a real conflict
    # resolved by the documented winner, so keep a few on purpose
    return {
        "universe": u,
        "commitments": commitments,
        "by_key": by_key,
        "assertions": assertions,
        "states": states,
        "edges": edges,
        "waivers": waivers,
        "budgets": budgets,
        "overrides": overrides,
        "cycles": cycles,
        "pick_surface": pick_surface,
        "rng": rng,
    }


# Feed files retired part way through the window. A row observed at or after
# the retirement instant is rejected; a row observed before it is kept.
RETIRED = {
    "commitments_mirror_02.tsv": mk(2032, 8, 14, 0, 0),
    "commitments_import_02.jsonl": mk(2032, 9, 2, 12, 0),
    "states_relay_01.rec": mk(2032, 10, 5, 0, 0),
    "edges_mirror_01.tsv": mk(2032, 7, 20, 6, 0),
}

BAD_PRINCIPALS = (
    "nobody.here",
    "vacant.seat",
    "unknown-9",
    "ghost.walker",
    "seat-99",
    "ref-99",
    "loop-a",
)
BAD_PROJECTS = ("PRJ-999", "PRJ-000", "PRJ-XX", "PRJ-777")


def _spread(items, n_files, rng):
    """Deal items into buckets so no file is a sample of the corpus head."""
    buckets = [[] for _ in range(n_files)]
    order = list(range(len(items)))
    rng.shuffle(order)
    for pos, idx in enumerate(order):
        buckets[pos % n_files].append(items[idx])
    return buckets


def build_corpus(seed: int, drop=frozenset()):
    w = build_world(seed)
    u = w["universe"]
    rng = random.Random(derive(seed, "corpus"))
    pick = w["pick_surface"]
    ambiguous = u["ambiguous"]

    # scoped alias assertions per principal, used to place observations exactly
    # on a scope boundary so the half open reading is load bearing
    canon_to_id = {a["canonical_handle"]: a["actor_id"] for a in u["actors"]}
    scoped_for: dict[str, list] = {}
    for a in u["aliases"]:
        tid = canon_to_id.get(a["target"])
        if tid is None:
            continue
        if a["scope_start"] > WINDOW_START or a["scope_end"] < WINDOW_END:
            scoped_for.setdefault(tid, []).append(a)

    files: dict[str, str] = {}

    # ---------------------------------------------------- commitment feeds
    file_of_class: dict[str, list] = {}
    for name, cls, fmt in COMMITMENT_FILES:
        file_of_class.setdefault(cls, []).append((name, fmt))

    rows_by_file = {name: [] for name, _c, _f in COMMITMENT_FILES}
    for a in w["assertions"]:
        cands = file_of_class[a["source_class"]]
        name, _fmt = cands[rng.randrange(len(cands))]
        rows_by_file[name].append(a)

    for name, cls, fmt in COMMITMENT_FILES:
        rows = []
        retire_at = RETIRED.get(name)
        for a in rows_by_file[name]:
            obs = a["observed_at"]
            if retire_at is not None and rng.random() < 0.13:
                obs = min(retire_at + rng.randrange(0, 40 * 1440), WINDOW_END - 1)
            obligor = pick(a["obligor_id"], obs, rng)
            obligee = pick(a["obligee_id"], obs, rng)
            due = a["due_at"]
            eff = a["effort_raw"]
            unit = a["effort_unit"]
            proj = a["project_ref"]
            malformed = False

            roll = rng.random()
            if roll < 0.030:
                obligor = rng.choice(BAD_PRINCIPALS)
            elif roll < 0.055:
                amb = ambiguous[rng.randrange(len(ambiguous))]
                if amb["overlap_end"] > amb["overlap_start"]:
                    obs = amb["overlap_start"] + rng.randrange(
                        0, amb["overlap_end"] - amb["overlap_start"]
                    )
                    obligor = amb["surface"]
            elif roll < 0.080:
                proj = rng.choice(BAD_PROJECTS)
            elif roll < 0.100:
                due = WINDOW_END + rng.randrange(0, 40 * 1440)
            elif roll < 0.115:
                due = WINDOW_START - rng.randrange(1, 40 * 1440)
            elif roll < 0.140:
                eff = rng.choice(("0", "-30", "-1"))
            elif roll < 0.160:
                malformed = True
            elif roll < 0.190:
                eff = ""
            elif roll < 0.210:
                eff = "null"
            elif roll < 0.245:
                # the pre dawn band, including both sides of the boundary
                minute = rng.choice(
                    [0, 1, 60, 119, 180, 238, 239, 239, 240, 240, 241, 300]
                    + [rng.randrange(0, 300)]
                )
                due = (due // 1440) * 1440 + minute
            elif roll < 0.275:
                obligor = (
                    obligor.upper() if rng.random() < 0.5 else obligor.replace(".", "_")
                )
            elif roll < 0.330:
                # place the observation exactly on an interval boundary. The
                # start instant is inside the interval and the end instant is
                # outside it, so only the second changes a graded value under
                # the closed reading.
                cands = scoped_for.get(a["obligor_id"])
                if cands:
                    al = cands[rng.randrange(len(cands))]
                    edge = al["scope_end"] if rng.random() < 0.62 else al["scope_start"]
                    if WINDOW_START <= edge < WINDOW_END:
                        obs = edge
                        obligor = al["surface"]

            # A unit spelled in another case is not one of the three named
            # units, so the row is malformed. Layouts carrying no unit field
            # are untouched, because they never read one.
            if cls not in ("legacy", "relay") and rng.random() < 0.024:
                unit = unit.capitalize() if rng.random() < 0.5 else unit.upper()

            row = {
                "assertion_id": a["assertion_id"],
                "commitment_key": a["key"],
                "obligor": obligor,
                "obligee": obligee,
                "project_ref": proj,
                "due_at": fmt_instant(due),
                "effort": eff,
                "effort_unit": unit,
                "cadence_ref": a["cadence_ref"],
                "observed_at": fmt_instant(obs),
            }
            if cls in ("legacy", "relay"):
                if eff not in ("", "null"):
                    try:
                        n = int(eff)
                    except ValueError:
                        n = None
                    if n is not None:
                        if unit == "minutes":
                            row["effort"] = str(max(1, n // 60)) if n > 0 else str(n)
                        elif unit == "hours":
                            row["effort"] = str(n)
                        else:
                            row["effort"] = str(n * 4)
                row.pop("effort_unit", None)
            if malformed:
                row["due_at"] = rng.choice(
                    ("2032-13-40T99:99Z", "not-a-date", "2032/06/11 09:00", "")
                )
            rows.append(row)

        cols = COMMIT_COLS_NOUNIT if cls in ("legacy", "relay") else COMMIT_COLS
        if fmt == "fixed":
            files[name] = write_fixed(rows, FIXED_COMMITMENT)
        else:
            files[name] = emit(rows, cols, fmt, root="commitments", item="commitment")

    # ---------------------------------------------------- state feeds
    file_of_class = {}
    for name, cls, fmt in STATE_FILES:
        file_of_class.setdefault(cls, []).append((name, fmt))
    rows_by_file = {name: [] for name, _c, _f in STATE_FILES}
    for s in w["states"]:
        cands = file_of_class.get(s["source_class"])
        if not cands:
            cands = file_of_class[
                sorted(file_of_class)[rng.randrange(len(file_of_class))]
            ]
        name, _fmt = cands[rng.randrange(len(cands))]
        rows_by_file[name].append(s)

    for name, cls, fmt in STATE_FILES:
        rows = []
        retire_at = RETIRED.get(name)
        for s in rows_by_file[name]:
            obs = s["observed_at"]
            to = s["to_state"]
            key = s["key"]
            if retire_at is not None and rng.random() < 0.14:
                obs = min(retire_at + rng.randrange(0, 30 * 1440), WINDOW_END - 1)
            roll = rng.random()
            if roll < 0.030:
                to = rng.choice(("CLOSED", "done", "PARKED", "OPEN_AGAIN"))
            elif roll < 0.050:
                key = f"CMT-{rng.randrange(90000, 99999):05d}"
            elif roll < 0.070:
                obs = WINDOW_END + rng.randrange(0, 30 * 1440)
            rows.append(
                {
                    "state_id": s["state_id"],
                    "commitment_key": key,
                    "to_state": to,
                    "observed_at": fmt_instant(obs),
                }
            )
        if fmt == "fixed":
            files[name] = write_fixed(rows, FIXED_STATE)
        else:
            files[name] = emit(rows, STATE_COLS, fmt, root="states", item="state")

    # ---------------------------------------------------- edge feeds
    buckets = _spread(w["edges"], len(EDGE_FILES), rng)
    for (name, cls, fmt), bucket in zip(EDGE_FILES, buckets):
        rows = []
        retire_at = RETIRED.get(name)
        for e in bucket:
            at = e["asserted_at"]
            if retire_at is not None and rng.random() < 0.15:
                at = min(retire_at + rng.randrange(0, 30 * 1440), WINDOW_END - 1)
            dep, blk = e["dependent"], e["blocker"]
            roll = rng.random()
            if roll < 0.020:
                at = WINDOW_END + rng.randrange(0, 20 * 1440)
            elif roll < 0.035:
                blk = ""
            if e["edge_id"] in drop:
                continue
            rows.append(
                {
                    "edge_id": e["edge_id"],
                    "dependent_key": dep,
                    "blocker_key": blk,
                    "asserted_at": fmt_instant(at),
                }
            )
        files[name] = emit(rows, EDGE_COLS, fmt, root="edges", item="edge")

    # ---------------------------------------------------- alias feeds
    al = u["aliases"]
    for name, fmt in ALIAS_FILES:
        take = list(al)
        rng.shuffle(take)
        rows = []
        for a in take[: max(215, (len(al) * 3) // 5)]:
            surface = a["surface"]
            r = rng.random()
            if r < 0.10:
                surface = surface.upper()
            elif r < 0.20:
                surface = surface.replace(".", "_")
            rows.append(
                {
                    "surface": surface,
                    "target": a["target"],
                    "scope_start": fmt_instant(a["scope_start"]),
                    "scope_end": fmt_instant(a["scope_end"]),
                    "asserted_at": fmt_instant(a["asserted_at"]),
                }
            )
        # an assertion repeated with identical folded surface, target and
        # interval is one assertion however many files carry it
        for a in take[:9]:
            rows.append(
                {
                    "surface": a["surface"],
                    "target": a["target"],
                    "scope_start": fmt_instant(a["scope_start"]),
                    "scope_end": fmt_instant(a["scope_end"]),
                    "asserted_at": fmt_instant(a["asserted_at"]),
                }
            )
        # an interval whose start equals its end contains no instant
        for k in range(8):
            a = take[(k * 7) % len(take)]
            t = WINDOW_START + rng.randrange(0, WINDOW_END - WINDOW_START)
            rows.append(
                {
                    "surface": f"void-{k + 1:02d}",
                    "target": a["target"],
                    "scope_start": fmt_instant(t),
                    "scope_end": fmt_instant(t),
                    "asserted_at": fmt_instant(t),
                }
            )
        # an interval lying wholly before the window holds at no instant a row
        # in this extract carries
        for k in range(8):
            a = take[(k * 11) % len(take)]
            t = WINDOW_START - rng.randrange(40 * 1440, 200 * 1440)
            rows.append(
                {
                    "surface": f"lapsed-{k + 1:02d}",
                    "target": a["target"],
                    "scope_start": fmt_instant(t),
                    "scope_end": fmt_instant(t + 20 * 1440),
                    "asserted_at": fmt_instant(t),
                }
            )
        rng.shuffle(rows)
        files[name] = emit(rows, ALIAS_COLS, fmt, root="aliases", item="alias")

    # ---------------------------------------------------- rosters
    roster_rows = []
    for a in u["actors"]:
        n = rng.randint(5, 6)
        cuts = sorted(rng.sample(range(1, 250), n - 1))
        bounds = [0] + cuts + [275]
        for i in range(n):
            roster_rows.append(
                {
                    "actor_id": a["actor_id"],
                    "canonical_handle": a["canonical_handle"],
                    "line_from": fmt_day(WINDOW_START // 1440 + bounds[i]),
                    "line_to": fmt_day(WINDOW_START // 1440 + bounds[i + 1]),
                }
            )
    for name, fmt in ROSTER_FILES:
        rows = list(roster_rows)
        for k in range(9):
            a = u["actors"][(k * 5) % len(u["actors"])]
            h = a["canonical_handle"]
            rows.append(
                {
                    "actor_id": a["actor_id"],
                    "canonical_handle": h.upper() if k % 2 else h.replace(".", "_"),
                    "line_from": fmt_day(WINDOW_START // 1440),
                    "line_to": fmt_day(WINDOW_END // 1440),
                }
            )
        rng.shuffle(rows)
        files[name] = emit(rows, ROSTER_COLS, fmt, root="roster", item="line")

    return files, w


PROJECT_REGISTRY_COLS = (
    "project_code",
    "revision",
    "display_name",
    "parent_code",
    "default_effort",
    "revised_at",
)
PROJECT_EVENT_COLS = (
    "event_id",
    "project_code",
    "event_type",
    "payload",
    "effective_at",
)
CADENCE_COLS = (
    "cadence_id",
    "revision",
    "obligor",
    "project_ref",
    "period_days",
    "anchor_at",
    "revised_at",
)
WAIVER_COLS = ("waiver_id", "cadence_id", "period_index", "reason", "asserted_at")
BUDGET_COLS = ("actor_id", "year_month", "monthly_minutes")
OVERRIDE_COLS = ("actor_id", "year_month", "monthly_minutes")
MANIFEST_COLS = ("feed_file", "source_class", "revision", "retired_at", "declared_at")

_WORDS = (
    "harbour",
    "lantern",
    "meadow",
    "orchard",
    "quarry",
    "ridge",
    "spindle",
    "thicket",
    "vellum",
    "warren",
    "bracken",
    "cinder",
)


def build_extra(seed: int, w, retired: dict, drop=frozenset()) -> dict[str, str]:
    u = w["universe"]
    rng = random.Random(derive(seed, "extra"))
    files: dict[str, str] = {}
    projects = u["projects"]
    codes = sorted(projects)

    # ---------------------------------------------------- project registry
    # default_effort is declared per revision; the revision that governs an
    # assertion is the latest one revised at or before the observation instant.
    reg_rows = []
    defaults = {}
    for code in codes:
        base = rng.choice((30, 45, 60, 90, 120, 150, 180))
        name = f"{rng.choice(_WORDS)}-{rng.choice(_WORDS)}"
        revs = []
        t = WINDOW_START - rng.randrange(20 * 1440, 90 * 1440)
        for r in range(4):
            revs.append((r + 1, t, base))
            t += rng.randrange(20 * 1440, 80 * 1440)
            base = max(15, base + rng.choice((-30, -15, 0, 15, 30, 45)))
        defaults[code] = revs
        for rev, at, dflt in revs:
            reg_rows.append(
                {
                    "project_code": code,
                    "revision": rev,
                    "display_name": name if rev == 1 else f"{name}-r{rev}",
                    "parent_code": projects[code]["parent"],
                    "default_effort": dflt,
                    "revised_at": fmt_instant(at),
                }
            )
    roots_list = sorted(r for r in codes if not projects[r]["parent"])
    moved = 0
    for row in reg_rows:
        if (
            row["revision"] == 4
            and projects[row["project_code"]]["parent"]
            and moved < 14
        ):
            row["parent_code"] = roots_list[moved % len(roots_list)]
            moved += 1
    for k in range(12):
        t = WINDOW_START - rng.randrange(10 * 1440, 80 * 1440)
        reg_rows.append(
            {
                "project_code": f"PRJ-6{k:02d}",
                "revision": 1,
                "display_name": f"{rng.choice(_WORDS)}-{rng.choice(_WORDS)}",
                "parent_code": "",
                "default_effort": rng.choice((30, 60, 90)),
                "revised_at": fmt_instant(t),
            }
        )
    rng.shuffle(reg_rows)
    files["project_registry.csv"] = emit(reg_rows, PROJECT_REGISTRY_COLS, "csv")

    # ---------------------------------------------------- project events
    ev_rows = []
    n = 0
    for r in u["renames"]:
        n += 1
        ev_rows.append(
            {
                "event_id": f"PEV-{n:05d}",
                "project_code": r["old_code"],
                "event_type": "RENAME",
                "payload": r["new_code"],
                "effective_at": fmt_instant(r["effective_at"]),
            }
        )
    for code in codes:
        for kind in ("OPENED", "REVIEWED", "REPARENTED", "ANNOTATED"):
            n += 1
            ev_rows.append(
                {
                    "event_id": f"PEV-{n:05d}",
                    "project_code": code,
                    "event_type": kind,
                    "payload": (
                        projects[code]["parent"]
                        if kind == "REPARENTED"
                        else rng.choice(_WORDS)
                    ),
                    "effective_at": fmt_instant(
                        WINDOW_START
                        - rng.randrange(0, 60 * 1440)
                        + rng.randrange(0, 200 * 1440)
                    ),
                }
            )
    # decoy renames naming a project code the registry never declares, which
    # the lineage walk must leave unresolved rather than invent
    for k in range(6):
        n += 1
        ev_rows.append(
            {
                "event_id": f"PEV-{n:05d}",
                "project_code": f"PRJ-8{k:02d}",
                "event_type": "RENAME",
                "payload": f"PRJ-9{k:02d}",
                "effective_at": fmt_instant(
                    WINDOW_START + rng.randrange(0, 200 * 1440)
                ),
            }
        )
    rng.shuffle(ev_rows)
    files["project_events.tsv"] = emit(ev_rows, PROJECT_EVENT_COLS, "tsv")

    # ---------------------------------------------------- cadence register
    c_by_id = {c["cadence_id"]: c for c in u["cadences"]}
    cad_rows = []
    for c in u["cadences"]:
        t = WINDOW_START - rng.randrange(5 * 1440, 40 * 1440)
        for rev in range(1, 5):
            cad_rows.append(
                {
                    "cadence_id": c["cadence_id"],
                    "revision": rev,
                    "obligor": c["obligor"],
                    "project_ref": c["project"],
                    "period_days": c["period_days"],
                    "anchor_at": fmt_instant(c["anchor_at"]),
                    "revised_at": fmt_instant(t),
                }
            )
            t += rng.randrange(10 * 1440, 50 * 1440)
    seen_top = set()
    for row in cad_rows:
        if row["revision"] < 4 and row["cadence_id"] not in seen_top:
            row["period_days"] = rng.choice((7, 14, 21, 28))
            row["anchor_at"] = fmt_instant(WINDOW_START + rng.randrange(0, 40) * 1440)
            row["obligor"] = c_by_id[row["cadence_id"]].get(
                "stale_obligor", row["obligor"]
            )
            seen_top.add(row["cadence_id"] + str(row["revision"]))
    rng.shuffle(cad_rows)
    files["cadence_register.csv"] = emit(cad_rows, CADENCE_COLS, "csv")

    # ---------------------------------------------------- waivers
    wv = list(w["waivers"])
    rng.shuffle(wv)
    half = len(wv) // 2
    for fname, fmt, chunk in (
        ("waivers_desk.csv", "csv", wv[:half]),
        ("waivers_partner.psv", "psv", wv[half:]),
    ):
        rows = []
        for x in chunk:
            rows.append(
                {
                    "waiver_id": x["waiver_id"],
                    "cadence_id": x["cadence_id"],
                    "period_index": x["period_index"],
                    "reason": x["reason"],
                    "asserted_at": fmt_instant(
                        WINDOW_START + rng.randrange(0, WINDOW_END - WINDOW_START)
                    ),
                }
            )
        # waivers naming a period beyond the window, which change nothing
        for k in range(14):
            rows.append(
                {
                    "waiver_id": f"WVR-9{k:04d}",
                    "cadence_id": rng.choice(u["cadences"])["cadence_id"],
                    "period_index": rng.randrange(400, 900),
                    "reason": "AGREED",
                    "asserted_at": fmt_instant(
                        WINDOW_START + rng.randrange(0, WINDOW_END - WINDOW_START)
                    ),
                }
            )
        for k, x in enumerate(chunk[:10]):
            rows.append(
                {
                    "waiver_id": f"WVR-8{k:04d}",
                    "cadence_id": x["cadence_id"],
                    "period_index": x["period_index"],
                    "reason": x["reason"],
                    "asserted_at": fmt_instant(
                        WINDOW_START + rng.randrange(0, WINDOW_END - WINDOW_START)
                    ),
                }
            )
        for k in range(8):
            rows.append(
                {
                    "waiver_id": f"WVR-7{k:04d}",
                    "cadence_id": f"CAD-9{k:02d}",
                    "period_index": rng.randrange(0, 12),
                    "reason": "AGREED",
                    "asserted_at": fmt_instant(
                        WINDOW_START + rng.randrange(0, WINDOW_END - WINDOW_START)
                    ),
                }
            )
        rng.shuffle(rows)
        rows = [r for r in rows if (r["cadence_id"], r["period_index"]) not in drop]
        files[fname] = emit(rows, WAIVER_COLS, fmt)

    # ---------------------------------------------------- budgets
    brows = [
        {
            "actor_id": b["actor_id"],
            "year_month": b["year_month"],
            "monthly_minutes": b["monthly_minutes"],
        }
        for b in w["budgets"]
    ]
    drop = set()
    while len(drop) < 16:
        drop.add(rng.randrange(len(brows)))
    brows = [r for i, r in enumerate(brows) if i not in drop]
    rng.shuffle(brows)
    files["attention_budget.csv"] = emit(brows, BUDGET_COLS, "csv")

    orows = [
        {
            "actor_id": o["actor_id"],
            "year_month": o["year_month"],
            "monthly_minutes": o["monthly_minutes"],
        }
        for o in w["overrides"]
    ]
    rng.shuffle(orows)
    files["budget_overrides.psv"] = emit(orows, OVERRIDE_COLS, "psv")

    # ---------------------------------------------------- feed manifest
    feed_names = (
        [(n, c) for n, c, _f in COMMITMENT_FILES]
        + [(n, c) for n, c, _f in STATE_FILES]
        + [(n, c) for n, c, _f in EDGE_FILES]
        + [(n, "reference") for n, _f in ALIAS_FILES]
        + [(n, "reference") for n, _f in ROSTER_FILES]
        + [
            ("project_registry.csv", "reference"),
            ("project_events.tsv", "reference"),
            ("cadence_register.csv", "reference"),
            ("waivers_desk.csv", "desk"),
            ("waivers_partner.psv", "partner"),
            ("attention_budget.csv", "reference"),
            ("budget_overrides.psv", "reference"),
        ]
    )
    mrows = []
    stale = 0
    for name, cls in feed_names:
        ret = retired.get(name)
        t = WINDOW_START - rng.randrange(2 * 1440, 30 * 1440)
        for rev in range(1, 6):
            stale_at = ""
            if ret is None and rev in (2, 3) and stale < 24:
                stale_at = fmt_instant(
                    WINDOW_START + rng.randrange(0, WINDOW_END - WINDOW_START)
                )
                stale += 1
            mrows.append(
                {
                    "feed_file": name,
                    "source_class": cls,
                    "revision": rev,
                    "retired_at": (
                        fmt_instant(ret) if (ret is not None and rev == 5) else stale_at
                    ),
                    "declared_at": fmt_instant(t),
                }
            )
            t += rng.randrange(5 * 1440, 30 * 1440)
    rng.shuffle(mrows)
    files["feed_manifest.csv"] = emit(mrows, MANIFEST_COLS, "csv")

    return files, defaults


DELIMS = {".csv": ",", ".tsv": "\t", ".psv": "|"}


def read_delim(text: str, sep: str):
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return []
    header = lines[0].split(sep)
    out = []
    for ln in lines[1:]:
        if ln == "":
            continue
        parts = ln.split(sep)
        if len(parts) != len(header):
            out.append({"__malformed__": ln})
            continue
        out.append(dict(zip(header, parts)))
    return out


def read_jsonl(text: str):
    out = []
    for ln in text.split("\n"):
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except ValueError:
            out.append({"__malformed__": ln})
            continue
        if not isinstance(obj, dict):
            out.append({"__malformed__": ln})
            continue
        out.append({k: ("" if v is None else str(v)) for k, v in obj.items()})
    return out


def read_kv(text: str):
    out = []
    for block in text.split("\n\n"):
        block = block.strip("\n")
        if not block.strip():
            continue
        rec = {}
        bad = False
        for ln in block.split("\n"):
            if ": " in ln:
                k, v = ln.split(": ", 1)
            elif ln.endswith(":"):
                k, v = ln[:-1], ""
            else:
                bad = True
                break
            rec[k.strip()] = v
        out.append({"__malformed__": block} if bad else rec)
    return out


def read_rec(text: str):
    out = []
    for ln in text.split("\n"):
        if not ln.strip():
            continue
        rec = {}
        bad = False
        for part in ln.split(";"):
            if "=" not in part:
                bad = True
                break
            k, v = part.split("=", 1)
            rec[k] = v
        out.append({"__malformed__": ln} if bad else rec)
    return out


def _unescape(s: str) -> str:
    return (
        s.replace("&quot;", '"')
        .replace("&gt;", ">")
        .replace("&lt;", "<")
        .replace("&amp;", "&")
    )


def read_xml(text: str):
    out = []
    for ln in text.split("\n"):
        ln = ln.strip()
        if (
            not ln.startswith("<")
            or ln.startswith("</")
            or ln.endswith(">")
            and not ln.endswith("/>")
        ):
            continue
        body = ln[1:-2].strip()
        sp = body.find(" ")
        if sp < 0:
            continue
        body = body[sp + 1 :]
        rec = {}
        i = 0
        ok = True
        while i < len(body):
            eq = body.find('="', i)
            if eq < 0:
                break
            key = body[i:eq].strip()
            end = body.find('"', eq + 2)
            if end < 0:
                ok = False
                break
            rec[key] = _unescape(body[eq + 2 : end])
            i = end + 1
            while i < len(body) and body[i] == " ":
                i += 1
        out.append(rec if ok else {"__malformed__": ln})
    return out


def read_fixed(text: str, cols):
    out = []
    width = sum(w for _c, w in cols)
    for ln in text.split("\n"):
        if not ln.strip():
            continue
        padded = ln.ljust(width)
        if len(padded) > width:
            out.append({"__malformed__": ln})
            continue
        rec = {}
        pos = 0
        for c, w in cols:
            rec[c] = padded[pos : pos + w].strip()
            pos += w
        out.append(rec)
    return out


def read_any(path: str, kind: str = ""):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    ext = os.path.splitext(path)[1]
    if ext in DELIMS:
        return read_delim(text, DELIMS[ext])
    if ext == ".jsonl":
        return read_jsonl(text)
    if ext == ".kv":
        return read_kv(text)
    if ext == ".rec":
        return read_rec(text)
    if ext == ".xml":
        return read_xml(text)
    if ext == ".fixed":
        cols = FIXED_STATE if kind == "state" else FIXED_COMMITMENT
        return read_fixed(text, cols)
    return []


HOURS_LAYOUTS = (".fixed", ".rec")


def _int(s):
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return None


def _scan(data_dir, prefix, kind=""):
    """Every feed file whose name starts with `prefix`, in name order."""
    out = []
    for name in sorted(os.listdir(data_dir)):
        if name.startswith(prefix):
            out.append((name, read_any(os.path.join(data_dir, name), kind)))
    return out


def _class_of(name: str) -> str:
    stem = name.split(".")[0]
    for part in stem.split("_"):
        if part in CLASS_RANK:
            return part
    return "reference"


def stage1(data_dir: str) -> dict:
    # ---------------------------------------------------------- reference
    manifest = {}
    for name, rows in _scan(data_dir, "feed_manifest"):
        for r in rows:
            if "__malformed__" in r:
                continue
            rev = _int(r.get("revision"))
            f = r.get("feed_file", "")
            cur = manifest.get(f)
            if cur is None or (rev is not None and rev > cur[0]):
                manifest[f] = (rev or 0, parse_instant(r.get("retired_at", "")))
    retired_at = {f: v[1] for f, v in manifest.items() if v[1] is not None}

    registry = {}
    for name, rows in _scan(data_dir, "project_registry"):
        for r in rows:
            if "__malformed__" in r:
                continue
            code = r.get("project_code", "")
            at = parse_instant(r.get("revised_at", ""))
            dflt = _int(r.get("default_effort"))
            if not code or at is None or dflt is None:
                continue
            registry.setdefault(code, []).append((at, dflt, r.get("parent_code", "")))
    for v in registry.values():
        v.sort()
    projects = {}
    for code, revs in registry.items():
        parent = revs[-1][2]
        projects[code] = {"code": code, "parent": parent}
    for code, p in projects.items():
        seen, cur = set(), code
        while True:
            par = projects.get(cur, {}).get("parent", "")
            if not par or par in seen or par not in projects:
                break
            seen.add(cur)
            cur = par
        p["root"] = cur

    renames = []
    for name, rows in _scan(data_dir, "project_events"):
        for r in rows:
            if "__malformed__" in r or r.get("event_type") != "RENAME":
                continue
            at = parse_instant(r.get("effective_at", ""))
            if at is None:
                continue
            renames.append(
                {
                    "old_code": r.get("project_code", ""),
                    "new_code": r.get("payload", ""),
                    "effective_at": at,
                }
            )

    roster = {}
    spellings: dict = {}
    for name, rows in _scan(data_dir, "roster_"):
        for r in rows:
            if "__malformed__" in r:
                continue
            aid, h = r.get("actor_id", ""), r.get("canonical_handle", "")
            if aid and h:
                roster[h] = aid
                spellings.setdefault(aid, {})
                spellings[aid][h] = spellings[aid].get(h, 0) + 1

    aliases = []
    seen_alias = set()
    for name, rows in _scan(data_dir, "aliases_"):
        for r in rows:
            if "__malformed__" in r:
                continue
            s0 = parse_instant(r.get("scope_start", ""))
            s1 = parse_instant(r.get("scope_end", ""))
            if s0 is None or s1 is None:
                continue
            key = (fold(r.get("surface", "")), fold(r.get("target", "")), s0, s1)
            if key in seen_alias:
                continue
            seen_alias.add(key)
            aliases.append(
                {
                    "surface": r.get("surface", ""),
                    "target": r.get("target", ""),
                    "scope_start": s0,
                    "scope_end": s1,
                }
            )

    res = Resolver(aliases, roster.keys(), projects, renames)
    handle_to_actor = {fold(h): a for h, a in roster.items()}

    def default_effort(code, at):
        revs = registry.get(code)
        if not revs:
            return None
        best = None
        for r_at, dflt, _p in revs:
            if r_at <= at:
                best = dflt
        return best if best is not None else revs[0][1]

    cadences = {}
    for name, rows in _scan(data_dir, "cadence_register"):
        for r in rows:
            if "__malformed__" in r:
                continue
            cid = r.get("cadence_id", "")
            rev = _int(r.get("revision"))
            pd = _int(r.get("period_days"))
            anchor = parse_instant(r.get("anchor_at", ""))
            if not cid or rev is None or pd is None or anchor is None:
                continue
            cur = cadences.get(cid)
            if cur is None or rev > cur["revision"]:
                cadences[cid] = {
                    "cadence_id": cid,
                    "revision": rev,
                    "obligor": r.get("obligor", ""),
                    "project_ref": r.get("project_ref", ""),
                    "period_days": pd,
                    "anchor_at": anchor,
                }

    waivers = {}
    for name, rows in _scan(data_dir, "waivers_"):
        for r in rows:
            if "__malformed__" in r:
                continue
            cid = r.get("cadence_id", "")
            pi = _int(r.get("period_index"))
            if cid and pi is not None:
                waivers.setdefault(cid, set()).add(pi)

    budget_month = {}
    for name, rows in _scan(data_dir, "attention_budget"):
        for r in rows:
            if "__malformed__" in r:
                continue
            m = _int(r.get("monthly_minutes"))
            if m is not None:
                budget_month[(r.get("actor_id", ""), r.get("year_month", ""))] = m
    budget_day = {}
    for name, rows in _scan(data_dir, "budget_overrides"):
        for r in rows:
            if "__malformed__" in r:
                continue
            m = _int(r.get("monthly_minutes"))
            d = r.get("year_month", "")
            if m is not None and d:
                budget_day[(r.get("actor_id", ""), d)] = m

    # ---------------------------------------------------------- stage 1
    normalized = []
    rejects = []
    ingested = 0
    fold_changed = 0

    for name, rows in _scan(data_dir, "commitments_"):
        cls = _class_of(name)
        ext = os.path.splitext(name)[1]
        hours_layout = ext in HOURS_LAYOUTS
        ret = retired_at.get(name)
        for idx, r in enumerate(rows):
            ingested += 1
            aid = r.get("assertion_id", "") if "__malformed__" not in r else ""
            key = r.get("commitment_key", "") if "__malformed__" not in r else ""

            def rej(code):
                rejects.append(
                    {
                        "assertion_id": aid,
                        "commitment_key": key,
                        "feed_file": name,
                        "row_index": idx,
                        "reason_code": code,
                    }
                )

            if "__malformed__" in r:
                rej("MALFORMED_ROW")
                continue
            obs = parse_instant(r.get("observed_at", ""))
            due = parse_instant(r.get("due_at", ""))
            if not aid or not key or obs is None or due is None:
                rej("MALFORMED_ROW")
                continue
            # A non-integer effort, or a positive one in a unit outside the
            # three named, is malformed, and protocol section 6 tests every
            # malformed condition before FEED_RETIRED.
            raw = (r.get("effort", "") or "").strip()
            unit = (
                "hours"
                if hours_layout
                else (r.get("effort_unit", "") or "").strip()
            )
            if raw != "" and raw != "null":
                n = _int(raw)
                if n is None or (n > 0 and unit not in EFFORT_UNITS):
                    rej("MALFORMED_ROW")
                    continue
            if ret is not None and obs >= ret:
                rej("FEED_RETIRED")
                continue
            if not (WINDOW_START <= due < WINDOW_END):
                rej("OUT_OF_WINDOW")
                continue

            surface = r.get("obligor", "")
            if fold(surface) != surface.strip().casefold():
                fold_changed += 1
            actor_h, why, hops = res.resolve_handle(surface, obs)
            if actor_h is None:
                rej(why)
                continue
            obligor = handle_to_actor[fold(actor_h)]

            # The obligee is resolved at the instant the commitment falls due,
            # which protocol section 3 names separately from the obligor's.
            oe_h, oe_why, _p2 = res.resolve_handle(r.get("obligee", ""), due)
            obligee = handle_to_actor[fold(oe_h)] if oe_h else ""

            code = res.resolve_project(r.get("project_ref", ""), obs)
            if code is None:
                rej("UNKNOWN_PROJECT")
                continue

            if raw == "":
                minutes = default_effort(code, obs)
                if minutes is None:
                    rej("NONPOSITIVE_EFFORT")
                    continue
                origin = "DEFAULTED"
            elif raw == "null":
                minutes = 0
                origin = "DECLARED_ZERO"
            else:
                n = _int(raw)
                if n <= 0:
                    rej("NONPOSITIVE_EFFORT")
                    continue
                minutes = n * EFFORT_UNITS[unit]
                origin = "STATED"

            normalized.append(
                {
                    "assertion_id": aid,
                    "commitment_key": key,
                    "obligor_actor": obligor,
                    "obligor_surface": surface,
                    "obligor_hops": max(0, len(hops) - 1),
                    "obligee_actor": obligee,
                    "obligee_surface": r.get("obligee", ""),
                    "obligee_status": (
                        "AMBIGUOUS"
                        if oe_why == "AMBIGUOUS_IDENTITY"
                        else ("RESOLVED" if oe_h else "UNKNOWN")
                    ),
                    "project_code": code,
                    "project_root": projects.get(code, {}).get("root", code),
                    "due_at": fmt_instant(due),
                    "commitment_day": fmt_day(commitment_day(due)),
                    "effort_minutes": clamp_effort(minutes),
                    "effort_origin": origin,
                    "cadence_ref": r.get("cadence_ref", "") or "",
                    "observed_at": fmt_instant(obs),
                    "source_class": cls,
                    "feed_file": name,
                }
            )

    normalized.sort(key=lambda r: r["assertion_id"])
    rejects.sort(key=lambda r: (r["feed_file"], r["row_index"], r["assertion_id"]))
    return {
        "normalized": normalized,
        "rejects": rejects,
        "ingested": ingested,
        "fold_changed": fold_changed,
        "res": res,
        "projects": projects,
        "roster": roster,
        "spellings": spellings,
        "handle_to_actor": handle_to_actor,
        "cadences": cadences,
        "waivers": waivers,
        "budget_month": budget_month,
        "budget_day": budget_day,
        "retired_at": retired_at,
        "aliases": aliases,
        "renames": renames,
        "data_dir": data_dir,
    }


def reconcile(data_dir: str) -> dict:
    st = stage1(data_dir)
    res = st["res"]
    projects = st["projects"]
    handle_to_actor = st["handle_to_actor"]
    normalized = st["normalized"]
    rejects = [
        dict(r, record_kind="commitment", record_id=r["assertion_id"])
        for r in st["rejects"]
    ]
    rows_ingested = st["ingested"]

    # ------------------------------------------------ winner per commitment
    groups: dict[str, list] = {}
    for r in normalized:
        groups.setdefault(r["commitment_key"], []).append(r)
    winners = {}
    contest_rows = []
    for key, rows in groups.items():
        ordered = sorted(
            rows,
            key=lambda r: precedence_key(
                r["source_class"], parse_instant(r["observed_at"]), r["assertion_id"]
            ),
        )
        win = ordered[-1]
        winners[key] = win
        contest_rows.append(
            {
                "commitment_key": key,
                "winning_assertion": win["assertion_id"],
                "winning_class": win["source_class"],
                "contender_count": len(rows),
                "distinct_classes": len({r["source_class"] for r in rows}),
            }
        )
    contest_rows.sort(key=lambda r: r["commitment_key"])

    # ------------------------------------------------ state resolution
    state_rows = []
    states_ingested = 0
    for name, rows in _scan(data_dir, "states_", "state"):
        cls = _class_of(name)
        ret = st["retired_at"].get(name)
        for idx, r in enumerate(rows):
            states_ingested += 1
            rows_ingested += 1
            sid = r.get("state_id", "") if "__malformed__" not in r else ""
            key = r.get("commitment_key", "") if "__malformed__" not in r else ""

            def rej(code):
                rejects.append(
                    {
                        "feed_file": name,
                        "row_index": idx,
                        "record_kind": "state",
                        "record_id": sid,
                        "assertion_id": sid,
                        "commitment_key": key,
                        "reason_code": code,
                    }
                )

            if "__malformed__" in r:
                rej("MALFORMED_ROW")
                continue
            obs = parse_instant(r.get("observed_at", ""))
            to = (r.get("to_state", "") or "").strip()
            # Every malformed-row condition is tested before any later code,
            # because protocol section 6 fixes the order and a row carries the
            # first code that applies. A to_state outside the closed list is a
            # malformed row wherever the feed stood.
            if not sid or not key or obs is None or to not in STATES:
                rej("MALFORMED_ROW")
                continue
            if ret is not None and obs >= ret:
                rej("FEED_RETIRED")
                continue
            if not (WINDOW_START <= obs < WINDOW_END):
                rej("OUT_OF_WINDOW")
                continue
            if key not in winners:
                rej("UNKNOWN_COMMITMENT")
                continue
            state_rows.append(
                {
                    "state_id": sid,
                    "commitment_key": key,
                    "to_state": to,
                    "observed_at": obs,
                    "source_class": cls,
                    "feed_file": name,
                    "row_index": idx,
                }
            )

    by_key: dict[str, list] = {}
    for s in state_rows:
        by_key.setdefault(s["commitment_key"], []).append(s)

    resolved_state = {}
    state_trace = []
    illegal = 0
    for key in winners:
        cur = "OPEN"
        seq = sorted(
            by_key.get(key, ()),
            key=lambda s: precedence_key(
                s["source_class"], s["observed_at"], s["state_id"], kind="state"
            ),
        )
        applied = 0
        last_class = ""
        for s in seq:
            if (cur, s["to_state"]) in LEGAL_TRANSITIONS:
                cur = s["to_state"]
                applied += 1
                last_class = s["source_class"]
            else:
                illegal += 1
                rejects.append(
                    {
                        "feed_file": s["feed_file"],
                        "row_index": s["row_index"],
                        "record_kind": "state",
                        "record_id": s["state_id"],
                        "assertion_id": s["state_id"],
                        "commitment_key": key,
                        "reason_code": "ILLEGAL_TRANSITION",
                    }
                )
        resolved_state[key] = cur
        state_trace.append(
            {
                "commitment_key": key,
                "resolved_state": cur,
                "assertions_seen": len(seq),
                "assertions_applied": applied,
                "governing_class": last_class,
            }
        )
    state_trace.sort(key=lambda r: r["commitment_key"])

    # ------------------------------------------------ dependency edges
    live_edges = []
    dropped_edges = []
    edges_ingested = 0
    for name, rows in _scan(data_dir, "edges_"):
        cls = _class_of(name)
        ret = st["retired_at"].get(name)
        for idx, r in enumerate(rows):
            edges_ingested += 1
            rows_ingested += 1
            eid = r.get("edge_id", "") if "__malformed__" not in r else ""
            dep = r.get("dependent_key", "") if "__malformed__" not in r else ""
            blk = r.get("blocker_key", "") if "__malformed__" not in r else ""

            def rej(code):
                rejects.append(
                    {
                        "feed_file": name,
                        "row_index": idx,
                        "record_kind": "edge",
                        "record_id": eid,
                        "assertion_id": eid,
                        "commitment_key": dep,
                        "reason_code": code,
                    }
                )

            if "__malformed__" in r:
                rej("MALFORMED_ROW")
                continue
            at = parse_instant(r.get("asserted_at", ""))
            if not eid or not dep or at is None:
                rej("MALFORMED_ROW")
                continue
            if ret is not None and at >= ret:
                rej("FEED_RETIRED")
                continue
            if not (WINDOW_START <= at < WINDOW_END):
                rej("OUT_OF_WINDOW")
                continue

            if dep == blk:
                dropped_edges.append(
                    {
                        "edge_id": eid,
                        "dependent_key": dep,
                        "blocker_key": blk,
                        "asserted_at": fmt_instant(at),
                        "drop_reason": "EDGE_SELF",
                    }
                )
                continue
            if dep not in winners or blk not in winners:
                dropped_edges.append(
                    {
                        "edge_id": eid,
                        "dependent_key": dep,
                        "blocker_key": blk,
                        "asserted_at": fmt_instant(at),
                        "drop_reason": "EDGE_DANGLING",
                    }
                )
                continue
            # the scope rule: both endpoints must resolve at the instant the
            # edge was asserted, never at the instant the commitment was seen
            dh, dwhy, _ = res.resolve_handle(winners[dep]["obligor_surface"], at)
            bh, bwhy, _ = res.resolve_handle(winners[blk]["obligor_surface"], at)
            if dh is None or bh is None:
                dropped_edges.append(
                    {
                        "edge_id": eid,
                        "dependent_key": dep,
                        "blocker_key": blk,
                        "asserted_at": fmt_instant(at),
                        "drop_reason": "EDGE_OUT_OF_SCOPE",
                    }
                )
                continue
            live_edges.append(
                {
                    "edge_id": eid,
                    "dependent_key": dep,
                    "blocker_key": blk,
                    "asserted_at": fmt_instant(at),
                    "dependent_actor": handle_to_actor[fold(dh)],
                    "blocker_actor": handle_to_actor[fold(bh)],
                }
            )

    live_edges.sort(key=lambda e: (e["dependent_key"], e["blocker_key"], e["edge_id"]))
    dropped_edges.sort(key=lambda e: (e["drop_reason"], e["edge_id"]))

    # ------------------------------------------------ closure over live edges
    HOLD = ("OPEN", "DEFERRED")
    adj: dict[str, set] = {}
    for e in live_edges:
        if resolved_state.get(e["blocker_key"]) in HOLD:
            adj.setdefault(e["dependent_key"], set()).add(e["blocker_key"])

    # A cycle is a set of holding commitments where each reaches the next and
    # the last reaches the first, which is exactly a strongly connected
    # component of two or more nodes. Tarjan, iterative so a deep graph cannot
    # exhaust the interpreter stack.
    index_of: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set = set()
    scc_stack: list = []
    counter = [0]
    in_cycle: set = set()

    for root in sorted(adj):
        if root in index_of:
            continue
        work = [(root, iter(sorted(adj.get(root, ()))))]
        index_of[root] = low[root] = counter[0]
        counter[0] += 1
        scc_stack.append(root)
        on_stack.add(root)
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index_of:
                    index_of[nxt] = low[nxt] = counter[0]
                    counter[0] += 1
                    scc_stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(sorted(adj.get(nxt, ())))))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index_of[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index_of[node]:
                component = []
                while True:
                    m = scc_stack.pop()
                    on_stack.discard(m)
                    component.append(m)
                    if m == node:
                        break
                if len(component) > 1:
                    in_cycle.update(component)

    closure_rows = []
    blocked_rows = []
    for n in sorted(adj):
        if n in in_cycle:
            continue
        reach = {}
        frontier = [(m, 1) for m in sorted(adj.get(n, ()))]
        while frontier:
            m, d = frontier.pop(0)
            if m in reach and reach[m] <= d:
                continue
            reach[m] = d
            for k in sorted(adj.get(m, ())):
                if k not in reach:
                    frontier.append((k, d + 1))
        if not reach:
            continue
        terminals = sorted(m for m in reach if not adj.get(m))
        for m in sorted(reach):
            closure_rows.append(
                {
                    "dependent_key": n,
                    "blocker_key": m,
                    "hop_distance": reach[m],
                    "blocker_state": resolved_state.get(m, "OPEN"),
                    "terminal": "yes" if not adj.get(m) else "no",
                }
            )
        blocked_rows.append(
            {
                "commitment_key": n,
                "reachable_blockers": len(reach),
                "frontier_count": len(terminals),
                "chain_depth": max(reach.values()),
                "frontier_head": terminals[0] if terminals else "",
            }
        )

    closure_rows.sort(key=lambda r: (r["dependent_key"], r["blocker_key"]))
    blocked_rows.sort(key=lambda r: r["commitment_key"])
    blocked_set = {r["commitment_key"] for r in blocked_rows}

    # Wait (glossary): zero off the blocked set, else one more than the
    # greatest wait among the blockers of the blocking edges leaving it.
    # Blocked commitments never sit on a cycle, so the recursion is finite.
    wait: dict[str, int] = {}
    for root in sorted(blocked_set):
        todo = [root]
        while todo:
            top = todo[-1]
            if top in wait:
                todo.pop()
                continue
            pending = [b for b in sorted(adj.get(top, ())) if b in blocked_set and b not in wait]
            if pending:
                todo.extend(pending)
                continue
            todo.pop()
            wait[top] = 1 + max((wait.get(b, 0) for b in adj.get(top, ())), default=0)

    st.update(
        {
            "winners": winners,
            "contest_rows": contest_rows,
            "resolved_state": resolved_state,
            "state_trace": state_trace,
            "live_edges": live_edges,
            "dropped_edges": dropped_edges,
            "closure_rows": closure_rows,
            "blocked_rows": blocked_rows,
            "blocked_set": blocked_set,
            "wait": wait,
            "in_cycle": in_cycle,
            "rejects": rejects,
            "rows_ingested": rows_ingested,
            "states_ingested": states_ingested,
            "edges_ingested": edges_ingested,
            "illegal": illegal,
            "adj": adj,
            "groups": groups,
            "state_rows": state_rows,
        }
    )
    return st


CLASSES = ("ACTIONABLE", "BLOCKED", "DEFERRED", "SETTLED", "UNRESOLVABLE", "WITHDRAWN")
OPEN_CLASSES = ("ACTIONABLE", "BLOCKED", "DEFERRED")
ALLOC_FLOOR = 15
WAIVER_ALLOWANCE = 4
RESERVE_PER_BLOCKED = 30
RESERVE_PER_WAIVED = 15


def compute(data_dir: str) -> dict:
    st = reconcile(data_dir)
    winners = st["winners"]
    state = st["resolved_state"]
    blocked_set = st["blocked_set"]
    in_cycle = st["in_cycle"]
    res = st["res"]
    projects = st["projects"]

    # ------------------------------------------------ ledger and classes
    ledger = []
    unresolvable = []
    for key in sorted(winners):
        w = winners[key]
        s = state[key]
        reason = ""
        if s == "SETTLED":
            cls = "SETTLED"
        elif s == "WITHDRAWN":
            cls = "WITHDRAWN"
        elif key in in_cycle:
            cls, reason = "UNRESOLVABLE", "CIRCULAR_DEPENDENCY"
        elif w["obligee_status"] == "AMBIGUOUS":
            cls, reason = "UNRESOLVABLE", "AMBIGUOUS_COUNTERPARTY"
        elif key in blocked_set:
            cls = "BLOCKED"
        elif s == "DEFERRED":
            cls = "DEFERRED"
        else:
            cls = "ACTIONABLE"
        ledger.append(
            {
                "commitment_key": key,
                "obligor_actor": w["obligor_actor"],
                "obligee_actor": w["obligee_actor"],
                "project_code": w["project_code"],
                "project_root": w["project_root"],
                "commitment_day": w["commitment_day"],
                "due_at": w["due_at"],
                "effort_minutes": w["effort_minutes"],
                "effort_origin": w["effort_origin"],
                "resolved_state": s,
                "commitment_class": cls,
                "cadence_ref": w["cadence_ref"],
                "source_class": w["source_class"],
                "winning_assertion": w["assertion_id"],
            }
        )
        if reason:
            unresolvable.append(
                {
                    "commitment_key": key,
                    "reason_code": reason,
                    "obligor_actor": w["obligor_actor"],
                    "commitment_day": w["commitment_day"],
                }
            )

    # canonical order: day, then obligor, then DESCENDING effort, then key
    ledger.sort(
        key=lambda r: (
            r["commitment_day"],
            r["obligor_actor"],
            -r["effort_minutes"],
            r["commitment_key"],
        )
    )
    unresolvable.sort(key=lambda r: (r["reason_code"], r["commitment_key"]))
    by_key = {r["commitment_key"]: r for r in ledger}

    # how many adjacent pairs the descending effort tiebreak actually decided
    tie_breaks = 0
    for a, b in zip(ledger, ledger[1:]):
        if (
            a["commitment_day"] == b["commitment_day"]
            and a["obligor_actor"] == b["obligor_actor"]
            and a["effort_minutes"] != b["effort_minutes"]
        ):
            tie_breaks += 1

    # ------------------------------------------------ cadence debt
    # The owner of a cadence is its obligor surface resolved at the anchor.
    owner_of: dict[str, str] = {}
    for cid in sorted(st["cadences"]):
        c = st["cadences"][cid]
        handle, _why, _p = res.resolve_handle(c["obligor"], c["anchor_at"])
        if handle is None:
            continue
        aid = st["handle_to_actor"].get(fold(handle))
        if aid:
            owner_of[cid] = aid
    # One allowance per principal, drawn by every waiver in an elapsed period
    # of a cadence it owns, by period start and then cadence id.
    draws: dict[str, list] = {}
    for cid in sorted(st["cadences"]):
        if cid not in owner_of:
            continue
        c = st["cadences"][cid]
        for p in sorted(st["waivers"].get(cid, ())):
            p0 = c["anchor_at"] + p * c["period_days"] * 1440
            if p >= 0 and p0 < WINDOW_END:
                draws.setdefault(owner_of[cid], []).append((p0, cid, p))
    lapsed_set = set()
    for aid, items in draws.items():
        items.sort()
        lapsed_set.update((cid, p) for _p0, cid, p in items[WAIVER_ALLOWANCE:])
    cadence_rows = []
    waiver_trace = []
    inert_waivers = 0
    suppressed = 0
    lapsed_count = 0
    discharges_by_cad: dict[str, dict] = {}
    for r in ledger:
        cid = r["cadence_ref"]
        if cid and r["commitment_class"] == "SETTLED":
            discharges_by_cad.setdefault(cid, {})
            t = parse_instant(r["due_at"])
            discharges_by_cad[cid].setdefault(t, []).append(r["commitment_key"])

    for cid in sorted(st["cadences"]):
        c = st["cadences"][cid]
        span = c["period_days"] * 1440
        debt = streak = maxstreak = 0
        periods = discharged = waived = 0
        p = 0
        while True:
            p0 = c["anchor_at"] + p * span
            if p0 >= WINDOW_END:
                break
            p1 = min(p0 + span, WINDOW_END)
            periods += 1
            hits = [
                k
                for t, ks in discharges_by_cad.get(cid, {}).items()
                if p0 <= t < p1
                for k in ks
            ]
            has_waiver = p in st["waivers"].get(cid, ())
            if has_waiver and (cid, p) in lapsed_set:
                has_waiver = False
                lapsed_count += 1
                waiver_trace.append(
                    {
                        "cadence_id": cid,
                        "period_index": p,
                        "effect": "LAPSED",
                        "period_start": fmt_instant(p0),
                    }
                )
            if hits:
                streak = 0
                discharged += 1
                if has_waiver:
                    inert_waivers += 1
                    waiver_trace.append(
                        {
                            "cadence_id": cid,
                            "period_index": p,
                            "effect": "INERT",
                            "period_start": fmt_instant(p0),
                        }
                    )
            elif has_waiver:
                waived += 1
                suppressed += 1
                waiver_trace.append(
                    {
                        "cadence_id": cid,
                        "period_index": p,
                        "effect": "SUPPRESSED",
                        "period_start": fmt_instant(p0),
                    }
                )
            else:
                debt += 1
                streak += 1
                maxstreak = max(maxstreak, streak)
            p += 1
        cadence_rows.append(
            {
                "cadence_id": cid,
                "period_days": c["period_days"],
                "periods_elapsed": periods,
                "periods_discharged": discharged,
                "periods_waived": waived,
                "debt": debt,
                "max_streak": maxstreak,
            }
        )
    cadence_rows.sort(key=lambda r: r["cadence_id"])
    waiver_trace.sort(key=lambda r: (r["cadence_id"], r["period_index"]))

    # ------------------------------------------------ attention allocation
    per_day: dict[tuple, list] = {}
    for r in ledger:
        if r["commitment_class"] in OPEN_CLASSES and r["effort_minutes"] > 0:
            per_day.setdefault(
                (r["commitment_day"][:7], r["obligor_actor"]), []
            ).append(r)

    # The reserve couples the envelope to the blocked set and the waived count.
    blocked_in: dict[tuple, int] = {}
    for b in st["blocked_rows"]:
        r = by_key[b["commitment_key"]]
        slot = (r["commitment_day"][:7], r["obligor_actor"])
        blocked_in[slot] = blocked_in.get(slot, 0) + st["wait"][b["commitment_key"]]
    waived_by_actor: dict[str, int] = {}
    for row in cadence_rows:
        aid = owner_of.get(row["cadence_id"])
        if aid:
            waived_by_actor[aid] = waived_by_actor.get(aid, 0) + row["periods_waived"]

    alloc_rows = []
    day_rows = []
    starved = 0
    for ym, actor in sorted(per_day):
        items = sorted(per_day[(ym, actor)], key=lambda r: r["commitment_key"])
        budget = st["budget_day"].get((actor, ym))
        source = "OVERRIDE"
        if budget is None:
            budget = st["budget_month"].get((actor, ym))
            source = "REGISTERED"
        if budget is None:
            budget = 0
            source = "ABSENT"
        reserve = RESERVE_PER_BLOCKED * blocked_in.get((ym, actor), 0) + (
            RESERVE_PER_WAIVED * waived_by_actor.get(actor, 0)
        )
        usable = max(0, budget - reserve)
        demand = sum(r["effort_minutes"] for r in items)
        weights = {r["commitment_key"]: r["effort_minutes"] for r in items}
        if demand <= usable:
            share = dict(weights)
        else:
            share = largest_remainder(weights, usable)
            keep = {k: weights[k] for k, v in share.items() if v >= ALLOC_FLOOR}
            dropped = [k for k, v in share.items() if v < ALLOC_FLOOR]
            starved += len(dropped)
            if keep:
                share = largest_remainder(keep, usable)
                for k in dropped:
                    share[k] = 0
            else:
                share = {k: 0 for k in weights}
        for r in items:
            alloc_rows.append(
                {
                    "year_month": ym,
                    "obligor_actor": actor,
                    "commitment_key": r["commitment_key"],
                    "demand_minutes": r["effort_minutes"],
                    "allocated_minutes": share.get(r["commitment_key"], 0),
                }
            )
        day_rows.append(
            {
                "year_month": ym,
                "obligor_actor": actor,
                "budget_source": source,
                "budget_minutes": budget,
                "reserve_minutes": reserve,
                "demand_minutes": demand,
                "allocated_minutes": sum(share.values()),
                "open_count": len(items),
            }
        )
    alloc_rows.sort(
        key=lambda r: (r["year_month"], r["obligor_actor"], r["commitment_key"])
    )
    day_rows.sort(key=lambda r: (r["year_month"], r["obligor_actor"]))

    # ------------------------------------------------ rollups
    actor_roll: dict[str, dict] = {}
    proj_roll: dict[str, dict] = {}
    alloc_by_actor: dict[str, int] = {}
    alloc_by_root: dict[str, int] = {}
    for a in alloc_rows:
        alloc_by_actor[a["obligor_actor"]] = (
            alloc_by_actor.get(a["obligor_actor"], 0) + a["allocated_minutes"]
        )
        root = by_key[a["commitment_key"]]["project_root"]
        alloc_by_root[root] = alloc_by_root.get(root, 0) + a["allocated_minutes"]

    for r in ledger:
        for bucket, kname in (
            (actor_roll, r["obligor_actor"]),
            (proj_roll, r["project_root"]),
        ):
            e = bucket.setdefault(kname, {c: 0 for c in CLASSES})
            e[r["commitment_class"]] += 1
            e.setdefault("open_effort_minutes", 0)
            e.setdefault("commitment_count", 0)
            e["commitment_count"] += 1
            if r["commitment_class"] in OPEN_CLASSES:
                e["open_effort_minutes"] += r["effort_minutes"]
    for k, e in actor_roll.items():
        e["allocated_minutes"] = alloc_by_actor.get(k, 0)
    for k, e in proj_roll.items():
        e["allocated_minutes"] = alloc_by_root.get(k, 0)

    open_total = sum(
        r["effort_minutes"] for r in ledger if r["commitment_class"] in OPEN_CLASSES
    )

    # ------------------------------------------------ provenance
    prov = []
    for key in sorted(st["groups"]):
        rows = sorted(st["groups"][key], key=lambda r: r["assertion_id"])
        prov.append(
            {
                "commitment_key": key,
                "winning_assertion": winners[key]["assertion_id"],
                "contributing_assertions": [r["assertion_id"] for r in rows],
                "source_files": sorted({r["feed_file"] for r in rows}),
                "state_assertions": sorted(
                    s["state_id"]
                    for s in st["state_rows"]
                    if s["commitment_key"] == key
                ),
            }
        )

    # ------------------------------------------------ surface resolution
    surf: dict[str, dict] = {}
    for r in st["normalized"]:
        f = fold(r["obligor_surface"])
        e = surf.setdefault(f, {"actors": set(), "count": 0, "hops": 0})
        e["actors"].add(r["obligor_actor"])
        e["count"] += 1
        e["hops"] = max(e["hops"], r["obligor_hops"])
    alias_rows = [
        {
            "surface_folded": k,
            "distinct_actors": sorted(v["actors"]),
            "assertion_count": v["count"],
            "max_hops": v["hops"],
        }
        for k, v in sorted(surf.items())
    ]
    split_surfaces = sum(1 for v in surf.values() if len(v["actors"]) > 1)
    multi_hop = sum(1 for r in st["normalized"] if r["obligor_hops"] >= 2)

    # ------------------------------------------------ project lineage
    pl: dict[str, set] = {}
    for r in st["normalized"]:
        pl.setdefault(r["project_code"], set()).add(r["project_root"])
    lineage_rows = [
        {
            "project_code": k,
            "project_root": sorted(v)[0],
            "assertion_count": sum(
                1 for r in st["normalized"] if r["project_code"] == k
            ),
        }
        for k, v in sorted(pl.items())
    ]

    # ------------------------------------------------ escalation queue
    # A node with four parents: the class, the envelope share, the debt the
    # principal carries across every cadence it owns, and the closure depth.
    # The cadence obligor is a surface like any other and is resolved at the
    # cadence anchor. A cadence whose obligor stands for nobody at that instant
    # is owned by nobody, and the debt it carries reaches no principal.
    debt_by_actor: dict[str, int] = {}
    debt_rows = {r["cadence_id"]: r for r in cadence_rows}
    for cid in sorted(st["cadences"]):
        aid = owner_of.get(cid)
        if not aid:
            continue
        row = debt_rows.get(cid)
        if row:
            debt_by_actor[aid] = debt_by_actor.get(aid, 0) + row["debt"]
    depth_by_key = {r["commitment_key"]: r["chain_depth"] for r in st["blocked_rows"]}
    alloc_by_key = {r["commitment_key"]: r["allocated_minutes"] for r in alloc_rows}
    final_month = "2032-11"
    escalation = []
    for r in ledger:
        if r["commitment_class"] not in ("ACTIONABLE", "BLOCKED"):
            continue
        allocated = alloc_by_key.get(r["commitment_key"], 0)
        if allocated >= r["effort_minutes"]:
            continue
        pdebt = debt_by_actor.get(r["obligor_actor"], 0)
        if pdebt < 4:
            continue
        depth = depth_by_key.get(r["commitment_key"], 0)
        by_depth = depth >= 2
        by_month = r["commitment_day"][:7] == final_month
        if not (by_depth or by_month):
            continue
        escalation.append(
            {
                "commitment_key": r["commitment_key"],
                "obligor_actor": r["obligor_actor"],
                "commitment_class": r["commitment_class"],
                "effort_minutes": r["effort_minutes"],
                "allocated_minutes": allocated,
                "shortfall_minutes": r["effort_minutes"] - allocated,
                "principal_debt": pdebt,
                "chain_depth": depth,
                "trigger": (
                    "BOTH"
                    if by_depth and by_month
                    else ("DEPTH" if by_depth else "MONTH")
                ),
            }
        )
    escalation.sort(key=lambda r: (-r["shortfall_minutes"], r["commitment_key"]))

    st.update(
        {
            "escalation": escalation,
            "debt_by_actor": debt_by_actor,
            "ledger": ledger,
            "by_key": by_key,
            "unresolvable": unresolvable,
            "cadence_rows": cadence_rows,
            "waiver_trace": waiver_trace,
            "alloc_rows": alloc_rows,
            "day_rows": day_rows,
            "actor_roll": actor_roll,
            "proj_roll": proj_roll,
            "prov": prov,
            "alias_rows": alias_rows,
            "lineage_rows": lineage_rows,
            "open_total": open_total,
            "tie_breaks": tie_breaks,
            "split_surfaces": split_surfaces,
            "multi_hop": multi_hop,
            "inert_waivers": inert_waivers,
            "suppressed": suppressed,
            "lapsed": lapsed_count,
            "drawn": {
                aid: (min(len(items), WAIVER_ALLOWANCE), max(0, len(items) - WAIVER_ALLOWANCE))
                for aid, items in draws.items()
            },
            "starved": starved,
        }
    )
    return st


CLASSES = ("ACTIONABLE", "BLOCKED", "DEFERRED", "SETTLED", "UNRESOLVABLE", "WITHDRAWN")
OPEN_CLASSES = ("ACTIONABLE", "BLOCKED", "DEFERRED")

REASON_CODES = (
    "AMBIGUOUS_IDENTITY",
    "FEED_RETIRED",
    "ILLEGAL_TRANSITION",
    "MALFORMED_ROW",
    "NONPOSITIVE_EFFORT",
    "OUT_OF_WINDOW",
    "UNKNOWN_COMMITMENT",
    "UNKNOWN_PRINCIPAL",
    "UNKNOWN_PROJECT",
)


def _w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def wr_jsonl(path, rows):
    _w(
        path,
        "".join(
            json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows
        ),
    )


def wr_json(path, obj):
    _w(path, json.dumps(obj, sort_keys=True, indent=2) + "\n")


def wr_table(path, cols, rows, sep=","):
    out = [sep.join(cols)]
    for r in rows:
        out.append(sep.join(str(r[c]) for c in cols))
    _w(path, "\n".join(out) + "\n")


def wr_text(path, lines):
    _w(path, "\n".join(lines) + "\n")


def write_all(st, out_dir):
    given = {a["commitment_key"]: a["allocated_minutes"] for a in st["alloc_rows"]}
    held = {r["commitment_key"] for r in st["blocked_rows"]}
    L = [dict(r, allocated_minutes=given.get(r["commitment_key"], 0)) for r in st["ledger"]]

    wr_jsonl(
        os.path.join(out_dir, "normalized_assertions.jsonl"),
        [
            {
                k: r[k]
                for k in (
                    "assertion_id",
                    "commitment_key",
                    "obligor_actor",
                    "obligee_actor",
                    "obligee_status",
                    "project_code",
                    "project_root",
                    "due_at",
                    "commitment_day",
                    "effort_minutes",
                    "effort_origin",
                    "cadence_ref",
                    "observed_at",
                    "source_class",
                )
            }
            for r in st["normalized"]
        ],
    )

    wr_table(
        os.path.join(out_dir, "rejects.csv"),
        (
            "feed_file",
            "row_index",
            "record_kind",
            "record_id",
            "commitment_key",
            "reason_code",
        ),
        sorted(
            st["rejects"],
            key=lambda r: (
                r["reason_code"],
                r["feed_file"],
                r["row_index"],
                r["record_id"],
            ),
        ),
    )

    wr_jsonl(os.path.join(out_dir, "alias_resolution.jsonl"), st["alias_rows"])

    wr_table(
        os.path.join(out_dir, "actor_roster.csv"),
        (
            "actor_id",
            "canonical_handle",
            "commitment_count",
            "open_effort_minutes",
            "waivers_granted",
            "waivers_lapsed",
        ),
        [
            {
                "actor_id": a,
                "canonical_handle": min(
                    st["spellings"][a],
                    key=lambda h: (-st["spellings"][a][h], h),
                ),
                "commitment_count": st["actor_roll"]
                .get(a, {})
                .get("commitment_count", 0),
                "open_effort_minutes": st["actor_roll"]
                .get(a, {})
                .get("open_effort_minutes", 0),
                "waivers_granted": st["drawn"].get(a, (0, 0))[0],
                "waivers_lapsed": st["drawn"].get(a, (0, 0))[1],
            }
            for a in sorted(set(st["roster"].values()))
        ],
    )

    wr_table(
        os.path.join(out_dir, "project_lineage.csv"),
        ("project_code", "project_root", "assertion_count", "allocated_minutes"),
        [
            dict(
                r,
                allocated_minutes=sum(
                    given.get(c["commitment_key"], 0)
                    for c in st["ledger"]
                    if c["project_code"] == r["project_code"]
                ),
            )
            for r in st["lineage_rows"]
        ],
    )

    wr_table(
        os.path.join(out_dir, "assertion_contests.csv"),
        (
            "commitment_key",
            "winning_assertion",
            "winning_class",
            "contender_count",
            "distinct_classes",
        ),
        st["contest_rows"],
    )

    wr_jsonl(os.path.join(out_dir, "commitment_ledger.jsonl"), L)

    wr_table(
        os.path.join(out_dir, "state_resolution.csv"),
        (
            "commitment_key",
            "resolved_state",
            "assertions_seen",
            "assertions_applied",
            "governing_class",
        ),
        st["state_trace"],
    )

    wr_table(
        os.path.join(out_dir, "live_edges.csv"),
        (
            "edge_id",
            "dependent_key",
            "blocker_key",
            "asserted_at",
            "dependent_actor",
            "blocker_actor",
            "dependent_blocked",
        ),
        [
            dict(r, dependent_blocked="yes" if r["dependent_key"] in held else "no")
            for r in st["live_edges"]
        ],
    )

    wr_table(
        os.path.join(out_dir, "dropped_edges.csv"),
        ("edge_id", "dependent_key", "blocker_key", "asserted_at", "drop_reason"),
        st["dropped_edges"],
    )

    wr_jsonl(os.path.join(out_dir, "blocking_closure.jsonl"), st["closure_rows"])

    wr_table(
        os.path.join(out_dir, "blocked_commitments.csv"),
        (
            "commitment_key",
            "reachable_blockers",
            "frontier_count",
            "chain_depth",
            "frontier_head",
            "allocated_minutes",
        ),
        [
            dict(r, allocated_minutes=given.get(r["commitment_key"], 0))
            for r in st["blocked_rows"]
        ],
    )
    q = [
        dict(r, allocated_minutes=given.get(r["commitment_key"], 0))
        for r in L
        if r["commitment_class"] == "ACTIONABLE"
    ]
    wr_table(
        os.path.join(out_dir, "actionable_queue.tsv"),
        (
            "commitment_key",
            "obligor_actor",
            "commitment_day",
            "effort_minutes",
            "project_root",
            "allocated_minutes",
        ),
        q,
        sep="\t",
    )

    d = [
        dict(r, allocated_minutes=given.get(r["commitment_key"], 0))
        for r in L
        if r["commitment_class"] == "DEFERRED"
    ]
    wr_table(
        os.path.join(out_dir, "deferred_queue.psv"),
        (
            "commitment_key",
            "obligor_actor",
            "commitment_day",
            "effort_minutes",
            "project_root",
            "allocated_minutes",
        ),
        d,
        sep="|",
    )

    wd = [r for r in L if r["commitment_class"] == "WITHDRAWN"]
    wr_table(
        os.path.join(out_dir, "withdrawn_register.csv"),
        (
            "commitment_key",
            "obligor_actor",
            "commitment_day",
            "effort_minutes",
            "source_class",
        ),
        wd,
    )

    wr_jsonl(os.path.join(out_dir, "unresolvable.jsonl"), st["unresolvable"])

    wr_table(
        os.path.join(out_dir, "cadence_debt.csv"),
        (
            "cadence_id",
            "period_days",
            "periods_elapsed",
            "periods_discharged",
            "periods_waived",
            "debt",
            "max_streak",
        ),
        st["cadence_rows"],
    )

    wr_jsonl(os.path.join(out_dir, "waiver_trace.jsonl"), st["waiver_trace"])

    wr_table(
        os.path.join(out_dir, "attention_allocation.csv"),
        (
            "year_month",
            "obligor_actor",
            "commitment_key",
            "demand_minutes",
            "allocated_minutes",
        ),
        st["alloc_rows"],
    )

    wr_table(
        os.path.join(out_dir, "month_load_index.csv"),
        (
            "year_month",
            "obligor_actor",
            "budget_source",
            "budget_minutes",
            "reserve_minutes",
            "demand_minutes",
            "allocated_minutes",
            "open_count",
        ),
        st["day_rows"],
    )

    wr_table(
        os.path.join(out_dir, "escalation_queue.csv"),
        (
            "commitment_key",
            "obligor_actor",
            "commitment_class",
            "effort_minutes",
            "allocated_minutes",
            "shortfall_minutes",
            "principal_debt",
            "chain_depth",
            "trigger",
        ),
        st["escalation"],
    )

    wr_json(os.path.join(out_dir, "actor_rollup.json"), st["actor_roll"])
    wr_json(os.path.join(out_dir, "project_rollup.json"), st["proj_roll"])
    wr_jsonl(os.path.join(out_dir, "provenance_index.jsonl"), st["prov"])

    # ---------------------------------------------------------- audit
    counts = {c: 0 for c in CLASSES}
    for r in L:
        counts[r["commitment_class"]] += 1
    rej_counts = {c: 0 for c in REASON_CODES}
    for r in st["rejects"]:
        rej_counts[r["reason_code"]] = rej_counts.get(r["reason_code"], 0) + 1

    audit = []
    audit.append({"metric": "rows_ingested", "value": st["rows_ingested"]})
    audit.append({"metric": "rows_rejected", "value": len(st["rejects"])})
    audit.append(
        {"metric": "rows_accepted", "value": st["rows_ingested"] - len(st["rejects"])}
    )
    audit.append({"metric": "commitments_admitted", "value": len(L)})
    for c in CLASSES:
        audit.append({"metric": f"class_{c.lower()}", "value": counts[c]})
    for c in REASON_CODES:
        audit.append({"metric": f"reject_{c.lower()}", "value": rej_counts[c]})
    audit.append({"metric": "live_edges", "value": len(st["live_edges"])})
    audit.append({"metric": "dropped_edges", "value": len(st["dropped_edges"])})
    audit.append({"metric": "closure_pairs", "value": len(st["closure_rows"])})
    audit.append({"metric": "blocked_commitments", "value": len(st["blocked_rows"])})
    audit.append({"metric": "open_effort_minutes", "value": st["open_total"]})
    audit.append(
        {
            "metric": "allocated_minutes",
            "value": sum(r["allocated_minutes"] for r in st["alloc_rows"]),
        }
    )
    audit.append({"metric": "escalated_commitments", "value": len(st["escalation"])})
    audit.append(
        {
            "metric": "cadence_debt_total",
            "value": sum(r["debt"] for r in st["cadence_rows"]),
        }
    )
    wr_table(os.path.join(out_dir, "audit_totals.csv"), ("metric", "value"), audit)

    # ---------------------------------------------------------- identities
    i1 = (
        st["rows_ingested"]
        - len(st["rejects"])
        - len(st["normalized"])
        - len(st["state_rows"])
        + st["illegal"]
        - len(st["live_edges"])
        - len(st["dropped_edges"])
    )
    i2 = len(L) - sum(counts.values())
    i3 = (
        sum(e["open_effort_minutes"] for e in st["actor_roll"].values())
        - st["open_total"]
    )
    i4 = (
        sum(e["open_effort_minutes"] for e in st["proj_roll"].values())
        - st["open_total"]
    )
    i5 = sum(r["frontier_count"] for r in st["blocked_rows"]) - sum(
        1 for r in st["closure_rows"] if r["terminal"] == "yes"
    )
    ident = {
        "I1_row_partition": i1,
        "I2_class_partition": i2,
        "I3_actor_effort": i3,
        "I4_project_effort": i4,
        "I5_closure_frontier": i5,
    }
    wr_json(
        os.path.join(out_dir, "validation_report.json"),
        {
            "identities": ident,
            "identities_checked": sorted(ident),
            "all_residuals_zero": all(v == 0 for v in ident.values()),
        },
    )

    wr_json(
        os.path.join(out_dir, "run_manifest.json"),
        {
            "day_boundary_offset_minutes": 240,
            "effort_floor_minutes": 15,
            "effort_ceiling_minutes": 480,
            "allocation_floor_minutes": 15,
            "window_start": "2032-03-01T00:00Z",
            "window_end": "2032-12-01T00:00Z",
            "reason_codes": list(REASON_CODES),
            "commitment_classes": list(CLASSES),
            "retired_feeds": sorted(st["retired_at"]),
            "split_surfaces": st["split_surfaces"],
            "multi_hop_assertions": st["multi_hop"],
            "order_tiebreaks_applied": st["tie_breaks"],
            "edges_dropped_out_of_scope": sum(
                1
                for e in st["dropped_edges"]
                if e["drop_reason"] == "EDGE_OUT_OF_SCOPE"
            ),
            "waivers_suppressing": st["suppressed"],
            "waivers_inert": st["inert_waivers"],
            "waivers_lapsed": st["lapsed"],
            "allocations_starved": st["starved"],
            "illegal_transitions": st["illegal"],
        },
    )

    wr_text(
        os.path.join(out_dir, "reconciliation.txt"),
        [
            "CALDERMOOR COMMITMENT CLOSURE",
            f"rows_ingested {st['rows_ingested']}",
            f"rows_rejected {len(st['rejects'])}",
            f"commitments_admitted {len(L)}",
            *[f"class_{c.lower()} {counts[c]}" for c in CLASSES],
            f"live_edges {len(st['live_edges'])}",
            f"dropped_edges {len(st['dropped_edges'])}",
            f"closure_pairs {len(st['closure_rows'])}",
            f"blocked_commitments {len(st['blocked_rows'])}",
            f"open_effort_minutes {st['open_total']}",
            f"allocated_minutes {sum(r['allocated_minutes'] for r in st['alloc_rows'])}",
            f"escalated_commitments {len(st['escalation'])}",
            f"cadence_debt_total {sum(r['debt'] for r in st['cadence_rows'])}",
            *[f"identity_{k} {v}" for k, v in sorted(ident.items())],
        ],
    )


def build_all(seed):
    """The whole shipped extract for one seed, as a name to text mapping."""
    drop = _SHIPPED_DROP if seed == SHIPPED_SEED else frozenset()
    files, w = build_corpus(seed, drop)
    ex, _defaults = build_extra(seed, w, RETIRED, drop)
    files.update(ex)
    return files, w


# The shipped extract leaves out these edges and waivers; every other seed
# keeps them.
_SHIPPED_DROP = frozenset(
    [f"EDG-{n:06d}" for n in (
        3, 7, 13, 15, 19, 21, 28, 40, 43, 44, 46, 58, 60, 80, 87, 89, 98,
        99, 103, 106, 108, 113, 124, 128, 133, 135, 156, 174, 176, 177, 182,
        185, 200, 204, 209, 213, 228, 240, 241, 244, 248, 252, 260, 264,
        268, 273, 276, 279, 284, 301, 304, 313, 314, 315, 321, 322, 324,
        327, 330, 342, 345, 347, 354, 356, 357, 362, 364, 371, 374, 381, 384,
        385, 402, 407, 411, 414, 415, 418, 424, 429, 431, 432, 434, 441,
        452, 454, 455, 456, 461, 465, 466, 471, 484, 485, 487, 491, 497, 502,
        516, 528, 532, 533, 542, 551, 565, 570, 574, 582, 594, 595, 602,
        609, 611, 622, 628, 644, 645, 664, 665, 667, 674, 680, 691, 696,
        706, 716, 725, 730, 739, 752, 760, 762, 769, 784, 798, 800, 806,
        812, 814, 816, 829, 834, 851, 861, 873, 876, 881, 892, 899, 904,
        905, 912, 918, 941, 944, 956, 959, 970, 978, 992, 997, 1001, 1008,
        1020, 1024, 1027, 1028, 1032, 1033, 1036, 1046, 1065, 1066, 1067,
        1076, 1078, 1085, 1093, 1096, 1098, 1099, 1103, 1104, 1108, 1146,
        1147, 1149, 1152, 1153, 1155, 1162, 1170, 1182, 1190, 1193, 1196,
        1201, 1202, 1205, 1207, 1212, 1215, 1218, 1220, 1222, 1234, 1244,
        1248, 1251, 1258, 1264, 1267, 1274, 1277, 1280, 1285, 1287, 1288,
        1294, 1296, 1300, 1304, 1307, 1313, 1321, 1324, 1325, 1333, 1339,
        1343, 1345, 1346, 1355, 1357, 1359, 1361, 1364, 1369, 1371, 1373,
        1377, 1380, 1386, 1389, 1391, 1394, 1410, 1412, 1426, 1427, 1434,
        1444, 1456, 1464
    )]
    + [
        ("CAD-003", 4), ("CAD-004", 4), ("CAD-005", 16), ("CAD-005", 33),
        ("CAD-006", 3), ("CAD-006", 15), ("CAD-008", 18), ("CAD-008", 27),
        ("CAD-008", 38), ("CAD-009", 0), ("CAD-009", 2), ("CAD-009", 5),
        ("CAD-010", 6), ("CAD-010", 10), ("CAD-011", 8), ("CAD-015", 3),
        ("CAD-015", 6), ("CAD-015", 10), ("CAD-016", 1), ("CAD-016", 3),
        ("CAD-016", 16), ("CAD-017", 7), ("CAD-017", 33), ("CAD-018", 34),
        ("CAD-019", 4), ("CAD-019", 6), ("CAD-020", 1), ("CAD-021", 6),
        ("CAD-023", 9), ("CAD-023", 17), ("CAD-024", 11), ("CAD-025", 3),
        ("CAD-026", 5), ("CAD-026", 30), ("CAD-026", 36), ("CAD-027", 3),
        ("CAD-028", 6), ("CAD-028", 7), ("CAD-029", 3), ("CAD-029", 11),
        ("CAD-030", 30), ("CAD-031", 26), ("CAD-032", 6), ("CAD-033", 8),
        ("CAD-034", 7), ("CAD-034", 13), ("CAD-034", 15), ("CAD-035", 22),
        ("CAD-036", 0), ("CAD-036", 7), ("CAD-037", 7), ("CAD-038", 33),
        ("CAD-042", 8), ("CAD-042", 31), ("CAD-042", 32), ("CAD-042", 36),
        ("CAD-043", 5), ("CAD-046", 0), ("CAD-046", 4), ("CAD-046", 5),
        ("CAD-048", 1), ("CAD-048", 11), ("CAD-051", 5), ("CAD-052", 2),
        ("CAD-052", 9), ("CAD-053", 19), ("CAD-053", 31), ("CAD-054", 8),
        ("CAD-056", 0), ("CAD-057", 32), ("CAD-058", 36), ("CAD-058", 37),
        ("CAD-059", 2), ("CAD-059", 19)
    ]
)


# --------------------------------------------------------------- harness

OUT = "/app/out"
PROGRAM = os.path.join(OUT, "reconcile.py")

SHIPPED_SEED = 20320917
EVAL_SEEDS = (77431905, 51208764, 93017226)
# One extract per rule probe. A solver that tunes itself to a single corpus
# passes none of the others, and no probe shares a fixture with another.
PROBE_SEEDS = (
    4100011,
    4100023,
    4100037,
    4100041,
    4100059,
    4100063,
    4100077,
    4100081,
    4100093,
    4100107,
    4100119,
    4100123,
    4100137,
)
RUN_TIMEOUT_SEC = 100

ARTIFACTS = (
    "reconcile.py",
    "normalized_assertions.jsonl",
    "rejects.csv",
    "alias_resolution.jsonl",
    "actor_roster.csv",
    "project_lineage.csv",
    "assertion_contests.csv",
    "commitment_ledger.jsonl",
    "state_resolution.csv",
    "live_edges.csv",
    "dropped_edges.csv",
    "blocking_closure.jsonl",
    "blocked_commitments.csv",
    "actionable_queue.tsv",
    "deferred_queue.psv",
    "withdrawn_register.csv",
    "unresolvable.jsonl",
    "cadence_debt.csv",
    "waiver_trace.jsonl",
    "attention_allocation.csv",
    "month_load_index.csv",
    "escalation_queue.csv",
    "actor_rollup.json",
    "project_rollup.json",
    "provenance_index.jsonl",
    "audit_totals.csv",
    "reconciliation.txt",
    "validation_report.json",
    "run_manifest.json",
)

_CACHE = {}
_PROBE_CACHE = {}


PRECEDENCE_PROBE_FEED = "commitments_desk_01.csv"
PRECEDENCE_PROBE_ROW = "ASR-999001"


def _add_precedence_row(files):
    """Copy the feed's last row with an undeclared project and a zero effort.

    The generator damages each row in one way only, so without this row no
    extract tests UNKNOWN_PROJECT against NONPOSITIVE_EFFORT on one row.
    """
    lines = files[PRECEDENCE_PROBE_FEED].rstrip("\n").split("\n")
    head = lines[0].split(",")
    row = dict(zip(head, lines[-1].split(",")))
    row.update(assertion_id=PRECEDENCE_PROBE_ROW, project_ref="PRJ-999", effort="0")
    lines.append(",".join(row[h] for h in head))
    files[PRECEDENCE_PROBE_FEED] = "\n".join(lines) + "\n"


def _add_small_envelopes(files):
    """Override every fourth registered envelope with twenty minutes.

    Generated envelopes are far larger than any reserve, so without these
    rows no extract has a reserve that outgrows its envelope.
    """
    taken = {tuple(line.split("|")[:2]) for line in files["budget_overrides.psv"].split("\n")[1:] if line}
    pairs = sorted(tuple(line.split(",")[:2]) for line in files["attention_budget.csv"].split("\n")[1:] if line)
    extra = [f"{a}|{m}|20" for a, m in pairs[::4] if (a, m) not in taken]
    files["budget_overrides.psv"] = files["budget_overrides.psv"].rstrip("\n") + "\n" + "\n".join(extra) + "\n"


SURVIVOR_SEEDS = (4100149, 68250419)
SURVIVOR_MAX_GROUPS = 8


def _add_survivor_envelopes(files):
    """Override envelopes so that the floor's survivors fit the distributable minutes.

    Generated envelopes either cover a principal-month's whole demand or leave
    its survivors asking for more than the envelope, so without these rows no
    extract hands the survivors of the floor more minutes than they asked for.
    """
    tmp = tempfile.mkdtemp(prefix="cmsurv")
    try:
        for name, text in files.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        st = compute(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    reserve = {(r["year_month"], r["obligor_actor"]): r["reserve_minutes"] for r in st["day_rows"]}
    groups: dict = {}
    for r in st["alloc_rows"]:
        if r["demand_minutes"] > 0:
            pair = (r["year_month"], r["obligor_actor"])
            groups.setdefault(pair, {})[r["commitment_key"]] = r["demand_minutes"]
    chosen = {}
    for pair in sorted(groups):
        weights = groups[pair]
        if len(weights) < 2:
            continue
        for usable in range(ALLOC_FLOOR, sum(weights.values())):
            share = largest_remainder(weights, usable)
            keep = {k: weights[k] for k, v in share.items() if v >= ALLOC_FLOOR}
            if keep and len(keep) < len(weights) and sum(keep.values()) < usable:
                chosen[pair] = reserve[pair] + usable
                break
        if len(chosen) >= SURVIVOR_MAX_GROUPS:
            break
    if not chosen:
        raise AssertionError("no month can separate the survivors' second share")
    head, *rest = [ln for ln in files["budget_overrides.psv"].split("\n") if ln]
    kept = [ln for ln in rest if tuple(ln.split("|")[1::-1]) not in chosen]
    kept += [f"{a}|{m}|{v}" for (m, a), v in sorted(chosen.items())]
    files["budget_overrides.psv"] = "\n".join([head] + kept) + "\n"


WAIT_SEEDS = (30561877, 72914403)
WAIT_MAX_GROUPS = 10
WAIT_MIN_MONTHS = 4
WAIT_EDGE_FEED = "edges_desk_01.csv"


def _compute_files(files, prefix):
    tmp = tempfile.mkdtemp(prefix=prefix)
    try:
        for name, text in files.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        return compute(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _wait_months(st):
    """Principal-months whose reserve depends on a wait other than the chain depth."""
    owner = {k: (w["commitment_day"][:7], w["obligor_actor"]) for k, w in st["winners"].items()}
    depth = {r["commitment_key"]: r["chain_depth"] for r in st["blocked_rows"]}
    gap: dict = {}
    for key in st["blocked_set"]:
        if key in owner:
            gap[owner[key]] = gap.get(owner[key], 0) + st["wait"][key] - depth[key]
    return {pair for pair, g in gap.items() if g}


def _add_wait_shortcuts(files):
    """Add blocking edges that skip one step of an existing chain, and bind those months.

    Generated chains rarely let a commitment reach one blocker by two routes of
    different lengths, so without these rows the wait of a blocked commitment
    and its chain depth seldom part. Each added row repeats the instant of a
    live edge leaving the same dependent, so it is live whenever that one is.
    """
    st = _compute_files(files, "cmwait")
    adj, blocked = st["adj"], st["blocked_set"]
    at = {(e["dependent_key"], e["blocker_key"]): e["asserted_at"] for e in st["live_edges"]}
    owner = {k: (w["commitment_day"][:7], w["obligor_actor"]) for k, w in st["winners"].items()}
    added, months = [], set()
    for x in sorted(blocked):
        if x not in owner or owner[x] in months:
            continue
        hops = [(y, z) for y in sorted(adj.get(x, ())) if y in blocked
                for z in sorted(adj.get(y, ())) if z in blocked and z != x and z not in adj.get(x, ())]
        if not hops:
            continue
        y, z = hops[0]
        added.append(f"EDG-9{len(added) + 1:05d},{x},{z},{at[(x, y)]}")
        months.add(owner[x])
        if len(added) >= WAIT_MAX_GROUPS:
            break
    if not added:
        raise AssertionError("no chain offers a step to skip")
    files[WAIT_EDGE_FEED] = files[WAIT_EDGE_FEED].rstrip("\n") + "\n" + "\n".join(added) + "\n"
    st = _compute_files(files, "cmwait")
    parted = _wait_months(st)
    demand: dict = {}
    for r in st["alloc_rows"]:
        pair = (r["year_month"], r["obligor_actor"])
        demand[pair] = demand.get(pair, 0) + r["demand_minutes"]
    reserve = {(r["year_month"], r["obligor_actor"]): r["reserve_minutes"] for r in st["day_rows"]}
    chosen = {pair: reserve[pair] + demand[pair] // 2 for pair in sorted(parted)
              if pair in reserve and demand.get(pair, 0) >= 2 * ALLOC_FLOOR}
    if len(chosen) < WAIT_MIN_MONTHS:
        raise AssertionError(f"only {len(chosen)} months part the wait from the chain depth")
    head, *rest = [ln for ln in files["budget_overrides.psv"].split("\n") if ln]
    kept = [ln for ln in rest if tuple(ln.split("|")[1::-1]) not in chosen]
    kept += [f"{a}|{m}|{v}" for (m, a), v in sorted(chosen.items())]
    files["budget_overrides.psv"] = "\n".join([head] + kept) + "\n"


IDENTITY_PROBE_ALIASES = "aliases_desk.csv"
IDENTITY_PROBE_FEED = "commitments_desk_01.csv"
IDENTITY_PROBE_ROSTER = "roster_desk.csv"
IDENTITY_PROBE_SURFACE = "Zo\u00eb \u00d6degaard"


def _roster_lines(files):
    out = []
    for name in sorted(files):
        if not name.startswith("roster_"):
            continue
        text = files[name]
        if name.endswith(".jsonl"):
            out.extend(json.loads(ln) for ln in text.split("\n") if ln.strip())
            continue
        sep = "\t" if name.endswith(".tsv") else ","
        lines = [ln for ln in text.split("\n") if ln]
        head = lines[0].split(sep)
        out.extend(dict(zip(head, ln.split(sep))) for ln in lines[1:])
    return out


def _add_identity_fixtures(files):
    """Give one held-back extract a decomposed alias and a tied roster spelling.

    Every generated surface is ASCII and no principal's spellings tie, so
    without these rows no extract exercises the NFC step of the fold or the
    roster tie between two spellings.
    """
    roster = _roster_lines(files)
    spellings: dict = {}
    for r in roster:
        counts = spellings.setdefault(r["actor_id"], {})
        counts[r["canonical_handle"]] = counts.get(r["canonical_handle"], 0) + 1
    handles = {r["canonical_handle"] for r in roster}

    # a decomposed alias surface, cited in its composed form by one actor's rows
    lines = files[IDENTITY_PROBE_FEED].rstrip("\n").split("\n")
    head = lines[0].split(",")
    obligor = head.index("obligor")
    cited: dict = {}
    for ln in lines[1:]:
        cells = ln.split(",")
        if len(cells) == len(head) and cells[obligor] in handles:
            cited[cells[obligor]] = cited.get(cells[obligor], 0) + 1
    target = min(cited, key=lambda h: (-cited[h], h))
    for i, ln in enumerate(lines[1:], start=1):
        cells = ln.split(",")
        if len(cells) == len(head) and cells[obligor] == target:
            cells[obligor] = unicodedata.normalize("NFC", IDENTITY_PROBE_SURFACE)
            lines[i] = ",".join(cells)
    files[IDENTITY_PROBE_FEED] = "\n".join(lines) + "\n"
    start = fmt_instant(WINDOW_START - 365 * 1440)
    alias = {
        "surface": unicodedata.normalize("NFD", IDENTITY_PROBE_SURFACE),
        "target": target,
        "scope_start": start,
        "scope_end": fmt_instant(WINDOW_END + 365 * 1440),
        "asserted_at": start,
    }
    files[IDENTITY_PROBE_ALIASES] += ",".join(alias[c] for c in ALIAS_COLS) + "\n"

    # a second spelling of one principal, on as many lines as its first
    for aid in sorted(spellings):
        counts = spellings[aid]
        top = min(counts, key=lambda h: (-counts[h], h))
        twin = top[:1].upper() + top[1:]
        if twin == top or twin in counts:
            continue
        line = {
            "actor_id": aid,
            "canonical_handle": twin,
            "line_from": fmt_day(WINDOW_START // 1440),
            "line_to": fmt_day(WINDOW_END // 1440),
        }
        files[IDENTITY_PROBE_ROSTER] += (
            ",".join(line[c] for c in ROSTER_COLS) + "\n"
        ) * counts[top]
        break


def _write_corpus(seed, dest, reverse=False):
    files, _w = build_all(seed)
    if seed == PROBE_SEEDS[8]:
        _add_precedence_row(files)
    if seed == PROBE_SEEDS[10]:
        _add_small_envelopes(files)
    if seed == EVAL_SEEDS[1]:
        _add_identity_fixtures(files)
    if seed in SURVIVOR_SEEDS:
        _add_survivor_envelopes(files)
    if seed in WAIT_SEEDS:
        _add_wait_shortcuts(files)
    os.makedirs(dest, exist_ok=True)
    for name, text in sorted(files.items(), reverse=reverse):
        with open(os.path.join(dest, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return dest


def _tree_digest(root):
    digest = hashlib.sha256()
    for current, dirs, files in os.walk(root):
        for name in sorted(dirs):
            rel = os.path.relpath(os.path.join(current, name), root)
            digest.update(b"D\0" + rel.replace(os.sep, "/").encode() + b"\0")
        for name in sorted(files):
            path = os.path.join(current, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            digest.update(b"F\0" + rel.encode() + b"\0")
            with open(path, "rb") as handle:
                digest.update(handle.read())
            digest.update(b"\0")
    return digest.hexdigest()


def _reference(seed):
    """The artifacts a correct run produces for one seed, as bytes."""
    if seed in _CACHE:
        return _CACHE[seed]
    tmp = tempfile.mkdtemp(prefix="cmref")
    data = _write_corpus(seed, os.path.join(tmp, "data"))
    out = os.path.join(tmp, "out")
    os.makedirs(out, exist_ok=True)
    write_all(compute(data), out)
    got = {}
    for name in sorted(os.listdir(out)):
        with open(os.path.join(out, name), "rb") as fh:
            got[name] = fh.read()
    _CACHE[seed] = (got, data)
    return _CACHE[seed]


def _delivered(name, base=OUT):
    path = os.path.join(base, name)
    if not os.path.isfile(path):
        raise AssertionError(f"missing declared artifact {name}")
    with open(path, "rb") as fh:
        return fh.read()


def _text(name, base=OUT):
    return _delivered(name, base).decode("utf-8")


def _rows(name, base=OUT):
    """Parse a delivered delimited artifact into dicts."""
    sep = {"csv": ",", "tsv": "\t", "psv": "|"}[name.rsplit(".", 1)[1]]
    lines = _text(name, base).split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        raise AssertionError(f"{name} is empty")
    head = lines[0].split(sep)
    out = []
    for ln in lines[1:]:
        parts = ln.split(sep)
        if len(parts) != len(head):
            raise AssertionError(f"{name} row has {len(parts)} fields")
        out.append(dict(zip(head, parts)))
    return out


def _objects(name, base=OUT):
    out = []
    for ln in _text(name, base).split("\n"):
        if ln:
            out.append(json.loads(ln))
    return out


def _same(name):
    """The delivered artifact equals the recomputed one, byte for byte."""
    exp, _d = _reference(SHIPPED_SEED)
    got = _delivered(name)
    if got != exp[name]:
        raise AssertionError(
            f"{name} differs from the recomputed artifact "
            f"({len(got)} bytes delivered, {len(exp[name])} expected)"
        )


def _all_same(*names):
    for n in names:
        _same(n)


def _grant_read(root):
    """Make a tree readable by the unprivileged user that runs the delivered program."""
    for here, dirs, files in os.walk(root):
        os.chmod(here, 0o755)
        for filename in files:
            os.chmod(os.path.join(here, filename), 0o644)
    head = os.path.dirname(os.path.abspath(root))
    while head and head != os.path.dirname(head):
        os.chmod(head, (os.stat(head).st_mode & 0o7777) | 0o011)
        head = os.path.dirname(head)


def _invoke_program(data_dir, out_dir, extra_env=None):
    if not os.path.isfile(PROGRAM):
        raise AssertionError("missing declared artifact reconcile.py")
    parent = os.path.dirname(out_dir)
    os.makedirs(parent, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    command = [sys.executable, PROGRAM, data_dir, out_dir]
    setpriv = "/usr/bin/setpriv"
    if os.path.isfile(setpriv):
        _grant_read(data_dir)
        _grant_read(os.path.dirname(PROGRAM))
        os.chmod(parent, 0o777)
        os.chmod(out_dir, 0o777)
        command = [
            setpriv,
            "--reuid=nobody",
            "--regid=nogroup",
            "--init-groups",
            "--no-new-privs",
            *command,
        ]
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )
    try:
        proc.wait(timeout=RUN_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (AttributeError, OSError):
            proc.kill()
        proc.wait()
        raise AssertionError(f"delivered program exceeded {RUN_TIMEOUT_SEC} seconds")
    # Anything the program left running in its group ends with the run.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return proc


def _run_program(data_dir, out_dir, extra_env=None):
    proc = _invoke_program(data_dir, out_dir, extra_env)
    if proc.returncode != 0:
        raise AssertionError(f"delivered program exited {proc.returncode}")
    return out_dir


def _assert_exact_output_tree(out_dir):
    seen = set()
    for root, dirs, files in os.walk(out_dir):
        for directory in dirs:
            rel = os.path.relpath(os.path.join(root, directory), out_dir)
            seen.add(rel.replace(os.sep, "/") + "/")
        for filename in files:
            rel = os.path.relpath(os.path.join(root, filename), out_dir)
            seen.add(rel.replace(os.sep, "/"))
    if seen != set(ARTIFACTS):
        raise AssertionError(
            f"output tree differs: missing {sorted(set(ARTIFACTS) - seen)}; "
            f"unexpected {sorted(seen - set(ARTIFACTS))}"
        )


def _assert_declared_present(out_dir):
    missing = [n for n in ARTIFACTS if not os.path.isfile(os.path.join(out_dir, n))]
    if missing:
        raise AssertionError(f"output tree is missing {missing}")


def _probe(seed):
    if seed in _PROBE_CACHE:
        return _PROBE_CACHE[seed]
    tmp = tempfile.mkdtemp(prefix="cmprobe")
    data = _write_corpus(seed, os.path.join(tmp, "data"))
    out = _run_program(data, os.path.join(tmp, "out"))
    _PROBE_CACHE[seed] = out
    return out


# --------------------------------------------------------------- positives


def test_normalized_and_rejects_exact():
    """POSITIVE: the accepted assertions and every rejected row are exact."""
    _all_same("normalized_assertions.jsonl", "rejects.csv")


def test_commitment_ledger_exact():
    """POSITIVE: the ledger is exact in content and in canonical order."""
    _same("commitment_ledger.jsonl")


def test_alias_resolution_exact():
    """POSITIVE: what each obligor surface resolved to is exact."""
    _same("alias_resolution.jsonl")


def test_actor_roster_exact():
    """POSITIVE: every principal's roster line is exact."""
    _same("actor_roster.csv")


def test_project_lineage_exact():
    """POSITIVE: every resolved project code and its root are exact."""
    _same("project_lineage.csv")


def test_state_resolution_and_contests_exact():
    """POSITIVE: precedence over assertions and over state rows is exact."""
    _all_same("state_resolution.csv", "assertion_contests.csv")


def test_edge_partition_exact():
    """POSITIVE: live edges and dropped edges are both exact."""
    _all_same("live_edges.csv", "dropped_edges.csv")


def test_closure_and_blocked_exact():
    """POSITIVE: the blocking closure and its blocked summary are exact."""
    _all_same("blocking_closure.jsonl", "blocked_commitments.csv")


def test_queues_and_registers_exact():
    """POSITIVE: every class view is exact and in canonical order."""
    _all_same(
        "actionable_queue.tsv",
        "deferred_queue.psv",
        "withdrawn_register.csv",
        "unresolvable.jsonl",
    )


def test_cadence_and_waiver_exact():
    """POSITIVE: cadence debt and the waiver trace are exact."""
    _all_same("cadence_debt.csv", "waiver_trace.jsonl")


def test_allocation_and_load_exact():
    """POSITIVE: the envelope distribution and the load index are exact."""
    _all_same("attention_allocation.csv", "month_load_index.csv")


def test_escalation_queue_exact():
    """POSITIVE: the escalation queue is exact in content and in order."""
    seed = PROBE_SEEDS[0]
    base = _probe(seed)
    expected, _data = _reference(seed)
    if _delivered("escalation_queue.csv", base) != expected["escalation_queue.csv"]:
        raise AssertionError("the probe escalation queue is not byte exact")
    got = _rows("escalation_queue.csv", base)
    want = _expect_rows("escalation_queue.csv", seed)
    if len(got) != len(want):
        raise AssertionError(f"{len(got)} escalated rows against {len(want)} expected")
    triggers = {r["trigger"] for r in want}
    if not triggers <= {"DEPTH", "MONTH", "BOTH"}:
        raise AssertionError("the probe extract carries an unknown trigger")
    ledger = {r["commitment_key"]: r for r in _objects("commitment_ledger.jsonl", base)}
    alloc = {
        r["commitment_key"]: int(r["allocated_minutes"])
        for r in _rows("attention_allocation.csv", base)
    }
    for r in got:
        k = r["commitment_key"]
        if k not in ledger:
            raise AssertionError(f"{k} escalates and is absent from the ledger")
        if ledger[k]["commitment_class"] not in ("ACTIONABLE", "BLOCKED"):
            raise AssertionError(
                f"{k} escalates while classed {ledger[k]['commitment_class']}"
            )
        eff = ledger[k]["effort_minutes"]
        if int(r["effort_minutes"]) != eff:
            raise AssertionError(f"{k} carries an effort the ledger denies")
        if int(r["allocated_minutes"]) != alloc.get(k, 0):
            raise AssertionError(f"{k} carries a share the allocation denies")
        if int(r["shortfall_minutes"]) != eff - alloc.get(k, 0):
            raise AssertionError(f"{k} shortfall disagrees with its own fields")
        if int(r["allocated_minutes"]) >= eff:
            raise AssertionError(f"{k} escalates with its effort fully funded")


def test_rollups_and_provenance_exact():
    """POSITIVE: both rollups and the provenance index are exact."""
    _all_same("actor_rollup.json", "project_rollup.json", "provenance_index.jsonl")


def test_audit_and_reconciliation_exact():
    """POSITIVE: the audit figures, the closing report and the residuals are exact."""
    _all_same("audit_totals.csv", "reconciliation.txt", "validation_report.json")


def test_run_manifest_exact():
    """POSITIVE: the decisions recorded for the shipped run are exact."""
    _same("run_manifest.json")


def test_identity_triangle_recomputed():
    """POSITIVE: the three effort identities recompute from the artifacts."""
    seed = PROBE_SEEDS[1]
    base = _probe(seed)
    ledger = _objects("commitment_ledger.jsonl", base)
    actor = json.loads(_text("actor_rollup.json", base))
    proj = json.loads(_text("project_rollup.json", base))
    openc = ("ACTIONABLE", "BLOCKED", "DEFERRED")
    ledger_open = sum(
        r["effort_minutes"] for r in ledger if r["commitment_class"] in openc
    )
    a = sum(v["open_effort_minutes"] for v in actor.values())
    p = sum(v["open_effort_minutes"] for v in proj.values())
    if not (ledger_open == a == p):
        raise AssertionError(
            f"effort identity broken: ledger {ledger_open}, "
            f"principals {a}, projects {p}"
        )
    per_actor = {}
    for r in ledger:
        if r["commitment_class"] in openc:
            per_actor[r["obligor_actor"]] = (
                per_actor.get(r["obligor_actor"], 0) + r["effort_minutes"]
            )
    for k, v in actor.items():
        if v["open_effort_minutes"] != per_actor.get(k, 0):
            raise AssertionError(f"principal {k} open effort disagrees")
    exp, _d = _reference(seed)
    if ledger_open != sum(
        r["effort_minutes"]
        for r in [
            json.loads(x)
            for x in exp["commitment_ledger.jsonl"].decode().split("\n")
            if x
        ]
        if r["commitment_class"] in openc
    ):
        raise AssertionError("open effort disagrees with the recomputed value")


def test_class_partition_complete_and_disjoint():
    """POSITIVE: every admitted commitment sits in exactly one class."""
    seed = PROBE_SEEDS[2]
    base = _probe(seed)
    ledger = _objects("commitment_ledger.jsonl", base)
    keys = [r["commitment_key"] for r in ledger]
    if len(keys) != len(set(keys)):
        raise AssertionError("the ledger repeats a commitment key")
    classes = (
        "ACTIONABLE",
        "BLOCKED",
        "DEFERRED",
        "SETTLED",
        "UNRESOLVABLE",
        "WITHDRAWN",
    )
    counts = {c: 0 for c in classes}
    for r in ledger:
        if r["commitment_class"] not in counts:
            raise AssertionError(
                f"class {r['commitment_class']} is outside the closed list"
            )
        counts[r["commitment_class"]] += 1
    audit = {r["metric"]: int(r["value"]) for r in _rows("audit_totals.csv", base)}
    if audit.get("commitments_admitted") != len(ledger):
        raise AssertionError("commitments_admitted disagrees with the ledger")
    if sum(counts.values()) != len(ledger):
        raise AssertionError("the class counts do not partition the ledger")
    for c in classes:
        if audit.get(f"class_{c.lower()}") != counts[c]:
            raise AssertionError(f"class_{c.lower()} disagrees with the ledger")
    want = {}
    for r in _expect_objects("commitment_ledger.jsonl", seed):
        want.setdefault(r["commitment_class"], set()).add(r["commitment_key"])
    for cls in classes:
        got = {r["commitment_key"] for r in ledger if r["commitment_class"] == cls}
        if got != want.get(cls, set()):
            missing = sorted(want.get(cls, set()) - got)[:3]
            extra = sorted(got - want.get(cls, set()))[:3]
            raise AssertionError(
                f"class {cls} holds {len(got)} commitments against "
                f"{len(want.get(cls, set()))} recomputed; missing {missing}; "
                f"unexpected {extra}"
            )
    views = {
        "ACTIONABLE": {
            r["commitment_key"] for r in _rows("actionable_queue.tsv", base)
        },
        "DEFERRED": {r["commitment_key"] for r in _rows("deferred_queue.psv", base)},
        "WITHDRAWN": {
            r["commitment_key"] for r in _rows("withdrawn_register.csv", base)
        },
        "UNRESOLVABLE": {
            r["commitment_key"] for r in _objects("unresolvable.jsonl", base)
        },
    }
    for cls, seen in views.items():
        want = {r["commitment_key"] for r in ledger if r["commitment_class"] == cls}
        if seen != want:
            raise AssertionError(f"the {cls} view disagrees with the ledger")
    if audit.get("rows_accepted", -1) != audit.get("rows_ingested", 0) - audit.get(
        "rows_rejected", 0
    ):
        raise AssertionError("the row partition does not close")


# ------------------------------------------- the same families, unseen extracts


def _hard(seed, *names):
    """Compare named deliverables of a cached run over an unseen extract."""
    exp, _d = _reference(seed)
    out = _probe(seed)
    _assert_exact_output_tree(out)
    for name in names:
        path = os.path.join(out, name)
        if not os.path.isfile(path):
            raise AssertionError(f"unseen extract {seed}: no {name} was written")
        with open(path, "rb") as fh:
            got = fh.read()
        if got == exp[name]:
            continue
        mine = got.decode("utf-8", "replace").splitlines()
        want = exp[name].decode("utf-8").splitlines()
        at = next(
            (i for i, (a, b) in enumerate(zip(mine, want)) if a != b),
            min(len(mine), len(want)),
        )
        raise AssertionError(
            f"unseen extract {seed}: {name} first differs at line {at + 1}: "
            f"produced {mine[at] if at < len(mine) else '<end>'!r}, "
            f"expected {want[at] if at < len(want) else '<end>'!r}"
        )


def test_normalized_and_rejects_hard():
    """POSITIVE: accepted assertions and rejects hold on an unseen extract."""
    _hard(EVAL_SEEDS[0], "normalized_assertions.jsonl", "rejects.csv")


def test_commitment_ledger_hard():
    """POSITIVE: the ledger holds on an unseen extract."""
    _hard(EVAL_SEEDS[1], "commitment_ledger.jsonl")


def test_alias_resolution_hard():
    """POSITIVE: obligor resolution holds on an unseen extract."""
    _hard(EVAL_SEEDS[2], "alias_resolution.jsonl")


def test_actor_roster_hard():
    """POSITIVE: the roster holds on an unseen extract."""
    _hard(EVAL_SEEDS[0], "actor_roster.csv")


def test_project_lineage_hard():
    """POSITIVE: project lineage holds on an unseen extract."""
    _hard(EVAL_SEEDS[1], "project_lineage.csv")


def test_state_resolution_and_contests_hard():
    """POSITIVE: state precedence holds on an unseen extract."""
    _hard(EVAL_SEEDS[2], "state_resolution.csv", "assertion_contests.csv")


def test_edge_partition_hard():
    """POSITIVE: the edge partition holds on an unseen extract."""
    _hard(EVAL_SEEDS[0], "live_edges.csv", "dropped_edges.csv")


def test_closure_and_blocked_hard():
    """POSITIVE: the closure and the blocked summary hold on an unseen extract."""
    _hard(EVAL_SEEDS[1], "blocking_closure.jsonl", "blocked_commitments.csv")


def test_queues_and_registers_hard():
    """POSITIVE: every class view holds on an unseen extract."""
    _hard(
        EVAL_SEEDS[2],
        "actionable_queue.tsv",
        "deferred_queue.psv",
        "withdrawn_register.csv",
        "unresolvable.jsonl",
    )


def test_cadence_and_waiver_hard():
    """POSITIVE: cadence debt and the waiver trace hold on an unseen extract."""
    _hard(EVAL_SEEDS[0], "cadence_debt.csv", "waiver_trace.jsonl")


def test_allocation_and_load_hard():
    """POSITIVE: allocation and the load index hold on an unseen extract."""
    _hard(EVAL_SEEDS[1], "attention_allocation.csv", "month_load_index.csv")


def test_rollups_and_provenance_hard():
    """POSITIVE: rollups and provenance hold on an unseen extract."""
    _hard(
        EVAL_SEEDS[2],
        "actor_rollup.json",
        "project_rollup.json",
        "provenance_index.jsonl",
    )


def test_audit_and_reconciliation_hard():
    """POSITIVE: audit figures and the report hold on an unseen extract."""
    _hard(
        EVAL_SEEDS[0],
        "audit_totals.csv",
        "reconciliation.txt",
        "validation_report.json",
    )


def test_run_manifest_hard():
    """POSITIVE: the run manifest holds on an unseen extract."""
    _hard(EVAL_SEEDS[1], "run_manifest.json")


# ------------------------------------------- the floor's survivors, owned rows


def _survivor_months(seed):
    """Principal-months whose survivors of the floor share more than they asked."""
    groups: dict = {}
    for r in _expect_rows("attention_allocation.csv", seed):
        groups.setdefault((r["year_month"], r["obligor_actor"]), []).append(r)
    months = set()
    for pair, rows in groups.items():
        held = [r for r in rows if int(r["allocated_minutes"]) > 0]
        lost = [
            r for r in rows
            if int(r["demand_minutes"]) > 0 and int(r["allocated_minutes"]) == 0
        ]
        given = sum(int(r["allocated_minutes"]) for r in held)
        if held and lost and given > sum(int(r["demand_minutes"]) for r in held):
            months.add(pair)
    if len(months) < 2:
        raise AssertionError(f"survivor extract {seed} plants too few months")
    keys = {r["commitment_key"] for pair in months for r in groups[pair]}
    return months, keys


def _survivor_rows(seed, name, ident):
    """Compare only the rows of one deliverable that the survivor months own."""
    months, keys = _survivor_months(seed)
    _owned_rows("survivor", seed, name, ident, months, keys)


def _wait_rows(seed, name, ident):
    """Compare only the rows of one deliverable that the months parted by the wait own."""
    months = _wait_months(compute(_reference(seed)[1]))
    if len(months) < WAIT_MIN_MONTHS:
        raise AssertionError(f"wait extract {seed} plants too few months")
    _owned_rows("wait", seed, name, ident, months, set())


def _owned_rows(label, seed, name, ident, months, keys):
    """Exact equality on the rows of one deliverable owned by the given months or keys."""
    out = _probe(seed)
    _assert_exact_output_tree(out)
    if name.endswith(".jsonl"):
        got, want = _objects(name, out), _expect_objects(name, seed)
    else:
        got, want = _rows(name, out), _expect_rows(name, seed)

    def owned(rows):
        mine = {}
        for r in rows:
            if "commitment_key" in ident:
                if r.get("commitment_key") not in keys:
                    continue
            elif (r.get("year_month"), r.get("obligor_actor")) not in months:
                continue
            mine.setdefault(tuple(str(r.get(c)) for c in ident), []).append(r)
        return mine

    have, need = owned(got), owned(want)
    for at in sorted(set(have) | set(need)):
        path = f"{label} extract {seed}: {name}[{','.join(at)}]"
        if at not in have:
            raise AssertionError(f"{path} is missing")
        if at not in need:
            raise AssertionError(f"{path} is not expected")
        if len(have[at]) != len(need[at]):
            raise AssertionError(f"{path} appears {len(have[at])} times")
        mine, theirs = have[at][0], need[at][0]
        for col in sorted(set(mine) | set(theirs), key=lambda c: (c not in theirs, c)):
            if mine.get(col) != theirs.get(col):
                raise AssertionError(
                    f"{path}.{col} produced {mine.get(col)!r}, expected {theirs.get(col)!r}"
                )


def test_survivor_allocation_exact():
    """POSITIVE: the floor's survivors share the distributable minutes exactly."""
    _survivor_rows(
        SURVIVOR_SEEDS[0],
        "attention_allocation.csv",
        ("year_month", "obligor_actor", "commitment_key"),
    )


def test_survivor_allocation_hard():
    """POSITIVE: the survivors' shares hold on an unseen extract."""
    _survivor_rows(
        SURVIVOR_SEEDS[1],
        "attention_allocation.csv",
        ("year_month", "obligor_actor", "commitment_key"),
    )


def test_survivor_month_load_exact():
    """POSITIVE: the survivor months' load rows are exact."""
    _survivor_rows(
        SURVIVOR_SEEDS[0], "month_load_index.csv", ("year_month", "obligor_actor")
    )


def test_survivor_month_load_hard():
    """POSITIVE: the survivor months' load rows hold on an unseen extract."""
    _survivor_rows(
        SURVIVOR_SEEDS[1], "month_load_index.csv", ("year_month", "obligor_actor")
    )


def test_survivor_ledger_exact():
    """POSITIVE: the ledger records of the survivor months are exact."""
    _survivor_rows(SURVIVOR_SEEDS[0], "commitment_ledger.jsonl", ("commitment_key",))


def test_survivor_ledger_hard():
    """POSITIVE: the survivor months' ledger records hold on an unseen extract."""
    _survivor_rows(SURVIVOR_SEEDS[1], "commitment_ledger.jsonl", ("commitment_key",))


def test_wait_reserve_exact():
    """POSITIVE: the reserve of every month whose blocked lines wait along a chain is exact."""
    _wait_rows(WAIT_SEEDS[0], "month_load_index.csv", ("year_month", "obligor_actor"))


def test_wait_reserve_hard():
    """POSITIVE: the reserve of the waiting months holds on an unseen extract."""
    _wait_rows(WAIT_SEEDS[1], "month_load_index.csv", ("year_month", "obligor_actor"))


# ------------------------------------------------------- rule level probes


def _expect_rows(name, seed=SHIPPED_SEED):
    exp, _d = _reference(seed)
    txt = exp[name].decode("utf-8")
    sep = {"csv": ",", "tsv": "\t", "psv": "|"}[name.rsplit(".", 1)[1]]
    lines = [ln for ln in txt.split("\n") if ln]
    head = lines[0].split(sep)
    return [dict(zip(head, ln.split(sep))) for ln in lines[1:]]


def _expect_objects(name, seed=SHIPPED_SEED):
    exp, _d = _reference(seed)
    return [json.loads(ln) for ln in exp[name].decode("utf-8").split("\n") if ln]


def test_documented_boundaries_exact():
    """POSITIVE: every documented boundary unit resolves the stated way."""
    seed = PROBE_SEEDS[3]
    base = _probe(seed)
    got = {r["assertion_id"]: r for r in _objects("normalized_assertions.jsonl", base)}
    want = {
        r["assertion_id"]: r
        for r in _expect_objects("normalized_assertions.jsonl", seed)
    }
    rejected = {r["record_id"] for r in _rows("rejects.csv", base)}
    want_rejected = {r["record_id"] for r in _expect_rows("rejects.csv", seed)}

    checked = 0
    # The instant the day boundary turns, and the first instant on its far
    # side. Every other pre dawn row belongs to the day boundary probe.
    for minute in ("04:00", "04:01"):
        band = {k for k, v in want.items() if v["due_at"][11:16] == minute}
        if not band:
            raise AssertionError(f"no assertion falls due at {minute}")
        for k in sorted(band):
            checked += 1
            if k not in got:
                raise AssertionError(f"{k} is absent from the accepted set")
            if got[k]["commitment_day"] != want[k]["commitment_day"]:
                raise AssertionError(
                    f"{k} falls due at {minute} and files on "
                    f"{got[k]['commitment_day']} rather than "
                    f"{want[k]['commitment_day']}"
                )

    # the first and last instants the window admits
    edge = {
        k
        for k, v in want.items()
        if v["due_at"] in ("2032-03-01T00:00Z", "2032-11-30T23:59Z")
    }
    for k in sorted(edge):
        checked += 1
        if k not in got:
            raise AssertionError(f"{k} sits inside the window and was refused")

    # every assertion the interval boundary decides, in both directions
    surfaces = {
        r["surface_folded"]: r for r in _expect_objects("alias_resolution.jsonl", seed)
    }
    delivered = {
        r["surface_folded"]: r for r in _objects("alias_resolution.jsonl", base)
    }
    split = {k for k, v in surfaces.items() if len(v["distinct_actors"]) > 1}
    if len(split) < 5:
        raise AssertionError(f"the probe extract carries only {len(split)} split surfaces")
    for k in sorted(split):
        checked += 1
        if k not in delivered:
            raise AssertionError(f"surface {k} is absent from the resolution")
        if delivered[k]["distinct_actors"] != surfaces[k]["distinct_actors"]:
            raise AssertionError(
                f"surface {k} resolved to "
                f"{delivered[k]['distinct_actors']} rather than "
                f"{surfaces[k]['distinct_actors']}"
            )
        if delivered[k]["assertion_count"] != surfaces[k]["assertion_count"]:
            raise AssertionError(f"surface {k} carries the wrong count")

    # every row the closure refuses stays refused and carries a reason code
    only_here = sorted(want_rejected - set(want))
    if not only_here:
        raise AssertionError("no row is refused at an interval boundary")
    for k in sorted(only_here)[:200]:
        checked += 1
        if k in got:
            raise AssertionError(f"{k} was accepted and the closure refuses it")
        if k not in rejected:
            raise AssertionError(f"{k} is refused and carries no reason code")
    # The obligee is resolved at the instant the commitment falls due, so its
    # status parts company with the obligor's wherever the two instants sit on
    # opposite sides of an alias interval.
    statuses = {}
    for k, v in want.items():
        statuses.setdefault(v["obligee_status"], set()).add(k)
    for name in ("RESOLVED", "AMBIGUOUS", "UNKNOWN"):
        if not statuses.get(name):
            raise AssertionError(f"no accepted assertion carries obligee {name}")
    for k in sorted(statuses["AMBIGUOUS"] | statuses["UNKNOWN"]):
        checked += 1
        if k not in got:
            raise AssertionError(f"assertion {k} is absent from the accepted set")
        if got[k]["obligee_status"] != want[k]["obligee_status"]:
            raise AssertionError(
                f"assertion {k} carries obligee status "
                f"{got[k]['obligee_status']} rather than {want[k]['obligee_status']}"
            )
        if got[k]["obligee_actor"] != want[k]["obligee_actor"]:
            raise AssertionError(f"assertion {k} names the wrong obligee")
    if checked < 60:
        raise AssertionError(f"only {checked} boundary units were reachable")


def test_edge_scope_rule_exact():
    """POSITIVE: edges are dropped at the instant they were asserted."""
    seed = PROBE_SEEDS[4]
    base = _probe(seed)
    got = {r["edge_id"]: r for r in _rows("dropped_edges.csv", base)}
    want = {r["edge_id"]: r for r in _expect_rows("dropped_edges.csv", seed)}
    oos = {k: v for k, v in want.items() if v["drop_reason"] == "EDGE_OUT_OF_SCOPE"}
    if not oos:
        raise AssertionError("the probe extract drops no edge out of scope")
    for k in sorted(oos):
        if k not in got:
            raise AssertionError(f"edge {k} was kept rather than dropped")
        if got[k]["drop_reason"] != "EDGE_OUT_OF_SCOPE":
            raise AssertionError(f"edge {k} carries {got[k]['drop_reason']}")
    live = {r["edge_id"] for r in _rows("live_edges.csv", base)}
    if live & set(oos):
        raise AssertionError("an out of scope edge is also live")


def test_precedence_inversion_exact():
    """POSITIVE: both inverting classes resolve by the order the charter gives them."""
    seed = PROBE_SEEDS[5]
    base = _probe(seed)
    got = {r["commitment_key"]: r for r in _rows("state_resolution.csv", base)}
    want = {r["commitment_key"]: r for r in _expect_rows("state_resolution.csv", seed)}
    # Both inverting classes are checked here: the journal class, which
    # inverts wherever it competes, and the sweep class, which inverts for
    # state rows and keeps the ordinary direction where commitments compete.
    desk = {
        k
        for k, v in want.items()
        if v["governing_class"] in ("desk", "bridge")
    }
    if len(desk) < 10:
        raise AssertionError(
            f"the probe extract exercises the journal class only {len(desk)} times"
        )
    ledger_want = {
        r["commitment_key"]: r for r in _expect_objects("commitment_ledger.jsonl", seed)
    }
    ledger_got = {
        r["commitment_key"]: r for r in _objects("commitment_ledger.jsonl", base)
    }
    sweep = [k for k, v in ledger_want.items() if v["source_class"] == "bridge"]
    if len(sweep) < 10:
        raise AssertionError(f"the sweep class wins only {len(sweep)} commitments")
    for k in sorted(sweep):
        if k not in ledger_got:
            raise AssertionError(f"commitment {k} is absent from the ledger")
        if ledger_got[k]["winning_assertion"] != ledger_want[k]["winning_assertion"]:
            raise AssertionError(
                f"commitment {k} is won by "
                f"{ledger_got[k]['winning_assertion']} rather than "
                f"{ledger_want[k]['winning_assertion']}"
            )
    for k in sorted(desk):
        if k not in got:
            raise AssertionError(f"commitment {k} is absent")
        if (
            got[k]["resolved_state"] != want[k]["resolved_state"]
            or got[k]["governing_class"] != want[k]["governing_class"]
        ):
            raise AssertionError(
                f"commitment {k} resolved to {got[k]['resolved_state']} under "
                f"{got[k]['governing_class']}"
            )


def test_effort_units_and_origins_exact():
    """POSITIVE: unit factors, defaults and declared zeros are all exact."""
    seed = PROBE_SEEDS[6]
    base = _probe(seed)
    got = {r["assertion_id"]: r for r in _objects("normalized_assertions.jsonl", base)}
    want = {
        r["assertion_id"]: r
        for r in _expect_objects("normalized_assertions.jsonl", seed)
    }
    for origin in ("DEFAULTED", "DECLARED_ZERO"):
        picked = {k for k, v in want.items() if v["effort_origin"] == origin}
        if not picked:
            raise AssertionError(f"no assertion carries {origin}")
        for k in sorted(picked):
            if k not in got:
                raise AssertionError(f"assertion {k} is absent")
            if (
                got[k]["effort_minutes"] != want[k]["effort_minutes"]
                or got[k]["effort_origin"] != origin
            ):
                raise AssertionError(
                    f"assertion {k} carries {got[k]['effort_minutes']} minutes "
                    f"as {got[k]['effort_origin']}"
                )
    hours = {k for k, v in want.items() if v["source_class"] in ("legacy", "relay")}
    for k in sorted(hours):
        if got.get(k, {}).get("effort_minutes") != want[k]["effort_minutes"]:
            raise AssertionError(f"assertion {k} effort disagrees")
    # A unit outside the three named spellings is a malformed row, and case is
    # part of the spelling. Those rows reach the rejects and never the ledger.
    cased = {
        r["record_id"]
        for r in _expect_rows("rejects.csv", seed)
        if r["reason_code"] == "MALFORMED_ROW" and r["record_kind"] == "commitment"
    }
    if len(cased) < 20:
        raise AssertionError(f"the probe extract carries only {len(cased)} such rows")
    delivered = {
        (r["record_id"], r["reason_code"]) for r in _rows("rejects.csv", base)
    }
    for k in sorted(cased):
        if (k, "MALFORMED_ROW") not in delivered:
            raise AssertionError(f"row {k} is malformed and the closure disagrees")
        if k in got:
            raise AssertionError(f"malformed row {k} reached the accepted set")


def test_day_boundary_exact():
    """POSITIVE: the day boundary files pre dawn obligations one day back."""
    seed = PROBE_SEEDS[7]
    base = _probe(seed)
    got = {r["assertion_id"]: r for r in _objects("normalized_assertions.jsonl", base)}
    want = {
        r["assertion_id"]: r
        for r in _expect_objects("normalized_assertions.jsonl", seed)
    }
    edge = {k for k, v in want.items() if v["due_at"][11:16] < "04:00"}
    if len(edge) < 20:
        raise AssertionError(
            f"the probe extract carries only {len(edge)} pre dawn rows"
        )
    for k in sorted(edge):
        if k not in got:
            raise AssertionError(f"assertion {k} is absent")
        if got[k]["commitment_day"] != want[k]["commitment_day"]:
            raise AssertionError(
                f"assertion {k} filed on {got[k]['commitment_day']} rather "
                f"than {want[k]['commitment_day']}"
            )


def test_reject_precedence_exact():
    """POSITIVE: every rejected row carries the first applicable code."""
    seed = PROBE_SEEDS[8]
    base = _probe(seed)
    got = {
        (r["feed_file"], r["row_index"], r["record_id"]): r["reason_code"]
        for r in _rows("rejects.csv", base)
    }
    want = {
        (r["feed_file"], r["row_index"], r["record_id"]): r["reason_code"]
        for r in _expect_rows("rejects.csv", seed)
    }
    probe_codes = [c for k, c in want.items() if k[2] == PRECEDENCE_PROBE_ROW]
    if probe_codes != ["UNKNOWN_PROJECT"]:
        raise AssertionError(f"the precedence probe row was coded {probe_codes}")
    if got != want:
        missing = sorted(set(want) - set(got))[:3]
        extra = sorted(set(got) - set(want))[:3]
        wrong = [k for k in set(got) & set(want) if got[k] != want[k]][:3]
        raise AssertionError(
            f"rejects disagree: {len(want)} expected, {len(got)} delivered; "
            f"missing {missing}; unexpected {extra}; miscoded {wrong}"
        )


def test_cadence_streak_and_waiver_semantics_exact():
    """POSITIVE: a waiver suppresses a period and leaves the streak standing."""
    seed = PROBE_SEEDS[9]
    base = _probe(seed)
    got = {r["cadence_id"]: r for r in _rows("cadence_debt.csv", base)}
    want = {r["cadence_id"]: r for r in _expect_rows("cadence_debt.csv", seed)}
    if set(got) != set(want):
        raise AssertionError("the cadence set disagrees")
    for k in sorted(want):
        for f in (
            "periods_elapsed",
            "periods_discharged",
            "periods_waived",
            "debt",
            "max_streak",
        ):
            if got[k][f] != want[k][f]:
                raise AssertionError(
                    f"cadence {k} {f} is {got[k][f]} rather than {want[k][f]}"
                )
    # The debt a cadence raises is owed by whoever its obligor surface stands
    # for at the cadence anchor, and a cadence standing for nobody there is
    # owned by nobody. The escalation queue carries that figure per principal.
    debt_got = {
        r["obligor_actor"]: int(r["principal_debt"])
        for r in _rows("escalation_queue.csv", base)
    }
    debt_want = {
        r["obligor_actor"]: int(r["principal_debt"])
        for r in _expect_rows("escalation_queue.csv", seed)
    }
    if debt_got != debt_want:
        wrong = [
            k for k in set(debt_got) & set(debt_want) if debt_got[k] != debt_want[k]
        ][:3]
        raise AssertionError(
            f"the debt owed per principal disagrees on {len(set(debt_got) ^ set(debt_want))} "
            f"principals and {len(wrong)} values, for example {wrong}"
        )
    gt = {
        (r["cadence_id"], r["period_index"]): r["effect"]
        for r in _objects("waiver_trace.jsonl", base)
    }
    wt = {
        (r["cadence_id"], r["period_index"]): r["effect"]
        for r in _expect_objects("waiver_trace.jsonl", seed)
    }
    if gt != wt:
        raise AssertionError("the waiver effects disagree")


def test_allocation_remainder_and_floor_exact():
    """POSITIVE: the envelope split honours largest remainder and the floor."""
    seed = PROBE_SEEDS[10]
    base = _probe(seed)
    got = {
        (r["year_month"], r["obligor_actor"], r["commitment_key"]): int(
            r["allocated_minutes"]
        )
        for r in _rows("attention_allocation.csv", base)
    }
    want = {
        (r["year_month"], r["obligor_actor"], r["commitment_key"]): int(
            r["allocated_minutes"]
        )
        for r in _expect_rows("attention_allocation.csv", seed)
    }
    if got != want:
        wrong = [k for k in set(got) & set(want) if got[k] != want[k]][:3]
        raise AssertionError(
            f"allocation disagrees on {len(set(got) ^ set(want))} keys and "
            f"{sum(1 for k in set(got) & set(want) if got[k] != want[k])} "
            f"values, for example {wrong}"
        )
    starved = sum(1 for v in want.values() if v == 0)
    if starved < 5:
        raise AssertionError("the probe extract starves too few shares")
    load = {
        (r["year_month"], r["obligor_actor"]): r
        for r in _rows("month_load_index.csv", base)
    }
    for (ym, actor), row in load.items():
        tot = sum(v for (m, a, _k), v in got.items() if m == ym and a == actor)
        if tot != int(row["allocated_minutes"]):
            raise AssertionError(
                f"{ym} {actor} allocated total disagrees with its rows"
            )
        if int(row["allocated_minutes"]) > int(row["budget_minutes"]):
            raise AssertionError(f"{ym} {actor} allocated above its envelope")


def test_run_manifest_counterfactuals_exact():
    """POSITIVE: the recorded branch figures match the recomputed run."""
    seed = PROBE_SEEDS[11]
    base = _probe(seed)
    got = json.loads(_text("run_manifest.json", base))
    exp, _d = _reference(seed)
    want = json.loads(exp["run_manifest.json"].decode("utf-8"))
    for f in (
        "split_surfaces",
        "multi_hop_assertions",
        "order_tiebreaks_applied",
        "edges_dropped_out_of_scope",
        "waivers_suppressing",
        "waivers_inert",
        "waivers_lapsed",
        "allocations_starved",
        "illegal_transitions",
        "retired_feeds",
        "reason_codes",
        "commitment_classes",
    ):
        if got.get(f) != want[f]:
            raise AssertionError(
                f"run manifest {f} is {got.get(f)!r} rather than {want[f]!r}"
            )


def test_validation_report_residuals_zero():
    """POSITIVE: the five identities are stated and every residual is zero."""
    seed = PROBE_SEEDS[12]
    base = _probe(seed)
    rep = json.loads(_text("validation_report.json", base))
    names = (
        "I1_row_partition",
        "I2_class_partition",
        "I3_actor_effort",
        "I4_project_effort",
        "I5_closure_frontier",
    )
    if sorted(rep.get("identities_checked", [])) != sorted(names):
        raise AssertionError("the identity list is wrong")
    ident = rep.get("identities", {})
    for n in names:
        if n not in ident:
            raise AssertionError(f"identity {n} is not reported")
        if type(ident[n]) is not int or ident[n] != 0:
            raise AssertionError(f"identity {n} has residual {ident[n]}")
    if rep.get("all_residuals_zero") is not True:
        raise AssertionError("all_residuals_zero is not true")
    closure = _objects("blocking_closure.jsonl", base)
    blocked = _rows("blocked_commitments.csv", base)
    terminal = sum(1 for r in closure if r["terminal"] == "yes")
    frontier = sum(int(r["frontier_count"]) for r in blocked)
    if terminal != frontier:
        raise AssertionError(
            f"closure frontier identity fails: {frontier} against {terminal}"
        )
    # residuals of zero prove the run is consistent with itself. The figures
    # the identities are taken over have to be the recomputed ones as well.
    audit = {r["metric"]: int(r["value"]) for r in _rows("audit_totals.csv", base)}
    want = {
        r["metric"]: int(r["value"]) for r in _expect_rows("audit_totals.csv", seed)
    }
    for metric in (
        "rows_ingested",
        "rows_rejected",
        "rows_accepted",
        "commitments_admitted",
        "open_effort_minutes",
        "allocated_minutes",
        "closure_pairs",
        "blocked_commitments",
        "live_edges",
        "dropped_edges",
        "escalated_commitments",
        "cadence_debt_total",
    ):
        if audit.get(metric) != want[metric]:
            raise AssertionError(
                f"{metric} is {audit.get(metric)} against {want[metric]} "
                "recomputed, so the identities close over the wrong figures"
            )
    if len(closure) != want["closure_pairs"]:
        raise AssertionError("the closure carries the wrong number of pairs")
    if len(blocked) != want["blocked_commitments"]:
        raise AssertionError("the blocked set is the wrong size")


def test_delivered_program_is_deterministic():
    """POSITIVE: two runs over one extract produce byte identical output."""
    tmp = tempfile.mkdtemp(prefix="cmdet")
    data = _write_corpus(EVAL_SEEDS[0], os.path.join(tmp, "data"))
    a = _run_program(data, os.path.join(tmp, "a"))
    b = _run_program(data, os.path.join(tmp, "b"))
    _assert_declared_present(a)
    _assert_declared_present(b)
    names = sorted(set(os.listdir(a)) | set(os.listdir(b)))
    if not names:
        raise AssertionError("the delivered program produced nothing")
    for n in names:
        pa, pb = os.path.join(a, n), os.path.join(b, n)
        if not (os.path.isfile(pa) and os.path.isfile(pb)):
            raise AssertionError(f"{n} was produced by only one of two runs")
        with open(pa, "rb") as fa, open(pb, "rb") as fb:
            first, second = fa.read(), fb.read()
        if first != second:
            raise AssertionError(f"{n} differs between two runs")


def test_failed_run_leaves_no_partial_file():
    """POSITIVE: a run that cannot publish leaves no partial file behind."""
    tmp = tempfile.mkdtemp(prefix="cmpartial")
    data = _write_corpus(EVAL_SEEDS[0], os.path.join(tmp, "data"))
    _assert_declared_present(_run_program(data, os.path.join(tmp, "clean")))
    parent = os.path.join(tmp, "publish")
    out = os.path.join(parent, "out")
    os.makedirs(os.path.join(out, ARTIFACTS[-1]))
    proc = _invoke_program(data, out)
    if proc.returncode == 0:
        _assert_exact_output_tree(out)
        return
    for root, _dirs, files in os.walk(parent):
        if files:
            rel = os.path.relpath(os.path.join(root, sorted(files)[0]), tmp)
            raise AssertionError(f"a run that could not finish left {rel} behind")


def test_declared_artifacts_present_and_parse():
    """POSITIVE: every declared artifact exists and parses in its own shape."""
    for name in ARTIFACTS:
        _delivered(name)
    for name in ARTIFACTS:
        if name.endswith(".jsonl"):
            _objects(name)
        elif name.endswith(".json"):
            json.loads(_text(name))
        elif name.rsplit(".", 1)[-1] in ("csv", "tsv", "psv"):
            _rows(name)
    for name in ARTIFACTS:
        body = _text(name)
        if not body.endswith("\n"):
            raise AssertionError(f"{name} has no trailing newline")
        if "\r" in body:
            raise AssertionError(f"{name} carries a carriage return")


# --------------------------------------------------------------- negatives


def test_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: fires when the program restates shipped figures on new input."""
    exp_shipped, _d = _reference(SHIPPED_SEED)
    tmp = tempfile.mkdtemp(prefix="cmhc")
    data = _write_corpus(EVAL_SEEDS[2], os.path.join(tmp, "data"))
    out = _run_program(data, os.path.join(tmp, "out"))
    path = os.path.join(out, "commitment_ledger.jsonl")
    if not os.path.isfile(path):
        raise AssertionError("the unseen run produced no ledger")
    with open(path, "rb") as fh:
        got = fh.read()
    if got == exp_shipped["commitment_ledger.jsonl"]:
        return True
    raise AssertionError("the program does not restate the shipped ledger")


def _snapshot(root, seed, names, data_name="data", reverse=False, extra_env=None):
    """Run the program in a fresh workspace at fixed paths and read its output."""
    shutil.rmtree(root, ignore_errors=True)
    data = _write_corpus(seed, os.path.join(root, data_name), reverse=reverse)
    out = _run_program(data, os.path.join(root, "out"), extra_env)
    got = {}
    for n in names:
        path = os.path.join(out, n)
        got[n] = None
        if os.path.isfile(path):
            with open(path, "rb") as fh:
                got[n] = fh.read()
    return got


def _perturbation_changes_output(seed, names, control, perturbed):
    """True when only the perturbation, and not a plain rerun, moves the output.

    Both runs use one workspace path, so a path written into the output cannot
    separate them, and a program that varies between identical runs is left to
    the determinism check rather than charged here as well.
    """
    holder = tempfile.mkdtemp(prefix="cmperturb")
    # mkdtemp makes its directory 0700 and owned by root, and the program runs
    # as nobody, so it could not pass through to its own extract otherwise.
    os.chmod(holder, 0o755)
    root = os.path.join(holder, "w")
    first = _snapshot(root, seed, names, **control)
    if _snapshot(root, seed, names, **control) != first:
        raise AssertionError("the output varies between identical runs")
    return _snapshot(root, seed, names, **perturbed) != first


def test_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: fires when renaming the extract directory changes the answer."""
    if _perturbation_changes_output(
        EVAL_SEEDS[1],
        ("commitment_ledger.jsonl",),
        {"data_name": "data"},
        {"data_name": "elsewhere"},
    ):
        return True
    raise AssertionError("the program is not sensitive to the directory name")


def test_negative_weight_mutates_input_extract():
    """NEGATIVE: fires when a run changes any input name or byte."""
    tmp = tempfile.mkdtemp(prefix="cminput")
    data = _write_corpus(EVAL_SEEDS[0], os.path.join(tmp, "data"))
    before = _tree_digest(data)
    _run_program(data, os.path.join(tmp, "out"))
    if _tree_digest(data) != before:
        return True
    raise AssertionError("the input extract is byte identical after the run")


def test_negative_weight_environment_dependent_output():
    """NEGATIVE: fires when harmless process metadata changes the output."""
    marker_a = {
        "HOSTNAME": "caldermoor-a",
        "USER": "closure-a",
        "CALDERMOOR_RUN_MARKER": "alpha",
    }
    marker_b = {
        "HOSTNAME": "caldermoor-b",
        "USER": "closure-b",
        "CALDERMOOR_RUN_MARKER": "beta",
    }
    if _perturbation_changes_output(
        EVAL_SEEDS[1], ARTIFACTS, {"extra_env": marker_a}, {"extra_env": marker_b}
    ):
        return True
    raise AssertionError("the output is independent of process metadata")


def test_negative_weight_directory_iteration_order():
    """NEGATIVE: fires when input creation order changes the output."""
    if _perturbation_changes_output(
        EVAL_SEEDS[2], ARTIFACTS, {"reverse": False}, {"reverse": True}
    ):
        return True
    raise AssertionError("the output is independent of directory iteration order")


# rewardkit checks. Each one runs the original test above; it passes when that test
# raises nothing. One lock runs the checks one at a time, as the old grader did,
# because rewardkit calls checks from parallel worker threads.
_GRADE_LOCK = threading.Lock()


def _passes(test) -> bool:
    with _GRADE_LOCK:
        try:
            test()
        except BaseException:
            return False
        return True


@criterion(description="every principal's roster line is exact.")
def actor_roster_exact(workspace: Path) -> bool:
    return _passes(test_actor_roster_exact)


@criterion(description="the roster holds on an unseen extract.")
def actor_roster_hard(workspace: Path) -> bool:
    return _passes(test_actor_roster_hard)


@criterion(description="what each obligor surface resolved to is exact.")
def alias_resolution_exact(workspace: Path) -> bool:
    return _passes(test_alias_resolution_exact)


@criterion(description="obligor resolution holds on an unseen extract.")
def alias_resolution_hard(workspace: Path) -> bool:
    return _passes(test_alias_resolution_hard)


@criterion(description="the envelope distribution and the load index are exact.")
def allocation_and_load_exact(workspace: Path) -> bool:
    return _passes(test_allocation_and_load_exact)


@criterion(description="allocation and the load index hold on an unseen extract.")
def allocation_and_load_hard(workspace: Path) -> bool:
    return _passes(test_allocation_and_load_hard)


@criterion(description="the envelope split honours largest remainder and the floor.")
def allocation_remainder_and_floor_exact(workspace: Path) -> bool:
    return _passes(test_allocation_remainder_and_floor_exact)


@criterion(description="the audit figures, the closing report and the residuals are exact.")
def audit_and_reconciliation_exact(workspace: Path) -> bool:
    return _passes(test_audit_and_reconciliation_exact)


@criterion(description="audit figures and the report hold on an unseen extract.")
def audit_and_reconciliation_hard(workspace: Path) -> bool:
    return _passes(test_audit_and_reconciliation_hard)


@criterion(description="cadence debt and the waiver trace are exact.")
def cadence_and_waiver_exact(workspace: Path) -> bool:
    return _passes(test_cadence_and_waiver_exact)


@criterion(description="cadence debt and the waiver trace hold on an unseen extract.")
def cadence_and_waiver_hard(workspace: Path) -> bool:
    return _passes(test_cadence_and_waiver_hard)


@criterion(description="a waiver suppresses a period and leaves the streak standing.")
def cadence_streak_and_waiver_semantics_exact(workspace: Path) -> bool:
    return _passes(test_cadence_streak_and_waiver_semantics_exact)


@criterion(description="every admitted commitment sits in exactly one class.")
def class_partition_complete_and_disjoint(workspace: Path) -> bool:
    return _passes(test_class_partition_complete_and_disjoint)


@criterion(description="the blocking closure and its blocked summary are exact.")
def closure_and_blocked_exact(workspace: Path) -> bool:
    return _passes(test_closure_and_blocked_exact)


@criterion(description="the closure and the blocked summary hold on an unseen extract.")
def closure_and_blocked_hard(workspace: Path) -> bool:
    return _passes(test_closure_and_blocked_hard)


@criterion(description="the ledger is exact in content and in canonical order.")
def commitment_ledger_exact(workspace: Path) -> bool:
    return _passes(test_commitment_ledger_exact)


@criterion(description="the ledger holds on an unseen extract.")
def commitment_ledger_hard(workspace: Path) -> bool:
    return _passes(test_commitment_ledger_hard)


@criterion(description="the day boundary files pre dawn obligations one day back.")
def day_boundary_exact(workspace: Path) -> bool:
    return _passes(test_day_boundary_exact)


@criterion(description="every declared artifact exists and parses in its own shape.")
def declared_artifacts_present_and_parse(workspace: Path) -> bool:
    return _passes(test_declared_artifacts_present_and_parse)


@criterion(description="two runs over one extract produce byte identical output.")
def delivered_program_is_deterministic(workspace: Path) -> bool:
    return _passes(test_delivered_program_is_deterministic)


@criterion(description="every documented boundary unit resolves the stated way.")
def documented_boundaries_exact(workspace: Path) -> bool:
    return _passes(test_documented_boundaries_exact)


@criterion(description="live edges and dropped edges are both exact.")
def edge_partition_exact(workspace: Path) -> bool:
    return _passes(test_edge_partition_exact)


@criterion(description="the edge partition holds on an unseen extract.")
def edge_partition_hard(workspace: Path) -> bool:
    return _passes(test_edge_partition_hard)


@criterion(description="edges are dropped at the instant they were asserted.")
def edge_scope_rule_exact(workspace: Path) -> bool:
    return _passes(test_edge_scope_rule_exact)


@criterion(description="unit factors, defaults and declared zeros are all exact.")
def effort_units_and_origins_exact(workspace: Path) -> bool:
    return _passes(test_effort_units_and_origins_exact)


@criterion(description="the escalation queue is exact in content and in order.")
def escalation_queue_exact(workspace: Path) -> bool:
    return _passes(test_escalation_queue_exact)


@criterion(description="a run that cannot publish leaves no partial file behind.")
def failed_run_leaves_no_partial_file(workspace: Path) -> bool:
    return _passes(test_failed_run_leaves_no_partial_file)


@criterion(description="the three effort identities recompute from the artifacts.")
def identity_triangle_recomputed(workspace: Path) -> bool:
    return _passes(test_identity_triangle_recomputed)


@criterion(description="fires when input creation order changes the output.")
def negative_directory_iteration_order(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_directory_iteration_order)


@criterion(description="fires when harmless process metadata changes the output.")
def negative_environment_dependent_output(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_environment_dependent_output)


@criterion(description="fires when renaming the extract directory changes the answer.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_filename_dependent_behaviour)


@criterion(description="fires when the program restates shipped figures on new input.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_hardcoded_sample_answers)


@criterion(description="fires when a run changes any input name or byte.")
def negative_mutates_input_extract(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_mutates_input_extract)


@criterion(description="the accepted assertions and every rejected row are exact.")
def normalized_and_rejects_exact(workspace: Path) -> bool:
    return _passes(test_normalized_and_rejects_exact)


@criterion(description="accepted assertions and rejects hold on an unseen extract.")
def normalized_and_rejects_hard(workspace: Path) -> bool:
    return _passes(test_normalized_and_rejects_hard)


@criterion(description="both inverting classes resolve by the order the charter gives them.")
def precedence_inversion_exact(workspace: Path) -> bool:
    return _passes(test_precedence_inversion_exact)


@criterion(description="every resolved project code and its root are exact.")
def project_lineage_exact(workspace: Path) -> bool:
    return _passes(test_project_lineage_exact)


@criterion(description="project lineage holds on an unseen extract.")
def project_lineage_hard(workspace: Path) -> bool:
    return _passes(test_project_lineage_hard)


@criterion(description="every class view is exact and in canonical order.")
def queues_and_registers_exact(workspace: Path) -> bool:
    return _passes(test_queues_and_registers_exact)


@criterion(description="every class view holds on an unseen extract.")
def queues_and_registers_hard(workspace: Path) -> bool:
    return _passes(test_queues_and_registers_hard)


@criterion(description="every rejected row carries the first applicable code.")
def reject_precedence_exact(workspace: Path) -> bool:
    return _passes(test_reject_precedence_exact)


@criterion(description="both rollups and the provenance index are exact.")
def rollups_and_provenance_exact(workspace: Path) -> bool:
    return _passes(test_rollups_and_provenance_exact)


@criterion(description="rollups and provenance hold on an unseen extract.")
def rollups_and_provenance_hard(workspace: Path) -> bool:
    return _passes(test_rollups_and_provenance_hard)


@criterion(description="the recorded branch figures match the recomputed run.")
def run_manifest_counterfactuals_exact(workspace: Path) -> bool:
    return _passes(test_run_manifest_counterfactuals_exact)


@criterion(description="the decisions recorded for the shipped run are exact.")
def run_manifest_exact(workspace: Path) -> bool:
    return _passes(test_run_manifest_exact)


@criterion(description="the run manifest holds on an unseen extract.")
def run_manifest_hard(workspace: Path) -> bool:
    return _passes(test_run_manifest_hard)


@criterion(description="precedence over assertions and over state rows is exact.")
def state_resolution_and_contests_exact(workspace: Path) -> bool:
    return _passes(test_state_resolution_and_contests_exact)


@criterion(description="state precedence holds on an unseen extract.")
def state_resolution_and_contests_hard(workspace: Path) -> bool:
    return _passes(test_state_resolution_and_contests_hard)


@criterion(description="the floor's survivors share the distributable minutes exactly.")
def survivor_allocation_exact(workspace: Path) -> bool:
    return _passes(test_survivor_allocation_exact)


@criterion(description="the survivors' shares hold on an unseen extract.")
def survivor_allocation_hard(workspace: Path) -> bool:
    return _passes(test_survivor_allocation_hard)


@criterion(description="the survivor months' ledger records are exact.")
def survivor_ledger_exact(workspace: Path) -> bool:
    return _passes(test_survivor_ledger_exact)


@criterion(description="the survivor months' ledger records hold on an unseen extract.")
def survivor_ledger_hard(workspace: Path) -> bool:
    return _passes(test_survivor_ledger_hard)


@criterion(description="the survivor months' load rows are exact.")
def survivor_month_load_exact(workspace: Path) -> bool:
    return _passes(test_survivor_month_load_exact)


@criterion(description="the survivor months' load rows hold on an unseen extract.")
def survivor_month_load_hard(workspace: Path) -> bool:
    return _passes(test_survivor_month_load_hard)


@criterion(description="the reserve of every month whose blocked lines wait along a chain is exact.")
def wait_reserve_exact(workspace: Path) -> bool:
    return _passes(test_wait_reserve_exact)


@criterion(description="the reserve of the waiting months holds on an unseen extract.")
def wait_reserve_hard(workspace: Path) -> bool:
    return _passes(test_wait_reserve_hard)


@criterion(description="the five identities are stated and every residual is zero.")
def validation_report_residuals_zero(workspace: Path) -> bool:
    return _passes(test_validation_report_residuals_zero)


criteria.actor_roster_exact(weight=3)
criteria.actor_roster_hard(weight=5)
criteria.alias_resolution_exact(weight=3)
criteria.alias_resolution_hard(weight=5)
criteria.allocation_and_load_exact(weight=3)
criteria.allocation_and_load_hard(weight=5)
criteria.allocation_remainder_and_floor_exact(weight=3)
criteria.audit_and_reconciliation_exact(weight=3)
criteria.audit_and_reconciliation_hard(weight=5)
criteria.cadence_and_waiver_exact(weight=3)
criteria.cadence_and_waiver_hard(weight=5)
criteria.cadence_streak_and_waiver_semantics_exact(weight=3)
criteria.class_partition_complete_and_disjoint(weight=5)
criteria.closure_and_blocked_exact(weight=3)
criteria.closure_and_blocked_hard(weight=5)
criteria.commitment_ledger_exact(weight=3)
criteria.commitment_ledger_hard(weight=5)
criteria.day_boundary_exact(weight=3)
criteria.declared_artifacts_present_and_parse(weight=1)
criteria.delivered_program_is_deterministic(weight=3)
criteria.documented_boundaries_exact(weight=3)
criteria.edge_partition_exact(weight=3)
criteria.edge_partition_hard(weight=5)
criteria.edge_scope_rule_exact(weight=3)
criteria.effort_units_and_origins_exact(weight=3)
criteria.escalation_queue_exact(weight=5)
criteria.failed_run_leaves_no_partial_file(weight=3)
criteria.identity_triangle_recomputed(weight=3)
criteria.negative_directory_iteration_order(weight=-3)
criteria.negative_environment_dependent_output(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_mutates_input_extract(weight=-5)
criteria.normalized_and_rejects_exact(weight=3)
criteria.normalized_and_rejects_hard(weight=5)
criteria.precedence_inversion_exact(weight=3)
criteria.project_lineage_exact(weight=3)
criteria.project_lineage_hard(weight=5)
criteria.queues_and_registers_exact(weight=3)
criteria.queues_and_registers_hard(weight=5)
criteria.reject_precedence_exact(weight=3)
criteria.rollups_and_provenance_exact(weight=3)
criteria.rollups_and_provenance_hard(weight=5)
criteria.run_manifest_counterfactuals_exact(weight=3)
criteria.run_manifest_exact(weight=3)
criteria.run_manifest_hard(weight=5)
criteria.state_resolution_and_contests_exact(weight=3)
criteria.state_resolution_and_contests_hard(weight=5)
criteria.survivor_allocation_exact(weight=3)
criteria.survivor_allocation_hard(weight=5)
criteria.survivor_ledger_exact(weight=3)
criteria.survivor_ledger_hard(weight=5)
criteria.survivor_month_load_exact(weight=3)
criteria.survivor_month_load_hard(weight=5)
criteria.validation_report_residuals_zero(weight=3)
criteria.wait_reserve_exact(weight=3)
criteria.wait_reserve_hard(weight=5)
