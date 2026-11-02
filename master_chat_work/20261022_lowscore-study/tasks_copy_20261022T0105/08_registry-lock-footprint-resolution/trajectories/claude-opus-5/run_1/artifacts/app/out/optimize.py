#!/usr/bin/env python3
"""Replay benchmark workspaces against a published binary registry index.

Usage: optimize.py <input directory> <output directory>

The program reads a published registry directory (binary index shards, the
registry tables and the policy documents), recovers the six withheld registry
constants from the calibration slice, decodes the field shards and writes nine
JSON documents into the output directory.
"""

import csv
import json
import os
import re
import struct
import sys
import zlib

# Flag word bits of the shard header.
MASK_BYTES = 0x0001
CHAIN_VERSION = 0x0002
DELTA2_DAY = 0x0004
DRIFT_KEY = 0x0008
BLOCK_PERMUTE = 0x0010
BACKREF_DEPS = 0x0020
ENDIAN_ISLAND = 0x0040
BIASED_COUNT = 0x0080
ROT_STATUS = 0x0100
XREF_KEY = 0x0200
SPLIT_TAIL = 0x0400
FULL_FLAG_SET = 0x07FF

M32 = 0xFFFFFFFF
ZERO_DEP = (0, 0, 0, 0, 0)
MOD = 1000003

PARAM_ORDER = [
    "salt",
    "window_span",
    "bias_limit",
    "rotation_base",
    "permutation_multiplier",
    "quarantine_days",
]

# Candidate list labels of the calibration slice, mapped to parameter names.
CONSTANT_LABELS = {
    "salt word": "salt",
    "window span": "window_span",
    "bias limit": "bias_limit",
    "rotation base": "rotation_base",
    "shuffle multiplier": "permutation_multiplier",
    "quarantine days": "quarantine_days",
}

DEFAULT_PERMISSIVE = {
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib",
    "Unlicense",
}
DEFAULT_COPYLEFT = {
    "GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0", "MPL-2.0",
    "EPL-2.0",
}


class Unreadable(Exception):
    """A shard cannot be read under the assignment in force."""


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------


def crc(block):
    return zlib.crc32(block) & M32


def rotr16(value, places):
    places &= 15
    if places == 0:
        return value & 0xFFFF
    return ((value >> places) | (value << (16 - places))) & 0xFFFF


def vstr(code):
    return "%d.%d.%d" % ((code >> 16) & 0xFFFF, (code >> 8) & 0xFF, code & 0xFF)


def vcode(text):
    major, minor, patch = (int(part) for part in text.split("."))
    return major * 65536 + minor * 256 + patch


# --------------------------------------------------------------------------
# shard decoding
# --------------------------------------------------------------------------


def load_shards(directory):
    shards = {}
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            data = handle.read()
        if data[0:4] == b"PIDX":
            shards[name] = data
    return shards


def read_header(data):
    if len(data) < 20 or data[0:4] != b"PIDX":
        raise Unreadable("magic")
    flags = struct.unpack_from("<H", data, 6)[0]
    nonce_fmt = ">I" if flags & ENDIAN_ISLAND else "<I"
    return {
        "format_version": data[4],
        "tier": data[5],
        "flags": flags,
        "nonce": struct.unpack_from(nonce_fmt, data, 8)[0],
        "area_len": struct.unpack_from("<I", data, 12)[0],
        "stored_count": struct.unpack_from("<H", data, 16)[0],
        "check": struct.unpack_from("<H", data, 18)[0],
        "size": len(data),
    }


def companions(headers):
    """Companion shard nonce of every shard, taken within its own tier."""
    by_tier = {}
    for name, header in headers.items():
        by_tier.setdefault(header["tier"], []).append((header["nonce"], name))
    result = {}
    for members in by_tier.values():
        members.sort()
        for index, (_nonce, name) in enumerate(members):
            result[name] = members[index - 1][0] if index > 0 else members[-1][0]
    return result


def bias_of(salt, bias_limit, nonce):
    digest = crc(salt.encode("ascii") + struct.pack("<I", nonce))
    return (digest & 0xFF) % bias_limit


def true_block_count(header, salt, bias_limit):
    if not header["flags"] & BIASED_COUNT:
        return header["stored_count"]
    bias = bias_of(salt, bias_limit, header["nonce"])
    return header["stored_count"] - bias


