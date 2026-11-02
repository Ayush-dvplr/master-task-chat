#!/usr/bin/env python3
"""Brassmoor Skirmish replay engine.

Usage: python3 optimize.py <data_dir> <out_dir>

Reads the rule tables, the map atlas, the player list and the five replay
logs from <data_dir>, replays every match under the season 5 rules (rule
book plus errata), and writes the nine JSON reports into <out_dir>.
Standard library only.
"""

# allow: SIZE_OK - the bundle requires a single self-contained replay executable.

import json
import sys
from pathlib import Path

SCENARIO_NAMES = ("visible", "peak", "steady", "burst", "latency")
NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))
HEX_DIGITS = set("0123456789abcdef")
PHASES = ("attack", "damage", "reaction")


# ------------------------------------------------------------------ tables

class Rules:
    """All numeric parameters, read from the data directory."""

    def __init__(self, data_dir: Path):
        self.units = json.loads((data_dir / "units.json").read_text())["units"]
        self.terrain = json.loads((data_dir / "terrain.json").read_text())["terrain"]
        adv = json.loads((data_dir / "advantage.json").read_text())
        self.adv_default = tuple(adv["default"])
        self.advantage = {(p["attacker"], p["defender"]): (p["num"], p["den"]) for p in adv["pairs"]}
        conf = json.loads((data_dir / "rulesets.json").read_text())
        self.rulesets = conf["rulesets"]
        dice = conf["dice"]
        self.lcg_mul = dice["multiplier"]
        self.lcg_inc = dice["increment"]
        self.lcg_mask = (1 << dice["modulus_bits"]) - 1
        self.out_shift = dice["output_shift"]
        self.out_span = 1 << dice["output_bits"]
        self.combat = conf["combat"]
        self.poison_turns = conf["status"]["poison_turns"]
        self.control_points = conf["scoring"]["control_points"]
        self.ladder = conf["ladder"]
        self.balance = conf["balance"]
        roster = json.loads((data_dir / "players.json").read_text())["players"]
        self.players = [(p["id"], p["rating"]) for p in roster]
        self.maps = read_atlas((data_dir / "maps.txt").read_text())

    def ratio(self, attacker_type, defender_type):
        return self.advantage.get((attacker_type, defender_type), self.adv_default)


def read_atlas(text):
    atlas = {}
    block = None
    for line in text.splitlines():
        if line.startswith("MAP "):
            parts = line.split()
            block = {"name": parts[1], "w": int(parts[2]), "h": int(parts[3]), "rows": []}
        elif line == "ENDMAP":
            atlas[block["name"]] = block
            block = None
        elif block is not None:
            block["rows"].append(line)
    return atlas


# ------------------------------------------------------------------ log grammar

def is_unit_id(tok):
    return len(tok) > 1 and tok[0] in ("A", "B") and tok[1:].isdigit() and tok[1] != "0"


def is_count(tok):
    if not tok.isdigit():
        return False
    return tok == "0" or not tok.startswith("0")


def is_hex8(tok):
    return len(tok) == 8 and set(tok) <= HEX_DIGITS


def read_order(parts):
    head = parts[0]
    if head == "O":
        lag = 0
    elif len(head) == 3 and head[:2] == "O~" and head[2] in "123456789":
        lag = int(head[2])
    else:
        return None
    if len(parts) < 3 or not is_unit_id(parts[1]):
        return None
    issuer, verb, rest = parts[1], parts[2], parts[3:]
    if verb in ("HOLD", "READY"):
        return {"lag": lag, "unit": issuer, "verb": verb} if not rest else None
    if verb == "ATTACK":
        if len(rest) == 1 and is_unit_id(rest[0]):
            return {"lag": lag, "unit": issuer, "verb": verb, "target": rest[0]}
        return None
    if verb == "MOVE" and rest:
        path = []
        for cell in rest:
            xy = cell.split(",")
            if len(xy) != 2 or not (is_count(xy[0]) and is_count(xy[1])):
                return None
            path.append((int(xy[0]), int(xy[1])))
        return {"lag": lag, "unit": issuer, "verb": verb, "path": path}
    return None


