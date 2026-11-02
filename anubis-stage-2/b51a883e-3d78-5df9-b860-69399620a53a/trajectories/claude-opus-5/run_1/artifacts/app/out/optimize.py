#!/usr/bin/env python3
"""Brassmoor Skirmish replay engine.

Usage:  python3 optimize.py <data_dir> <out_dir>

Reads the six tables and the five replay exports from <data_dir>, replays
every closed match exactly as the rule book (plus the season 5 errata)
describes and writes the nine reports into <out_dir>.
"""

import json
import os
import re
import sys

# ---------------------------------------------------------------- constants
# Only values that no table in <data_dir> supplies are written here.
D20_SIDES = 20                      # section 9.2: the hit roll is a d20
FNV_OFFSET = 0x811c9dc5             # appendix C
FNV_PRIME = 0x01000193
MASK32 = 0xffffffff

SCENARIOS = ("visible", "peak", "steady", "burst", "latency")
PHASES = ("attack", "damage", "reaction")

WHOLE_RE = re.compile(r"\A(?:0|[1-9][0-9]*)\Z")
UID_RE = re.compile(r"\A[AB][1-9][0-9]*\Z")
HEX8_RE = re.compile(r"\A[0-9a-f]{8}\Z")
WAYPOINT_RE = re.compile(r"\A(?:0|[1-9][0-9]*),(?:0|[1-9][0-9]*)\Z")
LAG_RE = re.compile(r"\AO~([1-9])\Z")

HOLD, READY, ATTACK, MOVE = "HOLD", "READY", "ATTACK", "MOVE"
HEADER_KEYS = frozenset(("v", "rules", "map", "seed", "p0", "p1", "turns"))


def fnv1a(text):
    h = FNV_OFFSET
    for byte in text.encode("ascii"):
        h = ((h ^ byte) * FNV_PRIME) & MASK32
    return "%08x" % h


def is_whole(tok):
    return WHOLE_RE.match(tok) is not None


def roster_key(uid):
    return (uid[0], int(uid[1:]))


# ------------------------------------------------------------------- tables
class GameMap(object):
    __slots__ = ("name", "width", "height", "rows", "objectives")

    def __init__(self, name, width, height, rows):
        self.name = name
        self.width = width
        self.height = height
        self.rows = rows
        self.objectives = []


class Tables(object):
    def __init__(self, data_dir):
        self.units = _load_json(data_dir, "units.json")["units"]
        self.terrain = _load_json(data_dir, "terrain.json")["terrain"]
        adv = _load_json(data_dir, "advantage.json")
        self.adv_default = (adv["default"][0], adv["default"][1])
        self.adv_pairs = {}
        for pair in adv["pairs"]:
            self.adv_pairs[(pair["attacker"], pair["defender"])] = (
                pair["num"], pair["den"])
        rules = _load_json(data_dir, "rulesets.json")
        self.rulesets = rules["rulesets"]
        self.dice = rules["dice"]
        self.combat = rules["combat"]
        self.status = rules["status"]
        self.scoring = rules["scoring"]
        self.ladder = rules["ladder"]
        self.balance = rules["balance"]
        self.players = {}
        for entry in _load_json(data_dir, "players.json")["players"]:
            self.players[entry["id"]] = entry["rating"]
        self.maps = _load_maps(os.path.join(data_dir, "maps.txt"))

        self.unit_types = list(self.units.keys())
        self.tag_sets = dict((name, frozenset(stats.get("tags") or []))
                             for name, stats in self.units.items())
        # stand-in entry for cells off the board: impassable, no modifiers
        self.outside = {"cost": {}, "def": 0, "blocks_los": False,
                        "range_bonus": 0, "objective": False}
        for gmap in self.maps.values():
            gmap.objectives = self._objectives(gmap)

    def _objectives(self, gmap):
        found = []
        for y in range(gmap.height):
            row = gmap.rows[y] if y < len(gmap.rows) else ""
            for x in range(gmap.width):
                info = self.terrain.get(row[x]) if x < len(row) else None
                if info is not None and info["objective"]:
                    found.append((x, y))
        return found

    def advantage(self, attacker_type, defender_type):
        return self.adv_pairs.get((attacker_type, defender_type),
                                  self.adv_default)


def _load_json(data_dir, name):
    with open(os.path.join(data_dir, name), "r") as handle:
        return json.load(handle)


