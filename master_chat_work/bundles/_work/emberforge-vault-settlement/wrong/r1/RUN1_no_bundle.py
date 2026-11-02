#!/usr/bin/env python3
"""Settle an Emberforge crafting season.

Usage: settle_vault.py [DATA_DIR] [OUT_DIR]   (defaults /app/data /app/out)

Four conventions of a council year - the salvage return schedule, the reduction
convention, the charge operator order and the scarcity reference - are written
in no rulebook; only the register of candidates is published.  This program
replays the published calibration slice under every candidate draw and keeps the
single draw that reproduces every published figure of the slice.  That draw then
settles the season proper.
"""

import csv
import json
import os
import sys
from collections import defaultdict

DEFAULT_DATA_DIR = "/app/data"
DEFAULT_OUT_DIR = "/app/out"
CAL = "calibration_"

FALLBACK = {
    "schedules": {"RS-A": (40, 50, 60), "RS-B": (45, 55, 65), "RS-C": (50, 60, 70),
                  "RS-D": (35, 50, 65), "RS-E": (55, 55, 55), "RS-F": (30, 45, 60),
                  "RS-G": (60, 50, 40)},
    "reductions": ("floor", "ceil", "half-up", "half-down", "half-even"),
    "orders": ("FGS", "FSG", "GFS", "GSF", "SFG", "SGF"),
    "references": ("opening", "opening-plus-acquired", "consumed", "acquired"),
}


def truthy(value):
    return str(value).strip().lower() in ("1", "true", "yes", "y", "t")


def reduce_fraction(num, den, mode):
    """Reduce num/den to a whole number under the season's reduction convention."""
    if den <= 0:
        raise ValueError("denominator must be positive")
    whole, rest = divmod(num, den)
    if rest == 0:
        return whole
    if mode == "floor":
        return whole
    if mode == "ceil":
        return whole + 1
    twice = 2 * rest
    if twice > den:
        return whole + 1
    if twice < den:
        return whole
    if mode == "half-up":
        return whole + 1
    if mode == "half-down":
        return whole
    if mode == "half-even":
        return whole if whole % 2 == 0 else whole + 1
    raise ValueError("unknown reduction convention: %r" % (mode,))


def read_register(data_dir):
    """Read the published register of candidate conventions."""
    path = os.path.join(data_dir, "convention_register.md")
    sections = {}
    if os.path.exists(path):
        current = None
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.rstrip("\n")
                if line.startswith("## "):
                    current = line[3:].strip().lower()
                    sections[current] = []
                elif current is not None:
                    sections[current].append(line)

    def bullets(section):
        tokens = []
        for line in sections.get(section, []):
            stripped = line.strip()
            if stripped.startswith("- `"):
                token = stripped[3:].split("`", 1)[0].strip()
                if token and token not in tokens:
                    tokens.append(token)
        return tokens

    schedules = {}
    for line in sections.get("return schedules", []):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 4:
            continue
        try:
            schedules[cells[0]] = tuple(int(cell) for cell in cells[1:4])
        except ValueError:
            continue

    orders = []
    for line in sections.get("operator orders", []):
        for token in line.split("`")[1::2]:
            token = token.strip()
            if len(token) == 3 and sorted(token) == ["F", "G", "S"] and token not in orders:
                orders.append(token)

    return {
        "schedules": schedules or dict(FALLBACK["schedules"]),
        "reductions": bullets("reduction conventions") or list(FALLBACK["reductions"]),
        "orders": orders or list(FALLBACK["orders"]),
        "references": bullets("scarcity references") or list(FALLBACK["references"]),
    }


def candidate_draws(register):
    """Every draw the register allows, in a canonical order."""
    draws = []
    for schedule in sorted(register["schedules"]):
        rates = register["schedules"][schedule]
        for reduction in register["reductions"]:
            for order in register["orders"]:
                for reference in register["references"]:
                    draws.append({"schedule": schedule,
                                  "rates": {i + 1: r for i, r in enumerate(rates)},
                                  "reduction": reduction,
                                  "order": order,
                                  "reference": reference})
    return draws


