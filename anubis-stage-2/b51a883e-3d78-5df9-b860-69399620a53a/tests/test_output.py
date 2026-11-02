"""Grading for the Brassmoor Skirmish replay engine.

The grading side rebuilds the rule tables, the maps, the player list and a
fresh evaluation set of replay logs from its own seed, runs the submitted
/app/out/optimize.py on that set as an unprivileged user, and compares the
reports with an independent reference simulation. Unamended matches isolate
individual game rules; amended matches separately exercise final recovery and
every intermediate revision audit. No measured difficulty score is assumed.

Negative checks return True when the named cheat is present.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
from pathlib import Path

from rewardkit import criteria, criterion

# allow: SIZE_OK - QC requires one verifier module, including its independent corpus builder.

SAMPLE_SEED = 7340213385512409
CHALLENGE_SEED = 4419927035126683
EVAL_SEED = 9182736450918273
DECOY_SEED = 2718281828459045

OUT_DIR = Path("/app/out")
SUBMISSION = OUT_DIR / "optimize.py"
SCENARIOS = ["visible", "peak", "steady", "burst", "latency"]
REPORTS = ["perf_report.json", "bottleneck_analysis.json", "recommendations.json", "data_quality.json"]
SHIPPED_REPORTS = {
    "/app/out/scenario_visible.json": "matches",
    "/app/out/scenario_peak.json": "matches",
    "/app/out/scenario_steady.json": "matches",
    "/app/out/scenario_burst.json": "matches",
    "/app/out/scenario_latency.json": "matches",
    "/app/out/perf_report.json": "scenarios",
    "/app/out/bottleneck_analysis.json": "scenarios",
    "/app/out/recommendations.json": "units",
    "/app/out/data_quality.json": "scenarios",
}
RUN_TIMEOUT_SEC = 300
M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF

LEVER_VARIANTS = {
    "L1": ["L1"], "L2": ["L2"], "L4": ["L4"], "L5": ["L5"],
    "L6": ["L6", "L7a", "L7b"],
    "L9": ["L9", "L10"],
    "L11": ["L11"],
    "L13": ["L13a", "L13b", "C14", "C23"],
    "L14": ["L14", "C8", "L15a", "L15b", "C12", "C21", "C26"],
    "L16": ["L16", "C10", "C24"],
}
# A lever is one graded property and owns every naive variant of it, so one
# misreading of that property is charged to that lever alone: initiative
# order (L6 full printed initiative, L7a no side alternation, L7b unit
# numbers compared as text), movement (L9 every class pays foot costs, L10 no
# zone of control stop), range and sight (L13, C14 range bonus from the
# target's cell, C23 living units not blocking), status effects (L14 poison
# stacks, C8 no tick, L15a units never rout, L15b printed season 4 rout
# threshold, C12 routed target keeps its defence, C21 routed units still
# attack, C26 poison never routs) and objectives (L16, C10 own cell only, C24
# scored before the poison tick).
# Every other rule clause of sections 3.3, 8 and 9 has a naive variant of its
# own. They are graded as two pools: the attack rules of section 9 and the
# turn flow rules of sections 3.3 and 8. A misreading one of them reproduces
# is charged to its pool and nothing else. Absolute keyframe adoption (L3)
# belongs to the baseline pool, the digests no single rule explains.
BASE_VARIANTS = {
    "L3": ["L3"],    # keyframes never adopted
}
COMBAT_VARIANTS = {
    "C1": ["C1"],    # no flank bonus
    "C2": ["C2"],    # critical hit does not double the dice
    "C3": ["C3"],    # terrain defence left out
    "C4": ["C4"],    # minimum damage 0
    "C5": ["C5"],    # no pinned penalty
    "C6": ["C6"],    # no brace bonus
    "C9": ["C9"],    # no critical hit
    "C13": ["C13"],  # shield wall from any friendly neighbour
    "C15": ["C15"],  # flank not capped
    "C16": ["C16"],  # flank counted for ranged attacks too
    "C22": ["C22"],  # ranged units cannot attack at distance 1
    "C25": ["C25"],  # the attacker counts towards its own flank
    "L12": ["L12"],  # armour taken off before the advantage ratio
}
FLOW_VARIANTS = {
    "C7": ["C7"],    # unit numbers compared as text in the roster order
    "C11": ["C11"],  # a unit may react more than once per turn
    "C17": ["C17"],  # skirmishers stop in a zone of control too
    "C18": ["C18"],  # a failed waypoint is skipped, the walk goes on
    "C19": ["C19"],  # reactions also follow a move that made no step
    "C20": ["C20"],  # reactions go in roster order, not execution order
    "L8": ["L8"],    # READY units never react
}
CORE_VARIANTS = {**COMBAT_VARIANTS, **FLOW_VARIANTS}
ALL_VARIANTS = {**LEVER_VARIANTS, **BASE_VARIANTS, **CORE_VARIANTS}

# ---------------------------------------------------------------- tables

UNIT_TABLE = {
    "pikeman": {"class": "foot", "hp": 14, "atk": 3, "def": 4, "move": 3, "range": 1, "dice": [1, 8, 1], "armour": 2, "init": 3, "cost": 4, "tags": ["pike"]},
    "swordsman": {"class": "foot", "hp": 16, "atk": 4, "def": 3, "move": 3, "range": 1, "dice": [1, 10, 1], "armour": 1, "init": 4, "cost": 5, "tags": []},
    "archer": {"class": "foot", "hp": 10, "atk": 3, "def": 1, "move": 3, "range": 4, "dice": [1, 6, 1], "armour": 0, "init": 5, "cost": 4, "tags": ["ranged"]},
    "crossbow": {"class": "foot", "hp": 11, "atk": 5, "def": 2, "move": 2, "range": 5, "dice": [1, 12, 0], "armour": 1, "init": 2, "cost": 5, "tags": ["ranged"]},
    "lancer": {"class": "horse", "hp": 15, "atk": 5, "def": 2, "move": 5, "range": 1, "dice": [2, 6, 0], "armour": 1, "init": 6, "cost": 7, "tags": []},
    "outrider": {"class": "horse", "hp": 10, "atk": 3, "def": 2, "move": 6, "range": 1, "dice": [1, 6, 1], "armour": 0, "init": 7, "cost": 4, "tags": ["skirmisher"]},
    "fenrunner": {"class": "foot", "hp": 9, "atk": 3, "def": 2, "move": 4, "range": 1, "dice": [1, 4, 1], "armour": 0, "init": 6, "cost": 4, "tags": ["skirmisher", "poison"]},
}
TYPE_ORDER = list(UNIT_TABLE)

TERRAIN_TABLE = {
    ".": {"name": "plain", "cost": {"foot": 1, "horse": 1}, "def": 0, "blocks_los": False, "range_bonus": 0, "objective": False},
    "r": {"name": "road", "cost": {"foot": 1, "horse": 1}, "def": 0, "blocks_los": False, "range_bonus": 0, "objective": False},
    "f": {"name": "forest", "cost": {"foot": 2, "horse": 3}, "def": 2, "blocks_los": True, "range_bonus": 0, "objective": False},
    "h": {"name": "hill", "cost": {"foot": 2, "horse": 2}, "def": 1, "blocks_los": False, "range_bonus": 1, "objective": False},
    "m": {"name": "fen", "cost": {"foot": 2, "horse": None}, "def": -1, "blocks_los": False, "range_bonus": 0, "objective": False},
    "w": {"name": "water", "cost": {"foot": None, "horse": None}, "def": 0, "blocks_los": False, "range_bonus": 0, "objective": False},
    "O": {"name": "objective", "cost": {"foot": 1, "horse": 1}, "def": 0, "blocks_los": False, "range_bonus": 0, "objective": True},
}

ADVANTAGE_PAIRS = [
    ("pikeman", "lancer", 3, 2), ("pikeman", "outrider", 3, 2),
    ("lancer", "archer", 3, 2), ("lancer", "crossbow", 3, 2),
    ("crossbow", "lancer", 5, 4), ("swordsman", "pikeman", 5, 4),
    ("archer", "fenrunner", 1, 2), ("outrider", "archer", 5, 4),
    ("fenrunner", "swordsman", 5, 4),
]

RULESETS = {
    "rulesets": {"1": {"reseed": False}, "2": {"reseed": True, "reseed_multiplier": 2654435761}},
    "dice": {"multiplier": 1103515245, "increment": 12345, "modulus_bits": 32, "output_shift": 23, "output_bits": 9},
    "combat": {"hit_target": 10, "crit_roll": 20, "flank_cap": 2, "shield_wall_bonus": 2, "brace_bonus": 1, "rout_penalty": 2, "pinned_penalty": 2, "min_damage": 1},
    "status": {"poison_turns": 3},
    "scoring": {"control_points": 5},
    "ladder": {"win_base": 16, "win_divisor": 25, "win_min": 4, "win_max": 28, "draw_divisor": 50, "draw_cap": 8},
    "balance": {"nerf_at": 2600, "buff_at": 1100},
}


class Rng:
    def __init__(self, seed: int) -> None:
        self.s = (seed & M64) or 0x9E3779B97F4A7C15

    def next(self) -> int:
        x = self.s
        x ^= x >> 12
        x = (x ^ (x << 25)) & M64
        x ^= x >> 27
        self.s = x
        return (x * 0x2545F4914F6CDD1D) & M64

    def rint(self, lo: int, hi: int) -> int:
        return lo + self.next() % (hi - lo + 1)

    def pct(self, p: int) -> bool:
        return self.next() % 100 < p

    def pick(self, seq):
        return seq[self.next() % len(seq)]


def table_texts() -> dict:
    out = {}
    out["units.json"] = json.dumps({"units": UNIT_TABLE}, indent=2) + "\n"
    out["terrain.json"] = json.dumps({"terrain": TERRAIN_TABLE}, indent=2) + "\n"
    out["advantage.json"] = json.dumps({"default": [1, 1], "pairs": [{"attacker": a, "defender": d, "num": n, "den": q} for a, d, n, q in ADVANTAGE_PAIRS]}, indent=2) + "\n"
    out["rulesets.json"] = json.dumps(RULESETS, indent=2) + "\n"
    rng = Rng(0x5EED0001)
    syl = ["ka", "ri", "mo", "ten", "va", "lo", "shi", "dar", "en", "pu", "go", "ral", "mi", "nor", "ta", "bek"]
    rows = []
    for i in range(1, 241):
        name = (rng.pick(syl) + rng.pick(syl) + rng.pick(syl)).capitalize()
        rows.append('  {"id": "P%04d", "name": "%s", "rating": %d}' % (i, name, rng.rint(1200, 1800)))
    out["players.json"] = '{"players": [\n' + ",\n".join(rows) + "\n]}\n"
    out["maps.txt"] = _maps_text()
    return out


def _maps_text() -> str:
    rng = Rng(0x5EED0002)
    lines = ["# Brassmoor map atlas, season 5", "# one MAP block per map, rows listed top row first", ""]
    for i in range(1, 171):
        w, h = rng.rint(11, 16), rng.rint(9, 13)
        g = [["." for _ in range(w)] for _ in range(h)]
        for ch, blobs, size in (("f", rng.rint(2, 4), 6), ("h", rng.rint(1, 3), 4), ("m", rng.rint(1, 3), 4), ("w", rng.rint(0, 2), 3)):
            for _ in range(blobs):
                x, y = rng.rint(3, w - 4), rng.rint(0, h - 1)
                for _ in range(rng.rint(2, size)):
                    if g[y][x] == ".":
                        g[y][x] = ch
                    d = rng.next() % 4
                    x = min(w - 4, max(3, x + (1, -1, 0, 0)[d]))
                    y = min(h - 1, max(0, y + (0, 0, 1, -1)[d]))
        ry = rng.rint(1, h - 2)
        for x in range(w):
            if g[ry][x] in ".fhm":
                g[ry][x] = "r"
        for y in range(h):
            for x in (0, 1, 2, w - 3, w - 2, w - 1):
                if g[y][x] in "mw":
                    g[y][x] = "."
            if rng.pct(10):
                g[y][rng.pick([0, 1, w - 2, w - 1])] = rng.pick(["f", "h"])
        for _ in range(rng.rint(1, 3)):
            x, y = rng.rint(w // 2 - 2, w // 2 + 1), rng.rint(1, h - 2)
            g[y][x] = "O"
        lines.append("MAP moor-%03d %d %d" % (i, w, h))
        lines.extend("".join(r) for r in g)
        lines.append("ENDMAP")
    return "\n".join(lines) + "\n"


def parse_maps(text: str) -> dict:
    maps, cur = {}, None
    for line in text.splitlines():
        if line.startswith("MAP "):
            _, name, w, h = line.split()
            cur = (name, int(w), int(h), [])
        elif line == "ENDMAP":
            maps[cur[0]] = (cur[1], cur[2], cur[3])
            cur = None
        elif cur is not None:
            cur[3].append(line)
    return maps


def players_list(text: str) -> list:
    return json.loads(text)["players"]


# ---------------------------------------------------------------- parsing

def _uid_ok(tok: str) -> bool:
    return len(tok) >= 2 and tok[0] in "AB" and tok[1:].isdigit() and tok[1] != "0"


def _nat(tok: str) -> bool:
    return tok.isdigit() and (tok == "0" or tok[0] != "0")


def _hex8(tok: str) -> bool:
    return len(tok) == 8 and all(c in "0123456789abcdef" for c in tok)


def parse_order(tok: list):
    """Return (lag, uid, kind, arg) or None for a malformed order line."""
    head = tok[0]
    if head == "O":
        lag = 0
    elif head.startswith("O~") and len(head) == 3 and head[2] in "123456789":
        lag = int(head[2])
    else:
        return None
    if len(tok) < 3 or not _uid_ok(tok[1]):
        return None
    kind = tok[2]
    if kind in ("HOLD", "READY") and len(tok) == 3:
        return (lag, tok[1], kind, None)
    if kind == "ATTACK" and len(tok) == 4 and _uid_ok(tok[3]):
        return (lag, tok[1], kind, tok[3])
    if kind == "MOVE" and len(tok) >= 4:
        pts = []
        for p in tok[3:]:
            a = p.split(",")
            if len(a) != 2 or not _nat(a[0]) or not _nat(a[1]):
                return None
            pts.append((int(a[0]), int(a[1])))
        return (lag, tok[1], kind, pts)
    return None


def parse_keyframe(tok: list):
    if len(tok) < 4 or not _nat(tok[1]) or not tok[2].startswith("rng=") or not _hex8(tok[2][4:]) or not tok[3].startswith("cp="):
        return None
    cps = tok[3][3:].split(",")
    if len(cps) != 2 or not all(_nat(c) for c in cps):
        return None
    units = []
    for t in tok[4:]:
        if "@" not in t:
            return None
        uid, rest = t.split("@", 1)
        vals = rest.split(",")
        if not _uid_ok(uid) or len(vals) != 5 or not all(_nat(v) for v in vals) or vals[4] not in ("0", "1"):
            return None
        units.append((uid, int(vals[0]), int(vals[1]), int(vals[2]), int(vals[3]), int(vals[4])))
    return (int(tok[1]), int(tok[2][4:], 16), (int(cps[0]), int(cps[1])), units)


def parse_log(text: str) -> dict:
    """Parse a replay log into matches plus syntactic counters."""
    matches, cur, turn = [], None, None
    counters = {"malformed_lines": 0, "unknown_unit_orders": 0, "orders_total": 0}
    for raw in text.split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tok = line.split(" ")
        head = tok[0]
        ok = False
        if head == "MATCH" and cur is None and len(tok) == 9:
            kv = {}
            for t in tok[2:]:
                if "=" in t:
                    k, v = t.split("=", 1)
                    kv[k] = v
            if (kv.get("v") in ("1", "2") and kv.get("rules") in ("1", "2") and "map" in kv and _hex8(kv.get("seed", ""))
                    and "p0" in kv and "p1" in kv and _nat(kv.get("turns", "x")) and len(kv) == 7):
                cur = {"id": tok[1], "v": int(kv["v"]), "rules": int(kv["rules"]), "map": kv["map"], "seed": int(kv["seed"], 16),
                       "players": [kv["p0"], kv["p1"]], "deploy": [], "turns": [], "edits": [], "tail": False}
                turn = None
                ok = True
        elif cur is not None and head == "R":
            if len(tok) >= 5 and all(_nat(x) for x in tok[1:4]):
                ti, si, rev = (int(x) for x in tok[1:4])
                drop = tok[4:] == ["DROP"]
                order = None if drop else parse_order(tok[4:])
                if (0 < ti <= len(cur["turns"]) and 0 < si <= len(cur["turns"][ti - 1]["orders"])
                        and (drop or order is not None)):
                    cur["edits"].append((ti, si, rev, order))
                    cur["tail"] = True
                    ok = True
        elif cur is not None and cur["tail"] and head != "END":
            ok = False
        elif cur is not None and head == "U" and len(tok) == 5 and not cur["turns"]:
            if _uid_ok(tok[1]) and tok[2] in UNIT_TABLE and _nat(tok[3]) and _nat(tok[4]):
                cur["deploy"].append((tok[1], tok[2], int(tok[3]), int(tok[4])))
                ok = True
        elif cur is not None and head == "T" and len(tok) == 2 and _nat(tok[1]):
            turn = {"n": int(tok[1]), "kf": None, "orders": []}
            cur["turns"].append(turn)
            ok = True
        elif cur is not None and head == "K" and turn is not None and not turn["orders"] and turn["kf"] is None:
            kf = parse_keyframe(tok)
            if kf is not None:
                turn["kf"] = kf
                ok = True
        elif cur is not None and head == "END" and len(tok) == 2 and tok[1] == cur["id"]:
            matches.append(cur)
            cur, turn = None, None
            ok = True
        elif cur is not None and turn is not None and (head == "O" or head.startswith("O~")):
            od = parse_order(tok)
            if od is not None:
                ok = True
                known = {d[0] for d in cur["deploy"]}
                if od[1] not in known or (od[2] == "ATTACK" and od[3] not in known):
                    counters["unknown_unit_orders"] += 1
                else:
                    counters["orders_total"] += 1
                    turn["orders"].append(od)
        if not ok:
            counters["malformed_lines"] += 1
    return {"matches": matches, "counters": counters}


def effective_orders(orders: list, naive_lag: bool):
    by_unit = {}
    for od in orders:
        by_unit.setdefault(od[1], []).append(od)
    eff, late, sup = {}, 0, 0
    for uid, lst in by_unit.items():
        if naive_lag:
            eff[uid] = lst[-1]
            continue
        fresh = [o for o in lst if o[0] == 0]
        lag1 = [o for o in lst if o[0] == 1]
        nlate = len(lst) - len(fresh) - len(lag1)
        late += nlate
        pick = fresh[-1] if fresh else (lag1[-1] if lag1 else None)
        if pick is not None:
            eff[uid] = pick
            sup += len(fresh) + len(lag1) - 1
    return eff, late, sup


# ---------------------------------------------------------------- simulation

class Unit:
    __slots__ = ("uid", "side", "num", "typ", "x", "y", "hp", "poison", "routed", "spec")

    def __init__(self, uid, typ, x, y):
        self.uid, self.typ, self.x, self.y = uid, typ, x, y
        self.side = 0 if uid[0] == "A" else 1
        self.num = int(uid[1:])
        self.spec = UNIT_TABLE[typ]
        self.hp = self.spec["hp"]
        self.poison = 0
        self.routed = 0


def fnv32(text: str) -> str:
    h = 0x811C9DC5
    for b in text.encode():
        h = ((h ^ b) * 0x01000193) & M32
    return "%08x" % h


class Sim:
    def __init__(self, match: dict, gamemap, flags=frozenset()):
        self.f = flags
        self.W, self.H, self.rows = gamemap
        self.match = match
        self.flip = match["v"] == 2 and "L1" not in flags
        self.rng = match["seed"]
        self.cp = [0, 0]
        self.units = {}
        self.occ = {}
        for uid, typ, x, y in match["deploy"]:
            u = Unit(uid, typ, x, self.fy(y))
            self.units[uid] = u
            self.occ[(u.x, u.y)] = u
        self.adv = {(a, d): (n, q) for a, d, n, q in ADVANTAGE_PAIRS}
        self.objectives = [(x, y) for y in range(self.H) for x in range(self.W) if self.rows[y][x] == "O"]
        self.draws = {"attack": 0, "damage": 0, "reaction": 0}
        self.dealt = {t: 0 for t in UNIT_TABLE}
        self.kills = {t: 0 for t in UNIT_TABLE}
        self.phase = "attack"

    def clone(self, flags):
        """Copy of the live state under other rule flags; tables are shared."""
        c = copy.copy(self)
        c.f = flags
        c.flip = self.match["v"] == 2 and "L1" not in flags
        c.cp = list(self.cp)
        c.units = {}
        for uid, u in self.units.items():
            v = copy.copy(u)
            c.units[uid] = v
        c.occ = {(v.x, v.y): v for v in c.units.values()}
        c.draws, c.dealt, c.kills = dict(self.draws), dict(self.dealt), dict(self.kills)
        return c

    def fy(self, y):
        return self.H - 1 - y if self.flip else y

    def roll(self, sides):
        while True:
            self.rng = (self.rng * 1103515245 + 12345) & M32
            o = (self.rng >> 23) & 0x1FF
            self.draws[self.phase] += 1
            if "L4" in self.f or o < 512 - 512 % sides:
                return 1 + o % sides

    def living(self):
        return sorted(self.units.values(), key=lambda u: (u.side, str(u.num) if "C7" in self.f else u.num))

    def digest(self, t):
        body = "t=%d;rng=%08x;cp=%d,%d;" % (t, self.rng, self.cp[0], self.cp[1])
        body += "".join("%s@%d,%d,%d,%d,%d;" % (u.uid, u.x, u.y, u.hp, u.poison, u.routed) for u in self.living())
        return fnv32(body)

    def snapshot(self):
        return (self.rng, (self.cp[0], self.cp[1]), [(u.uid, u.x, u.y, u.hp, u.poison, u.routed) for u in self.living()])

    def begin(self, n):
        if self.match["rules"] == 2 and "L5" not in self.f:
            self.rng = (self.match["seed"] ^ ((n * 2654435761) & M32)) & M32

    def keyframe(self, kf):
        _, rng, cp, units = kf
        units = [(uid, x, self.fy(y), hp, p, r) for uid, x, y, hp, p, r in units]
        mine = self.snapshot()
        diverged = mine != (rng, cp, units)
        self.rng, self.cp = rng, [cp[0], cp[1]]
        keep = {}
        for uid, x, y, hp, p, r in units:
            u = self.units.get(uid)
            if u is None:
                typ = next(d[1] for d in self.match["deploy"] if d[0] == uid)
                u = Unit(uid, typ, x, y)
            u.x, u.y, u.hp, u.poison, u.routed = x, y, hp, p, r
            keep[uid] = u
        self.units = keep
        self.occ = {(u.x, u.y): u for u in keep.values()}
        return diverged

    def cell(self, x, y):
        return TERRAIN_TABLE[self.rows[y][x]]

    def step_cost(self, u, x, y):
        col = "foot" if "L9" in self.f else u.spec["class"]
        return self.cell(x, y)["cost"][col]

    def adjacent_enemy(self, u):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            v = self.occ.get((u.x + dx, u.y + dy))
            if v is not None and v.side != u.side:
                return True
        return False

    def los_clear(self, a, b):
        x0, y0, x1, y1 = a.x, a.y, b.x, b.y
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
            if x0 == x1 and y0 == y1:
                return True
            if self.cell(x0, y0)["blocks_los"] or ((x0, y0) in self.occ and "C23" not in self.f):
                return False

    def attack_mode(self, a, b):
        """None if illegal, else 'melee', 'pinned' or 'ranged'."""
        if b.uid not in self.units or a.uid not in self.units or a.side == b.side:
            return None
        if a.routed and "L15a" not in self.f and "C21" not in self.f:
            return None
        dist = abs(a.x - b.x) + abs(a.y - b.y)
        ranged = "ranged" in a.spec["tags"]
        if dist == 1:
            if ranged and "C22" in self.f:
                return None
            return "pinned" if ranged else "melee"
        if not ranged or dist < 2:
            return None
        reach = a.spec["range"]
        if "L13b" not in self.f:
            reach += self.cell(b.x, b.y)["range_bonus"] if "C14" in self.f else self.cell(a.x, a.y)["range_bonus"]
        if dist > reach:
            return None
        if "L13a" not in self.f and not self.los_clear(a, b):
            return None
        return "ranged"

    def remove(self, u):
        del self.units[u.uid]
        del self.occ[(u.x, u.y)]

    def rout_check(self, u):
        if "L15a" in self.f or u.routed:
            return
        if ("L15b" in self.f and u.hp * 3 <= u.spec["hp"]) or ("L15b" not in self.f and u.hp * 4 <= u.spec["hp"]):
            u.routed = 1

    def strike(self, a, b, mode, phase):
        self.phase = phase
        r = self.roll(20)
        crit = r == 20 and "C9" not in self.f
        if not crit:
            flank = 0
            if mode != "ranged" or "C16" in self.f:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    v = self.occ.get((b.x + dx, b.y + dy))
                    if v is not None and v.side == a.side and (v is not a or "C25" in self.f):
                        flank += 1
                if "C15" not in self.f:
                    flank = min(2, flank)
            if "C1" in self.f:
                flank = 0
            dfn = b.spec["def"] + (0 if "C3" in self.f else self.cell(b.x, b.y)["def"])
            if "L11" not in self.f and "pike" in b.spec["tags"]:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    v = self.occ.get((b.x + dx, b.y + dy))
                    if v is not None and v.side == b.side and ("pike" in v.spec["tags"] or "C13" in self.f):
                        dfn += 2
                        break
            if b.uid in self.braced and "C6" not in self.f:
                dfn += 1
            if b.routed and "L15a" not in self.f and "C12" not in self.f:
                dfn -= 2
            atk = a.spec["atk"] - (2 if mode == "pinned" and "C5" not in self.f else 0)
            if r + atk + flank < 10 + dfn:
                return
        if phase == "attack":
            self.phase = "damage"
        n, sides, bonus = a.spec["dice"]
        total = bonus
        for _ in range(n * (2 if crit and "C2" not in self.f else 1)):
            total += self.roll(sides)
        num, den = self.adv.get((a.typ, b.typ), (1, 1))
        if "L12" in self.f:
            dmg = (total - b.spec["armour"]) * num // den
        else:
            dmg = total * num // den - b.spec["armour"]
        dmg = max(0 if "C4" in self.f else 1, dmg)
        b.hp -= dmg
        self.dealt[a.typ] += dmg
        if b.hp <= 0:
            self.remove(b)
            self.kills[a.typ] += 1
            return
        if "poison" in a.spec["tags"]:
            b.poison = b.poison + 3 if "L14" in self.f else 3
        self.rout_check(b)

    def move(self, u, pts, order):
        mp = u.spec["move"]
        steps = 0
        for x, y in pts:
            y = self.fy(y)
            if abs(x - u.x) + abs(y - u.y) != 1 or not (0 <= x < self.W and 0 <= y < self.H):
                if "C18" in self.f:
                    continue
                break
            c = self.step_cost(u, x, y)
            if c is None or (x, y) in self.occ or c > mp:
                if "C18" in self.f:
                    continue
                break
            mp -= c
            del self.occ[(u.x, u.y)]
            u.x, u.y = x, y
            self.occ[(x, y)] = u
            steps += 1
            if "L10" not in self.f and ("skirmisher" not in u.spec["tags"] or "C17" in self.f) and self.adjacent_enemy(u):
                break
        if (steps == 0 and "C19" not in self.f) or "L8" in self.f:
            return
        for r in (self.living() if "C20" in self.f else order):
            if u.uid not in self.units:
                return
            if r.side == u.side or r.uid not in self.armed or (r.uid in self.reacted and "C11" not in self.f) or r.uid not in self.units:
                continue
            mode = self.attack_mode(r, u)
            if mode is None:
                continue
            self.reacted.add(r.uid)
            self.strike(r, u, mode, "reaction")

    def play(self, n, orders):
        eff, _, _ = effective_orders(orders, "L2" in self.f)
        if "L6" in self.f:
            init = {u.uid: u.spec["init"] for u in self.units.values()}
        else:
            init = {u.uid: u.spec["init"] - (u.spec["hp"] - u.hp) // 3 for u in self.units.values()}
        if "L7a" in self.f:
            key = lambda u: (-init[u.uid], u.side, u.num)
        elif "L7b" in self.f:
            key = lambda u: (-init[u.uid], u.side if n % 2 else 1 - u.side, str(u.num))
        else:
            key = lambda u: (-init[u.uid], u.side if n % 2 else 1 - u.side, u.num)
        order = sorted(self.units.values(), key=key)
        self.braced = {uid for uid, od in eff.items() if od[2] == "HOLD" and uid in self.units}
        self.armed = {uid for uid, od in eff.items() if od[2] == "READY" and uid in self.units}
        self.reacted = set()
        for u in order:
            if u.uid not in self.units:
                continue
            od = eff.get(u.uid)
            if od is None:
                continue
            if od[2] == "MOVE":
                self.move(u, od[3], order)
            elif od[2] == "ATTACK":
                b = self.units.get(od[3])
                if b is not None:
                    mode = self.attack_mode(u, b)
                    if mode is not None:
                        self.strike(u, b, mode, "attack")
        if "C24" in self.f:
            self.score_objectives()
        for u in self.living():
            if u.poison > 0 and "C8" not in self.f:
                u.hp -= 1
                u.poison -= 1
                if u.hp <= 0:
                    self.remove(u)
                elif "C26" not in self.f:
                    self.rout_check(u)
        if "C24" not in self.f:
            self.score_objectives()
        self.braced, self.armed, self.reacted = set(), set(), set()
        return self.digest(n)

    def score_objectives(self):
        for ox, oy in self.objectives:
            cnt = [0, 0]
            for dx, dy in (((0, 0),) if "C10" in self.f else ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))):
                v = self.occ.get((ox + dx, oy + dy))
                if v is not None:
                    cnt[v.side] += 1
            if "L16" in self.f:
                if cnt[0] != cnt[1]:
                    self.cp[0 if cnt[0] > cnt[1] else 1] += 1
            elif (cnt[0] > 0) != (cnt[1] > 0):
                self.cp[0 if cnt[0] else 1] += 1


def _turn(sim, turn, flags):
    if turn["kf"] is not None and "L3" not in flags:
        sim.keyframe(turn["kf"])
    sim.begin(turn["n"])
    return sim.play(turn["n"], turn["orders"])


def local_sensitivity(match: dict, maps: dict) -> list:
    """Per digest index, {variant: digest it gives} for every rule variant that
    changes that digest when the turn starts from the true state.
    Earlier mistakes never carry over into a later turn."""
    gm = maps[match["map"]]
    base = Sim(match, gm)
    want = base.digest(0)
    here = {}
    for rule, variants in ALL_VARIANTS.items():
        for v in variants:
            d = Sim(match, gm, frozenset([v])).digest(0)
            if d != want:
                here[v] = d
    out = [here]
    for turn in match["turns"]:
        start = base.clone(frozenset())
        want = _turn(base, turn, frozenset())
        here = {}
        for rule, variants in ALL_VARIANTS.items():
            for v in variants:
                d = _turn(start.clone(frozenset([v])), turn, frozenset([v]))
                if d != want:
                    here[v] = d
        out.append(here)
    return out


def run_match(match: dict, maps: dict, flags=frozenset()) -> dict:
    sim = Sim(match, maps[match["map"]], flags)
    digests = [sim.digest(0)]
    divergences = []
    for turn in match["turns"]:
        if turn["kf"] is not None and "L3" not in flags:
            if sim.keyframe(turn["kf"]):
                divergences.append(turn["n"])
        sim.begin(turn["n"])
        digests.append(sim.play(turn["n"], turn["orders"]))
    return {"sim": sim, "digests": digests, "divergences": divergences}


def revision_replay(match: dict, maps: dict) -> dict:
    revisions, overrides = {}, {}
    known = {row[0] for row in match["deploy"]}
    counts = dict(applied=0, stale=0, unknown=0)
    result = run_match(match, maps)
    audit = []
    resolved = match
    for ti, si, revision, order in match.get("edits", []):
        address = (ti, si)
        if order is not None and (order[1] not in known or (order[2] == "ATTACK" and order[3] not in known)):
            counts["unknown"] += 1
            continue
        if revision != revisions.get(address, 0):
            counts["stale"] += 1
            continue
        revisions[address] = revision + 1
        overrides[address] = order
        turns = []
        for tindex, turn in enumerate(match["turns"], 1):
            slots = [overrides.get((tindex, sindex), original)
                     for sindex, original in enumerate(turn["orders"], 1)]
            turns.append({**turn, "orders": [item for item in slots if item is not None]})
        resolved = {**match, "turns": turns}
        updated = run_match(resolved, maps)
        a, b = result["sim"], updated["sim"]
        fingerprints = []
        for replay in (result, updated):
            encoded = ";".join(str(i) + ":" + d for i, d in enumerate(replay["digests"])) + ";"
            fingerprints.append(fnv32(encoded))
        audit.append({"turn": ti, "slot": si, "revision": revisions[address],
                      "before": fingerprints[0], "after": fingerprints[1],
                      "changed": [i for i in range(len(result["digests"]))
                                  if result["digests"][i] != updated["digests"][i]],
                      "draws_delta": {p: b.draws[p] - a.draws[p] for p in a.draws},
                      "damage_delta": {t: b.dealt[t] - a.dealt[t] for t in TYPE_ORDER},
                      "kills_delta": {t: b.kills[t] - a.kills[t] for t in TYPE_ORDER},
                      "divergences_before": result["divergences"],
                      "divergences_after": updated["divergences"]})
        result = updated
        counts["applied"] += 1
    return {**result, "resolved": resolved, "audit": audit, "edit_counts": counts}


# ---------------------------------------------------------------- generation

TIERS = {
    "visible": SimpleNamespace(matches=14, units=(4, 6), cap=24, v2=0, rules2=0, tamper=0, kf=[5], noise=0),
    "peak": SimpleNamespace(matches=80, units=(3, 6), cap=32, v2=45, rules2=45, tamper=30, kf=[7, 11], noise=2),
    "steady": SimpleNamespace(matches=74, units=(3, 6), cap=36, v2=40, rules2=55, tamper=20, kf=[9, 13], noise=2),
    "burst": SimpleNamespace(matches=80, units=(3, 6), cap=32, v2=40, rules2=40, tamper=25, kf=[6, 10], noise=3),
    "latency": SimpleNamespace(matches=80, units=(3, 6), cap=36, v2=65, rules2=50, tamper=20, kf=[8, 12], noise=3),
}
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
THEMES = [TYPE_ORDER, ["pikeman", "pikeman", "swordsman", "lancer"], ["pikeman", "swordsman", "outrider", "pikeman"],
          ["fenrunner", "fenrunner", "swordsman", "pikeman"], ["fenrunner", "pikeman", "lancer", "fenrunner"], ["archer", "crossbow", "swordsman", "outrider"],
          ["lancer", "outrider", "pikeman", "crossbow"]]


def _path(sim, u, goal_cells):
    grid_ok = lambda x, y: 0 <= x < sim.W and 0 <= y < sim.H and sim.rows[y][x] != "w"
    start = (u.x, u.y)
    prev = {start: None}
    q = [start]
    i = 0
    hit = None
    while i < len(q):
        c = q[i]
        i += 1
        if c in goal_cells and c != start:
            hit = c
            break
        for dx, dy in DIRS:
            nx, ny = c[0] + dx, c[1] + dy
            if (nx, ny) not in prev and grid_ok(nx, ny):
                prev[(nx, ny)] = c
                q.append((nx, ny))
    if hit is None:
        return []
    out = []
    while hit != start:
        out.append(hit)
        hit = prev[hit]
    return out[::-1]


def _plan(sim, rng, u):
    enemies = [v for v in sim.living() if v.side != u.side]
    if not enemies:
        return ("HOLD", None)
    dist = lambda v: abs(v.x - u.x) + abs(v.y - u.y)
    near = min(enemies, key=lambda v: (dist(v), v.side, v.num))
    nd = dist(near)
    roll = rng.rint(0, 99)
    if roll < 6:
        return ("HOLD", None)
    if roll < 16 and nd <= 4:
        return ("READY", None)
    legal = [v for v in enemies if sim.attack_mode(u, v) is not None]
    if "ranged" in u.spec["tags"] and rng.pct(30):
        loose = [v for v in enemies if 2 <= dist(v) <= u.spec["range"] + 1]
        if loose:
            return ("ATTACK", min(loose, key=lambda v: (v.hp, v.side, v.num)).uid)

    def pref(v):
        n, q = sim.adv.get((u.typ, v.typ), (1, 1))
        poisoned = 0 if ("poison" in u.spec["tags"] and v.poison > 0) else 1
        return (poisoned, -n * 100 // q, v.hp, v.side, v.num)

    if legal and rng.pct(90):
        return ("ATTACK", min(legal, key=pref).uid)
    if "pike" in u.spec["tags"] and rng.pct(55):
        for dx, dy in DIRS:
            w = sim.occ.get((u.x + dx, u.y + dy))
            if w is not None and w.side == u.side and "pike" in w.spec["tags"]:
                return ("HOLD", None) if rng.pct(60) else ("READY", None)
    if u.num % 3 == 0 and sim.objectives and rng.pct(60):
        goals = set()
        for ox, oy in sim.objectives:
            goals.add((ox, oy))
            for dx, dy in DIRS:
                goals.add((ox + dx, oy + dy))
    elif "ranged" not in u.spec["tags"] and len(enemies) > 1 and rng.pct(35):
        far = max(enemies, key=lambda v: (dist(v), -v.side, -v.num))
        goals = {(far.x + dx, far.y + dy) for dx, dy in DIRS}
    else:
        goals = {(near.x + dx, near.y + dy) for dx, dy in DIRS}
    path = _path(sim, u, goals)
    if not path:
        return ("HOLD", None)
    return ("MOVE", path[: u.spec["move"] + 1])


def _render(sim, uid, od, lag=0):
    head = "O" if lag == 0 else "O~%d" % lag
    kind, arg = od
    if kind == "MOVE":
        return "%s %s MOVE %s" % (head, uid, " ".join("%d,%d" % (x, sim.H - 1 - y if sim.flip else y) for x, y in arg))
    if kind == "ATTACK":
        return "%s %s ATTACK %s" % (head, uid, arg)
    return "%s %s %s" % (head, uid, kind)


def _alt(sim, rng, u):
    k = rng.rint(0, 3)
    if k == 0:
        return ("HOLD", None)
    if k == 1:
        return ("READY", None)
    if k == 2:
        enemies = [v for v in sim.living() if v.side != u.side]
        return ("ATTACK", rng.pick(enemies).uid)
    dx, dy = rng.pick(list(DIRS))
    return ("MOVE", [(min(sim.W - 1, max(0, u.x + dx)), min(sim.H - 1, max(0, u.y + dy)))])


MALFORMED = ["O {u} MOVE {x};{y}", "O {u} SPRINT", "O {u} ATTACK", "O~0 {u} HOLD", "ORDER {u} HOLD",
             "O {u} MOVE", "O {u} ATTACK {u} {u}", "O {u} MOVE {x},{y},1", "T", "O~x {u} READY", "O {u} HOLD now"]


SPARSE_NUMBERS = {1: 1, 2: 2, 3: 9, 4: 10, 5: 11, 6: 12}
SIEGE_MATCHES = 2
SIEGE_RULES = ("C15", "C20")  # flank cap, reactions in execution order


def _siege_cells(gamemap) -> list:
    """Centre cells away from both deployment strips whose own cell and four
    neighbours every unit class can stand on."""
    W, H, rows = gamemap
    ok = lambda x, y: all(c is not None for c in TERRAIN_TABLE[rows[y][x]]["cost"].values())
    return [(x, y) for y in range(1, H - 1) for x in range(3, W - 3)
            if ok(x, y) and all(ok(x + dx, y + dy) for dx, dy in DIRS)]


def gen_match(rng, cfg, mid, mapname, gamemap, players, siege=False):
    W, H, rows = gamemap
    v = 2 if rng.pct(cfg.v2) else 1
    rules = 2 if rng.pct(cfg.rules2) else 1
    seed = rng.next() & M32
    p0, p1 = rng.pick(players), rng.pick(players)
    while p1 == p0:
        p1 = rng.pick(players)
    deploy, used = [], set()
    # Every second match of a noisy export numbers its units sparsely, so that
    # numeric and text order of unit numbers differ. No random draw is spent.
    sparse = cfg.noise > 0 and int(mid[-1], 16) % 2 == 0
    theme = TYPE_ORDER if cfg.noise == 0 else rng.pick(THEMES)
    # A siege match places side B's first unit in the open with side A's first
    # four units on its four neighbours; the rest deploy as usual.
    placed = {0: [], 1: []}
    if siege:
        cx, cy = rng.pick(_siege_cells(gamemap))
        placed[1] = [(rng.pick(["pikeman", "swordsman"]), cx, cy)]
        placed[0] = [(rng.pick(theme), cx + dx, cy + dy) for dx, dy in DIRS]
    for side, cols in ((0, (0, 1, 2)), (1, (W - 1, W - 2, W - 3))):
        last = None
        for num in range(1, max(rng.rint(*cfg.units), len(placed[side])) + 1):
            if num <= len(placed[side]):
                typ, x, y = placed[side][num - 1]
                used.add((x, y))
                deploy.append(("AB"[side] + str(SPARSE_NUMBERS[num] if sparse else num), typ, x, y))
                continue
            pair = last is not None and last[0] == "pikeman" and rng.pct(70)
            typ = "pikeman" if pair else rng.pick(theme)
            cls = UNIT_TABLE[typ]["class"]
            cells = [(x, y) for x in cols for y in range(H) if (x, y) not in used and TERRAIN_TABLE[rows[y][x]]["cost"][cls] is not None]
            if pair:
                close = [c for c in cells if abs(c[0] - last[1]) + abs(c[1] - last[2]) == 1]
                cells = close or cells
            x, y = rng.pick(cells)
            used.add((x, y))
            deploy.append(("AB"[side] + str(SPARSE_NUMBERS[num] if sparse else num), typ, x, y))
            last = (typ, x, y) if not pair else None
    match = {"id": mid, "v": v, "rules": rules, "map": mapname, "seed": seed, "players": [p0["id"], p1["id"]], "deploy": deploy, "turns": []}
    sim = Sim(match, gamemap)
    lines = []
    for uid, typ, x, y in deploy:
        lines.append("U %s %s %d %d" % (uid, typ, x, H - 1 - y if v == 2 else y))
    noise = cfg.noise
    period = rng.pick(cfg.kf)
    tamper = rng.pct(cfg.tamper)
    lagged = noise and rng.pct(45)
    deaths = []
    for n in range(1, cfg.cap + 1):
        lines.append("T %d" % n)
        kf = None
        if n % period == 0:
            rr, cp, us = sim.snapshot()
            cp = list(cp)
            us = [list(t) for t in us]
            if tamper and rng.pct(30):
                k = rng.rint(0, 2)
                if k == 0:
                    t = rng.pick(us)
                    t[3] = max(1, t[3] - rng.rint(1, 2)) if t[3] > 1 else t[3] + 1
                elif k == 1:
                    cp[rng.rint(0, 1)] += 1
                else:
                    rr ^= 1 << rng.rint(0, 31)
            kline = "K %d rng=%08x cp=%d,%d" % (n, rr, cp[0], cp[1]) + "".join(
                " %s@%d,%d,%d,%d,%d" % (t[0], t[1], H - 1 - t[2] if v == 2 else t[2], t[3], t[4], t[5]) for t in us)
            lines.append(kline)
            kf = parse_keyframe(kline.split(" "))
            sim.keyframe(kf)
        sim.begin(n)
        block = []
        for u in sim.living():
            od = _plan(sim, rng, u)
            if siege and u.side == 1 and u.num > 1 and rng.pct(50):
                od = ("READY", None)  # the rest of side B waits armed
            if noise and od[0] == "MOVE" and rng.pct(4 * noise):
                # a detour whose first waypoint is taken or impassable: the walk
                # stops there, so the rest of the path is never walked
                stuck = [(u.x + dx, u.y + dy) for dx, dy in DIRS
                         if 0 <= u.x + dx < W and 0 <= u.y + dy < H and (u.x + dx, u.y + dy) != od[1][0]
                         and ((u.x + dx, u.y + dy) in sim.occ or sim.step_cost(u, u.x + dx, u.y + dy) is None)]
                if stuck:
                    od = ("MOVE", [rng.pick(stuck)] + od[1])
            entry = []
            if lagged and rng.pct(8 * noise // 2):
                entry.append(_render(sim, u.uid, _alt(sim, rng, u)))
            if lagged and rng.pct(4 * noise):
                entry.append(_render(sim, u.uid, od, 1))
            else:
                entry.append(_render(sim, u.uid, od))
                if lagged and rng.pct(3 * noise):
                    entry.append(_render(sim, u.uid, _alt(sim, rng, u), 1))
            if lagged and rng.pct(3 * noise):
                entry.append(_render(sim, u.uid, _alt(sim, rng, u), rng.rint(2, 4)))
            block.append(entry)
        if noise:
            if deaths and rng.pct(15):
                block.append(["O %s HOLD" % rng.pick(deaths)])
            if rng.pct(6 * noise):
                side = rng.pick("AB")
                block.append(["O %s%d %s" % (side, rng.rint(13, 19), rng.pick(["HOLD", "READY"]))])
            if rng.pct(4 * noise):
                u = rng.pick(sim.living())
                block.append(["O %s ATTACK %s%d" % (u.uid, "B" if u.side == 0 else "A", rng.rint(13, 19))])
            if rng.pct(5 * noise):
                u = rng.pick(sim.living())
                block.append([rng.pick(MALFORMED).format(u=u.uid, x=u.x, y=u.y)])
            if rng.pct(10):
                block.append(["# turn %d note: %s" % (n, rng.pick(["spectator lag", "replay ok", "casting delay", "clock sync"]))])
            if rng.pct(6):
                block.append([""])
        order_of = list(range(len(block)))
        for i in range(len(order_of) - 1, 0, -1):
            j = rng.next() % (i + 1)
            order_of[i], order_of[j] = order_of[j], order_of[i]
        flat = []
        for i in order_of:
            flat.extend(block[i])
        lines.extend(flat)
        parsed = parse_log("MATCH x v=1 rules=1 map=m seed=00000000 p0=a p1=b turns=1\n" + "\n".join(
            "U %s %s 0 0" % (d[0], d[1]) for d in deploy) + "\nT 1\n" + "\n".join(flat) + "\nEND x\n")
        orders = parsed["matches"][0]["turns"][0]["orders"]
        before = set(sim.units)
        sim.play(n, orders)
        deaths.extend(sorted(before - set(sim.units)))
        match["turns"].append({"n": n, "kf": kf, "orders": orders})
        sides = {u.side for u in sim.units.values()}
        if len(sides) < 2:
            break
    head = "MATCH %s v=%d rules=%d map=%s seed=%08x p0=%s p1=%s turns=%d" % (mid, v, rules, mapname, seed, p0["id"], p1["id"], len(match["turns"]))
    if noise and not siege and int(mid[-1], 16) % 2 == 0:
        first_turn = next(i for i, line in enumerate(lines) if line.startswith("T "))
        lines.insert(first_turn + 1, "R 1 999999 0 DROP")
        if int(mid[-1], 16) == 0:
            lines.insert(0, "# Turn labels were relabelled; absolute keyframes were retained.")
            lines = [(line.split(" ", 1)[0] + " " + str(2 * int(line.split(" ")[1]) - 1)
                      + (" " + " ".join(line.split(" ")[2:]) if line.startswith("K ") else ""))
                     if line.startswith(("T ", "K ")) else line for line in lines]
        lines.extend(correction_tail(match, rng))
    return [head] + lines + ["END %s" % mid]


def correction_tail(match: dict, rng: Rng) -> list[str]:
    slots = [(ti, si, od) for ti, t in enumerate(match["turns"], 1)
             for si, od in enumerate(t["orders"], 1)]
    if not slots:
        return []
    selected = []
    for kind in ("MOVE", "ATTACK", "READY"):
        candidates = [entry for entry in slots if entry[2][2] == kind and entry not in selected]
        if candidates:
            selected.append(rng.pick(candidates))
    selected.append(rng.pick(slots))
    seen = set()
    lines = []
    for ti, si, od in selected:
        if (ti, si) in seen:
            continue
        seen.add((ti, si))
        lag, uid, kind, arg = od
        prefix = "O" if lag == 0 else "O~" + str(lag)
        payload = prefix + " " + uid + " " + kind
        if kind == "MOVE":
            payload += " " + " ".join(str(x) + "," + str(y) for x, y in arg)
        elif kind == "ATTACK":
            payload += " " + arg
        address = f"R {ti} {si} "
        lines.extend([address + "0 DROP", address + "0 O A1 HOLD",
                      address + "0 O A999 ATTACK B999", address + "1 DROP",
                      address + "2 " + payload, address + "3 " + payload])
        if rng.pct(50):
            replacement_uid = rng.pick(match["deploy"])[0]
            lines.append(address + "4 O~2 " + replacement_uid + " READY")
    lines.extend(["R 0 1 0 DROP", "R 1 999999 0 DROP", "R 1 1 00 DROP",
                  "R 1 1 0 O A1 SPRINT", "T 999", "O A1 HOLD"])
    return lines


def gen_log(seed: int, name: str, maps: dict, players: list) -> str:
    cfg = TIERS[name]
    rng = Rng(seed ^ (sum(ord(c) * 131 ** i for i, c in enumerate(name)) & M64))
    names = sorted(maps)
    out = ["# Brassmoor Skirmish replay export, scenario %s" % name, "# lines starting with # are comments", ""]
    for i in range(cfg.matches):
        mid = "%s-%06x" % (name[:2], rng.next() & 0xFFFFFF)
        mapname = rng.pick(names)
        out.extend(gen_match(rng, cfg, mid, mapname, maps[mapname], players))
        out.append("")
    if cfg.noise > 0:
        # siege matches, from their own stream so the matches above stay as they are
        camp = Rng(rng.next() ^ 0x5E1E6E)
        open_maps = [m for m in names if _siege_cells(maps[m])]
        # a siege match is kept only when it is one of the first SIEGE_MATCHES
        # whose digests change under the flank cap or under the reaction order
        need = {rule: SIEGE_MATCHES for rule in SIEGE_RULES}
        for _ in range(400):
            if not any(need.values()):
                break
            mid = "%s-%06x" % (name[:2], camp.next() & 0xFFFFFF)
            mapname = camp.pick(open_maps)
            body = gen_match(camp, cfg, mid, mapname, maps[mapname], players, siege=True)
            m = parse_log("\n".join(body) + "\n")["matches"][0]
            true = run_match(m, maps)["digests"]
            hit = [r for r in SIEGE_RULES if need[r] and run_match(m, maps, frozenset({r}))["digests"] != true]
            if hit:
                for r in hit:
                    need[r] -= 1
                out.extend(body)
                out.append("")
        # a last match that is never closed: an END naming another id is malformed
        # and leaves it open, so it is dropped while its lines still count
        tail = Rng(rng.next() ^ 0xC105ED)
        mid = "%s-%06x" % (name[:2], tail.next() & 0xFFFFFF)
        mapname = tail.pick(names)
        body = gen_match(tail, cfg, mid, mapname, maps[mapname], players)[:-1]
        out.extend(body + ["END %s-%06x" % (name[:2], (int(mid[3:], 16) + 1) & 0xFFFFFF)])
    return "\n".join(out) + "\n"


def build_corpus(seed_for: dict) -> dict:
    """Return filename -> text for the static tables plus five replay logs."""
    files = table_texts()
    maps = parse_maps(files["maps.txt"])
    players = players_list(files["players.json"])
    for name in SCENARIOS:
        files["replays_%s.log" % name] = gen_log(seed_for[name], name, maps, players)
    return files


def tier_seeds(base: int, visible_seed: int) -> dict:
    out = {"visible": visible_seed}
    for i, name in enumerate(SCENARIOS[1:]):
        out[name] = (base * (i + 3) + 0x9E37) & M64
    return out


# ---------------------------------------------------------------- reference reports

def ladder(matches_out: list, players: list) -> list:
    rating = {p["id"]: p["rating"] for p in players}
    rec = {}
    for m in matches_out:
        a, b = m["players"]
        for p in (a, b):
            rec.setdefault(p, [0, 0, 0, 0])
            rec[p][0] += 1
        w = m["winner"]
        if w is None:
            rec[a][2] += 1
            rec[b][2] += 1
            hi, lo = (a, b) if rating[a] >= rating[b] else (b, a)
            gift = min(8, (rating[hi] - rating[lo]) // 50)
            rating[hi] -= gift
            rating[lo] += gift
        else:
            loser = b if w == a else a
            rec[w][1] += 1
            rec[loser][3] += 1
            delta = min(28, max(4, 16 + (rating[loser] - rating[w]) // 25))
            rating[w] += delta
            rating[loser] -= delta
    rows = [{"player": p, "rating": rating[p], "played": r[0], "won": r[1], "drawn": r[2], "lost": r[3]} for p, r in rec.items()]
    rows.sort(key=lambda r: (-r["rating"], r["player"]))
    return rows


def reference(files: dict) -> SimpleNamespace:
    """Full reference reports for a corpus plus the parsed matches."""
    maps = parse_maps(files["maps.txt"])
    players = players_list(files["players.json"])
    reports = {"perf": {}, "bottle": {}, "quality": {}}
    deployed = {t: 0 for t in UNIT_TABLE}
    dealt = {t: 0 for t in UNIT_TABLE}
    kills = {t: 0 for t in UNIT_TABLE}
    parsed_all, runs_all = {}, {}
    for name in SCENARIOS:
        parsed = parse_log(files["replays_%s.log" % name])
        parsed_all[name] = parsed
        mouts, draws, divs = [], {"attack": 0, "damage": 0, "reaction": 0}, []
        edits = dict(applied=0, stale=0, unknown=0)
        late = sup = turns = 0
        runs = []
        for m in parsed["matches"]:
            res = revision_replay(m, maps)
            runs.append(res)
            sim = res["sim"]
            for key in edits:
                edits[key] += res["edit_counts"][key]
            for t in res["resolved"]["turns"]:
                _, a, b = effective_orders(t["orders"], False)
                late += a
                sup += b
            turns += len(m["turns"])
            for k in draws:
                draws[k] += sim.draws[k]
            for t in UNIT_TABLE:
                dealt[t] += sim.dealt[t]
                kills[t] += sim.kills[t]
            for d in m["deploy"]:
                deployed[d[1]] += 1
            divs.extend([m["id"], n] for n in res["divergences"])
            living = sim.living()
            score = [sim.cp[s] * 5 + sum(u.spec["cost"] for u in living if u.side == s) for s in (0, 1)]
            sides = {u.side for u in living}
            if len(sides) == 1:
                win = m["players"][sides.pop()]
            elif not sides or score[0] == score[1]:
                win = None
            else:
                win = m["players"][0 if score[0] > score[1] else 1]
            mouts.append({"id": m["id"], "map": m["map"], "players": list(m["players"]), "turns": len(m["turns"]),
                          "digests": res["digests"], "control": list(sim.cp),
                          "survivors": [[u.uid, u.x, u.y, u.hp] for u in living], "score": score, "winner": win,
                          "amendments": res["audit"]})
        runs_all[name] = runs
        reports["scenario_%s.json" % name] = {"scenario": name, "source": "replays_%s.log" % name, "matches": mouts, "standings": ladder(mouts, players)}
        c = parsed["counters"]
        reports["perf"][name] = {"matches": len(parsed["matches"]), "turns": turns, "orders_total": c["orders_total"], "orders_late": late, "orders_superseded": sup}
        dom = sorted(draws, key=lambda k: (-draws[k], k))[0]
        reports["bottle"][name] = {"draws_by_phase": draws, "dominant_phase": dom}
        reports["quality"][name] = {"malformed_lines": c["malformed_lines"], "unknown_unit_orders": c["unknown_unit_orders"], "divergences": divs,
                                  "amendments": edits}
    units = {}
    for t, spec in UNIT_TABLE.items():
        pm = dealt[t] * 1000 // (deployed[t] * spec["cost"]) if deployed[t] else 0
        verdict = "nerf" if pm >= RULESETS["balance"]["nerf_at"] else ("buff" if pm <= RULESETS["balance"]["buff_at"] else "hold")
        units[t] = {"deployed": deployed[t], "damage_dealt": dealt[t], "kills": kills[t], "per_cost_permille": pm, "verdict": verdict}
    return SimpleNamespace(
        files={**{"scenario_%s.json" % n: reports["scenario_%s.json" % n] for n in SCENARIOS},
               "perf_report.json": {"scenarios": reports["perf"]},
               "bottleneck_analysis.json": {"scenarios": reports["bottle"]},
               "recommendations.json": {"units": units},
               "data_quality.json": {"scenarios": reports["quality"]}},
        parsed=parsed_all, maps=maps, players=players, runs=runs_all,
    )


def sensitivity(ref: SimpleNamespace) -> dict:
    """(scenario, match id) -> list of lever sets, one per digest index."""
    out = {}
    for name in SCENARIOS:
        for m, base in zip(ref.parsed[name]["matches"], ref.runs[name]):
            if m.get("edits"):
                continue
            sens = local_sensitivity(m, ref.maps)
            assert len(sens) == len(base["digests"])
            out[(name, m["id"])] = sens
    return out


# ---------------------------------------------------------------- running the submission

_LOCK = threading.Lock()
_CACHE: dict = {}
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", "--no-new-privs"]


def _untrusted(cmd: list) -> list:
    if os.name == "posix" and os.geteuid() == 0 and shutil.which("setpriv"):
        return [*_SETPRIV, *cmd]
    return cmd


def _write_dir(root: Path, files: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o755)
    for name, text in files.items():
        p = root / name
        p.write_text(text, encoding="utf-8")
        os.chmod(p, 0o644)


_STRAYS: list = []      # paths a finished grading run left outside its out_dir
_BASELINE: set = set()  # paths the dropped uid owned before the first run


def _dropped_uid() -> int | None:
    """uid the submission runs under, or None when no privilege drop happens."""
    if not _untrusted([]):
        return None
    try:
        import pwd
        return pwd.getpwnam("nobody").pw_uid
    except (ImportError, KeyError):
        return None


def _owned_paths(uid: int, keep: str | None) -> set:
    """Every path owned by `uid` outside `keep` (proc, sys and dev skipped, /dev/shm kept)."""
    found = set()
    for top in ("/", "/dev/shm"):
        for root, dirs, files in os.walk(top):
            if root == "/":
                dirs[:] = [d for d in dirs if d not in ("proc", "sys", "dev")]
            descend = []
            for name in dirs + files:
                p = os.path.join(root, name)
                if keep is not None and (p == keep or p.startswith(keep + os.sep)):
                    continue
                try:
                    owner = os.lstat(p).st_uid
                except OSError:
                    continue
                if owner == uid:
                    found.add(p)
                elif name in dirs:
                    descend.append(name)
            dirs[:] = descend
    return found


def _reap(uid: int) -> None:
    """Kill every live process of `uid`, so nothing the run started outlives it."""
    for _ in range(50):
        alive = 0
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                status = Path("/proc", pid, "status").read_text()
            except OSError:
                continue
            fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
            if fields.get("Uid", "").split()[:1] == [str(uid)] and not fields.get("State", "").strip().startswith("Z"):
                alive += 1
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except OSError:
                    pass
        if not alive:
            return


def _seal(out_dir: Path) -> None:
    """Hand a finished out_dir to root and close it, so later runs cannot read it."""
    if not out_dir.is_dir() or out_dir.is_symlink():
        return
    for root, dirs, files in os.walk(out_dir):
        for name in dirs + files:
            os.lchown(os.path.join(root, name), 0, 0)
    os.lchown(out_dir, 0, 0)
    os.chmod(out_dir, 0o700)


def _contain(out_dir: Path, finished: bool) -> None:
    """After a run: stop its processes, record and delete what it left outside
    out_dir (so no later run can reuse it), then seal out_dir."""
    uid = _dropped_uid()
    if uid is None:
        return
    _reap(uid)
    for p in sorted(_owned_paths(uid, str(out_dir)) - _BASELINE):
        if finished:
            _STRAYS.append(p)
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.unlink(p)
        except OSError:
            pass
    _seal(out_dir)


def _run_program(code_dir: Path, data_dir: Path, out_dir: Path, hashseed: str, create: bool = True) -> dict | None:
    if create:
        out_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(out_dir, 0o777)
    else:
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(out_dir.parent, 0o777)
    program = code_dir / "optimize.py"
    os.chmod(program, 0o644)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONHASHSEED": hashseed, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "HOME": "/tmp"}
    proc = subprocess.Popen(_untrusted([sys.executable, "-s", "-P", str(program), str(data_dir), str(out_dir)]),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=str(code_dir), start_new_session=True)
    try:
        proc.wait(timeout=RUN_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        proc.wait()
        _contain(out_dir, finished=False)
        return None
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
    result = {}
    for name in ["scenario_%s.json" % n for n in SCENARIOS] + REPORTS:
        p = out_dir / name
        try:
            result[name] = p.read_bytes()
        except OSError:
            result[name] = None
    _contain(out_dir, finished=True)
    return result


def _same(a, b) -> bool:
    """Equality that also requires the same JSON types (1, 1.0 and true differ)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _decode(blob):
    if blob is None:
        return None
    try:
        return json.loads(blob.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _place_decoy(files: dict) -> bool:
    decoy = Path("/app/data")
    try:
        if not decoy.exists() and os.geteuid() == 0:
            _write_dir(decoy, files)
            return True
    except OSError:
        pass
    return False


def _ghost_orders(files: dict) -> dict:
    """Section 6.3 keyframe placement fixture for the evaluation corpus. In the
    four exports that use the full grammar, every third keyframe of a match
    without a correction tail is preceded by an order whose issuer is not
    deployed. That order is counted in unknown_unit_orders and discarded; it is
    not an accepted order of its block, so the keyframe after it is still
    accepted. Matches with R lines are left alone, so the recovery audit never
    pays again for a keyframe placement mistake."""
    out = dict(files)
    for name in SCENARIOS[1:]:
        lines = files["replays_%s.log" % name].split("\n")
        blocks, block = [], []
        for line in lines:
            if line.startswith("MATCH ") and block:
                blocks.append(block)
                block = []
            block.append(line)
        blocks.append(block)
        fixed = []
        seen = 0
        for block in blocks:
            tail = any(line.startswith("R ") for line in block)
            for line in block:
                if line.startswith("K ") and not tail:
                    if seen % 3 == 0:
                        fixed.append("O %s%d %s" % ("AB"[seen % 2], 13 + seen % 7, ("HOLD", "READY")[seen // 3 % 2]))
                    seen += 1
                fixed.append(line)
        out["replays_%s.log" % name] = "\n".join(fixed)
    return out


TIE_SHAPES = {
    "attack": lambda d: d["attack"] == d["damage"] > d["reaction"],
    "damage": lambda d: d["damage"] == d["reaction"] > d["attack"],
}


def _tie_fixture(files: dict, ref: SimpleNamespace, shape: str) -> tuple[str, dict]:
    """A replay export whose two highest draw totals tie, so the section 13.3
    alphabetical tie break decides dominant_phase. Shape "attack" ties attack
    and damage above reaction; shape "damage" ties damage and reaction above
    attack, so a rule that always prefers attack, or takes the last of the
    tied phases, is caught as well. It holds every closed evaluation match
    whose own final draws tie that way, copied line for line, and its
    expected bottleneck entry is recomputed from the new log rather than
    assumed."""
    blocks = []
    for name in SCENARIOS:
        lines = files["replays_%s.log" % name].split("\n")
        for m, res in zip(ref.parsed[name]["matches"], ref.runs[name]):
            if not TIE_SHAPES[shape](res["sim"].draws):
                continue
            start = next(i for i, ln in enumerate(lines) if ln.strip().split(" ")[:2] == ["MATCH", m["id"]])
            end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "END " + m["id"])
            blocks.extend(lines[start:end + 1])
    text = "\n".join(blocks) + "\n"
    maps = parse_maps(files["maps.txt"])
    draws = {"attack": 0, "damage": 0, "reaction": 0}
    for m in parse_log(text)["matches"]:
        sim = revision_replay(m, maps)["sim"]
        for k in draws:
            draws[k] += sim.draws[k]
    dom = sorted(draws, key=lambda k: (-draws[k], k))[0]
    if not blocks or not TIE_SHAPES[shape](draws) or dom != shape:
        raise RuntimeError("tie fixture %s does not hold a tie" % shape)
    return text, {"draws_by_phase": draws, "dominant_phase": dom}


def _state() -> SimpleNamespace:
    """Build the reference corpora and run the submission once. A failure is
    cached as well, so every later check fails closed at once instead of
    rebuilding the corpora and rerunning the submission."""
    with _LOCK:
        if "state" in _CACHE:
            return _CACHE["state"]
        if "error" in _CACHE:
            raise RuntimeError("grading state unavailable") from _CACHE["error"]
        try:
            st = _build_state()
        except Exception as exc:
            _CACHE["error"] = exc
            raise
        _CACHE["state"] = st
        return st


def _build_state() -> SimpleNamespace:
    st = SimpleNamespace()
    shipped = build_corpus(tier_seeds(CHALLENGE_SEED, SAMPLE_SEED))
    st.shipped_ref = reference(shipped)
    st.shipped_ids = {m["id"] for n in SCENARIOS for m in st.shipped_ref.files["scenario_%s.json" % n]["matches"]}
    decoy = build_corpus(tier_seeds(DECOY_SEED, DECOY_SEED ^ 0xA5A5))
    st.decoy_ids = {mid for n in SCENARIOS for mid in _ids(decoy["replays_%s.log" % n])}
    evalc = _ghost_orders(build_corpus(tier_seeds(EVAL_SEED, EVAL_SEED ^ 0x5A5A)))
    st.eval_ref = reference(evalc)
    st.sens = sensitivity(st.eval_ref)
    st.tie_log, st.tie_bottle = _tie_fixture(evalc, st.eval_ref, "attack")
    st.tie2_log, st.tie2_bottle = _tie_fixture(evalc, st.eval_ref, "damage")
    st.runs = SimpleNamespace()
    if SUBMISSION.is_file():
        work = Path(tempfile.mkdtemp(prefix="brassmoor-"))
        os.chmod(work, 0o755)
        code = work / "code"
        code.mkdir()
        os.chmod(code, 0o755)
        shutil.copyfile(SUBMISSION, code / "optimize.py")
        os.chmod(code / "optimize.py", 0o644)
        data = work / "eval"
        _write_dir(data, evalc)
        st.decoy_placed = _place_decoy(decoy)
        uid = _dropped_uid()
        if uid is not None:
            _BASELINE.update(_owned_paths(uid, None))
        st.runs.main = _run_program(code, data, work / "out0", "0")
        twin = dict(evalc)
        twin["replays_steady.log"] = evalc["replays_peak.log"]
        twin["replays_burst.log"] = st.tie_log
        twin["replays_latency.log"] = st.tie2_log
        _write_dir(work / "twin", twin)
        st.runs.twin = _run_program(code, work / "twin", work / "out_twin", "0")
        st.runs.h1 = _run_program(code, data, work / "out1", "1")
        st.runs.h2 = _run_program(code, data, work / "out2", "2")
        _write_dir(work / "shipped", shipped)
        st.runs.fresh = _run_program(code, work / "shipped", work / "fresh" / "out", "0", create=False)
        st.twin_ids = [m["id"] for m in parse_log(evalc["replays_peak.log"])["matches"]]
        st.strays = list(_STRAYS)
    return st


def st_twin_ids() -> list:
    return getattr(_state(), "twin_ids", None) or []


def _ids(log: str) -> list:
    return [m["id"] for m in parse_log(log)["matches"]]


def _agent_eval(name: str):
    run = getattr(_state().runs, "main", None)
    if not run:
        return None
    return _decode(run.get(name))


def _agent_matches(st: SimpleNamespace) -> dict:
    out = {}
    for n in SCENARIOS:
        doc = _agent_eval("scenario_%s.json" % n)
        if isinstance(doc, dict) and isinstance(doc.get("matches"), list):
            for m in doc["matches"]:
                if isinstance(m, dict) and isinstance(m.get("id"), str):
                    out[(n, m["id"])] = m
    return out


COMBAT = "core_combat"
FLOW = "core_flow"
BASE = "base"


VARIANT_RULE = {v: r for r, vs in ALL_VARIANTS.items() for v in vs}


def _group(variant: str) -> str:
    rule = VARIANT_RULE[variant]
    return COMBAT if rule in COMBAT_VARIANTS else FLOW if rule in FLOW_VARIANTS else BASE if rule in BASE_VARIANTS else rule


NO_RULE = ""
POOL_PARTS = {
    BASE: [[NO_RULE], BASE_VARIANTS["L3"]],
    "L6": [["L6"], ["L7a", "L7b"]],
    "L9": [["L9"], ["L10"]],
    "L14": [["L14", "C8"], ["L15a", "L15b", "C12", "C21", "C26"]],
    COMBAT: [[v for r, vs in COMBAT_VARIANTS.items() if r != "L12" for v in vs], ["L12"]],
    FLOW: [[v for r, vs in FLOW_VARIANTS.items() if r != "L8" for v in vs], ["L8"]],
}
# Pools whose deployment digest alone could carry them: each also needs a
# right graded digest after at least one replayed turn that the rule touches.
TURN_PARTS = {
    "L1": ["L1"],
}


def _ledger(st) -> SimpleNamespace:
    """Walk every evaluation digest the agent reached from a true state (the
    deployment digest, or any turn whose previous agent digest is right).
    A right digest counts as evidence for the rules that touch that turn. A
    rule variant counts as the agent's reading when it reproduces more of the
    agent's digests on the turns it changes than the agent gets right there;
    the rule behind it is charged. Every other wrong digest is charged to the
    baseline, so no wrong digest goes unpaid and a rule is never charged for
    a digest it only matches by chance."""
    if getattr(st, "ledger", None) is not None:
        return st.ledger
    mine = _agent_matches(st)
    right, seen, seen_turn, repro, wrong = {}, {}, {}, {}, []
    for n in SCENARIOS:
        for m in st.eval_ref.files["scenario_%s.json" % n]["matches"]:
            if (n, m["id"]) not in st.sens:
                continue
            alt = st.sens[(n, m["id"])]
            got = mine.get((n, m["id"]))
            dig = got.get("digests") if got else None
            if not isinstance(dig, list):
                dig = []
            for i, true in enumerate(m["digests"]):
                if i > 0 and not (i - 1 < len(dig) and dig[i - 1] == m["digests"][i - 1]):
                    continue
                d = dig[i] if i < len(dig) else None
                if d == true:
                    for r in {_group(v) for v in alt[i]} or {BASE}:
                        right[r] = right.get(r, 0) + 1
                    for v in alt[i] or [NO_RULE]:
                        seen[v] = seen.get(v, 0) + 1
                        if i > 0:
                            seen_turn[v] = seen_turn.get(v, 0) + 1
                    continue
                hit = {v for v, alt_d in alt[i].items() if d == alt_d}
                for v in hit:
                    repro[v] = repro.get(v, 0) + 1
                wrong.append(hit)
    read = {v for v, k in repro.items() if k > seen.get(v, 0)}
    charged = {_group(v) for v in read}
    if any(not hit & read for hit in wrong):
        charged.add(BASE)
    st.ledger = SimpleNamespace(right=right, seen=seen, seen_turn=seen_turn, charged=charged)
    return st.ledger


def _pool_ok(rule: str) -> bool:
    """No graded digest is charged to `rule`, at least one graded digest that
    `rule` touches is right, and for a pool listed in POOL_PARTS every clause
    of the property has at least one right graded digest it touches. A pool
    listed in TURN_PARTS also needs a right graded digest it touches after a
    replayed turn, not only the deployment digest."""
    led = _ledger(_state())
    if rule in led.charged or led.right.get(rule, 0) <= 0:
        return False
    if rule in TURN_PARTS and not any(led.seen_turn.get(v, 0) > 0 for v in TURN_PARTS[rule]):
        return False
    return all(any(led.seen.get(v, 0) > 0 for v in part) for part in POOL_PARTS.get(rule, []))


def _lever(name: str) -> bool:
    try:
        return _pool_ok(name)
    except Exception:
        return False


def _match_divergences(doc, name: str, mid: str):
    """Turn numbers listed for one match in a data_quality document, or None."""
    rows = doc["scenarios"][name]["divergences"]
    if not isinstance(rows, list):
        return None
    return [r[1] for r in rows if isinstance(r, list) and len(r) == 2 and r[0] == mid]


def _audit_fields(keys: tuple[str, ...]) -> bool:
    """The last accepted entry's `after` fingerprint is a hash of the final
    digest vector, and its `divergences_after` is the match's final divergence
    list. Both final states are already graded (eval_recovered_history and
    lever_keyframe_divergences), so those two values are compared only where
    the agent got that final state right: a wrong final state is paid once,
    and a right final state still needs a matching audit entry."""
    try:
        st = _state()
        mine = _agent_matches(st)
        dq = _agent_eval("data_quality.json")
        ref_dq = st.eval_ref.files["data_quality.json"]
        for name in SCENARIOS:
            for row in st.eval_ref.files["scenario_%s.json" % name]["matches"]:
                got_match = mine.get((name, row["id"]), {})
                audits = got_match.get("amendments")
                if not isinstance(audits, list) or len(audits) != len(row["amendments"]):
                    return False
                skip = set()
                if row["amendments"]:
                    if not _same(got_match.get("digests"), row["digests"]):
                        skip.add("after")
                    try:
                        final_ok = _same(_match_divergences(dq, name, row["id"]),
                                         _match_divergences(ref_dq, name, row["id"]))
                    except Exception:
                        final_ok = False
                    if not final_ok:
                        skip.add("divergences_after")
                last = len(audits) - 1
                for i, (got, want) in enumerate(zip(audits, row["amendments"])):
                    if not isinstance(got, dict) or got.keys() != want.keys():
                        return False
                    for key in keys:
                        if i == last and key in skip:
                            continue
                        if not _same(got[key], want[key]):
                            return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- checks


@criterion(description="Each of the nine reports under /app/out is the submitted engine's own output for the shipped data: run on a rebuilt copy of the shipped exports into an out_dir that does not exist yet, the engine writes the same JSON value for every report, with its documented top level section non-empty.")
def shipped_outputs_present(workspace) -> bool:
    try:
        run = getattr(_state().runs, "fresh", None)
        if not run:
            return False
        for path, key in SHIPPED_REPORTS.items():
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or key not in doc or not doc[key]:
                return False
            if not _same(doc, _decode(run.get(Path(path).name))):
                return False
        return True
    except Exception:
        return False


@criterion(description="Each evaluation scenario report has the documented keys, scenario label, source file and match count, and every match row has the reference keys, id, map, players and turns in file order.")
def eval_match_metadata(workspace) -> bool:
    try:
        st = _state()
        run = getattr(st.runs, "main", None)
        if not run:
            return False
        for n in SCENARIOS:
            doc = _decode(run.get("scenario_%s.json" % n))
            expected = st.eval_ref.files["scenario_%s.json" % n]
            if not isinstance(doc, dict) or doc.keys() != expected.keys():
                return False
            if not _same(doc["scenario"], n) or not _same(doc["source"], expected["source"]):
                return False
            if not isinstance(doc["matches"], list) or len(doc["matches"]) != len(expected["matches"]):
                return False
            for got, want in zip(doc["matches"], expected["matches"]):
                if not isinstance(got, dict) or got.keys() != want.keys():
                    return False
                if any(not _same(got[key], want[key]) for key in ("id", "map", "players", "turns")):
                    return False
        return True
    except Exception:
        return False


@criterion(description="Every amended evaluation match reports the final corrected digest vector, after all applied revisions, rather than its provisional history.")
def eval_recovered_history(workspace) -> bool:
    try:
        st = _state()
        mine = _agent_matches(st)
        hits = 0
        for n in SCENARIOS:
            for row in st.eval_ref.files["scenario_%s.json" % n]["matches"]:
                if row["amendments"]:
                    hits += 1
                    if not _same(mine.get((n, row["id"]), {}).get("digests"), row["digests"]):
                        return False
        return hits > 0
    except Exception:
        return False


@criterion(description="Every evaluation audit has the exact accepted entry sequence, immutable turn and slot addresses and revision numbers, including applied no-ops and restored tombstones.")
def eval_revision_addresses(workspace) -> bool:
    return _audit_fields(("turn", "slot", "revision"))


@criterion(description="Every accepted evaluation revision reports the exact before and after full-history fingerprints, not just a hash of the final state; the last after fingerprint is compared where the final digest vector is right.")
def eval_revision_fingerprints(workspace) -> bool:
    return _audit_fields(("before", "after"))


@criterion(description="Every accepted evaluation revision reports exactly the ascending ordinal digest indices changed by that revision.")
def eval_revision_changed_indices(workspace) -> bool:
    return _audit_fields(("changed",))


@criterion(description="Every accepted evaluation revision reports exact signed full-history draw deltas in the attack, damage and reaction phases, including rejected samples.")
def eval_revision_draw_credits(workspace) -> bool:
    return _audit_fields(("draws_delta",))


@criterion(description="Every accepted evaluation revision reports exact signed direct damage deltas for every unit type, retaining prefix credits when later keyframes converge.")
def eval_revision_damage_credits(workspace) -> bool:
    return _audit_fields(("damage_delta",))


@criterion(description="Every accepted evaluation revision reports exact signed direct kill deltas for every unit type, excluding poison deaths and including keyframe resurrection effects.")
def eval_revision_kill_credits(workspace) -> bool:
    return _audit_fields(("kills_delta",))


@criterion(description="Every accepted evaluation revision reports exact full before and after keyframe divergence histories, with comparison before adoption and reseeding; the last after history is compared where the match's final divergences are right.")
def eval_revision_divergence_histories(workspace) -> bool:
    return _audit_fields(("divergences_before", "divergences_after"))


@criterion(description="Reached evaluation baseline digests and digests depending on absolute keyframe adoption agree with the reference.")
def eval_baseline_digests(workspace) -> bool:
    try:
        return _pool_ok(BASE)
    except Exception:
        return False


@criterion(description="The bottleneck_analysis.json draw counts and dominant phase equal the reference for every evaluation scenario and for twin exports whose two highest phase totals tie, attack with damage and damage with reaction, where the alphabetically first tied phase is dominant.")
def eval_bottleneck_analysis(workspace) -> bool:
    try:
        st = _state()
        if not _same(_agent_eval("bottleneck_analysis.json"), st.eval_ref.files["bottleneck_analysis.json"]):
            return False
        tie = _decode(st.runs.twin.get("bottleneck_analysis.json"))
        return (_same(tie["scenarios"]["burst"], st.tie_bottle)
                and _same(tie["scenarios"]["latency"], st.tie2_bottle))
    except Exception:
        return False


@criterion(description="The recommendations.json written for the evaluation run equals the reference unit totals and verdicts exactly.")
def eval_recommendations(workspace) -> bool:
    try:
        return _same(_agent_eval("recommendations.json"), _state().eval_ref.files["recommendations.json"])
    except Exception:
        return False


@criterion(description="For every evaluation scenario the malformed, unknown original order and applied, stale, unknown amendment counts equal the reference, including unknown-before-stale precedence.")
def eval_quality_counts(workspace) -> bool:
    try:
        doc = _agent_eval("data_quality.json")["scenarios"]
        ref = _state().eval_ref.files["data_quality.json"]["scenarios"]
        return all(_same(doc[n][key], ref[n][key]) for n in SCENARIOS
                   for key in ("malformed_lines", "unknown_unit_orders", "amendments"))
    except Exception:
        return False


@criterion(description="The perf_report.json written for the evaluation run equals the reference match, turn and order counters for every scenario.")
def eval_perf_counters(workspace) -> bool:
    try:
        return _same(_agent_eval("perf_report.json"), _state().eval_ref.files["perf_report.json"])
    except Exception:
        return False


@criterion(description="Digests are correct on evaluation turns whose state depends only on the bottom left origin of format 2 logs.")
def lever_format2_origin(workspace) -> bool:
    return _lever("L1")


@criterion(description="Digests are correct on evaluation turns whose state depends only on lag tagged orders, late orders and superseded orders.")
def lever_lagged_orders(workspace) -> bool:
    return _lever("L2")


@criterion(description="Each final data_quality divergence list exactly matches the corrected full-history keyframe comparisons in match and block order, for both rulesets.")
def lever_keyframe_divergences(workspace) -> bool:
    try:
        st = _state()
        doc = _agent_eval("data_quality.json")["scenarios"]
        want = st.eval_ref.files["data_quality.json"]["scenarios"]
        return all(_same(doc[n]["divergences"], want[n]["divergences"]) for n in SCENARIOS)
    except Exception:
        return False


@criterion(description="Digests are correct on evaluation turns whose state depends only on the rejection rule of the nine bit dice stream.")
def lever_dice_rejection(workspace) -> bool:
    return _lever("L4")


@criterion(description="Digests are correct on evaluation turns whose state depends only on the per turn reseed of ruleset 2.")
def lever_ruleset2_reseed(workspace) -> bool:
    return _lever("L5")


@criterion(description="Reached evaluation digests respect wounded initiative snapshots, alternating side priority and numeric unit tie breaks.")
def lever_initiative_order(workspace) -> bool:
    return _lever("L6")


@criterion(description="Reached evaluation digests respect class-specific terrain costs, zone of control stops and the skirmisher exemption.")
def lever_movement(workspace) -> bool:
    return _lever("L9")


@criterion(description="Digests are correct on evaluation turns whose state depends only on the pike shield wall bonus.")
def lever_shield_wall(workspace) -> bool:
    return _lever("L11")


@criterion(description="Digests are correct on evaluation turns whose state depends only on line of sight, the units that block it and the hill range bonus of the attacker's cell.")
def lever_line_of_sight(workspace) -> bool:
    return _lever("L13")


@criterion(description="Reached evaluation digests respect poison refresh and ticks, the corrected rout threshold and routed attack and defence effects.")
def lever_status_effects(workspace) -> bool:
    return _lever("L14")


@criterion(description="Digests are correct on evaluation turns whose state depends only on sole presence objective control over the cell and its four neighbours, scored after the poison tick.")
def lever_objective_control(workspace) -> bool:
    return _lever("L16")


@criterion(description="On evaluation matches whose full digest vector is correct, final control, survivors, score and winner equal the reference.")
def lever_final_result(workspace) -> bool:
    try:
        st = _state()
        mine = _agent_matches(st)
        hits = 0
        for n in SCENARIOS:
            for m in st.eval_ref.files["scenario_%s.json" % n]["matches"]:
                got = mine.get((n, m["id"]))
                # graded only where the agent's final state is right
                if not got or got.get("digests") != m["digests"]:
                    continue
                hits += 1
                if any(not _same(got.get(k), m[k]) for k in ("control", "survivors", "score", "winner")):
                    return False
        return hits > 0
    except Exception:
        return False


@criterion(description="Reached evaluation digests respect section 9 combat, including melee and pinned legality, capped flank, critical hits, defence, brace and advantage applied before armour.")
def lever_core_combat(workspace) -> bool:
    try:
        return _pool_ok(COMBAT)
    except Exception:
        return False


@criterion(description="Reached evaluation digests respect waypoint walking, roster order and READY reaction legality, execution order and once-per-turn limits.")
def lever_core_turn_flow(workspace) -> bool:
    try:
        return _pool_ok(FLOW)
    except Exception:
        return False


@criterion(description="Each evaluation standings list equals the ladder replayed from the true pairings in file order and the winners the program itself reported.")
def lever_ladder(workspace) -> bool:
    try:
        st = _state()
        players = st.eval_ref.players
        ids = {p["id"] for p in players}
        for n in SCENARIOS:
            doc = _agent_eval("scenario_%s.json" % n)
            ref = st.eval_ref.files["scenario_%s.json" % n]["matches"]
            if len(doc["matches"]) != len(ref):
                return False
            rows = []
            for got, m in zip(doc["matches"], ref):
                w = got.get("winner")
                if w is not None and (w not in ids or w not in m["players"]):
                    return False
                rows.append({"players": m["players"], "winner": w})
            if not _same(doc["standings"], ladder(rows, players)):
                return False
        return True
    except Exception:
        return False


@criterion(description="Cheat detector, true when the evaluation run reports match ids from the shipped corpus or the separately placed decoy rather than the requested data directory.")
def negative_wrong_corpus_ids(workspace) -> bool:
    try:
        st = _state()
        mine = _agent_matches(st)
        forbidden = st.shipped_ids | (st.decoy_ids if getattr(st, "decoy_placed", False) else set())
        # inverted polarity: True means a reported id came from a corpus the run was not given
        return any(mid in forbidden for _, mid in mine)
    except Exception:
        return False


@criterion(description="Cheat detector, true when identical log bytes stored as replays_peak.log and replays_steady.log produce different matches or standings.")
def negative_filename_dependent_behaviour(workspace) -> bool:
    try:
        runs = _state().runs
        base = getattr(runs, "main", None)
        if any(getattr(runs, k, None) is not None and getattr(runs, k) != base for k in ("h1", "h2")):
            return False
        run = getattr(runs, "twin", None)
        if not run:
            return False
        a, b = _decode(run["scenario_peak.json"]), _decode(run["scenario_steady.json"])
        if not isinstance(a, dict) or not isinstance(b, dict):
            return False
        ids = lambda d: sorted(str(m.get("id")) if isinstance(m, dict) else "" for m in d.get("matches") or [])
        # only a program that replayed both twin files can be filename dependent
        if ids(a) != sorted(st_twin_ids()) or ids(b) != sorted(st_twin_ids()):
            return False
        # inverted polarity: same bytes under two names must give the same content
        return not _same(a.get("matches"), b.get("matches")) or not _same(a.get("standings"), b.get("standings"))
    except Exception:
        return False


@criterion(description="Rule breach detector, true when optimize.py imports a top level module that is not part of the Python standard library, by an import statement or by a literal name passed to __import__ or import_module.")
def negative_engine_imports_non_stdlib(workspace) -> bool:
    try:
        tree = ast.parse(SUBMISSION.read_text(encoding="utf-8"))
    except Exception:
        return False
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str) and node.args[0].value:
            # dynamic imports by literal name: __import__("x"), importlib.import_module("x")
            fn = node.func
            called = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""
            if called in ("__import__", "import_module"):
                names.add(node.args[0].value.split(".")[0])
    # inverted polarity: any import outside the standard library breaks the stated rule
    return any(n not in sys.stdlib_module_names and n != "__future__" for n in names)


@criterion(description="Rule breach detector, true when a finished grading run of optimize.py leaves a file or directory behind outside the out_dir it was given.")
def negative_writes_outside_out_dir(workspace) -> bool:
    try:
        # inverted polarity: anything the engine's uid left outside <out_dir> breaks the stated write scope
        return bool(getattr(_state(), "strays", None))
    except Exception:
        return False


@criterion(description="Cheat detector, true when repeated evaluation runs with different hash seeds write different report bytes.")
def negative_nondeterministic_output(workspace) -> bool:
    try:
        runs = _state().runs
        base = getattr(runs, "main", None)
        if not base or base.get("scenario_visible.json") is None:
            return False
        # inverted polarity: identical input must give identical bytes on every run
        return any(getattr(runs, k, None) is not None and getattr(runs, k) != base for k in ("h1", "h2"))
    except Exception:
        return False


criteria.shipped_outputs_present(weight=1)
criteria.eval_match_metadata(weight=3)
criteria.eval_recovered_history(weight=5)
criteria.eval_revision_addresses(weight=5)
criteria.eval_revision_fingerprints(weight=5)
criteria.eval_revision_changed_indices(weight=5)
criteria.eval_revision_draw_credits(weight=5)
criteria.eval_revision_damage_credits(weight=5)
criteria.eval_revision_kill_credits(weight=5)
criteria.eval_revision_divergence_histories(weight=5)
criteria.eval_baseline_digests(weight=5)
criteria.eval_bottleneck_analysis(weight=3)
criteria.eval_recommendations(weight=3)
criteria.eval_quality_counts(weight=3)
criteria.eval_perf_counters(weight=3)
criteria.lever_format2_origin(weight=5)
criteria.lever_lagged_orders(weight=5)
criteria.lever_keyframe_divergences(weight=5)
criteria.lever_dice_rejection(weight=5)
criteria.lever_ruleset2_reseed(weight=5)
criteria.lever_initiative_order(weight=5)
criteria.lever_movement(weight=5)
criteria.lever_shield_wall(weight=5)
criteria.lever_line_of_sight(weight=5)
criteria.lever_status_effects(weight=5)
criteria.lever_objective_control(weight=5)
criteria.lever_final_result(weight=5)
criteria.lever_core_combat(weight=5)
criteria.lever_core_turn_flow(weight=5)
criteria.lever_ladder(weight=5)
criteria.negative_wrong_corpus_ids(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_engine_imports_non_stdlib(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_writes_outside_out_dir(weight=-3)