def _load_maps(path):
    maps = {}
    header = None
    rows = None
    with open(path, "r") as handle:
        for raw in handle:
            line = raw.rstrip("\n").rstrip("\r")
            if header is None:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                parts = stripped.split()
                if parts[0] == "MAP" and len(parts) == 4:
                    header = (parts[1], int(parts[2]), int(parts[3]))
                    rows = []
                continue
            if line.strip() == "ENDMAP":
                maps[header[0]] = GameMap(header[0], header[1], header[2],
                                          rows)
                header = None
                rows = None
                continue
            rows.append(line)
    return maps


# -------------------------------------------------------------- log parsing
class Order(object):
    __slots__ = ("lag", "uid", "verb", "target", "path")

    def __init__(self, lag, uid, verb, target=None, path=None):
        self.lag = lag
        self.uid = uid
        self.verb = verb
        self.target = target
        self.path = path


class Block(object):
    __slots__ = ("n", "keyframe", "has_keyframe", "slots", "first_order")

    def __init__(self, n):
        self.n = n
        self.keyframe = None
        self.has_keyframe = False
        self.slots = []
        self.first_order = False


class Match(object):
    __slots__ = ("mid", "fmt", "rules", "map_name", "gmap", "seed", "p0",
                 "p1", "deploy", "roster", "blocks", "seen_turn", "closed",
                 "tail_started", "amendments")

    def __init__(self):
        self.deploy = []
        self.roster = {}
        self.blocks = []
        self.seen_turn = False
        self.closed = False
        self.tail_started = False
        self.amendments = []


def parse_order_tokens(tokens):
    """Return an Order for a syntactically valid order, else None."""
    head = tokens[0]
    if head == "O":
        lag = 0
    else:
        hit = LAG_RE.match(head)
        if hit is None:
            return None
        lag = int(hit.group(1))
    if len(tokens) < 3:
        return None
    uid = tokens[1]
    if UID_RE.match(uid) is None:
        return None
    verb = tokens[2]
    if verb == HOLD or verb == READY:
        if len(tokens) != 3:
            return None
        return Order(lag, uid, verb)
    if verb == ATTACK:
        if len(tokens) != 4 or UID_RE.match(tokens[3]) is None:
            return None
        return Order(lag, uid, verb, target=tokens[3])
    if verb == MOVE:
        if len(tokens) < 4:
            return None
        path = []
        for tok in tokens[3:]:
            if WAYPOINT_RE.match(tok) is None:
                return None
            xs, ys = tok.split(",")
            path.append((int(xs), int(ys)))
        return Order(lag, uid, verb, path=tuple(path))
    return None


def parse_keyframe(tokens):
    """Return (rng, cp0, cp1, units) for a valid K line, else None."""
    if len(tokens) < 4 or not is_whole(tokens[1]):
        return None
    if not tokens[2].startswith("rng="):
        return None
    rng_text = tokens[2][4:]
    if HEX8_RE.match(rng_text) is None:
        return None
    if not tokens[3].startswith("cp="):
        return None
    cp_text = tokens[3][3:]
    if cp_text.count(",") != 1:
        return None
    c0, c1 = cp_text.split(",")
    if not is_whole(c0) or not is_whole(c1):
        return None
    units = []
    for entry in tokens[4:]:
        if entry.count("@") != 1:
            return None
        uid, rest = entry.split("@")
        if UID_RE.match(uid) is None:
            return None
        fields = rest.split(",")
        if len(fields) != 5 or fields[4] not in ("0", "1"):
            return None
        for field in fields:
            if not is_whole(field):
                return None
        units.append((uid, int(fields[0]), int(fields[1]), int(fields[2]),
                      int(fields[3]), int(fields[4])))
    return (int(rng_text, 16), int(c0), int(c1), units)


def parse_amendment(tokens, match):
    """Return (turn_ordinal, slot, expected_revision, order_or_None)."""
    if len(tokens) < 5:
        return None
    q_text, s_text, v_text = tokens[1], tokens[2], tokens[3]
    if not (is_whole(q_text) and is_whole(s_text) and is_whole(v_text)):
        return None
    turn_ordinal = int(q_text)
    slot = int(s_text)
    if turn_ordinal < 1 or slot < 1 or turn_ordinal > len(match.blocks):
        return None
    if slot > len(match.blocks[turn_ordinal - 1].slots):
        return None
    payload = tokens[4:]
    if len(payload) == 1 and payload[0] == "DROP":
        return (turn_ordinal, slot, int(v_text), None)
    order = parse_order_tokens(payload)
    if order is None:
        return None
    if order.verb == MOVE:
        order.path = tuple(to_canonical(match, x, y) for (x, y) in order.path)
    return (turn_ordinal, slot, int(v_text), order)


