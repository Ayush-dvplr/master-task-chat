"""Behavioral checks for the STRATA relocation planner and its artifacts."""
# allow: SIZE_OK - the harness requires one self-contained verifier, including embedded sources.

from __future__ import annotations

import ast
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import types
from dataclasses import dataclass
from pathlib import Path

from rewardkit import criteria, criterion

_CASE_DATA_SRC = r'''
"""Deterministic STRATA corpus construction utilities."""

from __future__ import annotations

import json
import random
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------- constants

CLASSES = ("gold", "silver", "bronze", "tin")
CLASS_RANK = {"gold": 1, "silver": 2, "bronze": 3, "tin": 4}
KINDS = ("regular", "symlink", "fifo", "socket", "chardev", "blockdev", "dir")
SIZE_UNITS = ("B", "KiB", "MiB", "GiB", "kB", "MB", "GB", "s", "bl")
UNIT_BYTES = {
    "B": 1,
    "KiB": 1024,
    "MiB": 1048576,
    "GiB": 1073741824,
    "kB": 1000,
    "MB": 1000000,
    "GB": 1000000000,
    "s": 512,
    "bl": 4096,
}
FLAG_WORDS = ("hole", "unwritten", "inline", "shared", "sealed")
XATTR_NAMESPACES = ("user", "security", "trusted", "system")
ACL_NAMES = ("system.posix_acl_access", "system.posix_acl_default")
MUTATION_KINDS = ("write", "truncate", "unlink", "rename", "link",
                  "setxattr", "chmod", "chown", "hold", "release")
# Writes and truncations dominate a post checkpoint window, so the journal
# invalidation path carries real weight.
MUTATION_WEIGHTS = ("write", "write", "write", "write", "truncate", "truncate",
                    "unlink", "rename", "link", "setxattr", "setxattr",
                    "chmod", "chown", "hold", "release")

N_POOLS = 220
N_DEVICES = 40
N_DOMAINS = 8
N_WINDOWS = 24
N_OBJECTS = 2600
N_HOLDS = 440
BASE_INO = 100000
BARRIER_BASE = 500000
# A spill chain where every hop is offline, so the hop cap is reached.
OFFLINE_ALWAYS = (3, 10, 17, 24, 31)
# Devices that only go offline in their later revisions.
OFFLINE_LATE = (7, 14, 21)

# Accented stems, so the normalisation form of a raw path decides identity.
ACCENT_STEMS = ("café", "nõde", "grün", "réseau", "ünit")
PLAIN_STEMS = ("archive", "spool", "vault", "ledger", "shard", "index",
               "queue", "warm", "cold", "stage")
LEAF_STEMS = ("blob", "chunk", "frame", "page", "slab", "table", "trace")


def make_rng(seed: int, salt: str) -> random.Random:
    return random.Random("{}:{}".format(seed, salt))


def to_nfd(text: str) -> str:
    return unicodedata.normalize("NFD", text)


def dev_id(index: int) -> str:
    return "D{:02d}".format(index)


def pool_id(index: int) -> str:
    return "P{:03d}".format(index)


def domain_id(index: int) -> str:
    return "SD{}".format(index)


# ---------------------------------------------------------------- entities

def build_pools(seed: int) -> list[dict]:
    rng = make_rng(seed, "pools")
    rows = []
    for i in range(N_POOLS):
        rows.append({
            "pool_id": pool_id(i),
            "alloc_unit": rng.choice([4096, 4096, 4096, 65536]),
            # Edge case: the depth cap is inclusive and varies per pool
            "root_depth_cap": rng.choice([4, 5, 5, 6, 7]),
            "region": "r{:02d}".format(rng.randrange(0, 12)),
        })
    return rows


def build_barriers(seed: int, pools: list[dict]) -> list[dict]:
    """Two revisions per pool. The authoritative barrier is the revision with
    the largest effective_seq, which is deliberately not the last row."""
    rng = make_rng(seed, "barriers")
    rows = []
    for pool in pools:
        primary = BARRIER_BASE + rng.randrange(100, 900)
        stale = primary - rng.randrange(20, 400)
        eff_a = 90 + rng.randrange(0, 5)
        # Edge case: a shared effective_seq forces the rev tie-break, and the larger
        # rev carries the stale barrier rather than the primary one
        eff_b = eff_a + rng.choice([-40, -30, 0, 0, 10, 20])
        rows.append({"pool_id": pool["pool_id"], "rev": 0, "barrier_seq": primary,
                     "effective_seq": eff_a})
        rows.append({"pool_id": pool["pool_id"], "rev": 1, "barrier_seq": stale,
                     "effective_seq": eff_b})
    return rows


def build_device_capacity(seed: int) -> list[dict]:
    """Six capacity revisions per device."""
    rng = make_rng(seed, "devcap")
    rows = []
    for i in range(N_DEVICES):
        base = rng.choice([8, 10, 12, 16, 20, 28]) * 1048576
        for rev in range(6):
            unit = rng.choice(["B", "KiB", "MiB", "bl"])
            cap = base + rev * 1048576
            raw = cap // UNIT_BYTES[unit]
            used = rng.randrange(1, 9) * 1048576
            uunit = rng.choice(["B", "KiB", "MiB", "bl"])
            rows.append({
                "device_id": dev_id(i),
                "rev": rev,
                "capacity_raw": raw,
                "capacity_unit": unit,
                "existing_used_raw": used // UNIT_BYTES[uunit],
                "existing_used_unit": uunit,
                # Edge case: reserve is parts per million and floors, never rounds
                "reserve_ppm": rng.choice([0, 12500, 25000, 50000, 75000, 100000]),
                "effective_seq": 40 + rng.randrange(0, 30),
            })
    return rows


def build_device_geometry(seed: int) -> list[dict]:
    """Six geometry revisions per device, keyed by a composite slot id."""
    rng = make_rng(seed, "devgeo")
    rows = []
    for i in range(N_DEVICES):
        domain = i % N_DOMAINS
        spill = dev_id((i + 7) % N_DEVICES)
        for rev in range(6):
            drift = rng.random() < 0.25
            rows.append({
                "slot_id": "{}.r{}".format(dev_id(i), rev),
                "device_id": dev_id(i),
                "rev": rev,
                "share_domain": domain_id((domain + (1 if drift else 0)) % N_DOMAINS),
                "spill_device": spill,
                "online": "false" if (i in OFFLINE_ALWAYS or
                                      (i in OFFLINE_LATE and rev > 2)) else "true",
                "alloc_unit": rng.choice([4096, 4096, 65536]),
                "effective_seq": 40 + rng.randrange(0, 30),
            })
    return rows


def build_windows(seed: int) -> list[dict]:
    rng = make_rng(seed, "windows")
    rows = []
    for i in range(N_DEVICES):
        for w in range(N_WINDOWS):
            unit = rng.choice(["B", "KiB", "bl"])
            budget = rng.choice([512, 640, 768, 1024, 1536]) * 1024
            rows.append({
                "device_id": dev_id(i),
                "window_index": w,
                "io_budget_raw": budget // UNIT_BYTES[unit],
                "io_budget_unit": unit,
                "descriptor_budget": rng.choice([2, 3, 4, 6, 8]),
            })
    return rows


def build_placement_map(seed: int, pools: list[dict]) -> list[dict]:
    rng = make_rng(seed, "placemap")
    rows = []
    n = 0
    for pool in pools:
        for cls in CLASSES:
            rows.append({
                "route_id": "RT{:05d}".format(n),
                "class": cls,
                "pool_id": pool["pool_id"],
                "device_id": dev_id(rng.randrange(0, N_DEVICES)),
            })
            n += 1
    # Edge case: a route naming a device the catalogue does not hold
    for row in rng.sample(list(rows), 45):
        row["device_id"] = "D99"
    # Edge case: a second route for one key, settled by the smallest route id
    for row in rng.sample(list(rows), 70):
        rows.append({
            "route_id": "RT{:05d}".format(n),
            "class": row["class"],
            "pool_id": row["pool_id"],
            "device_id": dev_id((int(row["device_id"][1:]) + 5) % N_DEVICES),
        })
        n += 1
    rng.shuffle(rows)
    return rows


def _segment(rng: random.Random) -> str:
    if rng.random() < 0.22:
        return rng.choice(ACCENT_STEMS)
    return rng.choice(PLAIN_STEMS)


def build_objects(seed: int, pools: list[dict]) -> list[dict]:
    rng = make_rng(seed, "objects")
    rows = []
    for i in range(N_OBJECTS):
        ino = BASE_INO + i
        kind = "regular"
        roll = rng.random()
        if roll < 0.18:
            kind = "symlink"
        elif roll < 0.23:
            kind = "fifo"
        elif roll < 0.26:
            kind = "socket"
        elif roll < 0.29:
            kind = "chardev"
        elif roll < 0.32:
            kind = "blockdev"
        elif roll < 0.42:
            kind = "dir"
        unit = rng.choice(SIZE_UNITS)
        size_bytes = rng.choice([0, 1, 4095, 4096, 4097, 65536, 131072, 1048576,
                                 5242880, 20971520, 104857600])
        cls = rng.choice(CLASSES)
        # Edge case: class arrives in mixed case and is canonicalised to lowercase
        class_raw = cls.upper() if rng.random() < 0.18 else (
            cls.capitalize() if rng.random() < 0.15 else cls)
        mode_value = rng.choice([0o644, 0o600, 0o755, 0o400, 0o664, 0o777, 0o750])
        mode_roll = rng.random()
        if mode_roll < 0.2:
            mode_raw = "{:o}".format(mode_value)          # no leading zero
        elif mode_roll < 0.3:
            mode_raw = "0o{:o}".format(mode_value)
        elif mode_roll < 0.38:
            mode_raw = "d{}".format(mode_value)           # decimal marked form
        else:
            mode_raw = "{:04o}".format(mode_value)
        state = "live"
        sroll = rng.random()
        if sroll < 0.03:
            state = "pruned"
        elif sroll < 0.06:
            state = "held"
        rows.append({
            "ino": ino,
            "kind": kind,
            "size_raw": max(1, size_bytes // UNIT_BYTES[unit]) if size_bytes else 0,
            "size_unit": unit,
            "mode_raw": mode_raw,
            "uid": rng.choice([0, 1000, 1001, 1002, 33, 65534]),
            "gid": rng.choice([0, 1000, 1001, 50, 65534]),
            "mtime_ns": 1735689600000000000 + i * 1000003 + rng.randrange(0, 999),
            "class_raw": class_raw,
            "pool_id": "P900" if rng.random() < 0.025 else rng.choice(pools)["pool_id"],
            "link_count": 1,
            "state": state,
            "gen": 1,
        })
    # Edge case: a later generation of the same inode supersedes the earlier row
    for row in rng.sample(rows, 120):
        clone = dict(row)
        clone["gen"] = 2
        clone["class_raw"] = rng.choice(CLASSES)
        clone["state"] = "live"
        clone["mode_raw"] = "{:04o}".format(rng.choice([0o644, 0o755, 0o600]))
        rows.append(clone)
    # Edge case: two rows share a generation and the later modification time wins
    for row in rng.sample([r for r in rows if r["gen"] == 2], 60):
        clone = dict(row)
        clone["mtime_ns"] = row["mtime_ns"] + rng.randrange(1, 5000)
        clone["class_raw"] = rng.choice(CLASSES)
        clone["uid"] = rng.choice([0, 1000, 1002])
        rows.append(clone)
    return rows


def build_paths(seed: int, objects: list[dict]) -> list[dict]:
    """One to three path records per object, in two normalisation forms."""
    rng = make_rng(seed, "paths")
    latest = _latest_objects(objects)
    rows = []
    ordinal = 0
    for obj in latest:
        depth = rng.choice([2, 3, 3, 4, 5, 6])
        segments = [_segment(rng) for _ in range(depth - 1)]
        leaf = "{}-{:05d}".format(rng.choice(LEAF_STEMS), obj["ino"] % 100000)
        base = "/" + "/".join(segments + [leaf]) if segments else "/" + leaf
        count = 1
        if obj["kind"] == "regular":
            roll = rng.random()
            if roll < 0.14:
                count = 2
            elif roll < 0.18:
                count = 3
        for k in range(count):
            raw = base
            if k == 1:
                raw = "/" + "/".join([_segment(rng)] + segments[:1] + [leaf])
            elif k == 2:
                raw = "/" + "/".join(["links", leaf])
            form = "nfc"
            # Edge case: the same path arriving in NFD is the same path
            if rng.random() < 0.18 and any(ord(c) > 127 for c in raw):
                raw = to_nfd(raw)
                form = "nfd"
            # Edge case: repeated separators, dot segments and trailing separators
            shape = rng.random()
            if shape < 0.05:
                raw = raw.replace("/", "//", 1)
            elif shape < 0.09:
                raw = raw + "/"
            elif shape < 0.13:
                head, _, tail = raw.rpartition("/")
                raw = head + "/./" + tail
            elif shape < 0.16:
                head, _, tail = raw.rpartition("/")
                raw = head + "/scratch/../" + tail
            elif shape < 0.18:
                raw = raw.lstrip("/")
            rows.append({
                "ino": obj["ino"],
                "path_raw": raw,
                "ordinal": ordinal,
                "form": form,
            })
            ordinal += 1
    # Edge case: two records for one inode that collapse to one canonical path,
    # so the primary path is settled at the fourth tiebreak level
    twins = [r for r in rows if any(ord(c) > 127 for c in r["path_raw"])]
    for row in rng.sample(twins, min(40, len(twins))):
        clone = dict(row)
        clone["path_raw"] = to_nfd(row["path_raw"]) if row["form"] == "nfc" else \
            unicodedata.normalize("NFC", row["path_raw"])
        clone["form"] = "nfd" if row["form"] == "nfc" else "nfc"
        clone["ordinal"] = ordinal
        ordinal += 1
        rows.append(clone)
    rng.shuffle(rows)
    return rows


def _latest_objects(objects: list[dict]) -> list[dict]:
    best: dict[int, dict] = {}
    for row in objects:
        cur = best.get(row["ino"])
        if cur is None or row["gen"] > cur["gen"]:
            best[row["ino"]] = row
    return [best[k] for k in sorted(best)]


def build_extents(seed: int, objects: list[dict], pools: list[dict]) -> list[dict]:
    rng = make_rng(seed, "extents")
    alloc = {p["pool_id"]: p["alloc_unit"] for p in pools}
    rows = []
    shared_pool = ["PX{:05d}".format(i) for i in range(240)]
    for obj in _latest_objects(objects):
        if obj["kind"] not in ("regular",):
            continue
        unit = alloc.get(obj["pool_id"], 4096)
        count = rng.choice([1, 1, 2, 3, 4, 6, 8])
        offset = 0
        for index in range(count):
            flags = []
            roll = rng.random()
            if roll < 0.14:
                flags.append("hole")
            elif roll < 0.22:
                flags.append("unwritten")
            elif roll < 0.26:
                flags.append("inline")
            if rng.random() < 0.16 and "hole" not in flags:
                flags.append("shared")
            if rng.random() < 0.1:
                flags.append("sealed")
            length = rng.choice([unit, unit, unit * 2, unit * 4, unit * 16,
                                 unit * 64, unit - 1, unit + 1, 0])
            lunit = rng.choice(["B", "B", "B", "KiB", "bl", "s"])
            physical = rng.choice(shared_pool) if "shared" in flags else \
                "PV{:06d}".format(obj["ino"] * 10 + index)
            rows.append({
                "ino": obj["ino"],
                "ext_index": index,
                "offset": offset,
                "length_raw": length // UNIT_BYTES[lunit] if length else 0,
                "length_unit": lunit,
                "physical_id": physical,
                "flags": ",".join(flags) if flags else "none",
                "gen": 1,
            })
            offset += length
    # Edge case: a superseding generation of one extent row
    for row in rng.sample(rows, 200):
        clone = dict(row)
        clone["gen"] = 2
        clone["flags"] = "none" if clone["flags"] == "hole" else clone["flags"]
        rows.append(clone)
    # Edge case: overlapping extents inside one inode, repaired by truncation
    overlaps = rng.sample([r for r in rows if r["gen"] == 1 and r["offset"] > 0], 160)
    for row in overlaps:
        clone = dict(row)
        clone["gen"] = 3
        clone["offset"] = max(0, row["offset"] - 2048)
        rows.append(clone)
    rng.shuffle(rows)
    return rows


def _resize_objects(seed: int, objects: list[dict], extents: list[dict]) -> None:
    """Logical size follows the extents, then a share of objects is trimmed so
    the clipping and voiding repairs have fixtures."""
    rng = make_rng(seed, "resize")
    total: dict[int, int] = {}
    tail: dict[int, int] = {}
    for row in extents:
        if row["gen"] != 1:
            continue
        length = row["length_raw"] * UNIT_BYTES[row["length_unit"]]
        total[row["ino"]] = total.get(row["ino"], 0) + length
        tail[row["ino"]] = max(tail.get(row["ino"], 0), row["offset"] + length)
    sizes: dict[int, int] = {}
    for ino, end in tail.items():
        roll = rng.random()
        if roll < 0.10:
            size = max(0, end - rng.choice([1, 512, 4096, 20480]))
        elif roll < 0.13:
            size = 0
        elif roll < 0.22:
            size = end + rng.choice([1, 4096, 65536])
        else:
            size = end
        sizes[ino] = size
    for row in objects:
        if row["ino"] not in sizes:
            continue
        size = sizes[row["ino"]]
        unit = "B"
        for candidate in ("bl", "MiB", "KiB", "s"):
            if size and size % UNIT_BYTES[candidate] == 0 and rng.random() < 0.45:
                unit = candidate
                break
        row["size_raw"] = size // UNIT_BYTES[unit]
        row["size_unit"] = unit


def build_symlinks(seed: int, objects: list[dict], paths: list[dict]) -> list[dict]:
    rng = make_rng(seed, "symlinks")
    known = [p["path_raw"] for p in paths if p["path_raw"].startswith("/")]
    rows = []
    for obj in _latest_objects(objects):
        if obj["kind"] != "symlink":
            continue
        roll = rng.random()
        if roll < 0.32:
            target = rng.choice(known)
        elif roll < 0.5:
            target = "../" + rng.choice(PLAIN_STEMS) + "/" + rng.choice(LEAF_STEMS)
        elif roll < 0.62:
            target = "/outside/" + rng.choice(PLAIN_STEMS)
        elif roll < 0.74:
            target = "/missing/" + rng.choice(LEAF_STEMS) + "-{:04d}".format(
                rng.randrange(0, 9999))
        else:
            target = rng.choice(known) if known else "/x"
        # Edge case: the fast symlink boundary sits at exactly 59 bytes
        if rng.random() < 0.2:
            fill = rng.choice([57, 58, 59, 60, 61])
            target = "/" + ("t" * (fill - 1))
        form = "nfc"
        if rng.random() < 0.15 and any(ord(c) > 127 for c in target):
            target = to_nfd(target)
            form = "nfd"
        rows.append({"ino": obj["ino"], "target_raw": target, "form": form})
    # Edge case: a cycle of symlinks that resolution must detect
    cyc = [r for r in rows if r["target_raw"].startswith("/")][:60]
    for i in range(0, len(cyc) - 1, 2):
        a, b = cyc[i], cyc[i + 1]
        pa = _first_path(paths, a["ino"])
        pb = _first_path(paths, b["ino"])
        if pa and pb:
            a["target_raw"] = pb
            b["target_raw"] = pa
    # Edge case: a chain long enough that resolution reaches the hop cap
    chain = [r for r in rows if r["target_raw"].startswith("/")][60:74]
    linked = []
    for row in chain:
        path = _first_path(paths, row["ino"])
        if path:
            linked.append((row, path))
    for i in range(len(linked) - 1):
        linked[i][0]["target_raw"] = linked[i + 1][1]
    # Rewrites can copy a path in either form; label the final bytes, never alter them.
    for row in rows:
        target = row["target_raw"]
        if unicodedata.is_normalized("NFC", target):
            row["form"] = "nfc"
        elif unicodedata.is_normalized("NFD", target):
            row["form"] = "nfd"
        else:
            raise ValueError("symlink target is neither NFC nor NFD", row["ino"])
    return rows


def _first_path(paths: list[dict], ino: int) -> str:
    for row in paths:
        if row["ino"] == ino and row["path_raw"].startswith("/"):
            return row["path_raw"]
    return ""


def build_special(seed: int, objects: list[dict]) -> list[dict]:
    rng = make_rng(seed, "special")
    rows = []
    for obj in _latest_objects(objects):
        if obj["kind"] not in ("fifo", "socket", "chardev", "blockdev"):
            continue
        # Edge case: a node with no record at all still reaches the plan
        if rng.random() < 0.08:
            continue
        # Edge case: a minor above 255 is a documented overflow, repaired modulo 256
        minor = rng.choice([0, 1, 7, 42, 128, 254, 255, 256, 300, 1024])
        rows.append({
            "node_id": "ND{:05d}".format(len(rows)),
            "ino": obj["ino"],
            "node_kind": rng.choice(["fifo", "socket", "chardev", "blockdev"])
            if rng.random() < 0.1 else obj["kind"],
            "major": rng.choice([0, 1, 4, 8, 10, 179, 253]),
            "minor": minor,
        })
    # Edge case: a second record for one inode, settled by the smallest node id
    for i, row in enumerate(rng.sample(list(rows), min(90, len(rows)))):
        clone = dict(row)
        clone["node_id"] = "NE{:05d}".format(i)
        clone["minor"] = (clone["minor"] + 1) % 512
        clone["major"] = (clone["major"] + 2) % 256
        rows.append(clone)
    rng.shuffle(rows)
    return rows


def build_xattrs(seed: int, objects: list[dict]) -> list[dict]:
    rng = make_rng(seed, "xattrs")
    rows = []
    for obj in _latest_objects(objects):
        count = rng.choice([0, 1, 1, 2, 3, 4])
        for k in range(count):
            ns = rng.choice(XATTR_NAMESPACES)
            if ns == "system" and rng.random() < 0.45:
                name = rng.choice(ACL_NAMES)
            else:
                name = "{}.{}{}".format(ns, rng.choice(["tier", "origin", "seal",
                                                        "chk", "note", "map"]), k)
            if rng.random() < 0.07:
                name = name + "=x"
            rows.append({
                "xattr_id": "XA{:06d}".format(len(rows)),
                "ino": obj["ino"],
                "name": name,
                "value_len": rng.choice([0, 1, 8, 16, 31, 32, 64, 255, 512]),
                "gen": 1,
            })
    for i, row in enumerate(rng.sample(rows, min(180, len(rows)))):
        clone = dict(row)
        clone["xattr_id"] = "XB{:06d}".format(i)
        clone["gen"] = 2
        clone["value_len"] = rng.choice([0, 4, 24, 96])
        rows.append(clone)
    rng.shuffle(rows)
    return rows


def build_claims(seed: int, objects: list[dict]) -> list[dict]:
    rng = make_rng(seed, "claims")
    rows = []
    cid = 0
    for obj in _latest_objects(objects):
        roll = rng.random()
        count = 1
        if roll < 0.05:
            count = 0
        elif roll < 0.09:
            count = 2
        for k in range(count):
            rows.append({
                "claim_id": "C{:06d}".format(cid),
                "ino": obj["ino"],
                "set_name": rng.choice(["tier-move", "rebalance", "evacuate",
                                        "reclaim"]),
            })
            cid += 1
    return rows


def build_deadlines(seed: int, objects: list[dict]) -> list[dict]:
    rng = make_rng(seed, "deadlines")
    rows = []
    for obj in _latest_objects(objects):
        rows.append({
            "ino": obj["ino"],
            "deadline_window": rng.randrange(0, N_WINDOWS),
            # advisory: recorded in the plan and never acted on
            "class_override": rng.choice(["", "gold", "silver", "bronze", "tin"]),
        })
    return rows


def build_holds(seed: int, objects: list[dict]) -> list[dict]:
    rng = make_rng(seed, "holds")
    latest = _latest_objects(objects)
    rows = []
    for i in range(N_HOLDS):
        obj = rng.choice(latest)
        rows.append({
            "ino": obj["ino"],
            "reason": rng.choice(["legal", "audit", "backup", "snapshot",
                                  "replication"]),
            "active": rng.choice(["true", "true", "false"]),
        })
    return rows


def build_journal(seed: int, extents: list[dict], objects: list[dict],
                  pools: list[dict], barriers: list[dict]) -> list[dict]:
    """Checkpoint entries from the interrupted run."""
    rng = make_rng(seed, "journal")
    alloc = {p["pool_id"]: p["alloc_unit"] for p in pools}
    obj_pool = {o["ino"]: o["pool_id"] for o in _latest_objects(objects)}
    barrier = {}
    for row in barriers:
        cur = barrier.get(row["pool_id"])
        if cur is None or row["effective_seq"] > cur[0]:
            barrier[row["pool_id"]] = (row["effective_seq"], row["barrier_seq"])
    rows = []
    seen = set()
    for ext in extents:
        if ext["gen"] != 1:
            continue
        key = (ext["ino"], ext["ext_index"])
        if key in seen:
            continue
        seen.add(key)
        if rng.random() > 0.55:
            continue
        pool = obj_pool.get(ext["ino"])
        if pool is None:
            continue
        unit = alloc.get(pool, 4096)
        length = ext["length_raw"] * UNIT_BYTES[ext["length_unit"]]
        full = 0 if "hole" in ext["flags"] or "inline" in ext["flags"] else \
            -(-length // unit) * unit
        if pool not in barrier:
            continue
        bseq = barrier[pool][1]
        roll = rng.random()
        if roll < 0.56:
            committed = full
        elif roll < 0.68:
            committed = "NIL"                     # never started
        elif roll < 0.72:
            committed = 0                          # started and zeroed
        elif roll < 0.86:
            committed = max(0, full - unit)        # partial
        else:
            committed = full + unit                # overrun
        # Edge case: a sequence exactly at the barrier is durable, one past is not
        offset = rng.choice([-40, -5, -1, 0, 0, 1, 3, 25])
        rows.append({
            "ino": ext["ino"],
            "ext_index": ext["ext_index"],
            "bytes_committed": committed,
            "seq": bseq + offset,
            "pool_id": pool,
        })
    for row in rng.sample(rows, min(200, len(rows))):
        clone = dict(row)
        clone["seq"] = row["seq"] - rng.randrange(1, 30)
        clone["bytes_committed"] = 0
        rows.append(clone)
    # Edge case: two entries of one group share a sequence, so the committed size
    # decides between them, and an absent committed size counts as less than
    # any number rather than as zero
    for row in rng.sample(rows, min(120, len(rows))):
        twin = dict(row)
        roll = rng.random()
        if roll < 0.35:
            twin["bytes_committed"] = "NIL"
        elif roll < 0.70:
            twin["bytes_committed"] = 0
        else:
            held = row["bytes_committed"]
            twin["bytes_committed"] = held + 4096 if isinstance(held, int) else 4096
        rows.append(twin)
    rng.shuffle(rows)
    return rows


def build_mutations(seed: int, objects: list[dict], paths: list[dict],
                    extents: list[dict], barriers: list[dict]) -> list[dict]:
    rng = make_rng(seed, "mutations")
    latest = _latest_objects(objects)
    barrier = {}
    for row in barriers:
        cur = barrier.get(row["pool_id"])
        if cur is None or row["effective_seq"] > cur[0]:
            barrier[row["pool_id"]] = (row["effective_seq"], row["barrier_seq"])
    pool_of = {o["ino"]: o["pool_id"] for o in latest}
    by_ino: dict[int, list[dict]] = {}
    for row in extents:
        by_ino.setdefault(row["ino"], []).append(row)
    path_by_ino: dict[int, list[str]] = {}
    for row in paths:
        path_by_ino.setdefault(row["ino"], []).append(row["path_raw"])
    rows = []
    seq_used: dict[int, int] = {}
    for i in range(1800):
        obj = rng.choice(latest)
        pool = pool_of[obj["ino"]]
        if pool not in barrier:
            continue
        base = barrier[pool][1]
        # Edge case: at or below the barrier the event is already absorbed
        seq = base + rng.choice([-6, -2, 0, 0, 1, 2, 4, 9, 17, 33, 61])
        ordinal = seq_used.get(seq, 0)
        seq_used[seq] = ordinal + 1
        kind = rng.choice(MUTATION_WEIGHTS)
        row = {
            "seq": seq,
            "ordinal": ordinal,
            "kind": kind,
            "ino": obj["ino"],
            "path_a": "",
            "path_b": "",
            "arg_num": 0,
            "arg_alt": 0,
        }
        exts = by_ino.get(obj["ino"], [])
        if kind == "write" and exts:
            ext = rng.choice(exts)
            length = ext["length_raw"] * UNIT_BYTES[ext["length_unit"]]
            end = ext["offset"] + length
            # Edge case: a write that starts exactly at the end touches nothing
            choice = rng.random()
            if choice < 0.3:
                row["arg_num"] = end
            elif choice < 0.6:
                row["arg_num"] = max(0, end - 1)
            else:
                row["arg_num"] = max(0, ext["offset"] + length // 2)
            row["arg_alt"] = rng.choice([1, 512, 4096, 65536])
        elif kind == "truncate" and exts:
            ext = rng.choice(exts)
            length = ext["length_raw"] * UNIT_BYTES[ext["length_unit"]]
            end = ext["offset"] + length
            # Edge case: truncating exactly to the extent end invalidates nothing
            row["arg_num"] = end if rng.random() < 0.5 else max(0, end - 1)
        elif kind in ("unlink", "rename", "link"):
            known = path_by_ino.get(obj["ino"], [])
            row["path_a"] = rng.choice(known) if known else "/unknown/path"
            if kind == "rename":
                row["path_b"] = "/" + rng.choice(PLAIN_STEMS) + "/moved-{:05d}".format(i)
            if kind == "link":
                row["path_a"] = "/" + rng.choice(PLAIN_STEMS) + "/extra-{:05d}".format(i)
        elif kind == "setxattr":
            row["path_a"] = rng.choice(["user.tier9", "security.seal9",
                                        "system.posix_acl_access", "trusted.map9"])
            row["arg_num"] = rng.choice([0, 8, 32, 64])
        elif kind == "chmod":
            row["arg_num"] = rng.choice([0o644, 0o600, 0o755])
        elif kind == "chown":
            row["arg_num"] = rng.choice([0, 1000, 1002])
            row["arg_alt"] = rng.choice([0, 1000, 50])
        rows.append(row)
    # Edge case: events naming an inode that is not in the inventory are ignored
    for i in range(90):
        seq = BARRIER_BASE + rng.randrange(100, 900)
        ordinal = seq_used.get(seq, 0)
        seq_used[seq] = ordinal + 1
        rows.append({
            "seq": seq,
            "ordinal": ordinal,
            "kind": rng.choice(["write", "unlink", "chmod"]),
            "ino": 9000000 + i,
            "path_a": "/ghost/{:04d}".format(i),
            "path_b": "",
            "arg_num": 0,
            "arg_alt": 0,
        })
    # Edge case: an event on an inventoried inode whose pool is outside the pool
    # catalogue is ignored for unknown_pool, which is a separate outcome from
    # an inode the inventory never held
    orphan = sorted({o["ino"] for o in latest if pool_of[o["ino"]] not in barrier})
    for i in range(70):
        if not orphan:
            break
        ino = orphan[i % len(orphan)]
        seq = BARRIER_BASE + rng.randrange(100, 900)
        ordinal = seq_used.get(seq, 0)
        seq_used[seq] = ordinal + 1
        known = path_by_ino.get(ino, [])
        rows.append({
            "seq": seq,
            "ordinal": ordinal,
            "kind": rng.choice(["write", "unlink", "chmod", "rename"]),
            "ino": ino,
            "path_a": rng.choice(known) if known else "/stranded/{:04d}".format(i),
            "path_b": "/" + rng.choice(PLAIN_STEMS) + "/stranded-{:05d}".format(i),
            "arg_num": 0,
            "arg_alt": 0,
        })
    # Edge case: an unlink or a rename at or below the barrier is absorbed before its
    # path is ever tested, so the two outcomes are ordered against each other
    pooled = sorted({o["ino"] for o in latest if pool_of[o["ino"]] in barrier})
    for i in range(60):
        if not pooled:
            break
        ino = pooled[(i * 37) % len(pooled)]
        base = barrier[pool_of[ino]][1]
        seq = base + rng.choice([-9, -3, 0])
        ordinal = seq_used.get(seq, 0)
        seq_used[seq] = ordinal + 1
        rows.append({
            "seq": seq,
            "ordinal": ordinal,
            "kind": rng.choice(["unlink", "rename"]),
            "ino": ino,
            "path_a": "/stale/{:05d}/{}".format(i, rng.choice(LEAF_STEMS)),
            "path_b": "/" + rng.choice(PLAIN_STEMS) + "/absorbed-{:05d}".format(i),
            "arg_num": 0,
            "arg_alt": 0,
        })
    rng.shuffle(rows)
    return rows


def build_all(seed: int) -> dict:
    pools = build_pools(seed)
    barriers = build_barriers(seed, pools)
    objects = build_objects(seed, pools)
    paths = build_paths(seed, objects)
    extents = build_extents(seed, objects, pools)
    _resize_objects(seed, objects, extents)
    data = {
        "pools": pools,
        "barriers": barriers,
        "device_capacity": build_device_capacity(seed),
        "device_geometry": build_device_geometry(seed),
        "windows": build_windows(seed),
        "placement_map": build_placement_map(seed, pools),
        "objects": objects,
        "paths": paths,
        "extents": extents,
        "symlinks": build_symlinks(seed, objects, paths),
        "special": build_special(seed, objects),
        "xattrs": build_xattrs(seed, objects),
        "claims": build_claims(seed, objects),
        "deadlines": build_deadlines(seed, objects),
        "holds": build_holds(seed, objects),
        "journal": build_journal(seed, extents, objects, pools, barriers),
        "mutations": build_mutations(seed, objects, paths, extents, barriers),
    }
    add_tiebreak_witnesses(data)
    return data


def add_tiebreak_witnesses(data: dict) -> None:
    """Fixed witnesses for the inode and kind tie-breaks the random estate never
    reaches. Rows are appended higher inode first and unlink before rename, so a
    planner that keeps whichever row it met first lands on the wrong side."""
    pool, busy, roomy, domain = "P950", "DZ0", "DZ1", "SDZ"
    data["pools"].append(dict(zip(F_POOL, (pool, 4096, 9, "r12"))))
    data["barriers"].append(dict(zip(F_BARRIER, (pool, 0, BARRIER_BASE, 1))))
    # Edge case: the busy device holds one of its two tin objects and no more, so
    # it sheds exactly one of them into a device of the same share domain
    for device, capacity, spill in ((busy, 98304, roomy), (roomy, 1073741824, busy)):
        data["device_capacity"].append(dict(zip(F_DEVCAP,
            (device, 0, capacity, "B", 0, "B", 0, 1))))
        data["device_geometry"].append(dict(zip(F_DEVGEO,
            (device + ".r0", device, 0, domain, spill, "true", 4096, 1))))
        for window in range(2):
            data["windows"].append(dict(zip(F_WINDOW, (device, window, 1048576, "B", 4))))
    for index, (cls, device) in enumerate((("tin", busy), ("gold", roomy))):
        data["placement_map"].append(dict(zip(F_PLACE, ("RZ{}".format(index), cls, pool, device))))

    merge = "/vault/réseau-merge"
    pair = "/spool/café-pair"
    objects = (
        # Edge case: one canonical path on two inodes; the path index gives it to
        # the lower inode, a regular file, so a symlink aimed at it ends inside
        (700101, "symlink", 0, "gold", [(to_nfd(merge), "nfd")]),
        (700100, "regular", 0, "gold", [(merge, "nfc")]),
        (700102, "symlink", 0, "gold", [("/vault/merge-link", "nfc")]),
        # Edge case: two tin objects on one canonical path and one physical
        # identifier tie on class, attributed bytes and path, so the inode decides
        # the copy owner, the shed object, the work set order and the cutover order
        (700111, "regular", 131072, "tin", [(to_nfd(pair), "nfd")]),
        (700110, "regular", 69632, "tin", [(pair, "nfc")]),
        # Edge case: a rename and an unlink of one path share a sequence and an
        # ordinal, so the kind decides which of them finds the path
        (700120, "regular", 65536, "gold", [("/queue/nõde-swap", "nfc"),
                                            ("/links/nõde-swap", "nfc")]),
    )
    for ordinal_base, (ino, kind, size, cls, records) in enumerate(objects):
        data["objects"].append(dict(zip(F_OBJECT,
            (ino, kind, size, "B", "0777" if kind == "symlink" else "0644", 0, 0,
             1735689600000000000 + ino, cls, pool, len(records), "live", 1))))
        for k, (raw, form) in enumerate(records):
            data["paths"].append(dict(zip(F_PATH, (ino, raw, 7000000 + ordinal_base * 10 + k, form))))
        data["claims"].append(dict(zip(F_CLAIM, ("CZ{}".format(ino), ino, "rebalance"))))
        data["deadlines"].append(dict(zip(F_DEADLINE, (ino, 3, ""))))
    data["symlinks"].append(dict(zip(F_SYMLINK, (700101, "/outside/merge", "nfc"))))
    data["symlinks"].append(dict(zip(F_SYMLINK, (700102, merge, "nfc"))))
    for ino, index, offset, length, physical, flags in (
            (700111, 0, 0, 65536, "PV7001110", "none"),
            (700111, 1, 65536, 65536, "PX90001", "shared"),
            (700110, 0, 0, 4096, "PV7001100", "hole"),
            (700110, 1, 4096, 65536, "PX90001", "shared"),
            (700120, 0, 0, 65536, "PV7001200", "none")):
        data["extents"].append(dict(zip(F_EXTENT,
            (ino, index, offset, length, "B", physical, flags, 1))))
    for seq, kind, ino, path_a, path_b, arg_num in (
            (BARRIER_BASE + 20, "unlink", 700120, "/queue/nõde-swap", "", 0),
            (BARRIER_BASE + 20, "rename", 700120, "/queue/nõde-swap", "/queue/nõde-swapped", 0),
            # Edge case: two events share a sequence, an ordinal and a kind, so the
            # inode decides their order
            (BARRIER_BASE + 30, "chmod", 700111, "", "", 0o600),
            (BARRIER_BASE + 30, "chmod", 700110, "", "", 0o600)):
        data["mutations"].append(dict(zip(F_MUTATION,
            (seq, 0, kind, ino, path_a, path_b, arg_num, 0))))


def build_edge(seed: int) -> dict:
    """Keep the full estate, adding isolated, non-random boundary witnesses."""
    data = build_all(seed)
    schedules = {
        "ZE0": (65536, [65536, 73728], 1),
        "ZE1": (65536, [65536, 32768, 65536], 1),
        "ZE2": (4096, [32768], 1),
        "ZE3": (4096, [1048576], 64),
    }
    for index, (device, (unit, budgets, descriptors)) in enumerate(schedules.items()):
        pool = "PE{}".format(index)
        data["pools"].append(dict(zip(F_POOL, (pool, 4096, 9, "edge"))))
        data["barriers"].append(dict(zip(F_BARRIER, (pool, 0, 100, 1))))
        data["device_capacity"].append(dict(zip(F_DEVCAP,
            (device, 0, 1073741824, "B", 0, "B", 0, 1))))
        data["device_geometry"].append(dict(zip(F_DEVGEO,
            (device + ".r0", device, 0, device, device, "true", unit, 1))))
        for window, budget in enumerate(budgets):
            data["windows"].append(dict(zip(F_WINDOW,
                (device, window, budget, "B", descriptors))))
        data["placement_map"].append(dict(zip(F_PLACE,
            ("RE{}".format(index), "gold", pool, device))))

    regular = [(800000, "PE0", [139264]), (800001, "PE1", [98304]),
               (800002, "PE2", [8192, 8192]), (800003, "PE2", [4096])]
    regular += [(ino, "PE3", [8192]) for ino in range(800010, 800019)]
    for ino, pool, lengths in regular:
        data["objects"].append(dict(zip(F_OBJECT,
            (ino, "regular", sum(lengths), "B", "0644", 0, 0, ino,
             "gold", pool, 1, "live", 1))))
        raw_path = "/edge/café-{}".format(ino)
        form = "nfc" if ino % 2 == 0 else "nfd"
        data["paths"].append(dict(zip(F_PATH,
            (ino, raw_path if form == "nfc" else to_nfd(raw_path), ino, form))))
        data["claims"].append(dict(zip(F_CLAIM, ("CE{}".format(ino), ino, "tier-move"))))
        offset = 0
        for index, length in enumerate(lengths):
            flags = "inline" if ino == 800018 else "none"
            data["extents"].append(dict(zip(F_EXTENT,
                (ino, index, offset, length, "B", "VE{}-{}".format(ino, index), flags, 1))))
            offset += length
    # Physical-class precedence: each extent carries two of hole, inline and unwritten.
    data["objects"].append(dict(zip(F_OBJECT,
        (800030, "regular", 12288, "B", "0644", 0, 0, 800030, "gold", "PE3", 1, "live", 1))))
    data["paths"].append(dict(zip(F_PATH, (800030, "/edge/flags-800030", 800030, "nfc"))))
    data["claims"].append(dict(zip(F_CLAIM, ("CE800030", 800030, "tier-move"))))
    for index, flags in enumerate(("hole,unwritten", "unwritten,inline", "inline,hole")):
        data["extents"].append(dict(zip(F_EXTENT,
            (800030, index, index * 4096, 4096, "B", "VE800030-{}".format(index), flags, 1))))
    # NIL, zero, inclusive barrier, future-only, no group, tie, newer NIL, redirty, zero expected.
    for ino, committed, seq in ((800010, "NIL", 100), (800011, 0, 100),
            (800012, 8192, 100), (800013, 8192, 101),
            (800015, "NIL", 100), (800015, 0, 100),
            (800016, 8192, 99), (800016, "NIL", 100),
            (800017, 8192, 100), (800018, 0, 100)):
        data["journal"].append(dict(zip(F_JOURNAL, (ino, 0, committed, seq, "PE3"))))
    for ino, seq, offset in ((800012, 100, 0), (800012, 101, 8192), (800017, 101, 8191)):
        data["mutations"].append(dict(zip(F_MUTATION,
            (seq, ino, "write", ino, "", "", offset, 1))))

    targets = {810000: "/edge/link-810000", 810001: "/edge/link-810002",
               810002: "/edge/link-810001",
               810030: "/edge/café-800010", 810031: to_nfd("/edge/café-800010")}
    for ino in range(810010, 810019):
        targets[ino] = "/edge/link-{}".format(ino + 1) if ino < 810018 else "/edge/café-800010"
    for ino, length in ((810040, 58), (810041, 59), (810042, 60)):
        targets[ino] = "/" + "t" * (length - 1)
    # An eight-link ring: hop eight is reached exactly when the next target would repeat.
    for k in range(8):
        targets[810050 + k] = "/edge/link-{}".format(810050 + (k + 1) % 8)
    for ino, target in targets.items():
        data["objects"].append(dict(zip(F_OBJECT,
            (ino, "symlink", 0, "B", "0777", 0, 0, ino, "gold", "PE3", 1, "live", 1))))
        data["paths"].append(dict(zip(F_PATH, (ino, "/edge/link-{}".format(ino), ino, "nfc"))))
        data["claims"].append(dict(zip(F_CLAIM, ("CE{}".format(ino), ino, "tier-move"))))
        form = "nfc" if unicodedata.is_normalized("NFC", target) else "nfd"
        data["symlinks"].append(dict(zip(F_SYMLINK, (ino, target, form))))

    # Overcommitted devices whose spill device is itself or outside the catalogue shed nothing.
    for index, (device, spill) in enumerate((("ZE4", "ZE4"), ("ZE5", "ZX9")), start=4):
        pool = "PE{}".format(index)
        data["pools"].append(dict(zip(F_POOL, (pool, 4096, 9, "edge"))))
        data["barriers"].append(dict(zip(F_BARRIER, (pool, 0, 100, 1))))
        data["device_capacity"].append(dict(zip(F_DEVCAP,
            (device, 0, 65536, "B", 0, "B", 0, 1))))
        data["device_geometry"].append(dict(zip(F_DEVGEO,
            (device + ".r0", device, 0, device, spill, "true", 4096, 1))))
        data["windows"].append(dict(zip(F_WINDOW, (device, 0, 1048576, "B", 64))))
        data["placement_map"].append(dict(zip(F_PLACE,
            ("RE{}".format(index), "gold", pool, device))))
        for ino in (800020 + 2 * (index - 4), 800021 + 2 * (index - 4)):
            data["objects"].append(dict(zip(F_OBJECT,
                (ino, "regular", 65536, "B", "0644", 0, 0, ino,
                 "gold", pool, 1, "live", 1))))
            data["paths"].append(dict(zip(F_PATH,
                (ino, "/edge/spill-{}".format(ino), ino, "nfc"))))
            data["claims"].append(dict(zip(F_CLAIM, ("CE{}".format(ino), ino, "tier-move"))))
            data["extents"].append(dict(zip(F_EXTENT,
                (ino, 0, 0, 65536, "B", "VE{}-0".format(ino), "none", 1))))
    # Edge case: only the exact token `true` makes a hold notice active; the class
    # is the one field the contract case-folds, so `TRUE` and `True` are not active
    for ino, reason, active in ((800000, "legal", "true"), (800000, "audit", "TRUE"),
                                (800000, "backup", "True"), (800001, "snapshot", "TRUE")):
        data["holds"].append(dict(zip(F_HOLD, (ino, reason, active))))
    return data


# ---------------------------------------------------------------- writers

NIL = "NIL"
BS = chr(92)


def _cell(value) -> str:
    if value is None:
        return NIL
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _csvish(rows, fields, delim, quote='"') -> str:
    out = [delim.join(fields)]
    for row in rows:
        cells = []
        for f in fields:
            text = _cell(row[f])
            if text == "" or delim in text or quote in text or "\n" in text:
                text = quote + text.replace(quote, quote + quote) + quote
            cells.append(text)
        out.append(delim.join(cells))
    return "\n".join(out) + "\n"


def w_csv(rows, fields):
    return _csvish(rows, fields, ",")


def w_psv(rows, fields):
    return _csvish(rows, fields, "|")


def w_ssv(rows, fields):
    return _csvish(rows, fields, " ")


def w_tsv(rows, fields):
    def esc(text):
        return (text.replace(BS, BS + BS).replace("\t", BS + "t")
                .replace("\n", BS + "n"))
    out = ["\t".join(fields)]
    for row in rows:
        out.append("\t".join(esc(_cell(row[f])) for f in fields))
    return "\n".join(out) + "\n"


def w_fixed(rows, fields):
    widths = {}
    for f in fields:
        widths[f] = max(len(f), max((len(_cell(r[f])) for r in rows), default=0)) + 2
    out = ["".join(f.ljust(widths[f]) for f in fields).rstrip()]
    for row in rows:
        out.append("".join(_cell(row[f]).ljust(widths[f]) for f in fields).rstrip())
    return "\n".join(out) + "\n"


def w_json(rows, fields):
    payload = {"records": [{f: r[f] for f in fields} for r in rows]}
    return json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def w_jsonl(rows, fields):
    return "".join(
        json.dumps({f: r[f] for f in fields}, ensure_ascii=False, sort_keys=False) + "\n"
        for r in rows
    )


def _toml_scalar(value) -> str:
    if value is None:
        return '"' + NIL + '"'
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    text = str(value).replace(BS, BS + BS).replace('"', BS + '"')
    return '"' + text + '"'


def w_toml(rows, fields):
    out = []
    for row in rows:
        out.append("[[record]]")
        for f in fields:
            out.append("{} = {}".format(f, _toml_scalar(row[f])))
        out.append("")
    return "\n".join(out) + "\n"


def w_ini(rows, fields):
    out = []
    key = fields[0]
    for row in rows:
        out.append("[{}]".format(_cell(row[key])))
        for f in fields[1:]:
            out.append("{} = {}".format(f, _cell(row[f])))
        out.append("")
    return "\n".join(out) + "\n"


def w_properties(rows, fields):
    out = []
    key = fields[0]
    for row in rows:
        ident = _cell(row[key])
        for f in fields[1:]:
            text = _cell(row[f]).replace(BS, BS + BS).replace(":", BS + ":") \
                .replace("=", BS + "=")
            out.append("{}.{}={}".format(ident, f, text))
    return "\n".join(out) + "\n"


def w_rfc822(rows, fields):
    out = []
    for row in rows:
        for f in fields:
            header = "-".join(part.capitalize() for part in f.split("_"))
            out.append("{}: {}".format(header, _cell(row[f])))
        out.append("")
    return "\n".join(out) + "\n"


def w_logfmt(rows, fields):
    out = []
    for row in rows:
        parts = []
        for f in fields:
            text = _cell(row[f])
            if text == "" or " " in text or '"' in text:
                text = '"' + text.replace(BS, BS + BS).replace('"', BS + '"') + '"'
            parts.append("{}={}".format(f, text))
        out.append(" ".join(parts))
    return "\n".join(out) + "\n"


def w_sexp(rows, fields):
    out = []
    for row in rows:
        parts = []
        for f in fields:
            text = _cell(row[f]).replace(BS, BS + BS).replace('"', BS + '"')
            parts.append('({} "{}")'.format(f, text))
        out.append("(record " + " ".join(parts) + ")")
    return "\n".join(out) + "\n"


def w_rfc5424(rows, fields):
    out = []
    key = fields[0]
    for i, row in enumerate(rows):
        sd = " ".join(
            '{}="{}"'.format(f, _cell(row[f]).replace(BS, BS + BS)
                             .replace('"', BS + '"').replace("]", BS + "]"))
            for f in fields
        )
        out.append(
            "<134>1 2026-02-01T00:00:00.000Z strata-host relocd - "
            "{} [strata@41762 {}] record {}".format(_cell(row[key]), sd, i)
        )
    return "\n".join(out) + "\n"


WRITERS = {
    "csv": w_csv, "tsv": w_tsv, "psv": w_psv, "ssv": w_ssv, "fixed": w_fixed,
    "json": w_json, "jsonl": w_jsonl, "toml": w_toml, "ini": w_ini,
    "properties": w_properties, "rfc822": w_rfc822, "logfmt": w_logfmt,
    "sexp": w_sexp, "rfc5424": w_rfc5424,
}


# ---------------------------------------------------------------- emission

def _shard(rows: list[dict], count: int) -> list[list[dict]]:
    size = (len(rows) + count - 1) // count
    return [rows[i * size:(i + 1) * size] for i in range(count)]


F_POOL = ["pool_id", "alloc_unit", "root_depth_cap", "region"]
F_BARRIER = ["pool_id", "rev", "barrier_seq", "effective_seq"]
F_DEVCAP = ["device_id", "rev", "capacity_raw", "capacity_unit",
            "existing_used_raw", "existing_used_unit", "reserve_ppm",
            "effective_seq"]
F_DEVGEO = ["slot_id", "device_id", "rev", "share_domain", "spill_device",
            "online", "alloc_unit", "effective_seq"]
F_WINDOW = ["device_id", "window_index", "io_budget_raw", "io_budget_unit",
            "descriptor_budget"]
F_PLACE = ["route_id", "class", "pool_id", "device_id"]
F_OBJECT = ["ino", "kind", "size_raw", "size_unit", "mode_raw", "uid", "gid",
            "mtime_ns", "class_raw", "pool_id", "link_count", "state", "gen"]
F_PATH = ["ino", "path_raw", "ordinal", "form"]
F_EXTENT = ["ino", "ext_index", "offset", "length_raw", "length_unit",
            "physical_id", "flags", "gen"]
F_SYMLINK = ["ino", "target_raw", "form"]
F_SPECIAL = ["node_id", "ino", "node_kind", "major", "minor"]
F_XATTR = ["xattr_id", "ino", "name", "value_len", "gen"]
F_CLAIM = ["claim_id", "ino", "set_name"]
F_DEADLINE = ["ino", "deadline_window", "class_override"]
F_HOLD = ["ino", "reason", "active"]
F_JOURNAL = ["ino", "ext_index", "bytes_committed", "seq", "pool_id"]
F_MUTATION = ["seq", "ordinal", "kind", "ino", "path_a", "path_b",
              "arg_num", "arg_alt"]

# (basename, format, table, field list, shard index, shard count)
LAYOUT = [
    ("estate__pools.json", "json", "pools", F_POOL, 0, 1),
    ("estate__barriers-a.toml", "toml", "barriers", F_BARRIER, 0, 2),
    ("estate__barriers-b.csv", "csv", "barriers", F_BARRIER, 1, 2),

    ("target__capacity.csv", "csv", "device_capacity", F_DEVCAP, 0, 1),
    ("target__geometry.ini", "ini", "device_geometry", F_DEVGEO, 0, 1),
    ("target__windows-a.csv", "csv", "windows", F_WINDOW, 0, 3),
    ("target__windows-b.tsv", "tsv", "windows", F_WINDOW, 1, 3),
    ("target__windows-c.psv", "psv", "windows", F_WINDOW, 2, 3),

    ("routing__map-a.csv", "csv", "placement_map", F_PLACE, 0, 4),
    ("routing__map-b.ini", "ini", "placement_map", F_PLACE, 1, 4),
    ("routing__map-c.properties", "properties", "placement_map", F_PLACE, 2, 4),
    ("routing__map-d.tsv", "tsv", "placement_map", F_PLACE, 3, 4),

    ("inode__table-a.csv", "csv", "objects", F_OBJECT, 0, 6),
    ("inode__table-b.tsv", "tsv", "objects", F_OBJECT, 1, 6),
    ("inode__table-c.psv", "psv", "objects", F_OBJECT, 2, 6),
    ("inode__table-d.jsonl", "jsonl", "objects", F_OBJECT, 3, 6),
    ("inode__table-e.fixed", "fixed", "objects", F_OBJECT, 4, 6),
    ("inode__table-f.logfmt", "logfmt", "objects", F_OBJECT, 5, 6),

    ("namespace__paths-a.csv", "csv", "paths", F_PATH, 0, 4),
    ("namespace__paths-b.tsv", "tsv", "paths", F_PATH, 1, 4),
    ("namespace__paths-c.ssv", "ssv", "paths", F_PATH, 2, 4),
    ("namespace__paths-d.jsonl", "jsonl", "paths", F_PATH, 3, 4),

    ("layout__extents-a.csv", "csv", "extents", F_EXTENT, 0, 7),
    ("layout__extents-b.tsv", "tsv", "extents", F_EXTENT, 1, 7),
    ("layout__extents-c.psv", "psv", "extents", F_EXTENT, 2, 7),
    ("layout__extents-d.jsonl", "jsonl", "extents", F_EXTENT, 3, 7),
    ("layout__extents-e.logfmt", "logfmt", "extents", F_EXTENT, 4, 7),
    ("layout__extents-f.ssv", "ssv", "extents", F_EXTENT, 5, 7),
    ("layout__extents-g.fixed", "fixed", "extents", F_EXTENT, 6, 7),

    ("namespace__symlinks-a.tsv", "tsv", "symlinks", F_SYMLINK, 0, 2),
    ("namespace__symlinks-b.jsonl", "jsonl", "symlinks", F_SYMLINK, 1, 2),

    ("nodes__special-a.csv", "csv", "special", F_SPECIAL, 0, 2),
    ("nodes__special-b.properties", "properties", "special", F_SPECIAL, 1, 2),

    ("metadata__xattrs-a.properties", "properties", "xattrs", F_XATTR, 0, 4),
    ("metadata__xattrs-b.jsonl", "jsonl", "xattrs", F_XATTR, 1, 4),
    ("metadata__xattrs-c.csv", "csv", "xattrs", F_XATTR, 2, 4),
    ("metadata__xattrs-d.tsv", "tsv", "xattrs", F_XATTR, 3, 4),

    ("workset__claims-a.psv", "psv", "claims", F_CLAIM, 0, 2),
    ("workset__claims-b.jsonl", "jsonl", "claims", F_CLAIM, 1, 2),

    ("workset__deadlines-a.psv", "psv", "deadlines", F_DEADLINE, 0, 2),
    ("workset__deadlines-b.logfmt", "logfmt", "deadlines", F_DEADLINE, 1, 2),

    ("workset__holds-a.ssv", "ssv", "holds", F_HOLD, 0, 2),
    ("workset__holds-b.rfc822", "rfc822", "holds", F_HOLD, 1, 2),

    ("checkpoint__journal-a.csv", "csv", "journal", F_JOURNAL, 0, 4),
    ("checkpoint__journal-b.jsonl", "jsonl", "journal", F_JOURNAL, 1, 4),
    ("checkpoint__journal-c.logfmt", "logfmt", "journal", F_JOURNAL, 2, 4),
    ("checkpoint__journal-d.rfc5424", "rfc5424", "journal", F_JOURNAL, 3, 4),

    ("activity__mutations-a.rfc5424", "rfc5424", "mutations", F_MUTATION, 0, 4),
    ("activity__mutations-b.logfmt", "logfmt", "mutations", F_MUTATION, 1, 4),
    ("activity__mutations-c.jsonl", "jsonl", "mutations", F_MUTATION, 2, 4),
    ("activity__mutations-d.sexp", "sexp", "mutations", F_MUTATION, 3, 4),
]


def emit_corpus(seed: int, outdir: Path) -> dict[str, int]:
    data = build_all(seed)
    outdir.mkdir(parents=True, exist_ok=True)
    shards: dict[tuple, list] = {}
    counts: dict[str, int] = {}
    for name, fmt, table, fields, idx, total in LAYOUT:
        key = (table, total)
        if key not in shards:
            shards[key] = _shard(data[table], total)
        rows = shards[key][idx]
        text = WRITERS[fmt](rows, fields)
        (outdir / name).write_text(text, encoding="utf-8", newline="\n")
        counts[name] = len(rows)
    return counts
'''