def read_keyframe(parts):
    if len(parts) < 4 or not is_count(parts[1]):
        return None
    if not parts[2].startswith("rng=") or not is_hex8(parts[2][4:]):
        return None
    if not parts[3].startswith("cp="):
        return None
    cp = parts[3][3:].split(",")
    if len(cp) != 2 or not all(is_count(c) for c in cp):
        return None
    listed = []
    for item in parts[4:]:
        uid, at, rest = item.partition("@")
        if not at or not is_unit_id(uid):
            return None
        fields = rest.split(",")
        if len(fields) != 5 or not all(is_count(f) for f in fields) or fields[4] not in ("0", "1"):
            return None
        listed.append((uid,) + tuple(int(f) for f in fields))
    return {"rng": int(parts[2][4:], 16), "cp": (int(cp[0]), int(cp[1])), "units": listed}


def read_header(parts):
    if len(parts) != 9:
        return None
    fields = {}
    for item in parts[2:]:
        key, eq, val = item.partition("=")
        if eq:
            fields[key] = val
    if len(fields) != 7:
        return None
    for key in ("map", "p0", "p1"):
        if key not in fields:
            return None
    if fields.get("v") not in ("1", "2") or fields.get("rules") not in ("1", "2"):
        return None
    if not is_hex8(fields.get("seed", "")) or not is_count(fields.get("turns", "-")):
        return None
    return {
        "id": parts[1], "version": int(fields["v"]), "ruleset": fields["rules"], "map": fields["map"],
        "seed": int(fields["seed"], 16), "players": [fields["p0"], fields["p1"]], "units": [], "turns": [],
        "amendments": [], "tail": False,
    }


def names_roster_units(order, roster):
    return order["unit"] in roster and order.get("target", order["unit"]) in roster


def read_log(text, unit_types):
    matches = []
    stats = {"malformed": 0, "unknown": 0, "orders": 0}
    match = None
    turn = None
    for raw in text.split("\n"):
        line = raw.strip()
        if line == "" or line[0] == "#":
            continue
        parts = line.split(" ")
        head = parts[0]
        accepted = False
        if head == "MATCH":
            if match is None:
                match = read_header(parts)
                turn = None
                accepted = match is not None
        elif match is None:
            accepted = False
        elif head == "R":
            if len(parts) >= 5 and all(is_count(p) for p in parts[1:4]):
                ordinal, slot, revision = map(int, parts[1:4])
                payload = None if parts[4:] == ["DROP"] else read_order(parts[4:])
                if (1 <= ordinal <= len(match["turns"])
                        and 1 <= slot <= len(match["turns"][ordinal - 1]["orders"])
                        and (parts[4:] == ["DROP"] or payload is not None)):
                    match["amendments"].append((ordinal, slot, revision, payload))
                    match["tail"] = True
                    accepted = True
        elif match["tail"] and head != "END":
            accepted = False
        elif head == "U":
            if (len(parts) == 5 and not match["turns"] and is_unit_id(parts[1]) and parts[2] in unit_types
                    and is_count(parts[3]) and is_count(parts[4])):
                match["units"].append((parts[1], parts[2], int(parts[3]), int(parts[4])))
                accepted = True
        elif head == "T":
            if len(parts) == 2 and is_count(parts[1]):
                turn = {"n": int(parts[1]), "key": None, "orders": []}
                match["turns"].append(turn)
                accepted = True
        elif head == "K":
            if turn is not None and turn["key"] is None and not turn["orders"]:
                frame = read_keyframe(parts)
                if frame is not None:
                    turn["key"] = frame
                    accepted = True
        elif head == "END":
            if len(parts) == 2 and parts[1] == match["id"]:
                matches.append(match)
                match = None
                turn = None
                accepted = True
        elif head.startswith("O") and turn is not None:
            order = read_order(parts)
            if order is not None:
                accepted = True
                roster = {u[0] for u in match["units"]}
                if not names_roster_units(order, roster):
                    stats["unknown"] += 1
                else:
                    stats["orders"] += 1
                    turn["orders"].append(order)
        if not accepted:
            stats["malformed"] += 1
    return matches, stats