def to_canonical(match, x, y):
    """Turn a logged client coordinate into the canonical frame (E-2).

    Format 2 logs put the origin at the bottom left for the coordinates the
    season 5 client emits: MOVE waypoints (fresh, lagged or inside an R
    replacement) and K entries.  The deployment coordinates of `U` lines are
    written in the canonical frame even in a format 2 log; flipping them
    instead leaves 94% of all first waypoints non adjacent to their issuer
    and makes honest keyframes disagree, so they are taken as they stand.
    """
    if match.fmt == 2:
        return (x, match.gmap.height - 1 - y)
    return (x, y)


class ParseResult(object):
    __slots__ = ("matches", "malformed_lines", "unknown_unit_orders",
                 "orders_total")

    def __init__(self):
        self.matches = []
        self.malformed_lines = 0
        self.unknown_unit_orders = 0
        self.orders_total = 0


def parse_log(path, tables):
    res = ParseResult()
    cur = None
    with open(path, "r") as handle:
        text = handle.read()

    for raw in text.split("\n"):
        line = raw.strip()
        if not line or line[0] == "#":
            continue
        tokens = line.split(" ")
        if "" in tokens:
            res.malformed_lines += 1
            continue
        head = tokens[0]

        if head == "MATCH":
            match = open_match(tokens, cur, tables)
            if match is None:
                res.malformed_lines += 1
            else:
                cur = match
                res.matches.append(match)
            continue

        if cur is None:
            res.malformed_lines += 1
            continue

        if head == "END":
            if len(tokens) == 2 and tokens[1] == cur.mid:
                cur.closed = True
                cur = None
            else:
                res.malformed_lines += 1
            continue

        if head == "R":
            record = parse_amendment(tokens, cur)
            if record is None:
                res.malformed_lines += 1
            else:
                cur.tail_started = True
                cur.amendments.append(record)
            continue

        if cur.tail_started:
            # inside the tail only R, comments, blanks and END are accepted
            res.malformed_lines += 1
            continue

        if head == "U":
            if cur.seen_turn or len(tokens) != 5:
                res.malformed_lines += 1
                continue
            uid, utype, xs, ys = tokens[1], tokens[2], tokens[3], tokens[4]
            if (UID_RE.match(uid) is None or utype not in tables.units
                    or not is_whole(xs) or not is_whole(ys)):
                res.malformed_lines += 1
                continue
            # deployment coordinates are canonical in both log formats
            cur.deploy.append((uid, utype, int(xs), int(ys)))
            cur.roster[uid] = utype
            continue

        if head == "T":
            if len(tokens) != 2 or not is_whole(tokens[1]):
                res.malformed_lines += 1
                continue
            cur.seen_turn = True
            cur.blocks.append(Block(int(tokens[1])))
            continue

        if head == "K":
            if not cur.blocks:
                res.malformed_lines += 1
                continue
            block = cur.blocks[-1]
            if block.has_keyframe or block.first_order:
                res.malformed_lines += 1
                continue
            parsed = parse_keyframe(tokens)
            if parsed is None:
                res.malformed_lines += 1
                continue
            rng, c0, c1, listed = parsed
            block.keyframe = (rng, c0, c1, [
                (uid,) + to_canonical(cur, x, y) + (hp, poison, routed)
                for (uid, x, y, hp, poison, routed) in listed])
            block.has_keyframe = True
            continue

        if head == "O" or head.startswith("O~"):
            order = parse_order_tokens(tokens)
            if order is None or not cur.blocks:
                res.malformed_lines += 1
                continue
            if (order.uid not in cur.roster or
                    (order.verb == ATTACK and order.target not in cur.roster)):
                res.unknown_unit_orders += 1
                continue
            if order.verb == MOVE:
                order.path = tuple(to_canonical(cur, x, y)
                                   for (x, y) in order.path)
            res.orders_total += 1
            block = cur.blocks[-1]
            block.slots.append(order)
            block.first_order = True
            continue

        res.malformed_lines += 1

    return res