_REF_SRC = r'''
#!/usr/bin/env python3
"""stratactl: the STRATA relocation planner.

Reads a relocation corpus directory, derives the resumable relocation plan in
dependency order, and writes the twenty-four declared artifacts plus a copy of
itself into the output directory it is handed.

Standard library only. Deterministic. No network use.

Usage: stratactl.py CORPUS_DIR OUT_DIR
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
import sys
import unicodedata
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_POLICY = 3

NIL = "NIL"
BS = chr(92)

DEFAULT_ALLOC_UNIT = 4096
FAST_SYMLINK_MAX = 59
MAX_SYMLINK_HOPS = 8
MAX_SPILL_HOPS = 4
MAX_EVICTION_ROUNDS = 8
ACL_NAMES = ("system.posix_acl_access", "system.posix_acl_default")
FLAG_ORDER = ("hole", "unwritten", "inline", "shared", "sealed")
CLASS_RANK = {"gold": 1, "silver": 2, "bronze": 3, "tin": 4}
UNIT_BYTES = {
    "B": 1, "KiB": 1024, "MiB": 1048576, "GiB": 1073741824,
    "kB": 1000, "MB": 1000000, "GB": 1000000000, "s": 512, "bl": 4096,
}
OP_RANK = {
    "mkdir": 1, "mknod": 2, "mkfifo": 2, "bind": 2, "symlink": 3, "link": 4,
    "reflink": 5, "fallocate": 6, "setxattr": 7, "chown": 8, "chmod": 9,
    "utimes": 10,
}

ARTIFACT_NAMES = [
    "object_inventory.jsonl",
    "device_topology.json",
    "extent_map.tsv",
    "symlink_topology.jsonl",
    "mutation_replay.jsonl",
    "scope_resolution.csv",
    "link_clusters.jsonl",
    "resume_state.jsonl",
    "xattr_ledger.csv",
    "special_nodes.tsv",
    "placement.csv",
    "sharing_expansion.jsonl",
    "allocation_projection.csv",
    "delta_workset.tsv",
    "metadata_workset.jsonl",
    "window_schedule.tsv",
    "split_ledger.jsonl",
    "descriptor_budget.csv",
    "cutover_sequence.txt",
    "rollback_plan.jsonl",
    "conservation.json",
    "cli_contract.json",
]


# ------------------------------------------------------------------ parsing

def _untyped(value):
    return None if value == NIL else value


def _split_quoted(line, delim):
    cells = []
    buf = []
    i = 0
    inq = False
    while i < len(line):
        ch = line[i]
        if inq:
            if ch == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    buf.append('"')
                    i += 2
                    continue
                inq = False
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue
        if ch == '"' and not buf:
            inq = True
            i += 1
            continue
        if ch == delim:
            cells.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    cells.append("".join(buf))
    return cells


def _body_lines(text):
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def p_delimited(text, delim):
    lines = _body_lines(text)
    header = _split_quoted(lines[0], delim)
    out = []
    for line in lines[1:]:
        cells = _split_quoted(line, delim)
        out.append({h: _untyped(c) for h, c in zip(header, cells)})
    return out


def p_csv(text):
    return p_delimited(text, ",")


def p_psv(text):
    return p_delimited(text, "|")


def p_ssv(text):
    return p_delimited(text, " ")


def _tsv_unescape(cell):
    out = []
    i = 0
    mapping = {"t": "\t", "n": "\n", BS: BS}
    while i < len(cell):
        if cell[i] == BS and i + 1 < len(cell):
            out.append(mapping.get(cell[i + 1], cell[i + 1]))
            i += 2
            continue
        out.append(cell[i])
        i += 1
    return "".join(out)


def p_tsv(text):
    lines = _body_lines(text)
    header = lines[0].split("\t")
    return [
        {h: _untyped(_tsv_unescape(c)) for h, c in zip(header, line.split("\t"))}
        for line in lines[1:]
    ]


def p_fixed(text):
    lines = _body_lines(text)
    head = lines[0]
    starts = [i for i in range(len(head))
              if head[i] != " " and (i == 0 or head[i - 1] == " ")]
    names = []
    bounds = []
    for n, s in enumerate(starts):
        e = starts[n + 1] if n + 1 < len(starts) else len(head)
        names.append(head[s:e].strip())
        bounds.append((s, e))
    out = []
    for line in lines[1:]:
        row = {}
        for n, (s, e) in enumerate(bounds):
            chunk = line[s:] if n + 1 == len(bounds) else line[s:e]
            row[names[n]] = _untyped(chunk.strip())
        out.append(row)
    return out


def p_json(text):
    return [{k: _untyped(v) for k, v in row.items()}
            for row in json.loads(text)["records"]]


def p_jsonl(text):
    return [{k: _untyped(v) for k, v in json.loads(ln).items()}
            for ln in text.split("\n") if ln.strip()]


def _backslash_unescape(raw):
    out = []
    i = 0
    while i < len(raw):
        if raw[i] == BS and i + 1 < len(raw):
            out.append(raw[i + 1])
            i += 2
            continue
        out.append(raw[i])
        i += 1
    return "".join(out)


def p_toml(text):
    out = []
    cur = None
    for line in text.split("\n"):
        line = line.strip()
        if line == "[[record]]":
            cur = {}
            out.append(cur)
            continue
        if not line or cur is None or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        raw = raw.strip()
        if raw.startswith('"'):
            cur[key.strip()] = _untyped(_backslash_unescape(raw[1:-1]))
        else:
            cur[key.strip()] = int(raw)
    return out


def p_ini(text, key_name):
    out = []
    cur = None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            cur = {key_name: line[1:-1]}
            out.append(cur)
            continue
        if not line or cur is None or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        cur[key.strip()] = _untyped(raw.strip())
    return out


def p_properties(text, key_name):
    groups = {}
    order = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        left, _, raw = line.partition("=")
        ident, _, field = left.rpartition(".")
        if ident not in groups:
            groups[ident] = {key_name: ident}
            order.append(ident)
        groups[ident][field] = _untyped(_backslash_unescape(raw))
    return [groups[k] for k in order]


def p_rfc822(text):
    out = []
    cur = {}
    for line in text.split("\n"):
        if not line.strip():
            if cur:
                out.append(cur)
                cur = {}
            continue
        head, _, raw = line.partition(":")
        cur[head.strip().lower().replace("-", "_")] = _untyped(raw.strip())
    if cur:
        out.append(cur)
    return out


def p_logfmt(text):
    out = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        row = {}
        i = 0
        while i < len(line):
            eq = line.find("=", i)
            if eq < 0:
                break
            key = line[i:eq]
            i = eq + 1
            if i < len(line) and line[i] == '"':
                buf = []
                i += 1
                while i < len(line):
                    if line[i] == BS and i + 1 < len(line):
                        buf.append(line[i + 1])
                        i += 2
                        continue
                    if line[i] == '"':
                        i += 1
                        break
                    buf.append(line[i])
                    i += 1
                row[key] = _untyped("".join(buf))
            else:
                sp = line.find(" ", i)
                sp = len(line) if sp < 0 else sp
                row[key] = _untyped(line[i:sp])
                i = sp
            while i < len(line) and line[i] == " ":
                i += 1
        out.append(row)
    return out


_SEXP_PAIR = re.compile(r'\((\w+) "((?:[^"\\]|\\.)*)"\)')


def p_sexp(text):
    out = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        out.append({k: _untyped(_backslash_unescape(v))
                    for k, v in _SEXP_PAIR.findall(line)})
    return out


_SD_PAIR = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')


def p_rfc5424(text):
    out = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        start = line.find("[strata@41762 ")
        end = line.rfind("]")
        if start < 0 or end < 0:
            continue
        body = line[start + 14:end]
        out.append({k: _untyped(_backslash_unescape(v))
                    for k, v in _SD_PAIR.findall(body)})
    return out


READERS = {
    "csv": p_csv, "psv": p_psv, "ssv": p_ssv, "tsv": p_tsv, "fixed": p_fixed,
    "json": p_json, "jsonl": p_jsonl, "toml": p_toml, "rfc822": p_rfc822,
    "logfmt": p_logfmt, "sexp": p_sexp, "rfc5424": p_rfc5424,
}
SCHEMAS = {
    "pools": "pool_id alloc_unit root_depth_cap region",
    "barriers": "pool_id rev barrier_seq effective_seq",
    "device_capacity": "device_id rev capacity_raw capacity_unit existing_used_raw existing_used_unit reserve_ppm effective_seq",
    "device_geometry": "slot_id device_id rev share_domain spill_device online alloc_unit effective_seq",
    "windows": "device_id window_index io_budget_raw io_budget_unit descriptor_budget",
    "routes": "route_id class pool_id device_id",
    "objects": "ino kind size_raw size_unit mode_raw uid gid mtime_ns class_raw pool_id link_count state gen",
    "paths": "ino path_raw ordinal form",
    "extents": "ino ext_index offset length_raw length_unit physical_id flags gen",
    "symlinks": "ino target_raw form",
    "special": "node_id ino node_kind major minor",
    "xattrs": "xattr_id ino name value_len gen",
    "claims": "claim_id ino set_name",
    "deadlines": "ino deadline_window class_override",
    "holds": "ino reason active",
    "journal": "ino ext_index bytes_committed seq pool_id",
    "mutations": "seq ordinal kind ino path_a path_b arg_num arg_alt",
}


def decode_shard(text):
    """Recognise syntax first, then require one complete schema for every row."""
    body = text.lstrip()
    if not body:
        return None
    first = body.split("\n", 1)[0]
    keyed = False
    if body.startswith("{"):
        # A one-line container and a one-row JSONL shard are distinct encodings.
        value, end = json.JSONDecoder().raw_decode(body)
        rows = p_json(body) if "records" in value and not body[end:].strip() else p_jsonl(body)
    elif body.startswith("[[record]]"):
        rows = p_toml(body)
    elif body.startswith("["):
        keyed = True
        rows = p_ini(body, "@key")
    elif body.startswith("(record "):
        rows = p_sexp(body)
    elif re.match(r"<\d+>1 ", body):
        rows = p_rfc5424(body)
    elif re.match(r"[A-Za-z][A-Za-z-]*: ", body):
        rows = p_rfc822(body)
    elif re.match(r"[^=\n]+\.[a-z_]+=", body):
        keyed = True
        rows = p_properties(body, "@key")
    elif re.match(r"[a-z_]+=", body):
        rows = p_logfmt(body)
    else:
        rows = None
        for delimiter, reader in ((",", p_csv), ("\t", p_tsv), ("|", p_psv), (" ", p_ssv)):
            if any(first.split(delimiter) == fields.split() for fields in SCHEMAS.values()):
                rows = reader(body)
                break
        if rows is None:
            if not any(first.split() == fields.split() for fields in SCHEMAS.values()):
                return None
            rows = p_fixed(body)
    if not rows:
        return None
    keys = set(rows[0])
    matches = []
    for table, fields in SCHEMAS.items():
        names = fields.split()
        signature = set(names[1:]) | {"@key"} if keyed else set(names)
        if keys == signature:
            matches.append((table, names[0]))
    if len(matches) != 1 or any(set(row) != keys for row in rows):
        raise ValueError("shard does not have one complete table schema", sorted(keys))
    table, first_field = matches[0]
    decoded = []
    for row in rows:
        record = {first_field if k == "@key" else k: _untyped(v) for k, v in row.items()}
        if table == "journal" and record["bytes_committed"] is not None:
            value = record["bytes_committed"]
            if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)):
                raise ValueError("invalid checkpoint byte count", value)
            record["bytes_committed"] = int(value)
        decoded.append(record)
    return table, decoded


def as_int(value, default=0):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return default
    return int(text)


def as_text(value, default=""):
    if value is None:
        return default
    return str(value)


# ------------------------------------------------------------------ helpers

def bytes_of(raw, unit):
    return as_int(raw) * UNIT_BYTES.get(as_text(unit, "B"), 1)


def canon_path(raw):
    """NFC, one separator, no dot segment, no trailing separator, rooted."""
    text = unicodedata.normalize("NFC", as_text(raw))
    if not text.startswith("/"):
        text = "/" + text
    out = []
    for part in text.split("/"):
        if part == "" or part == ".":
            continue
        if part == "..":
            if out:
                out.pop()
            continue
        out.append(part)
    return "/" + "/".join(out)


def path_depth(path):
    return 0 if path == "/" else len(path.strip("/").split("/"))


def canon_mode(raw):
    text = as_text(raw).strip()
    if text.startswith("0o") or text.startswith("0O"):
        value = int(text[2:], 8)
    elif text.startswith("d") or text.startswith("D"):
        value = int(text[1:], 10)
    else:
        value = int(text, 8)
    return "{:04o}".format(value & 0o7777)


def ceil_to(value, unit):
    if unit <= 0:
        return value
    return -(-value // unit) * unit


def digest16(payload):
    return hashlib.sha256(payload).hexdigest()[:16]


# ------------------------------------------------------------------ corpus

class Corpus:
    def __init__(self, root):
        self.root = root
        tables = {name: [] for name in SCHEMAS}
        for path in sorted(root.iterdir()):
            if not stat.S_ISREG(path.lstat().st_mode):
                continue
            shard = decode_shard(path.read_text(encoding="utf-8"))
            if shard is not None:
                name, rows = shard
                tables[name].extend(rows)
        for name, rows in tables.items():
            setattr(self, name, rows)


# ------------------------------------------------------------------ plan

class Plan:
    def __init__(self, corpus):
        self.c = corpus

    # -- stage 0 ---------------------------------------------------------
    def _authoritative(self):
        c = self.c
        self.pool = {}
        for row in c.pools:
            self.pool[as_text(row["pool_id"])] = {
                "alloc_unit": as_int(row["alloc_unit"], DEFAULT_ALLOC_UNIT),
                "root_depth_cap": as_int(row["root_depth_cap"]),
                "region": as_text(row["region"]),
            }
        best = {}
        for row in c.barriers:
            pid = as_text(row["pool_id"])
            key = (as_int(row["effective_seq"]), as_int(row["rev"]))
            if pid not in best or key > best[pid][0]:
                best[pid] = (key, as_int(row["barrier_seq"]))
        self.barrier = {k: v[1] for k, v in best.items()}

        best = {}
        for row in c.device_capacity:
            did = as_text(row["device_id"])
            key = (as_int(row["effective_seq"]), as_int(row["rev"]))
            if did not in best or key > best[did][0]:
                best[did] = (key, row)
        self.dev_cap = {k: v[1] for k, v in best.items()}

        best = {}
        for row in c.device_geometry:
            did = as_text(row["device_id"])
            key = (as_int(row["effective_seq"]), as_int(row["rev"]))
            if did not in best or key > best[did][0]:
                best[did] = (key, row)
        self.dev_geo = {k: v[1] for k, v in best.items()}

        self.win = {}
        for row in c.windows:
            did = as_text(row["device_id"])
            self.win.setdefault(did, {})[as_int(row["window_index"])] = {
                "io_budget": bytes_of(row["io_budget_raw"], row["io_budget_unit"]),
                "descriptors": as_int(row["descriptor_budget"]),
            }

        self.route = {}
        for row in c.routes:
            key = (as_text(row["class"]), as_text(row["pool_id"]))
            rid = as_text(row["route_id"])
            cur = self.route.get(key)
            if cur is None or rid < cur[0]:
                self.route[key] = (rid, as_text(row["device_id"]))

        best = {}
        for row in c.objects:
            ino = as_int(row["ino"])
            key = (as_int(row["gen"]), as_int(row["mtime_ns"]))
            if ino not in best or key > best[ino][0]:
                best[ino] = (key, row)
        self.superseded = {}
        for row in c.objects:
            ino = as_int(row["ino"])
            self.superseded[ino] = self.superseded.get(ino, -1) + 1
        self.obj_rows = {k: v[1] for k, v in best.items()}

    def _devices(self):
        self.devices = {}
        for did in sorted(self.dev_cap):
            cap_row = self.dev_cap[did]
            geo = self.dev_geo.get(did, {})
            capacity = bytes_of(cap_row["capacity_raw"], cap_row["capacity_unit"])
            reserve_ppm = as_int(cap_row["reserve_ppm"])
            reserve = capacity * reserve_ppm // 1000000
            windows = self.win.get(did, {})
            self.devices[did] = {
                "device_id": did,
                "capacity_bytes": capacity,
                "existing_used_bytes": bytes_of(cap_row["existing_used_raw"],
                                                cap_row["existing_used_unit"]),
                "reserve_ppm": reserve_ppm,
                "reserve_bytes": reserve,
                "usable_bytes": capacity - reserve,
                "alloc_unit": as_int(geo.get("alloc_unit"), DEFAULT_ALLOC_UNIT),
                "share_domain": as_text(geo.get("share_domain")),
                "spill_device": as_text(geo.get("spill_device")),
                "online": 1 if as_text(geo.get("online")) == "true" else 0,
                "windows": len(windows),
                "io_budget_bytes": sum(w["io_budget"] for w in windows.values()),
                "descriptor_peak": max((w["descriptors"] for w in windows.values()),
                                       default=0),
            }

    # -- stage 1 ---------------------------------------------------------
    def _inventory(self):
        self.inventory = []
        self.obj = {}
        for ino in sorted(self.obj_rows):
            row = self.obj_rows[ino]
            record = {
                "ino": ino,
                "kind": as_text(row["kind"]),
                "size_bytes": bytes_of(row["size_raw"], row["size_unit"]),
                "mode": canon_mode(row["mode_raw"]),
                "uid": as_int(row["uid"]),
                "gid": as_int(row["gid"]),
                "mtime_ns": as_int(row["mtime_ns"]),
                "class": as_text(row["class_raw"]).lower(),
                "pool_id": as_text(row["pool_id"]),
                "declared_link_count": as_int(row["link_count"]),
                "state": as_text(row["state"]),
                "superseded_rows": self.superseded[ino],
                "size_unit": as_text(row["size_unit"]),
            }
            self.inventory.append(record)
            self.obj[ino] = record

    def _paths(self):
        self.path_records = {}
        for row in self.c.paths:
            ino = as_int(row["ino"])
            if ino not in self.obj:
                continue
            self.path_records.setdefault(ino, []).append({
                "path": canon_path(row["path_raw"]),
                "ordinal": as_int(row["ordinal"]),
                "form": as_text(row["form"]),
            })
        for ino in self.path_records:
            self.path_records[ino].sort(key=lambda r: r["ordinal"])

    # -- stage 2 ---------------------------------------------------------
    def _extents(self):
        self.extent_generations = {}
        raw = {}
        for row in self.c.extents:
            ino = as_int(row["ino"])
            if ino not in self.obj or self.obj[ino]["kind"] != "regular":
                continue
            idx = as_int(row["ext_index"])
            gen = as_int(row["gen"])
            key = (ino, idx)
            cur = raw.get(key)
            if cur is None or gen > as_int(cur["gen"]):
                raw[key] = row
            self.extent_generations[key] = max(
                self.extent_generations.get(key, 0), gen)
        self.extent_rows = []
        by_ino = {}
        for (ino, idx) in sorted(raw):
            by_ino.setdefault(ino, []).append(raw[(ino, idx)])
        for ino in sorted(by_ino):
            obj = self.obj[ino]
            unit = self.pool.get(obj["pool_id"], {}).get(
                "alloc_unit", DEFAULT_ALLOC_UNIT)
            previous_end = 0
            for row in by_ino[ino]:
                flags = set(f for f in as_text(row["flags"]).split(",") if f and f != "none")
                offset = as_int(row["offset"])
                length = bytes_of(row["length_raw"], row["length_unit"])
                repairs = []
                if offset < previous_end:
                    shift = previous_end - offset
                    offset = previous_end
                    length = length - shift
                    repairs.append("truncated")
                if length > 0 and offset + length > obj["size_bytes"]:
                    length = obj["size_bytes"] - offset
                    repairs.append("clipped")
                if length <= 0:
                    length = 0
                    repairs = ["void"]
                if "hole" in flags:
                    kind = "hole"
                elif "inline" in flags:
                    kind = "inline"
                elif "unwritten" in flags:
                    kind = "reserved"
                else:
                    kind = "data"
                if length == 0:
                    kind = "void"
                physical = 0
                if kind in ("data", "reserved"):
                    physical = ceil_to(length, unit)
                record = {
                    "ino": ino,
                    "ext_index": as_int(row["ext_index"]),
                    "offset": offset,
                    "length_bytes": length,
                    "end_offset": offset + length,
                    "physical_id": as_text(row["physical_id"]),
                    "physical_class": kind,
                    "raw_physical_bytes": physical,
                    "flags": "+".join(f for f in FLAG_ORDER if f in flags) or "none",
                    "repair": "+".join(repairs) if repairs else "none",
                }
                self.extent_rows.append(record)
                if length > 0:
                    previous_end = offset + length
        self.extents_by_ino = {}
        for record in self.extent_rows:
            self.extents_by_ino.setdefault(record["ino"], []).append(record)

    def _symlinks(self):
        raw = {}
        for row in self.c.symlinks:
            ino = as_int(row["ino"])
            if ino not in self.obj:
                continue
            cur = raw.get(ino)
            if cur is None or as_text(row["target_raw"]) < as_text(cur["target_raw"]):
                raw[ino] = row
        known = {}
        for ino, records in self.path_records.items():
            for rec in records:
                held = known.get(rec["path"])
                if held is None or ino < held:
                    known[rec["path"]] = ino
        roots = set(p.strip("/").split("/")[0] for p in known if p != "/")
        self.symlink_rows = []
        self.symlink_bytes = {}
        for ino in sorted(raw):
            row = raw[ino]
            target = unicodedata.normalize("NFC", as_text(row["target_raw"]))
            target_bytes = len(target.encode("utf-8"))
            kind = "absolute" if target.startswith("/") else "relative"
            records = self.path_records.get(ino, [])
            base = records[0]["path"] if records else "/"
            seen = set()
            hops = 0
            cursor_ino = ino
            cursor_target = target
            resolution = "dangling"
            while True:
                parent = base.rsplit("/", 1)[0] or "/"
                joined = cursor_target if cursor_target.startswith("/") else \
                    parent + "/" + cursor_target
                resolved = canon_path(joined)
                if resolved in seen:
                    resolution = "cyclic"
                    break
                seen.add(resolved)
                if resolved not in known:
                    head = resolved.strip("/").split("/")[0] if resolved != "/" else ""
                    resolution = "dangling" if head in roots else "outside"
                    break
                next_ino = known[resolved]
                if self.obj[next_ino]["kind"] != "symlink" or next_ino not in raw:
                    resolution = "inside"
                    break
                hops += 1
                if hops >= MAX_SYMLINK_HOPS:
                    resolution = "capped"
                    break
                cursor_ino = next_ino
                cursor_target = unicodedata.normalize(
                    "NFC", as_text(raw[next_ino]["target_raw"]))
                nrec = self.path_records.get(next_ino, [])
                base = nrec[0]["path"] if nrec else "/"
            fast = target_bytes <= FAST_SYMLINK_MAX
            unit = self.pool.get(self.obj[ino]["pool_id"], {}).get(
                "alloc_unit", DEFAULT_ALLOC_UNIT)
            physical = 0 if fast else unit
            self.symlink_bytes[ino] = physical
            self.symlink_rows.append({
                "ino": ino,
                "arrival_form": as_text(row["form"]),
                "target": target,
                "target_bytes": target_bytes,
                "kind": kind,
                "resolution": resolution,
                "hops": hops,
                "fast": 1 if fast else 0,
                "physical_bytes": physical,
            })

    def _replay(self):
        events = []
        for row in self.c.mutations:
            events.append({
                "seq": as_int(row["seq"]),
                "ordinal": as_int(row["ordinal"]),
                "kind": as_text(row["kind"]),
                "ino": as_int(row["ino"]),
                "path_a": as_text(row["path_a"]),
                "path_b": as_text(row["path_b"]),
                "arg_num": as_int(row["arg_num"]),
                "arg_alt": as_int(row["arg_alt"]),
            })
        events.sort(key=lambda e: (e["seq"], e["ordinal"], e["kind"], e["ino"]))
        self.replay_rows = []
        self.applied = []
        self.live_paths = {ino: [dict(r) for r in recs]
                           for ino, recs in self.path_records.items()}
        self.state = {ino: rec["state"] for ino, rec in self.obj.items()}
        self.renamed = set()
        self.xattr_events = {}
        for event in events:
            ino = event["ino"]
            target = ""
            kind = event["kind"]
            if kind == "write":
                target = "{}:{}".format(event["arg_num"], event["arg_alt"])
            elif kind == "truncate":
                target = str(event["arg_num"])
            elif kind == "setxattr":
                target = event["path_a"]
            elif kind in ("unlink", "rename", "link"):
                target = canon_path(event["path_a"])
            elif kind in ("chmod", "chown"):
                target = str(event["arg_num"])
            effect = "applied"
            reason = ""
            if ino not in self.obj:
                effect, reason = "ignored", "unknown_inode"
            elif self.obj[ino]["pool_id"] not in self.barrier:
                effect, reason = "ignored", "unknown_pool"
            elif event["seq"] <= self.barrier[self.obj[ino]["pool_id"]]:
                effect, reason = "absorbed", "at_or_before_barrier"
            elif kind in ("unlink", "rename"):
                held = [r["path"] for r in self.live_paths.get(ino, [])]
                if target not in held:
                    effect, reason = "ignored", "unknown_path"
            if effect == "applied":
                self._apply(event, target)
                self.applied.append(event)
            self.replay_rows.append({
                "seq": event["seq"],
                "ordinal": event["ordinal"],
                "kind": kind,
                "ino": ino,
                "target": target,
                "effect": effect,
                "reason": reason,
            })

    def _apply(self, event, target):
        ino = event["ino"]
        kind = event["kind"]
        records = self.live_paths.setdefault(ino, [])
        if kind == "unlink":
            self.live_paths[ino] = [r for r in records if r["path"] != target]
            if not self.live_paths[ino]:
                self.state[ino] = "pruned"
        elif kind == "rename":
            for record in records:
                if record["path"] == target:
                    record["path"] = canon_path(event["path_b"])
                    self.renamed.add(ino)
        elif kind == "link":
            ordinal = max([r["ordinal"] for r in records], default=0) + 1
            records.append({"path": target, "ordinal": ordinal, "form": "nfc"})
        elif kind == "hold":
            self.state[ino] = "held"
        elif kind == "release":
            self.state[ino] = "live"
        elif kind == "setxattr":
            self.xattr_events.setdefault(ino, {})[event["path_a"]] = event["arg_num"]

    # -- stage 3 ---------------------------------------------------------
    def _clusters_and_scope(self):
        claims = {}
        claim_sets = {}
        for row in self.c.claims:
            ino = as_int(row["ino"])
            claims[ino] = claims.get(ino, 0) + 1
            claim_sets.setdefault(ino, set()).add(as_text(row["set_name"]))
        holds = {}
        hold_reasons = {}
        for row in self.c.holds:
            if as_text(row["active"]) == "true":
                ino = as_int(row["ino"])
                holds[ino] = holds.get(ino, 0) + 1
                hold_reasons.setdefault(ino, set()).add(as_text(row["reason"]))
        self.claims = claims
        self.scope_rows = []
        self.cluster_rows = []
        self.relocatable = {}
        self.primary = {}
        self.cluster = {}
        for record in self.inventory:
            ino = record["ino"]
            live = self.live_paths.get(ino, [])
            primary, level, members = self._primary(live)
            self.primary[ino] = primary
            depth = path_depth(primary) if primary else 0
            reason = ""
            if record["pool_id"] not in self.pool:
                reason = "unknown_pool"
            elif self.state[ino] != "live" or not live:
                reason = "not_live"
            elif claims.get(ino, 0) == 0:
                reason = "unclaimed"
            elif claims.get(ino, 0) > 1:
                reason = "contested"
            elif depth > self.pool[record["pool_id"]]["root_depth_cap"]:
                reason = "depth_exceeded"
            ok = reason == ""
            self.relocatable[ino] = ok
            self.scope_rows.append({
                "ino": ino,
                "class": record["class"],
                "pool_id": record["pool_id"],
                "pool_region": self.pool.get(record["pool_id"], {}).get("region", ""),
                "relocatable": 1 if ok else 0,
                "reason": reason,
                "paths_after_replay": len({r["path"] for r in live}),
                "hold_notices": holds.get(ino, 0),
                "hold_reasons": "+".join(sorted(hold_reasons.get(ino, ()))),
                "claims": claims.get(ino, 0),
                "claim_sets": "+".join(sorted(claim_sets.get(ino, ()))),
                "depth": depth,
            })
            if ok:
                forms = sum(1 for r in live if r["form"] == "nfd")
                self.cluster[ino] = {"primary": primary, "members": members}
                self.cluster_rows.append({
                    "ino": ino,
                    "primary_path": primary,
                    "tiebreak_level": level,
                    "member_paths": members,
                    "link_ops": len(members),
                    "arrival_forms": forms,
                })

    @staticmethod
    def _primary(records):
        if not records:
            return "", 0, []
        keys = [
            lambda r: path_depth(r["path"]),
            lambda r: len(r["path"].encode("utf-8")),
            lambda r: r["path"],
            lambda r: r["ordinal"],
        ]
        pool = list(records)
        level = 0
        for depth, key in enumerate(keys, start=1):
            best = min(key(r) for r in pool)
            kept = [r for r in pool if key(r) == best]
            if len(pool) > 1 and len(kept) < len(pool):
                level = depth
            pool = kept
            if len(pool) == 1:
                break
        winner = pool[0]
        if len(records) == 1:
            level = 0
        members = sorted({r["path"] for r in records if r["path"] != winner["path"]})
        return winner["path"], level, members

    def _resume(self):
        groups = {}
        for row in self.c.journal:
            ino = as_int(row["ino"])
            if ino not in self.obj:
                continue
            pool = self.obj[ino]["pool_id"]
            if pool not in self.barrier:
                continue
            key = (ino, as_int(row["ext_index"]))
            groups.setdefault(key, []).append(row)
        self.resume_rows = []
        self.resume_status = {}
        writes = {}
        truncs = {}
        for event in self.applied:
            if event["kind"] == "write":
                writes.setdefault(event["ino"], []).append(event)
            elif event["kind"] == "truncate":
                truncs.setdefault(event["ino"], []).append(event)
        for key in sorted(groups):
            ino, idx = key
            if not self.relocatable.get(ino):
                continue
            extents = [e for e in self.extents_by_ino.get(ino, []) if e["ext_index"] == idx]
            if not extents:
                continue
            extent = extents[0]
            barrier = self.barrier[self.obj[ino]["pool_id"]]
            below = [r for r in groups[key] if as_int(r["seq"]) <= barrier]
            expected = extent["raw_physical_bytes"]
            if not below:
                seq = min(as_int(r["seq"]) for r in groups[key])
                status, committed = "after_barrier", -1
            else:
                chosen = max(below, key=lambda r: (
                    as_int(r["seq"]),
                    -1 if r["bytes_committed"] is None else int(r["bytes_committed"])))
                seq = as_int(chosen["seq"])
                raw = chosen["bytes_committed"]
                if raw is None:
                    status, committed = "never_started", -1
                else:
                    committed = int(raw)
                    if committed == expected:
                        status = "durable"
                    elif committed > expected:
                        status = "overrun"
                    elif committed == 0:
                        status = "zeroed"
                    else:
                        status = "partial"
            invalidated = 0
            if status == "durable":
                hits = []
                for event in writes.get(ino, []):
                    start, length = event["arg_num"], event["arg_alt"]
                    if start < extent["end_offset"] and extent["offset"] < start + length:
                        hits.append(event)
                for event in truncs.get(ino, []):
                    if event["arg_num"] < extent["end_offset"]:
                        hits.append(event)
                if hits:
                    first = min(hits, key=lambda e: (e["seq"], e["ordinal"]))
                    invalidated = first["seq"]
                    status = "redirty"
            self.resume_status[key] = status
            self.resume_rows.append({
                "ino": ino,
                "ext_index": idx,
                "seq": seq,
                "committed": committed,
                "expected": expected,
                "status": status,
                "invalidated_by": invalidated,
            })

    def _xattrs(self):
        raw = {}
        for row in self.c.xattrs:
            ino = as_int(row["ino"])
            if ino not in self.obj:
                continue
            name = as_text(row["name"])
            key = (ino, name)
            rank = (as_int(row["gen"]), as_text(row["xattr_id"]))
            cur = raw.get(key)
            if cur is None or rank > (as_int(cur["gen"]), as_text(cur["xattr_id"])):
                raw[key] = row
        table = {}
        for (ino, name), row in raw.items():
            table.setdefault(ino, {})[name] = as_int(row["value_len"])
        for ino, updates in self.xattr_events.items():
            for name, value in updates.items():
                table.setdefault(ino, {})[name] = value
        self.xattr_rows = []
        self.migrated_xattrs = {}
        for record in self.inventory:
            ino = record["ino"]
            if not self.relocatable.get(ino):
                continue
            entries = table.get(ino, {})
            migrated = []
            dropped = []
            for name in sorted(entries):
                namespace = name.split(".", 1)[0]
                keep = True
                if namespace == "system" and name not in ACL_NAMES:
                    keep = False
                elif namespace == "security" and record["class"] not in ("gold", "silver"):
                    keep = False
                size = len(name.encode("utf-8")) + 1 + entries[name]
                (migrated if keep else dropped).append((name, size))
            self.migrated_xattrs[ino] = migrated
            spaces = sorted({n.split(".", 1)[0] for n, _ in migrated})
            self.xattr_rows.append({
                "ino": ino,
                "migrated_count": len(migrated),
                "dropped_count": len(dropped),
                "migrated_bytes": sum(s for _, s in migrated),
                "dropped_bytes": sum(s for _, s in dropped),
                "first_migrated_name": migrated[0][0] if migrated else "",
                "namespaces": "+".join(spaces),
            })

    def _special(self):
        raw = {}
        for row in self.c.special:
            ino = as_int(row["ino"])
            nid = as_text(row["node_id"])
            cur = raw.get(ino)
            if cur is None or nid < as_text(cur["node_id"]):
                raw[ino] = row
        self.special_rows = []
        for record in self.inventory:
            ino = record["ino"]
            kind = record["kind"]
            if kind not in ("fifo", "socket", "chardev", "blockdev"):
                continue
            if not self.relocatable.get(ino):
                continue
            row = raw.get(ino)
            recreate = {"fifo": "mkfifo", "socket": "bind",
                        "chardev": "mknod", "blockdev": "mknod"}[kind]
            if row is None:
                major = minor = 0
                overflow = 0
                if kind in ("chardev", "blockdev"):
                    recreate = "skip"
            else:
                major = as_int(row["major"])
                raw_minor = as_int(row["minor"])
                overflow = 1 if raw_minor > 255 else 0
                minor = raw_minor % 256
            self.special_rows.append({
                "ino": ino,
                "node_kind": kind,
                "major": major,
                "minor": minor,
                "rdev": major * 256 + minor,
                "overflow": overflow,
                "recreate": recreate,
            })

    # -- stage 4 ---------------------------------------------------------
    def _initial_device(self, record):
        key = (record["class"], record["pool_id"])
        device = self.route.get(key, (None, ""))[1]
        reason = ""
        if device not in self.devices:
            device = self.fallback_device
            reason = "unrouted"
        hops = 0
        while self.devices[device]["online"] == 0 and hops < MAX_SPILL_HOPS:
            nxt = self.devices[device]["spill_device"]
            if nxt not in self.devices:
                break
            device = nxt
            hops += 1
            reason = "offline_spill"
        if self.devices[device]["online"] == 0:
            reason = "offline_chain"
        return device, reason

    def _deadlines(self):
        self.deadline = {}
        self.override = {}
        for row in self.c.deadlines:
            ino = as_int(row["ino"])
            self.deadline[ino] = as_int(row["deadline_window"])
            self.override[ino] = as_text(row["class_override"])

    def _place(self):
        self.fallback_device = next(
            (d for d in sorted(self.devices) if self.devices[d]["online"] == 1),
            sorted(self.devices)[0] if self.devices else "")
        members = [r["ino"] for r in self.inventory if self.relocatable.get(r["ino"])]
        device_of = {}
        reason_of = {}
        for ino in members:
            device, reason = self._initial_device(self.obj[ino])
            device_of[ino] = device
            reason_of[ino] = reason
        self.initial_device = dict(device_of)
        evicted = set()
        moved_round = {}
        rounds = 0
        while rounds < MAX_EVICTION_ROUNDS:
            attributed, expansion = self._attribute(members, device_of)
            claim = {}
            for ino in members:
                did = device_of[ino]
                if did:
                    claim[did] = claim.get(did, 0) + attributed[ino]
            shed = False
            for did in sorted(self.devices):
                device = self.devices[did]
                headroom = (device["usable_bytes"] - device["existing_used_bytes"]
                            - claim.get(did, 0))
                if headroom >= 0:
                    continue
                candidates = [ino for ino in members
                              if device_of[ino] == did and ino not in evicted]
                if not candidates:
                    continue
                candidates.sort(key=lambda i: (-CLASS_RANK[self.obj[i]["class"]],
                                               -attributed[i],
                                               self.primary.get(i, ""), i))
                victim = candidates[0]
                spill = device["spill_device"]
                if spill not in self.devices or spill == did:
                    continue
                device_of[victim] = spill
                reason_of[victim] = "evicted"
                evicted.add(victim)
                moved_round[victim] = rounds + 1
                claim[did] = claim.get(did, 0) - attributed[victim]
                claim[spill] = claim.get(spill, 0) + attributed[victim]
                shed = True
            rounds += 1
            if not shed:
                break
        self.eviction_rounds = rounds
        self.device_of = device_of
        self.attributed, self.expansion = self._attribute(members, device_of)
        self.members = members
        self.placement_rows = []
        for ino in members:
            did = device_of[ino]
            self.placement_rows.append({
                "ino": ino,
                "class": self.obj[ino]["class"],
                "initial_device": self.initial_device[ino],
                "device": did,
                "share_domain": self.devices[did]["share_domain"] if did else "",
                "moved": 1 if did != self.initial_device[ino] else 0,
                "round": moved_round.get(ino, 0),
                "reason": reason_of[ino],
                "attributed_bytes": self.attributed[ino],
                "deadline_window": self.deadline.get(ino, 0),
                "class_override": self.override.get(ino, ""),
            })

    def _attribute(self, members, device_of):
        """Owner attribution of every surviving extent under share expansion."""
        refs = {}
        for ino in members:
            for extent in self.extents_by_ino.get(ino, []):
                if extent["physical_class"] not in ("data", "reserved"):
                    continue
                refs.setdefault(extent["physical_id"], []).append((ino, extent))
        attributed = {ino: 0 for ino in members}
        owners = {}
        expansion = []
        for pid in sorted(refs):
            entries = refs[pid]
            inos = sorted({ino for ino, _ in entries})
            domains = {}
            for ino, extent in entries:
                did = device_of[ino]
                domain = self.devices[did]["share_domain"] if did else ""
                domains.setdefault(domain, []).append((ino, extent))
            unit = max(extent["raw_physical_bytes"] for _, extent in entries)
            for domain in sorted(domains):
                holders = domains[domain]
                owner = min({ino for ino, _ in holders},
                            key=lambda i: (self.primary.get(i, ""), i))
                own_extent = min((e for i, e in holders if i == owner),
                                 key=lambda e: e["ext_index"])
                attributed[owner] += own_extent["raw_physical_bytes"]
                for ino, extent in holders:
                    owners[(ino, extent["ext_index"])] = (
                        ino == owner and extent["ext_index"] == own_extent["ext_index"])
            if len(inos) > 1:
                expansion.append({
                    "physical_id": pid,
                    "referencing_inodes": inos,
                    "domains": sorted(domains),
                    "copies": len(domains),
                    "owners": [min({i for i, _ in domains[d]},
                                    key=lambda i: (self.primary.get(i, ""), i))
                               for d in sorted(domains)],
                    "unit_bytes": unit,
                    "expanded_bytes": unit * (len(domains) - 1),
                })
        self.owner_flag = owners
        return attributed, expansion

    def _workset(self):
        deadlines = self.deadline
        domain_class = {}
        for ino in self.members:
            did = self.device_of[ino]
            domain = self.devices[did]["share_domain"] if did else ""
            for extent in self.extents_by_ino.get(ino, []):
                if extent["physical_class"] not in ("data", "reserved"):
                    continue
                key = (extent["physical_id"], domain)
                rank = CLASS_RANK[self.obj[ino]["class"]]
                if key not in domain_class or rank < domain_class[key]:
                    domain_class[key] = rank
        rank_class = {v: k for k, v in CLASS_RANK.items()}
        self.workset = []
        for ino in self.members:
            did = self.device_of[ino]
            domain = self.devices[did]["share_domain"] if did else ""
            for extent in self.extents_by_ino.get(ino, []):
                if extent["physical_class"] != "data":
                    continue
                if not self.owner_flag.get((ino, extent["ext_index"]), False):
                    continue
                status = self.resume_status.get((ino, extent["ext_index"]))
                if status == "durable":
                    continue
                if status is None:
                    origin = "fresh"
                elif status == "redirty":
                    origin = "redirty"
                else:
                    origin = "restart"
                effective = rank_class[domain_class[(extent["physical_id"], domain)]]
                self.workset.append({
                    "ino": ino,
                    "ext_index": extent["ext_index"],
                    "device_id": did,
                    "physical_id": extent["physical_id"],
                    "copy_bytes": extent["raw_physical_bytes"],
                    "origin": origin,
                    "effective_class": effective,
                    "deadline_window": deadlines.get(ino, 0),
                })
        self.workset.sort(key=lambda w: (CLASS_RANK[w["effective_class"]],
                                         w["deadline_window"],
                                         self.primary.get(w["ino"], ""),
                                         w["ino"], w["ext_index"]))

    def _metadata(self):
        self.metadata_rows = []
        for ino in self.members:
            record = self.obj[ino]
            primary = self.primary[ino]
            ops = []
            if record["kind"] == "dir":
                ops.append(("mkdir", "", 0))
            for row in self.special_rows:
                if row["ino"] == ino and row["recreate"] != "skip":
                    ops.append((row["recreate"],
                                "{}:{}".format(row["major"], row["minor"]), 0))
            for row in self.symlink_rows:
                if row["ino"] == ino:
                    ops.append(("symlink", row["target"], 0))
            for member in self.cluster[ino]["members"]:
                ops.append(("link", member, 0))
            did = self.device_of[ino]
            domain = self.devices[did]["share_domain"] if did else ""
            for extent in self.extents_by_ino.get(ino, []):
                if extent["physical_class"] == "reserved":
                    ops.append(("fallocate", str(extent["ext_index"]),
                                extent["raw_physical_bytes"]))
                elif extent["physical_class"] == "data" and not self.owner_flag.get(
                        (ino, extent["ext_index"]), False):
                    ops.append(("reflink", extent["physical_id"],
                                extent["raw_physical_bytes"]))
            for name, _size in self.migrated_xattrs.get(ino, []):
                ops.append(("setxattr", name, 0))
            ops.append(("chown", "{}:{}".format(record["uid"], record["gid"]), 0))
            ops.append(("chmod", record["mode"], 0))
            ops.append(("utimes", str(record["mtime_ns"]), 0))
            ops.sort(key=lambda o: (OP_RANK[o[0]], o[1]))
            for op, detail, size in ops:
                self.metadata_rows.append({
                    "op": op,
                    "ino": ino,
                    "path": primary,
                    "detail": detail,
                    "bytes": size,
                })

    def _schedule(self):
        remaining = {}
        opened = {}
        for did, windows in self.win.items():
            for index, spec in windows.items():
                remaining[(did, index)] = spec["io_budget"]
                opened[(did, index)] = set()
        self.schedule_rows = []
        self.split_rows = []
        self.deferred_bytes = {}
        for item in self.workset:
            did = item["device_id"]
            windows = sorted(self.win.get(did, {}))
            if not windows:
                self.split_rows.append(self._split_record(item, "deferred", 0, 0,
                                                          item["copy_bytes"], -1, -1))
                self.deferred_bytes[item["ino"]] = self.deferred_bytes.get(
                    item["ino"], 0) + item["copy_bytes"]
                continue
            budgets = self.win[did]
            largest = max(budgets[w]["io_budget"] for w in windows)
            unit = self.devices[did]["alloc_unit"]
            first_open = next((w for w in windows if remaining[(did, w)] > 0), -1)
            placements = []
            if item["copy_bytes"] <= largest:
                target = -1
                for w in windows:
                    if remaining[(did, w)] < item["copy_bytes"]:
                        continue
                    if (item["ino"] not in opened[(did, w)]
                            and len(opened[(did, w)]) >= budgets[w]["descriptors"]):
                        continue
                    target = w
                    break
                if target >= 0:
                    placements.append((target, item["copy_bytes"]))
            else:
                residual = item["copy_bytes"]
                for w in windows:
                    if residual <= 0:
                        break
                    free = remaining[(did, w)]
                    if free < unit:
                        continue
                    if (item["ino"] not in opened[(did, w)]
                            and len(opened[(did, w)]) >= budgets[w]["descriptors"]):
                        continue
                    chunk = residual if residual <= free else free - (free % unit)
                    if chunk <= 0:
                        continue
                    placements.append((w, chunk))
                    residual -= chunk
            placed = 0
            for chunk_index, (w, size) in enumerate(placements):
                fresh = item["ino"] not in opened[(did, w)]
                opened[(did, w)].add(item["ino"])
                remaining[(did, w)] -= size
                placed += size
                self.schedule_rows.append({
                    "device_id": did,
                    "window_index": w,
                    "ino": item["ino"],
                    "ext_index": item["ext_index"],
                    "chunk_index": chunk_index,
                    "bytes": size,
                    "descriptor_opened": 1 if fresh else 0,
                })
            residual = item["copy_bytes"] - placed
            if residual > 0:
                self.deferred_bytes[item["ino"]] = self.deferred_bytes.get(
                    item["ino"], 0) + residual
            if not placements:
                status = "deferred"
            elif residual > 0:
                status = "deferred"
            elif len(placements) > 1:
                status = "split"
            elif placements[0][0] != first_open:
                status = "rolled"
            else:
                status = "whole"
            if status != "whole":
                self.split_rows.append(self._split_record(
                    item, status, len(placements), placed, residual,
                    placements[0][0] if placements else -1,
                    placements[-1][0] if placements else -1))
        self.schedule_rows.sort(key=lambda r: (r["device_id"], r["window_index"],
                                               r["ino"], r["ext_index"],
                                               r["chunk_index"]))
        self.split_rows.sort(key=lambda r: (r["ino"], r["ext_index"]))
        self.descriptor_rows = []
        used_bytes = {}
        used_desc = {}
        for row in self.schedule_rows:
            key = (row["device_id"], row["window_index"])
            used_bytes[key] = used_bytes.get(key, 0) + row["bytes"]
            used_desc[key] = used_desc.get(key, 0) + row["descriptor_opened"]
        for did in sorted(self.win):
            for index in sorted(self.win[did]):
                spec = self.win[did][index]
                key = (did, index)
                budget = spec["io_budget"]
                consumed = used_bytes.get(key, 0)
                self.descriptor_rows.append({
                    "device_id": did,
                    "window_index": index,
                    "descriptor_budget": spec["descriptors"],
                    "descriptors_used": used_desc.get(key, 0),
                    "io_budget_bytes": budget,
                    "bytes_used": consumed,
                    "utilisation_ppm": (consumed * 1000000 // budget) if budget else 0,
                })

    @staticmethod
    def _split_record(item, status, chunks, placed, residual, first, last):
        return {
            "ino": item["ino"],
            "ext_index": item["ext_index"],
            "device_id": item["device_id"],
            "status": status,
            "chunks": chunks,
            "placed_bytes": placed,
            "residual_bytes": residual,
            "first_window": first,
            "last_window": last,
        }

    # -- stage 5 ---------------------------------------------------------
    def _cutover(self):
        ready = [ino for ino in self.members if self.deferred_bytes.get(ino, 0) == 0]
        ready.sort(key=lambda i: (path_depth(self.primary[i]), self.primary[i], i))
        self.cutover = [self.primary[ino] for ino in ready]
        self.rollback_rows = []
        redirty = set()
        copied = set()
        for row in self.resume_rows:
            if row["status"] == "redirty":
                redirty.add(row["ino"])
        for item in self.workset:
            copied.add(item["ino"])
        for step, ino in enumerate(ready, start=1):
            self.rollback_rows.append(self._rollback(step, ino, redirty, copied))
        deferred = sorted(ino for ino in self.members
                          if self.deferred_bytes.get(ino, 0) > 0)
        for ino in deferred:
            record = self._rollback(0, ino, redirty, copied)
            record["reverse"] = "abort_hold"
            self.rollback_rows.append(record)

    def _rollback(self, step, ino, redirty, copied):
        if ino in redirty:
            guard = "digest_match"
        elif ino in copied:
            guard = "size_match"
        else:
            guard = "xattr_count_match"
        if self.cluster[ino]["members"]:
            reverse = "restore_link"
        elif ino in self.renamed:
            reverse = "rename_back"
        else:
            reverse = "unlink_target"
        return {
            "step": step,
            "ino": ino,
            "path": self.primary[ino],
            "guard": guard,
            "reverse": reverse,
            "barrier_seq": self.barrier.get(self.obj[ino]["pool_id"], 0),
        }

    def _conservation(self):
        copied = {}
        for row in self.schedule_rows:
            copied[row["device_id"]] = copied.get(row["device_id"], 0) + row["bytes"]
        resumed = {}
        reserved = {}
        deferred = {}
        for ino in self.members:
            did = self.device_of[ino]
            for extent in self.extents_by_ino.get(ino, []):
                if not self.owner_flag.get((ino, extent["ext_index"]), False):
                    continue
                if extent["physical_class"] == "reserved":
                    reserved[did] = reserved.get(did, 0) + extent["raw_physical_bytes"]
                elif extent["physical_class"] == "data":
                    if self.resume_status.get((ino, extent["ext_index"])) == "durable":
                        resumed[did] = resumed.get(did, 0) + extent["raw_physical_bytes"]
            if self.deferred_bytes.get(ino, 0):
                deferred[did] = deferred.get(did, 0) + self.deferred_bytes[ino]
        attributed = {}
        for ino in self.members:
            did = self.device_of[ino]
            attributed[did] = attributed.get(did, 0) + self.attributed[ino]
        self.conservation_rows = []
        balanced = 0
        for did in sorted(self.devices):
            total = attributed.get(did, 0)
            residual = (total - copied.get(did, 0) - resumed.get(did, 0)
                        - reserved.get(did, 0) - deferred.get(did, 0))
            if residual == 0:
                balanced += 1
            self.conservation_rows.append({
                "device_id": did,
                "attributed_bytes": total,
                "copied_bytes": copied.get(did, 0),
                "resumed_bytes": resumed.get(did, 0),
                "reserved_bytes": reserved.get(did, 0),
                "deferred_bytes": deferred.get(did, 0),
                "residual_bytes": residual,
            })
        self.balanced_devices = balanced
        self.unbalanced_devices = len(self.devices) - balanced

    def build(self):
        self._authoritative()
        self._devices()
        self._inventory()
        self._paths()
        self._extents()
        self._symlinks()
        self._replay()
        self._clusters_and_scope()
        self._resume()
        self._xattrs()
        self._special()
        self._deadlines()
        self._place()
        self._workset()
        self._metadata()
        self._schedule()
        self._cutover()
        self._conservation()
        return self


# ------------------------------------------------------------------ emission

def render_cell(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_csv(rows, fields):
    out = [",".join(fields)]
    for row in rows:
        cells = []
        for f in fields:
            text = render_cell(row[f])
            if "," in text or '"' in text:
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        out.append(",".join(cells))
    return "\n".join(out) + "\n"


def render_tsv(rows, fields):
    out = ["\t".join(fields)]
    for row in rows:
        out.append("\t".join(render_cell(row[f]) for f in fields))
    return "\n".join(out) + "\n"


def render_json(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def render_jsonl(rows):
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n"
                   for r in rows)


F_EXTENT = ["ino", "ext_index", "offset", "length_bytes", "end_offset",
            "physical_id", "physical_class", "raw_physical_bytes", "flags",
            "repair"]
F_SCOPE = ["ino", "class", "pool_id", "pool_region", "relocatable", "reason",
           "paths_after_replay", "hold_notices", "hold_reasons", "claims",
           "claim_sets", "depth"]
F_XATTR = ["ino", "migrated_count", "dropped_count", "migrated_bytes",
           "dropped_bytes", "first_migrated_name", "namespaces"]
F_SPECIAL = ["ino", "node_kind", "major", "minor", "rdev", "overflow", "recreate"]
F_PLACE = ["ino", "class", "initial_device", "device", "share_domain", "moved",
           "round", "reason", "attributed_bytes", "deadline_window",
           "class_override"]
F_ALLOC = ["device_id", "capacity_bytes", "reserve_bytes", "usable_bytes",
           "existing_used_bytes", "claim_bytes", "projected_bytes",
           "headroom_bytes", "over_committed", "placed_objects", "evicted_out",
           "received_in"]
F_WORK = ["ino", "ext_index", "device_id", "physical_id", "copy_bytes",
          "origin", "effective_class", "deadline_window"]
F_SCHED = ["device_id", "window_index", "ino", "ext_index", "chunk_index",
           "bytes", "descriptor_opened"]
F_DESC = ["device_id", "window_index", "descriptor_budget", "descriptors_used",
          "io_budget_bytes", "bytes_used", "utilisation_ppm"]
F_DEVICE = ["device_id", "capacity_bytes", "existing_used_bytes", "reserve_ppm",
            "reserve_bytes", "usable_bytes", "alloc_unit", "share_domain",
            "spill_device", "online", "windows", "io_budget_bytes",
            "descriptor_peak"]


def render_all(plan):
    files = {}
    files["object_inventory.jsonl"] = render_jsonl(plan.inventory)
    files["device_topology.json"] = render_json({
        "devices": [{f: plan.devices[d][f] for f in F_DEVICE}
                    for d in sorted(plan.devices)],
        "device_count": len(plan.devices),
        "domain_count": len({plan.devices[d]["share_domain"] for d in plan.devices}),
    })
    files["extent_map.tsv"] = render_tsv(plan.extent_rows, F_EXTENT)
    files["symlink_topology.jsonl"] = render_jsonl(plan.symlink_rows)
    files["mutation_replay.jsonl"] = render_jsonl(plan.replay_rows)
    files["scope_resolution.csv"] = render_csv(plan.scope_rows, F_SCOPE)
    files["link_clusters.jsonl"] = render_jsonl(plan.cluster_rows)
    files["resume_state.jsonl"] = render_jsonl(plan.resume_rows)
    files["xattr_ledger.csv"] = render_csv(plan.xattr_rows, F_XATTR)
    files["special_nodes.tsv"] = render_tsv(plan.special_rows, F_SPECIAL)
    files["placement.csv"] = render_csv(plan.placement_rows, F_PLACE)
    files["sharing_expansion.jsonl"] = render_jsonl(plan.expansion)

    claim = {}
    placed = {}
    evicted_out = {}
    received_in = {}
    for row in plan.placement_rows:
        did = row["device"]
        claim[did] = claim.get(did, 0) + row["attributed_bytes"]
        placed[did] = placed.get(did, 0) + 1
        if row["moved"]:
            evicted_out[row["initial_device"]] = evicted_out.get(
                row["initial_device"], 0) + 1
            received_in[did] = received_in.get(did, 0) + 1
    alloc_rows = []
    for did in sorted(plan.devices):
        device = plan.devices[did]
        projected = device["existing_used_bytes"] + claim.get(did, 0)
        headroom = device["usable_bytes"] - projected
        alloc_rows.append({
            "device_id": did,
            "capacity_bytes": device["capacity_bytes"],
            "reserve_bytes": device["reserve_bytes"],
            "usable_bytes": device["usable_bytes"],
            "existing_used_bytes": device["existing_used_bytes"],
            "claim_bytes": claim.get(did, 0),
            "projected_bytes": projected,
            "headroom_bytes": headroom,
            "over_committed": 1 if headroom < 0 else 0,
            "placed_objects": placed.get(did, 0),
            "evicted_out": evicted_out.get(did, 0),
            "received_in": received_in.get(did, 0),
        })
    files["allocation_projection.csv"] = render_csv(alloc_rows, F_ALLOC)
    files["delta_workset.tsv"] = render_tsv(plan.workset, F_WORK)
    files["metadata_workset.jsonl"] = render_jsonl(plan.metadata_rows)
    files["window_schedule.tsv"] = render_tsv(plan.schedule_rows, F_SCHED)
    files["split_ledger.jsonl"] = render_jsonl(plan.split_rows)
    files["descriptor_budget.csv"] = render_csv(plan.descriptor_rows, F_DESC)
    files["cutover_sequence.txt"] = "".join(p + "\n" for p in plan.cutover)
    files["rollback_plan.jsonl"] = render_jsonl(plan.rollback_rows)
    files["conservation.json"] = render_json({
        "devices": plan.conservation_rows,
        "balanced_devices": plan.balanced_devices,
        "unbalanced_devices": plan.unbalanced_devices,
    })
    files["cli_contract.json"] = render_json({
        "tool": "stratactl",
        "usage": "stratactl.py CORPUS_DIR OUT_DIR",
        "exit_ok": EXIT_OK,
        "exit_usage": EXIT_USAGE,
        "exit_policy": EXIT_POLICY,
        "artifact_count": len(ARTIFACT_NAMES) + 2,
    })

    manifest = []
    for name in ARTIFACT_NAMES:
        payload = files[name].encode("utf-8")
        manifest.append({
            "name": name,
            "rows": files[name].count("\n"),
            "bytes": len(payload),
            "digest": digest16(payload),
        })
    files["manifest.json"] = render_json({"artifacts": manifest})
    joined = "\n".join(entry["digest"] for entry in manifest)
    files["summary.json"] = render_json({
        "relocatable_objects": sum(1 for r in plan.scope_rows if r["relocatable"]),
        "excluded_objects": sum(1 for r in plan.scope_rows if not r["relocatable"]),
        "clusters": len(plan.cluster_rows),
        "copy_items": len(plan.workset),
        "metadata_ops": len(plan.metadata_rows),
        "cutover_steps": len(plan.cutover),
        "manifest_digest": digest16(joined.encode("utf-8")),
    })
    return files


def deliver_self(out_dir):
    """The planner ships beside the plan it produced."""
    here = Path(__file__).resolve()
    (out_dir / "stratactl.py").write_text(
        here.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: stratactl.py CORPUS_DIR OUT_DIR\n")
        return EXIT_USAGE
    corpus_dir = Path(argv[1])
    out_dir = Path(argv[2])
    if not corpus_dir.is_dir():
        sys.stderr.write("corpus path does not resolve to a directory\n")
        return EXIT_POLICY
    out_dir.mkdir(parents=True, exist_ok=True)
    files = render_all(Plan(Corpus(corpus_dir)).build())
    for name, text in files.items():
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")
    deliver_self(out_dir)
    print("[stratactl] wrote {} files into {}".format(len(files) + 1, out_dir))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
'''


