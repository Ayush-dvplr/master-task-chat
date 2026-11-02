#!/usr/bin/env python3
"""Usage rating aggregator for the metered cloud billing extract.

``aggregate(events_path, rules_path)`` rates one workload under its extract's rules and
returns the result object of the record dictionary. Run as
``optimize.py EVENTS_CSV RULES_JSON`` it prints that object as one JSON document.

Every call settles the extract's own configuration from its evidence. The rate card
leaves a family of candidate kind weights (kinds absent from the card stay open in the
weight box); a constraint search over those weights, pruning each weight's domain and
replaying the withdrawal journal account by account as the weights it needs are fixed,
leaves a few complete (weights, table) candidates, and the
standing journal, re-rated with no carry and floor 2000, keeps exactly one. The two legacy
rules are applied as recovered from the journals: a void withdraws a live row of its own
kind when its booked account has one (the largest metered charge, the latest of equal
charges), and otherwise the allowed row of another kind with the smallest metered charge
(the earliest of equal charges); premium standing is the least set of accounts whose
unwaived total, plus their waivable penalty when their sponsor holds standing, reaches
the premium floor times their number of ordinary rows. Control rows are rated 0/0, rows
are processed by (ts, integer row number), and errata compare integer erratum numbers.
"""
from __future__ import annotations

import csv
import json
import sys
from bisect import bisect_left
from fractions import Fraction
from math import gcd
from pathlib import Path
from typing import Any

sys.setrecursionlimit(20000)
MULTIPLIER = 1315423911
MASK = 0xFFFFFFFF
CONTROL_FLAGS = frozenset(("void", "revive"))
WEIGHT_LOW, WEIGHT_HIGH = 2, 40
JOURNAL_FLOOR = 2000


# ------------------------------------------------------------------ small readers

