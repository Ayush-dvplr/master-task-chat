#!/usr/bin/env python3
"""Lock planner for a registry of binary index shards.

Usage: python3 optimize.py <input_dir> <output_dir>

Recovers the six withheld registry constants from the calibration slice, reads
the field shards through every announced transform, merges rename chains,
settles the smallest valid lock plan of every benchmark workspace and writes the
nine documents the report schema describes.
"""
from __future__ import annotations

import csv
import json
import struct
import sys
import zlib
from pathlib import Path

MOD32 = 1 << 32
BIG = 1000003
GATE_ALWAYS = 255
STATE_LIMIT = 250000

BIT = {
    "MASK_BYTES": 0x0001,
    "CHAIN_VERSION": 0x0002,
    "DELTA2_DAY": 0x0004,
    "DRIFT_KEY": 0x0008,
    "BLOCK_PERMUTE": 0x0010,
    "BACKREF_DEPS": 0x0020,
    "ENDIAN_ISLAND": 0x0040,
    "BIASED_COUNT": 0x0080,
    "ROT_STATUS": 0x0100,
    "XREF_KEY": 0x0200,
    "SPLIT_TAIL": 0x0400,
}
FULL_WORD = 0x07FF

LIST_ROWS = {
    "salt word": "salt",
    "window span": "window_span",
    "bias limit": "bias_limit",
    "rotation base": "rotation_base",
    "shuffle multiplier": "permutation_multiplier",
    "quarantine days": "quarantine_days",
}
PARAMETER_SEQUENCE = ("salt", "window_span", "bias_limit", "rotation_base", "permutation_multiplier", "quarantine_days")

PERMISSIVE_IDS = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib", "Unlicense"}
COPYLEFT_IDS = {"GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0", "MPL-2.0", "EPL-2.0"}


class BadShard(Exception):
    """The calibration or field shard cannot be read under the constants tried."""


def crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def version_string(code: int) -> str:
    return f"{code >> 16}.{(code >> 8) & 255}.{code & 255}"


def version_number(text: str) -> int:
    major, minor, patch = text.strip().split(".")
    return int(major) * 65536 + int(minor) * 256 + int(patch)


# ----------------------------------------------------------------------------
# wire layer
# ----------------------------------------------------------------------------

class Shard:
    """One index shard held as bytes plus its fixed header fields."""

    def __init__(self, name: str, blob: bytes) -> None:
        self.name = name
        self.blob = blob
        if len(blob) < 20 or blob[:4] != b"PIDX" or blob[4] != 2:
            raise BadShard(f"{name}: not an index shard")
        if (crc(blob[:18]) & 0xFFFF) != int.from_bytes(blob[18:20], "little"):
            raise BadShard(f"{name}: header check")
        self.tier = blob[5]
        self.word = int.from_bytes(blob[6:8], "little")
        self.nonce = int.from_bytes(blob[8:12], "big" if self.has("ENDIAN_ISLAND") else "little")
        if int.from_bytes(blob[12:16], "little") != len(blob) - 20:
            raise BadShard(f"{name}: block area length")
        self.stored_count = int.from_bytes(blob[16:18], "little")

    def has(self, flag: str) -> bool:
        return bool(self.word & BIT[flag])

    def walk(self, salt: str, bias_limit: int, rotation: int) -> list[dict]:
        """Split the block area into blocks in file order; values stay as stored."""
        count = self.stored_count
        if self.has("BIASED_COUNT"):
            count -= (crc(salt.encode() + self.nonce.to_bytes(4, "little")) & 255) % bias_limit
        if count < 0:
            raise BadShard("negative block count")
        blob = self.blob
        end = len(blob)
        cursor = 20
        count_order = "big" if self.has("ENDIAN_ISLAND") else "little"
        tagged = self.has("BACKREF_DEPS")
        blocks = []

        def need(size: int) -> None:
            if cursor + size > end:
                raise BadShard("field runs past the end")

        for _ in range(count):
            begin = cursor
            need(10)
            key = int.from_bytes(blob[cursor:cursor + 4], "little")
            n_records = int.from_bytes(blob[cursor + 4:cursor + 6], count_order)
            block_nonce = int.from_bytes(blob[cursor + 6:cursor + 10], "little")
            cursor += 10
            rows = []
            for ordinal in range(n_records):
                need(12)
                code, size, day, word = struct.unpack_from("<IIHH", blob, cursor)
                cursor += 12
                if self.has("ROT_STATUS"):
                    turn = (rotation + ordinal % 8) % 16
                    word = ((word >> turn) | (word << (16 - turn))) & 0xFFFF
                entries = []
                for _e in range(word & 255):
                    if tagged:
                        need(1)
                        tag = blob[cursor]
                        cursor += 1
                        if tag:
                            entries.append(tag)
                            continue
                    need(14)
                    entries.append(struct.unpack_from("<IIIBB", blob, cursor))
                    cursor += 14
                rows.append([code, size, day, word >> 8, entries])
            need(4)
            if crc(blob[begin:cursor]) != int.from_bytes(blob[cursor:cursor + 4], "little"):
                raise BadShard("block trailer")
            cursor += 4
            if self.has("SPLIT_TAIL"):
                cursor += block_nonce % 7
            blocks.append({"key": key, "nonce": block_nonce, "rows": rows})
        if cursor != end:
            raise BadShard("block area does not end at the last block")
        return blocks