def resolve_orders(orders):
    """Pick one effective order per unit. Returns (effective, late, superseded)."""
    grouped = {}
    for order in orders:
        grouped.setdefault(order["unit"], []).append(order)
    effective = {}
    late = 0
    superseded = 0
    for uid, mine in grouped.items():
        fresh = [o for o in mine if o["lag"] == 0]
        lag_one = [o for o in mine if o["lag"] == 1]
        late += sum(1 for o in mine if o["lag"] >= 2)
        candidates = fresh if fresh else lag_one
        if candidates:
            effective[uid] = candidates[-1]
            superseded += len(fresh) + len(lag_one) - 1
    return effective, late, superseded


# ------------------------------------------------------------------ engine

class Piece:
    def __init__(self, uid, kind, stats, x, y):
        self.uid = uid
        self.kind = kind
        self.stats = stats
        self.team = 0 if uid[0] == "A" else 1
        self.number = int(uid[1:])
        self.x = x
        self.y = y
        self.hp = stats["hp"]
        self.poison = 0
        self.routed = 0

    def order_key(self):
        return (self.team, self.number)

    def has(self, tag):
        return tag in self.stats["tags"]


def fnv1a(text):
    value = 2166136261
    for byte in text.encode("ascii"):
        value ^= byte
        value = (value * 16777619) % 4294967296
    return format(value, "08x")