# ------------------------------------------------------------ runtime setup

_SUPERVISOR_SRC = r'''
import ctypes
import json
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path

CAPTURE_LIMIT = 1048576


def kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return  # An already empty group still requires the adopted-child sweep.


def reap_tree(process: subprocess.Popen) -> None:
    kill_group(process.pid)
    children_file = Path(f"/proc/self/task/{os.getpid()}/children")
    while True:
        # Only this dedicated supervisor's children: never global /proc or verifier waitpid.
        for child in children_file.read_text().split():
            try:
                os.kill(int(child), signal.SIGKILL)
            except ProcessLookupError:
                continue
        try:
            while True:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                if pid == process.pid:
                    process.returncode = os.waitstatus_to_exitcode(status)
        except ChildProcessError:
            return
        # Killing parents reparents setsid/double-fork descendants here; repeat to ECHILD.
        time.sleep(0.01)


def main() -> None:
    command, timeout, control = json.loads(sys.argv[1])
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "cannot enable child subreaper")
    cancelled = False

    def cancel(signum, frame) -> None:
        nonlocal cancelled
        cancelled = True

    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    captures = {"stdout": bytearray(), "stderr": bytearray()}
    timed_out = False
    with selectors.DefaultSelector() as selector:
        selector.register(control, selectors.EVENT_READ, "control")
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True, close_fds=True)
        try:
            for label, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, label)
            deadline = time.monotonic() + timeout
            while not cancelled:
                # WNOWAIT pins the leader PID until its process group has been killed.
                if os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT):
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                for key, _ in selector.select(min(0.05, max(0, deadline - time.monotonic()))):
                    if key.data == "control":
                        cancelled = True
                        break
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        capture = captures[key.data]
                        capture.extend(chunk[:max(0, CAPTURE_LIMIT - len(capture))])
        finally:
            # No communicate(): descendants retaining pipe handles cannot extend the deadline.
            reap_tree(process)
            for label, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                with stream:
                    while True:
                        chunk = os.read(stream.fileno(), 65536)
                        if not chunk:
                            break
                        capture = captures[label]
                        capture.extend(chunk[:max(0, CAPTURE_LIMIT - len(capture))])
    print(json.dumps({"returncode": process.returncode, "timed_out": timed_out or cancelled,
                      "stdout": captures["stdout"].hex(), "stderr": captures["stderr"].hex()}))


if __name__ == "__main__":
    main()
'''