def shuffle_positions(count: int, seed: int, multiplier: int) -> list[int]:
    slots = list(range(count))
    state = seed
    for i in range(count - 1, 0, -1):
        state = (state * multiplier + 0x9E3779B9) % MOD32
        j = state % (i + 1)
        slots[i], slots[j] = slots[j], slots[i]
    return slots


def unshuffle(shard: Shard, blocks: list[dict], multiplier: int) -> list[dict]:
    if not shard.has("BLOCK_PERMUTE"):
        return blocks
    slots = shuffle_positions(len(blocks), shard.nonce, multiplier)
    logical = [None] * len(blocks)
    for file_position, logical_index in enumerate(slots):
        logical[logical_index] = blocks[file_position]
    return logical


def resolve_rows(shard: Shard, blocks: list[dict], salt: str, span: int, companion: int) -> list[dict]:
    """Turn stored rows of logically ordered blocks into true records."""
    out = []
    running = 0
    for block in blocks:
        key_word = block["nonce"] ^ running if shard.has("DRIFT_KEY") else block["nonce"]
        ring = [(0, 0, 0, 0, 0)] * span
        previous_code = 0
        back1 = back2 = 0
        records = []
        for ordinal, (code, size, day, status, entries) in enumerate(block["rows"]):
            if shard.has("CHAIN_VERSION") and ordinal:
                code = (code + previous_code) % MOD32
            previous_code = code
            if shard.has("MASK_BYTES"):
                pad = crc(salt.encode() + struct.pack("<IIH", shard.nonce, key_word % MOD32, ordinal))
                size ^= pad
            if shard.has("DELTA2_DAY"):
                day = (day + 2 * back1 - back2) % 65536
            back2, back1 = back1, day
            deps = []
            for item in entries:
                if isinstance(item, int):
                    if item > span:
                        raise BadShard("back reference tag above the span")
                    item = ring[span - item]
                else:
                    item = tuple(item)
                if shard.has("BACKREF_DEPS"):
                    ring = [item] + ring[:span - 1]
                deps.append(item)
            records.append({"code": code, "size": size, "day": day, "status": status, "deps": deps})
        running = (running + sum(r["size"] for r in records)) % MOD32
        key = block["key"] ^ companion if shard.has("XREF_KEY") else block["key"]
        out.append({"key": key, "records": records, "tags": sum(1 for r in block["rows"] for e in r[4] if isinstance(e, int))})
    return out


def companions(shards: list[Shard]) -> dict[str, int]:
    ranked = sorted(shards, key=lambda s: s.nonce)
    return {s.name: ranked[i - 1].nonce for i, s in enumerate(ranked)}