def open_match(tokens, cur, tables):
    if cur is not None or len(tokens) != 9:
        return None
    fields = {}
    for tok in tokens[2:]:
        key, sep, value = tok.partition("=")
        if not sep or key in fields:
            return None
        fields[key] = value
    if set(fields) != HEADER_KEYS:
        return None
    if fields["v"] not in ("1", "2") or fields["rules"] not in ("1", "2"):
        return None
    if HEX8_RE.match(fields["seed"]) is None:
        return None
    if not is_whole(fields["turns"]):
        return None
    gmap = tables.maps.get(fields["map"])
    if gmap is None:
        return None
    match = Match()
    match.mid = tokens[1]
    match.fmt = int(fields["v"])
    match.rules = fields["rules"]
    match.map_name = fields["map"]
    match.gmap = gmap
    match.seed = int(fields["seed"], 16)
    match.p0 = fields["p0"]
    match.p1 = fields["p1"]
    return match


# ------------------------------------------------------------------- replay
class Replay(object):
    __slots__ = ("digests", "control", "survivors", "score", "winner_side",
                 "draws", "damage", "kills", "divergences")


def effective_orders(orders):
    """Return (effective order per uid, late count, superseded count)."""
    groups = {}
    sequence = []
    late = 0
    for order in orders:
        if order is None:
            continue
        if order.lag >= 2:
            late += 1
            continue
        uid = order.uid
        group = groups.get(uid)
        if group is None:
            group = groups[uid] = [[], []]
            sequence.append(uid)
        group[0 if order.lag == 0 else 1].append(order)
    effective = {}
    superseded = 0
    for uid in sequence:
        zero, one = groups[uid]
        superseded += len(zero) + len(one) - 1
        effective[uid] = zero[-1] if zero else one[-1]
    return effective, late, superseded