CASE_DATA = types.ModuleType("strata_case_data")
exec(compile(_CASE_DATA_SRC, "strata_case_data", "exec"), CASE_DATA.__dict__)
REF = types.ModuleType("strata_ref")
exec(compile(_REF_SRC, "strata_ref", "exec"), REF.__dict__)

SAMPLE_SEED = 20260909
EVAL_SEED = 4471903352
CHALLENGE_SEED = 1180237991

# Assembled at run time so this module carries no literal corpus path.
SHIPPED_CORPUS = "/" + "app" + "/" + "data"
SHIPPED_OUT = "/" + "app" + "/" + "out"

ARTIFACTS = list(REF.ARTIFACT_NAMES) + ["manifest.json", "summary.json"]
TOOL_NAME = "stratactl.py"
_SETPRIV = ["/usr/bin/setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups",
            "--no-new-privs", "--bounding-set=-all"]
# Thirteen cached runs (including CLI probes) leave headroom in the verifier budget.
TOOL_TIMEOUT_SEC = 180

_corpora: dict[str, Path] = {}
_expected: dict[str, dict[str, bytes]] = {}
_tool_root: list[Path] = []
_tool_runs: dict[str, dict[str, bytes] | None] = {}
_run_extras: dict[str, bool] = {}
_repeat_runs: dict[Path, dict[str, bytes] | None] = {}
# rewardkit runs criteria in worker threads; one lock keeps the shared run caches coherent.
_CACHE_LOCK = threading.RLock()


