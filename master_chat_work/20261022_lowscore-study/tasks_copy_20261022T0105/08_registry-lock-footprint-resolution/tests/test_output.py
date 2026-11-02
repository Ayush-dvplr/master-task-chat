"""Graded checks for the registry lock footprint resolution task.

This module is self contained: it carries the index shard writer that produced
environment/data/, a reference shard reader used for the calibration figures,
the expectation model that settles every lock plan from plaintext, the staging
harness and the graded rewardkit criteria. Every check takes the workspace and
returns a bool; none of them raises, because an exception inside a check would
abort the whole rewardkit run and leave no reward at all.

Negative checks return True when the shortcut is present, so an honest program
makes them return False and the negative weight is never added.

The graded weight sits on the generalisation tiers, whose corpora each carry
their own withheld constants. The checks that read the shipped documents in
/app/out are deliberately weighted 1: a program that merely replays memorised
documents can satisfy them, so they are priced as the existence checks they are
rather than as evidence the work was done.
"""
# pyright: reportUndefinedVariable=false, reportArgumentType=false
from __future__ import annotations

import ast
import copy
import json
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import zlib
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

SAMPLE_SEED = 20260915
SEED = SAMPLE_SEED


MAGIC = b"PIDX"
FORMAT_VERSION = 2
HEADER_LEN = 20
BLOCK_HEADER_LEN = 10
RECORD_HEAD_LEN = 12
DEP_LEN = 14
TRAILER_LEN = 4
ALWAYS = 0xFF
MODULUS = 1000003

FLAG_MASK_BYTES = 0x0001
FLAG_CHAIN_VERSION = 0x0002
FLAG_DELTA2_DAY = 0x0004
FLAG_DRIFT_KEY = 0x0008
FLAG_BLOCK_PERMUTE = 0x0010
FLAG_BACKREF_DEPS = 0x0020
FLAG_ENDIAN_ISLAND = 0x0040
FLAG_BIASED_COUNT = 0x0080
FLAG_ROT_STATUS = 0x0100
FLAG_XREF_KEY = 0x0200
FLAG_SPLIT_TAIL = 0x0400
ALL_FLAGS = 0x07FF

FLAG_NAMES = (
    ("MASK_BYTES", FLAG_MASK_BYTES),
    ("CHAIN_VERSION", FLAG_CHAIN_VERSION),
    ("DELTA2_DAY", FLAG_DELTA2_DAY),
    ("DRIFT_KEY", FLAG_DRIFT_KEY),
    ("BLOCK_PERMUTE", FLAG_BLOCK_PERMUTE),
    ("BACKREF_DEPS", FLAG_BACKREF_DEPS),
    ("ENDIAN_ISLAND", FLAG_ENDIAN_ISLAND),
    ("BIASED_COUNT", FLAG_BIASED_COUNT),
    ("ROT_STATUS", FLAG_ROT_STATUS),
    ("XREF_KEY", FLAG_XREF_KEY),
    ("SPLIT_TAIL", FLAG_SPLIT_TAIL),
)

STATUS_YANKED = 0x01
STATUS_DEPRECATED = 0x02

TIER_SAMPLE = 0
TIER_CALIBRATION = 1
TIER_FIELD = 2

SALT_VOCAB = ["ALDER", "BIRCH", "CEDAR", "ELDER", "FIR", "HAZEL", "LARCH", "MAPLE", "ROWAN", "SPRUCE"]
WINDOW_VOCAB = [2, 3, 4, 5, 6, 7, 8, 10, 12, 16]
BIAS_VOCAB = [3, 5, 7, 11, 13, 17, 19, 23, 29, 31]
ROTATE_VOCAB = [1, 2, 3, 4, 5, 6, 7, 9, 11, 13]
PERMUTE_VOCAB = [
    0x2545F491, 0x27220A95, 0x9E3779B1, 0x85EBCA77, 0xC2B2AE3D,
    0x1B873593, 0xCC9E2D51, 0x6D2B79F5, 0x7FEB352D, 0x846CA68B,
]
QUARANTINE_VOCAB = [0, 1, 2, 3, 5, 7, 10, 14, 21, 30]

TRUE_PARAMS = {
    "salt": "ROWAN",
    "window": 6,
    "bias": 13,
    "rotate": 9,
    "permute": 0x846CA68B,
    "quarantine": 7,
}

PARAM_ORDER = ("salt", "window", "bias", "rotate", "permute", "quarantine")
VOCABS = {
    "salt": SALT_VOCAB,
    "window": WINDOW_VOCAB,
    "bias": BIAS_VOCAB,
    "rotate": ROTATE_VOCAB,
    "permute": PERMUTE_VOCAB,
    "quarantine": QUARANTINE_VOCAB,
}

SEARCH_STATE_CAP = 200000

WORKSPACE_NAMES = ("visible", "peak", "steady", "burst", "latency")

PERMISSIVE = ("MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib", "Unlicense")
COPYLEFT = ("GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0", "MPL-2.0", "EPL-2.0")


class Rng:
    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFFFFFFFFFF or 0xA0761D6478BD642F

    def _next(self) -> int:
        x = self.state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.state = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def rand_int(self, lo: int, hi: int) -> int:
        return lo + self._next() % (hi - lo + 1)

    def choice_gate(self) -> int:
        roll = self.rand_int(0, 5)
        return ALWAYS if roll >= 3 else roll


def vcode(text: str) -> int:
    major, minor, patch = (int(part) for part in text.split("."))
    return (major << 16) | (minor << 8) | patch


def vtext(code: int) -> str:
    return "%d.%d.%d" % (code >> 16, (code >> 8) & 0xFF, code & 0xFF)