def replay_match(match, tables, slots_by_block):
    combat = tables.combat
    hit_target = combat["hit_target"]
    crit_roll = combat["crit_roll"]
    flank_cap = combat["flank_cap"]
    shield_wall_bonus = combat["shield_wall_bonus"]
    brace_bonus = combat["brace_bonus"]
    rout_penalty = combat["rout_penalty"]
    pinned_penalty = combat["pinned_penalty"]
    min_damage = combat["min_damage"]
    poison_turns = tables.status["poison_turns"]
    control_points = tables.scoring["control_points"]

    dice = tables.dice
    multiplier = dice["multiplier"]
    increment = dice["increment"]
    state_mask = (1 << dice["modulus_bits"]) - 1
    output_shift = dice["output_shift"]
    span = 1 << dice["output_bits"]
    sample_mask = span - 1

    ruleset = tables.rulesets[match.rules]
    reseeds = bool(ruleset.get("reseed"))
    reseed_multiplier = ruleset.get("reseed_multiplier", 0)

    unit_tbl = tables.units
    tags_of = tables.tag_sets
    terrain = tables.terrain
    outside = tables.outside
    gmap = match.gmap
    width = gmap.width
    height = gmap.height
    rows = gmap.rows
    objectives = gmap.objectives

    def cell(x, y):
        if 0 <= x < width and 0 <= y < height:
            row = rows[y]
            if x < len(row):
                info = terrain.get(row[x])
                if info is not None:
                    return info
        return outside

    utype = {}
    for uid, typ, _x, _y in match.deploy:
        utype[uid] = typ
    roster_order = sorted(utype.keys(), key=roster_key)

    pos_x = {}
    pos_y = {}
    hp = {}
    poison = {}
    routed = {}
    occupied = {}
    alive = set()

    def place_all(entries):
        occupied.clear()
        alive.clear()
        for uid, x, y, points, venom, broken in entries:
            pos_x[uid] = x
            pos_y[uid] = y
            hp[uid] = points
            poison[uid] = venom
            routed[uid] = broken
            alive.add(uid)
            occupied[(x, y)] = uid

    place_all([(uid, x, y, unit_tbl[typ]["hp"], 0, 0)
               for uid, typ, x, y in match.deploy])

    rng_state = match.seed
    control = [0, 0]
    draws = {"attack": 0, "damage": 0, "reaction": 0}
    damage_credit = {}
    kill_credit = {}
    divergences = []

    def digest(turn):
        parts = ["t=%d;rng=%08x;cp=%d,%d;"
                 % (turn, rng_state, control[0], control[1])]
        for uid in roster_order:
            if uid in alive:
                parts.append("%s@%d,%d,%d,%d,%d;"
                             % (uid, pos_x[uid], pos_y[uid], hp[uid],
                                poison[uid], routed[uid]))
        return fnv1a("".join(parts))

    digests = [digest(0)]

    def remove(uid):
        alive.discard(uid)
        key = (pos_x[uid], pos_y[uid])
        if occupied.get(key) == uid:
            del occupied[key]

    def rout_check(uid):
        if not routed[uid] and hp[uid] * 4 <= unit_tbl[utype[uid]]["hp"]:
            routed[uid] = 1

    def line_blocked(x0, y0, x1, y1):
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
            if x0 == x1 and y0 == y1:
                return False
            if cell(x0, y0)["blocks_los"] or (x0, y0) in occupied:
                return True

    def legal_attack(auid, buid):
        if auid not in alive or buid not in alive:
            return False
        if auid[0] == buid[0] or routed[auid]:
            return False
        ax, ay = pos_x[auid], pos_y[auid]
        bx, by = pos_x[buid], pos_y[buid]
        dist = abs(ax - bx) + abs(ay - by)
        if dist == 1:
            return True
        if dist < 2 or "ranged" not in tags_of[utype[auid]]:
            return False
        if dist > unit_tbl[utype[auid]]["range"] + cell(ax, ay)["range_bonus"]:
            return False
        return not line_blocked(ax, ay, bx, by)

    def make_roller(phase):
        def roll(sides):
            nonlocal rng_state
            limit = span - span % sides
            while True:
                rng_state = (rng_state * multiplier + increment) & state_mask
                draws[phase] += 1
                sample = (rng_state >> output_shift) & sample_mask
                if sample < limit:
                    return 1 + sample % sides
        return roll

    roll_attack = make_roller("attack")
    roll_damage = make_roller("damage")
    roll_reaction = make_roller("reaction")

    braced = set()
    armed = set()

    def strike(auid, buid, reaction):
        if not legal_attack(auid, buid):
            return
        roll_hit = roll_reaction if reaction else roll_attack
        roll_dmg = roll_reaction if reaction else roll_damage
        atype = utype[auid]
        btype = utype[buid]
        astats = unit_tbl[atype]
        bstats = unit_tbl[btype]
        ax, ay = pos_x[auid], pos_y[auid]
        bx, by = pos_x[buid], pos_y[buid]
        neighbours = ((bx + 1, by), (bx - 1, by), (bx, by + 1), (bx, by - 1))
        pinned = (abs(ax - bx) + abs(ay - by) == 1
                  and "ranged" in tags_of[atype])
        attack_bonus = astats["atk"] - (pinned_penalty if pinned else 0)
        flank = 0
        if abs(ax - bx) + abs(ay - by) == 1:
            side = auid[0]
            for key in neighbours:
                other = occupied.get(key)
                if other is not None and other != auid and other[0] == side:
                    flank += 1
            if flank > flank_cap:
                flank = flank_cap
        defence = bstats["def"] + cell(bx, by)["def"]
        if "pike" in tags_of[btype]:
            side = buid[0]
            for key in neighbours:
                other = occupied.get(key)
                if (other is not None and other != buid and other[0] == side
                        and "pike" in tags_of[utype[other]]):
                    defence += shield_wall_bonus
                    break
        if buid in braced:
            defence += brace_bonus
        if routed[buid]:
            defence -= rout_penalty

        value = roll_hit(D20_SIDES)
        crit = value == crit_roll
        if not crit and value + attack_bonus + flank < hit_target + defence:
            return
        count, sides, bonus = astats["dice"]
        if crit:
            count *= 2
        total = bonus
        for _ in range(count):
            total += roll_dmg(sides)
        num, den = tables.advantage(atype, btype)
        dealt = (total * num) // den - bstats["armour"]
        if dealt < min_damage:
            dealt = min_damage
        damage_credit[atype] = damage_credit.get(atype, 0) + dealt
        hp[buid] -= dealt
        if hp[buid] <= 0:
            remove(buid)
            kill_credit[atype] = kill_credit.get(atype, 0) + 1
            return
        if "poison" in tags_of[atype]:
            poison[buid] = poison_turns
        rout_check(buid)

    for index, block in enumerate(match.blocks):
        # Side rotation, the ruleset 2 reseed and the digest all run on the
        # one based position of the block, not on its printed number: the
        # reseed state recorded by every keyframe of a match whose printed
        # numbers skip resolves to the ordinal.  The printed number is what a
        # divergence records (section 7).
        turn = index + 1

        if block.keyframe is not None:
            kf_rng, kf_c0, kf_c1, kf_units = block.keyframe
            observed = [(uid, pos_x[uid], pos_y[uid], hp[uid], poison[uid],
                         routed[uid]) for uid in roster_order if uid in alive]
            if (rng_state != kf_rng or control[0] != kf_c0
                    or control[1] != kf_c1 or observed != kf_units):
                divergences.append(block.n)
            rng_state = kf_rng
            control[0] = kf_c0
            control[1] = kf_c1
            place_all(kf_units)

        if reseeds:
            rng_state = match.seed ^ ((turn * reseed_multiplier) & MASK32)

        effective = effective_orders(slots_by_block[index])[0]

        init_of = {}
        for uid in alive:
            stats = unit_tbl[utype[uid]]
            init_of[uid] = stats["init"] - (stats["hp"] - hp[uid]) // 3
        a_rank = 0 if turn % 2 == 1 else 1
        exec_order = sorted(
            alive,
            key=lambda u: (-init_of[u],
                           a_rank if u[0] == "A" else 1 - a_rank,
                           int(u[1:])))

        braced.clear()
        armed.clear()
        for uid, order in effective.items():
            if uid in alive:
                if order.verb == HOLD:
                    braced.add(uid)
                elif order.verb == READY:
                    armed.add(uid)
        reacted = set()

        for uid in exec_order:
            if uid not in alive:
                continue
            order = effective.get(uid)
            if order is None:
                continue
            verb = order.verb
            if verb == ATTACK:
                if order.target in alive:
                    strike(uid, order.target, False)
                continue
            if verb != MOVE:
                continue

            stats = unit_tbl[utype[uid]]
            points = stats["move"]
            klass = stats["class"]
            skirmisher = "skirmisher" in tags_of[utype[uid]]
            side = uid[0]
            x, y = pos_x[uid], pos_y[uid]
            moved = False
            for wx, wy in order.path:
                if abs(wx - x) + abs(wy - y) != 1:
                    break
                if not (0 <= wx < width and 0 <= wy < height):
                    break
                cost = cell(wx, wy)["cost"].get(klass)
                if cost is None or cost > points or (wx, wy) in occupied:
                    break
                if occupied.get((x, y)) == uid:
                    del occupied[(x, y)]
                x, y = wx, wy
                occupied[(x, y)] = uid
                pos_x[uid] = x
                pos_y[uid] = y
                points -= cost
                moved = True
                if not skirmisher:
                    adjacent_enemy = False
                    for key in ((x + 1, y), (x - 1, y), (x, y + 1),
                                (x, y - 1)):
                        other = occupied.get(key)
                        if other is not None and other[0] != side:
                            adjacent_enemy = True
                            break
                    if adjacent_enemy:
                        break
            if not moved:
                continue
            for ruid in exec_order:
                if uid not in alive:
                    break
                if ruid not in alive or ruid[0] == side:
                    continue
                if ruid not in armed or ruid in reacted:
                    continue
                if not legal_attack(ruid, uid):
                    continue
                strike(ruid, uid, True)
                reacted.add(ruid)

        for uid in roster_order:
            if uid in alive and poison[uid] > 0:
                hp[uid] -= 1
                poison[uid] -= 1
                if hp[uid] <= 0:
                    remove(uid)
                else:
                    rout_check(uid)

        for ox, oy in objectives:
            sides = 0
            for key in ((ox, oy), (ox + 1, oy), (ox - 1, oy), (ox, oy + 1),
                        (ox, oy - 1)):
                other = occupied.get(key)
                if other is not None:
                    sides |= 1 if other[0] == "A" else 2
            if sides == 1:
                control[0] += 1
            elif sides == 2:
                control[1] += 1

        digests.append(digest(turn))

    survivors = []
    score = [control[0] * control_points, control[1] * control_points]
    live_a = 0
    live_b = 0
    for uid in roster_order:
        if uid in alive:
            survivors.append([uid, pos_x[uid], pos_y[uid], hp[uid]])
            cost = unit_tbl[utype[uid]]["cost"]
            if uid[0] == "A":
                live_a += 1
                score[0] += cost
            else:
                live_b += 1
                score[1] += cost

    if live_a and not live_b:
        winner_side = 0
    elif live_b and not live_a:
        winner_side = 1
    elif not live_a and not live_b:
        winner_side = None
    elif score[0] > score[1]:
        winner_side = 0
    elif score[1] > score[0]:
        winner_side = 1
    else:
        winner_side = None

    out = Replay()
    out.digests = digests
    out.control = [control[0], control[1]]
    out.survivors = survivors
    out.score = score
    out.winner_side = winner_side
    out.draws = draws
    out.damage = damage_credit
    out.kills = kill_credit
    out.divergences = divergences
    return out


