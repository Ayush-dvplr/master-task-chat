"""Grader for emberforge-vault-settlement.

Self-contained: stdlib only, no network, no reference bytes baked in.  The
grader re-derives the season's truth from the shipped corpus with its own copy
of the settlement engine, and it settles every corpus under the draw whose
council rulings it published with that corpus, the draw a correct solution
must recover from the rulings.
"""

from __future__ import annotations

import copy
import ast
import csv
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path
import threading
from rewardkit import criteria, criterion

# SAMPLE_SEED builds the season the agent receives; EVAL_SEED and
# CHALLENGE_SEED root the reseeded seasons only the grader builds.
SAMPLE_SEED = 11
EVAL_SEED = 23
CHALLENGE_SEED = 61

# --------------------------------------------------------------------------
# deterministic PRNG
# --------------------------------------------------------------------------

MASK64 = (1 << 64) - 1


class Rng:
    def __init__(self, seed: int) -> None:
        s = (seed * 0x9E3779B97F4A7C15 + 0x1234567) & MASK64
        self.s = s or 0x9E3779B97F4A7C15

    def next(self) -> int:
        x = self.s
        x ^= (x << 13) & MASK64
        x ^= x >> 7
        x ^= (x << 17) & MASK64
        self.s = x & MASK64
        return self.s

    def below(self, n: int) -> int:
        return self.next() % n

    def between(self, lo: int, hi: int) -> int:
        return lo + self.below(hi - lo + 1)

    def pick(self, seq):
        return seq[self.below(len(seq))]


# --------------------------------------------------------------------------
# withheld parameter axes
# --------------------------------------------------------------------------

RETURN_SCHEDULES: dict[str, dict[int, int]] = {
    "RS-A": {1: 40, 2: 50, 3: 60},
    "RS-B": {1: 45, 2: 55, 3: 65},
    "RS-C": {1: 50, 2: 60, 3: 70},
    "RS-D": {1: 35, 2: 50, 3: 65},
    "RS-E": {1: 55, 2: 55, 3: 55},
    "RS-F": {1: 30, 2: 45, 3: 60},
    "RS-G": {1: 60, 2: 50, 3: 40},
}

QUANTISERS = ("floor", "ceil", "half-up", "half-down", "half-even")

OPERATOR_ORDERS = tuple("".join(p) for p in permutations("FGS"))

SCARCITY_BASES = ("opening", "opening-plus-acquired", "consumed", "acquired")


@dataclass(frozen=True)
class Params:
    schedule: str
    quantiser: str
    order: str
    base: str


def all_params() -> list[Params]:
    out = []
    for s in RETURN_SCHEDULES:
        for q in QUANTISERS:
            for o in OPERATOR_ORDERS:
                for b in SCARCITY_BASES:
                    out.append(Params(s, q, o, b))
    return out


def quantise(num: int, den: int, mode: str) -> int:
    """Integer quantisation of num/den (den > 0, num may be negative)."""
    if den <= 0:
        raise ValueError("denominator must be positive")
    q, r = divmod(num, den)  # python floor division
    if r == 0:
        return q
    if mode == "floor":
        return q
    if mode == "ceil":
        return q + 1
    twice = 2 * r
    if mode == "half-up":
        return q + 1 if twice >= den else q
    if mode == "half-down":
        return q + 1 if twice > den else q
    if mode == "half-even":
        if twice > den:
            return q + 1
        if twice < den:
            return q
        return q if q % 2 == 0 else q + 1
    raise ValueError(f"unknown quantiser {mode!r}")


# --------------------------------------------------------------------------
# corpus model
# --------------------------------------------------------------------------

ARTIFACT_FAMILIES = ("blade", "ward", "sigil", "relic")
FAMILY_MULTIPLIER = {"blade": 130, "ward": 115, "sigil": 145, "relic": 160}
REAGENT_FAMILIES = ("ore", "essence", "alloy")
SCARCITY_CEILING = 60


@dataclass
class Corpus:
    patches: list[dict]
    reagents: list[dict]
    artifacts: list[dict]
    editions: list[dict]
    workshops: list[dict]
    identity: list[dict]
    ledger: list[dict]
    acquisitions: list[dict]
    opening: list[dict]
    requisitions: dict
    charter: dict


def _slug(n: int) -> str:
    names = [
        "cinderhall", "gloamworks", "slagmoor", "verdigris",
        "brackenvault", "quenchspar", "emberdown", "thornreach",
    ]
    return names[n % len(names)]