def read_population(shards: list[Shard], consts: dict) -> list[tuple[Shard, list[dict]]]:
    partner = companions(shards)
    result = []
    for shard in shards:
        raw = shard.walk(consts["salt"], consts["bias_limit"], consts["rotation_base"])
        ordered = unshuffle(shard, raw, consts["permutation_multiplier"])
        result.append((shard, resolve_rows(shard, ordered, consts["salt"], consts["window_span"], partner[shard.name])))
    return result


# ----------------------------------------------------------------------------
# calibration
# ----------------------------------------------------------------------------

def parse_calibration(text: str) -> tuple[dict, int, list[tuple[str, str, int]]]:
    lists: dict[str, list] = {}
    published = []
    snapshot = None
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("Calibration snapshot day:"):
            snapshot = int(line.split(":", 1)[1])
        elif len(cells) == 2 and cells[0] in LIST_ROWS:
            name = LIST_ROWS[cells[0]]
            raw = cells[1].split()
            if name == "salt":
                lists[name] = raw
            else:
                lists[name] = [int(v, 16) if v.startswith("0x") else int(v) for v in raw]
        elif len(cells) == 3 and cells[0].startswith("CTRL-"):
            published.append((cells[0], cells[1], int(cells[2])))
    if snapshot is None or len(lists) != 6 or not published:
        raise SystemExit("calibration slice is incomplete")
    return lists, snapshot, published


def control_figures(population: list[tuple[Shard, list[dict]]], quarantine: int, snapshot: int) -> list[int]:
    blocks_seen = keys = sizes = links = states = fresh = 0
    for _shard, blocks in population:
        for position, block in enumerate(blocks, start=1):
            blocks_seen += 1
            keys += position * block["key"]
            for ordinal, rec in enumerate(block["records"], start=1):
                sizes += ordinal * (rec["size"] + rec["code"])
                states += ordinal * (3 * rec["status"] + len(rec["deps"]))
                for place, dep in enumerate(rec["deps"], start=1):
                    links += place * ordinal * ((dep[0] ^ dep[1]) + 7 * dep[3] + dep[4])
                if not rec["status"] & 1 and rec["day"] <= snapshot and snapshot - rec["day"] >= quarantine:
                    fresh += 1
    return [blocks_seen, keys % BIG, sizes % BIG, links % BIG, states % BIG, fresh]


def try_figures(shards: list[Shard], consts: dict, snapshot: int) -> list[int] | None:
    try:
        return control_figures(read_population(shards, consts), consts["quarantine_days"], snapshot)
    except BadShard:
        return None


def recover_constants(shards: list[Shard], lists: dict, snapshot: int, published: list) -> dict:
    target = [value for _cid, _fig, value in published]
    walkable = []
    for salt in lists["salt"]:
        for limit in lists["bias_limit"]:
            for turn in lists["rotation_base"]:
                try:
                    for shard in shards:
                        shard.walk(salt, limit, turn)
                except BadShard:
                    continue
                walkable.append((salt, limit, turn))
    survivors = []
    for salt, limit, turn in walkable:
        for span in lists["window_span"]:
            for multiplier in lists["permutation_multiplier"]:
                consts = {"salt": salt, "bias_limit": limit, "rotation_base": turn, "window_span": span,
                          "permutation_multiplier": multiplier, "quarantine_days": 0}
                try:
                    population = read_population(shards, consts)
                except BadShard:
                    continue
                figures = control_figures(population, 0, snapshot)
                if figures[:5] != target[:5]:
                    continue
                for days in lists["quarantine_days"]:
                    if control_figures(population, days, snapshot)[5] == target[5]:
                        survivors.append(dict(consts, quarantine_days=days))
    if len(survivors) != 1:
        raise SystemExit(f"calibration slice admits {len(survivors)} assignments")
    return survivors[0]