class Identity(object):
    """Handles resolve to canonical smiths as a function of the day."""

    def __init__(self, events):
        self.aliases = sorted((e for e in events if e["kind"] in ("rename", "merge")),
                              key=lambda e: (e["day"], e["event_id"]))
        self.retires = sorted((e for e in events if e["kind"] == "retire"),
                              key=lambda e: (e["day"], e["event_id"]))
        self._canon = {}
        self._retired = {}

    def canonical(self, handle, day):
        key = (handle, day)
        if key in self._canon:
            return self._canon[key]
        current = handle
        seen = {current}
        while True:
            successor = None
            for event in self.aliases:
                if event["day"] <= day and event["from_ref"] == current:
                    successor = event["to_ref"]
                    break
            if successor is None or successor in seen:
                break
            seen.add(successor)
            current = successor
        self._canon[key] = current
        return current

    def retired(self, canonical, day):
        key = (canonical, day)
        if key not in self._retired:
            self._retired[key] = any(
                event["day"] <= day
                and self.canonical(event["from_ref"], event["day"]) == canonical
                for event in self.retires)
        return self._retired[key]


def read_csv_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def cell(row, key):
    return (row.get(key) or "").strip()


def build_editions(rows, patch_by_id):
    """Group edition rows into editions, each with the patch ordinal it enters force."""
    grouped = {}
    for row in rows:
        key = (row["artifact_id"], int(row["edition"]))
        edition = grouped.get(key)
        if edition is None:
            edition = {"artifact_id": row["artifact_id"],
                       "edition": int(row["edition"]),
                       "from_ordinal": patch_by_id[row["from_patch"]]["ordinal"],
                       "recalled": truthy(cell(row, "recalled")),
                       "lines": {}}
            grouped[key] = edition
        reagent = row["reagent_id"]
        edition["lines"][reagent] = edition["lines"].get(reagent, 0) + int(row["units_per_craft"])

    by_artifact = defaultdict(list)
    for key in sorted(grouped):
        edition = grouped[key]
        if edition["recalled"]:
            continue
        by_artifact[edition["artifact_id"]].append(edition)
    for editions in by_artifact.values():
        editions.sort(key=lambda edition: (edition["from_ordinal"], edition["edition"]))
    return dict(by_artifact)