# --------------------------------------------------------------- amendments
def fingerprint(digests):
    return fnv1a("".join("%d:%s;" % (i, d) for i, d in enumerate(digests)))


def run_match(match, tables):
    """Replay a closed match and apply its amendment tail (section 16)."""
    slots = [list(block.slots) for block in match.blocks]
    version = replay_match(match, tables, slots)
    audits = []
    counters = {"applied": 0, "stale": 0, "unknown": 0}
    revisions = {}
    unit_types = tables.unit_types

    for turn_ordinal, slot, expected, order in match.amendments:
        if order is not None and (
                order.uid not in match.roster
                or (order.verb == ATTACK
                    and order.target not in match.roster)):
            counters["unknown"] += 1
            continue
        address = (turn_ordinal, slot)
        current = revisions.get(address, 0)
        if current != expected:
            counters["stale"] += 1
            continue
        slots[turn_ordinal - 1][slot - 1] = order
        revisions[address] = current + 1
        counters["applied"] += 1
        updated = replay_match(match, tables, slots)

        before = version.digests
        after = updated.digests
        audits.append({
            "turn": turn_ordinal,
            "slot": slot,
            "revision": current + 1,
            "before": fingerprint(before),
            "after": fingerprint(after),
            "changed": [i for i in range(len(before))
                        if before[i] != after[i]],
            "draws_delta": dict(
                (phase, updated.draws[phase] - version.draws[phase])
                for phase in PHASES),
            "damage_delta": dict(
                (name, updated.damage.get(name, 0) - version.damage.get(name, 0))
                for name in unit_types),
            "kills_delta": dict(
                (name, updated.kills.get(name, 0) - version.kills.get(name, 0))
                for name in unit_types),
            "divergences_before": list(version.divergences),
            "divergences_after": list(updated.divergences),
        })
        version = updated

    late = 0
    superseded = 0
    for block_slots in slots:
        _effective, block_late, block_superseded = effective_orders(
            block_slots)
        late += block_late
        superseded += block_superseded

    return version, audits, counters, late, superseded