@dataclass(frozen=True, slots=True)
class OutputSnapshot:
    files: dict[str, bytes]
    undeclared: bool


_deliveries: dict[Path, OutputSnapshot] = {}


def _tmp(prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix="strata-" + prefix + "-"))
    path.chmod(0o755)
    return path


def out_dir(workspace: Path) -> Path:
    return workspace / "out"


def corpus(seed: int, tag: str = "", reverse: bool = False,
           perturb: bool = False) -> Path:
    """Build a corpus once per shape and cache it."""
    key = "{}:{}:{}:{}".format(seed, tag, reverse, perturb)
    if key in _corpora:
        return _corpora[key]
    data = CASE_DATA.build_edge(seed) if tag == "edge" else CASE_DATA.build_all(seed)
    root = _write_corpus(data, _tmp("corpus"), reverse=reverse, perturb=perturb)
    if tag in ("opaque", "misleading"):
        for index, (name, fmt, table, *_) in enumerate(CASE_DATA.LAYOUT):
            renamed = "{:04x}a7".format(len(CASE_DATA.LAYOUT) - index)
            if tag == "misleading":
                decoy = next(row[0] for row in CASE_DATA.LAYOUT if row[2] != table)
                suffix = "csv" if fmt == "json" else "json"
                renamed = "{}-{:03d}.{}".format(decoy.rsplit(".", 1)[0], index, suffix)
            (root / name).rename(root / renamed)
    _corpora[key] = root
    return _corpora[key]