def candidate_verdicts(shards: list[Shard], lists: dict, snapshot: int, published: list, truth: dict) -> list[dict]:
    target = [value for _cid, _fig, value in published]
    verdicts = []
    for parameter in PARAMETER_SEQUENCE:
        for value in lists[parameter]:
            shown = f"0x{value:08x}" if parameter == "permutation_multiplier" else str(value)
            if value == truth[parameter]:
                verdicts.append({"parameter": parameter, "value": shown, "verdict": "accepted", "falsifier": "none"})
                continue
            trial = dict(truth)
            trial[parameter] = value
            figures = try_figures(shards, trial, snapshot)
            if figures is None:
                label = "UNREADABLE"
            else:
                label = next(published[i][0] for i in range(len(target)) if figures[i] != target[i])
            verdicts.append({"parameter": parameter, "value": shown, "verdict": "rejected", "falsifier": label})
    return verdicts


# ----------------------------------------------------------------------------
# registry, licences and workspaces
# ----------------------------------------------------------------------------

def family_of(expression: str) -> str:
    if " OR " in expression:
        sides = {family_of(p) for p in expression.split(" OR ")}
        return "permissive" if "permissive" in sides else "copyleft"
    if " AND " in expression:
        sides = {family_of(p) for p in expression.split(" AND ")}
        return "copyleft" if "copyleft" in sides else "permissive"
    ident = expression.strip()
    if ident in PERMISSIVE_IDS:
        return "permissive"
    if ident in COPYLEFT_IDS:
        return "copyleft"
    raise SystemExit(f"unknown licence {ident}")


class Names:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = {r["package"]: r for r in rows}
        self.key_to_name = {int(r["package_key"], 16): r["package"] for r in rows}
        self.next_name = {r["renamed_from"]: r["package"] for r in rows if r["renamed_from"]}

    def newest(self, name: str) -> str:
        while name in self.next_name:
            name = self.next_name[name]
        return name

    def earliest(self, name: str) -> str:
        while self.rows[name]["renamed_from"]:
            name = self.rows[name]["renamed_from"]
        return name

    def package_for_key(self, key: int) -> str | None:
        name = self.key_to_name.get(key)
        return None if name is None else self.newest(name)

    def governing_family(self, package: str, earliest_governs: bool = True) -> str:
        name = self.earliest(package) if earliest_governs else package
        return family_of(self.rows[name]["licence"])


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# ----------------------------------------------------------------------------
# lock planning
# ----------------------------------------------------------------------------

def live(entry: tuple, mask: int) -> bool:
    return entry[4] == GATE_ALWAYS or (mask >> entry[4]) & 1 == 1


def smallest_features(chosen: dict, direct: list) -> dict:
    masks = dict.fromkeys(chosen, 0)
    for pkg, _lo, _hi, want in direct:
        if pkg in masks:
            masks[pkg] |= want
    queue = list(chosen)
    while queue:
        pkg = queue.pop()
        for entry in chosen[pkg]["links"]:
            dst = entry[0]
            if dst in masks and live(entry, masks[pkg]) and (masks[dst] | entry[3]) != masks[dst]:
                masks[dst] |= entry[3]
                queue.append(dst)
    return masks


def count_passes(chosen: dict, direct: list) -> int:
    state = dict.fromkeys(chosen, 0)
    for pkg, _lo, _hi, want in direct:
        if pkg in state:
            state[pkg] |= want
    rounds = 0
    while True:
        rounds += 1
        grown = dict(state)
        for pkg, version in chosen.items():
            for entry in version["links"]:
                if entry[0] in grown and live(entry, state[pkg]):
                    grown[entry[0]] |= entry[3]
        if grown == state:
            return rounds
        state = grown


