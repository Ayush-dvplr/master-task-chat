#!/usr/bin/env python3
"""Settle a season of the ranked team ladder.

Usage: settle_season.py <data directory> <output directory>

The program implements Rulebook: Structure, Scoring, Filings and protests,
Roster identity, Discipline and Standings over the records of a season
directory, and writes the artifacts fixed by the artifact contract into the
output directory.

Three season constants the rulebook does not print, determined from the
published calibration slice:

  * the forfeit credit rate is two thirds of the win award;
  * the adjustment operators compose forfeit, then schedule, then debit;
  * the single conversion to whole milli-points is to nearest, ties to even.
"""

import csv
import json
import os
import re
import sys
from fractions import Fraction

WIN_AWARD = 3000
FORFEIT_CREDIT_RATE = Fraction(2, 3)
FORFEIT_CREDIT_PER_WIN = int(FORFEIT_CREDIT_RATE * WIN_AWARD)

DEBIT_BY_SEVERITY = {"minor": 500, "major": 1500, "severe": 4000}
DEBIT_CAP = 6000
INELIGIBLE_DEBIT = 4500
DEFAULT_AMNESTY = "2049-01-01"

TIER_FLOORS = (("A", 14000), ("B", 10000), ("C", 6500))
OPPONENT_WEIGHT = {"A": 1150, "B": 1000, "C": 900, "D": 800}

EARNINGS = {
    "home_win": (3000, 0),
    "away_win": (0, 3000),
    "draw": (1000, 1000),
    "home_otw": (2000, 1000),
    "away_otw": (1000, 2000),
    "home_forfeit": (0, 0),
    "away_forfeit": (0, 0),
    "void": (0, 0),
}
ISSUABLE = {
    "home_win": 3000,
    "away_win": 3000,
    "draw": 2000,
    "home_otw": 3000,
    "away_otw": 3000,
    "home_forfeit": FORFEIT_CREDIT_PER_WIN,
    "away_forfeit": FORFEIT_CREDIT_PER_WIN,
    "void": 0,
}
FORFEIT_WINNER = {"home_forfeit": "away", "away_forfeit": "home"}

CHAIN_KINDS = ("rename", "merge", "split")


# --------------------------------------------------------------------------
# quantities
# --------------------------------------------------------------------------