def _write_corpus(data: dict, root: Path, reverse: bool = False,
                  perturb: bool = False) -> Path:
    """Write one corpus shape to disk. Shared by every shape this module builds."""
    root.mkdir(parents=True, exist_ok=True)
    if perturb:
        for row in data["device_capacity"]:
            row["reserve_ppm"] = 400000
    shards: dict[tuple, list] = {}
    for name, fmt, table, fields, idx, total in CASE_DATA.LAYOUT:
        ident = (table, total)
        if ident not in shards:
            shards[ident] = CASE_DATA._shard(data[table], total)
        rows = list(shards[ident][idx])
        if reverse:
            rows.reverse()
        (root / name).write_text(CASE_DATA.WRITERS[fmt](rows, fields),
                                 encoding="utf-8", newline="\n")
    return root


def expected(seed: int, **kwargs) -> dict[str, bytes]:
    """Reference bytes stay in verifier memory, never in the child's environment."""
    key = "{}:{}".format(seed, sorted(kwargs.items()))
    if key not in _expected:
        files = REF.render_all(REF.Plan(REF.Corpus(corpus(seed, **kwargs))).build())
        _expected[key] = {name: text.encode("utf-8") for name, text in files.items()}
    return _expected[key]


def delivery(workspace: Path) -> OutputSnapshot:
    if workspace not in _deliveries:
        _deliveries[workspace] = _inspect_output(out_dir(workspace))
    return _deliveries[workspace]