# ------------------------------------------------------------------- ladder
def run_ladder(tables, played):
    ladder = tables.ladder
    win_base = ladder["win_base"]
    win_divisor = ladder["win_divisor"]
    win_min = ladder["win_min"]
    win_max = ladder["win_max"]
    draw_divisor = ladder["draw_divisor"]
    draw_cap = ladder["draw_cap"]

    rating = {}
    record = {}

    def ensure(pid):
        if pid not in rating:
            rating[pid] = tables.players.get(pid, 0)
            record[pid] = [0, 0, 0, 0]   # played, won, drawn, lost

    for p0, p1, winner_side in played:
        ensure(p0)
        ensure(p1)
        record[p0][0] += 1
        record[p1][0] += 1
        if winner_side is None:
            record[p0][2] += 1
            record[p1][2] += 1
            if rating[p0] >= rating[p1]:
                high, low = p0, p1
            else:
                high, low = p1, p0
            gift = (rating[high] - rating[low]) // draw_divisor
            if gift > draw_cap:
                gift = draw_cap
            rating[high] -= gift
            rating[low] += gift
        else:
            winner = p0 if winner_side == 0 else p1
            loser = p1 if winner_side == 0 else p0
            record[winner][1] += 1
            record[loser][3] += 1
            delta = win_base + (rating[loser] - rating[winner]) // win_divisor
            if delta < win_min:
                delta = win_min
            elif delta > win_max:
                delta = win_max
            rating[winner] += delta
            rating[loser] -= delta

    rows = []
    for pid in sorted(rating, key=lambda p: (-rating[p], p)):
        played_n, won, drawn, lost = record[pid]
        rows.append({"player": pid, "rating": rating[pid],
                     "played": played_n, "won": won, "drawn": drawn,
                     "lost": lost})
    return rows