def build_corpus(seed: int, profile: str = "main") -> Corpus:
    rng = Rng(seed)
    small = profile == "slice"

    n_patch = 3 if small else 7
    n_reagent = 6 if small else 14
    n_artifact = 6 if small else 20
    n_smith = 8 if small else 44
    n_entry = 34 if small else 300
    n_workshop = 3 if small else 6

    # -- patches -----------------------------------------------------------
    patches = []
    day = 1
    span = 20 if small else 26
    for i in range(n_patch):
        closes = day + span - 1
        patches.append(
            {
                "patch_id": f"P{i + 1:02d}",
                "opens_day": day,
                "closes_day": closes,
                "ordinal": i + 1,
            }
        )
        day = closes + 1
    season_first = patches[0]["opens_day"]
    season_last = patches[-1]["closes_day"]

    # -- reagents ----------------------------------------------------------
    reagents = []
    n_scarce = 2 if small else 3
    scarce_at = set()
    while len(scarce_at) < n_scarce:
        scarce_at.add(rng.below(n_reagent))
    for i in range(n_reagent):
        reagents.append(
            {
                "reagent_id": f"R{i + 1:02d}",
                "grade": 1 + (i % 3),
                "family": REAGENT_FAMILIES[i % 3],
                "scarce": 1 if i in scarce_at else 0,
                "retired_patch": "",
            }
        )
    scarce_ids = [r["reagent_id"] for r in reagents if r["scarce"]]

    # -- artifacts ---------------------------------------------------------
    artifacts = []
    for i in range(n_artifact):
        artifacts.append(
            {
                "artifact_id": f"A{i + 1:02d}",
                "family": ARTIFACT_FAMILIES[i % len(ARTIFACT_FAMILIES)],
                "tier": 1 + (i % 3),
                "base_charge": 100 + 40 * (i % 7) + 10 * (i % 3),
                "introduced_patch": patches[min(i // 6, n_patch - 1)]["patch_id"],
            }
        )

    # -- recipe editions ---------------------------------------------------
    editions = []
    for a in artifacts:
        intro = next(p for p in patches if p["patch_id"] == a["introduced_patch"])
        cuts = [intro["ordinal"]]
        if small:
            if intro["ordinal"] + 1 <= n_patch:
                cuts.append(intro["ordinal"] + 1)
        else:
            mid = intro["ordinal"] + 1 + rng.below(max(1, n_patch - intro["ordinal"]))
            if n_patch >= 3 and intro["ordinal"] < mid <= n_patch:
                cuts.append(mid)
        cuts = sorted(set(cuts))
        for k, start in enumerate(cuts):
            end = (cuts[k + 1] - 1) if k + 1 < len(cuts) else n_patch
            n_line = 2 + rng.below(2)
            chosen: list[str] = []
            # every edition of a scarce-bearing artifact keeps at least one scarce line
            if (int(a["artifact_id"][1:]) % 3) == 0:
                chosen.append(scarce_ids[rng.below(len(scarce_ids))])
            while len(chosen) < n_line:
                cand = reagents[rng.below(n_reagent)]["reagent_id"]
                if cand not in chosen:
                    chosen.append(cand)
            for rid in chosen:
                editions.append(
                    {
                        "recipe_id": f"RC-{a['artifact_id']}",
                        "artifact_id": a["artifact_id"],
                        "edition": k + 1,
                        "from_patch": f"P{start:02d}",
                        "to_patch": f"P{end:02d}",
                        "reagent_id": rid,
                        "units_per_craft": 1 + rng.below(3) + k + (k if rid in scarce_ids else 0),
                    }
                )

    # -- workshops ---------------------------------------------------------
    guilds = ["ashen_compact", "tidebound_league"]
    workshops = []
    for i in range(n_workshop):
        in_scope = i < (2 if small else 4)
        workshops.append(
            {
                "workshop_id": _slug(i),
                "charter_id": f"CH-{(i % 3) + 1:02d}",
                "guild_id": guilds[0] if small else guilds[i % 2],
                "opened_day": season_first - 10 if in_scope else season_first + 12,
                "closed_day": "" if in_scope else season_last - 5,
                "charter_tier": (3 if i % 2 == 0 else 2) if in_scope else 1,
            }
        )
    scope_ids = [w["workshop_id"] for w in workshops if _in_scope(w, season_first, season_last)]

    # -- smiths + identity -------------------------------------------------
    identity = []
    smiths = [f"S{i + 1:03d}" for i in range(n_smith)]
    eid = 0
    renamed: dict[str, str] = {}
    merged: dict[str, str] = {}
    retired: dict[str, int] = {}
    n_rename = 2 if small else 7
    n_merge = 1 if small else 5
    n_retire = 1 if small else 3
    pool = list(smiths)
    for _ in range(n_rename):
        src = pool[rng.below(len(pool))]
        if src in renamed or src in merged:
            continue
        dst = f"{src}-x"
        eid += 1
        identity.append(
            {
                "event_id": f"IE{eid:03d}",
                "day": rng.between(season_first + 5, season_last - 5),
                "kind": "rename",
                "from_ref": src,
                "to_ref": dst,
            }
        )
        renamed[src] = dst
    for _ in range(n_merge):
        src = pool[rng.below(len(pool))]
        dst = pool[rng.below(len(pool))]
        if src == dst or src in merged or src in renamed or dst in merged:
            continue
        eid += 1
        identity.append(
            {
                "event_id": f"IE{eid:03d}",
                "day": rng.between(season_first + 5, season_last - 5),
                "kind": "merge",
                "from_ref": src,
                "to_ref": dst,
            }
        )
        merged[src] = dst
    for _ in range(n_retire):
        src = pool[rng.below(len(pool))]
        if src in merged or src in renamed:
            continue
        d = rng.between(season_first + 8, season_last - 3)
        eid += 1
        identity.append(
            {"event_id": f"IE{eid:03d}", "day": d, "kind": "retire", "from_ref": src, "to_ref": ""}
        )
        retired[src] = d
    identity.sort(key=lambda e: (e["day"], e["event_id"]))

    # -- opening stock + acquisitions -------------------------------------
    opening = [
        {
            "reagent_id": r["reagent_id"],
            "opening_units": (
                ((40 if small else 260) + 7 * i)
                if (small or r["reagent_id"] not in scarce_ids)
                else (120 + 3 * i)
            ),
        }
        for i, r in enumerate(reagents)
    ]
    acquisitions = []
    aid = 0
    for p in patches:
        for r in reagents:
            if rng.below(10) < (7 if r["scarce"] else 5):
                aid += 1
                acquisitions.append(
                    {
                        "acq_id": f"AQ{aid:04d}",
                        "patch_id": p["patch_id"],
                        "day": rng.between(p["opens_day"], p["closes_day"]),
                        "reagent_id": r["reagent_id"],
                        "units": rng.between(20, 60) if not small else rng.between(8, 20),
                        "workshop_id": scope_ids[rng.below(len(scope_ids))],
                    }
                )
    acquisitions.sort(key=lambda a: (a["day"], a["acq_id"]))

    # -- ledger ------------------------------------------------------------
    ledger = []
    forge_pool: list[dict] = []
    lid = 0
    intro_day = {
        a["artifact_id"]: next(
            p["opens_day"] for p in patches if p["patch_id"] == a["introduced_patch"]
        )
        for a in artifacts
    }
    for _ in range(n_entry):
        lid += 1
        do_salvage = len(forge_pool) >= 4 and rng.below(10) < 3
        if do_salvage:
            src = forge_pool[len(forge_pool) - 1 - rng.below(min(9, len(forge_pool)))]
            if src["day"] >= season_last:
                do_salvage = False
        if do_salvage:
            lo = min(src["day"] + span, season_last) if small else src["day"] + 1
            day_v = rng.between(min(lo, season_last), season_last)
            p = _patch_of(patches, day_v)
            ledger.append(
                {
                    "entry_id": f"L{lid:04d}",
                    "patch_id": p["patch_id"],
                    "day": day_v,
                    "workshop_id": src["workshop_id"],
                    "smith_ref": src["smith_ref"],
                    "op": "salvage",
                    "artifact_id": src["artifact_id"],
                    "units": src["units"],
                    "forge_ref": src["entry_id"],
                }
            )
        else:
            a = artifacts[rng.below(len(artifacts))]
            day_v = rng.between(intro_day[a["artifact_id"]], season_last)
            p = _patch_of(patches, day_v)
            ws = (
                workshops[rng.below(len(scope_ids))]
                if rng.below(10) < 8
                else workshops[rng.below(len(workshops))]
            )
            entry = {
                "entry_id": f"L{lid:04d}",
                "patch_id": p["patch_id"],
                "day": day_v,
                "workshop_id": ws["workshop_id"],
                "smith_ref": smiths[rng.below(len(smiths))],
                "op": "forge",
                "artifact_id": a["artifact_id"],
                "units": 1 + rng.below(3),
                "forge_ref": "",
            }
            ledger.append(entry)
            forge_pool.append(entry)
    # a few entries that cannot resolve an edition (referential closure)
    n_bad = 2 if small else 4
    for i in range(n_bad):
        lid += 1
        day_v = rng.between(season_first, season_last)
        p = _patch_of(patches, day_v)
        ledger.append(
            {
                "entry_id": f"L{lid:04d}",
                "patch_id": p["patch_id"],
                "day": day_v,
                "workshop_id": scope_ids[rng.below(len(scope_ids))],
                "smith_ref": smiths[rng.below(len(smiths))],
                "op": "forge",
                "artifact_id": f"A{90 + i:02d}",
                "units": 1,
                "forge_ref": "",
            }
        )
    ledger.sort(key=lambda e: (e["day"], e["entry_id"]))

    charter = {
        "season_pool_units": 48 if small else 150,
        "guild_cap_units": {g: (30 if small else 84) for g in guilds},
        "tier_unit_cap": {"1": 0, "2": 18, "3": 34},
        "scarcity_ceiling": SCARCITY_CEILING,
        "family_multiplier": FAMILY_MULTIPLIER,
        "grade_step": 10,
        "tier_charge_cap": {"1": 0, "2": 7400, "3": 24000} if small else {"1": 0, "2": 38000, "3": 120000},
    }

    requisitions = {"requisitions": []}
    for i, wid in enumerate(scope_ids):
        requisitions["requisitions"].append(
            {
                "req_id": f"RQ{i + 1:02d}",
                "workshop_id": wid,
                "reagent_id": scarce_ids[i % len(scarce_ids)],
                "priority": 1 + (i % 3),
                "min_units": 6 + 2 * (i % 3),
                "units_requested": 14 + 4 * (i % 3),
            }
        )

    return Corpus(
        patches=patches,
        reagents=reagents,
        artifacts=artifacts,
        editions=editions,
        workshops=workshops,
        identity=identity,
        ledger=ledger,
        acquisitions=acquisitions,
        opening=opening,
        requisitions=requisitions,
        charter=charter,
    )


def _in_scope(w: dict, first: int, last: int) -> bool:
    opened = int(w["opened_day"])
    closed = w["closed_day"]
    if opened > first:
        return False
    if closed not in ("", None) and int(closed) < last:
        return False
    return int(w["charter_tier"]) >= 2


def _patch_of(patches: list[dict], day: int) -> dict:
    for p in patches:
        if p["opens_day"] <= day <= p["closes_day"]:
            return p
    return patches[-1]


CODES = (
    "CAP_REACHED",
    "MISSING_FORGE_REF",
    "OUT_OF_SCOPE_WORKSHOP",
    "RETIRED_REAGENT",
    "RETIRED_SMITH",
    "SALVAGE_ALREADY_CREDITED",
    "STOCK_FLOOR",
    "UNCREDITED_SALVAGE",
    "UNRESOLVED_EDITION",
)


# ---------------------------------------------------------------- loading --


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def load(data_dir: Path, prefix: str = "") -> dict:
    d = Path(data_dir)
    g = lambda stem: d / f"{prefix}{stem}"
    corp = {
        "patches": _rows(g("patch_calendar.csv")),
        "reagents": _rows(g("reagent_registry.csv")),
        "artifacts": _rows(g("artifact_catalogue.csv")),
        "editions": _rows(g("recipe_editions.csv")),
        "workshops": _rows(g("workshop_registry.csv")),
        "identity": _rows(g("smith_identity_events.csv")),
        "ledger": _rows(g("crafting_ledger.csv")),
        "acquisitions": _rows(g("reagent_acquisitions.csv")),
        "opening": _rows(g("vault_opening.csv")),
        "requisitions": json.loads((g("requisitions.json")).read_text(encoding="utf-8")),
        "charter": json.loads((g("season_charter.json")).read_text(encoding="utf-8")),
    }
    for p in corp["patches"]:
        p["opens_day"] = int(p["opens_day"])
        p["closes_day"] = int(p["closes_day"])
        p["ordinal"] = int(p["ordinal"])
    for r in corp["reagents"]:
        r["grade"] = int(r["grade"])
        r["scarce"] = int(r["scarce"])
    for a in corp["artifacts"]:
        a["tier"] = int(a["tier"])
        a["base_charge"] = int(a["base_charge"])
    for e in corp["editions"]:
        e["edition"] = int(e["edition"])
        e["units_per_craft"] = int(e["units_per_craft"])
    for w in corp["workshops"]:
        w["opened_day"] = int(w["opened_day"])
        w["charter_tier"] = int(w["charter_tier"])
    for ev in corp["identity"]:
        ev["day"] = int(ev["day"])
    for e in corp["ledger"]:
        e["day"] = int(e["day"])
        e["units"] = int(e["units"])
    for a in corp["acquisitions"]:
        a["day"] = int(a["day"])
        a["units"] = int(a["units"])
    for o in corp["opening"]:
        o["opening_units"] = int(o["opening_units"])
    return corp


# ------------------------------------------------------- stages 1..4, 9.. --


def _patch_by_day(patches: list[dict], day: int) -> dict | None:
    for p in patches:
        if p["opens_day"] <= day <= p["closes_day"]:
            return p
    return None


def canonical_smith(identity: list[dict], ref: str, day: int) -> str:
    cur = ref
    for _ in range(10):
        nxt = None
        best = -1
        for ev in identity:
            if ev["kind"] in ("rename", "merge") and ev["from_ref"] == cur and ev["day"] <= day:
                if ev["day"] > best:
                    best = ev["day"]
                    nxt = ev["to_ref"]
        if nxt is None or nxt == cur:
            return cur
        cur = nxt
    return cur


def is_retired(identity: list[dict], ref: str, day: int) -> bool:
    exits = [ev["day"] for ev in identity
             if ev["kind"] == "retire" and ev["day"] <= day
             and canonical_smith(identity, ev["from_ref"], day) == ref]
    if not exits:
        return False
    last_exit = max(exits)
    return not any(ev["kind"] == "register"
                   and canonical_smith(identity, ev["from_ref"], day) == ref
                   and last_exit < ev["day"] <= day for ev in identity)


def in_scope(w: dict, first: int, last: int) -> bool:
    if w["opened_day"] > first:
        return False
    closed = w["closed_day"]
    if closed not in ("", None) and int(closed) < last:
        return False
    return w["charter_tier"] >= 2


def edition_for(editions: list[dict], artifact_id: str, ordinal: int) -> list[dict] | None:
    hits = [
        e
        for e in editions
        if e["artifact_id"] == artifact_id
        and int(e["from_patch"][1:]) <= ordinal <= int(e["to_patch"][1:])
    ]
    if not hits:
        return None
    nums = {e["edition"] for e in hits}
    if len(nums) != 1:
        chosen = min(nums)
        hits = [e for e in hits if e["edition"] == chosen]
    return sorted(hits, key=lambda e: e["reagent_id"])


# ------------------------------------------------------------- settlement --


LAST_PASSES = 0


def credited_acquisitions(corp: dict) -> list[dict]:
    """Acquisitions recorded on a day the season calendar covers."""
    patches = sorted(corp["patches"], key=lambda p: p["ordinal"])
    first = patches[0]["opens_day"]
    last = patches[-1]["closes_day"]
    return [a for a in corp["acquisitions"] if first <= a["day"] <= last]


def settle(corp: dict, params: Params) -> dict:
    patches = sorted(corp["patches"], key=lambda p: p["ordinal"])
    first = patches[0]["opens_day"]
    last = patches[-1]["closes_day"]
    reagents = {r["reagent_id"]: r for r in corp["reagents"]}
    artifacts = {a["artifact_id"]: a for a in corp["artifacts"]}
    workshops = {w["workshop_id"]: w for w in corp["workshops"]}
    identity = sorted(corp["identity"], key=lambda e: (e["day"], e["event_id"]))
    charter = corp["charter"]
    fam_mult = charter["family_multiplier"]
    grade_step = int(charter["grade_step"])
    ceiling = int(charter["scarcity_ceiling"])
    tier_charge_cap = {int(k): int(v) for k, v in charter["tier_charge_cap"].items()}
    q = params.quantiser
    schedule = {int(k): v for k, v in RETURN_SCHEDULES[params.schedule].items()}

    scope = sorted(w for w in workshops if in_scope(workshops[w], first, last))
    scope_set = set(scope)
    # V9: a reagent is retired from the first day of the patch its registry names.
    patch_open = {p["patch_id"]: p["opens_day"] for p in patches}
    retired_from = {
        rid: patch_open[r["retired_patch"]]
        for rid, r in reagents.items()
        if r.get("retired_patch") and r["retired_patch"] in patch_open
    }
    guilds = sorted({workshops[w]["guild_id"] for w in scope})

    opening = {o["reagent_id"]: o["opening_units"] for o in corp["opening"]}
    for rid in reagents:
        opening.setdefault(rid, 0)
    acquired: dict[str, int] = {rid: 0 for rid in reagents}
    for a in credited_acquisitions(corp):
        acquired[a["reagent_id"]] = acquired.get(a["reagent_id"], 0) + a["units"]

    ledger = sorted(corp["ledger"], key=lambda e: (e["day"], e["entry_id"]))
    forge_index = {e["entry_id"]: e for e in ledger if e["op"] == "forge"}

    # stage 4 - governing edition per entry (E3 is the counterfactual)
    resolved: dict[str, list[dict] | None] = {}
    findings: list[dict] = []
    for e in ledger:
        if e["op"] == "salvage":
            src = forge_index.get(e["forge_ref"])
            if src is None:
                resolved[e["entry_id"]] = None
                findings.append(
                    {"entry_id": e["entry_id"], "code": "MISSING_FORGE_REF", "detail": e["forge_ref"]}
                )
                continue
            # E3: a salvage follows the edition in force on the forge day.
            day = src["day"]
        else:
            day = e["day"]
        p = _patch_by_day(patches, day)
        if p is None or e["artifact_id"] not in artifacts:
            resolved[e["entry_id"]] = None
            findings.append(
                {"entry_id": e["entry_id"], "code": "UNRESOLVED_EDITION", "detail": e["artifact_id"]}
            )
            continue
        bom = edition_for(corp["editions"], e["artifact_id"], p["ordinal"])
        if bom is None:
            resolved[e["entry_id"]] = None
            findings.append(
                {"entry_id": e["entry_id"], "code": "UNRESOLVED_EDITION", "detail": e["artifact_id"]}
            )
            continue
        resolved[e["entry_id"]] = bom

    # stage 5 - static eligibility (workshop scope and smith standing).
    # Both conditions are evaluated on the entry as filed, independently of one
    # another, of settlement state and of edition resolution, so an entry
    # carries every one that holds (N3).
    blocked: set[str] = set()
    for e in ledger:
        eid = e["entry_id"]
        if resolved.get(eid) is None:
            blocked.add(eid)
        hit = False
        if e["workshop_id"] not in scope_set:
            findings.append(
                {"entry_id": eid, "code": "OUT_OF_SCOPE_WORKSHOP", "detail": e["workshop_id"]}
            )
            hit = True
        canon0 = canonical_smith(identity, e["smith_ref"], e["day"])
        if is_retired(identity, canon0, e["day"]):
            findings.append({"entry_id": eid, "code": "RETIRED_SMITH", "detail": canon0})
            hit = True
        if hit:
            blocked.add(eid)

    static_findings = list(findings)

    # scarcity denominators (params.base axis)
    def scar_base(rid: str, consumed_all: dict[str, int]) -> int:
        if params.base == "opening":
            return opening.get(rid, 0)
        if params.base == "opening-plus-acquired":
            return opening.get(rid, 0) + acquired.get(rid, 0)
        if params.base == "consumed":
            return consumed_all.get(rid, 0)
        return acquired.get(rid, 0)

    def charge_of(entry: dict, bom: list[dict], idx: dict[str, int]) -> int:
        art = artifacts[entry["artifact_id"]]
        value = art["base_charge"]
        max_grade = max(reagents[b["reagent_id"]]["grade"] for b in bom)
        uplift = sum(idx.get(b["reagent_id"], 0) for b in bom if reagents[b["reagent_id"]]["scarce"])
        for op in params.order:
            if op == "F":
                value = quantise(value * int(fam_mult[art["family"]]), 100, q)
            elif op == "G":
                value = quantise(value * (100 + grade_step * max_grade), 100, q)
            else:
                value = quantise(value * (100 + uplift), 100, q)
        charge = value * entry["units"]
        smith = canonical_smith(identity, entry["smith_ref"], entry["day"])
        registrations = [ev["day"] for ev in identity
                         if ev["kind"] == "register" and ev["day"] <= entry["day"]
                         and canonical_smith(identity, ev["from_ref"], entry["day"]) == smith]
        if registrations:
            first_patch = _patch_by_day(patches, min(registrations))
            forge_patch = _patch_by_day(patches, entry["day"])
            if first_patch is not None and forge_patch is not None and first_patch["patch_id"] == forge_patch["patch_id"]:
                charge = quantise(charge * 80, 100, q)
        return charge

    def one_pass(idx: dict[str, int]) -> dict:
        stock = dict(opening)
        acq_by_day: dict[int, list[dict]] = {}
        for a in credited_acquisitions(corp):
            acq_by_day.setdefault(a["day"], []).append(a)
        cum: dict[str, int] = {w: 0 for w in scope}
        released: dict[str, int] = {w: 0 for w in scope}
        closed: set[str] = set()
        consumed: dict[str, int] = {rid: 0 for rid in reagents}
        returned: dict[str, int] = {rid: 0 for rid in reagents}
        consumed_all: dict[str, int] = {rid: 0 for rid in reagents}
        per_patch: dict[str, dict[str, dict[str, int]]] = {
            p["patch_id"]: {rid: {"acquired": 0, "returned": 0, "consumed": 0} for rid in reagents}
            for p in patches
        }
        for a in credited_acquisitions(corp):
            pid = a["patch_id"]
            if pid in per_patch:
                per_patch[pid][a["reagent_id"]]["acquired"] += a["units"]
        admitted_forges: list[dict] = []
        rec: dict[str, dict] = {}
        redeemed: set[str] = set()
        run_findings: list[dict] = []
        seen_days: set[int] = set()

        for e in ledger:
            day = e["day"]
            if day not in seen_days:
                for d in sorted(k for k in acq_by_day if k <= day and k not in seen_days):
                    for a in sorted(acq_by_day[d], key=lambda x: x["acq_id"]):
                        stock[a["reagent_id"]] = stock.get(a["reagent_id"], 0) + a["units"]
                    seen_days.add(d)
                seen_days.add(day)
            eid = e["entry_id"]
            bom = resolved.get(eid)
            state = {"admitted": False, "charge": 0, "code": None, "canonical": None}
            rec[eid] = state
            # I5: every smith on an entry is reported, settled or not.
            canon = canonical_smith(identity, e["smith_ref"], day)
            state["canonical"] = canon
            if bom is None or eid in blocked:
                state["code"] = "BLOCKED"
                continue
            pid = _patch_by_day(patches, day)["patch_id"]
            if e["op"] == "forge":
                need = {b["reagent_id"]: b["units_per_craft"] * e["units"] for b in bom}
                for rid, n in need.items():
                    consumed_all[rid] = consumed_all.get(rid, 0) + n
                # N3: the cap, the floor and a retired reagent are separate
                # conditions of a forge; it carries every one that holds, and
                # the cap closes the workshop whatever else refuses the forge.
                short = sorted(rid for rid, n in need.items() if stock.get(rid, 0) - n < 0)
                gone = sorted(rid for rid in need if rid in retired_from and day >= retired_from[rid])
                codes: list[tuple[str, str]] = []
                charge = 0
                if e["workshop_id"] in closed:
                    codes.append(("CAP_REACHED", e["workshop_id"]))
                else:
                    charge = charge_of(e, bom, idx)
                    cap = tier_charge_cap[workshops[e["workshop_id"]]["charter_tier"]]
                    if cum[e["workshop_id"]] - released[e["workshop_id"]] + charge > cap:
                        closed.add(e["workshop_id"])
                        codes.append(("CAP_REACHED", e["workshop_id"]))
                if short:
                    codes.append(("STOCK_FLOOR", short[0]))
                if gone:
                    codes.append(("RETIRED_REAGENT", gone[0]))
                if codes:
                    state["code"] = codes[0][0]
                    for code, detail in codes:
                        run_findings.append({"entry_id": eid, "code": code, "detail": detail})
                    continue
                for rid, n in need.items():
                    stock[rid] -= n
                    consumed[rid] += n
                    per_patch[pid][rid]["consumed"] += n
                cum[e["workshop_id"]] += charge
                state["admitted"] = True
                state["charge"] = charge
                state["flow"] = {"consumed": dict(need), "returned": {}}
                admitted_forges.append(e)
            else:
                src = forge_index[e["forge_ref"]]
                fam = artifacts[e["artifact_id"]]["family"]
                hist = [
                    f
                    for f in admitted_forges
                    if artifacts[f["artifact_id"]]["family"] == fam
                    and rec[f["entry_id"]]["canonical"] == canon
                    and f["day"] < day
                    and f["entry_id"] not in redeemed
                ]
                # S6: a forge already redeemed settles no further salvage.
                if src["entry_id"] in redeemed:
                    state["code"] = "SALVAGE_ALREADY_CREDITED"
                    run_findings.append({"entry_id": eid, "code": state["code"], "detail": src["entry_id"]})
                    continue
                window = hist[-3:]
                if src["entry_id"] not in {f["entry_id"] for f in window}:
                    state["code"] = "UNCREDITED_SALVAGE"
                    run_findings.append({"entry_id": eid, "code": state["code"], "detail": src["entry_id"]})
                    continue
                tier = artifacts[e["artifact_id"]]["tier"]
                rate = schedule[tier]
                gave: dict[str, int] = {}
                for b in bom:
                    rid = b["reagent_id"]
                    back = quantise(b["units_per_craft"] * src["units"] * rate, 100, q)
                    stock[rid] = stock.get(rid, 0) + back
                    returned[rid] += back
                    per_patch[pid][rid]["returned"] += back
                    gave[rid] = gave.get(rid, 0) + back
                state["admitted"] = True
                redeemed.add(src["entry_id"])
                released[src["workshop_id"]] += rec[src["entry_id"]]["charge"]
                state["flow"] = {"consumed": {}, "returned": gave}

        new_idx = {}
        for rid, r in reagents.items():
            if not r["scarce"]:
                continue
            base = scar_base(rid, consumed_all)
            if base <= 0:
                new_idx[rid] = 0
            else:
                new_idx[rid] = min(ceiling, quantise(100 * consumed[rid], base, q))
        return {
            "idx": new_idx,
            "stock": stock,
            "cum": cum,
            "closed": closed,
            "consumed": consumed,
            "returned": returned,
            "per_patch": per_patch,
            "rec": rec,
            "findings": run_findings,
            "scope": scope,
            "guilds": guilds,
        }

    scarce_ids = sorted(rid for rid, r in reagents.items() if r["scarce"])

    def iterate(seed_value: int) -> tuple[dict, int]:
        idx = {rid: seed_value for rid in scarce_ids}
        seen = [dict(idx)]
        for step in range(1, 400):
            res = one_pass(idx)
            nxt = res["idx"]
            if nxt == idx:
                return res, step
            idx = nxt
            if idx in seen:
                # 2-cycle or longer: take the join of the cycle members
                return one_pass(idx), step
            seen.append(dict(idx))
        return one_pass(idx), 400

    global LAST_PASSES
    low, low_steps = iterate(0)
    LAST_PASSES = low_steps
    high, _ = iterate(ceiling)
    if low["idx"] != high["idx"]:
        raise ValueError(f"scarcity fixpoint not unique: {low['idx']} vs {high['idx']}")
    final = one_pass(low["idx"])
    if final["idx"] != low["idx"]:
        raise ValueError("scarcity assignment is not stable")

    return _assemble(corp, params, final, low_steps, static_findings)


# --------------------------------------------------------------- assembly --


def _assemble(corp, params, st, low_steps, static_findings) -> dict:
    patches = sorted(corp["patches"], key=lambda p: p["ordinal"])
    reagents = {r["reagent_id"]: r for r in corp["reagents"]}
    artifacts = {a["artifact_id"]: a for a in corp["artifacts"]}
    workshops = {w["workshop_id"]: w for w in corp["workshops"]}
    charter = corp["charter"]
    ledger = sorted(corp["ledger"], key=lambda e: (e["day"], e["entry_id"]))
    scope = st["scope"]
    guilds = st["guilds"]
    rec = st["rec"]
    opening = {o["reagent_id"]: o["opening_units"] for o in corp["opening"]}
    for rid in reagents:
        opening.setdefault(rid, 0)
    acquired = {rid: 0 for rid in reagents}
    for a in credited_acquisitions(corp):
        acquired[a["reagent_id"]] += a["units"]

    findings = sorted(
        static_findings + st["findings"], key=lambda f: (f["entry_id"], f["code"])
    )
    seen_pairs = set()
    uniq = []
    for f in findings:
        key = (f["entry_id"], f["code"])
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        uniq.append(f)
    findings = uniq

    # allocation CSP
    alloc, alloc_total = _allocate(corp, st, scope, workshops)
    alloc_by_workshop: dict[str, int] = {}
    for r in corp["requisitions"]["requisitions"]:
        alloc_by_workshop[r["workshop_id"]] = alloc_by_workshop.get(r["workshop_id"], 0) + alloc.get(r["req_id"], 0)

    ws_rows = {}
    for wid in scope:
        w = workshops[wid]
        cap = int(charter["tier_charge_cap"][str(w["charter_tier"])])
        smiths: dict[str, dict] = {}
        flow: dict[str, dict[str, int]] = {}
        adm = rej = 0
        for e in ledger:
            if e["workshop_id"] != wid:
                continue
            state = rec.get(e["entry_id"], {})
            if not state:
                continue
            if state.get("admitted"):
                adm += 1
            elif state.get("code"):
                rej += 1
            canon = state.get("canonical")
            if canon is None:
                continue
            s = smiths.setdefault(
                canon,
                {"canonical_smith": canon, "admitted_forges": 0, "credited_salvages": 0, "charge_ember": 0},
            )
            if state.get("admitted"):
                if e["op"] == "forge":
                    s["admitted_forges"] += 1
                    s["charge_ember"] += state["charge"]
                else:
                    s["credited_salvages"] += 1
        ws_rows[wid] = {
            "workshop_id": wid,
            "guild_id": w["guild_id"],
            "charter_id": w["charter_id"],
            "charter_tier": w["charter_tier"],
            "entries_admitted": adm,
            "entries_rejected": rej,
            "charge_ember": st["cum"][wid],
            "cap_ember": cap,
            "cap_reached": wid in st["closed"],
            "allocated_units": alloc_by_workshop.get(wid, 0),
            "smiths": sorted(smiths.values(), key=lambda s: s["canonical_smith"]),
            "reagent_flow": _flow_rows(ledger, rec, corp, wid),
        }
        flow  # noqa

    guild_rows = {}
    for g in guilds:
        members = [w for w in scope if workshops[w]["guild_id"] == g]
        guild_rows[g] = {
            "guild_id": g,
            "workshops": members,
            "entries_admitted": sum(ws_rows[w]["entries_admitted"] for w in members),
            "charge_ember": sum(ws_rows[w]["charge_ember"] for w in members),
            "allocated_units": sum(ws_rows[w]["allocated_units"] for w in members),
            "reagent_flow": _merge_flow([ws_rows[w]["reagent_flow"] for w in members]),
        }

    vault = []
    residual_total = 0
    for rid in sorted(reagents):
        closing = opening[rid] + acquired[rid] + st["returned"][rid] - st["consumed"][rid]
        residual = opening[rid] + acquired[rid] + st["returned"][rid] - st["consumed"][rid] - closing
        residual_total += abs(residual)
        vault.append(
            {
                "reagent_id": rid,
                "grade": reagents[rid]["grade"],
                "scarce": bool(reagents[rid]["scarce"]),
                "opening_units": opening[rid],
                "acquired_units": acquired[rid],
                "returned_units": st["returned"][rid],
                "consumed_units": st["consumed"][rid],
                "closing_units": closing,
                "scarcity_index": st["idx"].get(rid, 0),
            }
        )

    patch_rows = []
    running = dict(opening)
    for p in patches:
        rows = []
        for rid in sorted(reagents):
            pp = st["per_patch"][p["patch_id"]][rid]
            op_units = running[rid]
            cl = op_units + pp["acquired"] + pp["returned"] - pp["consumed"]
            rows.append(
                {
                    "reagent_id": rid,
                    "opening_units": op_units,
                    "acquired_units": pp["acquired"],
                    "returned_units": pp["returned"],
                    "consumed_units": pp["consumed"],
                    "closing_units": cl,
                    "residual": op_units + pp["acquired"] + pp["returned"] - pp["consumed"] - cl,
                }
            )
            running[rid] = cl
        patch_rows.append(
            {
                "patch_id": p["patch_id"],
                "ordinal": p["ordinal"],
                "reagents": rows,
                "residual": sum(abs(r["residual"]) for r in rows),
            }
        )

    season_charge = sum(ws_rows[w]["charge_ember"] for w in scope)
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["code"]] = counts.get(f["code"], 0) + 1

    admitted = sum(1 for s in rec.values() if s.get("admitted"))
    credited = sum(
        1
        for e in ledger
        if e["op"] == "salvage" and rec.get(e["entry_id"], {}).get("admitted")
    )
    uncredited = counts.get("UNCREDITED_SALVAGE", 0)

    summary = {
        "season": {
            "first_day": patches[0]["opens_day"],
            "last_day": patches[-1]["closes_day"],
            "patch_count": len(patches),
        },
        "workshops_in_scope": scope,
        "guilds_in_scope": guilds,
        "entries_total": len(ledger),
        "entries_admitted": admitted,
        "entries_rejected": len(ledger) - admitted,
        "credited_salvages": credited,
        "uncredited_salvages": uncredited,
        "scarcity_index": {k: st["idx"][k] for k in sorted(st["idx"])},
        "season_charge_ember": season_charge,
        "allocated_units_total": alloc_total,
        "conservation_residual": residual_total,
    }

    out = {
        "summary.json": summary,
        "vault_audit.json": {"reagents": vault},
        "reconciliation.json": {
            "patches": patch_rows,
            "season_residual": sum(p["residual"] for p in patch_rows),
            "charge_by_workshop": {w: ws_rows[w]["charge_ember"] for w in scope},
            "charge_by_guild": {g: guild_rows[g]["charge_ember"] for g in guilds},
            "charge_total": season_charge,
        },
        "data_quality.json": {"findings": findings, "counts": {k: counts[k] for k in sorted(counts)}},
        "allocation.json": {
            "pool_units": int(charter["season_pool_units"]),
            "assignments": [
                {
                    "req_id": r["req_id"],
                    "workshop_id": r["workshop_id"],
                    "reagent_id": r["reagent_id"],
                    "allocated_units": r["allocated_units"],
                    "served": r["allocated_units"] > 0,
                }
                for r in _alloc_rows(corp, alloc)
            ],
            "allocated_total": alloc_total,
        },
    }
    for wid in scope:
        out[f"workshop_{wid}.json"] = ws_rows[wid]
    for g in guilds:
        out[f"guild_{g}.json"] = guild_rows[g]
    return out


def _flow_rows(ledger, rec, corp, wid) -> list[dict]:
    agg: dict[str, dict[str, int]] = {}
    for e in ledger:
        if e["workshop_id"] != wid:
            continue
        st = rec.get(e["entry_id"], {})
        flow = st.get("flow")
        if not flow:
            continue
        for rid, n in flow["consumed"].items():
            agg.setdefault(rid, {"consumed_units": 0, "returned_units": 0})["consumed_units"] += n
        for rid, n in flow["returned"].items():
            agg.setdefault(rid, {"consumed_units": 0, "returned_units": 0})["returned_units"] += n
    return [
        {
            "reagent_id": rid,
            "consumed_units": agg[rid]["consumed_units"],
            "returned_units": agg[rid]["returned_units"],
            "net_units": agg[rid]["consumed_units"] - agg[rid]["returned_units"],
        }
        for rid in sorted(agg)
    ]


def _merge_flow(flows: list[list[dict]]) -> list[dict]:
    agg: dict[str, dict[str, int]] = {}
    for f in flows:
        for row in f:
            a = agg.setdefault(row["reagent_id"], {"consumed_units": 0, "returned_units": 0})
            a["consumed_units"] += row["consumed_units"]
            a["returned_units"] += row["returned_units"]
    return [
        {
            "reagent_id": rid,
            "consumed_units": agg[rid]["consumed_units"],
            "returned_units": agg[rid]["returned_units"],
            "net_units": agg[rid]["consumed_units"] - agg[rid]["returned_units"],
        }
        for rid in sorted(agg)
    ]


def _alloc_rows(corp, alloc) -> list[dict]:
    reqs = sorted(corp["requisitions"]["requisitions"], key=lambda r: r["req_id"])
    return [
        {
            "req_id": r["req_id"],
            "workshop_id": r["workshop_id"],
            "reagent_id": r["reagent_id"],
            "allocated_units": alloc.get(r["req_id"], 0),
        }
        for r in reqs
    ]


def _allocate(corp, st, scope, workshops) -> tuple[dict[str, int], int]:
    """The Q1-Q8 plan as units per requisition identifier, and its total."""
    charter = corp["charter"]
    scarce_set = {r["reagent_id"] for r in corp["reagents"] if r["scarce"]}
    reqs = [
        r
        for r in sorted(corp["requisitions"]["requisitions"], key=lambda r: r["req_id"])
        if r["workshop_id"] in scope
    ]
    pool = int(charter["season_pool_units"])
    guild_cap = {k: int(v) for k, v in charter["guild_cap_units"].items()}
    tier_cap = {int(k): int(v) for k, v in charter["tier_unit_cap"].items()}
    # Q5 limits a scarce reagent by the vault's CLOSING balance for the season.
    opening = {o["reagent_id"]: o["opening_units"] for o in corp["opening"]}
    acquired = {r["reagent_id"]: 0 for r in corp["reagents"]}
    for a in credited_acquisitions(corp):
        acquired[a["reagent_id"]] += a["units"]
    stock = {
        rid: opening.get(rid, 0) + acquired.get(rid, 0)
        + st["returned"].get(rid, 0) - st["consumed"].get(rid, 0)
        for rid in acquired
    }

    # Q8 reads plans in ascending priority then identifier order, so the search
    # walks requisitions in that order and tries each grant from the largest
    # down to nothing: the first plan it meets at the greatest total is the
    # one Q8 prefers.  A plan is pruned once even its upper bound cannot beat
    # the best total already found.
    reqs.sort(key=lambda r: (int(r["priority"]), r["req_id"]))
    n = len(reqs)
    guild = [workshops[r["workshop_id"]]["guild_id"] for r in reqs]
    charter = [workshops[r["workshop_id"]]["charter_id"] for r in reqs]
    reagent = [r["reagent_id"] for r in reqs]
    options = []
    for r in reqs:
        hi = min(int(r["units_requested"]), tier_cap[workshops[r["workshop_id"]]["charter_tier"]])
        lo = int(r["min_units"])
        options.append(list(range(hi, lo - 1, -1)) + [0] if hi >= lo else [0])

    def bound(i: int, room: int, g_left: dict, used: set) -> int:
        per_charter: dict[str, int] = {}
        per_guild: dict[str, dict[str, int]] = {}
        for j in range(i, n):
            if charter[j] in used or options[j][0] == 0:
                continue
            top = options[j][0]
            if top > per_charter.get(charter[j], 0):
                per_charter[charter[j]] = top
            slot = per_guild.setdefault(guild[j], {})
            if top > slot.get(charter[j], 0):
                slot[charter[j]] = top
        by_guild = sum(min(g_left.get(g, 0), sum(v.values())) for g, v in per_guild.items())
        return min(room, sum(per_charter.values()), by_guild)

    best_total = -1
    best_plan: list[int] = []
    plan = [0] * n

    def search(i: int, total: int, room: int, g_left: dict, s_left: dict, used: set) -> None:
        nonlocal best_total, best_plan
        if i == n:
            if total > best_total:
                best_total = total
                best_plan = list(plan)
            return
        if total + bound(i, room, g_left, used) <= best_total:
            return
        for v in options[i]:
            if v:
                if charter[i] in used or v > room or v > g_left.get(guild[i], 0):
                    continue
                if reagent[i] in scarce_set and v > s_left.get(reagent[i], 0):
                    continue
                plan[i] = v
                g_left[guild[i]] = g_left.get(guild[i], 0) - v
                if reagent[i] in scarce_set:
                    s_left[reagent[i]] -= v
                used.add(charter[i])
                search(i + 1, total + v, room - v, g_left, s_left, used)
                used.discard(charter[i])
                if reagent[i] in scarce_set:
                    s_left[reagent[i]] += v
                g_left[guild[i]] += v
                plan[i] = 0
            else:
                search(i + 1, total, room, g_left, s_left, used)

    search(0, 0, pool, dict(guild_cap), {rid: stock.get(rid, 0) for rid in scarce_set}, set())
    if best_total <= 0:
        return {}, 0
    return {r["req_id"]: v for r, v in zip(reqs, best_plan)}, best_total


CANON = dict(indent=2, sort_keys=False, separators=(",", ": "), ensure_ascii=False)

FIELDS = {
    "patch_calendar.csv": ["patch_id", "opens_day", "closes_day", "ordinal"],
    "reagent_registry.csv": ["reagent_id", "grade", "family", "scarce", "retired_patch"],
    "artifact_catalogue.csv": [
        "artifact_id", "family", "tier", "base_charge", "introduced_patch"
    ],
    "recipe_editions.csv": [
        "recipe_id", "artifact_id", "edition", "from_patch", "to_patch",
        "reagent_id", "units_per_craft",
    ],
    "workshop_registry.csv": [
        "workshop_id", "charter_id", "guild_id", "opened_day", "closed_day", "charter_tier"
    ],
    "smith_identity_events.csv": ["event_id", "day", "kind", "from_ref", "to_ref"],
    "crafting_ledger.csv": [
        "entry_id", "patch_id", "day", "workshop_id", "smith_ref", "op",
        "artifact_id", "units", "forge_ref",
    ],
    "reagent_acquisitions.csv": ["acq_id", "patch_id", "day", "reagent_id", "units", "workshop_id"],
    "vault_opening.csv": ["reagent_id", "opening_units"],
}

ATTR = {
    "patch_calendar.csv": "patches",
    "reagent_registry.csv": "reagents",
    "artifact_catalogue.csv": "artifacts",
    "recipe_editions.csv": "editions",
    "workshop_registry.csv": "workshops",
    "smith_identity_events.csv": "identity",
    "crafting_ledger.csv": "ledger",
    "reagent_acquisitions.csv": "acquisitions",
    "vault_opening.csv": "opening",
}


def _csv_text(fields: list[str], rows: list[dict]) -> str:
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in fields})
    return buf.getvalue()


