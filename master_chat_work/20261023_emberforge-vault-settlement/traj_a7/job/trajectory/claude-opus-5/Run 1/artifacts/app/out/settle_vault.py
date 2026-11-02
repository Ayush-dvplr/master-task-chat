#!/usr/bin/env python3
"""Settle one Emberforge crafting season.

Reads a season's records from a data directory and writes the settled season
(summary, vault audit, reconciliation, data quality, allocation, one report per
in-scope workshop and one per in-scope guild) into an output directory.

Standard library only.
"""

import csv
import json
import os
import sys

REQUIRED_FILES = [
    "patch_calendar.csv",
    "reagent_registry.csv",
    "artifact_catalogue.csv",
    "recipe_editions.csv",
    "workshop_registry.csv",
    "smith_identity_events.csv",
    "crafting_ledger.csv",
    "reagent_acquisitions.csv",
    "vault_opening.csv",
    "requisitions.json",
    "season_charter.json",
    "council_rulings.json",
]

RETURN_SCHEDULES = [
    ("RS-A", (40, 50, 60)),
    ("RS-B", (45, 55, 65)),
    ("RS-C", (50, 60, 70)),
    ("RS-D", (35, 50, 65)),
    ("RS-E", (55, 55, 55)),
    ("RS-F", (30, 45, 60)),
    ("RS-G", (60, 50, 40)),
]
REDUCTIONS = ["floor", "ceil", "half-up", "half-down", "half-even"]
OPERATOR_ORDERS = ["FGS", "FSG", "GFS", "GSF", "SFG", "SGF"]
SCARCITY_REFERENCES = ["opening", "opening-plus-acquired", "consumed", "acquired"]