def load_corpus(data_dir, prefix=""):
    def path(name):
        return os.path.join(data_dir, prefix + name)

    with open(path("season_charter.json"), encoding="utf-8") as handle:
        charter = json.load(handle)
    with open(path("requisitions.json"), encoding="utf-8") as handle:
        requisitions = json.load(handle)["requisitions"]

    patches = [{"patch_id": row["patch_id"],
                "opens_day": int(row["opens_day"]),
                "closes_day": int(row["closes_day"]),
                "ordinal": int(row["ordinal"])}
               for row in read_csv_rows(path("patch_calendar.csv"))]
    patches.sort(key=lambda patch: patch["ordinal"])
    patch_by_id = {patch["patch_id"]: patch for patch in patches}
    patch_of_day = {}
    for patch in patches:
        for day in range(patch["opens_day"], patch["closes_day"] + 1):
            patch_of_day[day] = patch
    first_day = min(patch["opens_day"] for patch in patches)
    last_day = max(patch["closes_day"] for patch in patches)

    workshops = {}
    for row in read_csv_rows(path("workshop_registry.csv")):
        closed_day = cell(row, "closed_day")
        workshops[row["workshop_id"]] = {
            "workshop_id": row["workshop_id"],
            "charter_id": row["charter_id"],
            "guild_id": row["guild_id"],
            "opened_day": int(row["opened_day"]),
            "closed_day": int(closed_day) if closed_day else None,
            "charter_tier": int(row["charter_tier"]),
            "provisional": truthy(cell(row, "provisional_charter")),
        }

    in_scope = sorted(
        workshop_id for workshop_id, workshop in workshops.items()
        if workshop["opened_day"] <= first_day
        and (workshop["closed_day"] is None or workshop["closed_day"] >= last_day)
        and workshop["charter_tier"] >= 2)
    guilds_in_scope = sorted({workshops[workshop_id]["guild_id"] for workshop_id in in_scope})

    extension = charter.get("extension_patch")
    allowance = charter.get("tier_extension_allowance", {})
    charge_cap = {}
    for workshop_id in in_scope:
        tier = str(workshops[workshop_id]["charter_tier"])
        cap = int(charter["tier_charge_cap"][tier])
        if extension:
            cap += int(allowance.get(tier, 0))
        if workshops[workshop_id]["provisional"]:
            cap = cap // 2
        charge_cap[workshop_id] = cap

    artifacts = {}
    for row in read_csv_rows(path("artifact_catalogue.csv")):
        artifacts[row["artifact_id"]] = {"artifact_id": row["artifact_id"],
                                         "family": row["family"],
                                         "tier": int(row["tier"]),
                                         "base_charge": int(row["base_charge"])}

    reagents = {}
    for row in read_csv_rows(path("reagent_registry.csv")):
        reagents[row["reagent_id"]] = {"reagent_id": row["reagent_id"],
                                       "grade": int(row["grade"]),
                                       "scarce": truthy(cell(row, "scarce"))}
    reagent_order = sorted(reagents)
    scarce_order = [r for r in reagent_order if reagents[r]["scarce"]]

    opening = {row["reagent_id"]: int(row["opening_units"])
               for row in read_csv_rows(path("vault_opening.csv"))}
    for reagent_id in reagent_order:
        opening.setdefault(reagent_id, 0)

    acquisitions_by_day = defaultdict(list)
    acquired = dict.fromkeys(reagent_order, 0)
    rows = read_csv_rows(path("reagent_acquisitions.csv"))
    rows.sort(key=lambda row: (int(row["day"]), row["acq_id"]))
    for row in rows:
        day = int(row["day"])
        if day not in patch_of_day:
            continue                      # V2: never credited, takes no part
        reagent = row["reagent_id"]
        units = int(row["units"])
        acquisitions_by_day[day].append({"reagent_id": reagent, "units": units})
        acquired[reagent] = acquired.get(reagent, 0) + units

    editions = build_editions(read_csv_rows(path("recipe_editions.csv")), patch_by_id)

    events = [{"event_id": row["event_id"], "day": int(row["day"]),
               "kind": cell(row, "kind").lower(),
               "from_ref": cell(row, "from_ref"),
               "to_ref": cell(row, "to_ref")}
              for row in read_csv_rows(path("smith_identity_events.csv"))]
    identity = Identity(events)

    registered_day = {}
    for event in sorted(events, key=lambda e: (e["day"], e["event_id"])):
        if event["kind"] != "register":
            continue
        handle = event["from_ref"] or event["to_ref"]
        canonical = identity.canonical(handle, event["day"])
        registered_day.setdefault(canonical, event["day"])

    ledger = [{"entry_id": row["entry_id"], "day": int(row["day"]),
               "workshop_id": row["workshop_id"], "smith_ref": row["smith_ref"],
               "op": cell(row, "op").lower(), "artifact_id": row["artifact_id"],
               "units": int(row["units"]), "forge_ref": cell(row, "forge_ref")}
              for row in read_csv_rows(path("crafting_ledger.csv"))]
    ledger.sort(key=lambda entry: (entry["day"], entry["entry_id"]))
    entries_by_day = defaultdict(list)
    for entry in ledger:
        entries_by_day[entry["day"]].append(entry)

    return {"charter": charter, "requisitions": requisitions, "patches": patches,
            "patch_by_id": patch_by_id, "patch_of_day": patch_of_day,
            "first_day": first_day, "last_day": last_day,
            "workshops": workshops, "in_scope": in_scope,
            "guilds_in_scope": guilds_in_scope, "charge_cap": charge_cap,
            "artifacts": artifacts, "reagents": reagents,
            "reagent_order": reagent_order, "scarce_order": scarce_order,
            "opening": opening, "acquired": acquired,
            "acquisitions_by_day": dict(acquisitions_by_day), "editions": editions,
            "identity": identity, "registered_day": registered_day,
            "ledger": ledger, "ledger_by_id": {e["entry_id"]: e for e in ledger},
            "entries_by_day": dict(entries_by_day)}


def governing_edition(corpus, artifact_id, day):
    """The edition in force for an artifact on a day, or None (E1, E4, E5)."""
    if artifact_id not in corpus["artifacts"]:
        return None
    patch = corpus["patch_of_day"].get(day)
    if patch is None:
        return None
    chosen = None
    for edition in corpus["editions"].get(artifact_id, ()):
        if edition["from_ordinal"] <= patch["ordinal"]:
            chosen = edition
        else:
            break
    return chosen


def entry_charge(corpus, draw, indices, entry, edition, artifact, canonical, day):
    charter = corpus["charter"]
    reagents = corpus["reagents"]
    reduction = draw["reduction"]
    value = artifact["base_charge"] * entry["units"]
    top_grade = max(reagents[reagent]["grade"] for reagent in edition["lines"])
    scarcity = sum(indices.get(reagent, 0) for reagent in edition["lines"]
                   if reagents[reagent]["scarce"])
    factors = {"F": int(charter["family_multiplier"][artifact["family"]]),
               "G": 100 + int(charter["grade_step"]) * top_grade,
               "S": 100 + scarcity}
    for operator in draw["order"]:
        value = reduce_fraction(value * factors[operator], 100, reduction)
    relief_day = corpus["registered_day"].get(canonical)
    if relief_day is not None:
        home = corpus["patch_of_day"].get(relief_day)
        if home is not None and home is corpus["patch_of_day"].get(day):
            value = reduce_fraction(value * 80, 100, reduction)     # H7
    return value