def crc16(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFF


def keystream(salt: str, nonce: int, block_key: int, ordinal: int) -> int:
    material = salt.encode("ascii") + struct.pack("<IIH", nonce & 0xFFFFFFFF, block_key & 0xFFFFFFFF, ordinal & 0xFFFF)
    return zlib.crc32(material) & 0xFFFFFFFF


def count_bias(salt: str, nonce: int, limit: int) -> int:
    return (zlib.crc32(salt.encode("ascii") + struct.pack("<I", nonce & 0xFFFFFFFF)) & 0xFF) % limit


def block_permutation(count: int, nonce: int, multiplier: int) -> list[int]:
    """order[k] is the logical block index written at wire position k."""
    order = list(range(count))
    state = nonce & 0xFFFFFFFF
    for i in range(count - 1, 0, -1):
        state = (state * multiplier + 0x9E3779B9) & 0xFFFFFFFF
        j = state % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def rotation_amount(base: int, ordinal: int) -> int:
    return (base + (ordinal % 8)) % 16


def rotl16(word: int, amount: int) -> int:
    amount %= 16
    word &= 0xFFFF
    return ((word << amount) | (word >> (16 - amount))) & 0xFFFF if amount else word


def rotr16(word: int, amount: int) -> int:
    return rotl16(word, (16 - amount % 16) % 16)


# ---------------------------------------------------------------------------
# shard writer
# ---------------------------------------------------------------------------


def encode_shard(shard: dict[str, Any], params: dict[str, Any]) -> bytes:
    flags = int(shard["flags"])
    nonce = int(shard["nonce"])
    blocks = shard["blocks"]
    salt = params["salt"]
    logical_count = len(blocks)
    stored_count = logical_count
    if flags & FLAG_BIASED_COUNT:
        stored_count += count_bias(salt, nonce, params["bias"])
    order = block_permutation(logical_count, nonce, params["permute"]) if flags & FLAG_BLOCK_PERMUTE else list(range(logical_count))
    encoded: dict[int, bytes] = {}
    drift = 0
    for logical_index, block in enumerate(blocks):
        block_key = int(block["block_nonce"])
        if flags & FLAG_DRIFT_KEY:
            block_key = (block_key ^ drift) & 0xFFFFFFFF
        wire = _encode_block(block, flags, nonce, block_key, params, int(shard.get("companion_nonce", 0)))
        if flags & FLAG_SPLIT_TAIL:
            wire += b"\x00" * (int(block["block_nonce"]) % 7)
        encoded[logical_index] = wire
        drift = (drift + sum(int(r["size"]) for r in block["records"])) & 0xFFFFFFFF
    body = b"".join(encoded[index] for index in order)
    header = bytearray()
    header += MAGIC
    header += bytes([FORMAT_VERSION, int(shard["tier"]) & 0xFF])
    header += struct.pack("<H", flags)
    header += struct.pack(">I" if flags & FLAG_ENDIAN_ISLAND else "<I", nonce)
    header += struct.pack("<I", len(body))
    header += struct.pack("<H", stored_count & 0xFFFF)
    header += struct.pack("<H", crc16(bytes(header)))
    assert len(header) == HEADER_LEN
    return bytes(header) + body


def _encode_block(block: dict[str, Any], flags: int, nonce: int, block_key: int,
                  params: dict[str, Any], companion: int) -> bytes:
    key = int(block["key"])
    if flags & FLAG_XREF_KEY:
        key ^= companion
    records = block["records"]
    head = struct.pack("<I", key & 0xFFFFFFFF)
    head += struct.pack(">H" if flags & FLAG_ENDIAN_ISLAND else "<H", len(records))
    head += struct.pack("<I", int(block["block_nonce"]) & 0xFFFFFFFF)
    assert len(head) == BLOCK_HEADER_LEN
    span = int(params["window"])
    ring: list[tuple[int, int, int, int, int]] = [(0, 0, 0, 0, 0)] * span
    body = bytearray()
    prev_code = 0
    day1 = 0
    day2 = 0
    for ordinal, record in enumerate(records):
        code = int(record["code"])
        stored_code = (code - prev_code) & 0xFFFFFFFF if flags & FLAG_CHAIN_VERSION and ordinal else code
        prev_code = code
        size = int(record["size"])
        if flags & FLAG_MASK_BYTES:
            size ^= keystream(params["salt"], nonce, block_key, ordinal)
        day = int(record["day"])
        stored_day = (day - 2 * day1 + day2) & 0xFFFF if flags & FLAG_DELTA2_DAY else day
        day2, day1 = day1, day
        deps = record["deps"]
        word = ((int(record["status"]) & 0xFF) << 8) | (len(deps) & 0xFF)
        if flags & FLAG_ROT_STATUS:
            word = rotl16(word, rotation_amount(params["rotate"], ordinal))
        body += struct.pack("<IIHH", stored_code, size & 0xFFFFFFFF, stored_day, word)
        for dep in deps:
            entry = tuple(int(v) for v in dep)
            packed = struct.pack("<IIIBB", *entry)
            if flags & FLAG_BACKREF_DEPS:
                hit = None
                for index in range(span):
                    if ring[index] == entry:
                        hit = index
                        break
                if hit is None:
                    body += b"\x00" + packed
                else:
                    body += bytes([span - hit])
                ring.insert(0, entry)
                del ring[span:]
            else:
                body += packed
    wire = head + bytes(body)
    return wire + struct.pack("<I", zlib.crc32(wire) & 0xFFFFFFFF)


# ---------------------------------------------------------------------------
# reference shard reader (used for calibration figures and pin witnesses)
# ---------------------------------------------------------------------------


class Unreadable(Exception):
    pass


def read_header(blob: bytes) -> dict[str, int]:
    if len(blob) < HEADER_LEN or blob[:4] != MAGIC or blob[4] != FORMAT_VERSION:
        raise Unreadable("bad header")
    if crc16(blob[:18]) != struct.unpack_from("<H", blob, 18)[0]:
        raise Unreadable("header check")
    flags = struct.unpack_from("<H", blob, 6)[0]
    nonce = struct.unpack_from(">I" if flags & FLAG_ENDIAN_ISLAND else "<I", blob, 8)[0]
    body_len = struct.unpack_from("<I", blob, 12)[0]
    if HEADER_LEN + body_len != len(blob):
        raise Unreadable("body length")
    return {"tier": blob[5], "flags": flags, "nonce": nonce, "stored_count": struct.unpack_from("<H", blob, 16)[0]}


def decode_shard(blob: bytes, companion: int, params: dict[str, Any]) -> dict[str, Any]:
    head = read_header(blob)
    flags = head["flags"]
    nonce = head["nonce"]
    count = head["stored_count"]
    if flags & FLAG_BIASED_COUNT:
        count -= count_bias(params["salt"], nonce, params["bias"])
    if count < 0:
        raise Unreadable("negative count")
    span = int(params["window"])
    pos = HEADER_LEN
    wire_blocks = []
    for _ in range(count):
        start = pos
        if pos + BLOCK_HEADER_LEN > len(blob):
            raise Unreadable("block header past end")
        key = struct.unpack_from("<I", blob, pos)[0]
        nrec = struct.unpack_from(">H" if flags & FLAG_ENDIAN_ISLAND else "<H", blob, pos + 4)[0]
        bnonce = struct.unpack_from("<I", blob, pos + 6)[0]
        pos += BLOCK_HEADER_LEN
        raw = []
        for ordinal in range(nrec):
            if pos + RECORD_HEAD_LEN > len(blob):
                raise Unreadable("record past end")
            scode, ssize, sday, word = struct.unpack_from("<IIHH", blob, pos)
            pos += RECORD_HEAD_LEN
            if flags & FLAG_ROT_STATUS:
                word = rotr16(word, rotation_amount(params["rotate"], ordinal))
            ndeps = word & 0xFF
            deps = []
            for _d in range(ndeps):
                if flags & FLAG_BACKREF_DEPS:
                    if pos >= len(blob):
                        raise Unreadable("tag past end")
                    tag = blob[pos]
                    pos += 1
                    if tag == 0:
                        if pos + DEP_LEN > len(blob):
                            raise Unreadable("dep past end")
                        deps.append(("lit", struct.unpack_from("<IIIBB", blob, pos)))
                        pos += DEP_LEN
                    else:
                        deps.append(("ref", tag))
                else:
                    if pos + DEP_LEN > len(blob):
                        raise Unreadable("dep past end")
                    deps.append(("lit", struct.unpack_from("<IIIBB", blob, pos)))
                    pos += DEP_LEN
            raw.append((scode, ssize, sday, word >> 8, deps))
        if pos + TRAILER_LEN > len(blob):
            raise Unreadable("trailer past end")
        if zlib.crc32(blob[start:pos]) & 0xFFFFFFFF != struct.unpack_from("<I", blob, pos)[0]:
            raise Unreadable("block trailer")
        pos += TRAILER_LEN
        if flags & FLAG_SPLIT_TAIL:
            pos += bnonce % 7
        wire_blocks.append((key, bnonce, raw))
    if pos != len(blob):
        raise Unreadable("trailing bytes")
    order = block_permutation(count, nonce, params["permute"]) if flags & FLAG_BLOCK_PERMUTE else list(range(count))
    logical: list[Any] = [None] * count
    for wire_pos, logical_index in enumerate(order):
        logical[logical_index] = wire_blocks[wire_pos]
    blocks = []
    drift = 0
    for key, bnonce, raw in logical:
        block_key = (bnonce ^ drift) & 0xFFFFFFFF if flags & FLAG_DRIFT_KEY else bnonce
        ring: list[tuple[int, ...]] = [(0, 0, 0, 0, 0)] * span
        prev_code = 0
        day1 = 0
        day2 = 0
        records = []
        backrefs = 0
        for ordinal, (scode, ssize, sday, status, deps) in enumerate(raw):
            code = (scode + prev_code) & 0xFFFFFFFF if flags & FLAG_CHAIN_VERSION and ordinal else scode
            prev_code = code
            size = ssize ^ keystream(params["salt"], nonce, block_key, ordinal) if flags & FLAG_MASK_BYTES else ssize
            day = (sday + 2 * day1 - day2) & 0xFFFF if flags & FLAG_DELTA2_DAY else sday
            day2, day1 = day1, day
            plain = []
            for kind, value in deps:
                if kind == "ref":
                    index = span - value
                    if index < 0 or index >= span:
                        raise Unreadable("back reference outside the ring")
                    entry = ring[index]
                    backrefs += 1
                else:
                    entry = tuple(value)
                if flags & FLAG_BACKREF_DEPS:
                    ring.insert(0, entry)
                    del ring[span:]
                plain.append(entry)
            records.append({"code": code, "size": size, "day": day, "status": status, "deps": plain})
        drift = (drift + sum(r["size"] for r in records)) & 0xFFFFFFFF
        stored_key = key ^ companion if flags & FLAG_XREF_KEY else key
        blocks.append({"key": stored_key, "block_nonce": bnonce, "records": records, "backrefs": backrefs})
    return {"tier": head["tier"], "flags": flags, "nonce": nonce, "blocks": blocks}


def decode_tier(blobs: dict[str, bytes], tier: int, params: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    for name in sorted(blobs):
        head = read_header(blobs[name])
        if head["tier"] == tier:
            entries.append((name, head["nonce"]))
    entries.sort(key=lambda item: item[1])
    decoded = []
    for pos, (name, _nonce) in enumerate(entries):
        companion = entries[pos - 1][1] if pos else entries[-1][1]
        decoded.append(decode_shard(blobs[name], companion, params) | {"name": name})
    decoded.sort(key=lambda item: item["name"])
    return decoded


# ---------------------------------------------------------------------------
# calibration controls
# ---------------------------------------------------------------------------

CONTROL_IDS = ("CTRL-1", "CTRL-2", "CTRL-3", "CTRL-4", "CTRL-5", "CTRL-6")
CONTROL_KEYS = (
    "calibration_block_total",
    "calibration_key_digest",
    "calibration_size_digest",
    "calibration_dependency_digest",
    "calibration_status_digest",
    "calibration_eligible_records",
)


def controls_from_decoded(shards: list[dict[str, Any]], quarantine: int, snapshot: int) -> dict[str, int]:
    block_total = 0
    key_digest = 0
    size_digest = 0
    dep_digest = 0
    status_digest = 0
    eligible = 0
    for shard in shards:
        for position, block in enumerate(shard["blocks"]):
            block_total += 1
            key_digest += (position + 1) * block["key"]
            for ordinal, record in enumerate(block["records"]):
                size_digest += (ordinal + 1) * (record["size"] + record["code"])
                status_digest += (ordinal + 1) * (3 * record["status"] + len(record["deps"]))
                for dep_index, dep in enumerate(record["deps"]):
                    dep_digest += (dep_index + 1) * (ordinal + 1) * ((dep[0] ^ dep[1]) + 7 * dep[3] + dep[4])
                if not record["status"] & STATUS_YANKED and record["day"] <= snapshot and snapshot - record["day"] >= quarantine:
                    eligible += 1
    return {
        "calibration_block_total": block_total,
        "calibration_key_digest": key_digest % MODULUS,
        "calibration_size_digest": size_digest % MODULUS,
        "calibration_dependency_digest": dep_digest % MODULUS,
        "calibration_status_digest": status_digest % MODULUS,
        "calibration_eligible_records": eligible,
    }


def controls(blobs: dict[str, bytes], params: dict[str, Any], snapshot: int) -> dict[str, int]:
    return controls_from_decoded(decode_tier(blobs, TIER_CALIBRATION, params), int(params["quarantine"]), snapshot)


# ---------------------------------------------------------------------------
# the published package universe
# ---------------------------------------------------------------------------


def package_key(name: str) -> int:
    return (zlib.crc32(("registry:" + name).encode("ascii")) & 0x7FFFFFFF) | 0x10000000


REGISTRY_ROWS = [
    ("ansi-term", "", "MIT"),
    ("bytecodec", "", "GPL-3.0"),
    ("byte-codec", "bytecodec", "MIT"),
    ("cli-args", "", "Apache-2.0"),
    ("crc-kit", "", "BSD-3-Clause"),
    ("datefmt", "", "MIT OR GPL-3.0"),
    ("date-fmt", "datefmt", "LGPL-2.1"),
    ("event-bus", "", "MPL-2.0"),
    ("glob-match", "", "ISC"),
    ("http-lite", "", "Apache-2.0"),
    ("jsonic", "", "ISC"),
    ("json-kit", "jsonic", "MIT"),
    ("json-core", "json-kit", "AGPL-3.0"),
    ("log-sink", "", "MIT"),
    ("path-norm", "", "BSD-2-Clause"),
    ("tls-shim", "", "Apache-2.0"),
    ("url-parse", "", "MIT"),
    ("zip-flate", "", "Zlib AND GPL-3.0"),
]


def D(name: str, lo: str, hi: str, req: int = 0, gate: int = ALWAYS) -> tuple[str, str, str, int, int]:
    return (name, lo, hi, req, gate)


PUBLISHED: dict[str, list[tuple[str, int, int, int, list[tuple[str, str, str, int, int]]]]] = {
    "http-lite": [
        ("2.0.0", 210, 1900, 0, [D("url-parse", "1.0.0", "2.0.0"), D("tls-shim", "1.3.0", "2.0.0", 2, 0), D("log-sink", "1.0.0", "2.0.0", 1, 1)]),
        ("2.1.0", 160, 1990, 0, [D("url-parse", "1.2.0", "2.0.0"), D("byte-codec", "1.0.0", "2.0.0", 1), D("tls-shim", "1.4.0", "2.0.0", 2, 0), D("log-sink", "1.1.0", "2.0.0", 1, 1)]),
        ("2.2.0", 150, 2036, 0, [D("url-parse", "1.2.0", "2.0.0"), D("byte-codec", "1.0.0", "2.0.0", 1), D("tls-shim", "1.4.0", "2.0.0", 2, 0), D("zip-flate", "0.9.0", "1.0.0", 0, 1)]),
        ("3.0.0", 90, 2020, 0, [D("url-parse", "1.3.0", "2.0.0")]),
    ],
    "tls-shim": [
        ("1.3.0", 120, 1850, 0, [D("crc-kit", "1.0.0", "2.0.0", 4, 1)]),
        ("1.3.1", 95, 2033, 0, [D("crc-kit", "1.0.0", "2.0.0", 4, 1)]),
        ("1.4.0", 70, 1950, 0, [D("bytecodec", "1.1.0", "2.0.0", 1, 1)]),
        ("1.4.1", 60, 2035, 0, [D("byte-codec", "1.1.0", "2.0.0", 1, 1)]),
    ],
    "bytecodec": [
        ("1.0.0", 40, 1700, 0, [D("crc-kit", "1.0.0", "2.0.0", 4, 0)]),
        ("1.1.0", 45, 1800, 0, [D("crc-kit", "1.0.0", "2.0.0", 4, 0)]),
    ],
    "byte-codec": [
        ("1.2.0", 38, 1960, 0, [D("crc-kit", "1.1.0", "2.0.0", 4, 0), D("log-sink", "1.0.0", "2.0.0", 2, 0)]),
        ("1.3.0", 30, 2010, STATUS_YANKED, [D("crc-kit", "1.1.0", "2.0.0", 4, 0)]),
    ],
    "crc-kit": [
        ("1.0.0", 12, 1600, 0, [D("log-sink", "1.0.0", "2.0.0", 4, 2)]),
        ("1.1.0", 10, 1750, 0, [D("log-sink", "1.1.0", "2.0.0", 4, 2)]),
        ("1.2.0", 14, 2000, STATUS_DEPRECATED, [D("datefmt", "1.0.0", "2.0.0", 1, 2)]),
    ],
    "log-sink": [
        ("1.0.0", 30, 1650, 0, [D("ansi-term", "0.3.0", "1.0.0", 0, 2)]),
        ("1.1.0", 26, 1880, 0, [D("ansi-term", "0.4.0", "1.0.0", 1, 2), D("date-fmt", "1.2.0", "2.0.0", 0, 0)]),
        ("1.2.0", 34, 2015, 0, [D("event-bus", "1.0.0", "2.0.0", 1, 2)]),
    ],
    "datefmt": [
        ("1.0.0", 22, 1500, 0, []),
        ("1.1.0", 20, 1700, 0, []),
    ],
    "date-fmt": [
        ("1.2.0", 18, 1900, 0, [D("ansi-term", "0.4.0", "1.0.0", 1, 0)]),
        ("1.3.0", 25, 2025, 0, [D("glob-match", "1.0.0", "2.0.0")]),
    ],
    "ansi-term": [
        ("0.3.0", 8, 1400, 0, []),
        ("0.4.0", 9, 1800, 0, [D("path-norm", "0.5.0", "1.0.0", 0, 0)]),
        ("0.5.0", 7, 2041, 0, []),
    ],
    "path-norm": [
        ("0.5.0", 6, 1500, 0, []),
        ("0.6.0", 5, 1900, 0, [D("glob-match", "1.1.0", "2.0.0")]),
    ],
    "glob-match": [
        ("1.0.0", 16, 1550, 0, []),
        ("1.1.0", 13, 1850, 0, [D("path-norm", "0.5.0", "0.6.0", 0, 0)]),
        ("1.2.0", 15, 2000, 0, []),
    ],
    "url-parse": [
        ("1.1.0", 25, 1600, 0, []),
        ("1.2.0", 21, 1870, 0, []),
        ("1.3.0", 19, 2038, 0, []),
    ],
    "cli-args": [
        ("1.0.0", 30, 1500, 0, [D("ansi-term", "0.3.0", "1.0.0")]),
        ("1.1.0", 28, 1900, 0, [D("ansi-term", "0.4.0", "1.0.0", 1)]),
        ("1.2.0", 27, 1990, 0, [D("argv-core", "1.0.0", "2.0.0")]),
    ],
    "event-bus": [
        ("1.0.0", 55, 1700, 0, [D("json-core", "3.0.0", "4.0.0", 2, 1)]),
        ("1.1.0", 48, 1950, 0, [D("json-kit", "3.1.0", "4.0.0", 2, 1), D("log-sink", "1.0.0", "2.0.0")]),
    ],
    "jsonic": [
        ("3.0.0", 70, 1600, 0, [D("datefmt", "1.0.0", "1.2.0", 0, 1)]),
    ],
    "json-kit": [
        ("3.1.0", 64, 1800, 0, [D("date-fmt", "1.1.0", "2.0.0", 0, 1), D("bytecodec", "1.0.0", "2.0.0", 1, 2)]),
    ],
    "json-core": [
        ("3.2.0", 58, 1980, 0, [D("date-fmt", "1.2.0", "2.0.0", 1, 1), D("crc-kit", "1.0.0", "2.0.0", 4, 2)]),
        ("3.3.0", 50, 2046, 0, [D("date-fmt", "1.2.0", "2.0.0", 1, 1)]),
    ],
    "zip-flate": [
        ("0.8.0", 44, 1700, 0, [D("crc-kit", "1.1.0", "2.0.0", 4, 0)]),
        ("0.9.0", 40, 1980, 0, [D("byte-codec", "1.2.0", "2.0.0", 1, 0)]),
    ],
    "argv-core": [
        ("1.0.0", 11, 1700, 0, []),
        ("1.1.0", 12, 1900, 0, []),
    ],
}

WORKSPACES = [
    ("visible", 2040, "forbidden"),
    ("peak", 2050, "allowed"),
    ("steady", 2030, "forbidden"),
    ("burst", 2055, "allowed"),
    ("latency", 2045, "forbidden"),
]

REQUIREMENTS = [
    ("visible", "http-lite", "2.0.0", "3.0.0", 1),
    ("visible", "cli-args", "1.0.0", "2.0.0", 0),
    ("peak", "event-bus", "1.0.0", "2.0.0", 2),
    ("peak", "jsonic", "3.0.0", "4.0.0", 1),
    ("steady", "log-sink", "1.0.0", "2.0.0", 1),
    ("steady", "date-fmt", "1.2.0", "2.0.0", 0),
    ("steady", "path-norm", "0.5.0", "1.0.0", 0),
    ("burst", "http-lite", "2.0.0", "3.0.0", 3),
    ("burst", "zip-flate", "0.8.0", "1.0.0", 1),
    ("latency", "json-core", "3.0.0", "4.0.0", 2),
    ("latency", "glob-match", "1.0.0", "2.0.0", 1),
    ("latency", "ansi-term", "0.3.0", "1.0.0", 0),
]

QUARANTINE_FIXTURES = (("tls-shim", "1.3.1", "visible"), ("url-parse", "1.3.0", "burst"))

CALIBRATION_SNAPSHOT = 2100
CALIBRATION_DIFFS = (0, 1, 2, 3, 4, 6, 8, 12, 17, 25, 40, 60)
FIELD_SHARDS = 8
FIELD_DROPPED_FLAG = {2: FLAG_ENDIAN_ISLAND, 5: FLAG_SPLIT_TAIL}


def _mutation_hash(text: str) -> int:
    return zlib.crc32(("mutation:" + text).encode("ascii")) & 0xFFFFFFFF


def corpus_params(corpus_id: str) -> dict[str, Any]:
    """Withheld constants of one corpus: the shipped set, or a set differing at every position."""
    if not corpus_id:
        return dict(TRUE_PARAMS)
    h = _mutation_hash(corpus_id)
    params: dict[str, Any] = {}
    for position, name in enumerate(PARAM_ORDER):
        vocab = VOCABS[name]
        true_index = vocab.index(TRUE_PARAMS[name])
        step = 1 + (h >> (position * 4)) % (len(vocab) - 1)
        params[name] = vocab[(true_index + step) % len(vocab)]
    return params


def base_universe() -> dict[str, Any]:
    return {
        "registry": [list(row) for row in REGISTRY_ROWS],
        "published": copy.deepcopy(PUBLISHED),
        "workspaces": [list(row) for row in WORKSPACES],
        "requirements": [list(row) for row in REQUIREMENTS],
        "shards": FIELD_SHARDS,
        "exact": {},
        "scale": 1,
        "no_backref": False,
    }


def _synthetic_blocks(rng: Rng, block_count: int, record_range: tuple[int, int], snapshot: int,
                      plant: list[int] | None = None) -> list[dict[str, Any]]:
    blocks = []
    plant = list(plant or [])
    for _ in range(block_count):
        key = rng.rand_int(0x20000000, 0x6FFFFFFF)
        pool = []
        for _p in range(4):
            lo = (rng.rand_int(0, 4) << 16) | (rng.rand_int(0, 9) << 8)
            pool.append((rng.rand_int(0x20000000, 0x6FFFFFFF), lo, lo + (1 << 16), rng.rand_int(0, 15), rng.choice_gate()))
        code = (rng.rand_int(0, 3) << 16) | (rng.rand_int(0, 5) << 8)
        records = []
        for _r in range(rng.rand_int(*record_range)):
            code += rng.rand_int(1, 3) if rng.rand_int(0, 2) else (1 << 8)
            planted = bool(plant)
            if planted:
                day = snapshot - plant.pop(0)
            else:
                day = snapshot - rng.rand_int(61, 400) if rng.rand_int(0, 5) else snapshot + rng.rand_int(1, 30)
            status = 0
            roll = rng.rand_int(0, 9)
            if roll == 0 and not planted:
                status = STATUS_YANKED
            elif roll <= 1:
                status = STATUS_DEPRECATED
            deps = [pool[rng.rand_int(0, 3)] for _d in range(rng.rand_int(0, 3))]
            records.append({"code": code, "size": rng.rand_int(1200, 96000), "day": day, "status": status, "deps": deps})
        blocks.append({"key": key, "block_nonce": rng.rand_int(0x01000000, 0xFEFFFFFF), "records": records})
    return blocks


def make_corpus(seed: int, mutation: str = "", field_flags: int | None = None) -> dict[str, Any]:
    corpus_id = mutation if field_flags is None else "%s/trap-%04x" % (mutation, field_flags)
    params = corpus_params(corpus_id)
    rng = Rng(seed ^ (_mutation_hash(corpus_id) << 16 if corpus_id else 0))
    universe = base_universe()
    if mutation:
        apply_mutation(mutation, universe)
    snapshots = {row[0]: int(row[1]) for row in universe["workspaces"]}
    for name_under, text, workspace in QUARANTINE_FIXTURES:
        _version(universe, name_under, text)[2] = snapshots[workspace] - int(params["quarantine"])

    registry = []
    for name, renamed_from, licence in universe["registry"]:
        registry.append({"package": name, "key": package_key(name), "renamed_from": renamed_from, "licence": licence})

    shards: list[dict[str, Any]] = []

    def add(tier: int, name: str, flags: int, blocks: list[dict[str, Any]]) -> None:
        nonce = rng.rand_int(0x10000000, 0xEFFFFFFF)
        while any(s["nonce"] == nonce for s in shards):
            nonce = rng.rand_int(0x10000000, 0xEFFFFFFF)
        shards.append({"tier": tier, "name": name, "flags": flags, "nonce": nonce, "blocks": blocks})

    for name in ("sample_a", "sample_b"):
        add(TIER_SAMPLE, name, 0, _synthetic_blocks(rng, 2, (3, 3), CALIBRATION_SNAPSHOT))

    plant = list(CALIBRATION_DIFFS)
    for index, name in enumerate(("calib_a", "calib_b", "calib_c", "calib_d", "calib_e")):
        share = plant[:3]
        plant = plant[3:]
        add(TIER_CALIBRATION, name, ALL_FLAGS, _synthetic_blocks(rng, 3 + index % 2, (5, 8), CALIBRATION_SNAPSHOT, share))

    field_blocks = []
    for name_under, versions in universe["published"].items():
        records = []
        seen_entries: set[tuple[int, ...]] = set()
        for text, kb, day, status, deps in versions:
            packed = []
            for dep_name, lo, hi, req, gate in deps:
                entry = (package_key(dep_name), vcode(lo), vcode(hi), req, gate)
                if universe["no_backref"]:
                    while entry in seen_entries:
                        entry = (entry[0], entry[1], entry[2] + 1, entry[3], entry[4])
                    seen_entries.add(entry)
                packed.append(entry)
            noise = rng.rand_int(0, 299)
            size = universe["exact"].get((name_under, text), kb * 1000 * int(universe["scale"]) + noise)
            records.append({"code": vcode(text), "size": size, "day": day, "status": status, "deps": packed})
        records.sort(key=lambda r: r["code"])
        field_blocks.append({"key": package_key(name_under), "block_nonce": rng.rand_int(0x01000000, 0xFEFFFFFF),
                             "records": records, "published_as": name_under})
    order = list(range(len(field_blocks)))
    for i in range(len(order) - 1, 0, -1):
        j = rng.rand_int(0, i)
        order[i], order[j] = order[j], order[i]
    shard_count = int(universe["shards"])
    buckets: list[list[dict[str, Any]]] = [[] for _ in range(shard_count)]
    for position, index in enumerate(order):
        buckets[position % shard_count].append(field_blocks[index])
    for index in range(shard_count):
        if field_flags is None:
            flags = ALL_FLAGS & ~FIELD_DROPPED_FLAG.get(index, 0)
        else:
            flags = field_flags
        add(TIER_FIELD, "field_%02d" % (index + 1), flags, buckets[index])

    files: dict[str, bytes] = {}
    by_tier: dict[int, list[dict[str, Any]]] = {}
    for shard in shards:
        by_tier.setdefault(shard["tier"], []).append(shard)
    for group in by_tier.values():
        ordered = sorted(group, key=lambda s: s["nonce"])
        for pos, shard in enumerate(ordered):
            shard["companion_nonce"] = ordered[pos - 1]["nonce"] if pos else ordered[-1]["nonce"]
    for shard in shards:
        files[shard["name"] + ".pidx"] = encode_shard(shard, params)

    return {
        "corpus_id": corpus_id,
        "params": params,
        "registry": registry,
        "workspaces": universe["workspaces"],
        "requirements": universe["requirements"],
        "shards": shards,
        "files": files,
        "calibration_snapshot": CALIBRATION_SNAPSHOT,
    }



# ---------------------------------------------------------------------------
# expectation model: every graded fact from the plaintext of one corpus
# ---------------------------------------------------------------------------


def licence_family(expression: str) -> str:
    text = expression.strip()
    if " OR " in text:
        parts = [licence_family(part) for part in text.split(" OR ")]
        return "permissive" if "permissive" in parts else "copyleft"
    if " AND " in text:
        parts = [licence_family(part) for part in text.split(" AND ")]
        return "copyleft" if "copyleft" in parts else "permissive"
    if text in PERMISSIVE:
        return "permissive"
    if text in COPYLEFT:
        return "copyleft"
    raise ValueError("unknown licence %r" % text)


class Registry:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.by_name = {row["package"]: row for row in rows}
        self.by_key = {row["key"]: row for row in rows}
        self.successor = {row["renamed_from"]: row["package"] for row in rows if row["renamed_from"]}

    def tip(self, name: str) -> str:
        seen = set()
        while name in self.successor and name not in seen:
            seen.add(name)
            name = self.successor[name]
        return name

    def root(self, name: str) -> str:
        seen = set()
        while self.by_name[name]["renamed_from"] and name not in seen:
            seen.add(name)
            name = self.by_name[name]["renamed_from"]
        return name

    def canonical_of_key(self, key: int) -> str | None:
        row = self.by_key.get(key)
        return None if row is None else self.tip(row["package"])

    def family(self, canonical: str, reading: str = "root") -> str:
        name = self.root(canonical) if reading == "root" else canonical
        return licence_family(self.by_name[name]["licence"])


def _ring_backrefs(records: list[dict[str, Any]], span: int) -> int:
    ring: list[Any] = [None] * span
    hits = 0
    for record in records:
        for dep in record["deps"]:
            entry = tuple(dep)
            if entry in ring:
                hits += 1
            ring.insert(0, entry)
            del ring[span:]
    return hits


def field_inventory(built: dict[str, Any]) -> dict[str, Any]:
    registry = Registry(built["registry"])
    span = int(built["params"]["window"])
    field = sorted((s for s in built["shards"] if s["tier"] == TIER_FIELD), key=lambda s: s["name"])
    quality = {
        "total_shards": len(field),
        "shards_with_full_flag_set": sum(1 for s in field if s["flags"] == ALL_FLAGS),
        "records_yanked": 0,
        "records_deprecated": 0,
        "records_unregistered_package": 0,
        "dependency_entries_back_referenced": 0,
        "dependency_entries_unregistered_target": 0,
        "excluded_bytes_by_cause": {"unregistered_package": 0, "yanked": 0},
    }
    totals = {"shards_decoded": len(field), "blocks_decoded": 0, "records_decoded": 0,
              "dependency_entries_decoded": 0, "decoded_bytes": 0}
    candidates: dict[str, list[dict[str, Any]]] = {}
    for shard in field:
        for block in shard["blocks"]:
            totals["blocks_decoded"] += 1
            if shard["flags"] & FLAG_BACKREF_DEPS:
                quality["dependency_entries_back_referenced"] += _ring_backrefs(block["records"], span)
            canonical = registry.canonical_of_key(block["key"])
            for record in block["records"]:
                totals["records_decoded"] += 1
                totals["dependency_entries_decoded"] += len(record["deps"])
                totals["decoded_bytes"] += record["size"]
                if record["status"] & STATUS_DEPRECATED:
                    quality["records_deprecated"] += 1
                for dep in record["deps"]:
                    if registry.canonical_of_key(dep[0]) is None:
                        quality["dependency_entries_unregistered_target"] += 1
                if canonical is None:
                    quality["records_unregistered_package"] += 1
                    quality["excluded_bytes_by_cause"]["unregistered_package"] += record["size"]
                    continue
                if record["status"] & STATUS_YANKED:
                    quality["records_yanked"] += 1
                    quality["excluded_bytes_by_cause"]["yanked"] += record["size"]
                    continue
                edges = []
                for dep in record["deps"]:
                    edges.append((registry.canonical_of_key(dep[0]), dep[1], dep[2], dep[3], dep[4]))
                candidates.setdefault(canonical, []).append(
                    {"code": record["code"], "size": record["size"], "day": record["day"], "edges": edges}
                )
    for versions in candidates.values():
        versions.sort(key=lambda r: r["code"])
    return {"registry": registry, "quality": quality, "totals": totals, "candidates": candidates}


def _active(edge: tuple[Any, ...], features: int) -> bool:
    return edge[4] == ALWAYS or bool(features >> edge[4] & 1)


def least_features(assign: dict[str, dict[str, Any]], roots: list[tuple[Any, ...]]) -> dict[str, int]:
    features = {name: 0 for name in assign}
    for root in roots:
        if root[0] in features:
            features[root[0]] |= root[3]
    changed = True
    while changed:
        changed = False
        for name in sorted(assign):
            for edge in assign[name]["edges"]:
                target = edge[0]
                if target in features and _active(edge, features[name]):
                    merged = features[target] | edge[3]
                    if merged != features[target]:
                        features[target] = merged
                        changed = True
    return features


def settlement_passes(assign: dict[str, dict[str, Any]], roots: list[tuple[Any, ...]]) -> int:
    state = {name: 0 for name in assign}
    for root in roots:
        if root[0] in state:
            state[root[0]] |= root[3]
    passes = 0
    while True:
        passes += 1
        nxt = dict(state)
        for name in assign:
            for edge in assign[name]["edges"]:
                if edge[0] in nxt and _active(edge, state[name]):
                    nxt[edge[0]] |= edge[3]
        if nxt == state:
            return passes
        state = nxt


class SearchBudget(Exception):
    pass


def resolve_workspace(inventory: dict[str, Any], roots: list[tuple[Any, ...]], snapshot: int,
                      quarantine: int, copyleft: str, reading: str = "root", strict: bool = False) -> dict[str, Any]:
    registry: Registry = inventory["registry"]
    eligible: dict[str, list[dict[str, Any]]] = {}
    floor = quarantine + 1 if strict else quarantine
    for name, versions in inventory["candidates"].items():
        eligible[name] = [v for v in versions if v["day"] <= snapshot and snapshot - v["day"] >= floor]
    allowed = {name: copyleft == "allowed" or registry.family(name, reading) == "permissive" for name in eligible}
    best: dict[str, Any] = {"key": None, "assign": None}
    states = [0]

    def violated(assign: dict[str, dict[str, Any]]) -> tuple[bool, set[str]]:
        features = least_features(assign, roots)
        required: set[str] = set()
        for root in roots:
            if root[0] is None:
                return True, required
            required.add(root[0])
            chosen = assign.get(root[0])
            if chosen is not None and not root[1] <= chosen["code"] < root[2]:
                return True, required
        for name, record in assign.items():
            for edge in record["edges"]:
                if not _active(edge, features[name]):
                    continue
                if edge[0] is None:
                    return True, required
                required.add(edge[0])
                chosen = assign.get(edge[0])
                if chosen is not None and not edge[1] <= chosen["code"] < edge[2]:
                    return True, required
        return False, required

    def plan_key(assign: dict[str, dict[str, Any]]) -> tuple[int, int, str]:
        footprint = sum(r["size"] for r in assign.values())
        code_sum = sum(r["code"] for r in assign.values())
        text = ",".join("%s@%08x" % (name, assign[name]["code"]) for name in sorted(assign))
        return (footprint, -code_sum, text)

    def walk(assign: dict[str, dict[str, Any]], cost: int) -> None:
        states[0] += 1
        if states[0] > SEARCH_STATE_CAP:
            raise SearchBudget("search state cap reached")
        if best["key"] is not None and cost > best["key"][0]:
            return
        bad, required = violated(assign)
        if bad:
            return
        open_names = sorted(required - set(assign))
        if not open_names:
            key = plan_key(assign)
            if best["key"] is None or key < best["key"]:
                best["key"] = key
                best["assign"] = dict(assign)
            return
        name = open_names[0]
        if not allowed.get(name, False):
            return
        for record in eligible.get(name, []):
            assign[name] = record
            walk(assign, cost + record["size"])
            del assign[name]

    walk({}, 0)
    assign = best["assign"]
    if assign is None:
        return {"feasible": False, "states": states[0]}
    features = least_features(assign, roots)
    return {
        "feasible": True,
        "assign": assign,
        "features": features,
        "footprint": best["key"][0],
        "passes": settlement_passes(assign, roots),
        "states": states[0],
        "eligible": eligible,
    }


def workspace_roots(built: dict[str, Any], registry: Registry, workspace: str) -> list[tuple[Any, ...]]:
    roots = []
    for ws, package, lo, hi, features in built["requirements"]:
        if ws != workspace:
            continue
        canonical = registry.tip(package) if package in registry.by_name else None
        roots.append((canonical, vcode(lo), vcode(hi), int(features), ALWAYS))
    return roots


def expected_facts(built: dict[str, Any]) -> dict[str, Any]:
    inventory = field_inventory(built)
    registry: Registry = inventory["registry"]
    params = built["params"]
    quarantine = int(params["quarantine"])
    scenarios: dict[str, dict[str, Any]] = {}
    plans: dict[str, dict[str, Any]] = {}
    divergence = []
    bottleneck = []
    locked_pairs: dict[tuple[str, int], int] = {}
    for workspace, snapshot, copyleft in built["workspaces"]:
        roots = workspace_roots(built, registry, workspace)
        plan = resolve_workspace(inventory, roots, int(snapshot), quarantine, copyleft)
        if not plan["feasible"]:
            raise AssertionError("workspace %s admits no lock plan in corpus %r" % (workspace, built["corpus_id"]))
        plans[workspace] = plan
        conventional = resolve_workspace(inventory, roots, int(snapshot), quarantine, copyleft, reading="tip")
        if not conventional["feasible"] or conventional["assign"] != plan["assign"]:
            divergence.append(workspace)
        assign = plan["assign"]
        quarantined = 0
        for versions in inventory["candidates"].values():
            for v in versions:
                if v["day"] <= int(snapshot) and int(snapshot) - v["day"] < quarantine:
                    quarantined += 1
        packages = []
        permissive = []
        copyleft_names = []
        held_back = []
        for name in sorted(assign):
            record = assign[name]
            family = registry.family(name)
            packages.append({
                "package": name,
                "version": vtext(record["code"]),
                "features": plan["features"][name],
                "licence_family": family,
                "bytes": record["size"],
            })
            (permissive if family == "permissive" else copyleft_names).append(name)
            newest = max(v["code"] for v in plan["eligible"][name])
            if record["code"] < newest:
                held_back.append({"package": name, "locked": vtext(record["code"]), "newest_eligible": vtext(newest)})
            locked_pairs[(name, record["code"])] = record["size"]
        scenarios[workspace] = {
            "workspace": workspace,
            "snapshot_day": int(snapshot),
            "copyleft": copyleft,
            "footprint_bytes": plan["footprint"],
            "package_count": len(packages),
            "quarantined_records": quarantined,
            "packages": packages,
        }
        bottleneck.append({
            "workspace": workspace,
            "held_back": held_back,
            "permissive_packages": permissive,
            "copyleft_packages": copyleft_names,
        })
    bottleneck.sort(key=lambda entry: entry["workspace"])
    totals = inventory["totals"]
    quality = inventory["quality"]
    excluded = sum(quality["excluded_bytes_by_cause"].values())
    locked_bytes = sum(locked_pairs.values())
    perf = dict(totals)
    perf.update({
        "excluded_bytes": excluded,
        "locked_bytes": locked_bytes,
        "byte_residual": totals["decoded_bytes"] - excluded - locked_bytes,
        "workspaces_resolved": len(scenarios),
        "footprint_by_workspace": {ws: scenarios[ws]["footprint_bytes"] for ws in sorted(scenarios)},
        "recovered_parameters": {
            "salt": str(params["salt"]),
            "window_span": int(params["window"]),
            "bias_limit": int(params["bias"]),
            "rotation_base": int(params["rotate"]),
            "permutation_multiplier": "0x%08x" % int(params["permute"]),
            "quarantine_days": quarantine,
        },
    })
    rivals = falsifier_table(built)
    unwitnessed = [row for row in rivals if row["falsifier"] is None]
    if unwitnessed:
        first = unwitnessed[0]
        raise AssertionError("rival %s=%r has no separating witness in corpus %r"
                             % (first["parameter"], first["value"], built["corpus_id"]))
    falsifier_totals: dict[str, int] = {}
    for row in rivals:
        falsifier_totals[row["falsifier"]] = falsifier_totals.get(row["falsifier"], 0) + 1
    return {
        "scenarios": scenarios,
        "perf_report": perf,
        "bottleneck_analysis": {"workspaces": bottleneck},
        "data_quality": quality,
        "plans": plans,
        "passes": {ws: plans[ws]["passes"] for ws in plans},
        "states": {ws: plans[ws]["states"] for ws in plans},
        "divergence": divergence,
        "rivals": rivals,
        "falsifier_totals": falsifier_totals,
        "controls": controls(built["files"], params, int(built["calibration_snapshot"])),
    }


# ---------------------------------------------------------------------------
# held out mutation families
# ---------------------------------------------------------------------------

MUTATIONS = (
    "tie_footprint",
    "temporal_edge",
    "invert_chain",
    "flip_licence",
    "empty_copyleft",
    "feature_cycle",
    "add_entity",
    "yank_wave",
    "scale_bytes",
    "unregistered_burst",
    "allow_copyleft",
    "narrow_roots",
    "wide_catalogue",
    "no_backref",
    "extend_chain",
    "early_snapshot",
)


def _licence(universe: dict[str, Any], name: str, licence: str) -> None:
    for row in universe["registry"]:
        if row[0] == name:
            row[2] = licence
            return
    raise KeyError(name)


def _version(universe: dict[str, Any], name_under: str, text: str) -> list[Any]:
    for index, entry in enumerate(universe["published"][name_under]):
        if entry[0] == text:
            entry = list(entry)
            universe["published"][name_under][index] = entry
            return entry
    raise KeyError((name_under, text))


def apply_mutation(name: str, universe: dict[str, Any]) -> None:
    if name not in MUTATIONS:
        raise KeyError(name)
    pub = universe["published"]
    if name == "tie_footprint":
        pub["log-sink"].append(("1.1.1", 26, 1890, 0, list(pub["log-sink"][1][4])))
        universe["exact"][("log-sink", "1.1.0")] = 26140
        universe["exact"][("log-sink", "1.1.1")] = 26140
        pub["glob-match"] = [
            ("1.1.0", 20, 1850, 0, []),
            ("1.2.0", 18, 1860, 0, [D("ansi-term", "0.5.0", "0.6.0")]),
        ]
        pub["ansi-term"] = [
            ("0.5.0", 12, 1840, 0, []),
            ("0.6.0", 10, 1845, 0, []),
        ]
        universe["exact"][("glob-match", "1.1.0")] = 20000
        universe["exact"][("glob-match", "1.2.0")] = 18000
        universe["exact"][("ansi-term", "0.5.0")] = 12000
        universe["exact"][("ansi-term", "0.6.0")] = 10000
    elif name == "temporal_edge":
        for row in universe["workspaces"]:
            if row[0] == "latency":
                row[1] = 2048
    elif name == "invert_chain":
        _licence(universe, "bytecodec", "MIT")
        _licence(universe, "byte-codec", "GPL-3.0")
    elif name == "flip_licence":
        _licence(universe, "event-bus", "MPL-2.0 OR Apache-2.0")
        _licence(universe, "zip-flate", "Zlib")
        _licence(universe, "datefmt", "Unlicense AND MIT")
    elif name == "empty_copyleft":
        _licence(universe, "bytecodec", "MIT")
        _licence(universe, "event-bus", "BSD-3-Clause")
        _licence(universe, "zip-flate", "ISC")
    elif name == "feature_cycle":
        entry = _version(universe, "path-norm", "0.5.0")
        entry[4] = [D("glob-match", "1.0.0", "2.0.0", 1, 0)]
        for row in universe["requirements"]:
            if row[0] == "steady" and row[1] == "path-norm":
                row[4] = 1
    elif name == "add_entity":
        universe["registry"].append(["mime-db", "", "MIT"])
        pub["mime-db"] = [
            ("2.0.0", 33, 1700, 0, []),
            ("2.1.0", 29, 1950, 0, [D("path-norm", "0.5.0", "1.0.0")]),
        ]
        entry = _version(universe, "url-parse", "1.2.0")
        entry[4] = [D("mime-db", "2.0.0", "3.0.0")]
        entry = _version(universe, "url-parse", "1.3.0")
        entry[4] = [D("mime-db", "2.1.0", "3.0.0")]
    elif name == "yank_wave":
        _version(universe, "http-lite", "2.2.0")[3] = STATUS_YANKED
        _version(universe, "tls-shim", "1.4.1")[3] = STATUS_YANKED
        _version(universe, "glob-match", "1.1.0")[3] = STATUS_YANKED
    elif name == "scale_bytes":
        universe["scale"] = 10
        universe["shards"] = 16
    elif name == "unregistered_burst":
        pub["fs-probe"] = [("0.1.0", 14, 1600, 0, []), ("0.2.0", 12, 1900, 0, [])]
        pub["net-shim"] = [("4.0.0", 64, 1700, 0, [D("fs-probe", "0.1.0", "1.0.0")])]
        entry = _version(universe, "url-parse", "1.1.0")
        entry[4] = [D("net-shim", "4.0.0", "5.0.0")]
        entry = _version(universe, "glob-match", "1.0.0")
        entry[4] = [D("fs-probe", "0.1.0", "1.0.0")]
    elif name == "allow_copyleft":
        for row in universe["workspaces"]:
            row[2] = "allowed"
    elif name == "narrow_roots":
        for row in universe["requirements"]:
            if row[0] == "latency" and row[1] == "json-core":
                row[2] = "3.2.0"
            if row[0] == "latency" and row[1] == "glob-match":
                row[2] = "1.2.0"
            if row[0] == "visible" and row[1] == "cli-args":
                row[2] = "1.1.0"
    elif name == "wide_catalogue":
        pub["log-sink"].insert(2, ("1.1.2", 24, 1960, 0, [D("ansi-term", "0.4.0", "1.0.0", 1, 2), D("date-fmt", "1.3.0", "2.0.0", 0, 0)]))
        pub["crc-kit"].insert(2, ("1.1.5", 11, 1990, 0, [D("log-sink", "1.1.2", "2.0.0", 4, 2)]))
        pub["url-parse"].insert(2, ("1.2.4", 20, 1995, 0, [D("ansi-term", "0.3.0", "0.4.0")]))
        pub["path-norm"].insert(1, ("0.5.9", 4, 1990, 0, [D("url-parse", "1.1.0", "2.0.0")]))
    elif name == "no_backref":
        universe["no_backref"] = True
    elif name == "extend_chain":
        universe["registry"].append(["url-kit", "url-parse", "BSD-2-Clause"])
        pub["url-kit"] = [
            ("1.4.0", 17, 1990, 0, []),
            ("1.5.0", 16, 2010, 0, [D("ansi-term", "0.4.0", "1.0.0", 1)]),
        ]
    elif name == "early_snapshot":
        for row in universe["workspaces"]:
            row[1] = int(row[1]) - 15
    else:
        raise ValueError("unknown mutation %s" % name)


# ---------------------------------------------------------------------------
# pin witnesses and generation post conditions
# ---------------------------------------------------------------------------


def falsifier_table(built: dict[str, Any]) -> list[dict[str, Any]]:
    """Every rival value, weighed with the other constants at their true values."""
    truth = built["params"]
    snapshot = built["calibration_snapshot"]
    published = controls(built["files"], truth, snapshot)
    rows = []
    for name in PARAM_ORDER:
        for value in VOCABS[name]:
            if value == truth[name]:
                continue
            probe = dict(truth)
            probe[name] = value
            try:
                figures = controls(built["files"], probe, snapshot)
            except Unreadable:
                rows.append({"parameter": name, "value": value, "falsifier": "UNREADABLE"})
                continue
            label = None
            for cid, key in zip(CONTROL_IDS, CONTROL_KEYS):
                if figures[key] != published[key]:
                    label = cid
                    break
            rows.append({"parameter": name, "value": value, "falsifier": label})
    return rows


def _plain_blocks(shard: dict[str, Any]) -> list[tuple[Any, ...]]:
    out = []
    for block in shard["blocks"]:
        records = tuple((r["code"], r["size"], r["day"], r["status"], tuple(tuple(d) for d in r["deps"])) for r in block["records"])
        out.append((block["key"], block["block_nonce"], records))
    return out


def assert_postconditions(built: dict[str, Any], shipped: bool) -> dict[str, Any]:
    """Raise on the first violated corpus property, naming the property and its repair."""
    for shard in built["shards"]:
        if shard["tier"] == TIER_SAMPLE and shard["flags"]:
            raise AssertionError("sample tier carries a trap flag; repair: clear the flag word of every sample shard")
    for tier in (TIER_SAMPLE, TIER_CALIBRATION, TIER_FIELD):
        decoded = {d["name"]: d for d in decode_tier(built["files"], tier, built["params"])}
        for shard in built["shards"]:
            if shard["tier"] != tier:
                continue
            got = decoded[shard["name"] + ".pidx"]
            want = _plain_blocks(shard)
            have = []
            for block in got["blocks"]:
                records = tuple((r["code"], r["size"], r["day"], r["status"], tuple(tuple(d) for d in r["deps"])) for r in block["records"])
                have.append((block["key"], block["block_nonce"], records))
            if have != want:
                raise AssertionError("shard %s does not read back to its plaintext; repair: align writer and reader" % shard["name"])
    if shipped:
        field = [s for s in built["shards"] if s["tier"] == TIER_FIELD]
        for flag_name, bit in FLAG_NAMES:
            share = sum(1 for s in field if s["flags"] & bit) / len(field)
            if share < 0.85:
                raise AssertionError("flag %s present in %.3f of field shards; repair: inject it into more field shards" % (flag_name, share))
        if not any(r["status"] & STATUS_DEPRECATED for s in field for b in s["blocks"] for r in b["records"]):
            raise AssertionError("the deprecated marker rule is exercised by no record; repair: mark one field record deprecated")
        if not any(" OR " in row["licence"] for row in built["registry"]):
            raise AssertionError("the licence alternative rule is exercised by no registry row; repair: give one root an OR expression")
    for name, vocab in VOCABS.items():
        if len(vocab) < 8:
            raise AssertionError("candidate list for %s has %d values; repair: widen it to eight" % (name, len(vocab)))
    missing = [row for row in falsifier_table(built) if row["falsifier"] is None]
    if missing:
        first = missing[0]
        raise AssertionError("rival %s=%r has no separating witness; repair: plant evidence for it" % (first["parameter"], first["value"]))
    facts = expected_facts(built)
    inventory = field_inventory(built)
    moved = []
    for workspace, snapshot, copyleft in built["workspaces"]:
        roots = workspace_roots(built, inventory["registry"], workspace)
        strict = resolve_workspace(inventory, roots, int(snapshot), int(built["params"]["quarantine"]), copyleft, strict=True)
        if not strict["feasible"] or strict["assign"] != facts["plans"][workspace]["assign"]:
            moved.append(workspace)
    if not moved:
        raise AssertionError("the inclusive quarantine boundary moves no lock plan; repair: re-place a boundary fixture version")
    facts["boundary_workspaces"] = moved
    return facts


# ---------------------------------------------------------------------------
# agent visible documents
# ---------------------------------------------------------------------------


def _doc(text: str) -> str:
    return text.lstrip("\n")


STATIC_DOCS: dict[str, str] = {
    "index-format.md": _doc("""
# Registry index shard format

An index shard is one binary file. Every integer is unsigned and little endian unless a transform
below says otherwise. A version travels as a version code: the major number times 65536, plus the
minor number times 256, plus the patch number. CRC-32 means the standard zlib CRC-32.

## Shard header, 20 bytes

| offset | size | field |
| --- | --- | --- |
| 0 | 4 | magic `PIDX` |
| 4 | 1 | format version, always 2 |
| 5 | 1 | tier marker: 0 rehearsal, 1 calibration, 2 field |
| 6 | 2 | flag word |
| 8 | 4 | shard nonce |
| 12 | 4 | block area length: the number of bytes after the header |
| 16 | 2 | stored block count |
| 18 | 2 | header check: the low 16 bits of the CRC-32 of bytes 0 to 17 |

## Block

A block carries the versions that one registry name published. It is a 10 byte block header, the
version records of the block, and a 4 byte block trailer.

| offset | size | field |
| --- | --- | --- |
| 0 | 4 | package key |
| 4 | 2 | record count |
| 6 | 4 | block nonce |

The block trailer is the CRC-32 of every byte from the start of the block header to the end of the
last record of the block, exactly as those bytes sit in the file. Records inside a block appear in
ascending version code, and the ordinal of a record is its zero based position inside its block.

## Version record

| offset | size | field |
| --- | --- | --- |
| 0 | 4 | version code |
| 4 | 4 | artifact bytes |
| 8 | 2 | publish day |
| 10 | 2 | status word: the status byte in the high byte, the dependency entry count in the low byte |

The dependency entries of the record follow its status word. Status bit 0 marks a yanked version and
status bit 1 marks a deprecated version.

## Dependency entry, 14 bytes

| offset | size | field |
| --- | --- | --- |
| 0 | 4 | target package key |
| 4 | 4 | lowest version code, inclusive |
| 8 | 4 | version code bound, exclusive |
| 12 | 1 | requested feature mask |
| 13 | 1 | gate: 255 means the entry always applies; any other value names the feature bit of the declaring package that switches the entry on |

## Optional transforms

Each set bit of the flag word switches on one transform. Five transforms use withheld registry
constants: the salt word, the window span, the bias limit, the rotation base and the shuffle
multiplier. Blocks are numbered from zero in logical order, which is the order in which the shard
writer produced them.

| bit | name | effect on the bytes |
| --- | --- | --- |
| 0x0001 | MASK_BYTES | the artifact bytes field holds the true value combined by exclusive or with a keystream word: the CRC-32 of the salt word in ASCII followed by the shard nonce (4 bytes), the block key (4 bytes) and the record ordinal (2 bytes), all little endian. The block key is the block nonce unless DRIFT_KEY is set |
| 0x0002 | CHAIN_VERSION | every record after the first in a block holds its version code minus the version code of the record before it, modulo 2^32 |
| 0x0004 | DELTA2_DAY | the publish day field of the record at ordinal k holds day(k) minus twice day(k-1) plus day(k-2), modulo 65536, where a day before the first record of the block counts as zero |
| 0x0008 | DRIFT_KEY | the block key is the block nonce combined by exclusive or with the sum, modulo 2^32, of the true artifact bytes of every record of every logically earlier block of the same shard |
| 0x0010 | BLOCK_PERMUTE | blocks sit in the file in a shuffled order. Start from the list 0 to count-1 and a state equal to the shard nonce; for i from count-1 down to 1, set the state to (state times multiplier plus 0x9E3779B9) modulo 2^32, let j be the state modulo (i+1) and swap list positions i and j. Position k of the final list names the logical block written k-th in the file |
| 0x0020 | BACKREF_DEPS | every dependency entry is preceded by a tag byte. Tag 0 means the 14 entry bytes follow. A tag t above 0 means no entry bytes follow and the entry equals slot span-t of the ring. The ring is a list of span entries, newest first, that begins every block filled with all zero entries; each entry of the block, once known, is placed at the front of the ring and the last slot is dropped. The writer uses a tag above 0 whenever the entry already sits in the ring |
| 0x0040 | ENDIAN_ISLAND | the shard nonce and every block record count are big endian |
| 0x0080 | BIASED_COUNT | the stored block count is the true count plus a bias: the low byte of the CRC-32 of the salt word in ASCII followed by the shard nonce (4 bytes, little endian), modulo the bias limit |
| 0x0100 | ROT_STATUS | the status word of the record at ordinal k is rotated left within 16 bits by (rotation base plus (k modulo 8)) modulo 16 bits, and the block trailer covers the rotated word |
| 0x0200 | XREF_KEY | the package key of every block is combined by exclusive or with the shard nonce of the companion shard, which is the shard of the same tier whose nonce is the next smaller one; the shard with the smallest nonce takes the shard with the largest nonce as its companion |
| 0x0400 | SPLIT_TAIL | every block trailer is followed by (block nonce modulo 7) zero bytes that no trailer covers |

A rehearsal shard carries a flag word of zero.
"""),
    "identity-policy.md": _doc("""
# Identity policy

The package registry lists every registered name with its package key, written as eight lowercase
hexadecimal digits, and the licence expression recorded against that name. A name whose row gives a
renamed_from value continues the package of that earlier name, so the rows form rename chains, and
every name of one chain denotes one package.

The versions of a package are the version records of every field block whose package key belongs to
any name of its chain. A dependency entry or a workspace requirement that names any member of a chain
refers to the whole package. A package is reported under the name of its chain that no row renames
from.

A package key that no registry row carries is unregistered. A block with an unregistered key gives
its records to no package, and a dependency entry whose target key is unregistered refers to no
package.
"""),
    "licence-policy.md": _doc("""
# Licence policy

Every licence identifier belongs to exactly one family.

Permissive: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, Zlib, Unlicense.

Copyleft: GPL-2.0, GPL-3.0, LGPL-2.1, LGPL-3.0, AGPL-3.0, MPL-2.0, EPL-2.0.

A licence expression is one identifier, or identifiers joined by OR, or identifiers joined by AND,
never a mix of the two. An OR expression is permissive when at least one of its identifiers is
permissive. An AND expression is copyleft when at least one of its identifiers is copyleft.

The licence that governs a package is the one recorded against the earliest name of its rename
chain, the name whose row gives no renamed_from value. A licence recorded against any later name of
the chain is kept for history and governs nothing, because a rename never relicenses the versions a
package has already published.

A workspace whose copyleft setting reads forbidden may lock no package whose governing licence is
copyleft. A workspace whose setting reads allowed may lock packages of either family.
"""),
    "resolution-policy.md": _doc("""
# Resolution policy

The workspace manifest names every benchmark workspace with its snapshot day and its copyleft
setting. The requirements table lists what each workspace asks for directly: a package name, a
lowest version (inclusive), a version bound (exclusive) and a requested feature mask. Versions are
written major.minor.patch. A version lies inside a range when its version code is at least the
lowest version code and below the bound.

## Eligible versions

A version of a package is eligible for a workspace when it is not yanked, its publish day is on or
before the snapshot day of the workspace, and its publish day lies at least the quarantine days
before that snapshot day. A version published exactly the quarantine days before the snapshot day
is eligible. The quarantine days is one registry constant shared by every workspace. The deprecated
marker has no bearing on eligibility.

A version record is quarantined for a workspace when it belongs to a registered package, is not
yanked, is published on or before the snapshot day, and is published fewer than the quarantine days
before it.

## Valid lock plans

A lock plan for a workspace locks exactly one eligible version of each package in a set of packages.
A lock plan is valid when every one of these conditions holds together:

- every package the workspace requires is locked, at a version inside the requirement's range;
- every active dependency entry of every locked version names a registered target, that target is
  locked, and its locked version lies inside the entry's range;
- every locked package is required by the workspace or is the target of an active dependency entry
  of a locked version;
- the copyleft setting of the workspace holds for every locked package.

Whether a dependency entry is active is settled by the feature policy.
"""),
    "feature-policy.md": _doc("""
# Feature policy

Every package version exposes eight feature bits, numbered 0 to 7. A dependency entry asks for
features of its target through its requested feature mask, and a workspace requirement asks for
features of its package in the same way.

A dependency entry of a locked version is active when its gate is 255, or when the feature bit its
gate names is enabled on the package that declares the entry. An inactive entry asks for nothing
and constrains nothing.

The enabled features of a lock plan give every locked package one mask. They form the smallest
assignment in which the mask of every locked package contains what the workspace asks of that
package directly and what every active entry of every locked version asks of it. Each set of
locked versions has exactly one such smallest assignment.

The settlement passes of a lock plan are counted this way. The state before the first pass gives
every locked package only what the workspace asks of it directly. A pass takes the state left by the
previous pass, collects the requests of every entry that is active in that state, and adds all of
them to that state at once. Passes continue until a pass adds nothing, and that last pass is
counted.
"""),
    "footprint-policy.md": _doc("""
# Footprint policy

The footprint of a lock plan is the sum of the artifact bytes of its locked versions. A workspace
receives the valid lock plan with the smallest footprint. When several valid plans share the smallest
footprint, the workspace receives the one whose locked version codes have the largest sum. When
several of those also share that sum, it receives the one whose plan text sorts first, where the plan
text lists every locked package in ascending reported name as the name, an at sign and the version
code in eight lowercase hexadecimal digits, joined by commas.

Every workspace of a population drawn from this policy admits at least one valid lock plan.

A locked package is held back in a workspace when its locked version code is below the largest
version code among its versions eligible for that workspace.

## Byte conservation

The decoded bytes of the field population total the artifact bytes of every version record of every
field shard. The excluded bytes total the artifact bytes of every record of an unregistered package,
whatever its status, and of every yanked record of a registered package. The locked bytes total the
artifact bytes of every distinct package version that at least one workspace locks, each such version
counted once. The byte residual is the decoded bytes less the excluded bytes less the locked bytes.
"""),
    "conventions.md": _doc("""
# Derivation record conventions

A candidate is one value of one withheld constant as it appears in the candidate lists of the
calibration slice, so the candidate space holds sixty candidates. The recovered value of each
constant is accepted and every other candidate is a rival.

The falsifier of a rival is decided with every other withheld constant held at its recovered value.
Under that assignment the calibration shards are either unreadable, and the falsifier is the label
UNREADABLE, or readable, and the falsifier is the first control, in the published order CTRL-1 to
CTRL-6, whose figure differs from its published figure. The calibration shards are unreadable when
any calibration shard gives a negative true block count, a block trailer that does not match, a back
reference tag above the window span, a field that runs past the end of the file, or a block area that
ends before or after its last block.

The falsifier totals count the rivals of each falsifier label and carry only the labels that set
aside at least one rival.

A workspace belongs to the licence divergence list when the lock plan it would receive, if the
licence recorded against the newest name of every rename chain governed, differs from the lock plan
it receives, or when no valid plan would exist under that reading.
"""),
    "report-schema.md": _doc("""
# Report schema

Every delivered document is a JSON object. This file fixes the field names, the value types and the
array orderings. It carries no derived value.

## Workspace lock plan

One document per workspace of the workspace manifest.

| field | type |
| --- | --- |
| `workspace` | string |
| `snapshot_day` | integer |
| `copyleft` | string, `allowed` or `forbidden` |
| `footprint_bytes` | integer |
| `package_count` | integer |
| `quarantined_records` | integer |
| `packages` | array of objects, ascending `package` |

Each entry of `packages` carries `package` (the reported name) as a string, `version` as a
major.minor.patch string, `features` as the integer enabled feature mask, `licence_family` as the
string `permissive` or `copyleft`, and `bytes` as the integer artifact bytes of the locked version.

## Registry performance report

| field | type |
| --- | --- |
| `shards_decoded` | integer |
| `blocks_decoded` | integer |
| `records_decoded` | integer |
| `dependency_entries_decoded` | integer |
| `decoded_bytes` | integer |
| `excluded_bytes` | integer |
| `locked_bytes` | integer |
| `byte_residual` | integer |
| `workspaces_resolved` | integer |
| `footprint_by_workspace` | object keyed by workspace name with integer members |
| `recovered_parameters` | object |

The counts cover the field shards only. `recovered_parameters` carries `salt` as a string,
`window_span`, `bias_limit`, `rotation_base` and `quarantine_days` as integers, and
`permutation_multiplier` as a string of `0x` and eight lowercase hexadecimal digits.

## Bottleneck analysis

| field | type |
| --- | --- |
| `workspaces` | array of objects, ascending `workspace` |

Each entry carries `workspace` as a string, `held_back` as an array of objects in ascending
`package`, each carrying `package`, `locked` and `newest_eligible` as strings, and
`permissive_packages` and `copyleft_packages` as arrays of reported names in ascending order that
together list every locked package of the workspace by governing family.

## Index integrity report

| field | type |
| --- | --- |
| `total_shards` | integer |
| `shards_with_full_flag_set` | integer, shards whose flag word is 0x07ff |
| `records_yanked` | integer, yanked records of registered packages |
| `records_deprecated` | integer, records carrying the deprecated marker |
| `records_unregistered_package` | integer |
| `dependency_entries_back_referenced` | integer, entries that arrived as a tag above 0 |
| `dependency_entries_unregistered_target` | integer |
| `excluded_bytes_by_cause` | object with integer members `unregistered_package` and `yanked` |

Every figure covers the field shards only.

## Derivation record

| field | type |
| --- | --- |
| `candidates` | array of objects, in the order the candidates were weighed |
| `falsifier_totals` | object keyed by falsifier label with integer members |
| `calibration_table` | array of objects, in published control order |
| `settlement_passes_by_workspace` | object keyed by workspace name with integer members |
| `licence_divergence` | array of workspace names, ascending |

Each entry of `candidates` carries `parameter` as one of `salt`, `window_span`, `bias_limit`,
`rotation_base`, `permutation_multiplier` and `quarantine_days`, `value` as a string written the way
the candidate lists write it, `verdict` as `accepted` or `rejected`, and `falsifier` as a falsifier
label, or `none` for an accepted candidate. Each entry of `calibration_table` carries `control` and
`figure` as strings and `published` and `reproduced` as integers.
"""),
}


def registry_csv(built: dict[str, Any]) -> str:
    lines = ["package,package_key,renamed_from,licence"]
    for row in built["registry"]:
        lines.append("%s,%08x,%s,%s" % (row["package"], row["key"], row["renamed_from"], row["licence"]))
    return "\n".join(lines) + "\n"


def workspaces_csv(built: dict[str, Any]) -> str:
    lines = ["workspace,snapshot_day,copyleft"]
    for workspace, snapshot, copyleft in built["workspaces"]:
        lines.append("%s,%d,%s" % (workspace, int(snapshot), copyleft))
    return "\n".join(lines) + "\n"


def requirements_csv(built: dict[str, Any]) -> str:
    lines = ["workspace,package,lowest,below,features"]
    for workspace, package, lo, hi, features in built["requirements"]:
        lines.append("%s,%s,%s,%s,%d" % (workspace, package, lo, hi, int(features)))
    return "\n".join(lines) + "\n"


def calibration_md(values: dict[str, int], snapshot: int) -> str:
    lines = [
        "# Calibration slice",
        "",
        "The calibration shards, tier marker 1, are a held out rehearsal population that never enters any lock",
        "plan. Six registry constants are withheld from every document in this directory. Exactly one",
        "assignment of the six, drawn from the candidate lists below, reproduces every control figure.",
        "",
        "## Candidate lists",
        "",
        "| constant | candidates |",
        "| --- | --- |",
        "| salt word | %s |" % " ".join(SALT_VOCAB),
        "| window span | %s |" % " ".join(str(v) for v in WINDOW_VOCAB),
        "| bias limit | %s |" % " ".join(str(v) for v in BIAS_VOCAB),
        "| rotation base | %s |" % " ".join(str(v) for v in ROTATE_VOCAB),
        "| shuffle multiplier | %s |" % " ".join("0x%08x" % v for v in PERMUTE_VOCAB),
        "| quarantine days | %s |" % " ".join(str(v) for v in QUARANTINE_VOCAB),
        "",
        "The quarantine days constant is the one the resolution policy uses.",
        "",
        "Calibration snapshot day: %d" % snapshot,
        "",
        "## Control figures",
        "",
        "| control | figure | value |",
        "| --- | --- | --- |",
    ]
    for cid, key in zip(CONTROL_IDS, CONTROL_KEYS):
        lines.append("| %s | %s | %d |" % (cid, key, values[key]))
    lines += [
        "",
        "Figure notes, in the same order. Positions and ordinals below are one based, blocks are taken in",
        "logical order, and every value is the true value the shard writer received.",
        "",
        "- CTRL-1: blocks counted across every calibration shard.",
        "- CTRL-2: every package key multiplied by the position of its block inside its shard, summed, modulo 1000003.",
        "- CTRL-3: for every record, the artifact bytes value plus the version code, multiplied by the ordinal of the record, summed, modulo 1000003.",
        "- CTRL-4: for every dependency entry, the target key combined by exclusive or with the lowest version code, plus seven times the requested feature mask, plus the gate, multiplied by the position of the entry inside its record and by the ordinal of the record, summed, modulo 1000003.",
        "- CTRL-5: for every record, three times the status byte plus the dependency entry count, multiplied by the ordinal of the record, summed, modulo 1000003.",
        "- CTRL-6: records that are not yanked, are published on or before the calibration snapshot day, and are published at least the quarantine days before it.",
        "",
    ]
    return "\n".join(lines)


def _dep_text(dep: tuple[int, ...]) -> str:
    gate = "always" if dep[4] == ALWAYS else "bit %d" % dep[4]
    return "%08x %s..%s mask %d %s" % (dep[0], vtext(dep[1]), vtext(dep[2]), dep[3], gate)


def sample_decodes_md(built: dict[str, Any], aliases: dict[str, str] | None = None) -> str:
    """The rehearsal tier in plaintext, headed by the file name the corpus carries.

    A corpus may store the shards under other names, so the heading is taken from
    the alias map rather than from the logical shard name; a document naming a
    file its own directory does not hold would invite a reader to key on names.
    """
    lines = [
        "# Rehearsal decodes",
        "",
        "The rehearsal shards carry tier marker 0 and a flag word of zero, so no optional transform touches",
        "their bytes. Every block they carry is listed below in file order so that a plain reader can be",
        "confirmed before any transform is considered. Their package keys belong to no registered name.",
        "",
    ]
    sample = [shard for shard in built["shards"] if shard["tier"] == TIER_SAMPLE]
    named = [((aliases or {}).get(shard["name"] + ".pidx", shard["name"] + ".pidx"), shard) for shard in sample]
    named.sort(key=lambda pair: pair[0])
    for filename, shard in named:
        lines.append("## %s" % filename)
        lines.append("")
        lines.append("Shard nonce %d, %d blocks." % (shard["nonce"], len(shard["blocks"])))
        lines.append("")
        for index, block in enumerate(shard["blocks"]):
            lines.append("Block %d: package key %08x, block nonce %d." % (index, block["key"], block["block_nonce"]))
            lines.append("")
            lines.append("| version | artifact bytes | publish day | status | dependency entries |")
            lines.append("| --- | --- | --- | --- | --- |")
            for record in block["records"]:
                deps = "; ".join(_dep_text(tuple(d)) for d in record["deps"]) or "none"
                lines.append("| %s | %d | %d | %d | %s |" % (vtext(record["code"]), record["size"], record["day"], record["status"], deps))
            lines.append("")
    return "\n".join(lines)


def example_report(built: dict[str, Any]) -> str:
    sample = [s for s in built["shards"] if s["tier"] == TIER_SAMPLE]
    records = [r for s in sample for b in s["blocks"] for r in b["records"]]
    doc = {
        "total_shards": len(sample),
        "shards_with_full_flag_set": 0,
        "records_yanked": 0,
        "records_deprecated": sum(1 for r in records if r["status"] & STATUS_DEPRECATED),
        "records_unregistered_package": len(records),
        "dependency_entries_back_referenced": 0,
        "dependency_entries_unregistered_target": sum(len(r["deps"]) for r in records),
        "excluded_bytes_by_cause": {"unregistered_package": sum(r["size"] for r in records), "yanked": 0},
    }
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


POISON_REPORT = {
    "total_shards": 99,
    "shards_with_full_flag_set": 99,
    "records_yanked": 99,
    "records_deprecated": 99,
    "records_unregistered_package": 99,
    "dependency_entries_back_referenced": 99,
    "dependency_entries_unregistered_target": 99,
    "excluded_bytes_by_cause": {"unregistered_package": 99, "yanked": 99},
}


def _write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def write_corpus(root: Path, seed: int, mutation: str = "", field_flags: int | None = None,
                 rename: str = "") -> dict[str, Any]:
    built = make_corpus(seed, mutation, field_flags)
    root.mkdir(parents=True, exist_ok=True)
    names = sorted(built["files"])
    aliases = {}
    for index, name in enumerate(names):
        aliases[name] = "shard_%02d.pidx" % ((index * 7 + 3) % len(names)) if rename == "alt" else name
    for name in names:
        (root / aliases[name]).write_bytes(built["files"][name])
    _write(root / "package-registry.csv", registry_csv(built))
    _write(root / "workspaces.csv", workspaces_csv(built))
    _write(root / "workspace-requirements.csv", requirements_csv(built))
    values = controls(built["files"], built["params"], built["calibration_snapshot"])
    _write(root / "calibration.md", calibration_md(values, built["calibration_snapshot"]))
    _write(root / "rehearsal-decodes.md", sample_decodes_md(built, aliases))
    example = example_report(built)
    if rename == "poison":
        example = json.dumps(POISON_REPORT, indent=2, sort_keys=True) + "\n"
    _write(root / "example-report.json", example)
    for doc_name, doc_text in STATIC_DOCS.items():
        _write(root / doc_name, doc_text)
    built["controls"] = values
    return built


def _write_corpus(root: Path) -> dict[str, Any]:
    return write_corpus(root, SEED)


# ---------------------------------------------------------------------------
# staging harness
# ---------------------------------------------------------------------------

SCENARIO_NAMES = tuple("scenario_%s" % ws for ws in WORKSPACE_NAMES)
ARTIFACT_NAMES = SCENARIO_NAMES + ("perf_report", "bottleneck_analysis", "recommendations", "data_quality")
PROGRAM_NAME = "optimize.py"
RUN_TIMEOUT_SEC = 60

# Figures of perf_report.json that follow from decoding the shards alone, and
# figures that follow from settling the lock plans. The two families are graded
# by different tiers so that one wrong figure costs one family rather than the
# whole channel.
DECODE_PERF_KEYS = (
    "shards_decoded",
    "blocks_decoded",
    "records_decoded",
    "dependency_entries_decoded",
    "decoded_bytes",
    "excluded_bytes",
)
PLAN_PERF_KEYS = (
    "locked_bytes",
    "byte_residual",
    "workspaces_resolved",
    "footprint_by_workspace",
)

_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

# rewardkit evaluates the criteria concurrently, so every lazy cache below is
# built under a lock. Staging a corpus and computing an expectation happen once
# each; the agent program runs outside the lock so the tiers still overlap.
_STAGE_LOCK = threading.Lock()
_FACTS_LOCK = threading.Lock()
_PAIR_LOCK = threading.Lock()
_STAGED: dict[tuple[str, int, str], Path] = {}
_FACTS: dict[tuple[str, int], Any] = {}
_PAIR: dict[str, list[Path | None]] = {}


def _untrusted_command(command: list[str]) -> list[str]:
    """Drop privileges before running agent code whenever there are any to drop.

    Grading runs as root in the verifier container, which is where the privilege
    drop matters: the agent's program is hostile input and /tests holds the
    expectations it is graded against. A reviewer running this module by hand is
    not root and has no protected /tests to shield, so there the command runs as
    the reviewer.
    """
    if os.name == "posix" and os.geteuid() == 0:
        return [*_SETPRIV, *command]
    return command


def _open_dir(prefix: str, mode: int = 0o755) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    path.chmod(mode)
    return path


def _relax(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        path.chmod(0o644 if path.is_file() else 0o755)
    root.chmod(0o755)


def _stage(mutation: str = "", field_flags: int | None = None, rename: str = "") -> Path:
    key = (mutation, -1 if field_flags is None else field_flags, rename)
    with _STAGE_LOCK:
        cached = _STAGED.get(key)
        if cached is not None:
            return cached
        root = _open_dir("pidx-stage-") / "data"
        write_corpus(root, SEED, mutation, field_flags, rename)
        _relax(root)
        _STAGED[key] = root
        return root


def _program(workspace: Path) -> Path:
    return workspace / "out" / PROGRAM_NAME


def _run(workspace: Path, root: Path) -> Path | None:
    """Run the delivered program over a private copy of a staged corpus.

    Returns the output directory, or None when the program is missing, times
    out, or exits non-zero. The subprocess gets its own session and the whole
    group is killed before this returns, so nothing the agent spawned can
    outlive the check and rewrite the reward after rewardkit has written it.
    """
    script = _program(workspace)
    if not script.is_file():
        return None
    out = _open_dir("pidx-out-", 0o777)
    copy_root = _open_dir("pidx-in-") / root.name
    shutil.copytree(root, copy_root)
    _relax(copy_root)
    proc = None
    try:
        proc = subprocess.Popen(
            _untrusted_command([sys.executable, str(script), str(copy_root), str(out)]),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            proc.communicate(timeout=RUN_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            return None
        if proc.returncode != 0:
            return None
        return out
    except OSError:
        return None
    finally:
        if proc is not None:
            _reap(proc)


def _reap(proc: subprocess.Popen[str]) -> None:
    """Kill the program's whole process group and wait for it to go away."""
    try:
        group = os.getpgid(proc.pid)
    except (OSError, AttributeError):
        group = None
    if group is not None:
        try:
            os.killpg(group, signal.SIGKILL)
        except OSError:
            pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    for pipe in (proc.stdout, proc.stderr):
        if pipe is not None and not pipe.closed:
            pipe.close()


def _run_staged(workspace: Path, mutation: str = "", field_flags: int | None = None,
                rename: str = "") -> Path | None:
    try:
        return _run(workspace, _stage(mutation, field_flags, rename))
    except (OSError, ValueError, KeyError, RecursionError, SearchBudget, Unreadable):
        return None


def _shipped_pair(workspace: Path) -> list[Path | None]:
    """Two runs of the delivered program over the same shipped corpus."""
    key = str(workspace)
    with _PAIR_LOCK:
        pair = _PAIR.get(key)
        if pair is None:
            pair = [_run_staged(workspace), _run_staged(workspace)]
            _PAIR[key] = pair
        return pair


def _facts(mutation: str = "", field_flags: int | None = None) -> Any:
    """The expectation for one corpus, computed from its plaintext.

    A corpus the expectation model cannot settle is an authoring defect rather
    than an agent defect; it is cached as the exception so every check that
    depends on it reports the same reason instead of raising.
    """
    key = (mutation, -1 if field_flags is None else field_flags)
    with _FACTS_LOCK:
        if key not in _FACTS:
            try:
                _FACTS[key] = expected_facts(make_corpus(SEED, mutation, field_flags))
            except (AssertionError, ValueError, KeyError, SearchBudget, Unreadable) as exc:
                _FACTS[key] = exc
        return _FACTS[key]


def _load(out: Path | None, name: str) -> Any:
    """One delivered document, or None when it is missing or not readable."""
    if out is None:
        return None
    path = out / (name + ".json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _diff(label: str, got: Any, want: Any) -> list[str]:
    if got == want:
        return []
    if isinstance(got, dict) and isinstance(want, dict):
        problems = []
        for key in sorted(set(got) | set(want)):
            if got.get(key) != want.get(key):
                problems.append("%s.%s is %r, expected %r" % (label, key, got.get(key), want.get(key)))
        if problems:
            return problems
    return ["%s is %r, expected %r" % (label, got, want)]


def _subset(doc: Any, keys: tuple[str, ...]) -> Any:
    if not isinstance(doc, dict):
        return None
    return {key: doc.get(key) for key in keys}


def _decode_problems(out: Path | None, facts: Any) -> list[str]:
    """The figures that follow from decoding the field shards."""
    if isinstance(facts, Exception):
        return ["the corpus expectation could not be settled: %s" % facts]
    if out is None:
        return ["the delivered program produced no output"]
    problems = _diff("data_quality", _load(out, "data_quality"), facts["data_quality"])
    perf = _load(out, "perf_report")
    want = facts["perf_report"]
    problems += _diff("perf_report", _subset(perf, DECODE_PERF_KEYS), _subset(want, DECODE_PERF_KEYS))
    problems += _diff(
        "perf_report.recovered_parameters",
        perf.get("recovered_parameters") if isinstance(perf, dict) else None,
        want["recovered_parameters"],
    )
    return problems


def _plan_problems(out: Path | None, facts: Any) -> list[str]:
    """The figures that follow from settling the lock plans."""
    if isinstance(facts, Exception):
        return ["the corpus expectation could not be settled: %s" % facts]
    if out is None:
        return ["the delivered program produced no output"]
    problems: list[str] = []
    for workspace in WORKSPACE_NAMES:
        problems += _diff(
            "scenario_" + workspace,
            _load(out, "scenario_" + workspace),
            facts["scenarios"][workspace],
        )
    problems += _diff("bottleneck_analysis", _load(out, "bottleneck_analysis"), facts["bottleneck_analysis"])
    perf = _load(out, "perf_report")
    want = facts["perf_report"]
    problems += _diff("perf_report", _subset(perf, PLAN_PERF_KEYS), _subset(want, PLAN_PERF_KEYS))
    if isinstance(perf, dict):
        try:
            residual = perf["decoded_bytes"] - perf["excluded_bytes"] - perf["locked_bytes"]
        except (KeyError, TypeError):
            problems.append("perf_report omits the figures the byte residual is built from")
        else:
            if residual < 0 or perf.get("byte_residual") != residual:
                problems.append("the byte residual does not close")
    return problems


RECORD_KEYS = {"candidates", "falsifier_totals", "calibration_table", "settlement_passes_by_workspace", "licence_divergence"}
RECORD_PARAMETERS = {
    "salt": "salt",
    "window_span": "window",
    "bias_limit": "bias",
    "rotation_base": "rotate",
    "permutation_multiplier": "permute",
    "quarantine_days": "quarantine",
}


def _candidate_text(name: str, value: Any) -> str:
    return "0x%08x" % value if name == "permute" else str(value)


def _exact_int(value: Any, want: int) -> bool:
    """True only for a JSON integer equal to want; a bool never counts as one."""
    return isinstance(value, int) and not isinstance(value, bool) and value == want


def _rival_falsifiers(facts: Any) -> dict[tuple[str, str], str]:
    """The falsifier label of every rival, keyed the way the record writes it."""
    label_of = {internal: label for label, internal in RECORD_PARAMETERS.items()}
    return {
        (label_of[row["parameter"]], _candidate_text(row["parameter"], row["value"])): row["falsifier"]
        for row in facts["rivals"]
    }


def _record_problems(out: Path | None, facts: Any) -> list[str]:
    """The derivation record: candidate verdicts, falsifier totals, passes, divergence."""
    if isinstance(facts, Exception):
        return ["the corpus expectation could not be settled: %s" % facts]
    record = _load(out, "recommendations")
    if not isinstance(record, dict):
        return ["the derivation record is missing or does not parse"]
    problems: list[str] = []
    if set(record) != RECORD_KEYS:
        return ["the derivation record carries fields %r" % sorted(record)]
    expected_space = {
        (label, _candidate_text(key, value))
        for label, key in RECORD_PARAMETERS.items()
        for value in VOCABS[key]
    }
    seen: set[tuple[str, str]] = set()
    accepted: dict[str, str] = {}
    rivals = _rival_falsifiers(facts)
    entries = record["candidates"]
    if not isinstance(entries, list):
        return ["the candidate list is not an array"]
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"parameter", "value", "verdict", "falsifier"}:
            problems.append("a candidate entry carries %r" % (sorted(entry) if isinstance(entry, dict) else entry))
            continue
        if not isinstance(entry["parameter"], str) or not isinstance(entry["value"], str):
            # Both are strings in the schema; a non-scalar would raise in the lookup
            # and the set below, aborting the whole run instead of failing one check.
            problems.append("a candidate entry names parameter %r with value %r"
                            % (entry["parameter"], entry["value"]))
            continue
        if entry["parameter"] not in RECORD_PARAMETERS:
            problems.append("unknown parameter %r" % entry["parameter"])
            continue
        seen.add((entry["parameter"], entry["value"]))
        if entry["verdict"] == "accepted":
            if entry["falsifier"] != "none":
                problems.append("accepted candidate %r carries falsifier %r" % (entry["value"], entry["falsifier"]))
            accepted[entry["parameter"]] = entry["value"]
        elif entry["verdict"] == "rejected":
            want = rivals.get((entry["parameter"], entry["value"]))
            if entry["falsifier"] != want:
                problems.append("rejected candidate %r carries falsifier %r, expected %r"
                                % (entry["value"], entry["falsifier"], want))
        else:
            problems.append("candidate %r carries verdict %r" % (entry["value"], entry["verdict"]))
    if seen != expected_space or len(entries) != len(expected_space):
        problems.append("the record does not weigh every candidate once")
    recovered = facts["perf_report"]["recovered_parameters"]
    wanted = {label: str(recovered[label]) for label in RECORD_PARAMETERS}
    if accepted != wanted:
        problems.append("the accepted candidates are %r, expected %r" % (accepted, wanted))
    totals = record["falsifier_totals"]
    if not isinstance(totals, dict) or totals != facts["falsifier_totals"]:
        problems.append("the falsifier totals are %r, expected %r" % (totals, facts["falsifier_totals"]))
    table = record["calibration_table"]
    if not isinstance(table, list) or [row.get("control") if isinstance(row, dict) else None for row in table] != list(CONTROL_IDS):
        problems.append("the calibration table rows are out of order")
    else:
        for row, control, key in zip(table, CONTROL_IDS, CONTROL_KEYS):
            if set(row) != {"control", "figure", "published", "reproduced"}:
                problems.append("calibration row %r carries %r" % (row.get("control"), sorted(row)))
                continue
            figure = facts["controls"][key]
            if row["figure"] != key:
                problems.append("control %s names figure %r, expected %r" % (control, row["figure"], key))
            if not _exact_int(row["published"], figure):
                problems.append("control %s publishes %r, expected %r" % (control, row["published"], figure))
            if not _exact_int(row["reproduced"], figure):
                problems.append("control %s reproduces %r, expected %r" % (control, row["reproduced"], figure))
    passes = record["settlement_passes_by_workspace"]
    if not isinstance(passes, dict) or passes != facts["passes"]:
        problems.append("the settlement passes are %r, expected %r" % (passes, facts["passes"]))
    divergence = record["licence_divergence"]
    if not isinstance(divergence, list) or divergence != sorted(facts["divergence"]):
        problems.append("the licence divergence list is %r, expected %r" % (divergence, sorted(facts["divergence"])))
    return problems


def _published_form(out: Path | None, name: str) -> bool:
    if out is None:
        return False
    try:
        text = (out / (name + ".json")).read_text(encoding="utf-8")
        return text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    except (OSError, ValueError):
        return False


def _strip_source(text: str) -> str:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    drop: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    drop.update(range(body[0].lineno, (body[0].end_lineno or body[0].lineno) + 1))
    kept = []
    for number, line in enumerate(text.splitlines(), start=1):
        if number in drop:
            continue
        cut = []
        quote = ""
        index = 0
        while index < len(line):
            ch = line[index]
            if quote:
                cut.append(ch)
                if ch == "\\":
                    index += 1
                    if index < len(line):
                        cut.append(line[index])
                elif ch == quote:
                    quote = ""
            elif ch in "'\"":
                quote = ch
                cut.append(ch)
            elif ch == "#":
                break
            else:
                cut.append(ch)
            index += 1
        kept.append("".join(cut))
    return "\n".join(kept)


def _delivered_source(workspace: Path) -> str:
    try:
        return _strip_source(_program(workspace).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return ""


def _artifact_bytes(out: Path | None) -> dict[str, str]:
    found = {}
    for name in ARTIFACT_NAMES:
        text = ""
        if out is not None:
            try:
                text = (out / (name + ".json")).read_text(encoding="utf-8")
            except OSError:
                text = ""
        found[name] = text
    return found


def _stable_pair(workspace: Path) -> dict[str, str] | None:
    """The documents of two identical runs, or None when the two disagree.

    The filename and example-report detectors below stand down on an unstable
    program so that one decision never fires two of them.
    """
    first, second = _shipped_pair(workspace)
    plain = _artifact_bytes(first)
    if plain != _artifact_bytes(second):
        return None
    return plain

# ---------------------------------------------------------------------------
# graded checks: shipped documents
#
# These four are weighted 1 on purpose. They read the documents already sitting
# in /app/out, which a program that replays memorised answers can satisfy, so
# they are priced as existence checks. The graded weight lives on the trap and
# generalisation tiers below, whose corpora each carry their own withheld
# constants and so cannot be replayed.
# ---------------------------------------------------------------------------


@criterion(description="the delivered program and all nine documents exist in the published serialised form")
def delivers_every_document(workspace: Path) -> bool:
    if not _program(workspace).is_file():
        return False
    out = workspace / "out"
    for name in ARTIFACT_NAMES:
        payload = _load(out, name)
        if not isinstance(payload, dict) or not payload:
            return False
        if not _published_form(out, name):
            return False
    return True


@criterion(description="the shipped field shards decode to the published integrity and byte figures")
def shipped_index_is_decoded(workspace: Path) -> bool:
    return not _decode_problems(workspace / "out", _facts())


@criterion(description="the five shipped workspaces receive their lock plans with settled features")
def shipped_workspaces_are_settled(workspace: Path) -> bool:
    return not _plan_problems(workspace / "out", _facts())


@criterion(description="the shipped derivation record weighs every candidate and reproduces every control")
def shipped_derivation_is_recorded(workspace: Path) -> bool:
    return not _record_problems(workspace / "out", _facts())


# ---------------------------------------------------------------------------
# graded checks: trap tier
#
# One corpus per optional transform, each carrying its own withheld constants.
# These grade the decode family only, so a planner defect cannot cost the whole
# channel and a decode defect cannot hide behind a correct plan.
# ---------------------------------------------------------------------------


def _trap(workspace: Path, flags: int) -> bool:
    return not _decode_problems(_run_staged(workspace, "", flags), _facts("", flags))


@criterion(description="the keyed artifact bytes mask is inverted on a population carrying only that transform")
def trap_mask_bytes(workspace: Path) -> bool:
    return _trap(workspace, FLAG_MASK_BYTES)


@criterion(description="chained version codes are rebuilt on a population carrying only that transform")
def trap_chain_version(workspace: Path) -> bool:
    return _trap(workspace, FLAG_CHAIN_VERSION)


@criterion(description="second order publish days are rebuilt on a population carrying only that transform")
def trap_delta2_day(workspace: Path) -> bool:
    return _trap(workspace, FLAG_DELTA2_DAY)


@criterion(description="the drifting block key is rebuilt while earlier blocks are decoded")
def trap_drift_key(workspace: Path) -> bool:
    return _trap(workspace, FLAG_MASK_BYTES | FLAG_DRIFT_KEY)


@criterion(description="the shuffled block order is inverted before the drifting key is rebuilt")
def trap_block_permute(workspace: Path) -> bool:
    return _trap(workspace, FLAG_MASK_BYTES | FLAG_DRIFT_KEY | FLAG_BLOCK_PERMUTE)


@criterion(description="back referenced dependency entries are resolved through the ring")
def trap_backref_deps(workspace: Path) -> bool:
    return _trap(workspace, FLAG_BACKREF_DEPS)


@criterion(description="the opposite endian nonce and record counts are read on a population carrying only that transform")
def trap_endian_island(workspace: Path) -> bool:
    return _trap(workspace, FLAG_ENDIAN_ISLAND)


@criterion(description="the block count bias is removed on a population carrying only that transform")
def trap_biased_count(workspace: Path) -> bool:
    return _trap(workspace, FLAG_BIASED_COUNT)


@criterion(description="rotated status words are restored after the block trailer is checked")
def trap_rot_status(workspace: Path) -> bool:
    return _trap(workspace, FLAG_ROT_STATUS)


@criterion(description="package keys are recovered through the companion shard of the same tier")
def trap_xref_key(workspace: Path) -> bool:
    return _trap(workspace, FLAG_XREF_KEY)


@criterion(description="the padding after each block trailer is skipped so the cursor stays aligned")
def trap_split_tail(workspace: Path) -> bool:
    return _trap(workspace, FLAG_SPLIT_TAIL)


# ---------------------------------------------------------------------------
# graded checks: generalisation tier
#
# One held out mutation family per check, each carrying its own withheld
# constants, so no shipped answer can be replayed. These grade the plan and
# record families.
# ---------------------------------------------------------------------------


def _held_out(workspace: Path, mutation: str) -> bool:
    out = _run_staged(workspace, mutation)
    facts = _facts(mutation)
    return not (_plan_problems(out, facts) + _record_problems(out, facts))


@criterion(description="a held out population whose smallest footprint is shared by two plans resolves")
def held_out_tie_footprint(workspace: Path) -> bool:
    return _held_out(workspace, "tie_footprint")


@criterion(description="a held out population with a version sitting on the quarantine boundary resolves")
def held_out_temporal_edge(workspace: Path) -> bool:
    return _held_out(workspace, "temporal_edge")


@criterion(description="a held out population with the licences of a rename chain swapped resolves")
def held_out_invert_chain(workspace: Path) -> bool:
    return _held_out(workspace, "invert_chain")


@criterion(description="a held out population with licence expressions flipped across families resolves")
def held_out_flip_licence(workspace: Path) -> bool:
    return _held_out(workspace, "flip_licence")


@criterion(description="a held out population with no copyleft package resolves")
def held_out_empty_copyleft(workspace: Path) -> bool:
    return _held_out(workspace, "empty_copyleft")


@criterion(description="a held out population with a feature activation cycle resolves")
def held_out_feature_cycle(workspace: Path) -> bool:
    return _held_out(workspace, "feature_cycle")


@criterion(description="a held out population with an added package that moves the plans resolves")
def held_out_add_entity(workspace: Path) -> bool:
    return _held_out(workspace, "add_entity")


@criterion(description="a held out population with newly yanked versions resolves")
def held_out_yank_wave(workspace: Path) -> bool:
    return _held_out(workspace, "yank_wave")


@criterion(description="a held out population scaled by an order of magnitude over twice the shards resolves")
def held_out_scale_bytes(workspace: Path) -> bool:
    return _held_out(workspace, "scale_bytes")


@criterion(description="a held out population with unregistered dependency targets resolves")
def held_out_unregistered_burst(workspace: Path) -> bool:
    return _held_out(workspace, "unregistered_burst")


@criterion(description="a held out population in which every workspace allows copyleft resolves")
def held_out_allow_copyleft(workspace: Path) -> bool:
    return _held_out(workspace, "allow_copyleft")


@criterion(description="a held out population with narrowed workspace requirements resolves")
def held_out_narrow_roots(workspace: Path) -> bool:
    return _held_out(workspace, "narrow_roots")


@criterion(description="a held out population with a wider version catalogue resolves")
def held_out_wide_catalogue(workspace: Path) -> bool:
    return _held_out(workspace, "wide_catalogue")


@criterion(description="a held out population with no repeated dependency entry resolves")
def held_out_no_backref(workspace: Path) -> bool:
    return _held_out(workspace, "no_backref")


@criterion(description="a held out population with a lengthened rename chain resolves")
def held_out_extend_chain(workspace: Path) -> bool:
    return _held_out(workspace, "extend_chain")


@criterion(description="a held out population with earlier snapshot days resolves")
def held_out_early_snapshot(workspace: Path) -> bool:
    return _held_out(workspace, "early_snapshot")


# ---------------------------------------------------------------------------
# graded checks: negatives
#
# Each returns True when its shortcut is present, so an honest program returns
# False and the negative weight is never added.
# ---------------------------------------------------------------------------


@criterion(description="the delivered program carries shipped answer figures as literals")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    source = _delivered_source(workspace)
    if not source:
        return False
    facts = _facts()
    if isinstance(facts, Exception):
        return False
    perf = facts["perf_report"]
    marks = [perf["decoded_bytes"], perf["locked_bytes"], perf["byte_residual"], perf["excluded_bytes"]]
    marks += [facts["scenarios"][ws]["footprint_bytes"] for ws in WORKSPACE_NAMES]
    return any(str(value) in source for value in marks)


@criterion(description="the delivered program keys its behaviour off the shard file names")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    plain = _stable_pair(workspace)
    if plain is None:
        return False
    renamed = _artifact_bytes(_run_staged(workspace, "", None, "alt"))
    return renamed != plain


@criterion(description="the delivered program consults the supplied example report while deriving")
def negative_reads_supplied_answer_data_at_runtime(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    honest = _stable_pair(workspace)
    if honest is None:
        return False
    poisoned = _artifact_bytes(_run_staged(workspace, "", None, "poison"))
    return poisoned != honest


@criterion(description="the delivered program produces different documents from identical input")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    first, second = _shipped_pair(workspace)
    if first is None and second is None:
        return False
    return _artifact_bytes(first) != _artifact_bytes(second)


# ---------------------------------------------------------------------------
# weight registrations
#
# 31 positive checks totalling 139, 4 negative checks totalling 18.
# ---------------------------------------------------------------------------

criteria.delivers_every_document(weight=1)
criteria.shipped_index_is_decoded(weight=1)
criteria.shipped_workspaces_are_settled(weight=1)
criteria.shipped_derivation_is_recorded(weight=1)

criteria.trap_mask_bytes(weight=5)
criteria.trap_chain_version(weight=5)
criteria.trap_delta2_day(weight=5)
criteria.trap_drift_key(weight=5)
criteria.trap_block_permute(weight=5)
criteria.trap_backref_deps(weight=5)
criteria.trap_endian_island(weight=5)
criteria.trap_biased_count(weight=5)
criteria.trap_rot_status(weight=5)
criteria.trap_xref_key(weight=5)
criteria.trap_split_tail(weight=5)

criteria.held_out_tie_footprint(weight=5)
criteria.held_out_temporal_edge(weight=5)
criteria.held_out_invert_chain(weight=5)
criteria.held_out_flip_licence(weight=5)
criteria.held_out_empty_copyleft(weight=5)
criteria.held_out_feature_cycle(weight=5)
criteria.held_out_add_entity(weight=5)
criteria.held_out_yank_wave(weight=5)
criteria.held_out_scale_bytes(weight=5)
criteria.held_out_unregistered_burst(weight=5)
criteria.held_out_allow_copyleft(weight=5)
criteria.held_out_narrow_roots(weight=5)
criteria.held_out_wide_catalogue(weight=5)
criteria.held_out_no_backref(weight=5)
criteria.held_out_extend_chain(weight=5)
criteria.held_out_early_snapshot(weight=5)

criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_supplied_answer_data_at_runtime(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)


# ---------------------------------------------------------------------------
# author side modes: python3 tests/test_output.py environment | pins <witness.json>
# ---------------------------------------------------------------------------


def _prove_pins(witness_path: Path | None) -> int:
    built = make_corpus(SEED)
    rows = falsifier_table(built)
    missing = [row for row in rows if row["falsifier"] is None]
    for row in missing:
        print("UNWITNESSED %s=%r" % (row["parameter"], row["value"]))
    if witness_path is not None:
        witness_path.write_bytes((json.dumps(rows, indent=1) + "\n").encode("utf-8"))
    print("PIN WITNESS " + ("FAIL" if missing else "OK"))
    return 1 if missing else 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "pins":
        sys.exit(_prove_pins(Path(sys.argv[2]) if len(sys.argv) > 2 else None))
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("environment")
    if target.name == "environment":
        target = target / "data"
    built = _write_corpus(target)
    assert_postconditions(built, shipped=True)
    print("CORPUS POSTCONDITIONS OK")