def write_corpus(corp: Corpus, out_dir: Path, prefix: str = "") -> list[str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fields in FIELDS.items():
        rows = getattr(corp, ATTR[name])
        (out / f"{prefix}{name}").write_text(_csv_text(fields, rows), encoding="utf-8")
        written.append(f"{prefix}{name}")
    (out / f"{prefix}requisitions.json").write_text(
        json.dumps(corp.requisitions, **CANON) + "\n", encoding="utf-8"
    )
    (out / f"{prefix}season_charter.json").write_text(
        json.dumps(corp.charter, **CANON) + "\n", encoding="utf-8"
    )
    written += [f"{prefix}requisitions.json", f"{prefix}season_charter.json"]
    return written


# --------------------------------------------------------------- harness ---

OUT = Path("/app/out")
PROGRAM = OUT / "settle_vault.py"

TRUE = Params("RS-C", "half-even", "GFS", "opening-plus-acquired")

RULINGS_NAME = "council_rulings.json"


# ------------------------------------------------------- council rulings --
#
# The council publishes no settled season. It publishes single worked cases,
# each the inputs of one reduction and the whole number it ruled, and the
# cases of a year leave exactly one draw of the register standing.  None of
# them is a figure of the season it ships with.


def _rule_charge(p: Params, case: dict) -> int:
    value = case["base_value"]
    factor = {"F": case["family_percent"], "G": case["grade_percent"], "S": case["scarcity_percent"]}
    for op in p.order:
        value = quantise(value * factor[op], 100, p.quantiser)
    return value


def _rule_return(p: Params, case: dict) -> int:
    rate = RETURN_SCHEDULES[p.schedule][case["tier"]]
    return quantise(case["committed_units"] * rate, 100, p.quantiser)


def _rule_index(p: Params, case: dict) -> int:
    base = {
        "opening": case["opening_units"],
        "opening-plus-acquired": case["opening_units"] + case["acquired_units"],
        "consumed": case["called_for_units"],
        "acquired": case["acquired_units"],
    }[p.base]
    if base <= 0:
        return 0
    return min(case["scarcity_ceiling"], quantise(100 * case["consumed_units"], base, p.quantiser))


_RULING_KINDS = (
    ("charge_rulings", "charge_ember", _rule_charge),
    ("return_rulings", "returned_units", _rule_return),
    ("scarcity_rulings", "scarcity_index", _rule_index),
)


def _ruling_case(kind: str, rng: Rng) -> dict:
    if kind == "charge_rulings":
        return {
            "base_value": 10 * rng.between(11, 300) + rng.below(10),
            "family_percent": rng.pick((115, 130, 145, 160)),
            "grade_percent": rng.pick((110, 120, 130)),
            "scarcity_percent": 100 + rng.between(1, 90),
        }
    if kind == "return_rulings":
        return {"tier": 1 + rng.below(3), "committed_units": rng.between(1, 40)}
    called = rng.between(40, 600)
    return {
        "opening_units": rng.between(30, 500),
        "acquired_units": rng.between(0, 400),
        "called_for_units": called,
        "consumed_units": rng.between(10, called),
        "scarcity_ceiling": SCARCITY_CEILING,
    }


def _rulings(params: Params) -> dict:
    """Cases that leave `params` as the only draw of the register.

    Greedy: each round adds the candidate case that leaves the fewest draws
    standing, so the published set is short and every case decides something.
    """
    rng = Rng(7919 * (all_params().index(params) + 1))
    standing = all_params()
    out: dict[str, list[dict]] = {kind: [] for kind, _f, _r in _RULING_KINDS}
    turn = 0
    while len(standing) > 1 or min(len(v) for v in out.values()) < 2:
        kind, field, rule = _RULING_KINDS[turn % len(_RULING_KINDS)]
        turn += 1
        best = None
        for _ in range(60):
            case = _ruling_case(kind, rng)
            case[field] = rule(params, case)
            if case in out[kind]:
                continue
            left = [p for p in standing if rule(p, case) == case[field]]
            if best is None or len(left) < len(best[1]):
                best = (case, left)
        if len(best[1]) < len(standing) or len(out[kind]) < 2:
            out[kind].append(best[0])
            standing = best[1]
        if turn > 300:
            raise AssertionError("no ruling set pins %r" % (params,))
    return out


def _draw_of(rulings: dict) -> list[Params]:
    return [
        p for p in all_params()
        if all(rule(p, case) == case[field]
               for kind, field, rule in _RULING_KINDS for case in rulings[kind])
    ]


# The rulebooks, invariants, finding codes, register and clerks' digest ship
# beside the records of every season, so every corpus built here carries them
# too, byte for byte as the agent's own data directory holds them.
RULEBOOK_TEXTS = {
    "clerks_digest.md": """\
# Clerks' digest

The vault clerks keep this page beside the ledger as a quick reference for the
desk. It is their shorthand for the points they are asked about most often.

- Entries are settled day by day, and within a day in ascending order of entry
  identifier.
- Units bought on a day can be drawn by forges filed that same day. Units a
  credited salvage returns can be drawn by entries settled after it.
- A salvage is credited when the forge it names is one of the three most recent
  forges of the same artifact family that the vault settled for the salvage's
  smith.
- A forge that has already been credited to a salvage is not credited again.
- A workshop that would pass its charge cap settles no further forge for the
  rest of the season.
""",
    "convention_register.md": """\
# Register of season conventions

Some conventions of a season are recorded with its charter. Others are fixed by
the guild council for a whole council year at once, and the council never
publishes the draw itself: it publishes this register of the conventions it may
draw from, and the rulings it handed down during the year. Every season draws
one entry from each table below, and the same draw governs every workshop, every
entry and every reagent of that season.

## Return schedules

A return schedule gives, for each artifact tier, the percentage of a source
forge's committed reagents that a settled salvage of that artifact returns.

| schedule | tier 1 | tier 2 | tier 3 |
| --- | --- | --- | --- |
| RS-A | 40 | 50 | 60 |
| RS-B | 45 | 55 | 65 |
| RS-C | 50 | 60 | 70 |
| RS-D | 35 | 50 | 65 |
| RS-E | 55 | 55 | 55 |
| RS-F | 30 | 45 | 60 |
| RS-G | 60 | 50 | 40 |

## Reduction conventions

Wherever a rule reduces a fractional quantity to a whole number, the season's
reduction convention decides the result. Write the fractional quantity as a
numerator over a positive denominator.

- `floor` - the greatest whole number that does not exceed the quantity.
- `ceil` - the least whole number that is not below the quantity.
- `half-up` - the nearer whole number; a quantity exactly halfway between two
  whole numbers goes to the greater of them.
- `half-down` - the nearer whole number; a quantity exactly halfway between two
  whole numbers goes to the lesser of them.
- `half-even` - the nearer whole number; a quantity exactly halfway between two
  whole numbers goes to whichever of them is even.

## Operator orders

The charge rulebook names three operators that a settled forge's charge passes
through: the family operator `F`, the grade operator `G` and the scarcity
operator `S`. A season's operator order is the sequence in which they are
applied, and the season's reduction convention is applied at each of the three
steps. The register holds all six sequences: `FGS`, `FSG`, `GFS`, `GSF`, `SFG`,
`SGF`.

## Scarcity references

The scarcity rulebook expresses a scarce reagent's settled consumption as a
percentage of a reference quantity of that reagent. The register holds these
candidate references:

- `opening` - the reagent's opening vault balance for the season.
- `opening-plus-acquired` - that opening balance together with every unit of the
  reagent the season acquired.
- `consumed` - the units of the reagent called for by every forge entry the
  season tests against the vault floor, whether or not that forge then settled.
  A forge refused for its workshop's scope, its smith's standing or an
  unresolved edition is never tested against the floor and calls for nothing
  here.
- `acquired` - the units of the reagent the season acquired.

A reference that stands at zero for a reagent leaves that reagent's scarcity
index at zero.

## The council's rulings

The rulings of the council year are published with the season's records. Each
ruling is one worked case taken from some season of that year: the quantities
that went into a single reduction, and the whole number the council ruled. A
ruling is not a figure of the season it is published with. Taken together, the
rulings of a year agree with exactly one draw of this register, and that draw
governs every season of the year.

- A charge ruling gives a forge's base value under H1, the family operator's
  percentage, the grade operator's percentage and the scarcity operator's
  percentage, and the charge the three operators gave that forge in the
  season's operator order.
- A return ruling gives the tier of a salvaged artifact and the units of one
  reagent line that its source forge committed (that line's units per craft
  times the units the forge committed), and the units that line returned.
- A scarcity ruling gives a scarce reagent's opening balance, the units the
  season acquired, the units called for by the forges tested against the floor,
  the reagent's settled consumption and the charter's scarcity ceiling, and the
  scarcity index the council ruled.
""",
    "finding_codes.md": """\
# Finding codes

A season records a finding against an entry whenever one of the conditions below
holds of that entry. The codes are listed in alphabetical order; that order
carries no meaning and no code ranks above another.

- `CAP_REACHED` - the entry is a forge that was not settled because its workshop
  had already reached its charge cap, or because settling it would have carried
  the workshop past that cap.
- `MISSING_FORGE_REF` - the entry is a salvage naming a forge entry the ledger
  does not hold.
- `OUT_OF_SCOPE_WORKSHOP` - the entry was filed against a workshop the season does
  not hold in scope.
- `RETIRED_REAGENT` - the entry is a forge whose governing recipe edition has
  a line for a reagent retired on or before the day of the entry.
- `RETIRED_SMITH` - the entry was filed by a smith whose canonical identity had
  been retired on or before the day of the entry.
- `SALVAGE_ALREADY_CREDITED` - the entry is a salvage naming a forge entry that an
  earlier salvage of the season has already been credited against.
- `STOCK_FLOOR` - the entry is a forge whose draw would have taken a reagent's
  vault balance below zero.
- `UNCREDITED_SALVAGE` - the entry is a salvage whose named forge does not fall in
  the salvage credit window.
- `UNRESOLVED_EDITION` - no recipe edition governs the entry.

Not every code is exercised by every season.

## What a finding carries

Every finding names the entry it concerns, the code of the condition, and one
further detail that says which thing the condition was about. Which thing that is
depends on the code:

- `CAP_REACHED` - the workshop that had reached its cap.
- `MISSING_FORGE_REF` - the forge reference the salvage named.
- `OUT_OF_SCOPE_WORKSHOP` - the workshop the entry was filed against.
- `RETIRED_REAGENT` - the retired reagent. Where the edition has lines for more
  than one retired reagent, the detail names the first of them in ascending
  reagent order.
- `RETIRED_SMITH` - the canonical identity that had been retired.
- `SALVAGE_ALREADY_CREDITED` - the forge entry that had already been redeemed.
- `STOCK_FLOOR` - the reagent whose balance the draw would have taken below zero.
  Where the draw would do that to more than one reagent, the detail names the
  first of them in ascending reagent order.
- `UNCREDITED_SALVAGE` - the forge entry the salvage named.
- `UNRESOLVED_EDITION` - the artifact the entry named.
""",
    "invariants.md": """\
# Invariants of a settled season

Every claim below holds of a correctly settled season. They are properties of the
result, not instructions for producing it.

## Terms

The rulebooks use these terms as defined here.

**Live forge entry.** A settled forge entry that no salvage has yet been credited
against.

## Properties

**N1. Settlement order.** A season settles its ledger in ascending order of day,
and within a day in ascending order of entry identifier. Every entry is
considered exactly once.

**N2. Referential closure.** Every salvage names a forge entry. A salvage naming
an entry the ledger does not hold settles nothing and is recorded against the
season's data quality.

**N3. Findings.** A finding names the entry it concerns, the code of the condition
it records, and the detail that code calls for. An entry carries a finding for
every condition that holds of it, so one entry may carry more than one. An entry
the season refuses for its workshop's scope, its smith's standing, a missing
forge or an unresolved edition carries a finding for each of those four that
holds of it and for nothing else: it is never tested against the charge cap, the
vault floor, a retired reagent, the credit window or the one-salvage-per-forge
rule. Every other forge is tested against the charge cap, the vault floor and
every retired reagent alike, and every other salvage against the
one-salvage-per-forge rule and, where that rule lets it through, the credit
window. The season's record of findings holds each entry and code pair once,
ordered by entry identifier and then by code, both ascending. The season also
reports how many findings it recorded under each code.

**N4. Conservation.** For every reagent and every patch of the season, that
reagent's opening balance for the patch, plus the units acquired in the patch,
plus the units returned in the patch, less the units consumed in the patch,
equals the reagent's closing balance for the patch. Each patch opens at the
previous patch's closing balance, and the first patch opens at the vault's
opening balance. The residual of that identity is zero for every reagent, for
every patch, and for the season taken as a whole.

**N5. Agreement.** A season's total charge equals the sum of the charges of the
workshops it holds in scope, and equals the sum of the charges of the guilds it
holds in scope. A guild's figures are the sums of the corresponding figures of
its in-scope workshops. The units a workshop receives are the units granted to
that workshop's requisition.

**N6. Membership.** A season reports on every workshop it holds in scope and on no
other, and on every guild that owns at least one in-scope workshop and on no
other. A workshop that settled nothing is still reported on.

**N7. Identity.** Every smith a settled season names is named by the canonical
identity its identity events give it, and a season's per-smith figures are
gathered under canonical identities.

**N8. Determinism.** Settling the same season twice yields the same records, byte
for byte.

**N9. Uniqueness.** A season has exactly one settled state.
""",
    "record_shapes.md": """\
# Record shapes

## The records a season is read from

A season is read from nine tables and three documents, all in one directory:
`patch_calendar.csv`, `reagent_registry.csv`, `artifact_catalogue.csv`,
`recipe_editions.csv`, `workshop_registry.csv`, `smith_identity_events.csv`,
`crafting_ledger.csv`, `reagent_acquisitions.csv`, `vault_opening.csv`,
`requisitions.json`, `season_charter.json` and `council_rulings.json`. The last
holds the council's rulings for the year as three lists, `charge_rulings`
(`base_value`, `family_percent`, `grade_percent`, `scarcity_percent`,
`charge_ember`), `return_rulings` (`tier`, `committed_units`, `returned_units`)
and `scarcity_rulings` (`opening_units`, `acquired_units`, `called_for_units`,
`consumed_units`, `scarcity_ceiling`, `scarcity_index`); the register of season
conventions says what each ruling records.

## How every settled record is written

Each record is one JSON object in UTF-8, indented by two spaces, with `","`
after every item but the last and no trailing whitespace on any line, `": "`
after each key, non-ASCII characters written as themselves, keys in exactly the
order listed below, and one newline after the closing brace. Every count, unit
and ember figure is a whole number. Grades, tiers, ordinals and every other
numeric column are written as JSON numbers. Values listed as true or false are
JSON booleans. Lists of rows are in the order
stated for them.

## summary.json

- `season`: an object with `first_day`, `last_day` and `patch_count`.
- `workshops_in_scope`: the in-scope workshop identifiers, ascending.
- `guilds_in_scope`: the identifiers of the guilds that own an in-scope
  workshop, ascending.
- `entries_total`: the number of ledger entries.
- `entries_admitted`: the number of entries that settled.
- `entries_rejected`: the number that did not.
- `credited_salvages`: the number of salvage entries that settled.
- `uncredited_salvages`: the number of `UNCREDITED_SALVAGE` findings.
- `scarcity_index`: an object from each scarce reagent, ascending, to its index.
- `season_charge_ember`: the season's total charge.
- `allocated_units_total`: the units granted across every requisition.
- `conservation_residual`: the sum over reagents of the absolute residual of
  the season's conservation identity.

## vault_audit.json

- `reagents`: one row for every reagent in the registry, ascending by
  identifier, each with `reagent_id`, `grade`, `scarce` (true or false),
  `opening_units`, `acquired_units`, `returned_units`, `consumed_units`,
  `closing_units` and `scarcity_index` (0 for a reagent the registry does not
  mark scarce).

## reconciliation.json

- `patches`: one row per patch in ordinal order, each with `patch_id`,
  `ordinal`, `reagents` and `residual`. `reagents` holds one row for every
  reagent, ascending, each with `reagent_id`, `opening_units`, `acquired_units`,
  `returned_units`, `consumed_units`, `closing_units` and `residual`. A patch's
  `residual` is the sum of the absolute residuals of its rows.
- `season_residual`: the sum of the patch residuals.
- `charge_by_workshop`: an object from each in-scope workshop, ascending, to its
  charge.
- `charge_by_guild`: an object from each in-scope guild, ascending, to its
  charge.
- `charge_total`: the season's total charge.

## data_quality.json

- `findings`: one row per entry and code pair, in the order N3 states, each
  with `entry_id`, `code` and `detail`.
- `counts`: an object from each code the season recorded at least once,
  ascending, to the number of findings under it.

## allocation.json

- `pool_units`: the season pool.
- `assignments`: one row for every requisition, ascending by identifier, each
  with `req_id`, `workshop_id`, `reagent_id`, `allocated_units` and `served`
  (true when the grant is above nothing).
- `allocated_total`: the units granted in all.

## Workshop reports

Each is named `workshop_` followed by the workshop identifier and `.json`.

- `workshop_id`, `guild_id`, `charter_id`, `charter_tier`.
- `entries_admitted` and `entries_rejected`: the entries filed against the
  workshop that settled and that did not.
- `charge_ember`: the sum of the charges of the forge entries the workshop
  settled.
- `cap_ember`: the charge cap of its charter tier.
- `cap_reached`: true when the workshop was closed under A4.
- `allocated_units`: the units granted to its requisitions.
- `smiths`: one row for every canonical smith the workshop reports under I5,
  ascending, each with `canonical_smith`, `admitted_forges`, `credited_salvages`
  and `charge_ember`.
- `reagent_flow`: one row for every reagent on a line of an entry the workshop
  settled, ascending, each with `reagent_id`, `consumed_units`,
  `returned_units` and `net_units` (consumed less returned).

## Guild reports

Each is named `guild_` followed by the guild identifier and `.json`.

- `guild_id`.
- `workshops`: the guild's in-scope workshops, ascending.
- `entries_admitted`, `charge_ember` and `allocated_units`: the sums over those
  workshops.
- `reagent_flow`: the workshops' `reagent_flow` rows added together per
  reagent, in the same shape and order.
""",
    "rulebook_admission.md": """\
# Rulebook: Admission

Applies to the Emberforge crafting season. This rulebook states which
workshops take part in a season and which ledger entries the season settles.
It states nothing about how a settled entry is valued.

## A1. Season window

A season spans the patches listed in the patch calendar. The season's first
day is the earliest day of its earliest patch; the season's last day is the
latest day of its latest patch.

## A2. Workshop participation

A workshop takes part in a season when all three of the following hold of its
registry row:

* it opened on or before the season's first day;
* it had not closed before the season's last day (a workshop with no closing
  day has not closed);
* its charter tier is 2 or higher.

A workshop that fails any one of these takes no part in the season. Ledger
entries filed against it are not settled, and it receives no report.

## A3. Standing of the acting smith

An entry filed by a smith whose canonical identity is retired as of the entry
day is not settled. Canonical identity and retirement are defined in the
identity rulebook.

## A4. Charge cap and closure

The season charter carries an ember charge cap for each charter tier. A
workshop accrues settled charge across the season. A forge entry is not
settled when settling it would carry that workshop's accrued settled charge
above the cap for its charter tier. When that happens the workshop is closed
for the remainder of the season and settles no further forge entry, whatever
its day, and whatever the entry would have cost.

The cap is judged on the charge a forge would carry if it settled.

A workshop that never reaches its cap is never closed by this rule.

## A5. Provisional charters

A workshop whose registry row carries a provisional charter flag accrues
against half its tier's charge cap, rounded down to a whole ember. No
workshop in this season carries a provisional charter flag.

## A6. Season extension

When the season charter names an extension patch, every tier's charge cap is
raised by that tier's extension allowance for the duration of the season. The
charter for this season names no extension patch.

## A7. Reporting obligation

Every workshop that takes part in the season is reported on, including a
workshop that settled nothing. A workshop that takes no part in the season is
not reported on.
""",
    "rulebook_charge.md": """\
# Rulebook: Charge

Applies to the Emberforge crafting season. This rulebook states how much ember
a settled forge entry costs. It states nothing about which entries are
settled.

Charge is carried in whole ember. Every operator below yields a whole number
of ember; the convention by which a fractional result is reduced to a whole
number is the same for every operator in the season and is not recorded in
this rulebook.

## H1. Base value

The base value of a forge entry is the base charge of the artifact it forges,
from the artifact catalogue.

## H2. Family operator

The family operator multiplies by the artifact family's multiplier, taken from
the season charter and read as a percentage.

## H3. Grade operator

The grade operator multiplies by one hundred plus the charter's grade step
times the highest reagent grade appearing in the entry's governing recipe
edition, read as a percentage. Reagent grade is a property of the reagent, not
of the edition line.

## H4. Scarcity operator

The scarcity operator multiplies by one hundred plus the sum of the scarcity
indices of those reagents in the entry's governing recipe edition that the
reagent registry marks scarce, read as a percentage. Reagents the registry
does not mark scarce contribute nothing to this sum, whatever their index
would be.

## H5. Composition

All three operators apply to the base value of every settled forge entry, each
exactly once, and each yields a whole number before the next applies. The order
in which they compose is fixed for the whole season but is not recorded in this
rulebook. The charge of the entry is the value the last operator yields,
multiplied by the number of units the entry forges.

## H6. Salvage entries

A settled salvage entry carries no charge of its own.

## H7. Apprentice relief

An entry filed by a smith within the patch in which that smith first
registered is charged at eighty percent of the charge H5 gives. No
entry in this season is filed by a smith inside that smith's registration
patch.
""",
    "rulebook_editions.md": """\
# Rulebook: Recipe editions

Applies to the Emberforge crafting season. This rulebook states which recipe
edition governs a ledger entry. The governing edition supplies the reagent
lines an entry commits and returns, and the reagent grades the charge rulebook
reads.

## E1. Edition windows

An artifact may be re-cut between patches. Each edition row names the artifact
and the patch ordinal from which that edition is in force. An edition is in
force from its own patch ordinal up to, but not including, the patch ordinal
of the next edition of the same artifact. The last edition of an artifact
stays in force to the end of the season.

Patch ordinals are the ordinals in the patch calendar. A day belongs to the
patch whose day range contains it.

## E2. Forge entries

A forge entry is governed by the edition in force on the day the forge entry
was filed.

## E3. Salvage entries

A salvage entry is governed by the edition in force on the day of the forge
entry it salvages.

## E4. Unresolvable entries

An entry that names an artifact absent from the artifact catalogue resolves to
no edition. An entry whose governing day falls outside every patch in the
calendar resolves to no edition. An entry that resolves to no edition is not
settled.

## E5. Recalled editions

An edition row marked recalled is treated as never having been in force, and
the edition that preceded it stays in force through the recalled edition's
window. No edition in this season is marked recalled.
""",
    "rulebook_identity.md": """\
# Rulebook: Smith identity

Applies to the Emberforge crafting season. Ledger entries name the handle a
smith was using when the entry was filed. Handles are not stable across a
season. This rulebook states how a handle resolves to the canonical smith that
the season reports on.

## I1. Identity events

The identity event log records four kinds of event, each with the day it takes
effect:

* **register** - a handle enters the roster as a smith in its own right.
* **rename** - the smith previously known by one handle is known by another
  from that day forward.
* **merge** - two handles are shown to have been the same person; the absorbed
  handle is the same smith as the surviving handle from that day forward.
* **retire** - the smith leaves the roster from that day forward.

## I2. Canonical identity

The canonical identity of a handle on a given day is obtained by applying the
rename and merge events that take effect on or before that day, following each
result in turn, until no further rename or merge applies to it. The result is
the canonical smith for that handle on that day.

A handle that no event has ever renamed or merged is its own canonical
identity.

## I3. Time dependence

Canonical identity is a function of the day as well as the handle. A handle
filed before a rename or a merge takes effect resolves to whatever it resolved
to on that earlier day, and a handle filed after resolves to the later result.

## I4. Retirement

A canonical identity is retired from the effective day of its retire event
onward, and not before. Retirement attaches to the canonical identity, not to
the handle: once an absorbed handle has merged into a surviving handle, a
retire event against the surviving handle retires entries filed under either.

## I5. Reporting

The season reports on canonical identities, never on handles. Every canonical
identity that appears on any entry filed against a participating workshop is
reported by that workshop, whether or not any of its entries were settled.

## I6. Reinstatement

A register event for a canonical identity that takes effect after that
identity's retire event reinstates the identity from the register day forward.
No identity in this season is reinstated.
""",
    "rulebook_requisitions.md": """\
# Rulebook - Requisitions

A season closes by granting reagent units against the requisitions its workshops
filed. Each requisition names one workshop and one reagent, and states the
smallest grant the workshop will accept, the number of units it asked for, and a
priority number.

**Q1. Eligibility.** A requisition is considered only when it names a workshop the
season holds in scope. A requisition naming any other workshop receives nothing
and takes no further part in the settlement, though the season still records its
grant of nothing.

**Q2. Shape of a grant.** A grant is a whole number of units of the reagent the
requisition names. It is either nothing at all, or it is at least the
requisition's stated minimum and no more than both the units it requested and the
unit ceiling the season charter records for the charter tier of the workshop that
filed it.

**Q3. Season pool.** The units granted across every requisition may not exceed the
season pool the charter records.

**Q4. Guild holding.** For each guild, the units granted to the requisitions of
that guild's in-scope workshops may not exceed the guild holding the charter
records for that guild.

**Q5. Vault balance.** For each reagent the reagent registry marks scarce, the
units granted for that reagent across every requisition may not exceed the
vault's closing balance of that reagent at the end of the season. A requisition
naming a reagent the registry does not mark scarce is not limited by the vault's
closing balance.

**Q6. Charter.** A charter holds at most one funded requisition. Where two
in-scope workshops share a charter, at most one of the two requisitions is
funded; the other receives nothing.

**Q7. Objective.** Among the funding plans that satisfy Q1 through Q6, the season
adopts one that grants the greatest total number of units.

**Q8. Preference.** Where more than one plan grants that greatest total, the
season prefers the plan that grants more units to the requisition carrying the
smallest priority number; where several requisitions carry the smallest priority
number, the one whose identifier sorts first among them; and so on through the
remaining requisitions taken in ascending order of priority number and then of
identifier. Exactly one plan survives this preference.

**Q9. Closed workshops.** A workshop that reached its charge cap during the season
remains eligible to receive a grant, and a workshop that settled no entry at all
remains eligible to receive a grant. Reaching the cap ends a workshop's
forging, not its charter.
""",
    "rulebook_salvage.md": """\
# Rulebook: Salvage

Applies to the Emberforge crafting season. A salvage entry breaks an artifact
back down and returns part of the reagents that were committed to make it.
This rulebook states when a salvage is credited and what it returns.

## S1. Source forge

Every salvage entry names the forge entry it salvages. A salvage that names an
entry absent from the ledger is not settled.

## S2. Credit window

A salvage is credited only when the forge entry it names is among the last
three live forge entries of the same artifact family settled for the same
canonical smith on days strictly before the salvage's own day. The canonical
smith is the one the salvage's own handle resolves to on the salvage day, and
the forge entries are read against that canonical smith whatever handles they
were filed under. Each artifact family carries its own window.

A salvage whose source forge falls outside that window is not settled and
returns nothing.

## S3. Return quantity

A credited salvage returns, for each reagent line of its governing recipe
edition, that line's units per craft multiplied by the number of units the
**source forge entry** committed, taken at the return rate for the
artifact's tier and reduced to whole units.

The return rate schedule assigns one rate to each artifact tier. The schedule
is fixed for the season but is not recorded in this rulebook.

## S4. Returned units re-enter the vault

Units returned by a credited salvage re-enter the vault on the salvage's day
and are available to entries settled after it. They are not available to
entries settled before it.

## S5. Salvage and the cap ledger

A salvage entry commits no reagents and cannot be blocked by a shortage of
stock. When a salvage is credited, the charge of its source forge entry leaves
the accrued settled charge of the workshop that filed that forge, for every
forge entry settled after the salvage. The charge stays in every charge figure
the season reports. A workshop already closed under A4 stays closed.

## S6. One salvage per forge

A forge entry may be credited to at most one salvage. Where the ledger holds
more than one salvage naming the same forge entry, the settlement reaches them
in the order it settles the ledger, and the first of them that the credit window
admits is credited. Every later salvage naming that forge entry is not settled,
whatever its own day and whatever the window would otherwise say of it.
A salvage refused under this rule is not tested against the credit window and
carries only `SALVAGE_ALREADY_CREDITED`.

A salvage the credit window turns away is not credited, and a later salvage
naming the same forge entry is judged on its own.
""",
    "rulebook_scarcity.md": """\
# Rulebook - The Reagent Vault and Scarcity

**V1. Opening.** The vault opens the season holding, for each reagent, the opening
balance recorded for that reagent.

**V2. Acquisitions.** An acquisition credits the vault with its units on the day it
records. Those units are available to entries filed on that day and on later
days, and are not available to entries filed earlier. An acquisition recorded for
a day the season calendar does not cover is not credited to the vault at all and
takes no part in the settlement.

**V3. Consumption.** A forge draws from the vault, for each reagent line of the
recipe edition that governs the forge, that line's units per craft multiplied by
the number of units the entry commits.

**V4. Floor.** The vault never holds a negative balance of any reagent. A forge
whose draw would take a reagent's balance below zero is not settled: it draws
nothing, it carries no charge, and it moves its workshop no closer to that
workshop's charge cap.

**V5. Scarcity index.** Every reagent the registry marks scarce carries one
scarcity index for the season. The index is the season's settled consumption of
that reagent, expressed as a percentage of a reference quantity of that reagent,
reduced to a whole number of percent, and then held at the scarcity ceiling the
charter records whenever it would otherwise stand above that ceiling. Which
quantity of a reagent serves as its reference is fixed for the season and is the
same choice for every scarce reagent, but it is not recorded in this rulebook.

**V6. Other reagents.** A reagent the registry does not mark scarce carries no
scarcity index and never contributes to the scarcity operator.

**V7. Returns are not consumption.** Units a settled salvage returns raise the
vault's balance. They are not consumption, and they never reduce a scarcity
index.

**V8. Settled state.** A season's scarcity indices and its settlement determine one
another: the indices are read off the settled season, and the settled season is
charged at those indices. Exactly one assignment of indices agrees with the
season that assignment produces, and the season is settled at that assignment.

**V9. Retired reagents.** A reagent whose registry row names a retired patch can
no longer be drawn from the vault from the first day of that patch onward. A
forge filed on or after that day whose governing recipe edition has a line for
that reagent is not settled: it draws nothing, it carries no charge, and it
moves its workshop no closer to that workshop's charge cap.
Retirement stops draws only: units of a retired reagent that a credited salvage
returns still re-enter the vault.
""",
}

_CACHE: dict = {}


def _canon(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=False, separators=(",", ": "),
                      ensure_ascii=False) + "\n"


def _build_corpus_dir(out_dir: Path, params: Params = TRUE, mutate="visible",
                      main_seed: int = SAMPLE_SEED) -> None:
    """Write a complete corpus, publishing the council's rulings for `params`."""
    visible = mutate == "visible"
    if mutate == "visible":
        mutate = _plant_visible
    out_dir.mkdir(parents=True, exist_ok=True)
    main = build_corpus(main_seed, "main")
    if mutate is not None:
        mutate(main, params)
    write_corpus(main, out_dir, "")
    for name, text in RULEBOOK_TEXTS.items():
        if not visible:
            text = text.replace("No identity in this season is reinstated.\n", "")
            text = text.replace("No\nentry in this season is filed by a smith inside that smith's registration\npatch.\n", "")
        (out_dir / name).write_text(text, encoding="utf-8")
    (out_dir / RULINGS_NAME).write_text(_canon(_rulings(params)), encoding="utf-8")


def _write_corpus(path: Path) -> None:
    _build_corpus_dir(Path(path))


# The delivered programme is hostile input.  Grading runs it as an unprivileged
# user in its own process group, so it cannot read the answer key under /tests,
# cannot touch the verifier's log directory, and cannot leave a child behind
# that outlives the run and rewrites the score.
SANDBOX_UID = 4001
SANDBOX_GID = 4001


def _running_as_root() -> bool:
    return os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() == 0


def _drop_privileges(command: list[str]) -> list[str]:
    if not _running_as_root():
        return command
    setpriv = shutil.which("setpriv")
    if setpriv is None:
        raise AssertionError(
            "the verifier image is missing setpriv, so agent code cannot be "
            "confined; grading refuses to execute it as root"
        )
    return [
        setpriv,
        "--reuid=%d" % SANDBOX_UID,
        "--regid=%d" % SANDBOX_GID,
        "--clear-groups",
        "--",
    ] + command


def _open_to_sandbox(path: Path, read_only: bool = False) -> None:
    """Let the unprivileged user reach a directory the grader made.

    A corpus is opened read-only, so the program can read its input but never
    rewrite it; only an output directory is opened for writing.
    """
    if not _running_as_root():
        return
    dir_mode, file_mode = (0o755, 0o644) if read_only else (0o777, 0o666)
    for current, dirnames, filenames in os.walk(path):
        os.chmod(current, dir_mode)
        for name in filenames:
            try:
                os.chmod(os.path.join(current, name), file_mode)
            except OSError:
                pass
    os.chmod(path, dir_mode)
    os.chmod(Path(path).parent, 0o711)


def _kill_sandbox_processes() -> None:
    """SIGKILL every process the sandbox account still owns.

    A child that called setsid() has left the run's process group, so the
    group kill misses it; this sweep does not.
    """
    if not _running_as_root() or not Path("/proc").is_dir():
        return
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / "status").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # the process exited while the sweep ran
        uid_line = next((ln for ln in status.splitlines() if ln.startswith("Uid:")), "")
        fields = uid_line.split()
        if len(fields) > 1 and fields[1] == str(SANDBOX_UID):
            try:
                os.kill(int(entry.name), signal.SIGKILL)
            except OSError:
                continue  # already gone