def points(milli):
    """Render whole milli-points as the contract's point quantity string."""
    sign = "-" if milli < 0 else ""
    whole = abs(milli)
    return "%s%d.%03d" % (sign, whole // 1000, whole % 1000)


def to_milli(quantity):
    """Convert an exact quantity to whole milli-points, nearest, ties to even."""
    floor = quantity.numerator // quantity.denominator
    remainder = quantity - floor
    half = Fraction(1, 2)
    if remainder < half:
        return floor
    if remainder > half:
        return floor + 1
    return floor if floor % 2 == 0 else floor + 1


def tier_of(adjusted):
    for letter, floor in TIER_FLOORS:
        if adjusted >= floor:
            return letter
    return "D"


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------

def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_amnesty(data_dir):
    path = os.path.join(data_dir, "rulebook_discipline.md")
    if not os.path.exists(path):
        return DEFAULT_AMNESTY
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    found = re.search(r"amnesty date for this season is\s*(\d{4}-\d{2}-\d{2})", text)
    return found.group(1) if found else DEFAULT_AMNESTY


def load(data_dir):
    season = {}

    season["circuits"] = {
        row["circuit_id"]: {
            "circuit_id": row["circuit_id"],
            "promotion_slots": int(row["promotion_slots"]),
        }
        for row in read_csv(os.path.join(data_dir, "circuits.csv"))
    }
    season["divisions"] = {
        row["division_id"]: {
            "division_id": row["division_id"],
            "circuit_id": row["circuit_id"],
            "provisional": int(row["provisional"]) == 1,
            "min_rosters": int(row["min_rosters"]),
            "promotion_slots": int(row["promotion_slots"]),
        }
        for row in read_csv(os.path.join(data_dir, "divisions.csv"))
    }
    season["rosters"] = {
        row["roster_id"]: {
            "roster_id": row["roster_id"],
            "division_id": row["division_id"],
            "home_region": row["home_region"],
        }
        for row in read_csv(os.path.join(data_dir, "rosters.csv"))
    }
    season["fixtures"] = sorted(
        (
            {
                "fixture_id": int(row["fixture_id"]),
                "stage": int(row["stage"]),
                "home_roster_id": row["home_roster_id"],
                "away_roster_id": row["away_roster_id"],
            }
            for row in read_csv(os.path.join(data_dir, "fixtures.csv"))
        ),
        key=lambda fixture: fixture["fixture_id"],
    )
    season["filings"] = [
        {
            "filing_id": row["filing_id"],
            "fixture_id": int(row["fixture_id"]),
            "filed_at": row["filed_at"],
            "result": row["result"],
            "retracted": int(row["retracted"]) == 1,
        }
        for row in read_csv(os.path.join(data_dir, "filings.csv"))
    ]
    season["events"] = [
        {
            "event_id": row["event_id"],
            "kind": row["kind"],
            "roster_id": row["roster_id"],
            "target_id": row["target_id"],
            "effective_fixture": int(row["effective_fixture"]),
        }
        for row in read_csv(os.path.join(data_dir, "roster_events.csv"))
    ]
    season["infractions"] = [
        {
            "infraction_id": row["infraction_id"],
            "roster_id": row["roster_id"],
            "filed_at": row["filed_at"],
            "severity": row["severity"],
        }
        for row in read_csv(os.path.join(data_dir, "infractions.csv"))
    ]

    protests_path = os.path.join(data_dir, "protests.json")
    protests = []
    if os.path.exists(protests_path):
        with open(protests_path, encoding="utf-8") as handle:
            payload = json.load(handle)
        for record in payload.get("protests", []):
            protests.append(
                {
                    "protest_id": record["protest_id"],
                    "fixture_id": int(record["fixture_id"]),
                    "status": record["status"],
                    "replacement_result": record.get("replacement_result", ""),
                }
            )
    season["protests"] = protests
    season["amnesty"] = read_amnesty(data_dir)
    return season


# --------------------------------------------------------------------------
# Rulebook: Filings and protests
# --------------------------------------------------------------------------

def settle_outcomes(season):
    """Return (outcome by fixture, superseded filing count, applied protests)."""
    live = {}
    for filing in season["filings"]:
        if filing["retracted"]:
            continue
        live.setdefault(filing["fixture_id"], []).append(filing)

    outcomes = {}
    superseded = 0
    for fixture in season["fixtures"]:
        contenders = live.get(fixture["fixture_id"], [])
        if not contenders:
            outcomes[fixture["fixture_id"]] = None
            continue
        # This competition settles on first report: earliest filed date wins,
        # ties broken by the smaller filing identifier.
        authoritative = min(contenders, key=lambda f: (f["filed_at"], f["filing_id"]))
        outcomes[fixture["fixture_id"]] = authoritative["result"]
        superseded += len(contenders) - 1

    applied = []
    upheld = [p for p in season["protests"] if p["status"] == "upheld"]
    for protest in sorted(upheld, key=lambda p: p["protest_id"]):
        if protest["fixture_id"] not in outcomes:
            continue
        outcomes[protest["fixture_id"]] = protest["replacement_result"]
        applied.append(
            {"fixture_id": protest["fixture_id"], "protest_id": protest["protest_id"]}
        )
    applied.sort(key=lambda entry: entry["protest_id"])
    return outcomes, superseded, applied


# --------------------------------------------------------------------------
# Rulebook: Roster identity
# --------------------------------------------------------------------------

def reject_cyclic_events(events):
    """Reject every event whose subject and target lie on one circular chain.

    Circularity is decided over every event of the season taken together, so
    the effective fixture of an event has no bearing on this question.
    """
    edges = {}
    nodes = set()
    for event in events:
        if event["kind"] not in CHAIN_KINDS:
            continue
        nodes.add(event["roster_id"])
        nodes.add(event["target_id"])
        edges.setdefault(event["roster_id"], set()).add(event["target_id"])

    # Tarjan's strongly connected components, iterative and order independent.
    index = {}
    low = {}
    on_stack = {}
    stack = []
    component = {}
    counter = [0]

    for root in sorted(nodes):
        if root in index:
            continue
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on_stack[root] = True
        work = [(root, iter(sorted(edges.get(root, ()))))]
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter[0]
                    counter[0] += 1
                    stack.append(child)
                    on_stack[child] = True
                    work.append((child, iter(sorted(edges.get(child, ())))))
                    advanced = True
                    break
                if on_stack.get(child):
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                members = set()
                while True:
                    member = stack.pop()
                    on_stack[member] = False
                    members.add(member)
                    if member == node:
                        break
                frozen = frozenset(members)
                for member in members:
                    component[member] = frozen

    def on_circle(node):
        members = component.get(node, frozenset())
        if len(members) > 1:
            return True
        return node in edges.get(node, set())

    rejected = {}
    for event in events:
        if event["kind"] not in CHAIN_KINDS:
            continue
        subject = event["roster_id"]
        target = event["target_id"]
        if (
            on_circle(subject)
            and on_circle(target)
            and component.get(subject) == component.get(target)
        ):
            rejected[event["event_id"]] = "merge_cycle"
    return rejected


class Identity(object):
    """Resolves the roster identifiers written on a fixture."""

    def __init__(self, season, rejected):
        self.rosters = season["rosters"]
        self.chain_events = {}
        self.disbands = {}
        for event in season["events"]:
            if event["event_id"] in rejected:
                continue
            if event["kind"] in CHAIN_KINDS:
                self.chain_events.setdefault(event["roster_id"], []).append(event)
            elif event["kind"] == "disband":
                self.disbands.setdefault(event["roster_id"], []).append(event)
        self.max_fixture = max(
            (fixture["fixture_id"] for fixture in season["fixtures"]), default=0
        )

    def _in_effect(self, roster_id, fixture_id):
        candidates = [
            event
            for event in self.chain_events.get(roster_id, ())
            if event["effective_fixture"] <= fixture_id
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda e: (e["effective_fixture"], e["event_id"]))

    def _disbanded(self, roster_id, fixture_id):
        return any(
            event["effective_fixture"] <= fixture_id
            for event in self.disbands.get(roster_id, ())
        )

    def resolve(self, roster_id, fixture_id, home_region):
        """Return (canonical identifier, disbanded) for one participant."""
        seen = set()
        current = roster_id
        while current not in seen:
            seen.add(current)
            if self._disbanded(current, fixture_id):
                return current, True
            event = self._in_effect(current, fixture_id)
            if event is None:
                return current, False
            if event["kind"] == "split":
                target = event["target_id"]
                target_region = self.rosters.get(target, {}).get("home_region")
                if home_region != target_region:
                    return current, False
                current = target
            else:
                current = event["target_id"]
        return current, False

    def at_close(self, roster_id):
        """The canonical competitor an identifier belongs to at season close."""
        seen = set()
        current = roster_id
        while current not in seen:
            seen.add(current)
            candidates = [
                event
                for event in self.chain_events.get(current, ())
                if event["kind"] in ("rename", "merge")
                and event["effective_fixture"] <= self.max_fixture
            ]
            if not candidates:
                return current
            current = max(
                candidates, key=lambda e: (e["effective_fixture"], e["event_id"])
            )["target_id"]
        return current


# --------------------------------------------------------------------------
# Rulebook: Scoring -- the fixture walk
# --------------------------------------------------------------------------

def walk_fixtures(season, outcomes, identity):
    stages = sorted({fixture["stage"] for fixture in season["fixtures"]})
    issued = dict.fromkeys(stages, 0)
    voided = dict.fromkeys(stages, 0)

    ledger = {}          # roster -> stage -> milli-points into base points
    forfeit_ledger = {}  # roster -> stage -> forfeit credit made available
    counted = {}         # roster -> list of (fixture_id, opponent, earned)
    forfeit_wins = {}
    void_fixtures = []
    disbanded_voids = []
    unattributable = []
    counted_fixture_count = 0

    for fixture in season["fixtures"]:
        fixture_id = fixture["fixture_id"]
        stage = fixture["stage"]
        outcome = outcomes.get(fixture_id)
        issuable = ISSUABLE.get(outcome, 0) if outcome else 0
        issued[stage] += issuable

        home_region = season["rosters"].get(
            fixture["home_roster_id"], {}
        ).get("home_region")
        home, home_disbanded = identity.resolve(
            fixture["home_roster_id"], fixture_id, home_region
        )
        away, away_disbanded = identity.resolve(
            fixture["away_roster_id"], fixture_id, home_region
        )

        disbanded = home_disbanded or away_disbanded
        unresolved = home not in season["rosters"] or away not in season["rosters"]
        if unresolved:
            unattributable.append(
                {
                    "away_roster_id": away,
                    "fixture_id": fixture_id,
                    "home_roster_id": home,
                }
            )

        is_void = outcome is None or outcome == "void" or disbanded or unresolved
        if is_void:
            void_fixtures.append(fixture_id)
            voided[stage] += issuable
            if disbanded:
                disbanded_voids.append(fixture_id)
            continue

        counted_fixture_count += 1
        home_earn, away_earn = EARNINGS[outcome]
        for roster, opponent, earned in (
            (home, away, home_earn),
            (away, home, away_earn),
        ):
            ledger.setdefault(roster, {}).setdefault(stage, 0)
            ledger[roster][stage] += earned
            counted.setdefault(roster, []).append((fixture_id, opponent, earned))

        winner = FORFEIT_WINNER.get(outcome)
        if winner is not None:
            roster = home if winner == "home" else away
            forfeit_wins[roster] = forfeit_wins.get(roster, 0) + 1
            forfeit_ledger.setdefault(roster, {}).setdefault(stage, 0)
            forfeit_ledger[roster][stage] += FORFEIT_CREDIT_PER_WIN

    return {
        "stages": stages,
        "issued": issued,
        "voided": voided,
        "ledger": ledger,
        "forfeit_ledger": forfeit_ledger,
        "counted": counted,
        "forfeit_wins": forfeit_wins,
        "void_fixtures": sorted(void_fixtures),
        "disbanded_voids": sorted(disbanded_voids),
        "unattributable": sorted(unattributable, key=lambda e: e["fixture_id"]),
        "counted_fixture_count": counted_fixture_count,
    }


# --------------------------------------------------------------------------
# Rulebook: Discipline
# --------------------------------------------------------------------------

def accrue_debits(season, identity):
    per_roster = {}
    for infraction in season["infractions"]:
        canonical = identity.at_close(infraction["roster_id"])
        if canonical not in season["rosters"]:
            continue  # accrues against nobody
        per_roster.setdefault(canonical, []).append(infraction)

    debits = {}
    for roster, infractions in per_roster.items():
        applied = 0
        for infraction in sorted(
            infractions, key=lambda i: (i["filed_at"], i["infraction_id"])
        ):
            if infraction["filed_at"] < season["amnesty"]:
                continue
            room = DEBIT_CAP - applied
            if room <= 0:
                continue
            applied += min(DEBIT_BY_SEVERITY[infraction["severity"]], room)
        debits[roster] = applied
    return debits


# --------------------------------------------------------------------------
# Rulebook: Standings
# --------------------------------------------------------------------------

def adjusted_for(assignment, counted, base, forfeit_credit, debits, roster):
    """Compose forfeit, then schedule, then debit, converting exactly once."""
    appearances = counted[roster]
    weight_total = sum(
        OPPONENT_WEIGHT[assignment[opponent]] for _, opponent, _ in appearances
    )
    strength = Fraction(weight_total, len(appearances) * 1000)
    quantity = (base.get(roster, 0) + forfeit_credit.get(roster, 0)) * strength
    quantity -= debits.get(roster, 0)
    if quantity < 0:
        quantity = Fraction(0)
    return to_milli(quantity), weight_total


def solve_tiers(active, counted, base, forfeit_credit, debits):
    """Find the stable assignment of tiers to the active rosters."""
    for start in ("D", "C", "B", "A"):
        assignment = {roster: start for roster in active}
        for _ in range(1000):
            adjusted = {}
            weights = {}
            for roster in active:
                adjusted[roster], weights[roster] = adjusted_for(
                    assignment, counted, base, forfeit_credit, debits, roster
                )
            proposal = {roster: tier_of(adjusted[roster]) for roster in active}
            if proposal == assignment:
                return assignment, adjusted, weights
            assignment = proposal
    raise SystemExit("no stable tier assignment found")


def order_division(entries):
    """Division ordering: adjusted, head to head, form window, identifier."""
    return sorted(
        entries,
        key=lambda e: (
            -e["adjusted"],
            -e["head_to_head"],
            -e["form_window"],
            e["roster_id"],
        ),
    )


# --------------------------------------------------------------------------
# the settlement
# --------------------------------------------------------------------------

def settle(data_dir):
    season = load(data_dir)
    outcomes, superseded, protests_applied = settle_outcomes(season)
    rejected = reject_cyclic_events(season["events"])
    identity = Identity(season, rejected)
    walk = walk_fixtures(season, outcomes, identity)

    counted = walk["counted"]
    active = sorted(roster for roster, games in counted.items() if games)
    base = {roster: sum(walk["ledger"].get(roster, {}).values()) for roster in active}
    forfeit_credit = {
        roster: walk["forfeit_wins"].get(roster, 0) * FORFEIT_CREDIT_PER_WIN
        for roster in active
    }
    debits = accrue_debits(season, identity)
    assignment, adjusted, weights = solve_tiers(
        active, counted, base, forfeit_credit, debits
    )

    # The credited side of the conservation identity is taken from the roster
    # ledger, never from a second walk of the fixtures.
    credited = dict.fromkeys(walk["stages"], 0)
    for by_stage in walk["ledger"].values():
        for stage, milli in by_stage.items():
            credited[stage] += milli
    for by_stage in walk["forfeit_ledger"].values():
        for stage, milli in by_stage.items():
            credited[stage] += milli

    roster_division = {
        roster: season["rosters"][roster]["division_id"] for roster in active
    }

    # Rulebook: Structure -- quorum and scope.
    division_active = {division: [] for division in season["divisions"]}
    for roster in active:
        division_active.setdefault(roster_division[roster], []).append(roster)
    meets_quorum = {
        division: len(division_active.get(division, []))
        >= season["divisions"][division]["min_rosters"]
        for division in season["divisions"]
    }
    circuit_divisions = {circuit: [] for circuit in season["circuits"]}
    for division in sorted(season["divisions"]):
        circuit_divisions.setdefault(
            season["divisions"][division]["circuit_id"], []
        ).append(division)
    candidate = {
        division: (not season["divisions"][division]["provisional"])
        and meets_quorum[division]
        for division in season["divisions"]
    }
    circuit_in_scope = {
        circuit: any(candidate[division] for division in divisions)
        for circuit, divisions in circuit_divisions.items()
    }
    division_in_scope = {
        division: candidate[division]
        and circuit_in_scope[season["divisions"][division]["circuit_id"]]
        for division in season["divisions"]
    }

    # Roster level figures.
    rosters = {}
    for roster in active:
        appearances = sorted(counted[roster])
        rosters[roster] = {
            "roster_id": roster,
            "division_id": roster_division[roster],
            "adjusted": adjusted[roster],
            "base": base[roster],
            "debit": debits.get(roster, 0),
            "eligible": debits.get(roster, 0) < INELIGIBLE_DEBIT,
            "forfeit_wins": walk["forfeit_wins"].get(roster, 0),
            "counted_fixtures": len(appearances),
            "schedule_weight_total": weights[roster],
            "form_window": sum(earned for _, _, earned in appearances[-4:]),
            "tier": assignment[roster],
            "head_to_head": 0,
        }

    for members in division_active.values():
        for roster in members:
            tied = {
                other
                for other in members
                if other != roster and adjusted[other] == adjusted[roster]
            }
            if not tied:
                continue
            rosters[roster]["head_to_head"] = sum(
                earned for _, opponent, earned in counted[roster] if opponent in tied
            )

    # Division ordering and promotion.
    division_order = {}
    division_promoted = {}
    for division in sorted(season["divisions"]):
        entries = order_division(
            [rosters[roster] for roster in division_active.get(division, [])]
        )
        division_order[division] = entries
        promoted = []
        if division_in_scope[division]:
            slots = season["divisions"][division]["promotion_slots"]
            for entry in entries:
                if len(promoted) >= slots:
                    break
                if entry["eligible"]:
                    promoted.append(entry["roster_id"])
        division_promoted[division] = promoted

    # Circuit promotion cap.
    circuit_result = {}
    for circuit in sorted(season["circuits"]):
        in_scope_divisions = [
            division
            for division in circuit_divisions.get(circuit, [])
            if division_in_scope[division]
        ]
        pool = []
        for division in in_scope_divisions:
            pool.extend(division_promoted[division])
        pre_cap = sorted(pool)
        remaining = list(pre_cap)
        removed = []
        slots = season["circuits"][circuit]["promotion_slots"]
        while len(remaining) > slots:
            # Reverse of the division ordering; highest identifier breaks ties.
            ranked = sorted(remaining, reverse=True)
            ranked.sort(
                key=lambda roster: (
                    rosters[roster]["adjusted"],
                    rosters[roster]["head_to_head"],
                    rosters[roster]["form_window"],
                )
            )
            lowest = ranked[0]
            remaining.remove(lowest)
            removed.append(lowest)
        circuit_result[circuit] = {
            "in_scope_divisions": in_scope_divisions,
            "out_of_scope_divisions": [
                division
                for division in circuit_divisions.get(circuit, [])
                if not division_in_scope[division]
            ],
            "pre_cap": pre_cap,
            "promoted": sorted(remaining),
            "removed": sorted(removed),
        }

    removed_everywhere = set()
    for result in circuit_result.values():
        removed_everywhere.update(result["removed"])

    divisions_in_scope = sorted(
        division for division in season["divisions"] if division_in_scope[division]
    )
    circuits_in_scope = sorted(
        circuit for circuit in season["circuits"] if circuit_in_scope[circuit]
    )
    season_promoted = sorted(
        {
            roster
            for circuit in circuits_in_scope
            for roster in circuit_result[circuit]["promoted"]
        }
    )

    issued_total = sum(walk["issued"].values())
    voided_total = sum(walk["voided"].values())
    credited_total = sum(credited.values())

    artifacts = {}

    artifacts["summary.json"] = {
        "active_roster_count": len(active),
        "circuit_ids_in_scope": circuits_in_scope,
        "counted_fixture_count": walk["counted_fixture_count"],
        "credited_points_total": points(credited_total),
        "division_ids_in_scope": divisions_in_scope,
        "fixture_count": len(season["fixtures"]),
        "ineligible_roster_count": sum(
            1 for roster in active if not rosters[roster]["eligible"]
        ),
        "issued_points_total": points(issued_total),
        "promoted_roster_count": len(season_promoted),
        "promoted_rosters": season_promoted,
        "stage_count": len(walk["stages"]),
        "void_fixture_count": len(walk["void_fixtures"]),
        "voided_points_total": points(voided_total),
    }

    tier_counts = {}
    for roster in active:
        tier = rosters[roster]["tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    artifacts["standings_audit.json"] = {
        "active_roster_count": len(active),
        "rosters": [
            {
                "adjusted_points": points(rosters[roster]["adjusted"]),
                "counted_fixtures": rosters[roster]["counted_fixtures"],
                "division_id": rosters[roster]["division_id"],
                "eligible": rosters[roster]["eligible"],
                "roster_id": roster,
                "schedule_weight_total": rosters[roster]["schedule_weight_total"],
                "tier": rosters[roster]["tier"],
            }
            for roster in active
        ],
        "tier_counts": tier_counts,
        "tier_weight_total": sum(
            rosters[roster]["schedule_weight_total"] for roster in active
        ),
    }

    artifacts["reconciliation.json"] = {
        "global_credited_points": points(credited_total),
        "global_issued_points": points(issued_total),
        "global_residual_points": points(issued_total - credited_total - voided_total),
        "global_voided_points": points(voided_total),
        "stage_count": len(walk["stages"]),
        "stages": [
            {
                "credited_points": points(credited[stage]),
                "issued_points": points(walk["issued"][stage]),
                "residual_points": points(
                    walk["issued"][stage] - credited[stage] - walk["voided"][stage]
                ),
                "stage": stage,
                "voided_points": points(walk["voided"][stage]),
            }
            for stage in walk["stages"]
        ],
    }

    artifacts["data_quality.json"] = {
        "disbanded_void_fixture_ids": walk["disbanded_voids"],
        "protests_applied": protests_applied,
        "rejected_identity_events": [
            {
                "event_id": event["event_id"],
                "reason": rejected[event["event_id"]],
                "roster_id": event["roster_id"],
                "target_id": event["target_id"],
            }
            for event in sorted(
                (e for e in season["events"] if e["event_id"] in rejected),
                key=lambda e: e["event_id"],
            )
        ],
        "superseded_filing_count": superseded,
        "unattributable_fixtures": walk["unattributable"],
        "void_fixture_count": len(walk["void_fixtures"]),
    }

    for division in divisions_in_scope:
        entries = division_order[division]
        record = season["divisions"][division]
        promoted = [
            entry["roster_id"]
            for entry in entries
            if entry["roster_id"] in division_promoted[division]
            and entry["roster_id"] not in removed_everywhere
        ]
        standings = []
        for rank, entry in enumerate(entries, start=1):
            standings.append(
                {
                    "adjusted_points": points(entry["adjusted"]),
                    "base_points": points(entry["base"]),
                    "counted_fixtures": entry["counted_fixtures"],
                    "debit_points": points(entry["debit"]),
                    "eligible": entry["eligible"],
                    "forfeit_wins": entry["forfeit_wins"],
                    "form_window_points": points(entry["form_window"]),
                    "head_to_head_points": points(entry["head_to_head"]),
                    "promoted": entry["roster_id"] in promoted,
                    "rank": rank,
                    "roster_id": entry["roster_id"],
                    "schedule_weight_total": entry["schedule_weight_total"],
                    "tier": entry["tier"],
                }
            )
        artifacts["division_%s.json" % division] = {
            "adjusted_points_total": points(sum(e["adjusted"] for e in entries)),
            "base_points_total": points(sum(e["base"] for e in entries)),
            "circuit_id": record["circuit_id"],
            "counted_fixture_slots": sum(e["counted_fixtures"] for e in entries),
            "division_id": division,
            "in_scope": True,
            "meets_quorum": meets_quorum[division],
            "promoted_rosters": promoted,
            "promotion_slots": record["promotion_slots"],
            "provisional": record["provisional"],
            "ranked_roster_ids": [e["roster_id"] for e in entries],
            "roster_count": len(entries),
            "standings": standings,
        }

    for circuit in circuits_in_scope:
        result = circuit_result[circuit]
        artifacts["circuit_%s.json" % circuit] = {
            "cap_removed_rosters": result["removed"],
            "circuit_id": circuit,
            "division_ids_in_scope": result["in_scope_divisions"],
            "division_ids_out_of_scope": result["out_of_scope_divisions"],
            "in_scope": True,
            "pre_cap_roster_count": len(result["pre_cap"]),
            "pre_cap_rosters": result["pre_cap"],
            "promoted_roster_count": len(result["promoted"]),
            "promoted_rosters": result["promoted"],
            "promotion_slots": season["circuits"][circuit]["promotion_slots"],
        }

    return artifacts


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: settle_season.py <data dir> <output dir>\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    artifacts = settle(data_dir)
    os.makedirs(out_dir, exist_ok=True)
    for name in sorted(artifacts):
        payload = json.dumps(
            artifacts[name], indent=2, sort_keys=True, ensure_ascii=True
        ) + "\n"
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="ascii", newline="\n") as handle:
            handle.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