def structural(data, header, rotation_base, window_span, companion_nonce,
               count=None):
    """Parse the blocks of a shard in file order.

    The byte layout depends only on the rotation base and the window span, so
    this parse is independent of the salt, the bias limit and the multiplier.
    With ``count`` None the parse runs until the block area ends, which names
    the only block count the bytes admit.
    """
    flags = header["flags"]
    limit = len(data)
    area_end = 20 + header["area_len"]
    if area_end > limit:
        raise Unreadable("block area past end of file")
    chained = flags & CHAIN_VERSION
    delta2 = flags & DELTA2_DAY
    backref = flags & BACKREF_DEPS
    big_endian = flags & ENDIAN_ISLAND
    rotated = flags & ROT_STATUS
    xref = flags & XREF_KEY
    split_tail = flags & SPLIT_TAIL
    count_fmt = ">H" if big_endian else "<H"

    blocks = []
    offset = 20
    while True:
        if count is None:
            if offset == area_end:
                break
            if offset > area_end:
                raise Unreadable("block area ends after its last block")
        elif len(blocks) == count:
            break
        start = offset
        if offset + 10 > limit:
            raise Unreadable("block header past end of file")
        key = struct.unpack_from("<I", data, offset)[0]
        if xref:
            key ^= companion_nonce
        record_count = struct.unpack_from(count_fmt, data, offset + 4)[0]
        block_nonce = struct.unpack_from("<I", data, offset + 6)[0]
        offset += 10

        records = []
        previous_code = 0
        day_back1 = 0
        day_back2 = 0
        ring = [ZERO_DEP] * window_span if backref else None
        for ordinal in range(record_count):
            if offset + 12 > limit:
                raise Unreadable("version record past end of file")
            stored_code, stored_bytes = struct.unpack_from("<II", data, offset)
            stored_day, stored_status = struct.unpack_from("<HH", data, offset + 8)
            offset += 12
            if chained and ordinal > 0:
                code = (previous_code + stored_code) & M32
            else:
                code = stored_code
            previous_code = code
            if delta2:
                day = (stored_day + 2 * day_back1 - day_back2) & 0xFFFF
            else:
                day = stored_day
            day_back2 = day_back1
            day_back1 = day
            if rotated:
                status_word = rotr16(
                    stored_status, (rotation_base + (ordinal % 8)) % 16
                )
            else:
                status_word = stored_status
            status = status_word >> 8
            dependency_count = status_word & 0xFF

            dependencies = []
            for _ in range(dependency_count):
                back_referenced = False
                if backref:
                    if offset + 1 > limit:
                        raise Unreadable("dependency tag past end of file")
                    tag = data[offset]
                    offset += 1
                    if tag == 0:
                        if offset + 14 > limit:
                            raise Unreadable("dependency entry past end of file")
                        target, low, high = struct.unpack_from("<III", data, offset)
                        entry = (target, low, high, data[offset + 12],
                                 data[offset + 13])
                        offset += 14
                    elif tag > window_span:
                        raise Unreadable("back reference tag above window span")
                    else:
                        entry = ring[window_span - tag]
                        back_referenced = True
                    ring.insert(0, entry)
                    ring.pop()
                else:
                    if offset + 14 > limit:
                        raise Unreadable("dependency entry past end of file")
                    target, low, high = struct.unpack_from("<III", data, offset)
                    entry = (target, low, high, data[offset + 12],
                             data[offset + 13])
                    offset += 14
                dependencies.append((entry, back_referenced))
            records.append({
                "code": code,
                "stored_bytes": stored_bytes,
                "day": day,
                "status": status,
                "dependency_count": dependency_count,
                "dependencies": dependencies,
            })
        if offset + 4 > limit:
            raise Unreadable("block trailer past end of file")
        trailer = struct.unpack_from("<I", data, offset)[0]
        if trailer != crc(data[start:offset]):
            raise Unreadable("block trailer does not match")
        offset += 4
        if split_tail:
            offset += block_nonce % 7
            if offset > limit:
                raise Unreadable("split tail past end of file")
        blocks.append({
            "key": key,
            "block_nonce": block_nonce,
            "records": records,
        })

    if offset != area_end:
        raise Unreadable("block area ends before or after its last block")
    return blocks


