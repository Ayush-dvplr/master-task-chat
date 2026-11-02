#!/usr/bin/env python3
"""Brassmoor Skirmish season 5 replay engine.

Usage:  python3 optimize.py <data_dir> <out_dir>

Reads the six tables and the five replay exports from <data_dir> and writes
the nine season 5 reports into <out_dir> (created when missing).  Follows the
season 5 rule book, the season 5 errata (E-1 .. E-7) and the JSON tables.
"""

import json
import os
import sys

SCENARIOS = ("visible", "peak", "steady", "burst", "latency")

PHASE_ATTACK = 0
PHASE_DAMAGE = 1
PHASE_REACTION = 2


# ---------------------------------------------------------------- utilities


def fnv1a(text):
    h = 0x811C9DC5
    for b in text.encode("ascii"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def fnv1a_hex(text):
    return "%08x" % fnv1a(text)


def is_whole(tok):
    """A whole number: decimal, no sign, no leading zeros ('0' is fine)."""
    if not tok or not tok.isdigit() or not tok.isascii():
        return False
    return len(tok) == 1 or tok[0] != "0"


def is_uid(tok):
    """Side letter A or B plus a unit number written without leading zeros."""
    if len(tok) < 2 or tok[0] not in "AB":
        return False
    return is_whole(tok[1:])


def is_hex8(tok):
    return len(tok) == 8 and all(c in "0123456789abcdef" for c in tok)


def unit_number(uid):
    return int(uid[1:])


# ------------------------------------------------------------------ tables


class Tables(object):
    def __init__(self, data_dir):
        with open(os.path.join(data_dir, "units.json")) as fh:
            self.units = json.load(fh)["units"]
        with open(os.path.join(data_dir, "terrain.json")) as fh:
            self.terrain = json.load(fh)["terrain"]
        with open(os.path.join(data_dir, "advantage.json")) as fh:
            adv = json.load(fh)
        self.adv_default = tuple(adv["default"])
        self.adv = {}
        for pair in adv.get("pairs", []):
            self.adv[(pair["attacker"], pair["defender"])] = (pair["num"], pair["den"])
        with open(os.path.join(data_dir, "rulesets.json")) as fh:
            self.rules = json.load(fh)
        with open(os.path.join(data_dir, "players.json")) as fh:
            self.players = json.load(fh)["players"]
        self.maps = {}
        name = None
        with open(os.path.join(data_dir, "maps.txt")) as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if parts[0] == "MAP":
                    name = parts[1]
                    self.maps[name] = {"w": int(parts[2]), "h": int(parts[3]),
                                       "rows": []}
                elif parts[0] == "ENDMAP":
                    name = None
                elif name is not None:
                    self.maps[name]["rows"].append(line)

    def map_of(self, name):
        return self.maps.get(name)


# ------------------------------------------------------------------- parsing


def parse_match_header(tokens):
    if len(tokens) != 9:
        return None
    fields = {}
    for tok in tokens[2:]:
        if "=" not in tok:
            return None
        key, value = tok.split("=", 1)
        if key in fields:
            return None
        fields[key] = value
    if set(fields) != {"v", "rules", "map", "seed", "p0", "p1", "turns"}:
        return None
    if fields["v"] not in ("1", "2") or fields["rules"] not in ("1", "2"):
        return None
    if not is_hex8(fields["seed"]):
        return None
    if not is_whole(fields["turns"]):
        return None
    return fields


def parse_keyframe_tokens(tokens):
    """Parse the fields of a K line -> dict, or None when it does not parse."""
    if len(tokens) < 4:
        return None
    if not is_whole(tokens[1]):
        return None
    if not tokens[2].startswith("rng=") or not is_hex8(tokens[2][4:]):
        return None
    if not tokens[3].startswith("cp="):
        return None
    cp = tokens[3][3:].split(",")
    if len(cp) != 2 or not is_whole(cp[0]) or not is_whole(cp[1]):
        return None
    units = []
    for ent in tokens[4:]:
        if "@" not in ent:
            return None
        uid, rest = ent.split("@", 1)
        if not is_uid(uid):
            return None
        fields = rest.split(",")
        if len(fields) != 5 or not all(is_whole(f) for f in fields):
            return None
        if fields[4] not in ("0", "1"):
            return None
        units.append((uid, int(fields[0]), int(fields[1]), int(fields[2]),
                     int(fields[3]), int(fields[4])))
    return {"turn": int(tokens[1]), "rng": int(tokens[2][4:], 16),
            "cp": (int(cp[0]), int(cp[1])), "units": units}


def parse_order_tokens(tokens):
    """Parse an O / O~<lag> line -> (lag, (uid, verb, arg)) or None."""
    head = tokens[0]
    if head == "O":
        lag = 0
    elif len(head) == 3 and head[0] == "O" and head[1] == "~":
        if head[2] not in "123456789":
            return None
        lag = int(head[2])
    else:
        return None
    if len(tokens) < 3:
        return None
    uid = tokens[1]
    if not is_uid(uid):
        return None
    verb = tokens[2]
    if verb in ("HOLD", "READY"):
        if len(tokens) != 3:
            return None
        return (lag, (uid, verb, None))
    if verb == "ATTACK":
        if len(tokens) != 4 or not is_uid(tokens[3]):
            return None
        return (lag, (uid, "ATTACK", tokens[3]))
    if verb == "MOVE":
        if len(tokens) < 4:
            return None
        pts = []
        for wp in tokens[3:]:
            parts = wp.split(",")
            if len(parts) != 2 or not is_whole(parts[0]) or not is_whole(parts[1]):
                return None
            pts.append((int(parts[0]), int(parts[1])))
        return (lag, (uid, "MOVE", pts))
    return None


def parse_r_line(tokens):
    """Parse an R line -> dict, or None when the line is malformed."""
    if len(tokens) < 5:
        return None
    if not (is_whole(tokens[1]) and is_whole(tokens[2]) and is_whole(tokens[3])):
        return None
    if int(tokens[1]) <= 0 or int(tokens[2]) <= 0:
        return None
    addr = (int(tokens[1]), int(tokens[2]))
    expected = int(tokens[3])
    if tokens[4] == "DROP":
        if len(tokens) != 5:
            return None
        return {"addr": addr, "rev": expected, "drop": True,
                "order": (0, (None, None, None))}
    parsed = parse_order_tokens(tokens[4:])
    if parsed is None:
        return None
    return {"addr": addr, "rev": expected, "drop": False,
            "order": parsed}


class Match(object):
    """One parsed match: transport record stream plus the recovery slots."""

    def __init__(self, mid, header):
        self.id = mid
        self.v = int(header["v"])
        self.rules_id = header["rules"]
        self.map = header["map"]
        self.seed = int(header["seed"], 16)
        self.p0 = header["p0"]
        self.p1 = header["p1"]
        self.header_turns = int(header["turns"])
        self.deployments = []          # (uid, type, x, y) canonical, file order
        self.blocks = []               # one dict per accepted turn block
        self.roster = set()            # unit ids deployed by the U lines
        self.closed = False
        self.r_lines = []


class Parser(object):
    def __init__(self, tables):
        self.tables = tables

    def r_address_exists(self, match, addr):
        """A structurally valid R needs an existing original address."""
        ordinal, slot_no = addr
        if ordinal < 1 or ordinal > len(match.blocks):
            return False
        return 1 <= slot_no <= len(match.blocks[ordinal - 1]["slots"])

    def parse_file(self, path):
        """Return (matches, malformed_lines, unknown_unit_orders, orders_total)."""
        tables = self.tables
        matches = []
        malformed = 0
        unknown_orders = 0
        orders_total = 0
        match = None
        block = None
        tail = False
        with open(path) as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                tokens = line.split(" ")
                word = tokens[0]
                if "" in tokens:
                    malformed += 1
                    continue

                if word == "MATCH":
                    if match is not None:
                        malformed += 1
                        continue
                    header = parse_match_header(tokens)
                    if header is None:
                        malformed += 1
                        continue
                    match = Match(tokens[1], header)
                    block = None
                    tail = False
                    continue

                if match is None:
                    malformed += 1
                    continue

                if word == "END":
                    if len(tokens) == 2 and tokens[1] == match.id:
                        match.closed = True
                        matches.append(match)
                        match = None
                        block = None
                        tail = False
                    else:
                        malformed += 1
                    continue

                if tail:
                    # Only further R lines, comments and blank lines pass.
                    if word != "R":
                        malformed += 1
                        continue
                    rec = parse_r_line(tokens)
                    if rec is None or not self.r_address_exists(match, rec["addr"]):
                        malformed += 1
                    else:
                        match.r_lines.append(rec)
                    continue

                if word == "R":
                    rec = parse_r_line(tokens)
                    if rec is None or not self.r_address_exists(match, rec["addr"]):
                        malformed += 1
                    else:
                        tail = True
                        match.r_lines.append(rec)
                    continue

                if word == "U":
                    if block is not None or len(tokens) != 5:
                        malformed += 1
                        continue
                    if not is_uid(tokens[1]) or tokens[2] not in tables.units:
                        malformed += 1
                        continue
                    if not (is_whole(tokens[3]) and is_whole(tokens[4])):
                        malformed += 1
                        continue
                    x = int(tokens[3])
                    y = int(tokens[4])
                    # Format 2 deployment coordinates are already canonical;
                    # only MOVE waypoints and keyframe entries carry the
                    # bottom left origin (see the note in the delivery notes).
                    match.deployments.append((tokens[1], tokens[2], x, y))
                    match.roster.add(tokens[1])
                    continue

                if word == "T":
                    if len(tokens) != 2 or not is_whole(tokens[1]):
                        malformed += 1
                        continue
                    block = {"turn": int(tokens[1]), "keyframe": None, "slots": []}
                    match.blocks.append(block)
                    continue

                if word == "K":
                    if block is None or block["slots"] or \
                            block["keyframe"] is not None:
                        malformed += 1
                        continue
                    kf = parse_keyframe_tokens(tokens)
                    if kf is None:
                        malformed += 1
                        continue
                    if match.v == 2:
                        m = tables.map_of(match.map)
                        if m is not None:
                            kf["units"] = [(u[0], u[1], m["h"] - 1 - u[2], u[3],
                                            u[4], u[5]) for u in kf["units"]]
                    block["keyframe"] = kf
                    continue

                if word == "O" or (len(word) == 3 and word[0] == "O"
                                   and word[1] == "~"):
                    if block is None:
                        malformed += 1
                        continue
                    parsed = parse_order_tokens(tokens)
                    if parsed is None:
                        malformed += 1
                        continue
                    lag, order = parsed
                    uid, verb, arg = order
                    known = uid in match.roster and \
                        (verb != "ATTACK" or arg in match.roster)
                    if not known:
                        unknown_orders += 1
                        continue
                    orders_total += 1
                    if match.v == 2 and verb == "MOVE":
                        m = tables.map_of(match.map)
                        if m is not None:
                            arg = [(p[0], m["h"] - 1 - p[1]) for p in arg]
                            order = (uid, verb, arg)
                    block["slots"].append({"order": (lag, order), "revision": 0,
                                           "dropped": False})
                    continue

                malformed += 1

        return matches, malformed, unknown_orders, orders_total


# ------------------------------------------------------------------- engine


def cells_between(x0, y0, x1, y1):
    """Integer line routine, appendix B; yields the cells strictly between."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
        if (x0, y0) == (x1, y1):
            return
        yield (x0, y0)


class Unit(object):
    __slots__ = ("uid", "type", "x", "y", "hp", "poison", "routed")

    def __init__(self, uid, type_, x, y, hp):
        self.uid = uid
        self.type = type_
        self.x = x
        self.y = y
        self.hp = hp
        self.poison = 0
        self.routed = 0


class History(object):
    """One full replay of a match under one version of its order slots."""

    def __init__(self, tables, match):
        self.tables = tables
        self.match = match
        self.map = tables.map_of(match.map)
        self.unit_types = {}
        for uid, type_, x, y in match.deployments:
            self.unit_types[uid] = type_
        self.digests = []
        self.divergences = []
        self.draws = [0, 0, 0]
        self.damage = {}
        self.kills = {}
        self.state = match.seed
        self.cp = [0, 0]
        self.units = {}
        self.unit_order = []
        self.braced = set()
        ruleset = tables.rules["rulesets"][match.rules_id]
        self.reseed = bool(ruleset.get("reseed", False))
        self.reseed_mult = ruleset.get("reseed_multiplier", 0)
        dice = tables.rules["dice"]
        self.mult = dice["multiplier"]
        self.inc = dice["increment"]
        self.mask = (1 << dice["modulus_bits"]) - 1
        self.shift = dice["output_shift"]
        self.span = 1 << dice["output_bits"]
        self.objectives = []
        if self.map is not None:
            for y, row in enumerate(self.map["rows"]):
                for x in range(min(self.map["w"], len(row))):
                    terr = tables.terrain.get(row[x])
                    if terr is not None and terr.get("objective"):
                        self.objectives.append((x, y))

    def in_map(self, x, y):
        if self.map is None:
            return False
        rows = self.map["rows"]
        if not 0 <= y < len(rows):
            return False
        row = rows[y]
        return 0 <= x < min(self.map["w"], len(row))

    def terrain_at(self, x, y):
        """The terrain entry of a cell, or None outside the atlas."""
        if not self.in_map(x, y):
            return None
        return self.tables.terrain.get(self.map["rows"][y][x])

    # -------------------------------------------------------------- dice

    def roll(self, sides, phase):
        limit = self.span - self.span % sides
        if limit <= 0:
            # A pathological table (sides wider than the sample span): accept
            # every sample rather than looping forever.
            limit = self.span
        self.draws[phase] += 1
        st = (self.state * self.mult + self.inc) & self.mask
        sample = (st >> self.shift) & (self.span - 1)
        while sample >= limit:
            self.draws[phase] += 1
            st = (st * self.mult + self.inc) & self.mask
            sample = (st >> self.shift) & (self.span - 1)
        self.state = st
        return 1 + sample % sides

    # ------------------------------------------------------------ digest

    def digest_text(self, turn):
        out = ["t=%d;rng=%08x;cp=%d,%d;" % (turn, self.state, self.cp[0], self.cp[1])]
        for uid in self.unit_order:
            u = self.units.get(uid)
            if u is None:
                continue
            out.append("%s@%d,%d,%d,%d,%d;" % (uid, u.x, u.y, u.hp, u.poison,
                                               u.routed))
        return "".join(out)

    # ----------------------------------------------------------- combat

    def attack_legal(self, a, b):
        if a is None or b is None:
            return False
        if a.uid[0] == b.uid[0] or a.routed:
            return False
        stats = self.tables.units[a.type]
        dist = abs(a.x - b.x) + abs(a.y - b.y)
        if dist == 1:
            return True
        if "ranged" not in stats.get("tags", []):
            return False
        if dist < 2:
            return False
        terr = self.terrain_at(a.x, a.y)
        if terr is None:
            return False
        if dist > stats["range"] + terr.get("range_bonus", 0):
            return False
        for cx, cy in cells_between(a.x, a.y, b.x, b.y):
            cell = self.terrain_at(cx, cy)
            if cell is not None and cell.get("blocks_los"):
                return False
            for u in self.units.values():
                if u.x == cx and u.y == cy:
                    return False
        return True

    def defence_of(self, b):
        t = self.tables
        cfg = t.rules["combat"]
        stats = t.units[b.type]
        d = stats["def"]
        terr = self.terrain_at(b.x, b.y)
        if terr is not None:
            d += terr.get("def", 0)
        if "pike" in stats.get("tags", []):
            for u in self.units.values():
                if u is not b and u.uid[0] == b.uid[0] and \
                        "pike" in t.units[u.type].get("tags", []) and \
                        abs(u.x - b.x) + abs(u.y - b.y) == 1:
                    d += cfg["shield_wall_bonus"]
                    break
        if b.uid in self.braced:
            d += cfg["brace_bonus"]
        if b.routed:
            d -= cfg["rout_penalty"]
        return d

    def strike(self, a, b, phase):
        t = self.tables
        cfg = t.rules["combat"]
        stats_a = t.units[a.type]
        dist = abs(a.x - b.x) + abs(a.y - b.y)
        pinned = dist == 1 and "ranged" in stats_a.get("tags", [])
        atk = stats_a["atk"] - (cfg["pinned_penalty"] if pinned else 0)
        roll = self.roll(20, phase)
        crit = roll == cfg["crit_roll"]
        if not crit:
            flank = 0
            if dist == 1:
                for u in self.units.values():
                    if u is not a and u.uid[0] == a.uid[0] and \
                            abs(u.x - b.x) + abs(u.y - b.y) == 1:
                        flank += 1
                flank = min(flank, cfg["flank_cap"])
            if roll + atk + flank < cfg["hit_target"] + self.defence_of(b):
                return
        count, sides, bonus = stats_a["dice"]
        if crit:
            count *= 2
        total = bonus
        for _ in range(count):
            total += self.roll(sides, PHASE_DAMAGE if phase == PHASE_ATTACK
                               else phase)
        num, den = t.adv.get((a.type, b.type), t.adv_default)
        damage = max(cfg["min_damage"],
                     (total * num) // den - t.units[b.type]["armour"])
        self.damage[a.type] = self.damage.get(a.type, 0) + damage
        b.hp -= damage
        if b.hp <= 0:
            self.kills[a.type] = self.kills.get(a.type, 0) + 1
            del self.units[b.uid]
            return
        if "poison" in stats_a.get("tags", []):
            b.poison = t.rules["status"]["poison_turns"]
        if not b.routed and b.hp * 4 <= t.units[b.type]["hp"]:
            b.routed = 1

    # ------------------------------------------------------------- turn

    def effective_order(self, block, uid):
        zero = None
        one = None
        for slot in block["slots"]:
            if slot["dropped"]:
                continue
            lag, order = slot["order"]
            if order[0] != uid or lag >= 2:
                continue
            if lag == 0:
                zero = order
            else:
                one = order
        return zero if zero is not None else one

    def run(self):
        t = self.tables
        for uid, type_, x, y in self.match.deployments:
            self.units[uid] = Unit(uid, type_, x, y, t.units[type_]["hp"])
        self.unit_order = sorted(self.units, key=lambda u: (u[0], unit_number(u)))
        self.digests.append(fnv1a_hex(self.digest_text(0)))
        for block in self.match.blocks:
            self.play_block(block)
            self.digests.append(fnv1a_hex(self.digest_text(block["turn"])))
        return self

    def play_block(self, block):
        turn = block["turn"]

        if block["keyframe"] is not None:
            self.apply_keyframe(block["keyframe"], turn)

        if self.reseed:
            self.state = self.match.seed ^ \
                ((turn * self.reseed_mult) & 0xFFFFFFFF)

        braced = set()
        armed = set()
        reacted = set()
        self.braced = braced
        orders = {}
        for uid in list(self.units):
            eff = self.effective_order(block, uid)
            if eff is None:
                continue
            orders[uid] = eff
            if eff[1] == "HOLD":
                braced.add(uid)
            elif eff[1] == "READY":
                armed.add(uid)

        side_first = "A" if turn % 2 == 1 else "B"
        living = list(self.units)
        living.sort(key=lambda u: (-self.eff_init(u),
                                   0 if u[0] == side_first else 1,
                                   unit_number(u)))

        for uid in living:
            u = self.units.get(uid)
            if u is None:
                continue
            eff = orders.get(uid)
            if eff is None:
                continue
            if eff[1] == "MOVE":
                self.do_move(u, eff[2], living, armed, reacted)
            elif eff[1] == "ATTACK":
                target = self.units.get(eff[2])
                if target is not None and self.attack_legal(u, target):
                    self.strike(u, target, PHASE_ATTACK)

        for uid in list(self.unit_order):
            u = self.units.get(uid)
            if u is None:
                continue
            if u.poison > 0:
                u.hp -= 1
                u.poison -= 1
                if u.hp <= 0:
                    del self.units[uid]
                elif not u.routed and u.hp * 4 <= self.tables.units[u.type]["hp"]:
                    u.routed = 1

        for ox, oy in self.objectives:
            sides = 0
            for cx, cy in ((ox, oy), (ox - 1, oy), (ox + 1, oy),
                           (ox, oy - 1), (ox, oy + 1)):
                for u in self.units.values():
                    if u.x == cx and u.y == cy:
                        sides |= 1 if u.uid[0] == "A" else 2
            if sides == 1:
                self.cp[0] += 1
            elif sides == 2:
                self.cp[1] += 1

    def eff_init(self, uid):
        u = self.units[uid]
        stats = self.tables.units[u.type]
        return stats["init"] - (stats["hp"] - u.hp) // 3

    def do_move(self, u, waypoints, living, armed, reacted):
        t = self.tables
        stats = t.units[u.type]
        cls = stats["class"]
        points = stats["move"]
        skirmisher = "skirmisher" in stats.get("tags", [])
        moved = False
        for wx, wy in waypoints:
            if abs(wx - u.x) + abs(wy - u.y) != 1:
                break
            terr = self.terrain_at(wx, wy)
            if terr is None:
                break
            cost = terr.get("cost", {}).get(cls)
            if cost is None or cost > points:
                break
            blocked = False
            for other in self.units.values():
                if other.x == wx and other.y == wy:
                    blocked = True
                    break
            if blocked:
                break
            u.x = wx
            u.y = wy
            points -= cost
            moved = True
            if not skirmisher:
                for other in self.units.values():
                    if other.uid[0] != u.uid[0] and \
                            abs(other.x - u.x) + abs(other.y - u.y) == 1:
                        self.reactions(u, living, armed, reacted)
                        return
        if moved:
            self.reactions(u, living, armed, reacted)

    def reactions(self, mover, living, armed, reacted):
        for uid in living:
            u = self.units.get(uid)
            if u is None:
                continue
            if uid[0] == mover.uid[0]:
                continue
            if uid not in armed or uid in reacted:
                continue
            if not self.attack_legal(u, mover):
                continue
            reacted.add(uid)
            self.strike(u, mover, PHASE_REACTION)
            if mover.uid not in self.units:
                break

    def apply_keyframe(self, kf, turn):
        match = self.match
        engine_units = []
        for uid in self.unit_order:
            u = self.units.get(uid)
            if u is not None:
                engine_units.append((uid, u.x, u.y, u.hp, u.poison, u.routed))
        if kf["rng"] != self.state or list(kf["cp"]) != self.cp or \
                engine_units != list(kf["units"]):
            self.divergences.append(turn)
        self.state = kf["rng"]
        self.cp = list(kf["cp"])
        self.units = {}
        for uid, x, y, hp, poison, routed in kf["units"]:
            type_ = self.unit_types.get(uid)
            if type_ is None:
                continue
            unit = Unit(uid, type_, x, y, hp)
            unit.poison = poison
            unit.routed = routed
            self.units[uid] = unit
        self.unit_order = sorted(self.units, key=lambda u: (u[0], unit_number(u)))


def timeline_fingerprint(digests):
    """FNV-1a of `0:d0;1:d1;...` over the deployment digest and every turn."""
    return fnv1a_hex("".join("%d:%s;" % (i, d) for i, d in enumerate(digests)))


# ------------------------------------------------------------- match result


def match_result(tables, history):
    """Return (score0, score1, winner) following section 12.1.

    The score is always filled in: control points plus the cost of the
    living units of the side.  The winner follows the three cases of
    section 12.1, which do not depend on the score in the first two.
    """
    match = history.match
    survivors0 = [u for u in history.units.values() if u.uid[0] == "A"]
    survivors1 = [u for u in history.units.values() if u.uid[0] == "B"]
    units = tables.units
    control = tables.rules["scoring"]["control_points"]
    s0 = history.cp[0] * control + sum(units[u.type]["cost"] for u in survivors0)
    s1 = history.cp[1] * control + sum(units[u.type]["cost"] for u in survivors1)
    if not survivors0 and not survivors1:
        return (s0, s1, None)
    if not survivors1:
        return (s0, s1, match.p0)
    if not survivors0:
        return (s0, s1, match.p1)
    if s0 > s1:
        winner = match.p0
    elif s1 > s0:
        winner = match.p1
    else:
        winner = None
    return (s0, s1, winner)


def survivor_rows(history):
    rows = []
    for uid in history.unit_order:
        u = history.units.get(uid)
        if u is not None:
            rows.append([uid, u.x, u.y, u.hp])
    return rows


# ----------------------------------------------------- recovery (section 16)


def replay_match(tables, match):
    return History(tables, match).run()


def apply_amendments(tables, match, audit_out):
    """Replay the match under every applied amendment, filling audit_out.

    Returns the final history.  The match's slots are left as the final
    version (the last applied amendment), which is what the reports use.
    """
    unit_types = list(tables.units)

    prev = replay_match(tables, match)
    prev_fp = timeline_fingerprint(prev.digests)

    def emit(ordinal, slot_no, revision, before, after, hist_before, hist_after):
        changed = [i for i, d in enumerate(hist_before.digests)
                   if hist_after.digests[i] != d]
        audit_out.append({
            "turn": ordinal,
            "slot": slot_no,
            "revision": revision,
            "before": before,
            "after": after,
            "changed": changed,
            "draws_delta": {
                "attack": hist_after.draws[0] - hist_before.draws[0],
                "damage": hist_after.draws[1] - hist_before.draws[1],
                "reaction": hist_after.draws[2] - hist_before.draws[2],
            },
            "damage_delta": {
                ut: hist_after.damage.get(ut, 0) - hist_before.damage.get(ut, 0)
                for ut in unit_types
            },
            "kills_delta": {
                ut: hist_after.kills.get(ut, 0) - hist_before.kills.get(ut, 0)
                for ut in unit_types
            },
            "divergences_before": list(hist_before.divergences),
            "divergences_after": list(hist_after.divergences),
        })

    for rec in match.r_lines:
        ordinal, slot_no = rec["addr"]
        block = match.blocks[ordinal - 1]
        slot = block["slots"][slot_no - 1]

        if not rec["drop"]:
            lag, order = rec["order"]
            uid, verb, arg = order
            if uid not in match.roster or (verb == "ATTACK" and arg not in match.roster):
                match.amend_unknown += 1
                continue
        if rec["rev"] != slot["revision"]:
            match.amend_stale += 1
            continue

        if rec["drop"]:
            new_state = (True, slot["order"])
        else:
            lag, order = rec["order"]
            uid, verb, arg = order
            if match.v == 2 and verb == "MOVE":
                m = tables.map_of(match.map)
                if m is not None:
                    arg = [(p[0], m["h"] - 1 - p[1]) for p in arg]
                    order = (uid, verb, arg)
            new_state = (False, (lag, order))

        slot["revision"] += 1
        match.amend_applied += 1
        revision = slot["revision"]

        if new_state == (slot["dropped"], slot["order"]):
            # Writing the same order again (or dropping a tombstone) leaves
            # the replay untouched, but it is still an applied revision.
            emit(ordinal, slot_no, revision, prev_fp, prev_fp, prev, prev)
            continue

        slot["dropped"], slot["order"] = new_state
        hist = replay_match(tables, match)
        fp = timeline_fingerprint(hist.digests)
        emit(ordinal, slot_no, revision, prev_fp, fp, prev, hist)
        prev = hist
        prev_fp = fp
    return prev


# ------------------------------------------------------------------- reports


def scenario_report(name, tables, matches, histories):
    ladder = {}
    for player in tables.players:
        ladder[player["id"]] = [player["rating"], 0, 0, 0, 0]
    ladder_cfg = tables.rules["ladder"]
    entries = []
    for match, hist in zip(matches, histories):
        s0, s1, winner = match_result(tables, hist)
        row = {
            "id": match.id,
            "map": match.map,
            "players": [match.p0, match.p1],
            "turns": len(match.blocks),
            "digests": hist.digests,
            "control": list(hist.cp),
            "survivors": survivor_rows(hist),
            "score": [s0, s1],
            "winner": winner,
            "amendments": match.audit,
        }
        entries.append(row)
        apply_ladder(ladder_cfg, ladder, match, winner)
    standings = []
    for pid, row in ladder.items():
        if row[1] == 0:
            continue
        standings.append({"player": pid, "rating": row[0], "played": row[1],
                           "won": row[2], "drawn": row[3], "lost": row[4]})
    standings.sort(key=lambda r: (-r["rating"], r["player"]))
    return {"scenario": name, "source": "replays_%s.log" % name,
            "matches": entries, "standings": standings}


def apply_ladder(ladder_cfg, ladder, match, winner):
    """Apply one match result to the ladder (section 12.2)."""
    p0, p1 = match.p0, match.p1
    if p0 not in ladder:
        ladder[p0] = [0, 0, 0, 0, 0]
    if p1 not in ladder:
        ladder[p1] = [0, 0, 0, 0, 0]
    row0 = ladder[p0]
    row1 = ladder[p1]
    row0[1] += 1
    row1[1] += 1
    if winner is None:
        row0[3] += 1
        row1[3] += 1
        if row0[0] >= row1[0]:
            high, low = row0, row1
        else:
            high, low = row1, row0
        gift = min(ladder_cfg["draw_cap"],
                   floor_div(high[0] - low[0], ladder_cfg["draw_divisor"]))
        high[0] -= gift
        low[0] += gift
        return
    if winner == p0:
        win, lose = row0, row1
        row0[2] += 1
        row1[4] += 1
    else:
        win, lose = row1, row0
        row1[2] += 1
        row0[4] += 1
    delta = ladder_cfg["win_base"] + \
        floor_div(lose[0] - win[0], ladder_cfg["win_divisor"])
    if delta < ladder_cfg["win_min"]:
        delta = ladder_cfg["win_min"]
    elif delta > ladder_cfg["win_max"]:
        delta = ladder_cfg["win_max"]
    win[0] += delta
    lose[0] -= delta


def floor_div(a, b):
    """Floor division, rounding toward negative infinity."""
    return a // b


def main(data_dir, out_dir):
    tables = Tables(data_dir)
    parser = Parser(tables)

    scenario_rows = {}
    units = list(tables.units)
    deployed = {ut: 0 for ut in units}
    damage = {ut: 0 for ut in units}
    kills = {ut: 0 for ut in units}

    for name in SCENARIOS:
        path = os.path.join(data_dir, "replays_%s.log" % name)
        matches, malformed, unknown_orders, orders_total = parser.parse_file(path)

        late = 0
        superseded = 0
        draws = [0, 0, 0]
        divergences = []
        applied = stale = unknown_amend = 0
        histories = []
        for match in matches:
            match.audit = []
            match.amend_applied = 0
            match.amend_stale = 0
            match.amend_unknown = 0
            hist = apply_amendments(tables, match, match.audit)
            histories.append(hist)
            for block in match.blocks:
                groups = {}
                for slot in block["slots"]:
                    if slot["dropped"]:
                        continue
                    lag, order = slot["order"]
                    if lag >= 2:
                        late += 1
                        continue
                    groups.setdefault(order[0], []).append(lag)
                for uid, lags in groups.items():
                    superseded += len(lags) - 1
            for i in range(3):
                draws[i] += hist.draws[i]
            divergences.extend([match.id, turn] for turn in hist.divergences)
            applied += match.amend_applied
            stale += match.amend_stale
            unknown_amend += match.amend_unknown
            for uid, type_, x, y in match.deployments:
                deployed[type_] += 1
            for type_, value in hist.damage.items():
                damage[type_] += value
            for type_, value in hist.kills.items():
                kills[type_] += value

        scenario_rows[name] = {
            "parsed": matches,
            "matches": len(matches),
            "turns": sum(len(m.blocks) for m in matches),
            "orders_total": orders_total,
            "orders_late": late,
            "orders_superseded": superseded,
            "malformed_lines": malformed,
            "unknown_unit_orders": unknown_orders,
            "divergences": divergences,
            "amendments": {"applied": applied, "stale": stale, "unknown": unknown_amend},
            "draws": draws,
            "histories": histories,
        }

    os.makedirs(out_dir, exist_ok=True)

    for name in SCENARIOS:
        row = scenario_rows[name]
        report = scenario_report(name, tables, row["parsed"], row["histories"])
        with open(os.path.join(out_dir, "scenario_%s.json" % name), "w") as fh:
            json.dump(report, fh, indent=2, sort_keys=False)
            fh.write("\n")

    perf = {"scenarios": {name: {
        "matches": scenario_rows[name]["matches"],
        "turns": scenario_rows[name]["turns"],
        "orders_total": scenario_rows[name]["orders_total"],
        "orders_late": scenario_rows[name]["orders_late"],
        "orders_superseded": scenario_rows[name]["orders_superseded"],
    } for name in SCENARIOS}}
    with open(os.path.join(out_dir, "perf_report.json"), "w") as fh:
        json.dump(perf, fh, indent=2)
        fh.write("\n")

    bottleneck = {"scenarios": {}}
    for name in SCENARIOS:
        draws = scenario_rows[name]["draws"]
        counts = {"attack": draws[0], "damage": draws[1], "reaction": draws[2]}
        dominant = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        bottleneck["scenarios"][name] = {
            "draws_by_phase": counts, "dominant_phase": dominant}
    with open(os.path.join(out_dir, "bottleneck_analysis.json"), "w") as fh:
        json.dump(bottleneck, fh, indent=2)
        fh.write("\n")

    balance = tables.rules["balance"]
    recs = {"units": {}}
    for ut in units:
        dep = deployed[ut]
        dmg = damage[ut]
        kil = kills[ut]
        cost = tables.units[ut]["cost"]
        per = (dmg * 1000) // (dep * cost) if dep else 0
        if per >= balance["nerf_at"]:
            verdict = "nerf"
        elif per <= balance["buff_at"]:
            verdict = "buff"
        else:
            verdict = "hold"
        recs["units"][ut] = {"deployed": dep, "damage_dealt": dmg, "kills": kil,
                             "per_cost_permille": per, "verdict": verdict}
    with open(os.path.join(out_dir, "recommendations.json"), "w") as fh:
        json.dump(recs, fh, indent=2)
        fh.write("\n")

    quality = {"scenarios": {}}
    for name in SCENARIOS:
        row = scenario_rows[name]
        quality["scenarios"][name] = {
            "malformed_lines": row["malformed_lines"],
            "unknown_unit_orders": row["unknown_unit_orders"],
            "divergences": row["divergences"],
            "amendments": row["amendments"],
        }
    with open(os.path.join(out_dir, "data_quality.json"), "w") as fh:
        json.dump(quality, fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.stderr.write("usage: optimize.py <data_dir> <out_dir>\n")
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