def _end_group(proc: subprocess.Popen) -> None:
    """Kill the whole process group so nothing the agent spawned survives."""
    if os.name != "posix":
        if proc.poll() is None:
            proc.kill()
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
    _kill_sandbox_processes()


def _stage_program() -> Path:
    """A world-readable copy of the delivered program in a folder the grader made.

    An editor saves the agent's file at mode 0600, which the sandbox account
    cannot open, so every run executes this copy instead of the original.
    """
    stage = Path(tempfile.mkdtemp(prefix="emberforge_program_"))
    staged = stage / "settle_vault.py"
    shutil.copyfile(PROGRAM, staged)
    os.chmod(staged, 0o644)
    os.chmod(stage, 0o755)
    return staged


def _run_delivered(data_dir: Path, out_dir: Path, pass_dirs: bool = True) -> None:
    if not PROGRAM.is_file():
        raise AssertionError("no settlement program was delivered")
    out_dir.mkdir(parents=True, exist_ok=True)
    _open_to_sandbox(Path(data_dir), read_only=True)
    _open_to_sandbox(Path(out_dir))
    args = [str(data_dir), str(out_dir)] if pass_dirs else []
    staged = _stage_program()
    command = _drop_privileges([sys.executable, str(staged)] + args)
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=(os.name == "posix"),
        )
        try:
            out, err = proc.communicate(timeout=_AGENT_TIMEOUT)
        except subprocess.TimeoutExpired:
            _end_group(proc)
            proc.communicate()
            raise AssertionError("delivered program did not finish on %s" % (data_dir,))
        finally:
            _end_group(proc)
    finally:
        shutil.rmtree(staged.parent, ignore_errors=True)
    if proc.returncode != 0:
        raise AssertionError(
            "delivered program failed on %s: %s"
            % (data_dir, (err or out or "")[-800:])
        )