def permutation(nonce, count, multiplier):
    """Position k of the returned list names the logical block written k-th."""
    order = list(range(count))
    state = nonce
    for i in range(count - 1, 0, -1):
        state = (state * multiplier + 0x9E3779B9) & M32
        j = state % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def logical_order(header, blocks, multiplier):
    """Return the blocks of a shard in logical order."""
    count = len(blocks)
    if header["flags"] & BLOCK_PERMUTE:
        logical_of_file = permutation(header["nonce"], count, multiplier)
    else:
        logical_of_file = list(range(count))
    file_of_logical = [0] * count
    for file_index, logical_index in enumerate(logical_of_file):
        file_of_logical[logical_index] = file_index
    order = []
    for logical_index in range(count):
        block = blocks[file_of_logical[logical_index]]
        block["logical"] = logical_index
        order.append(block)
    return order


def apply_mask(header, order, salt):
    """Attach the true artifact bytes to every record of a logical ordering."""
    flags = header["flags"]
    salt_bytes = salt.encode("ascii")
    nonce_bytes = struct.pack("<I", header["nonce"])
    drift = 0
    for block in order:
        if flags & DRIFT_KEY:
            block_key = block["block_nonce"] ^ drift
        else:
            block_key = block["block_nonce"]
        block["block_key"] = block_key
        prefix = salt_bytes + nonce_bytes + struct.pack("<I", block_key)
        total = 0
        for ordinal, record in enumerate(block["records"]):
            if flags & MASK_BYTES:
                keystream = crc(prefix + struct.pack("<H", ordinal))
                record["bytes"] = record["stored_bytes"] ^ keystream
            else:
                record["bytes"] = record["stored_bytes"]
            total = (total + record["bytes"]) & M32
        if flags & DRIFT_KEY:
            drift = (drift + total) & M32
    return order


# --------------------------------------------------------------------------
# published documents
# --------------------------------------------------------------------------


def table_rows(text):
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and set("".join(cells)) <= set("- :"):
            continue
        yield cells


def parse_calibration(path):
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    candidates = {}
    controls = []
    for cells in table_rows(text):
        if len(cells) == 2 and cells[0].lower() in CONSTANT_LABELS:
            parameter = CONSTANT_LABELS[cells[0].lower()]
            candidates[parameter] = [
                (token, convert_candidate(parameter, token))
                for token in cells[1].split()
            ]
        elif len(cells) == 3 and re.match(r"^CTRL-\d+$", cells[0]):
            controls.append((cells[0], cells[1], int(cells[2])))
    controls.sort(key=lambda row: int(row[0].split("-")[1]))
    match = re.search(r"snapshot day\D*(\d+)", text, re.IGNORECASE)
    return {
        "candidates": candidates,
        "controls": controls,
        "snapshot_day": int(match.group(1)),
    }


def convert_candidate(parameter, token):
    if parameter == "salt":
        return token
    if parameter == "permutation_multiplier":
        return int(token, 16)
    return int(token)


def parse_licences(path):
    permissive = set()
    copyleft = set()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return set(DEFAULT_PERMISSIVE), set(DEFAULT_COPYLEFT)
    for line in text.splitlines():
        match = re.match(r"\s*Permissive:\s*(.+)", line)
        if match:
            permissive = split_identifiers(match.group(1))
        match = re.match(r"\s*Copyleft:\s*(.+)", line)
        if match:
            copyleft = split_identifiers(match.group(1))
    return (permissive or set(DEFAULT_PERMISSIVE),
            copyleft or set(DEFAULT_COPYLEFT))


def split_identifiers(text):
    return {part.strip().rstrip(".").strip() for part in text.split(",")
            if part.strip().rstrip(".").strip()}


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def licence_family(expression, permissive, copyleft):
    if " OR " in expression:
        parts = [part.strip() for part in expression.split(" OR ")]
        return "permissive" if any(p in permissive for p in parts) else "copyleft"
    if " AND " in expression:
        parts = [part.strip() for part in expression.split(" AND ")]
        return "copyleft" if any(p in copyleft for p in parts) else "permissive"
    return "permissive" if expression.strip() in permissive else "copyleft"