def settle_pass(corpus, draw, indices):
    """Walk the ledger once (N1) at a fixed assignment of scarcity indices."""
    reduction = draw["reduction"]
    artifacts = corpus["artifacts"]
    identity = corpus["identity"]
    patch_of_day = corpus["patch_of_day"]
    ledger_by_id = corpus["ledger_by_id"]
    scope = set(corpus["in_scope"])

    balance = dict(corpus["opening"])
    accrued = dict.fromkeys(corpus["in_scope"], 0)
    closed = dict.fromkeys(corpus["in_scope"], False)
    charge_by_workshop = dict.fromkeys(corpus["in_scope"], 0)

    findings = []
    admitted = 0
    credited_salvages = 0
    uncredited_salvages = 0
    redeemed = set()
    history = defaultdict(list)
    ws_admitted = defaultdict(int)
    ws_rejected = defaultdict(int)
    ws_consumed = defaultdict(int)
    ws_returned = defaultdict(int)
    patch_consumed = defaultdict(int)
    patch_returned = defaultdict(int)
    consumed = dict.fromkeys(corpus["reagent_order"], 0)
    returned = dict.fromkeys(corpus["reagent_order"], 0)
    smiths = {}

    def smith_row(workshop_id, canonical):
        key = (workshop_id, canonical)
        row = smiths.get(key)
        if row is None:
            row = {"canonical_smith": canonical, "admitted_forges": 0,
                   "credited_salvages": 0, "charge_ember": 0}
            smiths[key] = row
        return row

    days = sorted(set(corpus["entries_by_day"]) | set(corpus["acquisitions_by_day"]))
    for day in days:
        for acquisition in corpus["acquisitions_by_day"].get(day, ()):
            reagent = acquisition["reagent_id"]
            balance[reagent] = balance.get(reagent, 0) + acquisition["units"]
        for entry in corpus["entries_by_day"].get(day, ()):
            entry_id = entry["entry_id"]
            workshop_id = entry["workshop_id"]
            canonical = identity.canonical(entry["smith_ref"], day)
            in_scope = workshop_id in scope

            refusals = []
            if not in_scope:
                refusals.append(("OUT_OF_SCOPE_WORKSHOP", workshop_id))
            if identity.retired(canonical, day):
                refusals.append(("RETIRED_SMITH", canonical))

            source = None
            resolve_day = day
            if entry["op"] == "salvage":
                source = ledger_by_id.get(entry["forge_ref"])
                if source is None:
                    refusals.append(("MISSING_FORGE_REF", entry["forge_ref"]))
                    resolve_day = None
                else:
                    resolve_day = source["day"]          # E3

            edition = None
            if resolve_day is not None:
                edition = governing_edition(corpus, entry["artifact_id"], resolve_day)
                if edition is None:
                    refusals.append(("UNRESOLVED_EDITION", entry["artifact_id"]))

            if in_scope:
                smith_row(workshop_id, canonical)        # I5

            if refusals:
                for code, detail in refusals:
                    findings.append((entry_id, code, detail))
                if in_scope:
                    ws_rejected[workshop_id] += 1
                continue

            artifact = artifacts[entry["artifact_id"]]
            patch_id = patch_of_day[day]["patch_id"]

            if entry["op"] == "forge":
                if closed[workshop_id]:                  # A4
                    findings.append((entry_id, "CAP_REACHED", workshop_id))
                    ws_rejected[workshop_id] += 1
                    continue
                wanted = {reagent: units * entry["units"]
                          for reagent, units in edition["lines"].items()}
                short = [reagent for reagent in sorted(wanted)
                         if balance.get(reagent, 0) < wanted[reagent]]
                if short:                                # V4
                    findings.append((entry_id, "STOCK_FLOOR", short[0]))
                    ws_rejected[workshop_id] += 1
                    continue
                charge = entry_charge(corpus, draw, indices, entry, edition,
                                      artifact, canonical, day)
                if accrued[workshop_id] + charge > corpus["charge_cap"][workshop_id]:
                    findings.append((entry_id, "CAP_REACHED", workshop_id))
                    closed[workshop_id] = True
                    ws_rejected[workshop_id] += 1
                    continue
                for reagent in sorted(wanted):
                    quantity = wanted[reagent]
                    balance[reagent] -= quantity
                    ws_consumed[(workshop_id, reagent)] += quantity
                    patch_consumed[(patch_id, reagent)] += quantity
                    consumed[reagent] = consumed.get(reagent, 0) + quantity
                accrued[workshop_id] += charge
                charge_by_workshop[workshop_id] += charge
                row = smith_row(workshop_id, canonical)
                row["admitted_forges"] += 1
                row["charge_ember"] += charge
                history[(canonical, artifact["family"])].append(entry_id)
                admitted += 1
                ws_admitted[workshop_id] += 1
            else:
                if entry["forge_ref"] in redeemed:       # S6
                    findings.append((entry_id, "SALVAGE_ALREADY_CREDITED", entry["forge_ref"]))
                    ws_rejected[workshop_id] += 1
                    continue
                window = [eid for eid in history[(canonical, artifact["family"])]
                          if ledger_by_id[eid]["day"] < day][-3:]
                if entry["forge_ref"] not in window:     # S2
                    findings.append((entry_id, "UNCREDITED_SALVAGE", entry["forge_ref"]))
                    uncredited_salvages += 1
                    ws_rejected[workshop_id] += 1
                    continue
                redeemed.add(entry["forge_ref"])
                rate = draw["rates"][artifact["tier"]]
                for reagent in sorted(edition["lines"]):
                    quantity = edition["lines"][reagent] * source["units"]
                    back = reduce_fraction(quantity * rate, 100, reduction)
                    balance[reagent] = balance.get(reagent, 0) + back
                    ws_returned[(workshop_id, reagent)] += back
                    patch_returned[(patch_id, reagent)] += back
                    returned[reagent] = returned.get(reagent, 0) + back
                row = smith_row(workshop_id, canonical)
                row["credited_salvages"] += 1
                credited_salvages += 1
                admitted += 1
                ws_admitted[workshop_id] += 1

    closing = {}
    for reagent in corpus["reagent_order"]:
        closing[reagent] = (corpus["opening"][reagent] + corpus["acquired"].get(reagent, 0)
                            + returned.get(reagent, 0) - consumed.get(reagent, 0))

    return {"findings": findings, "admitted": admitted,
            "credited_salvages": credited_salvages,
            "uncredited_salvages": uncredited_salvages,
            "closed": closed, "charge_by_workshop": charge_by_workshop,
            "ws_admitted": dict(ws_admitted), "ws_rejected": dict(ws_rejected),
            "ws_consumed": dict(ws_consumed), "ws_returned": dict(ws_returned),
            "patch_consumed": dict(patch_consumed), "patch_returned": dict(patch_returned),
            "consumed": consumed, "returned": returned, "closing": closing,
            "smiths": smiths}