def plan_workspace(pool: dict, direct: list, family_ok: dict) -> dict | None:
    ranked = {pkg: sorted(vs, key=lambda v: (v["size"], -v["code"])) for pkg, vs in pool.items()}
    best = {"rank": None, "plan": None}
    visits = [0]

    def inspect(chosen: dict) -> set | None:
        masks = smallest_features(chosen, direct)
        wanted = set()
        for pkg, lo, hi, _want in direct:
            if pkg is None:
                return None
            wanted.add(pkg)
            if pkg in chosen and not lo <= chosen[pkg]["code"] < hi:
                return None
        for pkg, version in chosen.items():
            for entry in version["links"]:
                if not live(entry, masks[pkg]):
                    continue
                if entry[0] is None:
                    return None
                wanted.add(entry[0])
                if entry[0] in chosen and not entry[1] <= chosen[entry[0]]["code"] < entry[2]:
                    return None
        return wanted

    def rank(chosen: dict) -> tuple:
        text = ",".join(f"{pkg}@{chosen[pkg]['code']:08x}" for pkg in sorted(chosen))
        return (sum(v["size"] for v in chosen.values()), -sum(v["code"] for v in chosen.values()), text)

    def extend(chosen: dict, spent: int) -> None:
        visits[0] += 1
        if visits[0] > STATE_LIMIT:
            raise SystemExit("lock search exceeded its state limit")
        if best["rank"] is not None and spent > best["rank"][0]:
            return
        wanted = inspect(chosen)
        if wanted is None:
            return
        pending = sorted(wanted.difference(chosen))
        if not pending:
            here = rank(chosen)
            if best["rank"] is None or here < best["rank"]:
                best["rank"], best["plan"] = here, dict(chosen)
            return
        pkg = pending[0]
        if not family_ok.get(pkg):
            return
        for version in ranked.get(pkg, []):
            chosen[pkg] = version
            extend(chosen, spent + version["size"])
            del chosen[pkg]

    extend({}, 0)
    return best["plan"]


# ----------------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------------