def build_registry(rows, permissive, copyleft):
    """Fold the registry rows into rename chains."""
    by_name = {}
    for row in rows:
        by_name[row["package"]] = {
            "name": row["package"],
            "key": int(row["package_key"], 16),
            "renamed_from": (row.get("renamed_from") or "").strip(),
            "licence": (row.get("licence") or "").strip(),
        }
    successor = {}
    for entry in by_name.values():
        if entry["renamed_from"]:
            successor[entry["renamed_from"]] = entry["name"]

    chains = {}
    chain_of_key = {}
    reported_of_name = {}
    for entry in by_name.values():
        if entry["renamed_from"]:
            continue
        names = [entry["name"]]
        while names[-1] in successor:
            names.append(successor[names[-1]])
        reported = names[-1]
        earliest = by_name[names[0]]["licence"]
        newest = by_name[reported]["licence"]
        chains[reported] = {
            "reported": reported,
            "names": names,
            "keys": [by_name[name]["key"] for name in names],
            "governing_licence": earliest,
            "newest_licence": newest,
            "governing_family": licence_family(earliest, permissive, copyleft),
            "newest_family": licence_family(newest, permissive, copyleft),
            "versions": {},
        }
        for name in names:
            reported_of_name[name] = reported
            chain_of_key[by_name[name]["key"]] = reported
    return chains, chain_of_key, reported_of_name, set(chain_of_key)


# --------------------------------------------------------------------------
# calibration figures and constant recovery
# --------------------------------------------------------------------------


def structural_figures(parsed, names):
    block_total = 0
    dependency_digest = 0
    status_digest = 0
    for name in names:
        blocks = parsed[name]
        block_total += len(blocks)
        for block in blocks:
            for ordinal, record in enumerate(block["records"], start=1):
                status_digest += (3 * record["status"]
                                  + record["dependency_count"]) * ordinal
                for position, (entry, _back) in enumerate(
                        record["dependencies"], start=1):
                    target, low, _high, mask, gate = entry
                    dependency_digest += (((target ^ low) + 7 * mask + gate)
                                          * position * ordinal)
    return (block_total, dependency_digest % MOD, status_digest % MOD)


def key_digest_of(headers, parsed, names, multiplier):
    digest = 0
    for name in names:
        order = logical_order(headers[name], parsed[name], multiplier)
        for position, block in enumerate(order, start=1):
            digest += block["key"] * position
    return digest % MOD


def size_digest_of(headers, parsed, names, salt, multiplier):
    digest = 0
    for name in names:
        order = apply_mask(
            headers[name],
            logical_order(headers[name], parsed[name], multiplier),
            salt,
        )
        for block in order:
            for ordinal, record in enumerate(block["records"], start=1):
                digest += (record["bytes"] + record["code"]) * ordinal
    return digest % MOD


def eligible_records_of(parsed, names, quarantine_days, snapshot_day):
    total = 0
    for name in names:
        for block in parsed[name]:
            for record in block["records"]:
                if record["status"] & 1:
                    continue
                if record["day"] > snapshot_day:
                    continue
                if snapshot_day - record["day"] < quarantine_days:
                    continue
                total += 1
    return total


def compute_figures(headers, parsed, names, assignment, snapshot_day):
    block_total, dependency_digest, status_digest = structural_figures(parsed, names)
    return {
        "calibration_block_total": block_total,
        "calibration_key_digest": key_digest_of(
            headers, parsed, names, assignment["permutation_multiplier"]),
        "calibration_size_digest": size_digest_of(
            headers, parsed, names, assignment["salt"],
            assignment["permutation_multiplier"]),
        "calibration_dependency_digest": dependency_digest,
        "calibration_status_digest": status_digest,
        "calibration_eligible_records": eligible_records_of(
            parsed, names, assignment["quarantine_days"], snapshot_day),
    }


def read_tier(raw, headers, comp, names, assignment):
    """Forward reader: the block count follows from the stored count and bias."""
    parsed = {}
    for name in names:
        header = headers[name]
        count = true_block_count(header, assignment["salt"],
                                 assignment["bias_limit"])
        if count < 0:
            raise Unreadable("negative true block count")
        parsed[name] = structural(
            raw[name], header, assignment["rotation_base"],
            assignment["window_span"], comp[name], count)
    return parsed


def falsifier_of(raw, headers, comp, names, assignment, controls, snapshot_day):
    """UNREADABLE, or the first published control whose figure differs."""
    try:
        parsed = read_tier(raw, headers, comp, names, assignment)
    except Unreadable:
        return "UNREADABLE"
    figures = compute_figures(headers, parsed, names, assignment, snapshot_day)
    for control, figure, published in controls:
        if figures.get(figure) != published:
            return control
    return None