def called_for(corpus):
    """Units of each reagent every forge of the season called for, settled or not."""
    totals = dict.fromkeys(corpus["reagent_order"], 0)
    for entry in corpus["ledger"]:
        if entry["op"] != "forge":
            continue
        edition = governing_edition(corpus, entry["artifact_id"], entry["day"])
        if edition is None:
            continue
        for reagent, units in edition["lines"].items():
            totals[reagent] = totals.get(reagent, 0) + units * entry["units"]
    return totals


def scarcity_indices(corpus, draw, result):
    """Read the scarcity indices off a settled pass (V5)."""
    ceiling = int(corpus["charter"]["scarcity_ceiling"])
    reference = draw["reference"]
    indices = {}
    for reagent in corpus["scarce_order"]:
        opening = corpus["opening"][reagent]
        acquired = corpus["acquired"].get(reagent, 0)
        if reference == "opening":
            basis = opening
        elif reference == "opening-plus-acquired":
            basis = opening + acquired
        elif reference == "acquired":
            basis = acquired
        elif reference == "consumed":
            basis = corpus["called_for"][reagent]
        else:
            raise ValueError("unknown scarcity reference: %r" % (reference,))
        if basis <= 0:
            indices[reagent] = 0
            continue
        index = reduce_fraction(100 * result["consumed"].get(reagent, 0), basis,
                               draw["reduction"])
        indices[reagent] = min(index, ceiling)
    return indices