# -------------------------------------------------------------------- main
def process_scenario(name, data_dir, tables):
    parsed = parse_log(os.path.join(data_dir, "replays_%s.log" % name),
                       tables)

    entries = []
    played = []
    divergences = []
    turns_total = 0
    late_total = 0
    superseded_total = 0
    draws_total = {"attack": 0, "damage": 0, "reaction": 0}
    amend_total = {"applied": 0, "stale": 0, "unknown": 0}
    deployed = {}
    damage_total = {}
    kills_total = {}

    for match in parsed.matches:
        if not match.closed:
            continue
        version, audits, counters, late, superseded = run_match(match, tables)
        turns_total += len(match.blocks)
        late_total += late
        superseded_total += superseded
        for phase in PHASES:
            draws_total[phase] += version.draws[phase]
        for key in amend_total:
            amend_total[key] += counters[key]
        for _uid, utype, _x, _y in match.deploy:
            deployed[utype] = deployed.get(utype, 0) + 1
        for utype, value in version.damage.items():
            damage_total[utype] = damage_total.get(utype, 0) + value
        for utype, value in version.kills.items():
            kills_total[utype] = kills_total.get(utype, 0) + value
        for turn in version.divergences:
            divergences.append([match.mid, turn])

        players = [match.p0, match.p1]
        side = version.winner_side
        entries.append({
            "id": match.mid,
            "map": match.map_name,
            "players": players,
            "turns": len(match.blocks),
            "digests": version.digests,
            "control": version.control,
            "survivors": version.survivors,
            "score": version.score,
            "winner": None if side is None else players[side],
            "amendments": audits,
        })
        played.append((match.p0, match.p1, side))

    dominant = PHASES[0]
    for phase in sorted(PHASES):
        if draws_total[phase] > draws_total[dominant]:
            dominant = phase

    scenario = {
        "scenario": name,
        "source": "replays_%s.log" % name,
        "matches": entries,
        "standings": run_ladder(tables, played),
    }
    perf = {
        "matches": len(entries),
        "turns": turns_total,
        "orders_total": parsed.orders_total,
        "orders_late": late_total,
        "orders_superseded": superseded_total,
    }
    bottleneck = {
        "draws_by_phase": dict(draws_total),
        "dominant_phase": dominant,
    }
    quality = {
        "malformed_lines": parsed.malformed_lines,
        "unknown_unit_orders": parsed.unknown_unit_orders,
        "divergences": divergences,
        "amendments": dict(amend_total),
    }
    return scenario, perf, bottleneck, quality, (deployed, damage_total,
                                                 kills_total)


def write_json(out_dir, name, payload):
    with open(os.path.join(out_dir, name), "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: optimize.py <data_dir> <out_dir>\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    tables = Tables(data_dir)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    perf = {}
    bottlenecks = {}
    quality = {}
    deployed = {}
    damage = {}
    kills = {}

    for name in SCENARIOS:
        scenario, stats, bottleneck, qual, totals = process_scenario(
            name, data_dir, tables)
        write_json(out_dir, "scenario_%s.json" % name, scenario)
        perf[name] = stats
        bottlenecks[name] = bottleneck
        quality[name] = qual
        for store, source in zip((deployed, damage, kills), totals):
            for key, value in source.items():
                store[key] = store.get(key, 0) + value

    nerf_at = tables.balance["nerf_at"]
    buff_at = tables.balance["buff_at"]
    units = {}
    for utype in tables.unit_types:
        count = deployed.get(utype, 0)
        dealt = damage.get(utype, 0)
        cost = tables.units[utype]["cost"]
        per_cost = (dealt * 1000) // (count * cost) if count else 0
        if per_cost >= nerf_at:
            verdict = "nerf"
        elif per_cost <= buff_at:
            verdict = "buff"
        else:
            verdict = "hold"
        units[utype] = {"deployed": count, "damage_dealt": dealt,
                        "kills": kills.get(utype, 0),
                        "per_cost_permille": per_cost, "verdict": verdict}

    write_json(out_dir, "perf_report.json", {"scenarios": perf})
    write_json(out_dir, "bottleneck_analysis.json", {"scenarios": bottlenecks})
    write_json(out_dir, "recommendations.json", {"units": units})
    write_json(out_dir, "data_quality.json", {"scenarios": quality})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