def recover(raw, headers, comp, calibration_names, calibration):
    """Find the one assignment that reproduces every published control."""
    candidates = calibration["candidates"]
    controls = calibration["controls"]
    snapshot_day = calibration["snapshot_day"]
    published = {figure: value for _c, figure, value in controls}

    structures = {}
    for _raw_rotation, rotation in candidates["rotation_base"]:
        for _raw_span, span in candidates["window_span"]:
            try:
                parsed = {
                    name: structural(raw[name], headers[name], rotation, span,
                                     comp[name], None)
                    for name in calibration_names
                }
            except Unreadable:
                continue
            structures[(rotation, span)] = parsed

    matches = []
    for (rotation, span), parsed in sorted(structures.items()):
        block_total, dependency_digest, status_digest = structural_figures(
            parsed, calibration_names)
        if published.get("calibration_block_total") != block_total:
            continue
        if published.get("calibration_dependency_digest") != dependency_digest:
            continue
        if published.get("calibration_status_digest") != status_digest:
            continue
        counts = {name: len(parsed[name]) for name in calibration_names}
        salt_options = []
        for _raw_salt, salt in candidates["salt"]:
            for _raw_limit, limit in candidates["bias_limit"]:
                if all(true_block_count(headers[name], salt, limit)
                       == counts[name] for name in calibration_names):
                    salt_options.append((salt, limit))
        if not salt_options:
            continue
        for _raw_mult, multiplier in candidates["permutation_multiplier"]:
            if published.get("calibration_key_digest") != key_digest_of(
                    headers, parsed, calibration_names, multiplier):
                continue
            for salt, limit in salt_options:
                if published.get("calibration_size_digest") != size_digest_of(
                        headers, parsed, calibration_names, salt, multiplier):
                    continue
                for _raw_quar, quarantine in candidates["quarantine_days"]:
                    if published.get("calibration_eligible_records") != \
                            eligible_records_of(parsed, calibration_names,
                                                quarantine, snapshot_day):
                        continue
                    matches.append({
                        "salt": salt,
                        "window_span": span,
                        "bias_limit": limit,
                        "rotation_base": rotation,
                        "permutation_multiplier": multiplier,
                        "quarantine_days": quarantine,
                    })
    if len(matches) != 1:
        raise SystemExit(
            "expected exactly one assignment reproducing every control, "
            "found %d" % len(matches))
    accepted = matches[0]

    rows = []
    totals = {}
    for parameter in PARAM_ORDER:
        for token, value in candidates[parameter]:
            if value == accepted[parameter]:
                rows.append({
                    "parameter": parameter,
                    "value": token,
                    "verdict": "accepted",
                    "falsifier": "none",
                })
                continue
            rival = dict(accepted)
            rival[parameter] = value
            label = falsifier_of(raw, headers, comp, calibration_names, rival,
                                 controls, snapshot_day)
            if label is None:
                raise SystemExit(
                    "rival %s=%s reproduces every control" % (parameter, token))
            rows.append({
                "parameter": parameter,
                "value": token,
                "verdict": "rejected",
                "falsifier": label,
            })
            totals[label] = totals.get(label, 0) + 1

    parsed = read_tier(raw, headers, comp, calibration_names, accepted)
    figures = compute_figures(headers, parsed, calibration_names, accepted,
                             snapshot_day)
    table = [{
        "control": control,
        "figure": figure,
        "published": value,
        "reproduced": figures[figure],
    } for control, figure, value in controls]
    return accepted, rows, totals, table


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------


def settle(context, chosen, direct):
    """Smallest feature assignment of a locked set, with the pass count."""
    packages = context["chains"]
    chain_of_key = context["chain_of_key"]
    masks = {name: direct.get(name, 0) for name in chosen}
    passes = 0
    while True:
        passes += 1
        collected = {}
        for name, code in chosen.items():
            mask = masks[name]
            for entry in packages[name]["versions"][code]["dependencies"]:
                target_key, _low, _high, requested, gate = entry
                if gate != 255 and not (mask >> gate) & 1:
                    continue
                target = chain_of_key.get(target_key)
                if target is None or target not in masks:
                    continue
                collected[target] = collected.get(target, 0) | requested
        changed = False
        for target, requested in collected.items():
            if masks[target] | requested != masks[target]:
                masks[target] |= requested
                changed = True
        if not changed:
            return masks, passes