def settle_to_fixed_point(corpus, draw):
    """V8: the one assignment of indices that agrees with the season it produces."""
    indices = dict.fromkeys(corpus["scarce_order"], 0)
    seen = []
    for _ in range(256):
        result = settle_pass(corpus, draw, indices)
        recovered = scarcity_indices(corpus, draw, result)
        if recovered == indices:
            result["scarcity_index"] = indices
            return result
        if recovered in seen:
            return None                  # cycles: no settled state under this draw
        seen.append(recovered)
        indices = recovered
    return None


def allocate(corpus, result):
    """Grant reagent units against the season's requisitions (Q1-Q9)."""
    charter = corpus["charter"]
    reagents = corpus["reagents"]
    pool = int(charter["season_pool_units"])
    guild_cap = {guild: int(units)
                 for guild, units in charter.get("guild_cap_units", {}).items()}
    tier_unit_cap = charter.get("tier_unit_cap", {})
    closing = result["closing"]
    scope = set(corpus["in_scope"])

    requisitions = sorted(corpus["requisitions"], key=lambda req: req["req_id"])
    items = []
    for req in requisitions:
        if req["workshop_id"] not in scope:                     # Q1
            continue
        workshop = corpus["workshops"][req["workshop_id"]]
        ceiling = int(tier_unit_cap.get(str(workshop["charter_tier"]), 0))
        low = max(int(req["min_units"]), 1)
        high = min(int(req["units_requested"]), ceiling)         # Q2
        choices = [0]
        if high >= low:
            choices.extend(range(low, high + 1))
        items.append({"req_id": req["req_id"], "workshop_id": req["workshop_id"],
                      "reagent_id": req["reagent_id"], "priority": int(req["priority"]),
                      "guild_id": workshop["guild_id"],
                      "charter_id": workshop["charter_id"],
                      "choices": choices})
    items.sort(key=lambda item: (item["priority"], item["req_id"]))    # Q8
    count = len(items)

    def step(index, value, state):
        """The state after granting `value` to item `index`, or None if Q3-Q6 forbid it."""
        pool_used, guild_used, reagent_used, charters = state
        if value == 0:
            return state
        item = items[index]
        if item["charter_id"] in charters:                        # Q6
            return None
        if pool_used + value > pool:                              # Q3
            return None
        guild = item["guild_id"]
        cap = guild_cap.get(guild)
        if cap is not None and guild_used.get(guild, 0) + value > cap:   # Q4
            return None
        reagent = item["reagent_id"]
        if reagents.get(reagent, {"scarce": False})["scarce"]:    # Q5
            if reagent_used.get(reagent, 0) + value > closing.get(reagent, 0):
                return None
        next_guild = dict(guild_used)
        next_guild[guild] = next_guild.get(guild, 0) + value
        next_reagent = dict(reagent_used)
        next_reagent[reagent] = next_reagent.get(reagent, 0) + value
        return (pool_used + value, next_guild, next_reagent,
                charters | {item["charter_id"]})

    def best_from(index, state):
        """The greatest total grantable from item `index` onward (Q7)."""
        if index == count:
            return 0
        best = 0
        for value in items[index]["choices"]:
            moved = step(index, value, state)
            if moved is None:
                continue
            total = value + best_from(index + 1, moved)
            if total > best:
                best = total
        return best

    state = (0, {}, {}, frozenset())
    remaining = best_from(0, state)
    grants = {}
    for index in range(count):
        for value in sorted(items[index]["choices"], reverse=True):
            moved = step(index, value, state)
            if moved is None:
                continue
            if value + best_from(index + 1, moved) == remaining:
                grants[items[index]["req_id"]] = value
                state = moved
                remaining -= value
                break

    by_workshop = dict.fromkeys(corpus["in_scope"], 0)
    assignments = []
    for req in requisitions:
        units = grants.get(req["req_id"], 0)
        assignments.append({"req_id": req["req_id"],
                            "workshop_id": req["workshop_id"],
                            "reagent_id": req["reagent_id"],
                            "allocated_units": units,
                            "served": units > 0})
        if req["workshop_id"] in by_workshop:
            by_workshop[req["workshop_id"]] += units
    total = sum(assignment["allocated_units"] for assignment in assignments)
    return {"pool_units": pool, "assignments": assignments, "allocated_total": total,
            "by_workshop": by_workshop}


def flow_rows(corpus, consumed, returned):
    rows = []
    for reagent in corpus["reagent_order"]:
        taken = consumed.get(reagent, 0)
        given = returned.get(reagent, 0)
        if taken or given:
            rows.append({"reagent_id": reagent, "consumed_units": taken,
                         "returned_units": given, "net_units": taken - given})
    return rows


