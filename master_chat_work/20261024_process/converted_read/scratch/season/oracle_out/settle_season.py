#!/usr/bin/env python3
"""Settle a ranked ladder season from its flat records.

Usage: settle_season.py DATA_DIR OUT_DIR

Every rule is taken from the rulebook files that sit beside the records, and
every artifact shape from artifact_contract.md. The three season constants the
rulebook leaves out are recovered as calibration.md describes: the published
miniature season is settled under every admissible assignment of them, and the
single assignment that reproduces all of its published figures is the one used.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from fractions import Fraction
from itertools import permutations
from pathlib import Path

# Rulebook: Scoring. Base milli-points per outcome, as (home side, away side).
WIN_AWARD = 3000
BASE_AWARDS = {
    "home_win": (3000, 0),
    "away_win": (0, 3000),
    "draw": (1000, 1000),
    "home_otw": (2000, 1000),
    "away_otw": (1000, 2000),
}
# A forfeit names the side that forfeited; the other side holds the forfeit win.
FORFEIT_WINNER = {"home_forfeit": "away", "away_forfeit": "home"}
VOID_OUTCOME = "void"

# Rulebook: Discipline.
SEVERITY_DEBIT = {"minor": 500, "major": 1500, "severe": 4000}
DEBIT_CAP = 6000
INELIGIBLE_FROM = 4500
AMNESTY_DATE = "2049-01-01"

# Rulebook: Standings.
TIER_BANDS = ((14000, "A"), (10000, "B"), (6500, "C"))
LOWEST_TIER = "D"
HIGHEST_TIER = "A"
OPPONENT_WEIGHT = {"A": 1150, "B": 1000, "C": 900, "D": 800}
FORM_WINDOW = 4

# calibration.md: what each absent constant may be.
RATE_CANDIDATES = sorted(
    {Fraction(n, d) for d in range(1, 5) for n in range(0, d + 1)}
)
OPERATORS = ("forfeit", "debit", "schedule")
CONVERSIONS = ("floor", "ceiling", "half_up", "half_down", "half_even", "half_odd")

SEASON_CLOSE = math.inf


# ------------------------------------------------------------------ records


def read_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class League:
    """The registries and season records, with every field in its proper type."""

    def __init__(self, tables: dict):
        self.circuit_slots = {
            row["circuit_id"]: int(row["promotion_slots"]) for row in tables["circuits"]
        }
        self.divisions = {
            row["division_id"]: {
                "circuit": row["circuit_id"],
                "provisional": int(row["provisional"]) == 1,
                "min_rosters": int(row["min_rosters"]),
                "slots": int(row["promotion_slots"]),
            }
            for row in tables["divisions"]
        }
        self.division_of = {row["roster_id"]: row["division_id"] for row in tables["rosters"]}
        self.region_of = {
            row["roster_id"]: row.get("home_region", "") for row in tables["rosters"]
        }
        self.fixtures = sorted(
            (
                int(row["fixture_id"]),
                int(row["stage"]),
                row["home_roster_id"],
                row["away_roster_id"],
            )
            for row in tables["fixtures"]
        )
        self.filings = defaultdict(list)
        for row in tables["filings"]:
            self.filings[int(row["fixture_id"])].append(
                {
                    "id": row["filing_id"],
                    "filed_at": row["filed_at"],
                    "result": row["result"],
                    "retracted": int(row["retracted"]) == 1,
                }
            )
        self.protests = defaultdict(list)
        for row in tables["protests"]:
            self.protests[int(row["fixture_id"])].append(row)
        self.events = [
            {
                "id": row["event_id"],
                "kind": row["kind"],
                "subject": row["roster_id"],
                "target": row["target_id"],
                "from_fixture": int(row["effective_fixture"]),
            }
            for row in tables["roster_events"]
        ]
        self.infractions = [
            {
                "id": row["infraction_id"],
                "roster": row["roster_id"],
                "filed_at": row["filed_at"],
                "severity": row["severity"],
            }
            for row in tables["infractions"]
        ]


def load_season(data_dir: Path) -> League:
    return League(
        {
            "circuits": read_rows(data_dir / "circuits.csv"),
            "divisions": read_rows(data_dir / "divisions.csv"),
            "rosters": read_rows(data_dir / "rosters.csv"),
            "fixtures": read_rows(data_dir / "fixtures.csv"),
            "filings": read_rows(data_dir / "filings.csv"),
            "roster_events": read_rows(data_dir / "roster_events.csv"),
            "infractions": read_rows(data_dir / "infractions.csv"),
            "protests": read_json(data_dir / "protests.json")["protests"],
        }
    )


def load_calibration(data_dir: Path) -> tuple[League, dict]:
    published = read_json(data_dir / "calibration_controls.json")
    return League(published), published["control_figures"]


# ----------------------------------------------------------------- identity


class Identity:
    """Rulebook: Roster identity."""

    def __init__(self, events: list[dict]):
        self.restatements = defaultdict(list)
        self.disbanded_from: dict[str, int] = {}
        self.splits = []
        for event in events:
            if event["kind"] in ("rename", "merge"):
                self.restatements[event["subject"]].append(event)
            elif event["kind"] == "disband":
                start = self.disbanded_from.get(event["subject"], event["from_fixture"])
                self.disbanded_from[event["subject"]] = min(start, event["from_fixture"])
            elif event["kind"] == "split":
                self.splits.append(event)
        for chain in self.restatements.values():
            chain.sort(key=lambda event: (event["from_fixture"], event["id"]))
        self.splits.sort(key=lambda event: (event["from_fixture"], event["id"]))
        self.rejected_ids: set[str] = set()
        self.rejected: list[dict] = []
        self._reject_circles()

    def _step(self, identifier: str, fixture_id) -> dict | None:
        """The most recent restatement of an identifier in effect at a fixture."""
        in_effect = [
            event
            for event in self.restatements.get(identifier, ())
            if event["from_fixture"] <= fixture_id and event["id"] not in self.rejected_ids
        ]
        return in_effect[-1] if in_effect else None

    def _find_circle(self) -> list[str] | None:
        """A circle among the restatements in effect once every event has taken effect."""
        successor = {}
        for identifier in self.restatements:
            event = self._step(identifier, SEASON_CLOSE)
            if event is not None:
                successor[identifier] = event["target"]
        finished: set[str] = set()
        for start in sorted(successor):
            path: list[str] = []
            node = start
            while node in successor and node not in finished and node not in path:
                path.append(node)
                node = successor[node]
            if node in path:
                return path[path.index(node) :]
            finished.update(path)
        return None

    def _reject_circles(self) -> None:
        """Whether an event lies on a circle is decided over the whole season."""
        circle = self._find_circle()
        while circle is not None:
            members = set(circle)
            for identifier in circle:
                for event in self.restatements[identifier]:
                    if event["target"] in members and event["id"] not in self.rejected_ids:
                        self.rejected_ids.add(event["id"])
                        self.rejected.append(
                            {
                                "event_id": event["id"],
                                "reason": "merge_cycle",
                                "roster_id": event["subject"],
                                "target_id": event["target"],
                            }
                        )
            circle = self._find_circle()

    def resolve(self, identifier: str, fixture_id) -> str:
        """Follow the chain in effect for this fixture to its last identifier."""
        visited = {identifier}
        while True:
            event = self._step(identifier, fixture_id)
            if event is None or event["target"] in visited:
                return identifier
            identifier = event["target"]
            visited.add(identifier)

    def after_splits(self, side: str, fixture_id: int, home_region: str, region_of) -> str:
        for event in self.splits:
            if (
                fixture_id >= event["from_fixture"]
                and side == event["subject"]
                and region_of.get(event["target"], "") == home_region
            ):
                side = event["target"]
        return side

    def is_disbanded(self, identifier: str, fixture_id: int) -> bool:
        start = self.disbanded_from.get(identifier)
        return start is not None and fixture_id >= start


# --------------------------------------------------------------- the fixtures


def governing_outcome(filings: list[dict], protests: list[dict]) -> tuple[str, int, list]:
    """Rulebook: Filings and protests. Returns outcome, superseded count, protests applied."""
    live = sorted(
        (filing for filing in filings if not filing["retracted"]),
        key=lambda filing: (filing["filed_at"], filing["id"]),
    )
    outcome = live[0]["result"] if live else VOID_OUTCOME
    superseded = max(len(live) - 1, 0)
    applied = []
    for protest in sorted(protests, key=lambda protest: protest["protest_id"]):
        if protest["status"] == "upheld":
            outcome = protest["replacement_result"]
            applied.append(protest["protest_id"])
    return outcome, superseded, applied


class FixtureWalk:
    """One pass over the fixtures: outcomes, participants, voids and the roster ledger.

    Nothing here depends on the absent constants. Forfeits are counted rather than
    valued, so the walk is shared by every candidate assignment.
    """

    def __init__(self, league: League, identity: Identity):
        self.stages = sorted({stage for _, stage, _, _ in league.fixtures})
        self.fixture_count = len(league.fixtures)
        self.counted_count = 0
        self.superseded = 0
        self.protests_applied: list[dict] = []
        self.unattributable: list[dict] = []
        self.disband_voids: list[int] = []
        # Issued and voided points per stage, split into fixed milli-points and a
        # number of forfeits whose value waits on the forfeit credit rate.
        self.issued_fixed = defaultdict(int)
        self.issued_forfeits = defaultdict(int)
        self.voided_fixed = defaultdict(int)
        self.voided_forfeits = defaultdict(int)
        # The roster side of the ledger: what each stage put into each roster's base
        # points, and how many forfeit credits each stage made available.
        self.stage_base = defaultdict(lambda: defaultdict(int))
        self.stage_forfeit_credits = defaultdict(int)
        self.results = {roster: [] for roster in league.division_of}
        self.forfeit_wins = {roster: 0 for roster in league.division_of}

        for fixture_id, stage, home_listed, away_listed in league.fixtures:
            outcome, superseded, applied = governing_outcome(
                league.filings.get(fixture_id, []), league.protests.get(fixture_id, [])
            )
            self.superseded += superseded
            self.protests_applied.extend(
                {"fixture_id": fixture_id, "protest_id": protest_id} for protest_id in applied
            )
            if outcome != VOID_OUTCOME and outcome not in BASE_AWARDS and outcome not in FORFEIT_WINNER:
                raise ValueError(f"fixture {fixture_id} has an unknown outcome {outcome!r}")

            home_region = league.region_of.get(home_listed, "")
            home, away = (
                identity.after_splits(
                    identity.resolve(listed, fixture_id), fixture_id, home_region, league.region_of
                )
                for listed in (home_listed, away_listed)
            )
            has_result = outcome != VOID_OUTCOME
            disbanded = any(identity.is_disbanded(side, fixture_id) for side in (home, away))
            unregistered = home not in league.division_of or away not in league.division_of
            if unregistered:
                self.unattributable.append(
                    {"away_roster_id": away, "fixture_id": fixture_id, "home_roster_id": home}
                )
            if has_result and disbanded:
                self.disband_voids.append(fixture_id)

            is_forfeit = outcome in FORFEIT_WINNER
            fixed = sum(BASE_AWARDS.get(outcome, (0, 0)))
            self.issued_fixed[stage] += fixed
            self.issued_forfeits[stage] += int(is_forfeit)
            if not has_result or disbanded or unregistered:
                self.voided_fixed[stage] += fixed
                self.voided_forfeits[stage] += int(is_forfeit)
                continue

            self.counted_count += 1
            home_award, away_award = BASE_AWARDS.get(outcome, (0, 0))
            self.stage_base[stage][home] += home_award
            self.stage_base[stage][away] += away_award
            self.results[home].append((fixture_id, away, home_award))
            self.results[away].append((fixture_id, home, away_award))
            if is_forfeit:
                winner = home if FORFEIT_WINNER[outcome] == "home" else away
                self.forfeit_wins[winner] += 1
                self.stage_forfeit_credits[stage] += 1

        self.base = {
            roster: sum(points for _, _, points in rows) for roster, rows in self.results.items()
        }
        self.active = sorted(roster for roster, rows in self.results.items() if rows)

    def stage_figures(self, rate: Fraction) -> list[dict]:
        """Invariants: Point conservation, the credited side read off the roster ledger."""
        forfeit_value = rate * WIN_AWARD
        figures = []
        for stage in self.stages:
            issued = self.issued_fixed[stage] + forfeit_value * self.issued_forfeits[stage]
            voided = self.voided_fixed[stage] + forfeit_value * self.voided_forfeits[stage]
            credited = sum(self.stage_base[stage].values()) + (
                forfeit_value * self.stage_forfeit_credits[stage]
            )
            figures.append(
                {
                    "stage": stage,
                    "issued": issued,
                    "credited": credited,
                    "voided": voided,
                    "residual": issued - credited - voided,
                }
            )
        return figures


def applied_debits(league: League, identity: Identity) -> dict[str, int]:
    """Rulebook: Discipline, accrued per competitor in filed order under the cap."""
    by_competitor = defaultdict(list)
    for infraction in league.infractions:
        owner = identity.resolve(infraction["roster"], SEASON_CLOSE)
        if owner in league.division_of:
            by_competitor[owner].append(infraction)
    debits = {roster: 0 for roster in league.division_of}
    for owner, infractions in by_competitor.items():
        for infraction in sorted(infractions, key=lambda i: (i["filed_at"], i["id"])):
            if infraction["filed_at"] < AMNESTY_DATE:
                continue
            room = DEBIT_CAP - debits[owner]
            debits[owner] += min(SEVERITY_DEBIT[infraction["severity"]], room)
    return debits


# ----------------------------------------------------------------- standings


def whole_milli(quantity: Fraction, convention: str) -> int:
    below = math.floor(quantity)
    if quantity == below or convention == "floor":
        return below
    if convention == "ceiling":
        return below + 1
    excess = quantity - below
    if excess != Fraction(1, 2):
        return below + 1 if excess > Fraction(1, 2) else below
    if convention == "half_up":
        return below + 1
    if convention == "half_down":
        return below
    if convention == "half_even":
        return below if below % 2 == 0 else below + 1
    if convention == "half_odd":
        return below if below % 2 == 1 else below + 1
    raise ValueError(f"unknown conversion {convention!r}")


def tier_of(adjusted: int) -> str:
    for lower_bound, tier in TIER_BANDS:
        if adjusted >= lower_bound:
            return tier
    return LOWEST_TIER


class Standings:
    """Adjusted points, tiers, orderings and promotions under one assignment."""

    def __init__(self, league, walk, debits, rate, order, conversion):
        self.league = league
        self.walk = walk
        self.debits = debits
        self.rate = rate
        self.order = order
        self.conversion = conversion
        self.tiers = self._stable_tiers(LOWEST_TIER)
        self.unique = self.tiers == self._stable_tiers(HIGHEST_TIER)
        self.adjusted = {roster: self._adjusted(roster, self.tiers) for roster in walk.active}
        self.stage_figures = walk.stage_figures(rate)
        self.credited_total = sum(stage["credited"] for stage in self.stage_figures)
        self.ineligible = {r for r in walk.active if debits[r] >= INELIGIBLE_FROM}
        self.members = defaultdict(list)
        for roster in walk.active:
            self.members[league.division_of[roster]].append(roster)
        self._decide_scope()
        self.form = {roster: self._form(roster) for roster in walk.active}
        self.head_to_head = {roster: self._head_to_head(roster) for roster in walk.active}
        self.ranking = {
            division: sorted(self.members.get(division, []), key=self.ordering_key)
            for division in league.divisions
        }
        self._promote()

    def _adjusted(self, roster: str, tiers: dict) -> int:
        points = Fraction(self.walk.base[roster])
        rows = self.walk.results[roster]
        for operator in self.order:
            if operator == "forfeit":
                points += self.rate * WIN_AWARD * self.walk.forfeit_wins[roster]
            elif operator == "debit":
                points = max(points - self.debits[roster], Fraction(0))
            else:
                weight = sum(OPPONENT_WEIGHT[tiers[opponent]] for _, opponent, _ in rows)
                points *= Fraction(weight, 1000 * len(rows))
        return whole_milli(points, self.conversion)

    def _stable_tiers(self, start: str) -> dict:
        """Rulebook: Standings, the stable tier assignment.

        Reading a tier off adjusted points is monotone in the opponents' tiers, so
        sweeping the rosters in place until nothing changes reaches the least stable
        assignment from all D and the greatest from all A.
        """
        tiers = {roster: start for roster in self.walk.active}
        changed = True
        while changed:
            changed = False
            for roster in self.walk.active:
                tier = tier_of(self._adjusted(roster, tiers))
                if tier != tiers[roster]:
                    tiers[roster] = tier
                    changed = True
        return tiers

    def _decide_scope(self) -> None:
        """Rulebook: Structure, quorum and scope."""
        divisions = self.league.divisions
        self.quorum = {
            division: len(self.members.get(division, [])) >= spec["min_rosters"]
            for division, spec in divisions.items()
        }
        live = {
            division
            for division, spec in divisions.items()
            if not spec["provisional"] and self.quorum[division]
        }
        self.circuit_in_scope = {
            circuit: any(divisions[d]["circuit"] == circuit for d in live)
            for circuit in self.league.circuit_slots
        }
        self.division_in_scope = {
            division: division in live and self.circuit_in_scope[spec["circuit"]]
            for division, spec in divisions.items()
        }

    def _form(self, roster: str) -> int:
        latest = sorted(self.walk.results[roster])[-FORM_WINDOW:]
        return sum(points for _, _, points in latest)

    def _head_to_head(self, roster: str) -> int:
        division = self.league.division_of[roster]
        tied = {
            other
            for other in self.members[division]
            if other != roster and self.adjusted[other] == self.adjusted[roster]
        }
        return sum(points for _, opponent, points in self.walk.results[roster] if opponent in tied)

    def ordering_key(self, roster: str) -> tuple:
        """Rulebook: Standings, division ordering."""
        return (-self.adjusted[roster], -self.head_to_head[roster], -self.form[roster], roster)

    def _promote(self) -> None:
        """Rulebook: Standings, division promotion then the circuit cap."""
        self.promoted = {}
        for division, spec in self.league.divisions.items():
            if not self.division_in_scope[division]:
                self.promoted[division] = []
                continue
            eligible = [r for r in self.ranking[division] if r not in self.ineligible]
            self.promoted[division] = eligible[: spec["slots"]]
        self.cap_removed = {circuit: [] for circuit in self.league.circuit_slots}
        for circuit, slots in self.league.circuit_slots.items():
            if not self.circuit_in_scope[circuit]:
                continue
            candidates = sorted(
                (
                    roster
                    for division in self.divisions_of(circuit)
                    if self.division_in_scope[division]
                    for roster in self.promoted[division]
                ),
                key=self.ordering_key,
            )
            removed = set(candidates[slots:])
            self.cap_removed[circuit] = sorted(removed)
            for division in self.divisions_of(circuit):
                self.promoted[division] = [r for r in self.promoted[division] if r not in removed]

    def divisions_of(self, circuit: str) -> list[str]:
        return [d for d, spec in self.league.divisions.items() if spec["circuit"] == circuit]

    def schedule_weight(self, roster: str) -> int:
        return sum(OPPONENT_WEIGHT[self.tiers[opponent]] for _, opponent, _ in self.walk.results[roster])


# ------------------------------------------------------- the absent constants


def parse_points(text: str) -> int:
    whole, _, milli = text.partition(".")
    magnitude = abs(int(whole)) * 1000 + int((milli + "000")[:3])
    return -magnitude if whole.startswith("-") else magnitude


def reproduces(standings: Standings, controls: dict) -> bool:
    """calibration.md: every published figure of the slice, all at once."""
    return (
        all(
            standings.adjusted.get(roster) == parse_points(value)
            for roster, value in controls["adjusted_points"].items()
        )
        and all(standings.tiers.get(roster) == tier for roster, tier in controls["tier"].items())
        and standings.credited_total == parse_points(controls["credited_points_total"])
        and standings.ranking[controls["division_id"]] == list(controls["ranked_roster_ids"])
    )


def recover_constants(data_dir: Path) -> tuple[Fraction, tuple, str]:
    league, controls = load_calibration(data_dir)
    identity = Identity(league.events)
    walk = FixtureWalk(league, identity)
    debits = applied_debits(league, identity)
    found = [
        (rate, order, conversion)
        for rate in RATE_CANDIDATES
        for order in permutations(OPERATORS)
        for conversion in CONVERSIONS
        if reproduces(Standings(league, walk, debits, rate, order, conversion), controls)
    ]
    if len(found) != 1:
        raise SystemExit(f"the calibration slice fits {len(found)} assignments, not exactly one")
    return found[0]


# ------------------------------------------------------------------ artifacts


def points(milli: int) -> str:
    """artifact_contract.md, Point quantities."""
    sign = "-" if milli < 0 else ""
    whole, part = divmod(abs(int(milli)), 1000)
    return f"{sign}{whole}.{part:03d}"


def division_report(league, walk, table: Standings, division: str) -> dict:
    spec = league.divisions[division]
    ranked = table.ranking[division]
    promoted = table.promoted[division]
    entries = []
    for rank, roster in enumerate(ranked, start=1):
        entries.append(
            {
                "adjusted_points": points(table.adjusted[roster]),
                "base_points": points(walk.base[roster]),
                "counted_fixtures": len(walk.results[roster]),
                "debit_points": points(table.debits[roster]),
                "eligible": roster not in table.ineligible,
                "forfeit_wins": walk.forfeit_wins[roster],
                "form_window_points": points(table.form[roster]),
                "head_to_head_points": points(table.head_to_head[roster]),
                "promoted": roster in promoted,
                "rank": rank,
                "roster_id": roster,
                "schedule_weight_total": table.schedule_weight(roster),
                "tier": table.tiers[roster],
            }
        )
    return {
        "adjusted_points_total": points(sum(table.adjusted[r] for r in ranked)),
        "base_points_total": points(sum(walk.base[r] for r in ranked)),
        "circuit_id": spec["circuit"],
        "counted_fixture_slots": sum(len(walk.results[r]) for r in ranked),
        "division_id": division,
        "in_scope": table.division_in_scope[division],
        "meets_quorum": table.quorum[division],
        "promoted_rosters": list(promoted),
        "promotion_slots": spec["slots"],
        "provisional": spec["provisional"],
        "ranked_roster_ids": list(ranked),
        "roster_count": len(ranked),
        "standings": entries,
    }


def circuit_report(table: Standings, circuit: str, slots: int) -> dict:
    held = table.divisions_of(circuit)
    in_scope = sorted(d for d in held if table.division_in_scope[d])
    promoted = sorted(r for d in in_scope for r in table.promoted[d])
    removed = table.cap_removed[circuit]
    return {
        "cap_removed_rosters": removed,
        "circuit_id": circuit,
        "division_ids_in_scope": in_scope,
        "division_ids_out_of_scope": sorted(d for d in held if not table.division_in_scope[d]),
        "in_scope": table.circuit_in_scope[circuit],
        "pre_cap_roster_count": len(promoted) + len(removed),
        "pre_cap_rosters": sorted(promoted + removed),
        "promoted_roster_count": len(promoted),
        "promoted_rosters": promoted,
        "promotion_slots": slots,
    }


def season_artifacts(league: League, identity: Identity, walk: FixtureWalk, table: Standings) -> dict:
    stages = table.stage_figures
    totals = {key: int(sum(stage[key] for stage in stages)) for key in ("issued", "credited", "voided", "residual")}
    divisions_in_scope = sorted(d for d, scoped in table.division_in_scope.items() if scoped)
    circuits_in_scope = sorted(c for c, scoped in table.circuit_in_scope.items() if scoped)
    promoted = sorted(r for d in divisions_in_scope for r in table.promoted[d])
    tier_counts = defaultdict(int)
    for roster in walk.active:
        tier_counts[table.tiers[roster]] += 1

    artifacts = {
        "summary.json": {
            "active_roster_count": len(walk.active),
            "circuit_ids_in_scope": circuits_in_scope,
            "counted_fixture_count": walk.counted_count,
            "credited_points_total": points(totals["credited"]),
            "division_ids_in_scope": divisions_in_scope,
            "fixture_count": walk.fixture_count,
            "ineligible_roster_count": len(table.ineligible),
            "issued_points_total": points(totals["issued"]),
            "promoted_roster_count": len(promoted),
            "promoted_rosters": promoted,
            "stage_count": len(stages),
            "void_fixture_count": walk.fixture_count - walk.counted_count,
            "voided_points_total": points(totals["voided"]),
        },
        "standings_audit.json": {
            "active_roster_count": len(walk.active),
            "rosters": [
                {
                    "adjusted_points": points(table.adjusted[roster]),
                    "counted_fixtures": len(walk.results[roster]),
                    "division_id": league.division_of[roster],
                    "eligible": roster not in table.ineligible,
                    "roster_id": roster,
                    "schedule_weight_total": table.schedule_weight(roster),
                    "tier": table.tiers[roster],
                }
                for roster in walk.active
            ],
            "tier_counts": dict(tier_counts),
            "tier_weight_total": sum(table.schedule_weight(roster) for roster in walk.active),
        },
        "reconciliation.json": {
            "global_credited_points": points(totals["credited"]),
            "global_issued_points": points(totals["issued"]),
            "global_residual_points": points(totals["residual"]),
            "global_voided_points": points(totals["voided"]),
            "stage_count": len(stages),
            "stages": [
                {
                    "credited_points": points(int(stage["credited"])),
                    "issued_points": points(int(stage["issued"])),
                    "residual_points": points(int(stage["residual"])),
                    "stage": stage["stage"],
                    "voided_points": points(int(stage["voided"])),
                }
                for stage in stages
            ],
        },
        "data_quality.json": {
            "disbanded_void_fixture_ids": sorted(walk.disband_voids),
            "protests_applied": sorted(walk.protests_applied, key=lambda p: p["protest_id"]),
            "rejected_identity_events": sorted(identity.rejected, key=lambda e: e["event_id"]),
            "superseded_filing_count": walk.superseded,
            "unattributable_fixtures": sorted(walk.unattributable, key=lambda u: u["fixture_id"]),
            "void_fixture_count": walk.fixture_count - walk.counted_count,
        },
    }
    for division in divisions_in_scope:
        artifacts[f"division_{division}.json"] = division_report(league, walk, table, division)
    for circuit in circuits_in_scope:
        artifacts[f"circuit_{circuit}.json"] = circuit_report(
            table, circuit, league.circuit_slots[circuit]
        )
    return artifacts


def serialize(document: dict) -> str:
    """artifact_contract.md, Serialization."""
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {Path(argv[0]).name} DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = Path(argv[1]), Path(argv[2])

    rate, order, conversion = recover_constants(data_dir)
    league = load_season(data_dir)
    identity = Identity(league.events)
    walk = FixtureWalk(league, identity)
    table = Standings(league, walk, applied_debits(league, identity), rate, order, conversion)
    if not table.unique:
        raise SystemExit("the season has more than one stable tier assignment")
    unbalanced = [stage["stage"] for stage in table.stage_figures if stage["residual"] != 0]
    if unbalanced:
        raise SystemExit(f"stages {unbalanced} do not reconcile to zero")

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, document in sorted(season_artifacts(league, identity, walk, table).items()):
        (out_dir / name).write_text(serialize(document), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