class Battle:
    def __init__(self, rules, match):
        self.rules = rules
        self.match = match
        board = rules.maps[match["map"]]
        self.width = board["w"]
        self.height = board["h"]
        self.grid = board["rows"]
        self.bottom_origin = match["version"] == 2
        self.state = match["seed"]
        self.control = [0, 0]
        self.pieces = {}
        self.where = {}
        for uid, kind, x, y in match["units"]:
            self.place(Piece(uid, kind, rules.units[kind], x, self.canon_y(y)))
        self.objectives = [(x, y) for y in range(self.height) for x in range(self.width)
                           if rules.terrain[self.grid[y][x]]["objective"]]
        self.draw_counts = dict.fromkeys(PHASES, 0)
        self.current_phase = "attack"
        self.damage_by_kind = {}
        self.kills_by_kind = {}
        self.braced = set()
        self.armed = set()
        self.spent = set()

    # geometry -----------------------------------------------------------
    def canon_y(self, y):
        return self.height - 1 - y if self.bottom_origin else y

    def place(self, piece):
        self.pieces[piece.uid] = piece
        self.where[(piece.x, piece.y)] = piece

    def take_off(self, piece):
        self.pieces.pop(piece.uid)
        self.where.pop((piece.x, piece.y))

    def tile(self, x, y):
        return self.rules.terrain[self.grid[y][x]]

    def neighbours(self, x, y):
        for dx, dy in NEIGHBOURS:
            other = self.where.get((x + dx, y + dy))
            if other is not None:
                yield other

    def roster(self):
        return sorted(self.pieces.values(), key=Piece.order_key)

    # dice ---------------------------------------------------------------
    def draw(self, sides):
        cutoff = self.rules.out_span - self.rules.out_span % sides
        while True:
            self.state = (self.state * self.rules.lcg_mul + self.rules.lcg_inc) & self.rules.lcg_mask
            self.draw_counts[self.current_phase] += 1
            sample = (self.state >> self.rules.out_shift) % self.rules.out_span
            if sample < cutoff:
                return sample % sides + 1

    # state io -----------------------------------------------------------
    def fingerprint(self, turn_no):
        text = "t=%d;rng=%08x;cp=%d,%d;" % (turn_no, self.state, self.control[0], self.control[1])
        for p in self.roster():
            text += "%s@%d,%d,%d,%d,%d;" % (p.uid, p.x, p.y, p.hp, p.poison, p.routed)
        return fnv1a(text)

    def sync(self, frame):
        """Adopt a keyframe. Returns True when the engine state differed."""
        wanted = [(uid, x, self.canon_y(y), hp, pz, rt) for uid, x, y, hp, pz, rt in frame["units"]]
        current = [(p.uid, p.x, p.y, p.hp, p.poison, p.routed) for p in self.roster()]
        differs = (self.state != frame["rng"] or tuple(self.control) != frame["cp"] or current != wanted)
        kinds = {uid: kind for uid, kind, _, _ in self.match["units"]}
        old = self.pieces
        self.pieces = {}
        self.where = {}
        for uid, x, y, hp, pz, rt in wanted:
            piece = old.get(uid) or Piece(uid, kinds[uid], self.rules.units[kinds[uid]], x, y)
            piece.x, piece.y, piece.hp, piece.poison, piece.routed = x, y, hp, pz, rt
            self.place(piece)
        self.state = frame["rng"]
        self.control = list(frame["cp"])
        return differs

    def start_turn(self, turn_no):
        ruleset = self.rules.rulesets[self.match["ruleset"]]
        if ruleset["reseed"]:
            self.state = (self.match["seed"] ^ (turn_no * ruleset["reseed_multiplier"])) & self.rules.lcg_mask

    # combat -------------------------------------------------------------
    def attack_kind(self, attacker, target):
        if attacker.uid not in self.pieces or target.uid not in self.pieces:
            return None
        if attacker.team == target.team or attacker.routed:
            return None
        gap = abs(attacker.x - target.x) + abs(attacker.y - target.y)
        shooter = attacker.has("ranged")
        if gap == 1:
            return "pinned" if shooter else "melee"
        if not shooter or gap < 2:
            return None
        if gap > attacker.stats["range"] + self.tile(attacker.x, attacker.y)["range_bonus"]:
            return None
        return "ranged" if self.sight_line(attacker, target) else None

    def sight_line(self, a, b):
        x, y = a.x, a.y
        span_x = abs(b.x - x)
        span_y = -abs(b.y - y)
        step_x = 1 if x < b.x else -1
        step_y = 1 if y < b.y else -1
        error = span_x + span_y
        while True:
            twice = error * 2
            if twice >= span_y:
                error += span_y
                x += step_x
            if twice <= span_x:
                error += span_x
                y += step_y
            if (x, y) == (b.x, b.y):
                return True
            if self.tile(x, y)["blocks_los"] or (x, y) in self.where:
                return False

    def defence(self, target):
        c = self.rules.combat
        value = target.stats["def"] + self.tile(target.x, target.y)["def"]
        if target.has("pike") and any(o.team == target.team and o.has("pike") for o in self.neighbours(target.x, target.y)):
            value += c["shield_wall_bonus"]
        if target.uid in self.braced:
            value += c["brace_bonus"]
        if target.routed:
            value -= c["rout_penalty"]
        return value

    def check_rout(self, piece):
        if not piece.routed and piece.hp * 4 <= piece.stats["hp"]:
            piece.routed = 1

    def resolve_attack(self, attacker, target, kind, reaction):
        c = self.rules.combat
        self.current_phase = "reaction" if reaction else "attack"
        roll = self.draw(20)
        critical = roll == c["crit_roll"]
        if not critical:
            flank = 0
            if kind != "ranged":
                helpers = [o for o in self.neighbours(target.x, target.y) if o.team == attacker.team and o is not attacker]
                flank = min(c["flank_cap"], len(helpers))
            attack = attacker.stats["atk"] - (c["pinned_penalty"] if kind == "pinned" else 0)
            if roll + attack + flank < c["hit_target"] + self.defence(target):
                return
        if not reaction:
            self.current_phase = "damage"
        count, sides, bonus = attacker.stats["dice"]
        if critical:
            count *= 2
        total = bonus + sum(self.draw(sides) for _ in range(count))
        num, den = self.rules.ratio(attacker.kind, target.kind)
        harm = max(c["min_damage"], total * num // den - target.stats["armour"])
        target.hp -= harm
        self.damage_by_kind[attacker.kind] = self.damage_by_kind.get(attacker.kind, 0) + harm
        if target.hp <= 0:
            self.take_off(target)
            self.kills_by_kind[attacker.kind] = self.kills_by_kind.get(attacker.kind, 0) + 1
            return
        if attacker.has("poison"):
            target.poison = self.rules.poison_turns
        self.check_rout(target)

    # movement -----------------------------------------------------------
    def walk(self, piece, path, sequence):
        budget = piece.stats["move"]
        column = piece.stats["class"]
        moved = 0
        for px, raw_y in path:
            py = self.canon_y(raw_y)
            if abs(px - piece.x) + abs(py - piece.y) != 1:
                break
            if not (0 <= px < self.width and 0 <= py < self.height):
                break
            cost = self.tile(px, py)["cost"][column]
            if cost is None or cost > budget or (px, py) in self.where:
                break
            budget -= cost
            self.where.pop((piece.x, piece.y))
            piece.x, piece.y = px, py
            self.where[(px, py)] = piece
            moved += 1
            if not piece.has("skirmisher") and any(o.team != piece.team for o in self.neighbours(px, py)):
                break
        if moved == 0:
            return
        for watcher in sequence:
            if piece.uid not in self.pieces:
                break
            if watcher.team == piece.team or watcher.uid in self.spent:
                continue
            if watcher.uid not in self.armed or watcher.uid not in self.pieces:
                continue
            kind = self.attack_kind(watcher, piece)
            if kind is not None:
                self.spent.add(watcher.uid)
                self.resolve_attack(watcher, piece, kind, True)

    # turn ---------------------------------------------------------------
    def play_turn(self, turn_no, orders):
        effective, _, _ = resolve_orders(orders)
        initiative = {p.uid: p.stats["init"] - (p.stats["hp"] - p.hp) // 3 for p in self.pieces.values()}
        first_team = 0 if turn_no % 2 == 1 else 1
        sequence = sorted(self.pieces.values(),
                          key=lambda p: (-initiative[p.uid], 0 if p.team == first_team else 1, p.number))
        self.braced = {u for u, o in effective.items() if o["verb"] == "HOLD" and u in self.pieces}
        self.armed = {u for u, o in effective.items() if o["verb"] == "READY" and u in self.pieces}
        self.spent = set()
        for piece in sequence:
            if piece.uid not in self.pieces or piece.uid not in effective:
                continue
            order = effective[piece.uid]
            if order["verb"] == "MOVE":
                self.walk(piece, order["path"], sequence)
            elif order["verb"] == "ATTACK":
                target = self.pieces.get(order["target"])
                if target is None:
                    continue
                kind = self.attack_kind(piece, target)
                if kind is not None:
                    self.resolve_attack(piece, target, kind, False)
        for piece in self.roster():
            if piece.poison > 0:
                piece.hp -= 1
                piece.poison -= 1
                if piece.hp <= 0:
                    self.take_off(piece)
                else:
                    self.check_rout(piece)
        for ox, oy in self.objectives:
            present = set()
            holder = self.where.get((ox, oy))
            if holder is not None:
                present.add(holder.team)
            for other in self.neighbours(ox, oy):
                present.add(other.team)
            if len(present) == 1:
                self.control[present.pop()] += 1
        self.braced, self.armed, self.spent = set(), set(), set()
        return self.fingerprint(turn_no)


# ------------------------------------------------------------------ reports

def replay_match(rules, match):
    battle = Battle(rules, match)
    prints = [battle.fingerprint(0)]
    diverged = []
    for turn in match["turns"]:
        if turn["key"] is not None and battle.sync(turn["key"]):
            diverged.append(turn["n"])
        battle.start_turn(turn["n"])
        prints.append(battle.play_turn(turn["n"], [o for o in turn["orders"] if o is not None]))
    return battle, prints, diverged


def history_fingerprint(digests):
    return fnv1a("".join(f"{i}:{d};" for i, d in enumerate(digests)))


def recover_match(rules, match):
    view = dict(match)
    view["turns"] = [dict(t, orders=list(t["orders"])) for t in match["turns"]]
    revisions = [[0] * len(t["orders"]) for t in view["turns"]]
    roster = {u[0] for u in match["units"]}
    counts = {"applied": 0, "stale": 0, "unknown": 0}
    history = []
    previous = replay_match(rules, view)
    for ordinal, slot, expected, replacement in match["amendments"]:
        if replacement is not None and not names_roster_units(replacement, roster):
            counts["unknown"] += 1
            continue
        if revisions[ordinal - 1][slot - 1] != expected:
            counts["stale"] += 1
            continue
        revisions[ordinal - 1][slot - 1] += 1
        view["turns"][ordinal - 1]["orders"][slot - 1] = replacement
        current = replay_match(rules, view)
        old, before, old_divs = previous
        new, after, new_divs = current
        history.append({
            "turn": ordinal, "slot": slot, "revision": expected + 1,
            "before": history_fingerprint(before),
            "after": history_fingerprint(after),
            "changed": [i for i, (a, b) in enumerate(zip(before, after)) if a != b],
            "draws_delta": {p: new.draw_counts[p] - old.draw_counts[p] for p in PHASES},
            "damage_delta": {k: new.damage_by_kind.get(k, 0) - old.damage_by_kind.get(k, 0)
                             for k in sorted(rules.units)},
            "kills_delta": {k: new.kills_by_kind.get(k, 0) - old.kills_by_kind.get(k, 0)
                            for k in sorted(rules.units)},
            "divergences_before": old_divs, "divergences_after": new_divs,
        })
        counts["applied"] += 1
        previous = current
    return previous, view, history, counts


def final_result(rules, battle, players):
    alive = battle.roster()
    teams = sorted({p.team for p in alive})
    score = []
    for team in (0, 1):
        worth = sum(p.stats["cost"] for p in alive if p.team == team)
        score.append(battle.control[team] * rules.control_points + worth)
    if len(teams) == 1:
        winner = players[teams[0]]
    elif not teams or score[0] == score[1]:
        winner = None
    else:
        winner = players[0] if score[0] > score[1] else players[1]
    survivors = [[p.uid, p.x, p.y, p.hp] for p in alive]
    return score, winner, survivors


def run_ladder(rules, results):
    table = rules.ladder
    rating = dict(rules.players)
    record = {}
    for res in results:
        first, second = res["players"]
        for pid in (first, second):
            if pid not in record:
                record[pid] = {"played": 0, "won": 0, "drawn": 0, "lost": 0}
            record[pid]["played"] += 1
        champ = res["winner"]
        if champ is None:
            record[first]["drawn"] += 1
            record[second]["drawn"] += 1
            if rating[first] >= rating[second]:
                high, low = first, second
            else:
                high, low = second, first
            gift = min(table["draw_cap"], (rating[high] - rating[low]) // table["draw_divisor"])
            rating[high] -= gift
            rating[low] += gift
        else:
            loser = second if champ == first else first
            record[champ]["won"] += 1
            record[loser]["lost"] += 1
            swing = table["win_base"] + (rating[loser] - rating[champ]) // table["win_divisor"]
            swing = max(table["win_min"], min(table["win_max"], swing))
            rating[champ] += swing
            rating[loser] -= swing
    rows = []
    for pid, rec in record.items():
        rows.append({"player": pid, "rating": rating[pid], "played": rec["played"],
                     "won": rec["won"], "drawn": rec["drawn"], "lost": rec["lost"]})
    rows.sort(key=lambda r: (-r["rating"], r["player"]))
    return rows


def build_reports(data_dir: Path):
    rules = Rules(data_dir)
    unit_types = set(rules.units)
    deployed = dict.fromkeys(rules.units, 0)
    dealt = dict.fromkeys(rules.units, 0)
    kills = dict.fromkeys(rules.units, 0)
    docs = {}
    perf, bottleneck, quality = {}, {}, {}
    for name in SCENARIO_NAMES:
        source = "replays_%s.log" % name
        matches, stats = read_log((data_dir / source).read_text(), unit_types)
        rows = []
        phase_totals = dict.fromkeys(PHASES, 0)
        divergences = []
        late_total = 0
        superseded_total = 0
        turn_total = 0
        amendment_counts = {"applied": 0, "stale": 0, "unknown": 0}
        for match in matches:
            recovered, view, history, counts = recover_match(rules, match)
            battle, prints, diverged = recovered
            for key in amendment_counts:
                amendment_counts[key] += counts[key]
            for turn in view["turns"]:
                _, late, superseded = resolve_orders([o for o in turn["orders"] if o is not None])
                late_total += late
                superseded_total += superseded
            turn_total += len(match["turns"])
            for phase in PHASES:
                phase_totals[phase] += battle.draw_counts[phase]
            for kind, amount in battle.damage_by_kind.items():
                dealt[kind] += amount
            for kind, amount in battle.kills_by_kind.items():
                kills[kind] += amount
            for _, kind, _, _ in match["units"]:
                deployed[kind] += 1
            for turn_no in diverged:
                divergences.append([match["id"], turn_no])
            score, winner, survivors = final_result(rules, battle, match["players"])
            rows.append({
                "id": match["id"], "map": match["map"], "players": list(match["players"]),
                "turns": len(match["turns"]), "digests": prints, "control": list(battle.control),
                "survivors": survivors, "score": score, "winner": winner,
                "amendments": history,
            })
        docs["scenario_%s.json" % name] = {"scenario": name, "source": source, "matches": rows,
                                           "standings": run_ladder(rules, rows)}
        perf[name] = {"matches": len(matches), "turns": turn_total, "orders_total": stats["orders"],
                      "orders_late": late_total, "orders_superseded": superseded_total}
        top = min(PHASES, key=lambda ph: (-phase_totals[ph], ph))
        bottleneck[name] = {"draws_by_phase": phase_totals, "dominant_phase": top}
        quality[name] = {"malformed_lines": stats["malformed"], "unknown_unit_orders": stats["unknown"],
                         "divergences": divergences, "amendments": amendment_counts}
    verdicts = {}
    for kind, spec in rules.units.items():
        per_cost = dealt[kind] * 1000 // (deployed[kind] * spec["cost"]) if deployed[kind] else 0
        if per_cost >= rules.balance["nerf_at"]:
            verdict = "nerf"
        elif per_cost <= rules.balance["buff_at"]:
            verdict = "buff"
        else:
            verdict = "hold"
        verdicts[kind] = {"deployed": deployed[kind], "damage_dealt": dealt[kind], "kills": kills[kind],
                          "per_cost_permille": per_cost, "verdict": verdict}
    docs["perf_report.json"] = {"scenarios": perf}
    docs["bottleneck_analysis.json"] = {"scenarios": bottleneck}
    docs["recommendations.json"] = {"units": verdicts}
    docs["data_quality.json"] = {"scenarios": quality}
    return docs


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: optimize.py <data_dir> <out_dir>\n")
        return 2
    data_dir = Path(argv[1])
    out_dir = Path(argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, doc in build_reports(data_dir).items():
        (out_dir / filename).write_text(json.dumps(doc, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
