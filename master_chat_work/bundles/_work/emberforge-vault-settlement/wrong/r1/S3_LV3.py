"""Settle one Emberforge crafting season.

Usage: settle_vault.py [DATA_DIR] [OUT_DIR]

DATA_DIR defaults to /app/data and OUT_DIR to /app/out.  The programme reads a
season corpus together with the published calibration slice that ships beside
it, recovers the council draw the slice pins down, settles the season under
that draw, and writes the eleven settled records.

Standard library only, whole-number arithmetic throughout, no clock and no
network, so the same corpus always yields the same bytes.
"""

from __future__ import annotations

import csv
import json
import sys
from bisect import bisect_right
from itertools import permutations, product
from pathlib import Path
from typing import Iterator, NamedTuple


# ---------------------------------------------------------------------------
# the register of candidate conventions
# ---------------------------------------------------------------------------

RETURN_SCHEDULES = {
    "RS-A": (40, 50, 60),
    "RS-B": (45, 55, 65),
    "RS-C": (50, 60, 70),
    "RS-D": (35, 50, 65),
    "RS-E": (55, 55, 55),
    "RS-F": (30, 45, 60),
    "RS-G": (60, 50, 40),
}

REDUCTIONS = ("floor", "ceil", "half-up", "half-down", "half-even")
OPERATOR_ORDERS = tuple("".join(seq) for seq in permutations("FGS"))
SCARCITY_REFERENCES = ("opening", "opening-plus-acquired", "consumed", "acquired")


class Draw(NamedTuple):
    """One entry taken from each of the four register tables."""

    schedule: str
    reduction: str
    order: str
    reference: str


def register_draws() -> Iterator[Draw]:
    for schedule in RETURN_SCHEDULES:
        for reduction in REDUCTIONS:
            for order in OPERATOR_ORDERS:
                for reference in SCARCITY_REFERENCES:
                    yield Draw(schedule, reduction, order, reference)


def whole(numer: int, denom: int, mode: str) -> int:
    """Reduce numer/denom to a whole number under the season's convention."""
    if denom <= 0:
        raise ValueError("the denominator of a reduction must be positive")
    lower, remainder = divmod(numer, denom)
    if remainder == 0:
        return lower
    if mode == "floor":
        return lower
    if mode == "ceil":
        return lower + 1
    doubled = remainder * 2
    if doubled > denom:
        return lower + 1
    if doubled < denom:
        return lower
    if mode == "half-up":
        return lower + 1
    if mode == "half-down":
        return lower
    if mode == "half-even":
        return lower if lower % 2 == 0 else lower + 1
    raise ValueError("unknown reduction convention %r" % (mode,))


# ---------------------------------------------------------------------------
# corpus
# ---------------------------------------------------------------------------


