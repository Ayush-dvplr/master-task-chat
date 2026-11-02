#!/usr/bin/env python3
"""Settle an Emberforge crafting season.

Usage: settle_vault.py [data_dir] [out_dir]
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

# The council's register of the conventions it may draw from.
RETURN_SCHEDULES = {
    "RS-A": {1: 40, 2: 50, 3: 60},
    "RS-B": {1: 45, 2: 55, 3: 65},
    "RS-C": {1: 50, 2: 60, 3: 70},
    "RS-D": {1: 35, 2: 50, 3: 65},
    "RS-E": {1: 55, 2: 55, 3: 55},
    "RS-F": {1: 30, 2: 45, 3: 60},
    "RS-G": {1: 60, 2: 50, 3: 40},
}
REDUCTIONS = ["ceil", "floor", "half-down", "half-even", "half-up"]
ORDERS = ["FGS", "FSG", "GFS", "GSF", "SFG", "SGF"]
REFERENCES = ["acquired", "consumed", "opening", "opening-plus-acquired"]

CODE_OUT_OF_SCOPE = "OUT_OF_SCOPE_WORKSHOP"
CODE_RETIRED_SMITH = "RETIRED_SMITH"
CODE_MISSING_FORGE = "MISSING_FORGE_REF"
CODE_UNRESOLVED = "UNRESOLVED_EDITION"
CODE_CAP = "CAP_REACHED"
CODE_FLOOR = "STOCK_FLOOR"
CODE_RETIRED_REAGENT = "RETIRED_REAGENT"
CODE_ALREADY = "SALVAGE_ALREADY_CREDITED"
CODE_UNCREDITED = "UNCREDITED_SALVAGE"


def reduce_q(num, den, mode):
    """Reduce num/den (den > 0) to a whole number under the season convention."""
    q, r = divmod(num, den)
    if r == 0:
        return q
    if mode == "floor":
        return q
    if mode == "ceil":
        return q + 1
    twice = 2 * r
    if twice < den:
        return q
    if twice > den:
        return q + 1
    if mode == "half-up":
        return q + 1
    if mode == "half-down":
        return q
    return q if q % 2 == 0 else q + 1


def pct(value, percent, mode):
    return reduce_q(value * percent, 100, mode)


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def as_int(text, default=None):
    if text is None:
        return default
    text = text.strip()
    if text == "":
        return default
    return int(text)


def truthy(text):
    if text is None:
        return False
    return text.strip().lower() in ("1", "true", "yes", "y", "t")


# --------------------------------------------------------------------------
# the corpus
# --------------------------------------------------------------------------


class Corpus(object):
    def __init__(self, data_dir):
        self.dir = data_dir
        self.patches = sorted(
            (
                {
                    "patch_id": r["patch_id"],
                    "opens_day": as_int(r["opens_day"]),
                    "closes_day": as_int(r["closes_day"]),
                    "ordinal": as_int(r["ordinal"]),
                }
                for r in read_csv(os.path.join(data_dir, "patch_calendar.csv"))
            ),
            key=lambda p: p["ordinal"],
        )
        self.patch_by_id = {p["patch_id"]: p for p in self.patches}
        self.ordinal_of = {p["patch_id"]: p["ordinal"] for p in self.patches}
        self.first_day = min(p["opens_day"] for p in self.patches)
        self.last_day = max(p["closes_day"] for p in self.patches)

        self.reagents = {}
        for r in read_csv(os.path.join(data_dir, "reagent_registry.csv")):
            self.reagents[r["reagent_id"]] = {
                "reagent_id": r["reagent_id"],
                "grade": as_int(r.get("grade"), 0),
                "family": (r.get("family") or "").strip(),
                "scarce": truthy(r.get("scarce")),
                "retired_patch": (r.get("retired_patch") or "").strip() or None,
            }
        self.reagent_ids = sorted(self.reagents)
        self.scarce_ids = sorted(k for k, v in self.reagents.items() if v["scarce"])

        self.artifacts = {}
        for r in read_csv(os.path.join(data_dir, "artifact_catalogue.csv")):
            self.artifacts[r["artifact_id"]] = {
                "artifact_id": r["artifact_id"],
                "family": r["family"],
                "tier": as_int(r["tier"]),
                "base_charge": as_int(r["base_charge"]),
            }

        editions = {}
        for r in read_csv(os.path.join(data_dir, "recipe_editions.csv")):
            if truthy(r.get("recalled")):
                continue
            key = (r["artifact_id"], as_int(r["edition"]))
            slot = editions.setdefault(
                key,
                {
                    "artifact_id": r["artifact_id"],
                    "edition": as_int(r["edition"]),
                    "from_ordinal": self.ordinal_of.get(r["from_patch"]),
                    "lines": {},
                },
            )
            slot["lines"][r["reagent_id"]] = slot["lines"].get(
                r["reagent_id"], 0
            ) + as_int(r["units_per_craft"], 0)
        self.editions_by_artifact = {}
        for key in sorted(editions):
            ed = editions[key]
            if ed["from_ordinal"] is None:
                continue
            ed["reagent_ids"] = sorted(ed["lines"])
            self.editions_by_artifact.setdefault(ed["artifact_id"], []).append(ed)
        for lst in self.editions_by_artifact.values():
            lst.sort(key=lambda e: (e["from_ordinal"], e["edition"]))

        self.workshops = {}
        for r in read_csv(os.path.join(data_dir, "workshop_registry.csv")):
            self.workshops[r["workshop_id"]] = {
                "workshop_id": r["workshop_id"],
                "charter_id": r["charter_id"],
                "guild_id": r["guild_id"],
                "opened_day": as_int(r["opened_day"]),
                "closed_day": as_int(r.get("closed_day")),
                "charter_tier": as_int(r["charter_tier"]),
                "provisional": truthy(r.get("provisional_charter"))
                or truthy(r.get("provisional")),
            }

        self.events = sorted(
            (
                {
                    "event_id": r["event_id"],
                    "day": as_int(r["day"]),
                    "kind": r["kind"].strip(),
                    "from_ref": (r.get("from_ref") or "").strip(),
                    "to_ref": (r.get("to_ref") or "").strip(),
                }
                for r in read_csv(os.path.join(data_dir, "smith_identity_events.csv"))
            ),
            key=lambda e: (e["day"], e["event_id"]),
        )

        self.ledger = []
        for r in read_csv(os.path.join(data_dir, "crafting_ledger.csv")):
            self.ledger.append(
                {
                    "entry_id": r["entry_id"],
                    "day": as_int(r["day"]),
                    "workshop_id": r["workshop_id"],
                    "smith_ref": r["smith_ref"],
                    "op": r["op"].strip(),
                    "artifact_id": r["artifact_id"],
                    "units": as_int(r["units"], 0),
                    "forge_ref": (r.get("forge_ref") or "").strip() or None,
                }
            )
        self.ledger.sort(key=lambda e: (e["day"], e["entry_id"]))
        self.ledger_by_id = {e["entry_id"]: e for e in self.ledger}

        self.acquisitions = sorted(
            (
                {
                    "acq_id": r["acq_id"],
                    "day": as_int(r["day"]),
                    "reagent_id": r["reagent_id"],
                    "units": as_int(r["units"], 0),
                }
                for r in read_csv(os.path.join(data_dir, "reagent_acquisitions.csv"))
            ),
            key=lambda a: (a["day"], a["acq_id"]),
        )

        self.opening = {rid: 0 for rid in self.reagent_ids}
        for r in read_csv(os.path.join(data_dir, "vault_opening.csv")):
            self.opening[r["reagent_id"]] = as_int(r["opening_units"], 0)

        self.requisitions = read_json(os.path.join(data_dir, "requisitions.json"))[
            "requisitions"
        ]
        self.charter = read_json(os.path.join(data_dir, "season_charter.json"))
        self.rulings = read_json(os.path.join(data_dir, "council_rulings.json"))

        self.patch_of_day = {}
        for p in self.patches:
            for day in range(p["opens_day"], p["closes_day"] + 1):
                self.patch_of_day[day] = p["patch_id"]

        self.reagent_retired_from = {}
        for rid, meta in self.reagents.items():
            rp = meta["retired_patch"]
            if rp and rp in self.patch_by_id:
                self.reagent_retired_from[rid] = self.patch_by_id[rp]["opens_day"]

    def ordinal_of_day(self, day):
        pid = self.patch_of_day.get(day)
        return self.ordinal_of[pid] if pid is not None else None

    def edition_for(self, artifact_id, day):
        if artifact_id not in self.artifacts:
            return None
        if day is None:
            return None
        ordinal = self.ordinal_of_day(day)
        if ordinal is None:
            return None
        chosen = None
        for ed in self.editions_by_artifact.get(artifact_id, []):
            if ed["from_ordinal"] <= ordinal:
                chosen = ed
            else:
                break
        return chosen


# --------------------------------------------------------------------------
# smith identity
# --------------------------------------------------------------------------


class Identity(object):
    def __init__(self, corpus):
        self.corpus = corpus
        self.links = [e for e in corpus.events if e["kind"] in ("rename", "merge")]
        self.retires = [e for e in corpus.events if e["kind"] == "retire"]
        self.registers = [e for e in corpus.events if e["kind"] == "register"]
        self._canon = {}
        self._retired = {}

    def canonical(self, handle, day):
        key = (handle, day)
        hit = self._canon.get(key)
        if hit is not None:
            return hit
        current = handle
        seen = set([current])
        changed = True
        while changed:
            changed = False
            for ev in self.links:
                if ev["day"] <= day and ev["from_ref"] == current:
                    nxt = ev["to_ref"]
                    if nxt in seen:
                        continue
                    current = nxt
                    seen.add(current)
                    changed = True
        self._canon[key] = current
        return current

    def is_retired(self, canon, day):
        key = (canon, day)
        hit = self._retired.get(key)
        if hit is not None:
            return hit
        retired_on = None
        for ev in self.retires:
            if ev["day"] <= day and self.canonical(ev["from_ref"], day) == canon:
                if retired_on is None or ev["day"] < retired_on:
                    retired_on = ev["day"]
        result = retired_on is not None
        if result:
            # I6: a register event after the retirement reinstates the identity.
            for ev in self.registers:
                ref = ev["from_ref"] or ev["to_ref"]
                if (
                    retired_on < ev["day"] <= day
                    and self.canonical(ref, day) == canon
                ):
                    result = False
                    break
        self._retired[key] = result
        return result

    def registration_patch(self, canon, day):
        for ev in self.registers:
            ref = ev["from_ref"] or ev["to_ref"]
            if ev["day"] <= day and self.canonical(ref, day) == canon:
                return self.corpus.patch_of_day.get(ev["day"])
        return None


# --------------------------------------------------------------------------
# the season's draw from the convention register
# --------------------------------------------------------------------------


def solve_conventions(rulings):
    sched_ok = set()
    for name, rates in RETURN_SCHEDULES.items():
        for mode in REDUCTIONS:
            good = True
            for r in rulings.get("return_rulings", []):
                rate = rates.get(int(r["tier"]))
                if rate is None or pct(
                    int(r["committed_units"]), rate, mode
                ) != int(r["returned_units"]):
                    good = False
                    break
            if good:
                sched_ok.add((name, mode))

    order_ok = set()
    for order in ORDERS:
        for mode in REDUCTIONS:
            good = True
            for r in rulings.get("charge_rulings", []):
                value = int(r["base_value"])
                percents = {
                    "F": int(r["family_percent"]),
                    "G": int(r["grade_percent"]),
                    "S": int(r["scarcity_percent"]),
                }
                for ch in order:
                    value = pct(value, percents[ch], mode)
                if value != int(r["charge_ember"]):
                    good = False
                    break
            if good:
                order_ok.add((order, mode))

    ref_ok = set()
    for ref in REFERENCES:
        for mode in REDUCTIONS:
            good = True
            for r in rulings.get("scarcity_rulings", []):
                opening = int(r["opening_units"])
                acquired = int(r["acquired_units"])
                base = {
                    "opening": opening,
                    "opening-plus-acquired": opening + acquired,
                    "consumed": int(r["called_for_units"]),
                    "acquired": acquired,
                }[ref]
                ceiling = int(r["scarcity_ceiling"])
                consumed = int(r["consumed_units"])
                if base <= 0:
                    index = 0
                else:
                    index = min(ceiling, reduce_q(consumed * 100, base, mode))
                if index != int(r["scarcity_index"]):
                    good = False
                    break
            if good:
                ref_ok.add((ref, mode))

    combos = []
    for mode in REDUCTIONS:
        for s in sorted(n for (n, m) in sched_ok if m == mode):
            for o in sorted(x for (x, m) in order_ok if m == mode):
                for f in sorted(x for (x, m) in ref_ok if m == mode):
                    combos.append((mode, s, o, f))
    if not combos:
        raise SystemExit(
            "no draw of the convention register agrees with the council's rulings"
        )
    combos.sort()
    mode, sched, order, ref = combos[0]
    return {
        "reduction": mode,
        "schedule": sched,
        "rates": RETURN_SCHEDULES[sched],
        "order": order,
        "reference": ref,
    }


# --------------------------------------------------------------------------
# settlement
# --------------------------------------------------------------------------


class Season(object):
    def __init__(self, corpus):
        self.c = corpus
        self.ident = Identity(corpus)
        self.conv = solve_conventions(corpus.rulings)
        self.mode = self.conv["reduction"]
        self.order = self.conv["order"]
        self.rates = self.conv["rates"]
        self.reference = self.conv["reference"]

        charter = corpus.charter
        self.pool = int(charter.get("season_pool_units", 0))
        self.guild_cap = {
            k: int(v) for k, v in (charter.get("guild_cap_units") or {}).items()
        }
        self.tier_unit_cap = {
            int(k): int(v) for k, v in (charter.get("tier_unit_cap") or {}).items()
        }
        self.tier_charge_cap = {
            int(k): int(v) for k, v in (charter.get("tier_charge_cap") or {}).items()
        }
        self.family_multiplier = {
            k: int(v) for k, v in (charter.get("family_multiplier") or {}).items()
        }
        self.grade_step = int(charter.get("grade_step", 0))
        self.scarcity_ceiling = int(charter.get("scarcity_ceiling", 0))
        self.extension_allowance = {
            int(k): int(v)
            for k, v in (charter.get("tier_extension_allowance") or {}).items()
        }
        self.extension_patch = charter.get("extension_patch") or None

        self.scope = self._scope()
        self.caps = dict((w, self._cap_for(w)) for w in self.scope)

        self.credited_acq = [
            a for a in corpus.acquisitions if a["day"] in corpus.patch_of_day
        ]
        self.acq_by_day = {}
        for a in self.credited_acq:
            self.acq_by_day.setdefault(a["day"], []).append(a)
        self.acquired_total = dict((rid, 0) for rid in corpus.reagent_ids)
        for a in self.credited_acq:
            self.acquired_total[a["reagent_id"]] = (
                self.acquired_total.get(a["reagent_id"], 0) + a["units"]
            )

        self.entries_by_day = {}
        for e in corpus.ledger:
            self.entries_by_day.setdefault(e["day"], []).append(e)
        self.days = sorted(set(self.acq_by_day) | set(self.entries_by_day))

    def _scope(self):
        out = []
        for wid, w in self.c.workshops.items():
            if w["opened_day"] is None or w["opened_day"] > self.c.first_day:
                continue
            if w["closed_day"] is not None and w["closed_day"] < self.c.last_day:
                continue
            if w["charter_tier"] is None or w["charter_tier"] < 2:
                continue
            out.append(wid)
        return sorted(out)

    def _cap_for(self, wid):
        w = self.c.workshops[wid]
        cap = self.tier_charge_cap.get(w["charter_tier"], 0)
        if self.extension_patch and self.extension_patch in self.c.patch_by_id:
            cap += self.extension_allowance.get(w["charter_tier"], 0)
        if w["provisional"]:
            cap = cap // 2
        return cap

    def forge_charge(self, entry, edition, indices, canon):
        art = self.c.artifacts[entry["artifact_id"]]
        value = art["base_charge"]
        grades = [
            self.c.reagents[rid]["grade"]
            for rid in edition["reagent_ids"]
            if rid in self.c.reagents
        ]
        top_grade = max(grades) if grades else 0
        scar = 0
        for rid in edition["reagent_ids"]:
            meta = self.c.reagents.get(rid)
            if meta is not None and meta["scarce"]:
                scar += indices.get(rid, 0)
        percents = {
            "F": self.family_multiplier.get(art["family"], 100),
            "G": 100 + self.grade_step * top_grade,
            "S": 100 + scar,
        }
        for ch in self.order:
            value = pct(value, percents[ch], self.mode)
        charge = value * entry["units"]
        if self.ident.registers:
            reg_patch = self.ident.registration_patch(canon, entry["day"])
            if reg_patch is not None and reg_patch == self.c.patch_of_day.get(
                entry["day"]
            ):
                charge = pct(charge, 80, self.mode)
        return charge

    def settle(self, indices):
        c = self.c
        ident = self.ident
        scope = set(self.scope)

        balance = dict(c.opening)
        accrued = dict((w, 0) for w in self.scope)
        closed = set()
        findings = []
        called_for = dict((rid, 0) for rid in c.reagent_ids)
        consumed = dict((rid, 0) for rid in c.reagent_ids)
        returned = dict((rid, 0) for rid in c.reagent_ids)
        patch_consumed = {}
        patch_returned = {}
        patch_acquired = {}
        ws_consumed = {}
        ws_returned = {}
        ws_charge = dict((w, 0) for w in self.scope)
        ws_admitted = dict((w, 0) for w in self.scope)
        ws_rejected = dict((w, 0) for w in self.scope)
        smith_rows = {}
        settled_forge = {}
        credited_forges = set()
        live = {}
        admitted = 0
        credited_salvages = 0

        def smith_slot(wid, canon):
            key = (wid, canon)
            slot = smith_rows.get(key)
            if slot is None:
                slot = {"admitted_forges": 0, "credited_salvages": 0, "charge": 0}
                smith_rows[key] = slot
            return slot

        for day in self.days:
            pid = c.patch_of_day.get(day)
            for a in self.acq_by_day.get(day, []):
                rid = a["reagent_id"]
                balance[rid] = balance.get(rid, 0) + a["units"]
                patch_acquired[(pid, rid)] = (
                    patch_acquired.get((pid, rid), 0) + a["units"]
                )
            for entry in self.entries_by_day.get(day, []):
                eid = entry["entry_id"]
                wid = entry["workshop_id"]
                in_scope = wid in scope
                canon = ident.canonical(entry["smith_ref"], day)
                if in_scope:
                    smith_slot(wid, canon)
                refused = False
                if not in_scope:
                    findings.append((eid, CODE_OUT_OF_SCOPE, wid))
                    refused = True
                if ident.is_retired(canon, day):
                    findings.append((eid, CODE_RETIRED_SMITH, canon))
                    refused = True
                source = None
                if entry["op"] == "salvage":
                    source = c.ledger_by_id.get(entry["forge_ref"])
                    if source is None:
                        findings.append(
                            (eid, CODE_MISSING_FORGE, entry["forge_ref"] or "")
                        )
                        refused = True
                    gov_day = source["day"] if source is not None else None
                else:
                    gov_day = entry["day"]
                epid = pid
                if epid is None and gov_day is not None:
                    # a salvage may fall outside the calendar while the forge it
                    # names does not; its flows still belong to a patch
                    epid = c.patch_of_day.get(gov_day)
                edition = c.edition_for(entry["artifact_id"], gov_day)
                if edition is None:
                    findings.append((eid, CODE_UNRESOLVED, entry["artifact_id"]))
                    refused = True
                if refused:
                    if in_scope:
                        ws_rejected[wid] += 1
                    continue

                if entry["op"] == "forge":
                    charge = self.forge_charge(entry, edition, indices, canon)
                    bad = False
                    if wid in closed:
                        findings.append((eid, CODE_CAP, wid))
                        bad = True
                    elif accrued[wid] + charge > self.caps[wid]:
                        findings.append((eid, CODE_CAP, wid))
                        closed.add(wid)
                        bad = True
                    need = {}
                    for rid, per in edition["lines"].items():
                        need[rid] = need.get(rid, 0) + per * entry["units"]
                    order = sorted(need)
                    for rid in order:
                        called_for[rid] = called_for.get(rid, 0) + need[rid]
                    retired_hit = None
                    for rid in order:
                        limit = c.reagent_retired_from.get(rid)
                        if limit is not None and day >= limit:
                            retired_hit = rid
                            break
                    if retired_hit is not None:
                        findings.append((eid, CODE_RETIRED_REAGENT, retired_hit))
                        bad = True
                    short = None
                    for rid in order:
                        if balance.get(rid, 0) - need[rid] < 0:
                            short = rid
                            break
                    if short is not None:
                        findings.append((eid, CODE_FLOOR, short))
                        bad = True
                    if bad:
                        ws_rejected[wid] += 1
                        continue
                    for rid in order:
                        balance[rid] = balance.get(rid, 0) - need[rid]
                        consumed[rid] = consumed.get(rid, 0) + need[rid]
                        patch_consumed[(epid, rid)] = (
                            patch_consumed.get((epid, rid), 0) + need[rid]
                        )
                        ws_consumed[(wid, rid)] = (
                            ws_consumed.get((wid, rid), 0) + need[rid]
                        )
                    accrued[wid] += charge
                    ws_charge[wid] += charge
                    ws_admitted[wid] += 1
                    admitted += 1
                    slot = smith_slot(wid, canon)
                    slot["admitted_forges"] += 1
                    slot["charge"] += charge
                    settled_forge[eid] = {"charge": charge, "canon": canon}
                    fam = c.artifacts[entry["artifact_id"]]["family"]
                    live.setdefault((canon, fam), []).append(eid)
                    continue

                fref = source["entry_id"]
                if fref in credited_forges:
                    findings.append((eid, CODE_ALREADY, fref))
                    ws_rejected[wid] += 1
                    continue
                src_art = c.artifacts.get(source["artifact_id"])
                fam = src_art["family"] if src_art is not None else None
                window = []
                if fam is not None:
                    pool = live.get((canon, fam), [])
                    window = [f for f in pool if c.ledger_by_id[f]["day"] < day][-3:]
                if fref not in window:
                    findings.append((eid, CODE_UNCREDITED, fref))
                    ws_rejected[wid] += 1
                    continue

                src = settled_forge[fref]
                rate = self.rates.get(src_art["tier"], 0)
                gain = {}
                for rid, per in edition["lines"].items():
                    gain[rid] = gain.get(rid, 0) + pct(
                        per * source["units"], rate, self.mode
                    )
                for rid in sorted(gain):
                    units = gain[rid]
                    if units == 0:
                        continue
                    balance[rid] = balance.get(rid, 0) + units
                    returned[rid] = returned.get(rid, 0) + units
                    patch_returned[(epid, rid)] = (
                        patch_returned.get((epid, rid), 0) + units
                    )
                    ws_returned[(wid, rid)] = ws_returned.get((wid, rid), 0) + units
                credited_forges.add(fref)
                src_wid = source["workshop_id"]
                if src_wid in accrued:
                    accrued[src_wid] -= src["charge"]
                pool = live.get((src["canon"], fam))
                if pool is not None and fref in pool:
                    pool.remove(fref)
                ws_admitted[wid] += 1
                admitted += 1
                credited_salvages += 1
                smith_slot(wid, canon)["credited_salvages"] += 1

        return {
            "balance": balance,
            "closed": closed,
            "findings": findings,
            "called_for": called_for,
            "consumed": consumed,
            "returned": returned,
            "patch_consumed": patch_consumed,
            "patch_returned": patch_returned,
            "patch_acquired": patch_acquired,
            "ws_consumed": ws_consumed,
            "ws_returned": ws_returned,
            "ws_charge": ws_charge,
            "ws_admitted": ws_admitted,
            "ws_rejected": ws_rejected,
            "smith_rows": smith_rows,
            "admitted": admitted,
            "credited_salvages": credited_salvages,
        }

    def indices_from(self, state):
        out = {}
        for rid in self.c.scarce_ids:
            if self.reference == "opening":
                base = self.c.opening.get(rid, 0)
            elif self.reference == "opening-plus-acquired":
                base = self.c.opening.get(rid, 0) + self.acquired_total.get(rid, 0)
            elif self.reference == "acquired":
                base = self.acquired_total.get(rid, 0)
            else:
                base = state["called_for"].get(rid, 0)
            if base <= 0:
                out[rid] = 0
            else:
                out[rid] = min(
                    self.scarcity_ceiling,
                    reduce_q(state["consumed"].get(rid, 0) * 100, base, self.mode),
                )
        return out

    def _step(self, key, seen):
        hit = seen.get(key)
        if hit is None:
            current = dict(zip(self.c.scarce_ids, key))
            state = self.settle(current)
            nxt = self.indices_from(state)
            hit = (state, tuple(nxt[r] for r in self.c.scarce_ids))
            seen[key] = hit
        return hit

    def resolve(self):
        """V8/V9: the one assignment of scarcity indices that agrees with itself."""
        scarce = self.c.scarce_ids
        seen = {}
        bottom = tuple(0 for _ in scarce)
        top = tuple(self.scarcity_ceiling for _ in scarce)
        for start in (bottom, top):
            key = start
            walked = set()
            while key not in walked:
                walked.add(key)
                state, nxt = self._step(key, seen)
                if nxt == key:
                    return dict(zip(scarce, key)), state
                key = nxt
        # the indices may oscillate; every visited point is a candidate
        for key in sorted(seen):
            state, nxt = seen[key]
            if nxt == key:
                return dict(zip(scarce, key)), state
        low = [min(k[i] for k in seen) for i in range(len(scarce))]
        high = [max(k[i] for k in seen) for i in range(len(scarce))]
        spans = [high[i] - low[i] + 1 for i in range(len(scarce))]
        total = 1
        for s in spans:
            total *= s
        if total > 20000:
            low = [0] * len(scarce)
            spans = [self.scarcity_ceiling + 1] * len(scarce)
            total = 1
            for s in spans:
                total *= s
        if total <= 20000:
            for n in range(total):
                rest = n
                vals = []
                for i, s in enumerate(spans):
                    vals.append(low[i] + rest % s)
                    rest //= s
                key = tuple(vals)
                state, nxt = self._step(key, seen)
                if nxt == key:
                    return dict(zip(scarce, key)), state
        raise SystemExit("no settled assignment of scarcity indices was found")


# --------------------------------------------------------------------------
# requisition allocation
# --------------------------------------------------------------------------


class MaxFlow(object):
    __slots__ = ("n", "to", "cap", "head")

    def __init__(self, n):
        self.n = n
        self.to = []
        self.cap = []
        self.head = [[] for _ in range(n)]

    def add(self, u, v, fwd):
        if fwd <= 0:
            return
        self.head[u].append(len(self.to))
        self.to.append(v)
        self.cap.append(fwd)
        self.head[v].append(len(self.to))
        self.to.append(u)
        self.cap.append(0)

    def run(self, s, t):
        flow = 0
        n = self.n
        to = self.to
        cap = self.cap
        head = self.head
        while True:
            prev = [-1] * n
            prev_edge = [-1] * n
            prev[s] = s
            queue = [s]
            while queue and prev[t] < 0:
                nxt = []
                for u in queue:
                    for eid in head[u]:
                        v = to[eid]
                        if cap[eid] > 0 and prev[v] < 0:
                            prev[v] = u
                            prev_edge[v] = eid
                            nxt.append(v)
                queue = nxt
            if prev[t] < 0:
                return flow
            bottleneck = None
            v = t
            while v != s:
                eid = prev_edge[v]
                if bottleneck is None or cap[eid] < bottleneck:
                    bottleneck = cap[eid]
                v = prev[v]
            v = t
            while v != s:
                eid = prev_edge[v]
                cap[eid] -= bottleneck
                cap[eid ^ 1] += bottleneck
                v = prev[v]
            flow += bottleneck


def _smear(bits, low, high, mask):
    """Every sum reachable by adding one value of [low, high] to `bits`."""
    out = (bits << low) & mask
    span = high - low
    step = 1
    while span > 0:
        take = step if step < span else span
        out |= (out << take) & mask
        span -= take
        step <<= 1
    return out


class Allocator(object):
    """The one funding plan Q1 through Q8 single out."""

    def __init__(self, season, closing):
        c = season.c
        self.pool = max(0, season.pool)
        self.reqs = sorted(c.requisitions, key=lambda r: r["req_id"])
        self.lo = {}
        self.hi = {}
        self.guild_of = {}
        self.reagent_of = {}
        self.charter_of = {}
        self.eligible = []
        for r in self.reqs:
            rid = r["req_id"]
            wid = r["workshop_id"]
            if wid not in season.caps:  # Q1
                continue
            w = c.workshops[wid]
            hi = min(
                int(r["units_requested"]),
                season.tier_unit_cap.get(w["charter_tier"], 0),
                self.pool,
            )
            lo = max(int(r["min_units"]), 1)
            if hi < lo:  # Q2 leaves no room for a grant
                continue
            self.eligible.append(rid)
            self.lo[rid] = lo
            self.hi[rid] = hi
            self.guild_of[rid] = w["guild_id"]
            self.reagent_of[rid] = r["reagent_id"]
            self.charter_of[rid] = w["charter_id"]

        guild_cap = {}
        reagent_cap = {}
        for rid in self.eligible:
            g = self.guild_of[rid]
            guild_cap[g] = min(season.guild_cap.get(g, self.pool), self.pool)
            rg = self.reagent_of[rid]
            meta = c.reagents.get(rg)
            if meta is not None and meta["scarce"]:  # Q5
                reagent_cap[rg] = min(max(0, closing.get(rg, 0)), self.pool)
            else:
                reagent_cap[rg] = self.pool

        self.charters = {}
        for rid in self.eligible:
            self.charters.setdefault(self.charter_of[rid], []).append(rid)
        for lst in self.charters.values():
            lst.sort(key=lambda x: (-self.hi[x], x))
        self.charter_ids = sorted(self.charters)

        self.guild_list = sorted(guild_cap)
        self.reagent_list = sorted(reagent_cap)
        self.gcaps = [guild_cap[g] for g in self.guild_list]
        self.rcaps = [reagent_cap[r] for r in self.reagent_list]
        gidx = dict((g, i) for i, g in enumerate(self.guild_list))
        ridx = dict((r, i) for i, r in enumerate(self.reagent_list))
        self.gi = dict((rid, gidx[self.guild_of[rid]]) for rid in self.eligible)
        self.ri = dict((rid, ridx[self.reagent_of[rid]]) for rid in self.eligible)
        self.mask = (1 << (self.pool + 1)) - 1

    # -- the value of a settled selection ---------------------------------

    def _flow_total(self, items):
        """Greatest total units over plans funding exactly `items`.

        `items` is a list of (req_id, lower, upper); None when no plan honours
        every lower bound.
        """
        ng = len(self.gcaps)
        nr = len(self.rcaps)
        gi = self.gi
        ri = self.ri
        ug = [0] * ng
        ur = [0] * nr
        base = 0
        for rid, lo, hi in items:
            ug[gi[rid]] += lo
            ur[ri[rid]] += lo
            base += lo
        if base > self.pool:
            return None
        for i in range(ng):
            if ug[i] > self.gcaps[i]:
                return None
        for i in range(nr):
            if ur[i] > self.rcaps[i]:
                return None
        if base >= self.pool:
            return self.pool
        mf = MaxFlow(2 + ng + nr)
        for i in range(ng):
            mf.add(0, 2 + i, self.gcaps[i] - ug[i])
        for rid, lo, hi in items:
            if hi > lo:
                mf.add(2 + gi[rid], 2 + ng + ri[rid], hi - lo)
        for i in range(nr):
            mf.add(2 + ng + i, 1, self.rcaps[i] - ur[i])
        return min(self.pool, base + mf.run(0, 1))

    def _flow_bound(self, items, groups, k):
        """Upper bound once `items` are funded and groups[k:] stay undecided."""
        ng = len(self.gcaps)
        nr = len(self.rcaps)
        gi = self.gi
        ri = self.ri
        hid = self.hi
        rest = groups[k:]
        nc = len(rest)
        ug = [0] * ng
        ur = [0] * nr
        base = 0
        for rid, lo, hi in items:
            ug[gi[rid]] += lo
            ur[ri[rid]] += lo
            base += lo
        if base >= self.pool:
            return self.pool
        gin = 2 + nc
        gout = gin + ng
        rbase = gout + ng
        mf = MaxFlow(rbase + nr)
        pair = {}
        for rid, lo, hi in items:
            room = hi - lo
            if room <= 0:
                continue
            mf.add(0, gin + gi[rid], room)
            key = (gi[rid], ri[rid])
            pair[key] = pair.get(key, 0) + room
        for j in range(nc):
            top = 0
            per_g = {}
            for rid in rest[j]:
                h = hid[rid]
                if h > top:
                    top = h
                g = gi[rid]
                if h > per_g.get(g, 0):
                    per_g[g] = h
                key = (g, ri[rid])
                pair[key] = pair.get(key, 0) + h
            mf.add(0, 2 + j, top)
            for g in sorted(per_g):
                mf.add(2 + j, gin + g, per_g[g])
        for i in range(ng):
            mf.add(gin + i, gout + i, self.gcaps[i] - ug[i])
        for key in sorted(pair):
            mf.add(gout + key[0], rbase + key[1], pair[key])
        for i in range(nr):
            mf.add(rbase + i, 1, self.rcaps[i] - ur[i])
        return min(self.pool, base + mf.run(0, 1))

    # -- enumeration ------------------------------------------------------

    def _undominated(self, members):
        keep = []
        for a in members:
            beaten = False
            for b in members:
                if b == a:
                    continue
                if (
                    self.gi[a] == self.gi[b]
                    and self.ri[a] == self.ri[b]
                    and self.lo[b] <= self.lo[a]
                    and self.hi[b] >= self.hi[a]
                    and (self.lo[b], -self.hi[b], b) < (self.lo[a], -self.hi[a], a)
                ):
                    beaten = True
                    break
            if not beaten:
                keep.append(a)
        return keep

    def _prep(self, bounds):
        """Split a partial plan into forced grants and undecided charters."""
        forced = []
        taken = set()
        blocked = set()
        for rid in sorted(bounds):
            span = bounds[rid]
            if rid not in self.lo:
                continue
            if span is None:
                blocked.add(rid)
                continue
            lo, hi = span
            if lo < self.lo[rid] or hi > self.hi[rid] or lo > hi:
                return None
            cid = self.charter_of[rid]
            if cid in taken:  # Q6
                return None
            taken.add(cid)
            forced.append((rid, lo, hi))
        groups = []
        for cid in self.charter_ids:
            if cid in taken:
                continue
            members = [r for r in self.charters[cid] if r not in blocked]
            if members:
                groups.append(self._undominated(members))
        groups.sort(key=lambda m: (-max(self.hi[r] for r in m), m[0]))
        return forced, groups

    def max_total(self, bounds, stop=None):
        """Greatest total units; may stop early once `stop` units are reached."""
        prep = self._prep(bounds)
        if prep is None:
            return -1
        forced, groups = prep
        ng = len(self.gcaps)
        nr = len(self.rcaps)
        n = len(groups)
        gcaps = self.gcaps
        rcaps = self.rcaps
        pool = self.pool
        mask = self.mask
        gi = self.gi
        ri = self.ri

        # reachable additions from the charters still to be decided
        one = 1
        suf_all = [one] * (n + 1)
        suf_g = [None] * (n + 1)
        suf_r = [None] * (n + 1)
        suf_g[n] = [one] * ng
        suf_r[n] = [one] * nr
        for j in range(n - 1, -1, -1):
            members = groups[j]
            total = suf_all[j + 1]
            for rid in members:
                total |= _smear(suf_all[j + 1], self.lo[rid], self.hi[rid], mask)
            suf_all[j] = total
            row_g = list(suf_g[j + 1])
            row_r = list(suf_r[j + 1])
            for rid in members:
                g = gi[rid]
                row_g[g] |= _smear(
                    suf_g[j + 1][g], self.lo[rid], self.hi[rid], mask
                )
                r = ri[rid]
                row_r[r] |= _smear(
                    suf_r[j + 1][r], self.lo[rid], self.hi[rid], mask
                )
            suf_g[j] = row_g
            suf_r[j] = row_r

        sel = list(forced)
        run = [sum(h for _, _, h in sel), sum(l for _, l, _ in sel)]
        g_hi = [0] * ng
        r_hi = [0] * nr
        g_lo = [0] * ng
        r_lo = [0] * nr
        for rid, lo, hi in sel:
            g_hi[gi[rid]] += hi
            r_hi[ri[rid]] += hi
            g_lo[gi[rid]] += lo
            r_lo[ri[rid]] += lo

        def reach_bound(j):
            """None when no plan survives, else an upper bound on the total."""
            room = pool - run[1]
            if room < 0:
                return None
            bits = suf_all[j] & ((one << (room + 1)) - 1)
            if not bits:
                return None
            value = run[0] + bits.bit_length() - 1
            if value > pool:
                value = pool
            acc = 0
            for i in range(ng):
                room = gcaps[i] - g_lo[i]
                if room < 0:
                    return None
                bits = suf_g[j][i] & ((one << (room + 1)) - 1)
                if not bits:
                    return None
                reach = g_hi[i] + bits.bit_length() - 1
                acc += reach if reach < gcaps[i] else gcaps[i]
            if acc < value:
                value = acc
            acc = 0
            for i in range(nr):
                room = rcaps[i] - r_lo[i]
                if room < 0:
                    return None
                bits = suf_r[j][i] & ((one << (room + 1)) - 1)
                if not bits:
                    return None
                reach = r_hi[i] + bits.bit_length() - 1
                acc += reach if reach < rcaps[i] else rcaps[i]
            if acc < value:
                value = acc
            return value

        root = reach_bound(0)
        if root is None:
            return -1
        flow_root = self._flow_bound(sel, groups, 0)
        if flow_root < root:
            root = flow_root
        ceiling = root if stop is None else min(root, stop)

        best = self._flow_total(sel)
        if best is None:
            best = -1
        # a greedy plan first, to give the bound something to prune against
        seed = list(sel)
        for members in groups:
            pick = None
            for rid in members:
                value = self._flow_total(seed + [(rid, self.lo[rid], self.hi[rid])])
                if value is not None and (pick is None or value > pick[0]):
                    pick = (value, rid)
            if pick is None:
                continue
            seed.append((pick[1], self.lo[pick[1]], self.hi[pick[1]]))
            if pick[0] > best:
                best = pick[0]
        if best >= ceiling:
            return best

        state = [best, False]

        def dfs(j):
            value = reach_bound(j)
            if value is None or value <= state[0]:
                return
            if j == n:
                total = self._flow_total(sel)
                if total is not None and total > state[0]:
                    state[0] = total
                    if total >= ceiling:
                        state[1] = True
                return
            if self._flow_bound(sel, groups, j) <= state[0]:
                return
            for rid in groups[j]:
                lo = self.lo[rid]
                hi = self.hi[rid]
                g = gi[rid]
                r = ri[rid]
                sel.append((rid, lo, hi))
                run[0] += hi
                run[1] += lo
                g_hi[g] += hi
                r_hi[r] += hi
                g_lo[g] += lo
                r_lo[r] += lo
                dfs(j + 1)
                run[0] -= hi
                run[1] -= lo
                g_hi[g] -= hi
                r_hi[r] -= hi
                g_lo[g] -= lo
                r_lo[r] -= lo
                sel.pop()
                if state[1]:
                    return
            dfs(j + 1)

        dfs(0)
        return state[0]

    def solve(self):
        best_total = self.max_total({})
        if best_total < 0:
            best_total = 0
        fixed = {}
        bounds = {}
        for r in sorted(self.reqs, key=lambda x: (int(x["priority"]), x["req_id"])):
            rid = r["req_id"]
            if rid not in self.lo or best_total == 0:
                fixed[rid] = 0
                bounds[rid] = None
                continue
            low = self.lo[rid]
            high = self.hi[rid]
            trial = dict(bounds)
            trial[rid] = (low, high)
            if self.max_total(trial, best_total) < best_total:
                fixed[rid] = 0
                bounds[rid] = None
                continue
            while low < high:  # Q8
                mid = (low + high + 1) // 2
                trial = dict(bounds)
                trial[rid] = (mid, high)
                if self.max_total(trial, best_total) >= best_total:
                    low = mid
                else:
                    high = mid - 1
            fixed[rid] = low
            bounds[rid] = (low, low)
        return fixed, best_total


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------


def write_json(path, obj):
    text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def build_outputs(corpus, season, indices, state, grants, out_dir):
    c = corpus
    reagent_ids = c.reagent_ids
    allocated_total = sum(grants.values())

    closing = {}
    for rid in reagent_ids:
        closing[rid] = (
            c.opening.get(rid, 0)
            + season.acquired_total.get(rid, 0)
            + state["returned"].get(rid, 0)
            - state["consumed"].get(rid, 0)
        )

    patch_rows = []
    running = dict((rid, c.opening.get(rid, 0)) for rid in reagent_ids)
    season_residual = 0
    for p in c.patches:
        rows = []
        presidual = 0
        for rid in reagent_ids:
            opening = running[rid]
            acq = state["patch_acquired"].get((p["patch_id"], rid), 0)
            ret = state["patch_returned"].get((p["patch_id"], rid), 0)
            con = state["patch_consumed"].get((p["patch_id"], rid), 0)
            close = opening + acq + ret - con
            residual = opening + acq + ret - con - close
            presidual += abs(residual)
            rows.append(
                {
                    "reagent_id": rid,
                    "opening_units": opening,
                    "acquired_units": acq,
                    "returned_units": ret,
                    "consumed_units": con,
                    "closing_units": close,
                    "residual": residual,
                }
            )
            running[rid] = close
        season_residual += presidual
        patch_rows.append(
            {
                "patch_id": p["patch_id"],
                "ordinal": p["ordinal"],
                "reagents": rows,
                "residual": presidual,
            }
        )

    conservation_residual = 0
    for rid in reagent_ids:
        conservation_residual += abs(
            c.opening.get(rid, 0)
            + season.acquired_total.get(rid, 0)
            + state["returned"].get(rid, 0)
            - state["consumed"].get(rid, 0)
            - closing[rid]
        )

    ws_alloc = dict((w, 0) for w in season.scope)
    for r in c.requisitions:
        wid = r["workshop_id"]
        if wid in ws_alloc:
            ws_alloc[wid] += grants.get(r["req_id"], 0)

    charge_by_workshop = dict((w, state["ws_charge"][w]) for w in season.scope)
    charge_total = sum(charge_by_workshop.values())
    guild_workshops = {}
    for w in season.scope:
        guild_workshops.setdefault(c.workshops[w]["guild_id"], []).append(w)
    guilds = sorted(guild_workshops)
    for g in guilds:
        guild_workshops[g].sort()
    charge_by_guild = dict(
        (g, sum(charge_by_workshop[w] for w in guild_workshops[g])) for g in guilds
    )

    entries_total = len(c.ledger)
    admitted = state["admitted"]
    findings = sorted(set(state["findings"]), key=lambda f: (f[0], f[1]))
    uncredited = sum(1 for f in findings if f[1] == CODE_UNCREDITED)

    write_json(
        os.path.join(out_dir, "summary.json"),
        {
            "season": {
                "first_day": c.first_day,
                "last_day": c.last_day,
                "patch_count": len(c.patches),
            },
            "workshops_in_scope": list(season.scope),
            "guilds_in_scope": guilds,
            "entries_total": entries_total,
            "entries_admitted": admitted,
            "entries_rejected": entries_total - admitted,
            "credited_salvages": state["credited_salvages"],
            "uncredited_salvages": uncredited,
            "scarcity_index": dict(
                (rid, indices.get(rid, 0)) for rid in c.scarce_ids
            ),
            "season_charge_ember": charge_total,
            "allocated_units_total": allocated_total,
            "conservation_residual": conservation_residual,
        },
    )

    write_json(
        os.path.join(out_dir, "vault_audit.json"),
        {
            "reagents": [
                {
                    "reagent_id": rid,
                    "grade": c.reagents[rid]["grade"],
                    "scarce": bool(c.reagents[rid]["scarce"]),
                    "opening_units": c.opening.get(rid, 0),
                    "acquired_units": season.acquired_total.get(rid, 0),
                    "returned_units": state["returned"].get(rid, 0),
                    "consumed_units": state["consumed"].get(rid, 0),
                    "closing_units": closing[rid],
                    "scarcity_index": indices.get(rid, 0)
                    if c.reagents[rid]["scarce"]
                    else 0,
                }
                for rid in reagent_ids
            ]
        },
    )

    write_json(
        os.path.join(out_dir, "reconciliation.json"),
        {
            "patches": patch_rows,
            "season_residual": season_residual,
            "charge_by_workshop": dict(
                (w, charge_by_workshop[w]) for w in season.scope
            ),
            "charge_by_guild": dict((g, charge_by_guild[g]) for g in guilds),
            "charge_total": charge_total,
        },
    )

    counts = {}
    for _, code, _ in findings:
        counts[code] = counts.get(code, 0) + 1
    write_json(
        os.path.join(out_dir, "data_quality.json"),
        {
            "findings": [
                {"entry_id": eid, "code": code, "detail": detail}
                for eid, code, detail in findings
            ],
            "counts": dict((code, counts[code]) for code in sorted(counts)),
        },
    )

    write_json(
        os.path.join(out_dir, "allocation.json"),
        {
            "pool_units": season.pool,
            "assignments": [
                {
                    "req_id": r["req_id"],
                    "workshop_id": r["workshop_id"],
                    "reagent_id": r["reagent_id"],
                    "allocated_units": grants.get(r["req_id"], 0),
                    "served": grants.get(r["req_id"], 0) > 0,
                }
                for r in sorted(c.requisitions, key=lambda x: x["req_id"])
            ],
            "allocated_total": allocated_total,
        },
    )

    ws_flow = {}
    for (wid, rid), units in state["ws_consumed"].items():
        ws_flow.setdefault(wid, {}).setdefault(rid, [0, 0])[0] += units
    for (wid, rid), units in state["ws_returned"].items():
        ws_flow.setdefault(wid, {}).setdefault(rid, [0, 0])[1] += units

    for wid in season.scope:
        w = c.workshops[wid]
        smiths = []
        for (swid, canon) in sorted(state["smith_rows"]):
            if swid != wid:
                continue
            slot = state["smith_rows"][(swid, canon)]
            smiths.append(
                {
                    "canonical_smith": canon,
                    "admitted_forges": slot["admitted_forges"],
                    "credited_salvages": slot["credited_salvages"],
                    "charge_ember": slot["charge"],
                }
            )
        flow = ws_flow.get(wid, {})
        write_json(
            os.path.join(out_dir, "workshop_%s.json" % wid),
            {
                "workshop_id": wid,
                "guild_id": w["guild_id"],
                "charter_id": w["charter_id"],
                "charter_tier": w["charter_tier"],
                "entries_admitted": state["ws_admitted"][wid],
                "entries_rejected": state["ws_rejected"][wid],
                "charge_ember": charge_by_workshop[wid],
                "cap_ember": season.caps[wid],
                "cap_reached": wid in state["closed"],
                "allocated_units": ws_alloc[wid],
                "smiths": smiths,
                "reagent_flow": [
                    {
                        "reagent_id": rid,
                        "consumed_units": flow[rid][0],
                        "returned_units": flow[rid][1],
                        "net_units": flow[rid][0] - flow[rid][1],
                    }
                    for rid in sorted(flow)
                ],
            },
        )

    for g in guilds:
        members = guild_workshops[g]
        merged = {}
        for wid in members:
            for rid, pair in ws_flow.get(wid, {}).items():
                slot = merged.setdefault(rid, [0, 0])
                slot[0] += pair[0]
                slot[1] += pair[1]
        write_json(
            os.path.join(out_dir, "guild_%s.json" % g),
            {
                "guild_id": g,
                "workshops": members,
                "entries_admitted": sum(state["ws_admitted"][w] for w in members),
                "charge_ember": charge_by_guild[g],
                "allocated_units": sum(ws_alloc[w] for w in members),
                "reagent_flow": [
                    {
                        "reagent_id": rid,
                        "consumed_units": merged[rid][0],
                        "returned_units": merged[rid][1],
                        "net_units": merged[rid][0] - merged[rid][1],
                    }
                    for rid in sorted(merged)
                ],
            },
        )


def main(argv):
    data_dir = argv[1] if len(argv) > 1 else "/app/data"
    out_dir = argv[2] if len(argv) > 2 else "/app/out"
    missing = [
        name
        for name in REQUIRED_FILES
        if not os.path.isfile(os.path.join(data_dir, name))
    ]
    if missing:
        for name in missing:
            sys.stderr.write(
                "missing required input file: %s\n" % os.path.join(data_dir, name)
            )
        return 2
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    corpus = Corpus(data_dir)
    season = Season(corpus)
    indices, state = season.resolve()
    closing = dict(
        (
            rid,
            corpus.opening.get(rid, 0)
            + season.acquired_total.get(rid, 0)
            + state["returned"].get(rid, 0)
            - state["consumed"].get(rid, 0),
        )
        for rid in corpus.reagent_ids
    )
    grants, _ = Allocator(season, closing).solve()
    build_outputs(corpus, season, indices, state, grants, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