def delivered(workspace: Path, name: str) -> bytes | None:
    return delivery(workspace).files.get(name)


def tool_root(workspace: Path) -> Path | None:
    """Copy the delivered planner somewhere it cannot rewrite itself."""
    if _tool_root:
        return _tool_root[0]
    source = delivered(workspace, TOOL_NAME)
    if source is None:
        return None
    try:
        root = _tmp("tool")
        dest = root / TOOL_NAME
        dest.write_bytes(source)
        dest.chmod(0o644)
    except OSError:
        return None
    _tool_root.append(root)
    return root


def tool_source(workspace: Path) -> str | None:
    root = tool_root(workspace)
    if root is None:
        return None
    chunks = []
    try:
        for path in sorted(root.rglob("*.py")):
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return "\n".join(chunks)


def tool_ast(workspace: Path):
    """The delivered planner parsed, or None when it is not valid Python."""
    text = tool_source(workspace)
    if text is None:
        return None
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None


def invoke_tool(workspace: Path, args: list[str]) -> subprocess.CompletedProcess[bytes] | None:
    """A private root supervisor owns/reaps only this invocation's unprivileged tree."""
    if not sys.platform.startswith("linux") or os.geteuid() != 0:
        raise RuntimeError("planner isolation requires a root Linux verifier")
    root = tool_root(workspace)
    if root is None:
        return None
    entry = root / TOOL_NAME
    entry.chmod(0o644)
    command = [*_SETPRIV, sys.executable, "-I", "-B", str(entry), *args]
    with tempfile.TemporaryDirectory(prefix="strata-supervisor-") as scratch:
        supervisor = Path(scratch) / "supervisor.py"
        supervisor.write_text(_SUPERVISOR_SRC, encoding="utf-8")
        read_fd, write_fd = os.pipe()
        with os.fdopen(read_fd, "rb") as control, os.fdopen(write_fd, "wb") as cancel:
            with tempfile.TemporaryFile() as report:
                config = json.dumps([command, TOOL_TIMEOUT_SEC, control.fileno()])
                try:
                    process = subprocess.Popen(
                        [sys.executable, "-I", "-B", str(supervisor), config],
                        cwd=scratch, stdin=subprocess.DEVNULL, stdout=report,
                        stderr=subprocess.DEVNULL, start_new_session=True,
                        pass_fds=(control.fileno(),),
                        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONHASHSEED": "0",
                             "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
                except OSError:
                    return None
                try:
                    process.wait(timeout=TOOL_TIMEOUT_SEC + 15)
                finally:
                    # EOF also cancels on exceptions or verifier death; never kill the reaper.
                    cancel.close()
                    process.wait(timeout=15)
                if process.returncode != 0:
                    raise RuntimeError("trusted supervisor failed to certify descendant cleanup")
                report.seek(0)
                result = json.load(report)
                if result["timed_out"]:
                    return None
                return subprocess.CompletedProcess(command, result["returncode"],
                    bytes.fromhex(result["stdout"]), bytes.fromhex(result["stderr"]))


def run_tool(workspace: Path, corpus_dir: Path, target: Path):
    try:
        target.mkdir(parents=True, exist_ok=True)
        target.chmod(0o777)
    except OSError:
        return None
    return invoke_tool(workspace, [str(corpus_dir), str(target)])


def _inspect_output(target: Path) -> OutputSnapshot:
    """A directory entry is enough to reject extras; never traverse or open them."""
    produced: dict[str, bytes] = {}
    extra = False
    allowed = set(ARTIFACTS) | {TOOL_NAME}
    try:
        if not stat.S_ISDIR(target.lstat().st_mode):
            return OutputSnapshot(produced, True)
        directory = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        return OutputSnapshot(produced, False)
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name not in allowed or not entry.is_file(follow_symlinks=False):
                    extra = True
                    continue
                try:
                    fd = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 dir_fd=directory)
                    with os.fdopen(fd, "rb") as stream:
                        if stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                            payload = stream.read(32 * 1024 * 1024 + 1)
                            if len(payload) <= 32 * 1024 * 1024:
                                produced[entry.name] = payload
                except OSError:
                    continue
    finally:
        os.close(directory)
    return OutputSnapshot(produced, extra)