def _table(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _document(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Calendar:
    """The patches of a season and the days they cover."""

    def __init__(self, rows: list[dict]) -> None:
        self.patches = sorted(
            (
                {
                    "patch_id": row["patch_id"],
                    "opens_day": int(row["opens_day"]),
                    "closes_day": int(row["closes_day"]),
                    "ordinal": int(row["ordinal"]),
                }
                for row in rows
            ),
            key=lambda patch: patch["ordinal"],
        )
        self._opens = [patch["opens_day"] for patch in self.patches]

    @property
    def first_day(self) -> int:
        return self.patches[0]["opens_day"]

    @property
    def last_day(self) -> int:
        return self.patches[-1]["closes_day"]

    def patch_of(self, day: int) -> dict | None:
        seat = bisect_right(self._opens, day) - 1
        if seat < 0:
            return None
        patch = self.patches[seat]
        return patch if day <= patch["closes_day"] else None

    def covers(self, day: int) -> bool:
        return self.patch_of(day) is not None


class Roster:
    """Smith handles, the events that move them, and retirement."""

    def __init__(self, rows: list[dict]) -> None:
        events = sorted(
            ({**row, "day": int(row["day"])} for row in rows),
            key=lambda event: (event["day"], event["event_id"]),
        )
        self._moves: dict[str, list[tuple[int, str]]] = {}
        self._exits: dict[str, list[int]] = {}
        for event in events:
            kind = event["kind"]
            if kind in ("rename", "merge"):
                self._moves.setdefault(event["from_ref"], []).append(
                    (event["day"], event["to_ref"])
                )
            elif kind == "retire":
                self._exits.setdefault(event["from_ref"], []).append(event["day"])
        self._memo: dict[tuple[str, int], str] = {}

    def canonical(self, handle: str, day: int) -> str:
        key = (handle, day)
        cached = self._memo.get(key)
        if cached is not None:
            return cached
        seen = {handle}
        current = handle
        while True:
            latest = -1
            successor = None
            for moved_on, target in self._moves.get(current, ()):
                if moved_on <= day and moved_on > latest:
                    latest = moved_on
                    successor = target
            if successor is None or successor in seen:
                break
            seen.add(successor)
            current = successor
        self._memo[key] = current
        return current

    def retired(self, canonical_handle: str, day: int) -> bool:
        return any(when <= day for when in self._exits.get(canonical_handle, ()))


class RecipeBook:
    """Which edition of an artifact is in force in which patch."""

    def __init__(self, rows: list[dict], ordinals: list[int]) -> None:
        self._shelf: dict[tuple[str, int], tuple[int, list[dict]]] = {}
        grouped: dict[tuple[str, int, int], list[dict]] = {}
        for row in rows:
            grouped.setdefault(
                (row["artifact_id"], int(row["edition"]), int(row["from_patch"][1:])), []
            ).append(
                {
                    "reagent_id": row["reagent_id"],
                    "units_per_craft": int(row["units_per_craft"]),
                    "to": int(row["to_patch"][1:]),
                }
            )
        for (artifact_id, edition, from_ordinal), lines in grouped.items():
            to_ordinal = max(line["to"] for line in lines)
            body = sorted(
                (
                    {
                        "reagent_id": line["reagent_id"],
                        "units_per_craft": line["units_per_craft"],
                    }
                    for line in lines
                ),
                key=lambda line: line["reagent_id"],
            )
            for ordinal in ordinals:
                if from_ordinal <= ordinal <= to_ordinal:
                    seat = (artifact_id, ordinal)
                    held = self._shelf.get(seat)
                    if held is None or edition < held[0]:
                        self._shelf[seat] = (edition, body)

    def in_force(self, artifact_id: str, ordinal: int) -> list[dict] | None:
        held = self._shelf.get((artifact_id, ordinal))
        return held[1] if held else None


class Corpus:
    """Every record of one season, loaded and typed."""

    def __init__(self, data_dir: Path, prefix: str = "") -> None:
        named = lambda stem: Path(data_dir) / (prefix + stem)
        self.calendar = Calendar(_table(named("patch_calendar.csv")))
        ordinals = [patch["ordinal"] for patch in self.calendar.patches]

        self.reagents = {
            row["reagent_id"]: {
                "reagent_id": row["reagent_id"],
                "grade": int(row["grade"]),
                "family": row["family"],
                "scarce": int(row["scarce"]) == 1,
                "retired_patch": (row.get("retired_patch") or "").strip(),
            }
            for row in _table(named("reagent_registry.csv"))
        }
        self.artifacts = {
            row["artifact_id"]: {
                "artifact_id": row["artifact_id"],
                "family": row["family"],
                "tier": int(row["tier"]),
                "base_charge": int(row["base_charge"]),
            }
            for row in _table(named("artifact_catalogue.csv"))
        }
        self.recipes = RecipeBook(_table(named("recipe_editions.csv")), ordinals)
        self.workshops = {
            row["workshop_id"]: {
                "workshop_id": row["workshop_id"],
                "charter_id": row["charter_id"],
                "guild_id": row["guild_id"],
                "opened_day": int(row["opened_day"]),
                "closed_day": (
                    None if row["closed_day"] in ("", None) else int(row["closed_day"])
                ),
                "charter_tier": int(row["charter_tier"]),
            }
            for row in _table(named("workshop_registry.csv"))
        }
        self.roster = Roster(_table(named("smith_identity_events.csv")))
        self.ledger = sorted(
            (
                {
                    "entry_id": row["entry_id"],
                    "day": int(row["day"]),
                    "workshop_id": row["workshop_id"],
                    "smith_ref": row["smith_ref"],
                    "op": row["op"],
                    "artifact_id": row["artifact_id"],
                    "units": int(row["units"]),
                    "forge_ref": row["forge_ref"],
                }
                for row in _table(named("crafting_ledger.csv"))
            ),
            key=lambda entry: (entry["day"], entry["entry_id"]),
        )
        # V2: an acquisition recorded for a day the calendar does not cover is
        # never credited and takes no part in the settlement.
        self.acquisitions = sorted(
            (
                {
                    "acq_id": row["acq_id"],
                    "patch_id": row["patch_id"],
                    "day": int(row["day"]),
                    "reagent_id": row["reagent_id"],
                    "units": int(row["units"]),
                }
                for row in _table(named("reagent_acquisitions.csv"))
                if self.calendar.covers(int(row["day"]))
            ),
            key=lambda row: (row["day"], row["acq_id"]),
        )
        self.opening = {reagent_id: 0 for reagent_id in self.reagents}
        for row in _table(named("vault_opening.csv")):
            self.opening[row["reagent_id"]] = int(row["opening_units"])
        self.requisitions = sorted(
            _document(named("requisitions.json"))["requisitions"],
            key=lambda req: req["req_id"],
        )
        self.charter = _document(named("season_charter.json"))

        self.forges = {
            entry["entry_id"]: entry for entry in self.ledger if entry["op"] == "forge"
        }
        self.in_scope = tuple(
            sorted(
                workshop_id
                for workshop_id, workshop in self.workshops.items()
                if self._participates(workshop)
            )
        )
        self.guilds = tuple(
            sorted({self.workshops[w]["guild_id"] for w in self.in_scope})
        )
        self.scarce = tuple(
            sorted(rid for rid, reagent in self.reagents.items() if reagent["scarce"])
        )
        # V9: a reagent leaves the vault from the first day of its retired patch.
        opens = {patch["patch_id"]: patch["opens_day"] for patch in self.calendar.patches}
        self.retired_from = {
            rid: opens[reagent["retired_patch"]]
            for rid, reagent in self.reagents.items()
            if reagent["retired_patch"] in opens
        }

    def _participates(self, workshop: dict) -> bool:
        """A2: opened in time, still open at the close, charter tier 2 or above."""
        if workshop["opened_day"] > self.calendar.first_day:
            return False
        if (
            workshop["closed_day"] is not None
            and workshop["closed_day"] < self.calendar.last_day
        ):
            return False
        return workshop["charter_tier"] >= 2

    def acquired_total(self) -> dict[str, int]:
        totals = {reagent_id: 0 for reagent_id in self.reagents}
        for row in self.acquisitions:
            totals[row["reagent_id"]] += row["units"]
        return totals


# ---------------------------------------------------------------------------
# settlement
# ---------------------------------------------------------------------------


class Sweep:
    """What one walk of the ledger at a fixed assignment leaves behind."""

    __slots__ = (
        "indices",
        "accrued",
        "closed",
        "consumed",
        "returned",
        "called_for",
        "movement",
        "state",
        "findings",
        "balance",
        "windows",
        "redeemed",
    )


class Settlement:
    """Settle one corpus under one draw."""

    def __init__(self, corpus: Corpus, draw: Draw) -> None:
        self.corpus = corpus
        self.draw = draw
        self.rates = dict(zip((1, 2, 3), RETURN_SCHEDULES[draw.schedule]))
        charter = corpus.charter
        self.family_multiplier = charter["family_multiplier"]
        self.grade_step = int(charter["grade_step"])
        self.ceiling = int(charter["scarcity_ceiling"])
        self.charge_cap = {int(k): int(v) for k, v in charter["tier_charge_cap"].items()}
        self.acquired = corpus.acquired_total()
        self._resolve()

    # -- what can be read off an entry as filed, before any settlement

    def _resolve(self) -> None:
        self.bom: dict[str, list[dict] | None] = {}
        self.standing: list[dict] = []
        self.barred: set[str] = set()
        for entry in self.corpus.ledger:
            lines, bars = self._read_entry(entry)
            self.bom[entry["entry_id"]] = lines
            if bars:
                self.barred.add(entry["entry_id"])
            for code, detail in bars:
                self.standing.append(
                    {"entry_id": entry["entry_id"], "code": code, "detail": detail}
                )

    def _governing_day(self, entry: dict) -> int | None:
        """E2 for a forge; E3 for a salvage, or None when S1 finds no forge."""
        if entry["op"] == "forge":
            return entry["day"]
        source = self.corpus.forges.get(entry["forge_ref"])
        return None if source is None else source["day"]

    def _read_entry(self, entry: dict) -> tuple[list[dict] | None, list[tuple[str, str]]]:
        """The governing edition, and every static condition that holds (N3)."""
        corpus = self.corpus
        bars: list[tuple[str, str]] = []
        lines = None
        day = self._governing_day(entry)
        if day is None:
            bars.append(("MISSING_FORGE_REF", entry["forge_ref"]))
        else:
            patch = corpus.calendar.patch_of(day)
            if patch is not None and entry["artifact_id"] in corpus.artifacts:
                lines = corpus.recipes.in_force(entry["artifact_id"], patch["ordinal"])
            if lines is None:
                bars.append(("UNRESOLVED_EDITION", entry["artifact_id"]))
        if entry["workshop_id"] not in corpus.in_scope:
            bars.append(("OUT_OF_SCOPE_WORKSHOP", entry["workshop_id"]))
        smith = corpus.roster.canonical(entry["smith_ref"], entry["day"])
        if corpus.roster.retired(smith, entry["day"]):
            bars.append(("RETIRED_SMITH", smith))
        return lines, bars

    # -- H1 through H5

    def _charge(self, entry: dict, lines: list[dict], indices: dict[str, int]) -> int:
        corpus = self.corpus
        artifact = corpus.artifacts[entry["artifact_id"]]
        value = artifact["base_charge"] * entry["units"]
        top_grade = max(corpus.reagents[line["reagent_id"]]["grade"] for line in lines)
        scarcity = sum(
            indices.get(line["reagent_id"], 0)
            for line in lines
            if corpus.reagents[line["reagent_id"]]["scarce"]
        )
        percent = {
            "F": int(self.family_multiplier[artifact["family"]]),
            "G": 100 + self.grade_step * top_grade,
            "S": 100 + scarcity,
        }
        for operator in self.draw.order:
            value = whole(value * percent[operator], 100, self.draw.reduction)
        return value

    # -- one walk of the ledger at a fixed assignment

    def _sweep(self, indices: dict[str, int]) -> Sweep:
        corpus = self.corpus
        walk = Sweep()
        walk.balance = dict(corpus.opening)
        walk.accrued = {workshop_id: 0 for workshop_id in corpus.in_scope}
        walk.closed = set()
        walk.consumed = {reagent_id: 0 for reagent_id in corpus.reagents}
        walk.returned = {reagent_id: 0 for reagent_id in corpus.reagents}
        walk.called_for = {reagent_id: 0 for reagent_id in corpus.reagents}
        walk.movement = {
            patch["patch_id"]: {
                reagent_id: {"acquired": 0, "returned": 0, "consumed": 0}
                for reagent_id in corpus.reagents
            }
            for patch in corpus.calendar.patches
        }
        for row in corpus.acquisitions:
            if row["patch_id"] in walk.movement:
                walk.movement[row["patch_id"]][row["reagent_id"]]["acquired"] += row["units"]
        walk.state = {}
        walk.findings = []
        walk.windows = {}
        walk.redeemed = set()

        arrivals = list(corpus.acquisitions)
        for entry in corpus.ledger:
            # V2: units recorded on a day serve entries of that day and later.
            while arrivals and arrivals[0]["day"] <= entry["day"]:
                row = arrivals.pop(0)
                walk.balance[row["reagent_id"]] += row["units"]
            here = {
                "settled": False,
                "charge": 0,
                "smith": corpus.roster.canonical(entry["smith_ref"], entry["day"]),
                "flow": None,
            }
            walk.state[entry["entry_id"]] = here
            lines = self.bom[entry["entry_id"]]
            if lines is not None and entry["op"] == "forge" and entry["entry_id"] in self.barred:
                for line in lines:
                    walk.called_for[line["reagent_id"]] += line["units_per_craft"] * entry["units"]
            if lines is None or entry["entry_id"] in self.barred:
                continue
            if entry["op"] == "forge":
                bars = self._forge(walk, entry, lines, here, indices)
            else:
                bars = self._salvage(walk, entry, lines, here)
            for code, detail in bars:
                walk.findings.append(
                    {"entry_id": entry["entry_id"], "code": code, "detail": detail}
                )

        walk.indices = self._read_indices(walk.consumed, walk.called_for)
        return walk

    def _forge(
        self, walk: Sweep, entry: dict, lines: list[dict], here: dict, indices: dict[str, int]
    ) -> list[tuple[str, str]]:
        """A4, V4 and V9 are separate conditions; a forge carries each one that holds."""
        corpus = self.corpus
        workshop_id = entry["workshop_id"]
        draw = {line["reagent_id"]: line["units_per_craft"] * entry["units"] for line in lines}
        for reagent_id, units in draw.items():
            walk.called_for[reagent_id] += units

        bars: list[tuple[str, str]] = []
        cost = 0
        if workshop_id in walk.closed:
            bars.append(("CAP_REACHED", workshop_id))
        else:
            cost = self._charge(entry, lines, indices)
            cap = self.charge_cap[corpus.workshops[workshop_id]["charter_tier"]]
            if walk.accrued[workshop_id] + cost > cap:
                walk.closed.add(workshop_id)
                bars.append(("CAP_REACHED", workshop_id))
        short = [reagent_id for reagent_id in sorted(draw) if walk.balance[reagent_id] < draw[reagent_id]]
        if short:
            bars.append(("STOCK_FLOOR", short[0]))
        retired = [
            reagent_id
            for reagent_id in sorted(draw)
            if entry["day"] >= corpus.retired_from.get(reagent_id, entry["day"] + 1)
        ]
        if retired:
            bars.append(("RETIRED_REAGENT", retired[0]))
        if bars:
            return bars

        patch_id = corpus.calendar.patch_of(entry["day"])["patch_id"]
        for reagent_id, units in draw.items():
            walk.balance[reagent_id] -= units
            walk.consumed[reagent_id] += units
            walk.movement[patch_id][reagent_id]["consumed"] += units
        walk.accrued[workshop_id] += cost
        here["settled"] = True
        here["charge"] = cost
        here["flow"] = (dict(draw), {})
        family = corpus.artifacts[entry["artifact_id"]]["family"]
        walk.windows.setdefault((here["smith"], family), []).append(
            (entry["day"], entry["entry_id"])
        )
        return []

    def _salvage(
        self, walk: Sweep, entry: dict, lines: list[dict], here: dict
    ) -> list[tuple[str, str]]:
        """S6, then the S2 credit window, then the S3 return."""
        corpus = self.corpus
        source_id = entry["forge_ref"]
        if source_id in walk.redeemed:
            return [("SALVAGE_ALREADY_CREDITED", source_id)]
        family = corpus.artifacts[entry["artifact_id"]]["family"]
        earlier = [
            forge_id
            for day, forge_id in walk.windows.get((here["smith"], family), ())
            if day < entry["day"]
        ]
        if source_id not in earlier[-3:]:
            return [("UNCREDITED_SALVAGE", source_id)]

        source_units = corpus.forges[source_id]["units"]
        rate = self.rates[corpus.artifacts[entry["artifact_id"]]["tier"]]
        patch_id = corpus.calendar.patch_of(entry["day"])["patch_id"]
        given: dict[str, int] = {}
        for line in lines:
            reagent_id = line["reagent_id"]
            back = whole(line["units_per_craft"] * source_units * rate, 100, self.draw.reduction)
            walk.balance[reagent_id] += back
            walk.returned[reagent_id] += back
            walk.movement[patch_id][reagent_id]["returned"] += back
            given[reagent_id] = given.get(reagent_id, 0) + back
        here["settled"] = True
        here["flow"] = ({}, given)
        walk.redeemed.add(source_id)
        return []

    def _read_indices(
        self, consumed: dict[str, int], called_for: dict[str, int]
    ) -> dict[str, int]:
        """V5, read against the reference the season's draw names."""
        corpus = self.corpus
        indices: dict[str, int] = {}
        for reagent_id in corpus.scarce:
            if self.draw.reference == "opening":
                base = corpus.opening[reagent_id]
            elif self.draw.reference == "opening-plus-acquired":
                base = corpus.opening[reagent_id] + self.acquired[reagent_id]
            elif self.draw.reference == "consumed":
                base = called_for[reagent_id]
            else:
                base = self.acquired[reagent_id]
            if base <= 0:
                indices[reagent_id] = 0
            else:
                indices[reagent_id] = min(
                    self.ceiling,
                    whole(100 * consumed[reagent_id], base, self.draw.reduction),
                )
        return indices

    def _climb(self, seed: int) -> dict[str, int]:
        """Walk the assignment to its fixed point from one starting height."""
        indices = {reagent_id: seed for reagent_id in self.corpus.scarce}
        history = [dict(indices)]
        for _ in range(256):
            following = self._sweep(indices).indices
            if following == indices:
                return indices
            if following in history:
                raise ArithmeticError("the scarcity assignment cycles under this draw")
            history.append(dict(following))
            indices = following
        raise ArithmeticError("the scarcity assignment does not settle under this draw")

    def stable(self) -> Sweep:
        """V8: the one assignment that agrees with the season it produces."""
        from_above = self._climb(self.ceiling)
        from_below = self._climb(0)
        if from_above != from_below:
            raise ArithmeticError("the scarcity assignment is not unique under this draw")
        confirmed = self._sweep(from_above)
        if confirmed.indices != from_above:
            raise ArithmeticError("the scarcity assignment does not reproduce itself")
        return confirmed


# ---------------------------------------------------------------------------
# the requisition plan
# ---------------------------------------------------------------------------


class Requests:
    """The eligible requisitions of a season and the limits Q2 through Q6 set."""

    def __init__(self, corpus: Corpus, eligible: list[dict], closing: dict[str, int]) -> None:
        charter = corpus.charter
        tier_cap = {int(tier): int(cap) for tier, cap in charter["tier_unit_cap"].items()}
        self.pool = int(charter["season_pool_units"])
        self.guild_cap = {name: int(cap) for name, cap in charter["guild_cap_units"].items()}
        self.vault = {rid: closing.get(rid, 0) for rid in corpus.scarce}
        self.seats = []
        for req in eligible:
            workshop = corpus.workshops[req["workshop_id"]]
            self.seats.append(
                {
                    "low": int(req["min_units"]),
                    "high": min(int(req["units_requested"]), tier_cap[workshop["charter_tier"]]),
                    "guild": workshop["guild_id"],
                    "charter": workshop["charter_id"],
                    "reagent": req["reagent_id"],
                }
            )

    def grades(self, seat: int) -> list[int]:
        """Q2: every grant a seat may receive other than nothing, largest first."""
        held = self.seats[seat]
        return list(range(held["high"], held["low"] - 1, -1))

    def best_total(self, forced: dict[int, int], need: int | None = None) -> int:
        """The largest total any plan agreeing with `forced` grants (Q3 to Q7).

        With `need` set, the search stops as soon as a plan reaches it, and a
        result below `need` means no plan does.  Returns -1 when `forced` alone
        breaks a limit.
        """
        room = {"pool": self.pool}
        guild_left = dict(self.guild_cap)
        vault_left = dict(self.vault)
        taken: set[str] = set()
        start = 0
        for seat, units in forced.items():
            if units == 0:
                continue
            held = self.seats[seat]
            if held["charter"] in taken or not held["low"] <= units <= held["high"]:
                return -1
            taken.add(held["charter"])
            room["pool"] -= units
            guild_left[held["guild"]] = guild_left.get(held["guild"], 0) - units
            if held["reagent"] in vault_left:
                vault_left[held["reagent"]] -= units
            start += units
        if room["pool"] < 0 or min(guild_left.values(), default=0) < 0 or min(vault_left.values(), default=0) < 0:
            return -1

        groups: dict[str, list[int]] = {}
        for seat, held in enumerate(self.seats):
            if seat in forced or held["charter"] in taken or held["high"] < held["low"]:
                continue
            groups.setdefault(held["charter"], []).append(seat)
        order = sorted(groups.values(), key=lambda members: -max(self.seats[m]["high"] for m in members))
        for members in order:
            members.sort(key=lambda m: -self.seats[m]["high"])

        best = {"total": start}
        target = need

        def ceiling(k: int) -> int:
            plain = 0
            by_guild: dict[str, int] = {}
            by_vault: dict[str, int] = {}
            overall = 0
            for members in order[k:]:
                overall += max(self.seats[m]["high"] for m in members)
                guild_top: dict[str, int] = {}
                vault_top: dict[str, int] = {}
                plain_top = 0
                for m in members:
                    held = self.seats[m]
                    guild_top[held["guild"]] = max(guild_top.get(held["guild"], 0), held["high"])
                    if held["reagent"] in vault_left:
                        vault_top[held["reagent"]] = max(vault_top.get(held["reagent"], 0), held["high"])
                    else:
                        plain_top = max(plain_top, held["high"])
                for name, units in guild_top.items():
                    by_guild[name] = by_guild.get(name, 0) + units
                for name, units in vault_top.items():
                    by_vault[name] = by_vault.get(name, 0) + units
                plain += plain_top
            guild_bound = sum(min(max(guild_left.get(g, 0), 0), u) for g, u in by_guild.items())
            vault_bound = plain + sum(min(max(vault_left[r], 0), u) for r, u in by_vault.items())
            return min(room["pool"], overall, guild_bound, vault_bound)

        def walk(k: int, total: int) -> bool:
            if total > best["total"]:
                best["total"] = total
                if target is not None and total >= target:
                    return True
            if k == len(order):
                return False
            reach = total + ceiling(k)
            if reach <= best["total"] or (target is not None and reach < target):
                return False
            for seat in order[k]:
                held = self.seats[seat]
                top = min(held["high"], room["pool"], guild_left.get(held["guild"], 0))
                if held["reagent"] in vault_left:
                    top = min(top, vault_left[held["reagent"]])
                for units in range(top, held["low"] - 1, -1):
                    room["pool"] -= units
                    guild_left[held["guild"]] -= units
                    if held["reagent"] in vault_left:
                        vault_left[held["reagent"]] -= units
                    done = walk(k + 1, total + units)
                    if held["reagent"] in vault_left:
                        vault_left[held["reagent"]] += units
                    guild_left[held["guild"]] += units
                    room["pool"] += units
                    if done:
                        return True
            return walk(k + 1, total)

        walk(0, start)
        return best["total"]


def fund(corpus: Corpus, closing: dict[str, int]) -> tuple[dict[str, int], int]:
    """The single plan Q1 through Q8 select."""
    # Q1: a requisition naming a workshop out of scope takes no further part.
    eligible = [req for req in corpus.requisitions if req["workshop_id"] in corpus.in_scope]
    if not eligible:
        return {}, 0
    book = Requests(corpus, eligible, closing)
    most = book.best_total({})  # Q7
    if most <= 0:
        return {}, 0
    # Q8: fix each requisition in ascending priority then identifier order at
    # the largest grant that still leaves a plan reaching the Q7 total.
    preference = sorted(
        range(len(eligible)), key=lambda seat: (int(eligible[seat]["priority"]), eligible[seat]["req_id"])
    )
    forced: dict[int, int] = {}
    for seat in preference:
        for units in book.grades(seat) + [0]:
            forced[seat] = units
            if book.best_total(forced, need=most) >= most:
                break
    return {eligible[seat]["req_id"]: forced[seat] for seat in forced}, most


# ---------------------------------------------------------------------------
# the delivered records
# ---------------------------------------------------------------------------


def _flow_rows(pairs: list[tuple[dict, dict]]) -> list[dict]:
    tally: dict[str, list[int]] = {}
    for taken, given in pairs:
        for reagent_id, units in taken.items():
            tally.setdefault(reagent_id, [0, 0])[0] += units
        for reagent_id, units in given.items():
            tally.setdefault(reagent_id, [0, 0])[1] += units
    return [
        {
            "reagent_id": reagent_id,
            "consumed_units": tally[reagent_id][0],
            "returned_units": tally[reagent_id][1],
            "net_units": tally[reagent_id][0] - tally[reagent_id][1],
        }
        for reagent_id in sorted(tally)
    ]


def compile_records(corpus: Corpus, settlement: Settlement, sweep: Sweep) -> dict:
    calendar = corpus.calendar

    closing = {
        reagent_id: corpus.opening[reagent_id]
        + settlement.acquired[reagent_id]
        + sweep.returned[reagent_id]
        - sweep.consumed[reagent_id]
        for reagent_id in corpus.reagents
    }
    grants, granted_total = fund(corpus, closing)
    grant_by_workshop = {
        req["workshop_id"]: grants.get(req["req_id"], 0) for req in corpus.requisitions
    }

    workshop_records: dict[str, dict] = {}
    for workshop_id in corpus.in_scope:
        workshop = corpus.workshops[workshop_id]
        smiths: dict[str, dict] = {}
        flows: list[tuple[dict, dict]] = []
        settled = rejected = 0
        for entry in corpus.ledger:
            if entry["workshop_id"] != workshop_id:
                continue
            here = sweep.state[entry["entry_id"]]
            if here["settled"]:
                settled += 1
            else:
                rejected += 1
            # I5: every canonical identity that appears on any entry filed
            # against the workshop is reported, settled or not.
            row = smiths.setdefault(
                here["smith"],
                {
                    "canonical_smith": here["smith"],
                    "admitted_forges": 0,
                    "credited_salvages": 0,
                    "charge_ember": 0,
                },
            )
            if here["settled"]:
                if entry["op"] == "forge":
                    row["admitted_forges"] += 1
                    row["charge_ember"] += here["charge"]
                else:
                    row["credited_salvages"] += 1
            if here["flow"] is not None:
                flows.append(here["flow"])
        workshop_records[workshop_id] = {
            "workshop_id": workshop_id,
            "guild_id": workshop["guild_id"],
            "charter_id": workshop["charter_id"],
            "charter_tier": workshop["charter_tier"],
            "entries_admitted": settled,
            "entries_rejected": rejected,
            "charge_ember": sweep.accrued[workshop_id],
            "cap_ember": settlement.charge_cap[workshop["charter_tier"]],
            "cap_reached": workshop_id in sweep.closed,
            "allocated_units": grant_by_workshop.get(workshop_id, 0),
            "smiths": sorted(smiths.values(), key=lambda row: row["canonical_smith"]),
            "reagent_flow": _flow_rows(flows),
        }

    guild_records: dict[str, dict] = {}
    for guild_id in corpus.guilds:
        members = [w for w in corpus.in_scope if corpus.workshops[w]["guild_id"] == guild_id]
        merged: dict[str, list[int]] = {}
        for member in members:
            for row in workshop_records[member]["reagent_flow"]:
                pair = merged.setdefault(row["reagent_id"], [0, 0])
                pair[0] += row["consumed_units"]
                pair[1] += row["returned_units"]
        guild_records[guild_id] = {
            "guild_id": guild_id,
            "workshops": members,
            "entries_admitted": sum(
                workshop_records[m]["entries_admitted"] for m in members
            ),
            "charge_ember": sum(workshop_records[m]["charge_ember"] for m in members),
            "allocated_units": sum(workshop_records[m]["allocated_units"] for m in members),
            "reagent_flow": [
                {
                    "reagent_id": reagent_id,
                    "consumed_units": merged[reagent_id][0],
                    "returned_units": merged[reagent_id][1],
                    "net_units": merged[reagent_id][0] - merged[reagent_id][1],
                }
                for reagent_id in sorted(merged)
            ],
        }

    vault_rows = []
    season_residual = 0
    for reagent_id in sorted(corpus.reagents):
        reagent = corpus.reagents[reagent_id]
        opening = corpus.opening[reagent_id]
        acquired = settlement.acquired[reagent_id]
        returned = sweep.returned[reagent_id]
        consumed = sweep.consumed[reagent_id]
        season_residual += abs(
            opening + acquired + returned - consumed - closing[reagent_id]
        )
        vault_rows.append(
            {
                "reagent_id": reagent_id,
                "grade": reagent["grade"],
                "scarce": reagent["scarce"],
                "opening_units": opening,
                "acquired_units": acquired,
                "returned_units": returned,
                "consumed_units": consumed,
                "closing_units": closing[reagent_id],
                "scarcity_index": sweep.indices.get(reagent_id, 0),
            }
        )

    patch_rows = []
    carried = dict(corpus.opening)
    for patch in calendar.patches:
        reagent_rows = []
        for reagent_id in sorted(corpus.reagents):
            moved = sweep.movement[patch["patch_id"]][reagent_id]
            opening = carried[reagent_id]
            shut = opening + moved["acquired"] + moved["returned"] - moved["consumed"]
            reagent_rows.append(
                {
                    "reagent_id": reagent_id,
                    "opening_units": opening,
                    "acquired_units": moved["acquired"],
                    "returned_units": moved["returned"],
                    "consumed_units": moved["consumed"],
                    "closing_units": shut,
                    "residual": opening
                    + moved["acquired"]
                    + moved["returned"]
                    - moved["consumed"]
                    - shut,
                }
            )
            carried[reagent_id] = shut
        patch_rows.append(
            {
                "patch_id": patch["patch_id"],
                "ordinal": patch["ordinal"],
                "reagents": reagent_rows,
                "residual": sum(abs(row["residual"]) for row in reagent_rows),
            }
        )

    # N3: one pair per entry and code, ascending by entry then by code.
    findings = []
    seen: set[tuple[str, str]] = set()
    for finding in sorted(
        settlement.standing + sweep.findings,
        key=lambda item: (item["entry_id"], item["code"]),
    ):
        pair = (finding["entry_id"], finding["code"])
        if pair in seen:
            continue
        seen.add(pair)
        findings.append(finding)
    tally: dict[str, int] = {}
    for finding in findings:
        tally[finding["code"]] = tally.get(finding["code"], 0) + 1

    settled_entries = sum(1 for here in sweep.state.values() if here["settled"])
    credited = sum(
        1
        for entry in corpus.ledger
        if entry["op"] == "salvage" and sweep.state[entry["entry_id"]]["settled"]
    )
    season_charge = sum(workshop_records[w]["charge_ember"] for w in corpus.in_scope)

    records = {
        "summary.json": {
            "season": {
                "first_day": calendar.first_day,
                "last_day": calendar.last_day,
                "patch_count": len(calendar.patches),
            },
            "workshops_in_scope": list(corpus.in_scope),
            "guilds_in_scope": list(corpus.guilds),
            "entries_total": len(corpus.ledger),
            "entries_admitted": settled_entries,
            "entries_rejected": len(corpus.ledger) - settled_entries,
            "credited_salvages": credited,
            "uncredited_salvages": tally.get("UNCREDITED_SALVAGE", 0),
            "scarcity_index": {rid: sweep.indices[rid] for rid in sorted(sweep.indices)},
            "season_charge_ember": season_charge,
            "allocated_units_total": granted_total,
            "conservation_residual": season_residual,
        },
        "vault_audit.json": {"reagents": vault_rows},
        "reconciliation.json": {
            "patches": patch_rows,
            "season_residual": sum(row["residual"] for row in patch_rows),
            "charge_by_workshop": {
                w: workshop_records[w]["charge_ember"] for w in corpus.in_scope
            },
            "charge_by_guild": {g: guild_records[g]["charge_ember"] for g in corpus.guilds},
            "charge_total": season_charge,
        },
        "data_quality.json": {
            "findings": findings,
            "counts": {code: tally[code] for code in sorted(tally)},
        },
        "allocation.json": {
            "pool_units": int(corpus.charter["season_pool_units"]),
            "assignments": [
                {
                    "req_id": req["req_id"],
                    "workshop_id": req["workshop_id"],
                    "reagent_id": req["reagent_id"],
                    "allocated_units": grants.get(req["req_id"], 0),
                    "served": grants.get(req["req_id"], 0) > 0,
                }
                for req in corpus.requisitions
            ],
            "allocated_total": granted_total,
        },
    }
    for workshop_id in corpus.in_scope:
        records["workshop_%s.json" % workshop_id] = workshop_records[workshop_id]
    for guild_id in corpus.guilds:
        records["guild_%s.json" % guild_id] = guild_records[guild_id]
    return records


def settle(corpus: Corpus, draw: Draw) -> dict:
    settlement = Settlement(corpus, draw)
    return compile_records(corpus, settlement, settlement.stable())


# ---------------------------------------------------------------------------
# recovering the council draw, and the driver
# ---------------------------------------------------------------------------


def recover(data_dir: Path) -> Draw:
    """The one draw that reproduces every published figure of the slice."""
    data_dir = Path(data_dir)
    slice_corpus = Corpus(data_dir, "calibration_")
    controls = _document(data_dir / "calibration_controls.json")
    example = _document(data_dir / "example_workshop_report.json")
    example_name = "workshop_%s.json" % example["workshop_id"]

    survivors = []
    for candidate in register_draws():
        try:
            settled = settle(slice_corpus, candidate)
        except (ArithmeticError, ValueError, KeyError):
            continue
        flow = settled.get(example_name, {}).get("reagent_flow", [])
        returned = {row["reagent_id"]: row["returned_units"] for row in flow if row["returned_units"]}
        if settled["summary.json"] == controls and returned == example["returned_units"]:
            survivors.append(candidate)
    if len(survivors) != 1:
        raise SystemExit(
            "the calibration slice admits %d draws; exactly one was expected"
            % len(survivors)
        )
    return survivors[0]


CANONICAL = dict(indent=2, sort_keys=False, separators=(",", ": "), ensure_ascii=False)


def write(records: dict, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(records):
        (out_dir / name).write_text(
            json.dumps(records[name], **CANONICAL) + "\n", encoding="utf-8"
        )


def run(data_dir: Path, out_dir: Path) -> dict:
    draw = recover(data_dir)
    records = settle(Corpus(Path(data_dir), ""), draw)
    write(records, out_dir)
    return records


def main(argv: list[str]) -> int:
    data_dir = Path(argv[1]) if len(argv) > 1 else Path("/app/data")
    out_dir = Path(argv[2]) if len(argv) > 2 else Path("/app/out")
    records = run(data_dir, out_dir)
    print(
        json.dumps(
            {
                "records": sorted(records),
                "season_charge_ember": records["summary.json"]["season_charge_ember"],
                "conservation_residual": records["summary.json"]["conservation_residual"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