def build_records(corpus, result, allocation):
    records = {}
    reagent_order = corpus["reagent_order"]

    for workshop_id in corpus["in_scope"]:
        workshop = corpus["workshops"][workshop_id]
        consumed = {reagent: units for (owner, reagent), units
                    in result["ws_consumed"].items() if owner == workshop_id}
        returned = {reagent: units for (owner, reagent), units
                    in result["ws_returned"].items() if owner == workshop_id}
        smiths = [result["smiths"][key] for key in sorted(result["smiths"])
                  if key[0] == workshop_id]
        records["workshop_%s.json" % workshop_id] = {
            "workshop_id": workshop_id,
            "guild_id": workshop["guild_id"],
            "charter_id": workshop["charter_id"],
            "charter_tier": workshop["charter_tier"],
            "entries_admitted": result["ws_admitted"].get(workshop_id, 0),
            "entries_rejected": result["ws_rejected"].get(workshop_id, 0),
            "charge_ember": result["charge_by_workshop"][workshop_id],
            "cap_ember": corpus["charge_cap"][workshop_id],
            "cap_reached": result["closed"][workshop_id],
            "allocated_units": allocation["by_workshop"].get(workshop_id, 0),
            "smiths": [dict(row) for row in smiths],
            "reagent_flow": flow_rows(corpus, consumed, returned),
        }

    charge_by_guild = {}
    for guild in corpus["guilds_in_scope"]:
        members = [workshop_id for workshop_id in corpus["in_scope"]
                   if corpus["workshops"][workshop_id]["guild_id"] == guild]
        consumed = defaultdict(int)
        returned = defaultdict(int)
        for workshop_id in members:
            for (owner, reagent), units in result["ws_consumed"].items():
                if owner == workshop_id:
                    consumed[reagent] += units
            for (owner, reagent), units in result["ws_returned"].items():
                if owner == workshop_id:
                    returned[reagent] += units
        charge = sum(result["charge_by_workshop"][workshop_id] for workshop_id in members)
        charge_by_guild[guild] = charge
        records["guild_%s.json" % guild] = {
            "guild_id": guild,
            "workshops": members,
            "entries_admitted": sum(result["ws_admitted"].get(w, 0) for w in members),
            "charge_ember": charge,
            "allocated_units": sum(allocation["by_workshop"].get(w, 0) for w in members),
            "reagent_flow": flow_rows(corpus, consumed, returned),
        }

    running = dict(corpus["opening"])
    patch_rows = []
    season_residual = 0
    for patch in corpus["patches"]:
        patch_id = patch["patch_id"]
        rows = []
        patch_residual = 0
        for reagent in reagent_order:
            opening = running[reagent]
            acquired = sum(acq["units"]
                           for day in range(patch["opens_day"], patch["closes_day"] + 1)
                           for acq in corpus["acquisitions_by_day"].get(day, ())
                           if acq["reagent_id"] == reagent)
            given = result["patch_returned"].get((patch_id, reagent), 0)
            taken = result["patch_consumed"].get((patch_id, reagent), 0)
            closing = opening + acquired + given - taken
            residual = opening + acquired + given - taken - closing
            patch_residual += abs(residual)
            rows.append({"reagent_id": reagent, "opening_units": opening,
                         "acquired_units": acquired, "returned_units": given,
                         "consumed_units": taken, "closing_units": closing,
                         "residual": residual})
            running[reagent] = closing
        season_residual += patch_residual
        patch_rows.append({"patch_id": patch_id, "ordinal": patch["ordinal"],
                           "reagents": rows, "residual": patch_residual})

    for reagent in reagent_order:
        if running[reagent] != result["closing"][reagent]:
            raise SystemExit("conservation broke for %s" % reagent)

    charge_total = sum(result["charge_by_workshop"][w] for w in corpus["in_scope"])
    if charge_total != sum(charge_by_guild.values()):
        raise SystemExit("workshop and guild charges disagree")

    records["reconciliation.json"] = {
        "patches": patch_rows,
        "season_residual": season_residual,
        "charge_by_workshop": {w: result["charge_by_workshop"][w] for w in corpus["in_scope"]},
        "charge_by_guild": {g: charge_by_guild[g] for g in corpus["guilds_in_scope"]},
        "charge_total": charge_total,
    }

    records["vault_audit.json"] = {"reagents": [
        {"reagent_id": reagent,
         "grade": corpus["reagents"][reagent]["grade"],
         "scarce": corpus["reagents"][reagent]["scarce"],
         "opening_units": corpus["opening"][reagent],
         "acquired_units": corpus["acquired"].get(reagent, 0),
         "returned_units": result["returned"].get(reagent, 0),
         "consumed_units": result["consumed"].get(reagent, 0),
         "closing_units": result["closing"][reagent],
         "scarcity_index": result["scarcity_index"].get(reagent, 0)}
        for reagent in reagent_order]}

    seen = {}
    for entry_id, code, detail in result["findings"]:
        seen.setdefault((entry_id, code), detail)
    counts = defaultdict(int)
    findings = []
    for key in sorted(seen):
        findings.append({"entry_id": key[0], "code": key[1], "detail": seen[key]})
        counts[key[1]] += 1
    records["data_quality.json"] = {
        "findings": findings,
        "counts": {code: counts[code] for code in sorted(counts)},
    }

    records["allocation.json"] = {
        "pool_units": allocation["pool_units"],
        "assignments": allocation["assignments"],
        "allocated_total": allocation["allocated_total"],
    }

    records["summary.json"] = {
        "season": {"first_day": corpus["first_day"], "last_day": corpus["last_day"],
                   "patch_count": len(corpus["patches"])},
        "workshops_in_scope": list(corpus["in_scope"]),
        "guilds_in_scope": list(corpus["guilds_in_scope"]),
        "entries_total": len(corpus["ledger"]),
        "entries_admitted": result["admitted"],
        "entries_rejected": len(corpus["ledger"]) - result["admitted"],
        "credited_salvages": result["credited_salvages"],
        "uncredited_salvages": result["uncredited_salvages"],
        "scarcity_index": {reagent: result["scarcity_index"][reagent]
                           for reagent in corpus["scarce_order"]},
        "season_charge_ember": charge_total,
        "allocated_units_total": allocation["allocated_total"],
        "conservation_residual": season_residual,
    }
    return records