def best_plan(context, workspace, families):
    """The valid lock plan of smallest footprint, or None."""
    packages = context["chains"]
    chain_of_key = context["chain_of_key"]
    quarantine = context["assignment"]["quarantine_days"]
    snapshot_day = workspace["snapshot_day"]
    allow_copyleft = workspace["copyleft"] == "allowed"

    eligible = {}
    for name, chain in packages.items():
        codes = []
        for code in sorted(chain["versions"]):
            record = chain["versions"][code]
            if record["status"] & 1:
                continue
            if record["day"] > snapshot_day:
                continue
            if snapshot_day - record["day"] < quarantine:
                continue
            codes.append(code)
        eligible[name] = codes
    allowed = {}
    for name in packages:
        if not allow_copyleft and families[name] == "copyleft":
            allowed[name] = []
        else:
            allowed[name] = eligible[name]

    direct = {}
    ranges = {}
    for requirement in context["requirements"].get(workspace["workspace"], []):
        name = context["reported_of_name"].get(requirement["package"])
        if name is None:
            return None
        direct[name] = direct.get(name, 0) | requirement["features"]
        ranges.setdefault(name, []).append((requirement["lowest"],
                                            requirement["below"]))

    required = sorted(ranges)
    required_codes = {}
    for name in required:
        codes = [code for code in allowed[name]
                 if all(low <= code < high for low, high in ranges[name])]
        if not codes:
            return None
        required_codes[name] = codes

    best = [None]

    def footprint(chosen):
        return sum(packages[name]["versions"][code]["bytes"]
                   for name, code in chosen.items())

    def active_entries(chosen, masks):
        for name, code in chosen.items():
            mask = masks[name]
            for entry in packages[name]["versions"][code]["dependencies"]:
                if entry[4] != 255 and not (mask >> entry[4]) & 1:
                    continue
                yield name, entry

    def settle_plan(chosen):
        masks, passes = settle(context, chosen, direct)
        for _name, entry in active_entries(chosen, masks):
            target = chain_of_key.get(entry[0])
            if target is None or target not in chosen:
                return None
            if not entry[1] <= chosen[target] < entry[2]:
                return None
        return masks, passes

    def record(chosen):
        settled = settle_plan(chosen)
        if settled is None:
            return
        masks, passes = settled
        total = footprint(chosen)
        code_sum = sum(chosen.values())
        text = ",".join("%s@%08x" % (name, chosen[name])
                        for name in sorted(chosen))
        ordering = (total, -code_sum, text)
        if best[0] is None or ordering < best[0]["ordering"]:
            best[0] = {
                "ordering": ordering,
                "plan": dict(chosen),
                "masks": masks,
                "passes": passes,
                "footprint": total,
            }

    def extend(chosen):
        if best[0] is not None and footprint(chosen) > best[0]["ordering"][0]:
            return
        masks, _passes = settle(context, chosen, direct)
        missing = None
        for name in sorted(chosen):
            mask = masks[name]
            for entry in packages[name]["versions"][chosen[name]]["dependencies"]:
                if entry[4] != 255 and not (mask >> entry[4]) & 1:
                    continue
                target = chain_of_key.get(entry[0])
                if target is None:
                    return
                if target not in chosen:
                    missing = target
                    break
            if missing is not None:
                break
        if missing is None:
            record(chosen)
            return
        bounds = []
        for _name, entry in active_entries(chosen, masks):
            if chain_of_key.get(entry[0]) == missing:
                bounds.append((entry[1], entry[2]))
        for code in allowed[missing]:
            if all(low <= code < high for low, high in bounds):
                chosen[missing] = code
                extend(chosen)
                del chosen[missing]

    def choose(index, chosen):
        if index == len(required):
            extend(chosen)
            return
        name = required[index]
        for code in required_codes[name]:
            chosen[name] = code
            choose(index + 1, chosen)
            del chosen[name]

    choose(0, {})
    if best[0] is None:
        return None
    best[0]["eligible"] = eligible
    return best[0]


# --------------------------------------------------------------------------
# documents
# --------------------------------------------------------------------------


def write_json(path, document):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")