def dump(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    source = Path(argv[1])
    target = Path(argv[2])
    target.mkdir(parents=True, exist_ok=True)

    shards = []
    for path in sorted(source.iterdir()):
        if path.is_file() and path.read_bytes()[:4] == b"PIDX":
            shards.append(Shard(path.name, path.read_bytes()))
    calibration = [s for s in shards if s.tier == 1]
    field = [s for s in shards if s.tier == 2]

    lists, calib_day, published = parse_calibration((source / "calibration.md").read_text(encoding="utf-8"))
    truth = recover_constants(calibration, lists, calib_day, published)
    verdicts = candidate_verdicts(calibration, lists, calib_day, published, truth)
    reproduced = control_figures(read_population(calibration, truth), truth["quarantine_days"], calib_day)

    names = Names(read_csv(source / "package-registry.csv"))
    population = read_population(field, truth)

    quality = {
        "total_shards": len(field),
        "shards_with_full_flag_set": sum(1 for s in field if s.word == FULL_WORD),
        "records_yanked": 0,
        "records_deprecated": 0,
        "records_unregistered_package": 0,
        "dependency_entries_back_referenced": 0,
        "dependency_entries_unregistered_target": 0,
        "excluded_bytes_by_cause": {"unregistered_package": 0, "yanked": 0},
    }
    tally = {"shards_decoded": len(field), "blocks_decoded": 0, "records_decoded": 0,
             "dependency_entries_decoded": 0, "decoded_bytes": 0}
    catalogue: dict[str, list] = {}
    for _shard, blocks in population:
        for block in blocks:
            tally["blocks_decoded"] += 1
            quality["dependency_entries_back_referenced"] += block["tags"]
            owner = names.package_for_key(block["key"])
            for rec in block["records"]:
                tally["records_decoded"] += 1
                tally["dependency_entries_decoded"] += len(rec["deps"])
                tally["decoded_bytes"] += rec["size"]
                quality["records_deprecated"] += 1 if rec["status"] & 2 else 0
                quality["dependency_entries_unregistered_target"] += sum(
                    1 for d in rec["deps"] if names.package_for_key(d[0]) is None)
                if owner is None:
                    quality["records_unregistered_package"] += 1
                    quality["excluded_bytes_by_cause"]["unregistered_package"] += rec["size"]
                elif rec["status"] & 1:
                    quality["records_yanked"] += 1
                    quality["excluded_bytes_by_cause"]["yanked"] += rec["size"]
                else:
                    links = [(names.package_for_key(d[0]), d[1], d[2], d[3], d[4]) for d in rec["deps"]]
                    catalogue.setdefault(owner, []).append(
                        {"code": rec["code"], "size": rec["size"], "day": rec["day"], "links": links})

    workspaces = read_csv(source / "workspaces.csv")
    requirements = read_csv(source / "workspace-requirements.csv")
    quarantine = truth["quarantine_days"]

    lock_docs = {}
    bottlenecks = []
    passes = {}
    divergence = []
    locked_once: dict[tuple, int] = {}
    for ws in workspaces:
        label = ws["workspace"]
        day = int(ws["snapshot_day"])
        forbids = ws["copyleft"] == "forbidden"
        direct = []
        for req in requirements:
            if req["workspace"] == label:
                pkg = names.newest(req["package"]) if req["package"] in names.rows else None
                direct.append((pkg, version_number(req["lowest"]), version_number(req["below"]), int(req["features"])))
        pool = {pkg: [v for v in versions if v["day"] <= day and day - v["day"] >= quarantine]
                for pkg, versions in catalogue.items()}
        ok_root = {pkg: not forbids or names.governing_family(pkg) == "permissive" for pkg in pool}
        ok_newest = {pkg: not forbids or names.governing_family(pkg, False) == "permissive" for pkg in pool}
        plan = plan_workspace(pool, direct, ok_root)
        if plan is None:
            raise SystemExit(f"workspace {label} has no valid lock plan")
        if plan_workspace(pool, direct, ok_newest) != plan:
            divergence.append(label)
        masks = smallest_features(plan, direct)
        passes[label] = count_passes(plan, direct)
        entries = []
        held = []
        families = {"permissive": [], "copyleft": []}
        for pkg in sorted(plan):
            version = plan[pkg]
            fam = names.governing_family(pkg)
            entries.append({"package": pkg, "version": version_string(version["code"]), "features": masks[pkg],
                            "licence_family": fam, "bytes": version["size"]})
            families[fam].append(pkg)
            top = max(v["code"] for v in pool[pkg])
            if version["code"] < top:
                held.append({"package": pkg, "locked": version_string(version["code"]), "newest_eligible": version_string(top)})
            locked_once[(pkg, version["code"])] = version["size"]
        quarantined = sum(1 for versions in catalogue.values() for v in versions if v["day"] <= day and day - v["day"] < quarantine)
        lock_docs[label] = {
            "workspace": label,
            "snapshot_day": day,
            "copyleft": ws["copyleft"],
            "footprint_bytes": sum(v["size"] for v in plan.values()),
            "package_count": len(plan),
            "quarantined_records": quarantined,
            "packages": entries,
        }
        bottlenecks.append({"workspace": label, "held_back": held,
                            "permissive_packages": families["permissive"], "copyleft_packages": families["copyleft"]})

    excluded = sum(quality["excluded_bytes_by_cause"].values())
    locked = sum(locked_once.values())
    perf = dict(tally)
    perf.update({
        "excluded_bytes": excluded,
        "locked_bytes": locked,
        "byte_residual": tally["decoded_bytes"] - excluded - locked,
        "workspaces_resolved": len(lock_docs),
        "footprint_by_workspace": {k: v["footprint_bytes"] for k, v in lock_docs.items()},
        "recovered_parameters": {
            "salt": truth["salt"],
            "window_span": truth["window_span"],
            "bias_limit": truth["bias_limit"],
            "rotation_base": truth["rotation_base"],
            "permutation_multiplier": f"0x{truth['permutation_multiplier']:08x}",
            "quarantine_days": truth["quarantine_days"],
        },
    })
    totals: dict[str, int] = {}
    for row in verdicts:
        if row["verdict"] == "rejected":
            totals[row["falsifier"]] = totals.get(row["falsifier"], 0) + 1
    record = {
        "candidates": verdicts,
        "falsifier_totals": totals,
        "calibration_table": [{"control": cid, "figure": fig, "published": value, "reproduced": reproduced[i]}
                              for i, (cid, fig, value) in enumerate(published)],
        "settlement_passes_by_workspace": passes,
        "licence_divergence": sorted(divergence),
    }

    for label, doc in lock_docs.items():
        dump(target / f"scenario_{label}.json", doc)
    dump(target / "perf_report.json", perf)
    dump(target / "bottleneck_analysis.json", {"workspaces": sorted(bottlenecks, key=lambda b: b["workspace"])})
    dump(target / "data_quality.json", quality)
    dump(target / "recommendations.json", record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