# --------------------------------------------------------------- mutations --


def _mut_priority_tie(main, params):
    # RQ01 and RQ04 share charter CH-01 and both carry priority 1, so Q8 breaks
    # the tie by identifier; giving RQ01 the larger number hands CH-01 to RQ04.
    reqs = main.requisitions["requisitions"]
    reqs[0]["priority"] = reqs[-1]["priority"] + 1


def _mut_cap_push(main, params):
    main.charter["tier_charge_cap"]["3"] = 50000
    main.charter["tier_charge_cap"]["2"] = 22000


def _mut_partition(main, params):
    drop = ("slagmoor", "verdigris")
    for w in main.workshops:
        if w["workshop_id"] in drop:
            w["charter_tier"] = 1
    main.requisitions["requisitions"] = [
        r for r in main.requisitions["requisitions"] if r["workshop_id"] not in drop
    ]


def _mut_temporal(main, params):
    patches = sorted(main.patches, key=lambda p: p["ordinal"])
    last = patches[-1]["closes_day"]
    main.acquisitions[3]["day"] = last + 4
    order = [p["patch_id"] for p in patches]
    later = [
        e for e in main.editions
        if int(e["edition"]) > 1 and order.index(e["from_patch"]) > 1
    ]
    if later:
        target = sorted({e["artifact_id"] for e in later})[0]
        for e in main.editions:
            if e["artifact_id"] != target:
                continue
            if int(e["edition"]) > 1:
                e["from_patch"] = order[order.index(e["from_patch"]) - 1]
            else:
                e["to_patch"] = order[order.index(e["to_patch"]) - 1]