def build(input_dir):
    calibration = parse_calibration(os.path.join(input_dir, "calibration.md"))
    permissive, copyleft = parse_licences(
        os.path.join(input_dir, "licence-policy.md"))
    registry_rows = read_csv(os.path.join(input_dir, "package-registry.csv"))
    workspace_rows = read_csv(os.path.join(input_dir, "workspaces.csv"))
    requirement_rows = read_csv(
        os.path.join(input_dir, "workspace-requirements.csv"))

    chains, chain_of_key, reported_of_name, registered_keys = build_registry(
        registry_rows, permissive, copyleft)

    raw = load_shards(input_dir)
    headers = {name: read_header(data) for name, data in raw.items()}
    comp = companions(headers)
    calibration_names = sorted(name for name, header in headers.items()
                               if header["tier"] == 1)
    field_names = sorted(name for name, header in headers.items()
                         if header["tier"] == 2)

    assignment, candidate_rows, totals, table = recover(
        raw, headers, comp, calibration_names, calibration)

    field = read_tier(raw, headers, comp, field_names, assignment)
    for name in field_names:
        apply_mask(headers[name],
                   logical_order(headers[name], field[name],
                                 assignment["permutation_multiplier"]),
                   assignment["salt"])

    stats = {
        "blocks": 0,
        "records": 0,
        "dependency_entries": 0,
        "decoded_bytes": 0,
        "excluded_unregistered": 0,
        "excluded_yanked": 0,
        "records_yanked": 0,
        "records_deprecated": 0,
        "records_unregistered": 0,
        "back_referenced": 0,
        "unregistered_target": 0,
        "full_flag_set": 0,
    }
    all_records = []
    for name in field_names:
        if headers[name]["flags"] == FULL_FLAG_SET:
            stats["full_flag_set"] += 1
        for block in field[name]:
            stats["blocks"] += 1
            reported = chain_of_key.get(block["key"])
            for record in block["records"]:
                stats["records"] += 1
                stats["decoded_bytes"] += record["bytes"]
                if record["status"] & 2:
                    stats["records_deprecated"] += 1
                if reported is None:
                    stats["records_unregistered"] += 1
                    stats["excluded_unregistered"] += record["bytes"]
                else:
                    if record["status"] & 1:
                        stats["records_yanked"] += 1
                        stats["excluded_yanked"] += record["bytes"]
                    all_records.append((reported, record))
                for entry, back_referenced in record["dependencies"]:
                    stats["dependency_entries"] += 1
                    if back_referenced:
                        stats["back_referenced"] += 1
                    if entry[0] not in registered_keys:
                        stats["unregistered_target"] += 1
                if reported is not None:
                    chains[reported]["versions"][record["code"]] = {
                        "bytes": record["bytes"],
                        "day": record["day"],
                        "status": record["status"],
                        "dependencies": [entry for entry, _b
                                         in record["dependencies"]],
                    }

    requirements = {}
    for row in requirement_rows:
        requirements.setdefault(row["workspace"], []).append({
            "package": row["package"],
            "lowest": vcode(row["lowest"]),
            "below": vcode(row["below"]),
            "features": int(row["features"]),
        })

    workspaces = [{
        "workspace": row["workspace"],
        "snapshot_day": int(row["snapshot_day"]),
        "copyleft": row["copyleft"],
    } for row in workspace_rows]

    context = {
        "chains": chains,
        "chain_of_key": chain_of_key,
        "reported_of_name": reported_of_name,
        "requirements": requirements,
        "assignment": assignment,
    }

    governing = {name: chain["governing_family"]
                 for name, chain in chains.items()}
    newest = {name: chain["newest_family"] for name, chain in chains.items()}

    documents = {}
    footprints = {}
    passes_by_workspace = {}
    locked_versions = {}
    bottleneck = []
    divergence = []
    resolved = 0

    for workspace in workspaces:
        result = best_plan(context, workspace, governing)
        quarantined = 0
        for reported, record in all_records:
            if record["status"] & 1:
                continue
            if record["day"] > workspace["snapshot_day"]:
                continue
            if workspace["snapshot_day"] - record["day"] < \
                    assignment["quarantine_days"]:
                continue
            quarantined += 1
        entries = []
        held_back = []
        permissive_names = []
        copyleft_names = []
        if result is None:
            footprints[workspace["workspace"]] = 0
            passes_by_workspace[workspace["workspace"]] = 0
            footprint_total = 0
            package_count = 0
        else:
            resolved += 1
            plan = result["plan"]
            footprint_total = result["footprint"]
            package_count = len(plan)
            footprints[workspace["workspace"]] = footprint_total
            passes_by_workspace[workspace["workspace"]] = result["passes"]
            for name in sorted(plan):
                code = plan[name]
                version = chains[name]["versions"][code]
                locked_versions[(name, code)] = version["bytes"]
                entries.append({
                    "package": name,
                    "version": vstr(code),
                    "features": result["masks"][name],
                    "licence_family": governing[name],
                    "bytes": version["bytes"],
                })
                newest_eligible = max(result["eligible"][name])
                if code < newest_eligible:
                    held_back.append({
                        "package": name,
                        "locked": vstr(code),
                        "newest_eligible": vstr(newest_eligible),
                    })
                if governing[name] == "permissive":
                    permissive_names.append(name)
                else:
                    copyleft_names.append(name)

        documents["scenario_%s.json" % workspace["workspace"]] = {
            "workspace": workspace["workspace"],
            "snapshot_day": workspace["snapshot_day"],
            "copyleft": workspace["copyleft"],
            "footprint_bytes": footprint_total,
            "package_count": package_count,
            "quarantined_records": quarantined,
            "packages": entries,
        }
        bottleneck.append({
            "workspace": workspace["workspace"],
            "held_back": held_back,
            "permissive_packages": sorted(permissive_names),
            "copyleft_packages": sorted(copyleft_names),
        })

        rival = best_plan(context, workspace, newest)
        if rival is None:
            if result is not None:
                divergence.append(workspace["workspace"])
        elif result is None or rival["plan"] != result["plan"]:
            divergence.append(workspace["workspace"])

    locked_bytes = sum(locked_versions.values())
    excluded = stats["excluded_unregistered"] + stats["excluded_yanked"]
    documents["perf_report.json"] = {
        "shards_decoded": len(field_names),
        "blocks_decoded": stats["blocks"],
        "records_decoded": stats["records"],
        "dependency_entries_decoded": stats["dependency_entries"],
        "decoded_bytes": stats["decoded_bytes"],
        "excluded_bytes": excluded,
        "locked_bytes": locked_bytes,
        "byte_residual": stats["decoded_bytes"] - excluded - locked_bytes,
        "workspaces_resolved": resolved,
        "footprint_by_workspace": footprints,
        "recovered_parameters": {
            "salt": assignment["salt"],
            "window_span": assignment["window_span"],
            "bias_limit": assignment["bias_limit"],
            "rotation_base": assignment["rotation_base"],
            "quarantine_days": assignment["quarantine_days"],
            "permutation_multiplier": "0x%08x" % assignment[
                "permutation_multiplier"],
        },
    }
    documents["bottleneck_analysis.json"] = {
        "workspaces": sorted(bottleneck, key=lambda row: row["workspace"]),
    }
    documents["data_quality.json"] = {
        "total_shards": len(field_names),
        "shards_with_full_flag_set": stats["full_flag_set"],
        "records_yanked": stats["records_yanked"],
        "records_deprecated": stats["records_deprecated"],
        "records_unregistered_package": stats["records_unregistered"],
        "dependency_entries_back_referenced": stats["back_referenced"],
        "dependency_entries_unregistered_target": stats["unregistered_target"],
        "excluded_bytes_by_cause": {
            "unregistered_package": stats["excluded_unregistered"],
            "yanked": stats["excluded_yanked"],
        },
    }
    documents["recommendations.json"] = {
        "candidates": candidate_rows,
        "falsifier_totals": totals,
        "calibration_table": table,
        "settlement_passes_by_workspace": passes_by_workspace,
        "licence_divergence": sorted(divergence),
    }

    diagnostics = {
        "assignment": assignment,
        "chains": chains,
        "candidate_rows": candidate_rows,
        "calibration_table": table,
    }
    return documents, diagnostics


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: optimize.py <input directory> <output directory>")
    input_dir, output_dir = argv[1], argv[2]
    documents, _diagnostics = build(input_dir)
    os.makedirs(output_dir, exist_ok=True)
    for name in sorted(documents):
        write_json(os.path.join(output_dir, name), documents[name])


if __name__ == "__main__":
    main(sys.argv)