CODE_CAP = "CAP_REACHED"
CODE_MISSING_FORGE = "MISSING_FORGE_REF"
CODE_OUT_OF_SCOPE = "OUT_OF_SCOPE_WORKSHOP"
CODE_RETIRED_REAGENT = "RETIRED_REAGENT"
CODE_RETIRED_SMITH = "RETIRED_SMITH"
CODE_ALREADY_CREDITED = "SALVAGE_ALREADY_CREDITED"
CODE_STOCK_FLOOR = "STOCK_FLOOR"
CODE_UNCREDITED = "UNCREDITED_SALVAGE"
CODE_UNRESOLVED = "UNRESOLVED_EDITION"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def reduce_fraction(num, den, convention):
    """Reduce num/den (den > 0) to a whole number under the given convention."""
    if convention == "floor":
        return num // den
    if convention == "ceil":
        return -((-num) // den)
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den:
        return q + 1
    if twice < den:
        return q
    if convention == "half-up":
        return q + 1
    if convention == "half-down":
        return q
    if convention == "half-even":
        return q if q % 2 == 0 else q + 1
    raise ValueError("unknown reduction convention: %s" % convention)


def truthy(value):
    return str(value).strip().lower() in ("1", "true", "yes", "y", "t")


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = []
        for row in csv.DictReader(handle):
            clean = {}
            for key, val in row.items():
                if key is None:
                    continue
                clean[key.strip()] = (val or "").strip()
            if any(clean.values()):
                rows.append(clean)
        return rows


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def as_int(value):
    return int(str(value).strip())


def write_record(out_dir, name, obj):
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.write("\n")


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

class Season(object):
    pass


def load_season(data_dir):
    missing = [n for n in REQUIRED_FILES
               if not os.path.isfile(os.path.join(data_dir, n))]
    if missing:
        for name in missing:
            sys.stderr.write("error: missing required input file: %s\n"
                             % os.path.join(data_dir, name))
        sys.exit(2)

    s = Season()

    def path(name):
        return os.path.join(data_dir, name)

    # ---- patch calendar -------------------------------------------------
    patches = []
    for row in read_csv(path("patch_calendar.csv")):
        patches.append({
            "patch_id": row["patch_id"],
            "opens_day": as_int(row["opens_day"]),
            "closes_day": as_int(row["closes_day"]),
            "ordinal": as_int(row["ordinal"]),
        })
    patches.sort(key=lambda p: (p["ordinal"], p["patch_id"]))
    s.patches = patches
    s.patch_by_id = dict((p["patch_id"], p) for p in patches)
    s.first_day = min(p["opens_day"] for p in patches)
    s.last_day = max(p["closes_day"] for p in patches)

    day_patch = {}

    def patch_of_day(day):
        if day in day_patch:
            return day_patch[day]
        found = None
        for p in patches:
            if p["opens_day"] <= day <= p["closes_day"]:
                found = p
                break
        day_patch[day] = found
        return found

    s.patch_of_day = patch_of_day

    # ---- reagents -------------------------------------------------------
    reagents = {}
    for row in read_csv(path("reagent_registry.csv")):
        rid = row["reagent_id"]
        retired_patch = row.get("retired_patch", "")
        retired_day = None
        if retired_patch and retired_patch in s.patch_by_id:
            retired_day = s.patch_by_id[retired_patch]["opens_day"]
        reagents[rid] = {
            "reagent_id": rid,
            "grade": as_int(row["grade"]),
            "scarce": truthy(row.get("scarce", "0")),
            "retired_day": retired_day,
        }
    s.reagents = reagents
    s.reagent_ids = sorted(reagents)
    s.scarce_ids = [r for r in s.reagent_ids if reagents[r]["scarce"]]

    # ---- artifacts ------------------------------------------------------
    artifacts = {}
    for row in read_csv(path("artifact_catalogue.csv")):
        artifacts[row["artifact_id"]] = {
            "artifact_id": row["artifact_id"],
            "family": row["family"],
            "tier": as_int(row["tier"]),
            "base_charge": as_int(row["base_charge"]),
        }
    s.artifacts = artifacts

    # ---- recipe editions ------------------------------------------------
    grouped = {}
    for row in read_csv(path("recipe_editions.csv")):
        if row.get("recalled") and truthy(row["recalled"]):
            continue
        patch = s.patch_by_id.get(row["from_patch"])
        if patch is None:
            continue
        key = (row["artifact_id"], as_int(row["edition"]), patch["ordinal"])
        grouped.setdefault(key, []).append(
            (row["reagent_id"], as_int(row["units_per_craft"])))
    editions_by_artifact = {}
    for (art, edition, ordinal), lines in sorted(grouped.items()):
        lines = sorted(lines)
        grades = [reagents[r]["grade"] for r, _ in lines if r in reagents]
        editions_by_artifact.setdefault(art, []).append({
            "edition": edition,
            "from_ordinal": ordinal,
            "lines": lines,
            "max_grade": max(grades) if grades else 0,
            "scarce_lines": sorted(set(r for r, _ in lines
                                       if r in reagents and reagents[r]["scarce"])),
        })
    for art in editions_by_artifact:
        editions_by_artifact[art].sort(key=lambda e: (e["from_ordinal"], e["edition"]))
    s.editions_by_artifact = editions_by_artifact

    # ---- workshops ------------------------------------------------------
    workshops = {}
    for row in read_csv(path("workshop_registry.csv")):
        closed = row.get("closed_day", "")
        provisional = any("provisional" in key.lower() and truthy(val)
                          for key, val in row.items())
        workshops[row["workshop_id"]] = {
            "workshop_id": row["workshop_id"],
            "charter_id": row["charter_id"],
            "guild_id": row["guild_id"],
            "opened_day": as_int(row["opened_day"]),
            "closed_day": as_int(closed) if closed else None,
            "charter_tier": as_int(row["charter_tier"]),
            "provisional": provisional,
        }
    s.workshops = workshops

    # ---- identity events ------------------------------------------------
    events = []
    for row in read_csv(path("smith_identity_events.csv")):
        events.append({
            "event_id": row["event_id"],
            "day": as_int(row["day"]),
            "kind": row["kind"].strip().lower(),
            "from_ref": row.get("from_ref", ""),
            "to_ref": row.get("to_ref", ""),
        })
    events.sort(key=lambda e: (e["day"], e["event_id"]))
    s.identity_events = events

    # ---- ledger ---------------------------------------------------------
    ledger = []
    for row in read_csv(path("crafting_ledger.csv")):
        ledger.append({
            "entry_id": row["entry_id"],
            "day": as_int(row["day"]),
            "workshop_id": row["workshop_id"],
            "smith_ref": row["smith_ref"],
            "op": row["op"].strip().lower(),
            "artifact_id": row["artifact_id"],
            "units": as_int(row["units"]),
            "forge_ref": row.get("forge_ref", ""),
        })
    ledger.sort(key=lambda e: (e["day"], e["entry_id"]))
    s.ledger = ledger
    s.ledger_ids = set(e["entry_id"] for e in ledger)

    # ---- acquisitions ---------------------------------------------------
    acquisitions = []
    for row in read_csv(path("reagent_acquisitions.csv")):
        acquisitions.append({
            "acq_id": row["acq_id"],
            "day": as_int(row["day"]),
            "reagent_id": row["reagent_id"],
            "units": as_int(row["units"]),
        })
    acquisitions.sort(key=lambda a: (a["day"], a["acq_id"]))
    s.acquisitions = acquisitions

    # ---- vault opening --------------------------------------------------
    opening = {}
    for row in read_csv(path("vault_opening.csv")):
        opening[row["reagent_id"]] = as_int(row["opening_units"])
    s.opening = dict((r, opening.get(r, 0)) for r in s.reagent_ids)

    # ---- requisitions ---------------------------------------------------
    reqs = []
    for row in read_json(path("requisitions.json"))["requisitions"]:
        reqs.append({
            "req_id": row["req_id"],
            "workshop_id": row["workshop_id"],
            "reagent_id": row["reagent_id"],
            "priority": as_int(row["priority"]),
            "min_units": as_int(row["min_units"]),
            "units_requested": as_int(row["units_requested"]),
        })
    s.requisitions = sorted(reqs, key=lambda r: r["req_id"])

    # ---- charter --------------------------------------------------------
    charter = read_json(path("season_charter.json"))
    s.charter = charter
    s.pool_units = as_int(charter["season_pool_units"])
    s.guild_cap = dict((k, as_int(v)) for k, v in charter["guild_cap_units"].items())
    s.tier_unit_cap = dict((int(k), as_int(v)) for k, v in charter["tier_unit_cap"].items())
    s.family_multiplier = dict((k, as_int(v)) for k, v in charter["family_multiplier"].items())
    s.grade_step = as_int(charter["grade_step"])
    s.scarcity_ceiling = as_int(charter["scarcity_ceiling"])
    s.tier_charge_cap = dict((int(k), as_int(v)) for k, v in charter["tier_charge_cap"].items())

    s.rulings = read_json(path("council_rulings.json"))
    return s


# --------------------------------------------------------------------------
# the conventions the council drew
# --------------------------------------------------------------------------

def derive_conventions(rulings):
    """Find the one draw of the convention register the year's rulings agree with."""
    charge_rulings = rulings.get("charge_rulings", [])
    return_rulings = rulings.get("return_rulings", [])
    scarcity_rulings = rulings.get("scarcity_rulings", [])

    def charge_ok(order, conv):
        for r in charge_rulings:
            pct = {"F": as_int(r["family_percent"]),
                   "G": as_int(r["grade_percent"]),
                   "S": as_int(r["scarcity_percent"])}
            value = as_int(r["base_value"])
            for op in order:
                value = reduce_fraction(value * pct[op], 100, conv)
            if value != as_int(r["charge_ember"]):
                return False
        return True

    def schedule_ok(rates, conv):
        for r in return_rulings:
            tier = as_int(r["tier"])
            if not 1 <= tier <= len(rates):
                return False
            if reduce_fraction(as_int(r["committed_units"]) * rates[tier - 1],
                               100, conv) != as_int(r["returned_units"]):
                return False
        return True

    def reference_ok(ref, conv):
        for r in scarcity_rulings:
            refv = scarcity_reference_value(
                ref, as_int(r["opening_units"]), as_int(r["acquired_units"]),
                as_int(r["called_for_units"]))
            ceiling = as_int(r["scarcity_ceiling"])
            idx = scarcity_index(as_int(r["consumed_units"]), refv, ceiling, conv)
            if idx != as_int(r["scarcity_index"]):
                return False
        return True

    for conv in REDUCTIONS:
        for order in OPERATOR_ORDERS:
            if not charge_ok(order, conv):
                continue
            for name, rates in RETURN_SCHEDULES:
                if not schedule_ok(rates, conv):
                    continue
                for ref in SCARCITY_REFERENCES:
                    if reference_ok(ref, conv):
                        return {
                            "reduction": conv,
                            "operator_order": order,
                            "return_schedule": name,
                            "return_rates": rates,
                            "scarcity_reference": ref,
                        }
    sys.stderr.write("error: the council's rulings agree with no draw of the "
                     "convention register\n")
    sys.exit(3)


def scarcity_reference_value(reference, opening, acquired, called_for):
    if reference == "opening":
        return opening
    if reference == "opening-plus-acquired":
        return opening + acquired
    if reference == "consumed":
        return called_for
    if reference == "acquired":
        return acquired
    raise ValueError("unknown scarcity reference: %s" % reference)


def scarcity_index(consumed, reference_value, ceiling, convention):
    if reference_value <= 0:
        return 0
    return min(ceiling, reduce_fraction(consumed * 100, reference_value, convention))


# --------------------------------------------------------------------------
# identity
# --------------------------------------------------------------------------

class Identity(object):
    """Canonical identities and standing under the identity rulebook."""

    def __init__(self, events):
        self.moves = [(e["day"], e["from_ref"], e["to_ref"]) for e in events
                      if e["kind"] in ("rename", "merge") and e["from_ref"] and e["to_ref"]]
        self.retires = [(e["day"], e["from_ref"] or e["to_ref"]) for e in events
                        if e["kind"] == "retire"]
        self.registers = [(e["day"], e["from_ref"] or e["to_ref"]) for e in events
                          if e["kind"] == "register"]
        self._canon = {}
        self._retired = {}

    def canonical(self, handle, day):
        key = (handle, day)
        hit = self._canon.get(key)
        if hit is not None:
            return hit
        cur = handle
        for _ in range(len(self.moves) + 1):
            changed = False
            for eday, src, dst in self.moves:
                if eday <= day and src == cur and dst != cur:
                    cur = dst
                    changed = True
            if not changed:
                break
        self._canon[key] = cur
        return cur

    def is_retired(self, handle, day):
        canon = self.canonical(handle, day)
        key = (canon, day)
        hit = self._retired.get(key)
        if hit is not None:
            return hit
        retired = False
        for rday, ref in self.retires:
            if rday > day or not ref:
                continue
            if self.canonical(ref, day) != canon:
                continue
            reinstated = any(rday < gday <= day and gref
                             and self.canonical(gref, day) == canon
                             for gday, gref in self.registers)
            if not reinstated:
                retired = True
                break
        self._retired[key] = retired
        return retired

    def registration_day(self, handle, day):
        """Earliest register day of the handle's identity as of that day, if any."""
        canon = self.canonical(handle, day)
        best = None
        for gday, gref in self.registers:
            if not gref or gday > day:
                continue
            if gref == handle or self.canonical(gref, day) == canon:
                if best is None or gday < best:
                    best = gday
        return best


# --------------------------------------------------------------------------
# settlement
# --------------------------------------------------------------------------

def in_scope_workshops(s):
    chosen = []
    for wid, w in s.workshops.items():
        if w["opened_day"] > s.first_day:
            continue
        if w["closed_day"] is not None and w["closed_day"] < s.last_day:
            continue
        if w["charter_tier"] < 2:
            continue
        chosen.append(wid)
    return sorted(chosen)


def charge_cap_for(s, workshop):
    tier = workshop["charter_tier"]
    cap = s.tier_charge_cap.get(tier, 0)
    if s.charter.get("extension_patch"):
        allowance = s.charter.get("tier_extension_allowance") or {}
        extra = allowance.get(str(tier), allowance.get(tier, 0)) or 0
        cap += as_int(extra)
    if workshop["provisional"]:
        cap = cap // 2
    return cap


def prepare(s):
    """Precompute every per-entry fact that does not turn on the scarcity indices."""
    ident = Identity(s.identity_events)
    scope = in_scope_workshops(s)
    scope_set = set(scope)
    raw_by_id = dict((e["entry_id"], e) for e in s.ledger)

    entries = []
    for entry in s.ledger:
        info = dict(entry)
        wid = entry["workshop_id"]
        workshop = s.workshops.get(wid)
        info["in_scope"] = wid in scope_set
        info["guild_id"] = workshop["guild_id"] if workshop else None
        info["canonical"] = ident.canonical(entry["smith_ref"], entry["day"])
        info["retired_smith"] = ident.is_retired(entry["smith_ref"], entry["day"])
        info["patch"] = s.patch_of_day(entry["day"])
        art = s.artifacts.get(entry["artifact_id"])
        info["artifact"] = art
        info["family"] = art["family"] if art else None
        info["tier"] = art["tier"] if art else None

        if entry["op"] == "salvage":
            info["missing_forge"] = entry["forge_ref"] not in s.ledger_ids
            source = raw_by_id.get(entry["forge_ref"])
            governing_day = source["day"] if source is not None else None
        else:
            info["missing_forge"] = False
            governing_day = entry["day"]

        edition = None
        if art is not None and governing_day is not None:
            patch = s.patch_of_day(governing_day)
            if patch is not None:
                for cand in s.editions_by_artifact.get(entry["artifact_id"], []):
                    if cand["from_ordinal"] <= patch["ordinal"]:
                        edition = cand
                    else:
                        break
        info["edition"] = edition
        # a salvage whose forge the ledger does not hold has no governing day to
        # place in the calendar; only its artifact can leave it unresolved
        if info["missing_forge"]:
            info["unresolved"] = art is None
        else:
            info["unresolved"] = edition is None

        if edition is not None and entry["op"] == "forge":
            draw = {}
            for reagent, upc in edition["lines"]:
                if reagent in s.reagents:
                    draw[reagent] = draw.get(reagent, 0) + upc * entry["units"]
            info["draw"] = sorted(draw.items())
            info["retired_reagents"] = sorted(
                set(r for r, _ in edition["lines"]
                    if r in s.reagents and s.reagents[r]["retired_day"] is not None
                    and s.reagents[r]["retired_day"] <= entry["day"]))
        else:
            info["draw"] = []
            info["retired_reagents"] = []

        relief = False
        if entry["op"] == "forge" and info["patch"] is not None:
            reg_day = ident.registration_day(entry["smith_ref"], entry["day"])
            if reg_day is not None:
                reg_patch = s.patch_of_day(reg_day)
                if reg_patch is not None and reg_patch["patch_id"] == info["patch"]["patch_id"]:
                    relief = True
        info["apprentice_relief"] = relief
        entries.append(info)

    acquisitions = []
    for acq in s.acquisitions:
        patch = s.patch_of_day(acq["day"])
        if patch is None or acq["reagent_id"] not in s.reagents:
            continue
        acquisitions.append((acq["day"], acq["reagent_id"], acq["units"], patch["ordinal"]))

    return {
        "identity": ident,
        "scope": scope,
        "entries": entries,
        "by_id": dict((e["entry_id"], e) for e in entries),
        "acquisitions": acquisitions,
        "caps": dict((wid, charge_cap_for(s, s.workshops[wid])) for wid in scope),
    }


def entry_charge(s, conventions, info, indices):
    art = info["artifact"]
    edition = info["edition"]
    pct = {
        "F": s.family_multiplier.get(art["family"], 100),
        "G": 100 + s.grade_step * edition["max_grade"],
        "S": 100 + sum(indices.get(r, 0) for r in edition["scarce_lines"]),
    }
    conv = conventions["reduction"]
    value = art["base_charge"]
    for op in conventions["operator_order"]:
        value = reduce_fraction(value * pct[op], 100, conv)
    charge = value * info["units"]
    if info["apprentice_relief"]:
        charge = reduce_fraction(charge * 80, 100, conv)
    return charge


def settle(s, conventions, ctx, indices):
    """Settle the whole ledger at one assignment of scarcity indices."""
    conv = conventions["reduction"]
    rates = conventions["return_rates"]
    scope = ctx["scope"]
    caps = ctx["caps"]
    identity = ctx["identity"]

    balance = dict((r, s.opening[r]) for r in s.reagent_ids)
    acquired = dict((r, 0) for r in s.reagent_ids)
    returned = dict((r, 0) for r in s.reagent_ids)
    consumed = dict((r, 0) for r in s.reagent_ids)
    called_for = dict((r, 0) for r in s.reagent_ids)

    flow = dict((p["ordinal"], {"acquired": dict((r, 0) for r in s.reagent_ids),
                                "returned": dict((r, 0) for r in s.reagent_ids),
                                "consumed": dict((r, 0) for r in s.reagent_ids)})
                for p in s.patches)

    accrued = dict((wid, 0) for wid in scope)
    closed = dict((wid, False) for wid in scope)
    ws_charge = dict((wid, 0) for wid in scope)
    ws_admitted = dict((wid, 0) for wid in scope)
    ws_rejected = dict((wid, 0) for wid in scope)
    ws_flow = dict((wid, {}) for wid in scope)
    smiths = dict((wid, {}) for wid in scope)

    findings = []
    live = []          # settled forges no salvage has been credited against
    credited = set()
    charge_of = {}
    credited_salvages = 0

    def smith_row(wid, canon):
        row = smiths[wid].get(canon)
        if row is None:
            row = {"canonical_smith": canon, "admitted_forges": 0,
                   "credited_salvages": 0, "charge_ember": 0}
            smiths[wid][canon] = row
        return row

    def flow_row(wid, reagent):
        row = ws_flow[wid].get(reagent)
        if row is None:
            row = {"reagent_id": reagent, "consumed_units": 0, "returned_units": 0}
            ws_flow[wid][reagent] = row
        return row

    acquisitions = ctx["acquisitions"]
    n_acq = len(acquisitions)
    acq_index = 0

    def credit_acquisitions(upto_day):
        nonlocal acq_index
        while acq_index < n_acq and acquisitions[acq_index][0] <= upto_day:
            _, rid, units, ordinal = acquisitions[acq_index]
            balance[rid] += units
            acquired[rid] += units
            flow[ordinal]["acquired"][rid] += units
            acq_index += 1

    entries = ctx["entries"]
    for info in entries:
        day = info["day"]
        credit_acquisitions(day)
        eid = info["entry_id"]
        wid = info["workshop_id"]

        refused = False
        if not info["in_scope"]:
            findings.append((eid, CODE_OUT_OF_SCOPE, wid))
            refused = True
        if info["retired_smith"]:
            findings.append((eid, CODE_RETIRED_SMITH, info["canonical"]))
            refused = True
        if info["missing_forge"]:
            findings.append((eid, CODE_MISSING_FORGE, info["forge_ref"]))
            refused = True
        if info["unresolved"]:
            findings.append((eid, CODE_UNRESOLVED, info["artifact_id"]))
            refused = True
        if refused:
            if info["in_scope"]:
                ws_rejected[wid] += 1
                smith_row(wid, info["canonical"])
            continue

        smith_row(wid, info["canonical"])
        ordinal = info["patch"]["ordinal"]

        if info["op"] == "forge":
            charge = entry_charge(s, conventions, info, indices)
            bad = False
            if closed[wid] or accrued[wid] + charge > caps[wid]:
                findings.append((eid, CODE_CAP, wid))
                closed[wid] = True
                bad = True
            short = []
            for rid, need in info["draw"]:
                called_for[rid] += need
                if balance.get(rid, 0) - need < 0:
                    short.append(rid)
            if short:
                findings.append((eid, CODE_STOCK_FLOOR, min(short)))
                bad = True
            if info["retired_reagents"]:
                findings.append((eid, CODE_RETIRED_REAGENT, info["retired_reagents"][0]))
                bad = True
            if bad:
                ws_rejected[wid] += 1
                continue
            for rid, need in info["draw"]:
                balance[rid] -= need
                consumed[rid] += need
                flow[ordinal]["consumed"][rid] += need
                flow_row(wid, rid)["consumed_units"] += need
            accrued[wid] += charge
            ws_charge[wid] += charge
            ws_admitted[wid] += 1
            charge_of[eid] = charge
            row = smith_row(wid, info["canonical"])
            row["admitted_forges"] += 1
            row["charge_ember"] += charge
            live.append(info)
            continue

        ref = info["forge_ref"]
        if ref in credited:
            findings.append((eid, CODE_ALREADY_CREDITED, ref))
            ws_rejected[wid] += 1
            continue
        canon = info["canonical"]
        family = info["family"]
        window = [cand["entry_id"] for cand in live
                  if cand["family"] == family and cand["day"] < day
                  and identity.canonical(cand["smith_ref"], day) == canon][-3:]
        if ref not in window:
            findings.append((eid, CODE_UNCREDITED, ref))
            ws_rejected[wid] += 1
            continue

        source = ctx["by_id"][ref]
        rate = rates[info["tier"] - 1]
        for rid, upc in info["edition"]["lines"]:
            if rid not in balance:
                continue
            give = reduce_fraction(upc * source["units"] * rate, 100, conv)
            balance[rid] += give
            returned[rid] += give
            flow[ordinal]["returned"][rid] += give
            flow_row(wid, rid)["returned_units"] += give
        credited.add(ref)
        live = [cand for cand in live if cand["entry_id"] != ref]
        src_wid = source["workshop_id"]
        if src_wid in accrued:
            accrued[src_wid] -= charge_of.get(ref, 0)
        ws_admitted[wid] += 1
        credited_salvages += 1
        smith_row(wid, canon)["credited_salvages"] += 1

    credit_acquisitions(s.last_day if not acquisitions else acquisitions[-1][0])

    new_indices = {}
    for rid in s.scarce_ids:
        refv = scarcity_reference_value(conventions["scarcity_reference"],
                                        s.opening[rid], acquired[rid], called_for[rid])
        new_indices[rid] = scarcity_index(consumed[rid], refv, s.scarcity_ceiling, conv)

    return {
        "indices": new_indices,
        "balance": balance,
        "acquired": acquired,
        "returned": returned,
        "consumed": consumed,
        "called_for": called_for,
        "patch_flow": flow,
        "charge_by_workshop": ws_charge,
        "admitted_by_workshop": ws_admitted,
        "rejected_by_workshop": ws_rejected,
        "closed": closed,
        "workshop_flow": ws_flow,
        "smiths": smiths,
        "findings": findings,
        "credited_salvages": credited_salvages,
    }


def settled_season(s, conventions, ctx):
    """Find the assignment of scarcity indices that agrees with its own season."""
    indices = dict((r, 0) for r in s.scarce_ids)
    visited = []
    seen = {}
    cycle_start = None
    for _ in range(500):
        result = settle(s, conventions, ctx, indices)
        if result["indices"] == indices:
            return result
        key = tuple(sorted(indices.items()))
        if key in seen:
            cycle_start = seen[key]
            break
        seen[key] = len(visited)
        visited.append(indices)
        indices = result["indices"]

    # the iteration cycled: sweep the box the cycle spans for the fixed point
    cycle = visited[cycle_start:] if cycle_start is not None else visited
    lows = dict((r, min(v[r] for v in cycle)) for r in s.scarce_ids)
    highs = dict((r, max(v[r] for v in cycle)) for r in s.scarce_ids)
    span = 1
    for rid in s.scarce_ids:
        span *= highs[rid] - lows[rid] + 1
    if span <= 20000:
        candidates = [{}]
        for rid in s.scarce_ids:
            grown = []
            for cand in candidates:
                for value in range(lows[rid], highs[rid] + 1):
                    nxt = dict(cand)
                    nxt[rid] = value
                    grown.append(nxt)
            candidates = grown
        for cand in candidates:
            result = settle(s, conventions, ctx, cand)
            if result["indices"] == cand:
                return result
    sys.stderr.write("error: no settled assignment of scarcity indices agrees "
                     "with the season it produces\n")
    sys.exit(4)


# --------------------------------------------------------------------------
# requisitions
# --------------------------------------------------------------------------

class MaxFlow(object):
    def __init__(self, n):
        self.n = n
        self.graph = [[] for _ in range(n)]

    def add(self, u, v, cap):
        if cap <= 0:
            return
        self.graph[u].append([v, cap, len(self.graph[v])])
        self.graph[v].append([u, 0, len(self.graph[u]) - 1])

    def max_flow(self, src, dst):
        flow = 0
        graph = self.graph
        while True:
            level = [-1] * self.n
            level[src] = 0
            queue = [src]
            while queue:
                nxt = []
                for u in queue:
                    for edge in graph[u]:
                        if edge[1] > 0 and level[edge[0]] < 0:
                            level[edge[0]] = level[u] + 1
                            nxt.append(edge[0])
                queue = nxt
            if level[dst] < 0:
                return flow
            iters = [0] * self.n
            stack_limit = 1 << 60

            def dfs(u, limit):
                if u == dst:
                    return limit
                while iters[u] < len(graph[u]):
                    edge = graph[u][iters[u]]
                    v, cap = edge[0], edge[1]
                    if cap > 0 and level[v] == level[u] + 1:
                        got = dfs(v, limit if limit < cap else cap)
                        if got > 0:
                            edge[1] -= got
                            graph[v][edge[2]][1] += got
                            return got
                    iters[u] += 1
                return 0

            while True:
                pushed = dfs(src, stack_limit)
                if pushed == 0:
                    break
                flow += pushed


class Allocator(object):
    """Grants reagent units against the season's requisitions under Q1 - Q8."""

    def __init__(self, s, scope, closing):
        self.pool = s.pool_units
        self.guild_cap = dict(s.guild_cap)
        self.reagent_cap = dict((rid, max(0, closing.get(rid, 0))) for rid in s.scarce_ids)
        self.all_reqs = s.requisitions
        items = []
        for req in s.requisitions:
            if req["workshop_id"] not in scope:
                continue
            workshop = s.workshops[req["workshop_id"]]
            hi = min(req["units_requested"],
                     s.tier_unit_cap.get(workshop["charter_tier"], 0))
            lo = max(req["min_units"], 1)
            if hi < lo:
                continue
            items.append({
                "req_id": req["req_id"],
                "priority": req["priority"],
                "lo": lo,
                "hi": hi,
                "guild": workshop["guild_id"],
                "charter": workshop["charter_id"],
                "reagent": (req["reagent_id"]
                            if req["reagent_id"] in self.reagent_cap else None),
            })
        items.sort(key=lambda it: it["req_id"])
        self.items = items
        self.index = dict((it["req_id"], k) for k, it in enumerate(items))
        charters = {}
        for it in items:
            charters.setdefault(it["charter"], []).append(it)
        self.charters = []
        for name in sorted(charters):
            group = sorted(charters[name], key=lambda it: (-it["hi"], it["req_id"]))
            self.charters.append([it["req_id"] for it in group])
        self.guilds = sorted(set(it["guild"] for it in items))
        self.reagents = sorted(set(it["reagent"] for it in items
                                   if it["reagent"] is not None))
        self.order = [it["req_id"] for it in sorted(
            items, key=lambda it: (it["priority"], it["req_id"]))]
        self.width = min(self.pool, sum(it["hi"] for it in items))
        self._cache = {}
        self._masks = {}

    def reachable_masks(self, groups):
        """Bit `t` of mask[pos] is set when groups pos.. can grant t units in all.

        The caps are left out, so the highest set bit at or below the units still
        to grant is an upper bound that respects the minimums and the ceilings.
        """
        key = tuple(tuple(group) for group in groups)
        if key in self._masks:
            return self._masks[key]
        limit = (1 << (self.width + 1)) - 1
        masks = [1] * (len(groups) + 1)
        for pos in range(len(groups) - 1, -1, -1):
            nxt = masks[pos + 1]
            acc = nxt
            for rid in groups[pos]:
                it = self.items[self.index[rid]]
                for value in range(it["lo"], it["hi"] + 1):
                    acc |= nxt << value
            masks[pos] = acc & limit
        self._masks[key] = masks
        return masks

    def reachable_below(self, mask, room):
        if room > self.width:
            room = self.width
        return (mask & ((1 << (room + 1)) - 1)).bit_length() - 1

    def _capacity(self, selected, relaxed_groups):
        """Greatest total for a funded set.

        `selected` maps a requisition to the units it is held at and the units
        it may grow to. Each group in `relaxed_groups` is relaxed to a single
        pool of units no larger than its widest requisition, which keeps the
        result an upper bound on any plan that funds at most one requisition
        per charter.
        """
        base = 0
        guild_used = dict((g, 0) for g in self.guilds)
        reagent_used = dict((r, 0) for r in self.reagents)
        for rid, (value, _) in selected.items():
            it = self.items[self.index[rid]]
            base += value
            guild_used[it["guild"]] += value
            if it["reagent"] is not None:
                reagent_used[it["reagent"]] += value
        if base > self.pool:
            return None
        for g in self.guilds:
            if guild_used[g] > self.guild_cap.get(g, 0):
                return None
        for r in self.reagents:
            if reagent_used[r] > self.reagent_cap[r]:
                return None

        n_guild = len(self.guilds)
        n_reagent = len(self.reagents)
        n_item = len(self.items)
        src = 0
        gin = 1
        gout = gin + n_guild
        rin = gout + n_guild
        opt = rin + n_reagent
        grp = opt + n_item
        snk = grp + len(relaxed_groups)
        net = MaxFlow(snk + 1)
        gin_idx = dict((g, gin + k) for k, g in enumerate(self.guilds))
        gout_idx = dict((g, gout + k) for k, g in enumerate(self.guilds))
        rin_idx = dict((r, rin + k) for k, r in enumerate(self.reagents))

        room = self.pool - base
        infinite = room + 1
        for g in self.guilds:
            net.add(gin_idx[g], gout_idx[g], self.guild_cap.get(g, 0) - guild_used[g])
        for r in self.reagents:
            net.add(rin_idx[r], snk, self.reagent_cap[r] - reagent_used[r])
        wired = set()

        def wire(it):
            """Route one requisition's own node through its guild and reagent."""
            node = opt + self.index[it["req_id"]]
            if it["req_id"] in wired:
                return node
            wired.add(it["req_id"])
            net.add(node, gin_idx[it["guild"]], infinite)
            key = (it["guild"], it["reagent"])
            if key not in wired:
                wired.add(key)
                if it["reagent"] is None:
                    net.add(gout_idx[it["guild"]], snk, infinite)
                else:
                    net.add(gout_idx[it["guild"]], rin_idx[it["reagent"]], infinite)
            return node

        for rid, (value, cap) in selected.items():
            it = self.items[self.index[rid]]
            headroom = cap - value
            if headroom > 0:
                net.add(src, wire(it), headroom)
        for k, group in enumerate(relaxed_groups):
            group_node = grp + k
            widest = 0
            for rid in group:
                it = self.items[self.index[rid]]
                if it["hi"] > widest:
                    widest = it["hi"]
                net.add(group_node, wire(it), it["hi"])
            net.add(src, group_node, min(widest, room))
        extra = net.max_flow(src, snk)
        return base + (extra if extra < room else room)

    def best_total(self, fixed):
        """Greatest grantable total given exact grants for some requisitions."""
        key = tuple(sorted(fixed.items()))
        if key in self._cache:
            return self._cache[key]
        forced = dict((rid, (v, v)) for rid, v in fixed.items() if v > 0)
        groups = []
        for group in self.charters:
            if any(fixed.get(rid, 0) > 0 for rid in group):
                continue
            options = [rid for rid in group if rid not in fixed]
            if options:
                groups.append(options)
        best = [-1]
        ceiling = [None]
        masks = self.reachable_masks(groups)

        class Done(Exception):
            pass

        def knapsack_bound(pos, base, base_max):
            reach = self.reachable_below(masks[pos], self.pool - base)
            bound = base_max + reach
            return bound if bound < self.pool else self.pool

        def search(pos, selected, base, base_max):
            value = self._capacity(selected, [])
            if value is None:
                return
            if value > best[0]:
                best[0] = value
                if ceiling[0] is not None and best[0] >= ceiling[0]:
                    raise Done
            if pos == len(groups):
                return
            bound = knapsack_bound(pos, base, base_max)
            flow_bound = self._capacity(selected, groups[pos:])
            if flow_bound is None:
                return
            if flow_bound < bound:
                bound = flow_bound
            if bound <= best[0]:
                return
            for rid in groups[pos]:
                it = self.items[self.index[rid]]
                selected[rid] = (it["lo"], it["hi"])
                if self._capacity(selected, []) is not None:
                    search(pos + 1, selected, base + it["lo"], base_max + it["hi"])
                del selected[rid]
            search(pos + 1, selected, base, base_max)

        if self._capacity(forced, []) is not None:
            base = sum(v for v, _ in forced.values())
            ceiling[0] = min(self._capacity(forced, groups),
                             knapsack_bound(0, base, base))
            try:
                search(0, dict(forced), base, base)
            except Done:
                pass
        total = best[0] if best[0] >= 0 else None
        self._cache[key] = total
        return total

    def solve(self):
        grants = dict((req["req_id"], 0) for req in self.all_reqs)
        target = self.best_total({})
        if target is None:
            return grants, 0
        fixed = {}
        for rid in self.order:
            if rid in fixed:
                continue
            it = self.items[self.index[rid]]
            best = 0
            for value in range(it["hi"], it["lo"] - 1, -1):
                trial = dict(fixed)
                trial[rid] = value
                if self.best_total(trial) == target:
                    best = value
                    break
            fixed[rid] = best
            if best > 0:
                for group in self.charters:
                    if rid in group:
                        for other in group:
                            if other != rid:
                                fixed[other] = 0
        for rid, value in fixed.items():
            grants[rid] = value
        return grants, sum(grants.values())


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------

def build_records(s, ctx, result, grants, allocated_total):
    scope = ctx["scope"]
    guilds = sorted(set(s.workshops[w]["guild_id"] for w in scope))
    indices = result["indices"]

    findings = sorted(set(result["findings"]), key=lambda f: (f[0], f[1]))
    counts = {}
    for _, code, _ in findings:
        counts[code] = counts.get(code, 0) + 1

    ws_alloc = dict((w, 0) for w in scope)
    for req in s.requisitions:
        if req["workshop_id"] in ws_alloc:
            ws_alloc[req["workshop_id"]] += grants.get(req["req_id"], 0)

    opening = s.opening
    acquired = result["acquired"]
    returned = result["returned"]
    consumed = result["consumed"]
    closing = result["balance"]

    conservation_residual = sum(
        abs(opening[rid] + acquired[rid] + returned[rid] - consumed[rid] - closing[rid])
        for rid in s.reagent_ids)

    admitted_total = sum(result["admitted_by_workshop"][w] for w in scope)
    charge_total = sum(result["charge_by_workshop"][w] for w in scope)

    summary = {
        "season": {
            "first_day": s.first_day,
            "last_day": s.last_day,
            "patch_count": len(s.patches),
        },
        "workshops_in_scope": list(scope),
        "guilds_in_scope": guilds,
        "entries_total": len(s.ledger),
        "entries_admitted": admitted_total,
        "entries_rejected": len(s.ledger) - admitted_total,
        "credited_salvages": result["credited_salvages"],
        "uncredited_salvages": counts.get(CODE_UNCREDITED, 0),
        "scarcity_index": dict((rid, indices[rid]) for rid in s.scarce_ids),
        "season_charge_ember": charge_total,
        "allocated_units_total": allocated_total,
        "conservation_residual": conservation_residual,
    }

    vault_audit = {"reagents": [{
        "reagent_id": rid,
        "grade": s.reagents[rid]["grade"],
        "scarce": bool(s.reagents[rid]["scarce"]),
        "opening_units": opening[rid],
        "acquired_units": acquired[rid],
        "returned_units": returned[rid],
        "consumed_units": consumed[rid],
        "closing_units": closing[rid],
        "scarcity_index": indices[rid] if s.reagents[rid]["scarce"] else 0,
    } for rid in s.reagent_ids]}

    patches = []
    running = dict((rid, opening[rid]) for rid in s.reagent_ids)
    season_residual = 0
    for patch in s.patches:
        flow = result["patch_flow"][patch["ordinal"]]
        rows = []
        patch_residual = 0
        for rid in s.reagent_ids:
            open_u = running[rid]
            acq = flow["acquired"][rid]
            ret = flow["returned"][rid]
            con = flow["consumed"][rid]
            close_u = open_u + acq + ret - con
            residual = open_u + acq + ret - con - close_u
            patch_residual += abs(residual)
            rows.append({
                "reagent_id": rid,
                "opening_units": open_u,
                "acquired_units": acq,
                "returned_units": ret,
                "consumed_units": con,
                "closing_units": close_u,
                "residual": residual,
            })
            running[rid] = close_u
        season_residual += patch_residual
        patches.append({
            "patch_id": patch["patch_id"],
            "ordinal": patch["ordinal"],
            "reagents": rows,
            "residual": patch_residual,
        })

    reconciliation = {
        "patches": patches,
        "season_residual": season_residual,
        "charge_by_workshop": dict((w, result["charge_by_workshop"][w]) for w in scope),
        "charge_by_guild": dict(
            (g, sum(result["charge_by_workshop"][w] for w in scope
                    if s.workshops[w]["guild_id"] == g)) for g in guilds),
        "charge_total": charge_total,
    }

    data_quality = {
        "findings": [{"entry_id": eid, "code": code, "detail": detail}
                     for eid, code, detail in findings],
        "counts": dict((code, counts[code]) for code in sorted(counts)),
    }

    allocation = {
        "pool_units": s.pool_units,
        "assignments": [{
            "req_id": req["req_id"],
            "workshop_id": req["workshop_id"],
            "reagent_id": req["reagent_id"],
            "allocated_units": grants.get(req["req_id"], 0),
            "served": grants.get(req["req_id"], 0) > 0,
        } for req in s.requisitions],
        "allocated_total": allocated_total,
    }

    workshop_records = {}
    for wid in scope:
        workshop = s.workshops[wid]
        rows = result["workshop_flow"][wid]
        workshop_records[wid] = {
            "workshop_id": wid,
            "guild_id": workshop["guild_id"],
            "charter_id": workshop["charter_id"],
            "charter_tier": workshop["charter_tier"],
            "entries_admitted": result["admitted_by_workshop"][wid],
            "entries_rejected": result["rejected_by_workshop"][wid],
            "charge_ember": result["charge_by_workshop"][wid],
            "cap_ember": ctx["caps"][wid],
            "cap_reached": bool(result["closed"][wid]),
            "allocated_units": ws_alloc[wid],
            "smiths": [{
                "canonical_smith": canon,
                "admitted_forges": result["smiths"][wid][canon]["admitted_forges"],
                "credited_salvages": result["smiths"][wid][canon]["credited_salvages"],
                "charge_ember": result["smiths"][wid][canon]["charge_ember"],
            } for canon in sorted(result["smiths"][wid])],
            "reagent_flow": [{
                "reagent_id": rid,
                "consumed_units": rows[rid]["consumed_units"],
                "returned_units": rows[rid]["returned_units"],
                "net_units": rows[rid]["consumed_units"] - rows[rid]["returned_units"],
            } for rid in sorted(rows)],
        }

    guild_records = {}
    for guild in guilds:
        members = [w for w in scope if s.workshops[w]["guild_id"] == guild]
        merged = {}
        for wid in members:
            for row in workshop_records[wid]["reagent_flow"]:
                tgt = merged.setdefault(row["reagent_id"],
                                        {"consumed_units": 0, "returned_units": 0})
                tgt["consumed_units"] += row["consumed_units"]
                tgt["returned_units"] += row["returned_units"]
        guild_records[guild] = {
            "guild_id": guild,
            "workshops": members,
            "entries_admitted": sum(workshop_records[w]["entries_admitted"]
                                    for w in members),
            "charge_ember": sum(workshop_records[w]["charge_ember"] for w in members),
            "allocated_units": sum(workshop_records[w]["allocated_units"]
                                   for w in members),
            "reagent_flow": [{
                "reagent_id": rid,
                "consumed_units": merged[rid]["consumed_units"],
                "returned_units": merged[rid]["returned_units"],
                "net_units": merged[rid]["consumed_units"] - merged[rid]["returned_units"],
            } for rid in sorted(merged)],
        }

    return {
        "summary.json": summary,
        "vault_audit.json": vault_audit,
        "reconciliation.json": reconciliation,
        "data_quality.json": data_quality,
        "allocation.json": allocation,
        "workshops": workshop_records,
        "guilds": guild_records,
    }


def main(argv):
    data_dir = argv[1] if len(argv) > 1 else "/app/data"
    out_dir = argv[2] if len(argv) > 2 else "/app/out"
    s = load_season(data_dir)
    conventions = derive_conventions(s.rulings)
    ctx = prepare(s)
    result = settled_season(s, conventions, ctx)
    allocator = Allocator(s, set(ctx["scope"]), result["balance"])
    grants, allocated_total = allocator.solve()
    records = build_records(s, ctx, result, grants, allocated_total)

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    for name in ("summary.json", "vault_audit.json", "reconciliation.json",
                 "data_quality.json", "allocation.json"):
        write_record(out_dir, name, records[name])
    for wid in sorted(records["workshops"]):
        write_record(out_dir, "workshop_%s.json" % wid, records["workshops"][wid])
    for guild in sorted(records["guilds"]):
        write_record(out_dir, "guild_%s.json" % guild, records["guilds"][guild])
    return 0


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    sys.exit(main(sys.argv))