def _mut_identity(main, params):
    handles = sorted({e["smith_ref"] for e in main.ledger})
    a, b, c = handles[0], handles[1], handles[2]
    day = sorted(main.patches, key=lambda p: p["ordinal"])[1]["opens_day"]
    main.identity.append(
        {"event_id": "IDZ1", "day": day, "kind": "merge", "from_ref": a, "to_ref": b}
    )
    main.identity.append(
        {"event_id": "IDZ2", "day": day + 1, "kind": "merge", "from_ref": b, "to_ref": c}
    )


def _mut_nonapplying(main, params):
    reag = sorted(main.reagents, key=lambda r: r["reagent_id"])
    plain = [r["reagent_id"] for r in reag if not r["scarce"]]
    if plain:
        main.requisitions["requisitions"][1]["reagent_id"] = plain[0]
    scarce = [r["reagent_id"] for r in reag if r["scarce"]]
    for o in main.opening:
        if o["reagent_id"] == scarce[0]:
            o["opening_units"] = 1
    salv = [e for e in main.ledger if e["op"] == "salvage"]
    if salv:
        salv[0]["forge_ref"] = "E99999"
    _trigger_quiet_rules(main)


def _trigger_quiet_rules(main):
    """Build the situations the season proper never creates, one per rule.

    Each edit below is there so that an engine breaking exactly that rule
    settles this corpus differently from a correct one.
    """
    first = min(p["opens_day"] for p in main.patches)
    ws = {w["workshop_id"]: w for w in main.workshops}
    # A2: one workshop fails only its opening day, another only its closing day.
    ws["brackenvault"].update(charter_tier=2, closed_day="")
    ws["quenchspar"].update(charter_tier=3, opened_day=first - 10)
    # A2 at its edges: a workshop opened on the first day itself and one closed
    # on the last day itself both still take part.
    last = max(p["closes_day"] for p in main.patches)
    inside = sorted(k for k, w in ws.items() if _in_scope(w, first, last))
    ws[inside[0]]["opened_day"] = first
    ws[inside[1]]["closed_day"] = last
    reqs = {r["req_id"]: r for r in main.requisitions["requisitions"]}
    # Q2 tier unit ceiling, Q3 season pool and Q5 (a non-scarce reagent whose
    # closing balance is below the grant) all bind on this plan.
    reqs["RQ02"].update(units_requested=24, priority=1, reagent_id="R06")
    reqs["RQ01"]["priority"] = 3
    for o in main.opening:
        if o["reagent_id"] == "R06":
            o["opening_units"] = 148
    main.charter["season_pool_units"] = 26
    # Q1: a requisition from an out-of-scope workshop that Q8 would otherwise fund.
    main.requisitions["requisitions"].append(
        {"req_id": "RQ05", "workshop_id": "brackenvault", "reagent_id": "R05",
         "priority": 0, "min_units": 6, "units_requested": 18}
    )
    # I4: retire the surviving handle of the first merge the day after it.
    merge = sorted(
        (e for e in main.identity if e["kind"] == "merge"), key=lambda e: (e["day"], e["event_id"])
    )[0]
    main.identity.append(
        {"event_id": "IDZ9", "day": merge["day"] + 1, "kind": "retire",
         "from_ref": merge["to_ref"], "to_ref": ""}
    )
    by_id = {e["entry_id"]: e for e in main.ledger}
    # V2: an acquisition on the very day of a forge that needs it.
    forge = by_id["L0117"]
    main.acquisitions.append(
        {"acq_id": "AQ9001", "patch_id": forge["patch_id"], "day": forge["day"],
         "reagent_id": "R04", "units": 200, "workshop_id": forge["workshop_id"]}
    )
    # S2: a salvage filed on the same day as the forge it names.
    same_day = dict(by_id["L0061"])
    same_day.update(entry_id="L0901", op="salvage", forge_ref="L0061")
    # STOCK_FLOOR detail: a forge short on more than one reagent.
    heavy = dict(by_id["L0246"])
    heavy.update(entry_id="L0902", units=999)
    main.ledger += [same_day, heavy]
    # N1: the ledger is written out of settlement order.
    main.ledger.reverse()


MUTATIONS = {
    "priority_tie": _mut_priority_tie,
    "cap_push": _mut_cap_push,
    "partition": _mut_partition,
    "temporal": _mut_temporal,
    "identity": _mut_identity,
    "nonapplying": _mut_nonapplying,
}


# ------------------------------------------------------ plants and seasons --
#
# The forge_* seasons are reseeded hidden seasons graded one whole document per
# check.  The iso_* and mut_* seasons each read one documented rule on an
# otherwise open season (no cap and no floor in reach unless the rule is A4).

BULK_UNITS = 999

def _ordered_patches(main) -> list[dict]:
    return sorted(main.patches, key=lambda p: p["ordinal"])


def _scope_of(main) -> list[str]:
    patches = _ordered_patches(main)
    first, last = patches[0]["opens_day"], patches[-1]["closes_day"]
    return [w["workshop_id"] for w in main.workshops if _in_scope(w, first, last)]


def _abundant_stock(main) -> None:
    """V4 never binds: every reagent opens far above any draw."""
    for o in main.opening:
        o["opening_units"] = 50000


def _caps_out_of_reach(main) -> None:
    """A4 never binds: no workshop can reach its cap."""
    main.charter["tier_charge_cap"] = {"1": 0, "2": 10 ** 9, "3": 10 ** 9}


def _retire(main, reagent_id: str, patch_rank: int) -> None:
    patch_id = _ordered_patches(main)[patch_rank]["patch_id"]
    for r in main.reagents:
        if r["reagent_id"] == reagent_id:
            r["retired_patch"] = patch_id


def _most_used_plain(main) -> str:
    scarce = {r["reagent_id"] for r in main.reagents if r["scarce"]}
    counts: dict[str, int] = {}
    for e in main.editions:
        if e["reagent_id"] not in scarce:
            counts[e["reagent_id"]] = counts.get(e["reagent_id"], 0) + 1
    return sorted(counts, key=lambda rid: (-counts[rid], rid))[0]


def _bulk_order(main, workshop_rank: int, patch_rank: int, needs: str | None = None,
                entry_id: str = "L0950") -> None:
    """Copy one ordinary forge of a workshop as a bulk order of BULK_UNITS units.

    The copy is filed the same day by the same smith, so it settles nothing
    but its own refusal: its charge is past any cap and its draw past any
    stock the season holds, unless the season's stock is abundant.
    """
    patch = _ordered_patches(main)[patch_rank]
    wid = _scope_of(main)[workshop_rank]
    artifacts = {a["artifact_id"] for a in main.artifacts}
    identity = sorted(main.identity, key=lambda ev: (ev["day"], ev["event_id"]))
    for e in sorted(main.ledger, key=lambda x: (x["day"], x["entry_id"])):
        if e["op"] != "forge" or e["workshop_id"] != wid or e["artifact_id"] not in artifacts:
            continue
        if not patch["opens_day"] <= e["day"] <= patch["closes_day"]:
            continue
        if is_retired(identity, canonical_smith(identity, e["smith_ref"], e["day"]), e["day"]):
            continue
        bom = edition_for(main.editions, e["artifact_id"], patch["ordinal"])
        if bom is None or (needs is not None and needs not in {b["reagent_id"] for b in bom}):
            continue
        bulk = dict(e)
        bulk.update(entry_id=entry_id, units=BULK_UNITS)
        main.ledger.append(bulk)
        return
    raise AssertionError("no forge to copy as a bulk order at %s in %s" % (wid, patch["patch_id"]))


def _set_caps(main, cap2: int, cap3: int) -> None:
    """Caps low enough that closures happen, and when they happen follows the draw."""
    main.charter["tier_charge_cap"] = {"1": 0, "2": cap2, "3": cap3}


def _hold_to_returns(main, reagent_id: str) -> None:
    """Leave a reagent's closing balance at exactly what salvage returns of it.

    Caps are put out of reach and every other reagent is abundant, so every
    forge the season tests settles.  The held reagent is never acquired and
    opens at exactly what those forges draw of it, so it is never short, and
    its closing balance (the Q5 limit) is the units salvages return, which the
    draw's return schedule and reduction convention decide.
    """
    _caps_out_of_reach(main)
    _abundant_stock(main)
    patches = _ordered_patches(main)
    first, last = patches[0]["opens_day"], patches[-1]["closes_day"]
    scope = {w["workshop_id"] for w in main.workshops if _in_scope(w, first, last)}
    artifacts = {a["artifact_id"] for a in main.artifacts}
    identity = sorted(main.identity, key=lambda ev: (ev["day"], ev["event_id"]))
    need = 0
    for e in main.ledger:
        if e["op"] != "forge" or e["workshop_id"] not in scope or e["artifact_id"] not in artifacts:
            continue
        if is_retired(identity, canonical_smith(identity, e["smith_ref"], e["day"]), e["day"]):
            continue
        p = _patch_by_day(patches, e["day"])
        bom = edition_for(main.editions, e["artifact_id"], p["ordinal"]) if p else None
        for b in bom or ():
            if b["reagent_id"] == reagent_id:
                need += b["units_per_craft"] * e["units"]
    for o in main.opening:
        if o["reagent_id"] == reagent_id:
            o["opening_units"] = need
    main.acquisitions = [a for a in main.acquisitions if a["reagent_id"] != reagent_id]