def _lines(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _document(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ------------------------------------------------------------------ kind weights and withdrawal configuration

def weight_system(kinds: list[str], card: list[dict[str, str]], figures: dict[str, int]):
    """Reduced form of the figure equations: the free kinds and, for every pivot kind, its
    weight as an affine function of the free ones (None when the figures are inconsistent)."""
    column = {kind: j for j, kind in enumerate(kinds)}
    batches = sorted(figures)
    where = {batch: i for i, batch in enumerate(batches)}
    system = [[Fraction(0)] * len(kinds) + [Fraction(int(figures[b]))] for b in batches]
    for line in card:
        system[where[line["batch"]]][column[line["kind"]]] += int(line["amount"]) * int(line["units"])
    lead: list[int] = []
    for col in range(len(kinds)):
        row = len(lead)
        pivot = next((i for i in range(row, len(system)) if system[i][col]), None)
        if pivot is None:
            continue
        system[row], system[pivot] = system[pivot], system[row]
        scale = system[row][col]
        system[row] = [value / scale for value in system[row]]
        for i, other in enumerate(system):
            if i != row and other[col]:
                factor = other[col]
                system[i] = [a - factor * b for a, b in zip(other, system[row])]
        lead.append(col)
    if any(r[-1] and not any(r[:-1]) for r in system):
        return None
    free = [c for c in range(len(kinds)) if c not in lead]
    pivots = [(col, system[i][-1], {f: system[i][f] for f in free if system[i][f]}) for i, col in enumerate(lead)]
    return free, pivots


def _choose(live: list[int], rows: list[dict[str, Any]], void_kind: str, weights: dict[str, int]) -> list[int]:
    """The rows a void may withdraw, in the withdrawal rule's order: first the rows of the
    void's own kind from the largest metered charge down, the latest of equal charges first;
    then the rows of other kinds from the smallest metered charge up, the earliest first."""
    own, other = [], []
    for i in live:
        row = rows[i]
        (own if row["kind"] == void_kind else other).append((row["amount"] * row["units"] * weights[row["kind"]], i))
    own.sort(reverse=True)
    other.sort()
    return [i for _, i in own] + [i for _, i in other]


def _account_extensions(rows: list[dict[str, Any]], table: dict[tuple[str, str], bool],
                        weights: dict[str, int]) -> list[dict[tuple[str, str], bool]]:
    """Every set of new table entries under which this journal account replays exactly."""
    found: list[dict[tuple[str, str], bool]] = []

    def step(j: int, live: list[int], taken: list[int], new: dict[tuple[str, str], bool]) -> None:
        if j == len(rows):
            alive = set(live)
            if all(r["state"] == ("live" if i in alive else "withdrawn")
                   for i, r in enumerate(rows) if r["flag"] not in CONTROL_FLAGS):
                found.append(dict(new))
            return
        row = rows[j]
        if row["flag"] == "revive":
            if taken and row["state"] == "applied":
                step(j + 1, live + [taken[-1]], taken[:-1], new)
            elif not taken and row["state"] == "orphan":
                step(j + 1, live, taken, new)
            return
        if row["flag"] != "void":
            step(j + 1, live + [j], taken, new)
            return
        order = _choose(live, rows, row["kind"], weights)

        def withdraw(i: int) -> None:
            if row["state"] == "applied":
                step(j + 1, [x for x in live if x != i], taken + [i], new)

        def walk(c: int) -> None:
            if c == len(order):
                if row["state"] == "orphan":
                    step(j + 1, live, taken, new)
                return
            target = order[c]
            pair = (row["kind"], rows[target]["kind"])
            allowed = True if pair[0] == pair[1] else table.get(pair, new.get(pair))
            if allowed is True:
                withdraw(target)
            elif allowed is False:
                walk(c + 1)
            else:
                new[pair] = True
                withdraw(target)
                new[pair] = False
                walk(c + 1)
                del new[pair]

        walk(0)

    step(0, [], [], {})
    return found


def withdrawal_candidates(kinds: list[str], card: list[dict[str, str]], figures: dict[str, int],
                          journal: list[list[dict[str, Any]]]):
    """Every (weights, table) that reproduces the figures and every withdrawal journal line.

    A constraint search over the free weights. Each free weight keeps a domain of the values
    still admissible; a pivot weight is computed once every free weight it depends on has a
    value, and a value is dropped from a domain as soon as a pivot it completes would leave
    the weight box or the integers. The search branches on the open weight with the fewest
    values left (ties: the one that lets the most journal accounts replay, then kind order),
    replays every account whose ordinary kinds all have weights by extending the table
    jointly, and prunes the open domains after every choice. Nothing is capped."""
    reduced = weight_system(kinds, card, figures)
    if reduced is None:
        return []
    free, pivots = reduced
    index = {kind: j for j, kind in enumerate(kinds)}
    needs = [frozenset(index[r["kind"]] for r in rows if r["flag"] not in CONTROL_FLAGS) for rows in journal]
    exact: dict[int, tuple[int, int, list[tuple[int, int]]]] = {}
    for col, rhs, coef in pivots:
        scale = rhs.denominator
        for c in coef.values():
            scale = scale * c.denominator // gcd(scale, c.denominator)
        exact[col] = (int(rhs * scale), scale, [(f, int(c * scale)) for f, c in coef.items()])
    depends = {col: frozenset(f for f, _ in exact[col][2]) for col, _, _ in pivots}
    values: dict[int, int] = {}

    def pivot_value(col: int) -> int | None:
        top, scale, terms = exact[col]
        for f, c in terms:
            top -= c * values[f]
        if top % scale or not WEIGHT_LOW <= top // scale <= WEIGHT_HIGH:
            return None
        return top // scale

    for col in depends:
        if not depends[col]:
            fixed = pivot_value(col)
            if fixed is None:
                return []
            values[col] = fixed

    waiting = {f: [col for col, deps in depends.items() if f in deps] for f in free}

    def narrow(f: int, domain: list[int]) -> list[int]:
        """The values of f under which no pivot that f alone still blocks leaves the box or the integers."""
        assigned = {g for g in free if g in values} | {f}
        due = [col for col in waiting[f] if col not in values and depends[col] <= assigned]
        if not due:
            return domain
        # each such pivot is (base - c * value) / scale, with base fixed by the weights already set
        lines = []
        for col in due:
            base, scale, terms = exact[col]
            c = 0
            for g, k in terms:
                if g == f:
                    c = k
                else:
                    base -= k * values[g]
            lines.append((base, c, scale))
        low, high = WEIGHT_LOW, WEIGHT_HIGH
        return [v for v in domain
                if all(not (base - c * v) % scale and low <= (base - c * v) // scale <= high for base, c, scale in lines)]

    domains = {f: narrow(f, list(range(WEIGHT_LOW, WEIGHT_HIGH + 1))) for f in free}
    table: dict[tuple[str, str], bool] = {}
    every_pair = [(a, b) for a in kinds for b in kinds if a != b]
    found: list[tuple[dict[str, int], dict[tuple[str, str], bool], bool]] = []
    kinds_of = [sorted({r["kind"] for r in rows}) for rows in journal]
    pairs_of = [[(a, b) for a in ks for b in ks if a != b] for ks in kinds_of]
    cache: dict[tuple[Any, ...], list[dict[tuple[str, str], bool]]] = {}

    def weights_now() -> dict[str, int]:
        # a kind with no weight yet only occurs in accounts with a single ordinary kind, whose
        # withdrawal order any common positive weight leaves unchanged
        return {kind: values.get(j, 1) for j, kind in enumerate(kinds)}

    def extensions(i: int) -> list[dict[tuple[str, str], bool]]:
        weights = weights_now()
        # the withdrawal order only compares charges inside one account, so weights that differ
        # by a common factor replay alike
        own = [weights[k] for k in kinds_of[i]]
        common = 0
        for w in own:
            common = gcd(common, w)
        key = (i, tuple(w // common for w in own), tuple(table.get(p) for p in pairs_of[i]))
        if key not in cache:
            cache[key] = _account_extensions(journal[i], table, weights)
        return cache[key]

    def replay(accounts: list[int], then) -> None:
        if not accounts:
            then()
            return
        for extension in extensions(accounts[0]):
            table.update(extension)
            replay(accounts[1:], then)
            for pair in extension:
                del table[pair]

    def completed_by(f: int, known: set[int]) -> set[int]:
        assigned = {g for g in free if g in values} | {f}
        return known | {f} | {col for col, deps in depends.items() if deps and deps <= assigned}

    def search(domains: dict[int, list[int]], known: set[int], pending: list[int]) -> None:
        open_weights = [f for f in free if f not in values]
        if not open_weights:
            found.append(({kind: values[j] for j, kind in enumerate(kinds)}, dict(table),
                          all(p in table for p in every_pair)))
            return

        def urgency(f: int) -> tuple[int, int, int]:
            reach = completed_by(f, known)
            return (len(domains[f]), -sum(1 for i in pending if needs[i] <= reach), free.index(f))

        f = min(open_weights, key=urgency)
        rest = [g for g in open_weights if g != f]
        for value in domains[f]:
            values[f] = value
            newly = [col for col, deps in depends.items()
                     if deps and col not in values and deps <= {g for g in free if g in values}]
            settled = {col: pivot_value(col) for col in newly}
            if None not in settled.values():
                values.update(settled)
                narrowed = {g: narrow(g, domains[g]) for g in rest}
                if all(narrowed.values()):
                    known_now = known | {f} | set(newly)
                    ready = [i for i in pending if needs[i] <= known_now]
                    later = [i for i in pending if not needs[i] <= known_now]
                    replay(ready, lambda: search(narrowed, known_now, later))
            for col in newly:
                values.pop(col, None)
        del values[f]

    known = set(values)
    first = [i for i, need in enumerate(needs) if len(need) <= 1 or need <= known]
    pending = [i for i in range(len(journal)) if i not in set(first)]
    if all(domains.values()):
        replay(first, lambda: search(domains, known, pending))
    return found


# ------------------------------------------------------------------ standing journal

def _standing_members(names: list[str], sponsor: dict[str, str], unwaived: dict[str, int], room: dict[str, int],
                      ordinary: dict[str, int], floor: int) -> set[str]:
    """Least set closed under the standing rule: an account holds standing when its
    unwaived total, plus its waivable penalty if its sponsor holds standing, reaches the
    floor times its number of ordinary rows."""
    holders = {n for n in names if ordinary[n] > 0 and unwaived[n] >= floor * ordinary[n]}
    backers: dict[str, list[str]] = {}
    for n in names:
        if sponsor.get(n):
            backers.setdefault(sponsor[n], []).append(n)
    frontier = list(holders)
    while frontier:
        lifted = frontier.pop()
        for n in backers.get(lifted, ()):
            if n not in holders and ordinary[n] > 0 and unwaived[n] + room[n] >= floor * ordinary[n]:
                holders.add(n)
                frontier.append(n)
    return holders


def _period_standing(period: dict[str, list[dict[str, Any]]], rules: dict[str, Any], weights: dict[str, int],
                     table: dict[tuple[str, str], bool]) -> set[str]:
    """The accounts the standing rule grants standing in the standing journal's period,
    rated with no carry between rows and the journal's floor."""
    offsets, penalties, quantum = rules["region_offsets"], rules["flag_penalties"], int(rules["latency_quantum"])
    unwaived, room, ordinary, sponsor = {}, {}, {}, {}
    for name, rows in period.items():
        live: list[int] = []
        taken: list[int] = []
        for j, row in enumerate(rows):
            if row["flag"] == "void":
                pick = next((i for i in _choose(live, rows, row["kind"], weights)
                             if rows[i]["kind"] == row["kind"] or table[(row["kind"], rows[i]["kind"])]), None)
                if pick is not None:
                    live.remove(pick)
                    taken.append(pick)
            elif row["flag"] == "revive":
                if taken:
                    live.append(taken.pop())
            else:
                live.append(j)
        sponsor[name] = rows[0]["sponsor"]
        ordinary[name] = sum(1 for r in rows if r["flag"] not in CONTROL_FLAGS)
        unwaived[name] = room[name] = 0
        for j in live:
            row = rows[j]
            charge = (row["amount"] * row["units"] * weights[row["kind"]] + int(offsets[row["region"]])
                      - row["latency"] // quantum)
            penalty = int(penalties.get(row["flag"], 0))
            unwaived[name] += charge - penalty
            room[name] += penalty
    names = sorted(period)
    sponsor = {n: (s if s in period else "") for n, s in sponsor.items()}
    return _standing_members(names, sponsor, unwaived, room, ordinary, JOURNAL_FLOOR)


def _processing_order(lines: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    accounts: dict[str, list[dict[str, str]]] = {}
    for line in lines:
        accounts.setdefault(line["account"], []).append(line)
    for rows in accounts.values():
        rows.sort(key=lambda line: (int(line["ts"]), int(line["row"][1:])))
    return accounts


def configuration(rules: dict[str, Any], folder: Path) -> tuple[dict[str, int], dict[tuple[str, str], bool]]:
    """The kind weights and the cancellation table that the extract's evidence settles."""
    kinds = list(rules["kinds"])
    journal = [[{"kind": line["kind"], "amount": int(line["amount"]), "units": int(line["units"]),
                 "flag": line["flag"], "state": line["state"]} for line in rows]
               for rows in _processing_order(_lines(folder / rules["withdrawals_journal_file"])).values()]
    found = withdrawal_candidates(kinds, _lines(folder / rules["rate_card_file"]),
                                  _document(folder / rules["rate_figures_file"])["figures"], journal)
    period = {name: [{"kind": line["kind"], "amount": int(line["amount"]), "units": int(line["units"]),
                      "flag": line["flag"], "region": line["region"], "latency": int(line["latency_ms"]),
                      "sponsor": line["sponsor"], "standing": line["standing"]} for line in rows]
              for name, rows in _processing_order(_lines(folder / rules["standing_journal_file"])).items()}
    recorded = {name for name, rows in period.items() if rows[0]["standing"] == "premium"}
    settled = []
    for weights, table, complete in found:
        if not complete:
            raise ValueError("the withdrawal journal leaves a table pair open")
        if _period_standing(period, rules, weights, table) == recorded:
            settled.append((weights, table))
    if len(settled) != 1:
        raise ValueError("the rate card and the two journals do not settle one configuration")
    return settled[0]


# ------------------------------------------------------------------ identity

class Directory:
    """Governing records, merge timeline and sponsor links of one extract."""

    def __init__(self, registry: list[dict[str, str]], export: list[dict[str, str]],
                 merges: list[dict[str, str]]) -> None:
        chosen: dict[str, tuple[str, int, dict[str, str]]] = {}
        for index, record in enumerate(registry):
            rank = (record["updated"], index)
            held = chosen.get(record["account"])
            if held is None or (held[0], held[1]) <= rank:
                chosen[record["account"]] = (rank[0], rank[1], record)
        self.records = {name: entry[2] for name, entry in chosen.items()}
        for record in export:
            self.records.setdefault(record["account"], record)
        self.timeline: dict[str, tuple[list[int], list[str]]] = {}
        staged: dict[str, list[tuple[int, str]]] = {}
        for record in merges:
            staged.setdefault(record["account"], []).append((int(record["effective_ts"]), record["merged_into"]))
        for name, entries in staged.items():
            entries.sort()
            self.timeline[name] = ([e for e, _ in entries], [t for _, t in entries])
        self._cache: dict[tuple[str, int], str] = {}

    def known(self, name: str) -> bool:
        return name in self.records

    def owner(self, name: str, stamp: int) -> str:
        key = (name, stamp)
        hit = self._cache.get(key)
        if hit is None:
            hit = self._walk(name, stamp)
            self._cache[key] = hit
        return hit

    def _walk(self, name: str, stamp: float) -> str:
        for _ in range(len(self.timeline) + 1):
            line = self.timeline.get(name)
            if line is None:
                return name
            reach = bisect_left(line[0], stamp)  # records with effective_ts < stamp
            if reach == 0 or not line[1][reach - 1]:
                return name
            name = line[1][reach - 1]
        return name

    def home(self, name: str) -> str:
        return self.records[name]["home_region"]

    def patron(self, name: str) -> str:
        named = (self.records.get(name) or {}).get("sponsor") or ""
        return self._walk(named, float("inf")) if named else ""


# ------------------------------------------------------------------ errata

def errata_state(entries: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, str]]:
    withdrawn = {entry["reverts"] for entry in entries if "reverts" in entry}
    earliest: dict[tuple[str, int, str], tuple[int, str]] = {}
    for entry in entries:
        if "reverts" in entry or entry["erratum"] in withdrawn:
            continue
        cell = (entry["booked_account"], int(entry["ts"]), entry["field"])
        number = int(entry["erratum"].split("-", 1)[1])
        if cell not in earliest or number < earliest[cell][0]:
            earliest[cell] = (number, str(entry["value"]))
    patch: dict[tuple[str, int], dict[str, str]] = {}
    for (name, stamp, field), (_, value) in earliest.items():
        patch.setdefault((name, stamp), {})[field] = value
    return patch


# ------------------------------------------------------------------ rating

def aggregate(events_path: str | Path, rules_path: str | Path) -> dict[str, Any]:
    return rate(Path(events_path), Path(rules_path))["result"]


def rate(events_path: Path, rules_path: Path) -> dict[str, Any]:
    rules = _document(rules_path)
    folder = rules_path.parent
    weights, table = configuration(rules, folder)
    directory = Directory(_lines(folder / rules["registry_file"]),
                          _document(folder / rules["export_file"])["accounts"],
                          _lines(folder / rules["merges_file"]))
    with open(folder / rules["errata_file"], encoding="utf-8") as handle:
        patch = errata_state([json.loads(text) for text in handle if text.strip()])
    with open(events_path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        cells_list = list(reader)
    at = {name: i for i, name in enumerate(header)}
    for cells in cells_list:
        cells[at["account"]] = cells[at["account"]].strip().upper()
        cells[at["kind"]] = cells[at["kind"]].strip().lower()
        cells[at["flag"]] = cells[at["flag"]].strip().lower()
    micro = "latency_us" in at
    lat_at = at["latency_us"] if micro else at["latency_ms"]

    unpriced = unregistered = rebooked = 0
    staged = []
    for cells in cells_list:
        stamp = int(cells[at["ts"]])
        owner = directory.owner(cells[at["account"]], stamp)
        if not directory.known(owner):
            unregistered += 1
            continue
        fix = patch.get((owner, stamp), {})
        amount = fix.get("amount", cells[at["amount"]])
        if amount == "":
            unpriced += 1
            continue
        if owner != cells[at["account"]]:
            rebooked += 1
        latency = int(cells[lat_at])
        if micro:
            latency = (latency + 500) // 1000
        rid = cells[at["id"]]
        flag = fix.get("flag", cells[at["flag"]])
        control = flag in CONTROL_FLAGS
        staged.append({"stamp": stamp, "number": int(rid[1:]), "id": rid, "owner": owner, "kind": cells[at["kind"]],
                       "amount": 0 if control else int(amount),
                       "units": 0 if control else int(fix.get("units", cells[at["units"]])), "latency": latency,
                       "flag": flag, "amended": (owner, stamp) in patch})
    staged.sort(key=lambda rec: (rec["stamp"], rec["number"]))

    offsets = rules["region_offsets"]
    penalties = rules["flag_penalties"]
    modulus = int(rules["carry_modulus"])
    quantum = int(rules["latency_quantum"])
    carry: dict[str, int] = {}
    pools: dict[str, list[int]] = {}
    stacks: dict[str, list[int]] = {}
    live: set[int] = set()
    orphan_voids = orphan_revives = 0
    for pos, rec in enumerate(staged):
        rec["region"] = directory.home(rec["owner"])
        rec["control"] = rec["flag"] in CONTROL_FLAGS
        rec["penalty"] = int(penalties.get(rec["flag"], 0))
        value = (rec["amount"] * rec["units"] * weights[rec["kind"]] + int(offsets[rec["region"]])
                 - rec["latency"] // quantum)
        if not rec["control"]:
            value += carry.get(rec["region"], 0)
            carry[rec["region"]] = value % modulus
            pools.setdefault(rec["owner"], []).append(pos)
            live.add(pos)
        rec["carried"] = value
        if rec["flag"] == "void":
            pool = pools.get(rec["owner"], [])
            target = next((i for i in _choose(pool, staged, rec["kind"], weights)
                           if staged[i]["kind"] == rec["kind"] or table[(rec["kind"], staged[i]["kind"])]), None)
            if target is None:
                orphan_voids += 1
            else:
                pool.remove(target)
                live.discard(target)
                stacks.setdefault(rec["owner"], []).append(target)
        elif rec["flag"] == "revive":
            stack = stacks.get(rec["owner"])
            if stack:
                back = stack.pop()
                pools[rec["owner"]].append(back)
                live.add(back)
            else:
                orphan_revives += 1

    members = sorted({rec["owner"] for rec in staged if not rec["control"]})
    unwaived = dict.fromkeys(members, 0)
    room = dict.fromkeys(members, 0)
    ordinary = dict.fromkeys(members, 0)
    for pos, rec in enumerate(staged):
        if rec["control"]:
            continue
        ordinary[rec["owner"]] += 1
        if pos in live:
            unwaived[rec["owner"]] += rec["carried"] - rec["penalty"]
            room[rec["owner"]] += rec["penalty"]
    sponsor = {name: directory.patron(name) for name in members}
    floor = int(rules["premium_floor"])
    holders = _standing_members(members, sponsor, unwaived, room, ordinary, floor)

    account_totals = dict.fromkeys(members, 0)
    region_totals: dict[str, int] = {}
    kind_totals: dict[str, int] = {}
    flag_counts: dict[str, int] = {}
    checksum = waived_penalty = cancelled = 0
    amended_rows = []
    for pos, rec in enumerate(staged):
        waive = not rec["control"] and sponsor.get(rec["owner"], "") in holders
        final = rec["carried"] - (0 if waive else rec["penalty"])
        if waive:
            waived_penalty += rec["penalty"]
        checksum = (checksum * MULTIPLIER + final * (pos + 1) + rec["number"]) & MASK
        if rec["amended"]:
            amended_rows.append([rec["id"], final])
        if rec["control"]:
            flag_counts[rec["flag"]] = flag_counts.get(rec["flag"], 0) + 1
            continue
        share = final if pos in live else 0
        account_totals[rec["owner"]] += share
        region_totals[rec["region"]] = region_totals.get(rec["region"], 0) + share
        kind_totals[rec["kind"]] = kind_totals.get(rec["kind"], 0) + share
        flag_counts[rec["flag"]] = flag_counts.get(rec["flag"], 0) + (1 if pos in live else 0)
        if pos not in live:
            cancelled += final
    ranking = sorted(account_totals.items(), key=lambda item: (-item[1], item[0]))[: int(rules["top_n"])]
    result = {
        "label": str(rules["label"]),
        "event_count": len(cells_list),
        "account_totals": dict(sorted(account_totals.items())),
        "region_totals": dict(sorted(region_totals.items())),
        "kind_totals": dict(sorted(kind_totals.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "premium_accounts": sorted(holders),
        "top_accounts": [[name, total] for name, total in ranking],
        "checksum": checksum,
    }
    return {
        "result": result,
        "quality": {"unpriced_rows": unpriced, "unregistered_rows": unregistered, "rebooked_rows": rebooked,
                    "orphan_voids": orphan_voids, "orphan_revives": orphan_revives,
                    "cancelled_score": cancelled, "amendments": amended_rows},
        "rescued": sorted(n for n in holders if unwaived[n] < floor * ordinary[n]),
        "waived_penalty": waived_penalty,
        "processed": len(staged),
        "live": sum(1 for pos in live if not staged[pos]["control"]),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: optimize.py EVENTS_CSV RULES_JSON", file=sys.stderr)
        return 2
    print(json.dumps(aggregate(argv[1], argv[2]), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