def settle_season(corpus, draw):
    result = settle_to_fixed_point(corpus, draw)
    if result is None:
        return None
    return build_records(corpus, result, allocate(corpus, result))


def published_records(data_dir):
    """The slice's settlement as the council published it, keyed by record name."""
    published = {}
    with open(os.path.join(data_dir, CAL + "controls.json"), encoding="utf-8") as handle:
        published["summary.json"] = json.load(handle)
    with open(os.path.join(data_dir, "example_workshop_report.json"), encoding="utf-8") as handle:
        report = json.load(handle)
    published["workshop_%s.json" % report["workshop_id"]] = report
    return published


def recover_draw(data_dir):
    """The one draw from the register that reproduces every published slice figure."""
    register = read_register(data_dir)
    published = published_records(data_dir)
    slice_corpus = load_corpus(data_dir, CAL)
    slice_corpus["called_for"] = called_for(slice_corpus)
    matches = []
    for draw in candidate_draws(register):
        records = settle_season(slice_corpus, draw)
        if records is None:
            continue
        ok = True
        for name, record in published.items():
            got = records.get(name)
            if name.startswith("workshop_"):
                got = {"workshop_id": got["workshop_id"], "returned_units": {r["reagent_id"]: r["returned_units"] for r in got["reagent_flow"] if r["returned_units"]}} if got else None
            ok = ok and got == record
        if ok:
            matches.append(draw)
    if len(matches) != 1:
        raise SystemExit("the calibration slice admits %d draws, not one" % len(matches))
    return matches[0]


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main(argv):
    data_dir = argv[1] if len(argv) > 1 else DEFAULT_DATA_DIR
    out_dir = argv[2] if len(argv) > 2 else DEFAULT_OUT_DIR

    draw = recover_draw(data_dir)
    corpus = load_corpus(data_dir, "")
    corpus["called_for"] = called_for(corpus)
    records = settle_season(corpus, draw)
    if records is None:
        raise SystemExit("the season reaches no settled state under the recovered draw")

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    for name in sorted(records):
        write_json(os.path.join(out_dir, name), records[name])

    summary = records["summary.json"]
    print("return schedule      %s" % draw["schedule"])
    print("reduction convention %s" % draw["reduction"])
    print("operator order       %s" % draw["order"])
    print("scarcity reference   %s" % draw["reference"])
    print("season charge        %d ember" % summary["season_charge_ember"])
    print("entries admitted     %d of %d" % (summary["entries_admitted"],
                                             summary["entries_total"]))
    print("units allocated      %d" % summary["allocated_units_total"])
    print("conservation         %d" % summary["conservation_residual"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