def _lever_ladder(n: int, pool: int, guild_cap: int, spread: int):
    """LV-EF-4: n requisitions on n workshops; pairs share a charter (Q6).

    A third of them name one scarce reagent held to its salvage returns, so
    the Q5 limit binds and follows the draw.
    """
    def mutate(main, params):
        rng = Rng(CHALLENGE_SEED * 1000 + n)
        first = _ordered_patches(main)[0]["opens_day"]
        scarce = sorted(r["reagent_id"] for r in main.reagents if r["scarce"])
        plain = sorted(r["reagent_id"] for r in main.reagents if not r["scarce"])
        held = scarce[0]
        _hold_to_returns(main, held)
        guilds = ["ashen_compact", "tidebound_league"]
        reqs = []
        for j in range(n):
            wid = "hall_%02d" % (j + 1)
            charter = "CH-%02d" % (20 + j // 2) if j < n // 2 else "CH-%02d" % (40 + j)
            main.workshops.append(
                {"workshop_id": wid, "charter_id": charter, "guild_id": guilds[j % 2],
                 "opened_day": first - 30, "closed_day": "", "charter_tier": 3 if j % 3 == 0 else 2}
            )
            reagent = held if j % 3 == 1 else plain[rng.below(len(plain))]
            low = 6 + rng.below(5)
            reqs.append(
                {"req_id": "RQ%02d" % (j + 1), "workshop_id": wid, "reagent_id": reagent,
                 "priority": 1 + rng.below(4), "min_units": low,
                 "units_requested": low + rng.below(spread + 1)}
            )
        main.requisitions["requisitions"] = reqs
        main.charter["season_pool_units"] = pool
        main.charter["guild_cap_units"] = {g: guild_cap for g in guilds}
    return mutate


def _as_corp(main) -> dict:
    """The settle() input for a corpus held in memory, before it is written."""
    corp = {name: copy.deepcopy(getattr(main, name)) for name in ATTR.values()}
    corp["requisitions"] = copy.deepcopy(main.requisitions)
    corp["charter"] = copy.deepcopy(main.charter)
    return corp


def _retire_pair(main, patch_rank: int) -> str:
    """Retire the most used plain reagent and a plain reagent sharing an edition with it."""
    rid = _most_used_plain(main)
    scarce = {r["reagent_id"] for r in main.reagents if r["scarce"]}
    ordinal = _ordered_patches(main)[patch_rank]["ordinal"]
    partners = sorted({
        b["reagent_id"]
        for e in main.editions
        if e["reagent_id"] == rid and int(e["to_patch"][1:]) >= ordinal
        for b in main.editions
        if b["recipe_id"] == e["recipe_id"] and b["edition"] == e["edition"]
        and b["reagent_id"] not in scarce and b["reagent_id"] != rid
    })
    if not partners:
        raise AssertionError("no plain reagent shares an edition with %s" % rid)
    _retire(main, rid, patch_rank)
    _retire(main, partners[0], patch_rank)
    return rid


def _same_day_window(main, params, needs: str | None = None, finalize=None) -> None:
    """S2 boundary: a salvage of the oldest of three forges settled before its day,
    filed after a forge of the same family that settles earlier on that same day.

    Strictly before the salvage's day, its source is in the window and the
    salvage is credited; a window that also counted the same-day forge would
    hold the later three and turn it away.  The block is placed where every
    entry of it settles, which the settled season confirms.
    """
    scarce = {r["reagent_id"] for r in main.reagents if r["scarce"]}
    patches = _ordered_patches(main)
    named = {ev["from_ref"] for ev in main.identity} | {ev["to_ref"] for ev in main.identity}
    smith = sorted({e["smith_ref"] for e in main.ledger} - named)[0]
    nxt = 1 + max(int(e["entry_id"][1:]) for e in main.ledger if int(e["entry_id"][1:]) < 900)
    eids = ["L%04d" % (nxt + k) for k in range(5)]
    for patch in patches[1:-1]:
        day = patch["opens_day"]
        for wid in _scope_of(main):
            for art in sorted(main.artifacts, key=lambda a: a["artifact_id"]):
                bom = edition_for(main.editions, art["artifact_id"], patch["ordinal"])
                if bom is None:
                    continue
                lines = {b["reagent_id"] for b in bom}
                if (needs is not None and needs not in lines) or not lines & scarce:
                    continue
                block = [
                    (eids[0], day + 2, "forge", 3, ""),
                    (eids[1], day + 4, "forge", 1, ""),
                    (eids[2], day + 9, "forge", 2, ""),
                    (eids[3], day + 13, "forge", 1, ""),
                    (eids[4], day + 13, "salvage", 3, eids[0]),
                ]
                ids = {b[0] for b in block}
                main.ledger += [
                    {"entry_id": eid, "patch_id": patch["patch_id"], "day": d,
                     "workshop_id": wid, "smith_ref": smith, "op": op,
                     "artifact_id": art["artifact_id"], "units": units, "forge_ref": ref}
                    for eid, d, op, units, ref in block
                ]
                if finalize is not None:
                    finalize(main)
                try:
                    res = settle(_as_corp(main), params)
                except ValueError:
                    res = None  # no stable scarcity assignment here; try the next place
                if res is not None and not ids & {
                    f["entry_id"] for f in res["data_quality.json"]["findings"]
                }:
                    return
                main.ledger = [e for e in main.ledger if e["entry_id"] not in ids]
                if finalize is not None:
                    finalize(main)
    raise AssertionError("no place settles the same-day window block")


def _live_window(main, params, needs: str | None = None, finalize=None) -> None:
    """S2 over live forge entries: four forges of one family for one smith, a
    credited salvage of the third, then a salvage of the first.

    The redeemed third no longer holds a place, so the first is among the
    last three live forges and its salvage is credited; a window over every
    settled forge would hold the later three and turn it away.  The block is
    placed where every entry of it settles, which the settled season confirms.
    """
    scarce = {r["reagent_id"] for r in main.reagents if r["scarce"]}
    patches = _ordered_patches(main)
    named = {ev["from_ref"] for ev in main.identity} | {ev["to_ref"] for ev in main.identity}
    smith = sorted({e["smith_ref"] for e in main.ledger} - named)[1]
    nxt = 1 + max(int(e["entry_id"][1:]) for e in main.ledger if int(e["entry_id"][1:]) < 900)
    eids = ["L%04d" % (nxt + k) for k in range(6)]
    for patch in patches[1:-1]:
        day = patch["opens_day"]
        for wid in _scope_of(main):
            for art in sorted(main.artifacts, key=lambda a: a["artifact_id"]):
                bom = edition_for(main.editions, art["artifact_id"], patch["ordinal"])
                if bom is None:
                    continue
                lines = {b["reagent_id"] for b in bom}
                if (needs is not None and needs not in lines) or not lines & scarce:
                    continue
                block = [
                    (eids[0], day + 1, "forge", 4, ""),
                    (eids[1], day + 2, "forge", 1, ""),
                    (eids[2], day + 3, "forge", 1, ""),
                    (eids[3], day + 5, "forge", 1, ""),
                    (eids[4], day + 7, "salvage", 1, eids[2]),
                    (eids[5], day + 9, "salvage", 4, eids[0]),
                ]
                ids = {b[0] for b in block}
                main.ledger += [
                    {"entry_id": eid, "patch_id": patch["patch_id"], "day": d,
                     "workshop_id": wid, "smith_ref": smith, "op": op,
                     "artifact_id": art["artifact_id"], "units": units, "forge_ref": ref}
                    for eid, d, op, units, ref in block
                ]
                if finalize is not None:
                    finalize(main)
                try:
                    res = settle(_as_corp(main), params)
                except ValueError:
                    res = None  # no stable scarcity assignment here; try the next place
                if res is not None and not ids & {
                    f["entry_id"] for f in res["data_quality.json"]["findings"]
                }:
                    return
                main.ledger = [e for e in main.ledger if e["entry_id"] not in ids]
                if finalize is not None:
                    finalize(main)
    raise AssertionError("no place settles the live window block")


def _plant_visible(main, params) -> None:
    """The season the agent receives: one retired reagent, one bulk order and
    the same-day window boundary."""
    _retire(main, "R14", 4)
    _bulk_order(main, 1, 1, entry_id="L0305")
    _same_day_window(main, params)
    main.ledger.sort(key=lambda e: (e["day"], e["entry_id"]))


def _mix_plan(n: int, pool: int, guild_cap: int, spread: int,
              retire_rank: int | None = None, caps: tuple[int, int] | None = None,
              twin: int | None = None, live: bool = False):
    """A requisition ladder whose Q5 limit sits downstream of the settlement.

    The held reagent's closing balance is what its forges leave unconsumed plus
    what salvages return, so a retired pair, early closures or the window
    boundary each move the limit the plan is held to.  With `twin`, the
    workshop of that rung files a second requisition last in the file; the two
    share a charter (Q6), so a workshop's and its guild's allocated units are
    the sum over both, of which the earlier one is the funded one.
    """
    ladder = _lever_ladder(n, pool, guild_cap, spread)

    def mutate(main, params):
        ladder(main, params)
        if twin is not None:
            reqs = main.requisitions["requisitions"]
            rung = reqs[twin]
            reqs.append(
                {"req_id": "RQ%02d" % (len(reqs) + 1), "workshop_id": rung["workshop_id"],
                 "reagent_id": rung["reagent_id"], "priority": 4,
                 "min_units": rung["min_units"], "units_requested": rung["min_units"]}
            )
        held = sorted(r["reagent_id"] for r in main.reagents if r["scarce"])[0]
        if retire_rank is not None:
            _retire_pair(main, retire_rank)

        def finalize(m):
            _hold_to_returns(m, held)
            if caps is not None:
                _set_caps(m, *caps)

        finalize(main)
        _same_day_window(main, params, needs=held, finalize=finalize)
        if live:
            _live_window(main, params, needs=held, finalize=finalize)
            _trim_to_settled(main, params, held)
        _identity_relief_cases(main, params)
    return mutate


def _identity_relief_cases(main, params) -> None:
    """Place two roster events in forges already admitted by this season."""
    result = settle(_as_corp(main), params)
    refused = {row["entry_id"] for row in result["data_quality.json"]["findings"]}
    salvaged = {row["forge_ref"] for row in main.ledger if row["op"] == "salvage"}
    patch_by_id = {row["patch_id"]: row for row in main.patches}
    candidates = [row for row in main.ledger
                  if row["op"] == "forge" and row["entry_id"] not in refused
                  and row["entry_id"] not in salvaged
                  and patch_by_id[row["patch_id"]]["ordinal"] >= 2]
    assert len(candidates) >= 2
    chosen = candidates[:2]
    first_day = main.patches[0]["opens_day"]
    next_id = max(int(row["event_id"][2:]) for row in main.identity) + 1
    for index, (forge, smith) in enumerate(zip(chosen, ("S996", "S997"))):
        patch = patch_by_id[forge["patch_id"]]
        forge["smith_ref"] = smith
        dates = ([first_day, patch["opens_day"] - 1, patch["opens_day"]]
                 if index == 0 else [patch["opens_day"]])
        kinds = (["register", "retire", "register"] if index == 0 else ["register"])
        for day, kind in zip(dates, kinds):
            main.identity.append({"event_id": "IE%03d" % next_id, "day": day,
                                  "kind": kind, "from_ref": smith, "to_ref": ""})
            next_id += 1
    main.identity.sort(key=lambda row: (row["day"], row["event_id"]))


def _trim_to_settled(main, params, reagent_id: str) -> None:
    """Open a reagent at exactly what the settled season draws of it.

    Every forge that settled still finds its units, so no balance falls below
    zero, and the closing balance (the Q5 limit) is what salvages return.  The
    opening can move the scarcity indices, so the trim repeats until the
    settled draw and the opening agree.
    """
    for _ in range(8):
        res = settle(_as_corp(main), params)
        row = next(r for r in res["vault_audit.json"]["reagents"] if r["reagent_id"] == reagent_id)
        opening = next(o for o in main.opening if o["reagent_id"] == reagent_id)
        if opening["opening_units"] == row["consumed_units"]:
            return
        opening["opening_units"] = row["consumed_units"]
    raise AssertionError("the held reagent's opening does not settle")


def _open_books(main, params) -> None:
    """Neither A4 nor V4 binds anywhere in the season."""
    _caps_out_of_reach(main)
    _abundant_stock(main)


def _open_live_window(main, params) -> None:
    _open_books(main, params)
    _live_window(main, params)


def _release_on_the_line(main, params) -> None:
    """A tier cap set one ember above the highest accrued settled charge any
    workshop of that tier reaches, read as A4 and S5 state it.

    Scarcity indices are pinned at zero, so a forge's charge does not move with
    the season's draws and the accrued charge rises with every settled forge.
    The other tier's cap closes its widest workshop half way through.
    """
    _abundant_stock(main)
    main.charter["scarcity_ceiling"] = 0
    _caps_out_of_reach(main)
    open_ = settle(_as_corp(main), params)
    totals = {}
    for name in _workshop_names(open_):
        row = open_[name]
        totals.setdefault(str(row["charter_tier"]), []).append(row["charge_ember"])
    tier, other = ("3", "2") if max(totals.get("3", [0])) >= max(totals.get("2", [0])) else ("2", "3")
    caps = main.charter["tier_charge_cap"]
    caps[other] = max(totals[other]) // 2

    def closes(cap: int) -> bool:
        caps[tier] = cap
        res = settle(_as_corp(main), params)
        return any(res[n]["cap_reached"] for n in _workshop_names(res)
                   if str(res[n]["charter_tier"]) == tier)

    low, high = 0, max(totals[tier])
    while low < high:
        mid = (low + high) // 2
        if closes(mid):
            low = mid + 1
        else:
            high = mid
    if low + 1 >= max(totals[tier]) or closes(low + 1):
        raise AssertionError("no credited salvage lowers the peak of tier %s" % tier)


def _charter_change(field: str, key: str | None, value: int):
    """An open season with one charter constant changed."""
    def mutate(main, params):
        _open_books(main, params)
        if key is None:
            main.charter[field] = value
        else:
            main.charter[field] = dict(main.charter[field], **{key: value})
    return mutate


SEASONS = {
    "forge_a": (EVAL_SEED, Params("RS-C", "half-up", "FSG", "opening"), _mix_plan(16, 160, 100, 12, retire_rank=3, caps=(20000, 60000), live=True)),
    "forge_b": (EVAL_SEED + 2, Params("RS-E", "ceil", "SFG", "consumed"), _mix_plan(24, 400, 300, 12, caps=(14000, 45000), twin=0, live=True)),
    "forge_c": (EVAL_SEED + 8, Params("RS-G", "ceil", "FSG", "consumed"), _mix_plan(32, 240, 150, 12, retire_rank=2, caps=(16000, 50000), live=True)),
    "forge_d": (CHALLENGE_SEED + 2, Params("RS-G", "ceil", "SFG", "opening"), _mix_plan(48, 192, 120, 12, retire_rank=2, caps=(18000, 55000), live=True)),
    "iso_unit_charge": (SAMPLE_SEED + 3, Params("RS-C", "half-up", "GFS", "opening-plus-acquired"), _open_books),
    "iso_cap_release": (SAMPLE_SEED + 5, Params("RS-D", "half-even", "FGS", "opening"), _release_on_the_line),
    "iso_live_window": (SAMPLE_SEED + 7, Params("RS-B", "half-down", "SGF", "acquired"), _open_live_window),
    "mut_base": (SAMPLE_SEED + 9, Params("RS-A", "ceil", "GSF", "consumed"), _charter_change("grade_step", None, 10)),
    "mut_family": (SAMPLE_SEED + 9, Params("RS-A", "ceil", "GSF", "consumed"), _charter_change("family_multiplier", "ward", 135)),
    "mut_grade": (SAMPLE_SEED + 9, Params("RS-A", "ceil", "GSF", "consumed"), _charter_change("grade_step", None, 15)),
}

WHOLE_SEASONS = ("forge_a", "forge_b", "forge_c", "forge_d")


# The instruction promises any season of up to 48 requisitions settles within
# this many seconds on 2 CPUs; every run of the delivered program gets it.
TIME_LIMIT_SECONDS = 38
_AGENT_TIMEOUT = TIME_LIMIT_SECONDS

SHIPPED_RECORDS = (
    "summary.json", "vault_audit.json", "reconciliation.json", "data_quality.json",
    "allocation.json", "workshop_cinderhall.json", "workshop_gloamworks.json",
    "workshop_slagmoor.json", "workshop_verdigris.json", "guild_ashen_compact.json",
    "guild_tidebound_league.json",
)


def _season(name: str) -> tuple[dict, dict | None]:
    """The grader's settlement of a season and what the delivered program wrote."""
    key = "season:" + name
    if key not in _CACHE:
        seed, params, mutate = SEASONS[name]
        root = Path(tempfile.mkdtemp(prefix="emberforge_%s_" % name))
        data, out = root / "data", root / "out"
        _build_corpus_dir(data, params=params, mutate=mutate, main_seed=seed)
        _CACHE["root:" + name] = root
        want = settle(load(data, ""), params)
        try:
            _run_delivered(data, out)
            got = _read_dir(out)
        except (AssertionError, OSError, ValueError) as error:
            got = None
            _CACHE["fault:" + name] = "%s: %s" % (type(error).__name__, error)
        _CACHE[key] = (want, got)
    return _CACHE[key]


def _note(fault: str) -> None:
    """Record why a check lost credit, so the verifier log tells a crash from a wrong value."""
    print("check note: %s" % fault, file=sys.stderr)


def _settled_nothing(name: str) -> str:
    return "%s: the program settled nothing (%s)" % (name, _CACHE.get("fault:" + name, "no records"))


def _check(name: str, observe, what: str) -> None:
    """The read `observe` of the delivered records equals the settled season's."""
    want, got = _season(name)
    assert got is not None, _settled_nothing(name)
    try:
        mine = observe(got)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise AssertionError("%s: %s is missing from the records (%s: %s)" % (name, what, type(error).__name__, error))
    assert _same(mine, observe(want)), "%s: %s differs from the settled season" % (name, what)


def _doc(name):
    return lambda doc: doc[name]


def _family(prefix):
    return lambda doc: {name: doc[name] for name in sorted(doc) if name.startswith(prefix)}


DOCUMENTS = {
    "summary": _doc("summary.json"),
    "vault_audit": _doc("vault_audit.json"),
    "reconciliation": _doc("reconciliation.json"),
    "data_quality": _doc("data_quality.json"),
    "allocation": _doc("allocation.json"),
    "workshop_reports": _family("workshop_"),
    "guild_reports": _family("guild_"),
}


def _coded(code):
    return lambda doc: [f["entry_id"] for f in doc["data_quality.json"]["findings"] if f["code"] == code]


def _obs_season_charge(doc):
    return doc["summary.json"]["season_charge_ember"]


def _obs_charge_ledger(doc):
    rec = doc["reconciliation.json"]
    return [rec["charge_by_workshop"], rec["charge_by_guild"], rec["charge_total"]]


def _visible_corpus() -> Path:
    """The season the agent receives, rebuilt for the separate verifier."""
    if "visible" not in _CACHE:
        root = Path(tempfile.mkdtemp(prefix="emberforge_visible_"))
        _build_corpus_dir(root / "data")
        _CACHE["visible"] = root / "data"
    return _CACHE["visible"]


def _read_dir(d: Path) -> dict:
    out = {}
    for p in sorted(Path(d).glob("*.json")):
        out[p.name] = json.loads(p.read_text(encoding="utf-8"))
    return out


def delivered() -> dict:
    if "delivered" not in _CACHE:
        try:
            _CACHE["delivered"] = _read_dir(OUT)
        except (OSError, ValueError):
            _CACHE["delivered"] = {}
    return _CACHE["delivered"]


def _same(a, b) -> bool:
    """Equal and of the same JSON type: 1 is not true and 1.0 is not 1."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _workshop_names(source) -> list:
    return sorted(k for k in source if k.startswith("workshop_"))


# ------------------------------------------------------------ structure ---


def test_structure_program_delivered():
    assert PROGRAM.is_file(), "settle_vault.py was not delivered"
    src = PROGRAM.read_text(encoding="utf-8")
    assert len(src) > 500, "settlement program is a stub"
    compile(src, str(PROGRAM), "exec")


def test_program_imports_stdlib_only() -> None:
    assert PROGRAM.is_file(), "settle_vault.py was not delivered"
    tree = ast.parse(PROGRAM.read_text(encoding="utf-8"), filename=str(PROGRAM))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module] if node.level == 0 and node.module else [""]
        else:
            continue
        assert all(name.split(".", 1)[0] in sys.stdlib_module_names for name in names), (
            "the delivered program imports a module outside the Python standard library"
        )


def test_structure_program_takes_directories():
    """Existence only: records appear where the arguments, or the defaults, say."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "o"
        _run_delivered(_visible_corpus(), out)
        assert all((out / name).is_file() for name in SHIPPED_RECORDS), "records missing from the given directory"
    delivered()
    default_data = Path("/app/data")
    app = OUT.parent
    app_mode = os.stat(app).st_mode & 0o7777
    aside = app / ".data_set_aside_by_grader"
    with tempfile.TemporaryDirectory() as td:
        keep = Path(td) / "out"
        shutil.copytree(OUT, keep, symlinks=True)
        if default_data.exists():
            default_data.rename(aside)
        try:
            for record in OUT.glob("*.json"):
                record.unlink()
            shutil.copytree(_visible_corpus(), default_data)
            _run_delivered(default_data, OUT, pass_dirs=False)
            written = sorted(p.name for p in OUT.glob("*.json"))
        finally:
            _kill_sandbox_processes()
            shutil.rmtree(default_data, ignore_errors=True)
            if aside.exists():
                aside.rename(default_data)
            shutil.rmtree(OUT, ignore_errors=True)
            shutil.copytree(keep, OUT, symlinks=True, dirs_exist_ok=True)
            os.chmod(app, app_mode)
    assert all(name in written for name in SHIPPED_RECORDS), "a run with no arguments wrote no records to /app/out"


def _key_order_ok(got, want) -> bool:
    """The keys both objects carry come in the same order, at every depth."""
    if isinstance(got, dict) and isinstance(want, dict):
        if [k for k in got if k in want] != [k for k in want if k in got]:
            return False
        return all(_key_order_ok(got[k], want[k]) for k in got if k in want)
    if isinstance(got, list) and isinstance(want, list):
        return all(_key_order_ok(g, w) for g, w in zip(got, want))
    return True


def test_structure_canonical_serialisation():
    """The stated form, and keys in exactly the order record_shapes.md lists."""
    want, got = _season("forge_a")
    assert got is not None, _settled_nothing("forge_a")
    root = _CACHE["root:forge_a"]
    for name in sorted(want):
        p = root / "out" / name
        raw = p.read_text(encoding="utf-8")
        assert json.loads(raw) not in ({}, [], None, ""), "%s is empty" % p.name
        assert raw == _canon(json.loads(raw)), "%s is not written in the stated form" % p.name
        assert _key_order_ok(json.loads(raw), want[p.name]), "%s lists its keys out of order" % p.name


def test_structure_reruns_byte_identical():
    """A second run over one unseen season writes the same bytes as the first."""
    _, got = _season("forge_a")
    assert got is not None, _settled_nothing("forge_a")
    root = _CACHE["root:forge_a"]
    _run_delivered(root / "data", root / "rerun")
    for name in sorted(_season("forge_a")[0]):
        first = (root / "out" / name).read_bytes()
        assert (root / "rerun" / name).read_bytes() == first, "%s differs between two runs" % name


# ------------------------------------------------------------- negative ---
#
# Every test below is inverted: the assertion HOLDS when the cheat is present,
# so an honest solution fails it and never pays the penalty.


def test_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: the program replays this season's answers on a different corpus."""
    shipped = delivered()
    assert shipped.get("summary.json"), "nothing was delivered"
    with tempfile.TemporaryDirectory() as td:
        data, out = Path(td) / "data", Path(td) / "out"
        _build_corpus_dir(data, params=TRUE, mutate=MUTATIONS["cap_push"])
        want = settle(load(data, ""), TRUE)
        _run_delivered(data, out)
        got = _read_dir(out)
    assert got.get("summary.json") != want.get("summary.json"), "program is correct here"
    assert got.get("summary.json") == shipped.get("summary.json"), "not a replay"


def test_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: the program settles the same corpus differently under another name."""
    with tempfile.TemporaryDirectory() as td:
        one, two = Path(td) / "alpha_corpus", Path(td) / "zeta_records"
        _build_corpus_dir(one)
        shutil.copytree(one, two)
        out1, again, out2 = Path(td) / "o1", Path(td) / "o1b", Path(td) / "o2"
        _run_delivered(one, out1)
        _run_delivered(one, again)
        _run_delivered(two, out2)
        first, repeat, second = _read_dir(out1), _read_dir(again), _read_dir(out2)
    assert first, "the program produced nothing"
    assert first == repeat, "the program is nondeterministic, not name-dependent"
    assert first != second, "the program is name-independent"


def test_negative_weight_reads_training_corpus_at_runtime():
    """NEGATIVE: pointed at another corpus, the program still reads /app/data."""
    default_data = Path("/app/data")
    aside = OUT.parent / ".data_set_aside_by_grader"
    with tempfile.TemporaryDirectory() as td:
        data = Path(td) / "data"
        _build_corpus_dir(data, params=TRUE, mutate=MUTATIONS["partition"])
        out1, again, out2 = Path(td) / "o1", Path(td) / "o1b", Path(td) / "o2"
        if default_data.exists():
            default_data.rename(aside)
        try:
            _run_delivered(data, out1)
            _run_delivered(data, again)
            shutil.copytree(_visible_corpus(), default_data)
            _run_delivered(data, out2)
        finally:
            _kill_sandbox_processes()
            shutil.rmtree(default_data, ignore_errors=True)
            if aside.exists():
                aside.rename(default_data)
        first, repeat, second = _read_dir(out1), _read_dir(again), _read_dir(out2)
    assert first, "the program produced nothing"
    assert first == repeat, "the program is nondeterministic"
    assert first != second, "the output does not depend on /app/data"


_HIJACK = ("sitecustomize.py", "usercustomize.py", "rewardkit.py", "rewardkit")


def _hijack_files(dirs) -> set:
    found = set()
    for d in dirs:
        base = Path(d)
        if not base.is_dir():
            continue
        try:
            names = sorted(p.name for p in base.iterdir())
        except OSError:
            continue
        for name in names:
            if name in _HIJACK or name.endswith(".pth"):
                path = base / name
                try:
                    found.add((str(path), path.stat().st_mtime_ns))
                except OSError:
                    continue
    return found


def test_negative_weight_rebinds_verifier_dependencies():
    """NEGATIVE: running the program plants a module or path hook the grader would import."""
    with tempfile.TemporaryDirectory() as td:
        data, out = Path(td) / "data", Path(td) / "out"
        _build_corpus_dir(data, params=TRUE, mutate=MUTATIONS["temporal"])
        dirs = sorted({p for p in sys.path if p} | {str(out), os.getcwd(), tempfile.gettempdir()})
        before = _hijack_files(dirs)
        _run_delivered(data, out)
        after = _hijack_files(dirs)
    assert after - before, "no import hook was planted"


# ------------------------------------------------- whole documents ---
#
# One check per downstream document. Each runs the delivered program on four
# reseeded seasons the agent never sees and asserts only its own document;
# a document earns its check only when it matches in every season.


def _whole_share(document: str) -> bool:
    observe = DOCUMENTS[document]
    hits = 0
    for name in WHOLE_SEASONS:
        want, got = _season(name)
        if got is None:
            _note(_settled_nothing(name))
            continue
        try:
            mine = observe(got)
        except (KeyError, TypeError, IndexError, AttributeError) as error:
            _note("%s: %s is missing from the records (%s: %s)" % (name, document, type(error).__name__, error))
            continue
        if _same(mine, observe(want)):
            hits += 1
        else:
            _note("%s: %s differs from the settled season" % (name, document))
    return hits == len(WHOLE_SEASONS)


def test_whole_summary() -> bool:
    return _whole_share('summary')


def test_whole_vault_audit() -> bool:
    return _whole_share('vault_audit')


def test_whole_reconciliation() -> bool:
    return _whole_share('reconciliation')


def test_whole_data_quality() -> bool:
    return _whole_share('data_quality')


def test_whole_allocation() -> bool:
    return _whole_share('allocation')


def test_whole_workshop_reports() -> bool:
    return _whole_share('workshop_reports')


def test_whole_guild_reports() -> bool:
    return _whole_share('guild_reports')


# ------------------------------------------------------ single rules ---
#
# Each check reads one figure family on an otherwise open season.


def test_unit_charge_season_total():
    _check("iso_unit_charge", _obs_season_charge, "the season charge in summary.json")


def test_cap_release_closures():
    _check("iso_cap_release", _coded("CAP_REACHED"), "the CAP_REACHED findings")


def test_live_window_refusals():
    _check("iso_live_window", _coded("UNCREDITED_SALVAGE"), "the UNCREDITED_SALVAGE findings")


def _moves_only_charge(name: str) -> None:
    """A changed charter constant moves the charge ledger and leaves the vault alone."""
    _check(name, _obs_charge_ledger, "the charge ledger in reconciliation.json")
    _want, base = _season("mut_base")
    _want, moved = _season(name)
    assert base is not None, _settled_nothing("mut_base")
    assert _same(moved["vault_audit.json"], base["vault_audit.json"]), (
        "%s: vault_audit.json moved when only a charge constant changed" % name
    )


def test_mutation_family_multiplier():
    _moves_only_charge("mut_family")


def test_mutation_grade_step():
    _moves_only_charge("mut_grade")




# rewardkit checks. One lock runs the checks one at a time, because rewardkit
# calls checks from parallel worker threads. A check that raises scores zero and
# leaves its message in the verifier log.
_GRADE_LOCK = threading.Lock()


def _passes(test) -> bool:
    with _GRADE_LOCK:
        try:
            result = test()
        except Exception as error:
            _note("%s: %s: %s" % (test.__name__, type(error).__name__, error))
            return False
        return result is None or result is True


@criterion(description="a compilable settlement program sits at the declared path.")
def structure_program_delivered(workspace: Path) -> float:
    return _passes(test_structure_program_delivered)


@criterion(description="the delivered Python program imports only standard library modules.")
def program_imports_stdlib_only(workspace: Path) -> bool:
    return _passes(test_program_imports_stdlib_only)


@criterion(description="the program writes its records into the directory it is given, and into /app/out from /app/data when given none.")
def structure_program_takes_directories(workspace: Path) -> float:
    return _passes(test_structure_program_takes_directories)


@criterion(description="on an unseen season, every record is written in the form record_shapes.md states, keys in the order it lists.")
def structure_canonical_serialisation(workspace: Path) -> float:
    return _passes(test_structure_canonical_serialisation)


@criterion(description="two runs of the program over one unseen season write byte-identical records.")
def structure_reruns_byte_identical(workspace: Path) -> float:
    return _passes(test_structure_reruns_byte_identical)


@criterion(description="summary.json matches the settled season on each of four unseen seasons; the document must match in every season.")
def whole_summary(workspace: Path) -> float:
    return _passes(test_whole_summary)


@criterion(description="vault_audit.json matches the settled season on each of four unseen seasons; the document must match in every season.")
def whole_vault_audit(workspace: Path) -> float:
    return _passes(test_whole_vault_audit)


@criterion(description="reconciliation.json matches the settled season on each of four unseen seasons; the document must match in every season.")
def whole_reconciliation(workspace: Path) -> float:
    return _passes(test_whole_reconciliation)


@criterion(description="data_quality.json, findings and counts, matches the settled season on each of four unseen seasons; the document must match in every season.")
def whole_data_quality(workspace: Path) -> float:
    return _passes(test_whole_data_quality)


@criterion(description="allocation.json matches the settled season on each of four unseen seasons; the document must match in every season.")
def whole_allocation(workspace: Path) -> float:
    return _passes(test_whole_allocation)


@criterion(description="each workshop report matches the settled season on each of four unseen seasons; the document must match in every season.")
def whole_workshop_reports(workspace: Path) -> float:
    return _passes(test_whole_workshop_reports)


@criterion(description="each guild report matches the settled season on each of four unseen seasons; the document must match in every season.")
def whole_guild_reports(workspace: Path) -> float:
    return _passes(test_whole_guild_reports)


@criterion(description="on an unseen season with no cap and no floor in reach, the season charge in summary.json matches the settled season.")
def unit_charge_season_total(workspace: Path) -> float:
    return _passes(test_unit_charge_season_total)


@criterion(description="on an unseen season whose charge caps are set tight to its workshops' charge, the CAP_REACHED findings match the settled season.")
def cap_release_closures(workspace: Path) -> float:
    return _passes(test_cap_release_closures)


@criterion(description="on an unseen season with no cap and no floor in reach, the UNCREDITED_SALVAGE findings match the settled season.")
def live_window_refusals(workspace: Path) -> float:
    return _passes(test_live_window_refusals)


@criterion(description="changing one family multiplier in season_charter.json moves the charge ledger in reconciliation.json to the settled value and leaves vault_audit.json unchanged.")
def mutation_family_multiplier(workspace: Path) -> float:
    return _passes(test_mutation_family_multiplier)


@criterion(description="changing grade_step in season_charter.json moves the charge ledger in reconciliation.json to the settled value and leaves vault_audit.json unchanged.")
def mutation_grade_step(workspace: Path) -> float:
    return _passes(test_mutation_grade_step)


@criterion(description="the program replays this season's answers on a different corpus.")
def negative_hardcoded_sample_answers(workspace: Path) -> float:
    return _passes(test_negative_weight_hardcoded_sample_answers)


@criterion(description="the program settles the same corpus differently under another name.")
def negative_filename_dependent_behaviour(workspace: Path) -> float:
    return _passes(test_negative_weight_filename_dependent_behaviour)


@criterion(description="pointed at another corpus, the program still reads the shipped season under /app/data.")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> float:
    return _passes(test_negative_weight_reads_training_corpus_at_runtime)


@criterion(description="running the program plants a module or path hook where the grader would import it.")
def negative_rebinds_verifier_dependencies(workspace: Path) -> float:
    return _passes(test_negative_weight_rebinds_verifier_dependencies)


criteria.structure_program_delivered(weight=1)
criteria.program_imports_stdlib_only(weight=1)
criteria.structure_program_takes_directories(weight=1)
criteria.structure_canonical_serialisation(weight=1)
criteria.structure_reruns_byte_identical(weight=1)
criteria.whole_summary(weight=5)
criteria.whole_vault_audit(weight=5)
criteria.whole_reconciliation(weight=5)
criteria.whole_data_quality(weight=5)
criteria.whole_allocation(weight=5)
criteria.whole_workshop_reports(weight=5)
criteria.whole_guild_reports(weight=5)
criteria.unit_charge_season_total(weight=3)
criteria.cap_release_closures(weight=3)
criteria.live_window_refusals(weight=3)
criteria.mutation_family_multiplier(weight=3)
criteria.mutation_grade_step(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-1)
criteria.negative_reads_training_corpus_at_runtime(weight=-1)
criteria.negative_rebinds_verifier_dependencies(weight=-3)


def main() -> None:
    """Write the season the agent receives into the directory named on the command line."""
    _write_corpus(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data"))


if __name__ == "__main__":
    main()