def _collect(target: Path) -> dict[str, bytes]:
    return _inspect_output(target).files


def tool_outputs(workspace: Path, seed: int, **kwargs) -> dict[str, bytes] | None:
    """Run the delivered planner over a corpus shape and read what it wrote."""
    key = "{}:{}".format(seed, sorted(kwargs.items()))
    with _CACHE_LOCK:
        if key in _tool_runs:
            return _tool_runs[key]
        _tool_runs[key] = None
        target = _tmp("out")
        shape = corpus(seed, **kwargs)
        result = run_tool(workspace, shape, target)
        snapshot = _inspect_output(target)
        _run_extras[key] = snapshot.undeclared
        if result is None or result.returncode != 0:
            return None
        _tool_runs[key] = snapshot.files
        return _tool_runs[key]


def check_artifact(workspace: Path, name: str) -> bool:
    """Exact bytes on delivery, sample rerun, hidden, renamed and boundary corpora."""
    want_sample = expected(SAMPLE_SEED)
    if want_sample is None or name not in want_sample:
        return False
    if delivered(workspace, name) != want_sample[name]:
        return False
    shapes = (
        (SAMPLE_SEED, {}),
        (EVAL_SEED, {}),
        (CHALLENGE_SEED, {}),
        (EVAL_SEED, {"tag": "alt"}),
        (EVAL_SEED, {"tag": "opaque"}),
        (EVAL_SEED, {"tag": "misleading"}),
        (EVAL_SEED, {"tag": "edge"}),
        (EVAL_SEED, {"perturb": True}),
        (EVAL_SEED, {"reverse": True}),
    )
    for seed, options in shapes:
        want = expected(seed, **options)
        produced = tool_outputs(workspace, seed, **options)
        if produced is None or produced.get(name) != want[name]:
            return False
    return True


# ---------------------------------------------------------------- positives

@criterion(description="every declared artifact and the planner source exist and are non-empty")
def declared_artifacts_present(workspace: Path) -> bool:
    for name in ARTIFACTS + [TOOL_NAME]:
        if not delivered(workspace, name):
            return False
    return True


@criterion(description="each artifact parses under the encoding its name declares, with no BOM, no CR and exactly one trailing newline")
def declared_artifacts_parse(workspace: Path) -> bool:
    for name in ARTIFACTS:
        payload = delivered(workspace, name)
        if payload is None:
            return False
        try:
            text = payload.decode("utf-8")
        except UnicodeError:
            return False
        if not text.endswith("\n") or text.endswith("\n\n"):
            return False
        if "\r" in text or text.startswith("\ufeff"):
            return False
        lines = text.splitlines()
        try:
            if name.endswith(".json"):
                json.loads(text)
            elif name.endswith(".jsonl"):
                for line in lines:
                    json.loads(line)
            elif name.endswith(".csv"):
                if not lines or "," not in lines[0]:
                    return False
            elif name.endswith(".tsv"):
                if not lines or "\t" not in lines[0]:
                    return False
        except (ValueError, RecursionError, MemoryError):
            return False
    return True


@criterion(description="object_inventory.jsonl canonicalises size, mode and class")
def artifact_object_inventory(workspace: Path) -> bool:
    return check_artifact(workspace, "object_inventory.jsonl")


@criterion(description="device_topology.json settles capacity, reserve and geometry")
def artifact_device_topology(workspace: Path) -> bool:
    return check_artifact(workspace, "device_topology.json")


@criterion(description="extent_map.tsv repairs overlap and overrun and classes each range")
def artifact_extent_map(workspace: Path) -> bool:
    return check_artifact(workspace, "extent_map.tsv")


@criterion(description="symlink_topology.jsonl resolves targets without following them")
def artifact_symlink_topology(workspace: Path) -> bool:
    return check_artifact(workspace, "symlink_topology.jsonl")


@criterion(description="mutation_replay.jsonl replays the post-barrier activity in order")
def artifact_mutation_replay(workspace: Path) -> bool:
    return check_artifact(workspace, "mutation_replay.jsonl")


@criterion(description="scope_resolution.csv reports the first failed relocatable condition")
def artifact_scope_resolution(workspace: Path) -> bool:
    return check_artifact(workspace, "scope_resolution.csv")


@criterion(description="link_clusters.jsonl settles each primary path by the four key ladder")
def artifact_link_clusters(workspace: Path) -> bool:
    return check_artifact(workspace, "link_clusters.jsonl")


@criterion(description="resume_state.jsonl separates what the interrupted run committed from what it started")
def artifact_resume_state(workspace: Path) -> bool:
    return check_artifact(workspace, "resume_state.jsonl")


@criterion(description="xattr_ledger.csv carries a row for every relocatable object including those with no attributes")
def artifact_xattr_ledger(workspace: Path) -> bool:
    return check_artifact(workspace, "xattr_ledger.csv")


@criterion(description="special_nodes.tsv rebuilds device numbers and repairs the overflow")
def artifact_special_nodes(workspace: Path) -> bool:
    return check_artifact(workspace, "special_nodes.tsv")


@criterion(description="placement.csv settles the eviction fixed point over the shedding rounds")
def artifact_placement(workspace: Path) -> bool:
    return check_artifact(workspace, "placement.csv")


@criterion(description="sharing_expansion.jsonl materialises one copy per domain and names its owner")
def artifact_sharing_expansion(workspace: Path) -> bool:
    return check_artifact(workspace, "sharing_expansion.jsonl")


@criterion(description="allocation_projection.csv agrees with the placement it summarises")
def artifact_allocation_projection(workspace: Path) -> bool:
    return check_artifact(workspace, "allocation_projection.csv")


@criterion(description="delta_workset.tsv carries only the ranges that are read from the source")
def artifact_delta_workset(workspace: Path) -> bool:
    return check_artifact(workspace, "delta_workset.tsv")


@criterion(description="metadata_workset.jsonl ranks the metadata operations as the contract states")
def artifact_metadata_workset(workspace: Path) -> bool:
    return check_artifact(workspace, "metadata_workset.jsonl")


@criterion(description="window_schedule.tsv respects both the byte budget and the descriptor budget")
def artifact_window_schedule(workspace: Path) -> bool:
    return check_artifact(workspace, "window_schedule.tsv")


@criterion(description="split_ledger.jsonl records every copy cut across windows")
def artifact_split_ledger(workspace: Path) -> bool:
    return check_artifact(workspace, "split_ledger.jsonl")


@criterion(description="descriptor_budget.csv produces a row for every window including the empty ones")
def artifact_descriptor_budget(workspace: Path) -> bool:
    return check_artifact(workspace, "descriptor_budget.csv")


@criterion(description="cutover_sequence.txt orders every directory ahead of what sits beneath it")
def artifact_cutover_sequence(workspace: Path) -> bool:
    return check_artifact(workspace, "cutover_sequence.txt")


@criterion(description="rollback_plan.jsonl pairs each cutover step with its guard and its reverse")
def artifact_rollback_plan(workspace: Path) -> bool:
    return check_artifact(workspace, "rollback_plan.jsonl")


@criterion(description="conservation.json closes the residual to zero on every device")
def artifact_conservation(workspace: Path) -> bool:
    return check_artifact(workspace, "conservation.json")


@criterion(description="manifest.json digests the artifacts in the order the contract states")
def artifact_manifest(workspace: Path) -> bool:
    return check_artifact(workspace, "manifest.json")


@criterion(description="summary.json totals agree with the tables it summarises")
def artifact_summary(workspace: Path) -> bool:
    return check_artifact(workspace, "summary.json")


@criterion(description="cli_contract.json reports the planner's usage and policy codes")
def artifact_cli_contract(workspace: Path) -> bool:
    return check_artifact(workspace, "cli_contract.json")


@criterion(description="the planner's exit codes agree with the contract it delivers")
def exit_codes(workspace: Path) -> bool:
    text = delivered(workspace, "cli_contract.json")
    if text is None:
        return False
    try:
        contract = json.loads(text)
        usage = contract["exit_usage"]
        policy = contract["exit_policy"]
    except (ValueError, KeyError, TypeError, RecursionError, MemoryError):
        return False
    try:
        shape = corpus(EVAL_SEED)
        absent = _tmp("nodir") / "not-a-directory"
        spare = _tmp("exitout")
    except Exception:
        return False
    no_args = invoke_tool(workspace, [])
    one_arg = invoke_tool(workspace, [str(shape)])
    bad_dir = invoke_tool(workspace, [str(absent), str(spare)])
    if no_args is None or one_arg is None or bad_dir is None:
        return False
    return (no_args.returncode == usage
            and one_arg.returncode == usage
            and bad_dir.returncode == policy)


# ---------------------------------------------------------------- negatives

def repeats_itself(workspace: Path) -> bool:
    """True when two runs over one corpus agree. Isolates the controls below
    from nondeterminism, which is owned by its own control."""
    first = tool_outputs(workspace, EVAL_SEED)
    if first is None:
        return False
    return first == repeat_outputs(workspace)


def repeat_outputs(workspace: Path) -> dict[str, bytes] | None:
    with _CACHE_LOCK:
        if workspace not in _repeat_runs:
            _repeat_runs[workspace] = None
            target = _tmp("repeat")
            result = run_tool(workspace, corpus(EVAL_SEED), target)
            if result is not None and result.returncode == 0:
                _repeat_runs[workspace] = _collect(target)
        return _repeat_runs[workspace]


def directory_stable(workspace: Path) -> bool:
    """True when the corpus directory name does not change the result."""
    first = tool_outputs(workspace, EVAL_SEED)
    second = tool_outputs(workspace, EVAL_SEED, tag="alt")
    return first is not None and second is not None and first == second


def tracks_corpus(workspace: Path) -> bool:
    """True when two unseen corpora produce two different plans.

    Both sides are corpora the agent has never held, so a planner that merely
    replayed the shipped answers cannot pass this by accident."""
    first = tool_outputs(workspace, EVAL_SEED)
    second = tool_outputs(workspace, CHALLENGE_SEED)
    return first is not None and second is not None and first != second


@criterion(description="the planner reproduces the shipped corpus exactly and gets every varying artifact wrong on an unseen one")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Inverted polarity: True penalises sample-only correctness, not general correctness.
    sample = tool_outputs(workspace, SAMPLE_SEED)
    want_sample = expected(SAMPLE_SEED)
    want_eval = expected(EVAL_SEED)
    produced_eval = tool_outputs(workspace, EVAL_SEED)
    if None in (sample, want_sample, want_eval, produced_eval):
        return False
    sample_ok = all(sample.get(n, "") == want_sample[n] for n in ARTIFACTS)
    varying = [n for n in ARTIFACTS if want_sample[n] != want_eval[n]]
    eval_all_wrong = all(produced_eval.get(n, "") != want_eval[n] for n in varying)
    return bool(sample_ok and varying and eval_all_wrong)


@criterion(description="the same corpus under a second directory name plans differently")
def negative_corpus_directory_dependence(workspace: Path) -> bool:
    # Inverted polarity: True penalises directory dependence after a stable repeat.
    first = tool_outputs(workspace, EVAL_SEED)
    second = tool_outputs(workspace, EVAL_SEED, tag="alt")
    if first is None or second is None:
        return False
    return repeats_itself(workspace) and first != second


@criterion(description="the delivered planner carries a path from this machine in an executable string")
def negative_hardcodes_machine_path(workspace: Path) -> bool:
    """Only executable string values count. A comment or a docstring naming the
    shipped corpus or delivery path is prose about the run the agent happened to
    do, not a read, so both are stripped before the needle is looked for and an
    honest planner that documents its usage keeps its reward.
    """
    # Inverted polarity: True penalises an executable machine-path literal, not prose.
    tree = tool_ast(workspace)
    if tree is None:
        return False
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    literals = [node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings]
    return any(SHIPPED_CORPUS in text or SHIPPED_OUT in text for text in literals)


@criterion(description="two runs over one corpus disagree")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Inverted polarity: True penalises disagreement between two successful runs.
    first = tool_outputs(workspace, EVAL_SEED)
    if first is None:
        return False
    second = repeat_outputs(workspace)
    return second is not None and first != second


@criterion(description="raising every device reserve leaves the allocation projection unchanged")
def negative_ignores_perturbed_input(workspace: Path) -> bool:
    # Inverted polarity: True penalises ignoring reserves only when other corpus changes register.
    plain = tool_outputs(workspace, EVAL_SEED)
    moved = tool_outputs(workspace, EVAL_SEED, perturb=True)
    if plain is None or moved is None:
        return False
    if not tracks_corpus(workspace):
        return False
    return (plain.get("allocation_projection.csv", "")
            == moved.get("allocation_projection.csv", ""))


@criterion(description="the uploaded output or hidden rerun contains undeclared entries, directories or non-regular files")
def negative_writes_undeclared_files(workspace: Path) -> bool:
    # Inverted polarity: True penalises extras in either output, never missing files alone.
    original_extra = delivery(workspace).undeclared
    tool_outputs(workspace, EVAL_SEED)
    return original_extra or _run_extras.get("{}:[]".format(EVAL_SEED), False)


@criterion(description="reversing the corpus row order changes the plan")
def negative_input_order_dependent_output(workspace: Path) -> bool:
    # Inverted polarity: True penalises row-order dependence after repeat/directory controls.
    straight = tool_outputs(workspace, EVAL_SEED)
    reversed_rows = tool_outputs(workspace, EVAL_SEED, reverse=True)
    if straight is None or reversed_rows is None:
        return False
    if not (repeats_itself(workspace) and directory_stable(workspace)):
        return False
    return straight != reversed_rows


@criterion(description="the delivered planner imports outside the standard library")
def negative_nonstdlib_imports(workspace: Path) -> bool:
    # Inverted polarity: True penalises non-stdlib imports, not dependency rebinding.
    tree = tool_ast(workspace)
    if tree is None:
        return False
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    return bool(sorted(imported - set(sys.stdlib_module_names)))


# ------------------------------------------------------------- registrations

criteria.declared_artifacts_present(weight=1)
criteria.declared_artifacts_parse(weight=1)
criteria.artifact_object_inventory(weight=1)
criteria.artifact_device_topology(weight=1)
criteria.artifact_extent_map(weight=1)
criteria.artifact_symlink_topology(weight=1)
criteria.artifact_mutation_replay(weight=1)
criteria.artifact_scope_resolution(weight=1)
criteria.artifact_link_clusters(weight=1)
criteria.artifact_resume_state(weight=1)
criteria.artifact_xattr_ledger(weight=1)
criteria.artifact_special_nodes(weight=1)
criteria.artifact_cli_contract(weight=1)
criteria.exit_codes(weight=3)
criteria.artifact_placement(weight=5)
criteria.artifact_sharing_expansion(weight=5)
criteria.artifact_allocation_projection(weight=5)
criteria.artifact_delta_workset(weight=5)
criteria.artifact_metadata_workset(weight=5)
criteria.artifact_window_schedule(weight=5)
criteria.artifact_split_ledger(weight=5)
criteria.artifact_descriptor_budget(weight=5)
criteria.artifact_cutover_sequence(weight=5)
criteria.artifact_rollback_plan(weight=5)
criteria.artifact_conservation(weight=5)
criteria.artifact_manifest(weight=5)
criteria.artifact_summary(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_corpus_directory_dependence(weight=-5)
criteria.negative_hardcodes_machine_path(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_ignores_perturbed_input(weight=-5)
criteria.negative_writes_undeclared_files(weight=-5)
criteria.negative_input_order_dependent_output(weight=-3)
criteria.negative_nonstdlib_imports(weight=-3)
