"""Verifier for the VARC1 recovery task (self-contained).

Holds the reference codec written from format_contract.md, escape_rules.md,
revision_notes.md and decoder_appendix.md; the builders that regenerate the
agent-visible data (SAMPLE_SEED drives the tables and the catalog,
CHALLENGE_SEED the three stream 3 segment files); the builders that draw the
hidden multi-segment evaluation streams from EVAL_SEED at grade time; and the
rewardkit checks. Grading runs in a separate container without /app/data, so
everything the checks compare against is rebuilt here.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

MAGIC = b"VARC1"
VERSION = 2
HEADER_SIZE = 16
TRAILER_SIZE = 4
SYNC = 0xAA
ESC = 0x1B
MIN_FRAME = 5

MODE_RAW, MODE_DELTA, MODE_DICT, MODE_RESET = 0, 1, 2, 3
MODE_NAME = {0: "raw", 1: "delta", 2: "dict", 3: "reset"}
NAME_MODE = {v: k for k, v in MODE_NAME.items()}


class FrameError(Exception):
    """A frame that does not parse (escape_rules.md, "When a frame parses")."""


# --------------------------------------------------------------------------- #
# varints and escaping                                                         #
# --------------------------------------------------------------------------- #
def write_uvarint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def read_uvarint(buf: bytes, pos: int, end: int) -> tuple[int, int]:
    val = shift = 0
    while True:
        if pos >= end:
            raise FrameError("truncated varint")
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if not b & 0x80:
            return val, pos
        shift += 7


def write_sleb128(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if (n == 0 and not b & 0x40) or (n == -1 and b & 0x40):
            out.append(b)
            return bytes(out)
        out.append(b | 0x80)


def write_sleb128_len(n: int, length: int | None) -> bytes:
    """Exactly `length` bytes (sign-repeating groups), or shortest when None."""
    out = bytearray(write_sleb128(n))
    if length is None or length <= len(out):
        return bytes(out)
    fill = 0x7F if n < 0 else 0x00
    while len(out) < length:
        out[-1] |= 0x80
        out.append(fill)
    return bytes(out)


def read_sleb128(buf: bytes, pos: int, end: int) -> tuple[int, int]:
    result = shift = 0
    start = pos
    while True:
        if pos >= end:
            raise FrameError("truncated sleb128")
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            if b & 0x40:
                result -= 1 << shift
            return result, pos - start


def escape_body(raw: bytes) -> bytes:
    out = bytearray()
    for b in raw:
        if b in (SYNC, ESC):
            out += bytes([ESC, b ^ 0x20])
        else:
            out.append(b)
    return bytes(out)


def unescape_window(buf: bytes, pos: int, body_len: int, end: int) -> tuple[bytes, int]:
    stop = pos + body_len
    if stop > end:
        raise FrameError("body runs past the trailer")
    raw = bytearray()
    i = pos
    while i < stop:
        if buf[i] == ESC:
            if i + 1 >= stop:
                raise FrameError("escape byte without a partner")
            raw.append(buf[i + 1] ^ 0x20)
            i += 2
        else:
            raw.append(buf[i])
            i += 1
    return bytes(raw), stop


# --------------------------------------------------------------------------- #
# header, trailer, encoder                                                     #
# --------------------------------------------------------------------------- #
def crc_header(buf: bytes) -> int:
    return zlib.crc32(bytes(buf[5:16])) & 0xFFFFFFFF


def build_header(stream_id: int, seq_no: int, rec_count: int, revision: int,
                 stream_continues: bool) -> bytes:
    return (MAGIC + bytes([VERSION, 0x01 if stream_continues else 0x00])
            + struct.pack("<HHH", stream_id, seq_no, rec_count)
            + bytes([revision, 0, 0]))


def _json_int(value) -> bool:
    """A JSON integer as json.loads returns it (bool is not one)."""
    return type(value) is int


def encode_frame(rec: dict) -> bytes:
    mode_name = rec["mode"]
    mode = NAME_MODE[mode_name]
    wide = bool(rec.get("wide")) if mode_name == "raw" else False
    long_key = bool(rec.get("long_key"))
    exts = rec.get("extensions") or []
    raw = bytearray()
    if mode_name == "raw":
        # decoder_appendix.md: raw_value is written as its low 16 or 32 bits
        width = 4 if wide else 2
        raw += (rec["raw_value"] & ((1 << (8 * width)) - 1)).to_bytes(width, "little")
    elif mode_name == "delta":
        length = rec.get("delta_raw_len")
        raw += write_sleb128_len(rec["delta_raw"], length if _json_int(length) else None)
    elif mode_name == "dict":
        raw.append(rec["dict_index"])
    for ext in exts:
        payload = bytes.fromhex(ext["hex"].strip())
        raw += write_uvarint(ext["type"]) + write_uvarint(len(payload)) + payload
    sel = mode | (wide << 2) | (long_key << 3) | (bool(exts) << 4)
    frame = bytearray([SYNC, sel])
    if long_key:
        kb = rec["key_str"].encode("utf-8")
        frame += write_uvarint(len(kb)) + kb
    else:
        frame.append(rec["raw_key"])
    esc = escape_body(bytes(raw))
    frame.append(sum(raw) & 0xFF)
    frame += write_uvarint(len(esc)) + esc
    return bytes(frame)


def encode_segment(doc: dict) -> bytes:
    body = b"".join(encode_frame(rec) for rec in doc["records"])
    header = build_header(doc["stream_id"], doc["seq_no"], len(doc["records"]),
                          doc["revision"], bool(doc["flags"]["stream_continues"]))
    return header + body + struct.pack("<I", crc_header(header))


# --------------------------------------------------------------------------- #
# stream state and field names                                                 #
# --------------------------------------------------------------------------- #
class StreamState:
    """format_contract.md Terms: one cumulator per field name, one resolved list."""
    __slots__ = ("cumulators", "resolved")

    def __init__(self) -> None:
        self.cumulators: dict[Any, int] = {}
        self.resolved: list[int] = []

    def copy(self) -> "StreamState":
        twin = StreamState()
        twin.cumulators = dict(self.cumulators)
        twin.resolved = list(self.resolved)
        return twin

    def apply(self, rec: dict) -> None:
        if rec["mode"] == "reset":
            self.cumulators = {}
            self.resolved = []
            return
        self.resolved.append(rec["value"])
        if rec["mode"] in ("raw", "delta"):
            self.cumulators[rec["field"]] = rec["value"]


def empty_schema() -> dict:
    return {"id_to_name": {}, "name_to_id": {}, "id_to_unit": {}, "alias": {}, "remap": {}}


def resolve_field(rec: dict, stream_id: int, revision: int, schema: dict):
    if rec["mode"] == "reset":
        return None, None, None
    if rec["long_key"]:
        base = rec["key_str"]
        canonical = schema["name_to_id"].get(base)
    else:
        canonical = schema["remap"].get((revision, rec["raw_key"]), rec["raw_key"])
        base = schema["id_to_name"].get(canonical)
    if canonical is None:
        return base, None, None
    return (schema["alias"].get((stream_id, canonical), base),
            schema["id_to_unit"].get(canonical), canonical)


def parse_frame(buf: bytes, pos: int, end: int, state: StreamState, stream_id: int,
                revision: int, schema: dict) -> tuple[dict, int]:
    """Parse one frame without touching `state`; the caller applies it."""
    if pos >= end or buf[pos] != SYNC:
        raise FrameError("no sync byte")
    if pos + 1 >= end:
        raise FrameError("truncated selector")
    sel = buf[pos + 1]
    p = pos + 2
    mode = sel & 0x03
    wide = bool(sel & 0x04)
    long_key = bool(sel & 0x08)
    has_ext = bool(sel & 0x10)
    if sel >> 5:
        raise FrameError("reserved selector bits set")
    if wide and mode != MODE_RAW:
        raise FrameError("wide bit on a non raw frame")
    key_str = None
    raw_key = None
    if long_key:
        klen, p = read_uvarint(buf, p, end)
        if p + klen > end:
            raise FrameError("truncated key")
        try:
            key_str = bytes(buf[p:p + klen]).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FrameError("key is not UTF-8") from exc
        p += klen
    else:
        if p >= end:
            raise FrameError("truncated key")
        raw_key = buf[p]
        p += 1
    if p >= end:
        raise FrameError("truncated fchk")
    fchk = buf[p]
    p += 1
    body_len, p = read_uvarint(buf, p, end)
    raw, p = unescape_window(buf, p, body_len, end)
    if sum(raw) & 0xFF != fchk:
        raise FrameError("fchk mismatch")

    rec: dict[str, Any] = {"raw_key": raw_key, "long_key": long_key}
    if long_key:
        rec["key_str"] = key_str
    rec["mode"] = MODE_NAME[mode]
    rec["wide"] = None
    if mode == MODE_RESET:
        rec["field"], rec["unit"], rec["canonical_id"] = None, None, None
    else:
        rec["field"], rec["unit"], rec["canonical_id"] = resolve_field(rec, stream_id, revision,
                                                                        schema)
    off = 0
    if mode == MODE_RAW:
        width = 4 if wide else 2
        if len(raw) < width:
            raise FrameError("raw value short")
        rec["wide"] = wide
        rec["raw_value"] = int.from_bytes(raw[:width], "little", signed=rec["unit"] != "count")
        rec["value"] = rec["raw_value"]
        off = width
    elif mode == MODE_DELTA:
        delta, nb = read_sleb128(raw, 0, len(raw))
        rec["delta_raw"] = delta
        rec["delta_raw_len"] = nb
        rec["value"] = state.cumulators.get(rec["field"], 0) + delta
        off = nb
    elif mode == MODE_DICT:
        if not raw:
            raise FrameError("dict index missing")
        idx = raw[0]
        if idx >= len(state.resolved):
            raise FrameError("dict index outside the resolved list")
        rec["dict_index"] = idx
        rec["value"] = state.resolved[len(state.resolved) - 1 - idx]
        off = 1
    else:
        rec["value"] = None
    exts = []
    if has_ext:
        if off >= len(raw):
            raise FrameError("extension flag without an extension")
        q = off
        while q < len(raw):
            etype, q = read_uvarint(raw, q, len(raw))
            elen, q = read_uvarint(raw, q, len(raw))
            if q + elen > len(raw):
                raise FrameError("extension payload truncated")
            exts.append({"type": etype, "hex": raw[q:q + elen].hex()})
            q += elen
    elif off != len(raw):
        raise FrameError("body bytes after the value")
    rec["ext_present"] = has_ext
    rec["extensions"] = exts
    return rec, p


# --------------------------------------------------------------------------- #
# rejection, decode, stream, salvage                                           #
# --------------------------------------------------------------------------- #
def header_defect(buf: bytes):
    if len(buf) < HEADER_SIZE + TRAILER_SIZE or bytes(buf[:5]) != MAGIC:
        return {"error": "bad_magic"}
    if buf[5] != VERSION:
        return {"error": "unsupported_version", "version": buf[5]}
    for off in (14, 15):
        if buf[off] != 0:
            return {"error": "reserved_not_zero", "offset": off}
    rec_count = struct.unpack_from("<H", buf, 11)[0]
    if rec_count * MIN_FRAME > len(buf) - HEADER_SIZE - TRAILER_SIZE:
        return {"error": "record_count_overflow", "record_count": rec_count}
    expected = crc_header(buf)
    found = struct.unpack_from("<I", buf, len(buf) - TRAILER_SIZE)[0]
    if expected != found:
        return {"error": "trailer_crc_mismatch", "expected": expected, "found": found}
    return None


def header_fields(buf: bytes) -> dict:
    return {"stream_id": struct.unpack_from("<H", buf, 7)[0],
            "seq_no": struct.unpack_from("<H", buf, 9)[0],
            "revision": buf[13],
            "flags": {"stream_continues": bool(buf[6] & 0x01)},
            "record_count": struct.unpack_from("<H", buf, 11)[0]}


def decode_segment(buf: bytes, schema: dict, state: StreamState | None = None) -> dict:
    defect = header_defect(buf)
    if defect is not None:
        return defect
    hf = header_fields(buf)
    state = state if state is not None else StreamState()
    end = len(buf) - TRAILER_SIZE
    pos = HEADER_SIZE
    records = []
    for _ in range(hf["record_count"]):
        rec, pos = parse_frame(buf, pos, end, state, hf["stream_id"], hf["revision"], schema)
        state.apply(rec)
        records.append(rec)
    return {"magic_ok": True, "version": VERSION, "stream_id": hf["stream_id"],
            "seq_no": hf["seq_no"], "revision": hf["revision"], "flags": hf["flags"],
            "record_count": hf["record_count"], "records": records}


def entry_continues(entry: dict, header_bit: bool) -> bool:
    """decoder_appendix.md Runs: a JSON boolean `stream_continues` in the entry
    decides in place of the header bit; any other value leaves the header bit."""
    override = entry.get("stream_continues")
    return override if type(override) is bool else header_bit


def decode_stream(entries: list[dict], schema: dict) -> dict:
    """decoder_appendix.md --stream. `entries` are manifest entries with the
    segment bytes under "buf". Each stream has at most one current run, holding
    its state and the seq_no of the last segment taken into it."""
    runs: dict[int, dict] = {}
    docs = []
    for entry in entries:
        buf = entry["buf"]
        hf = header_fields(buf)
        sid = hf["stream_id"]
        run = runs.get(sid)
        if run is not None and hf["seq_no"] <= run["last_seq"]:
            docs.append(decode_segment(buf, schema, run["state"].copy()))
            continue
        if run is None:
            run = {"state": StreamState(), "last_seq": None}
            runs[sid] = run
        docs.append(decode_segment(buf, schema, run["state"]))
        run["last_seq"] = hf["seq_no"]
        if not entry_continues(entry, hf["flags"]["stream_continues"]):
            del runs[sid]
    return {"segments": docs}


def _parses(buf, pos, end, state, stream_id, revision, schema) -> bool:
    try:
        parse_frame(buf, pos, end, state, stream_id, revision, schema)
        return True
    except FrameError:
        return False


def salvage(buf: bytes, schema: dict) -> dict:
    defect = header_defect(buf)
    if len(buf) >= HEADER_SIZE:
        hf = header_fields(buf)
        sid, rev = hf["stream_id"], hf["revision"]
    else:
        sid, rev = 0, 0
    end = len(buf) - TRAILER_SIZE
    state = StreamState()
    records: list[dict] = []
    damaged: list[dict] = []
    pos = HEADER_SIZE
    while pos < end:
        try:
            rec, newpos = parse_frame(buf, pos, end, state, sid, rev, schema)
        except FrameError as exc:
            resync = next((i for i in range(pos + 1, end)
                           if buf[i] == SYNC and _parses(buf, i, end, state, sid, rev, schema)),
                          None)
            damaged.append({"from_offset": pos,
                            "resync_offset": end if resync is None else resync,
                            "reason": str(exc)})
            if resync is None:
                break
            pos = resync
            continue
        state.apply(rec)
        records.append(rec)
        pos = newpos
    return {"records": records, "damaged": damaged,
            "header_defect": defect["error"] if defect else None}


# --------------------------------------------------------------------------- #
# agent-visible data (SAMPLE_SEED: tables and catalog; CHALLENGE_SEED: the     #
# three stream 3 segment files)                                                #
# --------------------------------------------------------------------------- #
SAMPLE_SEED = 284611
CHALLENGE_SEED = SAMPLE_SEED ^ 0x5EED5EED
EVAL_SEED = 0x5641524345564C31

N_FIELDS = 2100
N_STREAMS = 40
N_CLEAN = 15200
N_REJECT = 2500
MASK = (1 << 64) - 1
IDENTITY_REVS = [0, 1, 2, 3]
NONIDENTITY_REVS = [4, 5, 6, 7]
EXT_TYPES = {1: "span", 2: "quality", 3: "source"}
DAMAGE_KINDS = ["bad_magic", "unsupported_version", "reserved_not_zero",
                "record_count_overflow", "trailer_crc_mismatch"]
_UNITS = ["celsius", "pascal", "volt", "ampere", "hertz", "percent", "count", "meter"]
_BASES = ["temp", "pressure", "voltage", "current", "freq", "load", "ticks", "phase",
          "level", "flow", "rms", "peak", "humid", "angle", "speed", "power"]


class Rng:
    __slots__ = ("s",)

    def __init__(self, seed: int) -> None:
        self.s = seed & MASK or 0x9E3779B97F4A7C15

    def nxt(self) -> int:
        x = self.s
        x ^= (x >> 12) & MASK
        x ^= (x << 25) & MASK
        x ^= (x >> 27) & MASK
        self.s = x & MASK
        return (self.s * 0x2545F4914F6CDD1D) & MASK

    def rint(self, lo: int, hi: int) -> int:
        return lo + self.nxt() % (hi - lo + 1)

    def pick(self, seq):
        return seq[self.nxt() % len(seq)]


def build_field_layouts():
    rng = Rng(SAMPLE_SEED ^ 0xF1E1D5)
    rows = []
    for cid in range(1, N_FIELDS + 1):
        name = f"{_BASES[cid % len(_BASES)]}_{cid:04d}"
        unit = _UNITS[rng.nxt() % len(_UNITS)]
        width = 4 if rng.nxt() % 2 else 2
        rows.append((cid, name, unit, width))
    return rows


def home_stream(cid: int) -> int:
    return (cid % N_STREAMS) + 1


def build_symbol_table(layouts):
    return [(home_stream(cid), cid, f"{name}@s{home_stream(cid)}")
            for (cid, name, unit, width) in layouts]


def build_revision_map():
    """Sections list only the key bytes a revision moves. A share of the moved
    bytes land on an id with the same home stream as the key byte, so on that
    stream the alias of the moved id and the alias of the key byte both exist."""
    revisions = {rev: {} for rev in IDENTITY_REVS}
    for rev in NONIDENTITY_REVS:
        rng = Rng(SAMPLE_SEED ^ (0xB0 + rev))
        moved = {}
        for raw in range(1, 256):
            target = rng.rint(1, N_FIELDS)
            keep = rng.nxt() % 4
            if raw % 8 == rev % 8:
                moved[raw] = raw + N_STREAMS * rng.rint(1, (N_FIELDS - raw) // N_STREAMS)
            elif keep and target != raw:
                moved[raw] = target
        revisions[rev] = moved
    return revisions


def build_schema():
    layouts = build_field_layouts()
    symrows = build_symbol_table(layouts)
    revisions = build_revision_map()
    schema = empty_schema()
    schema["id_to_name"] = {cid: name for (cid, name, unit, width) in layouts}
    schema["name_to_id"] = {name: cid for (cid, name, unit, width) in layouts}
    schema["id_to_unit"] = {cid: unit for (cid, name, unit, width) in layouts}
    schema["alias"] = {(sid, cid): alias for (sid, cid, alias) in symrows}
    schema["remap"] = {(rev, raw): tgt for rev, mp in revisions.items() for raw, tgt in mp.items()}
    return schema, layouts, symrows, revisions


_FORBIDDEN = (0xAA, 0x1B)
_SAFE = [b for b in range(0x80) if b not in _FORBIDDEN]


def _ext(rng):
    payload = bytes(rng.pick(_SAFE) for _ in range(rng.rint(1, 3)))
    return {"type": rng.pick([1, 2, 3, 7, 9]), "hex": payload.hex()}


def _clean_bytes(data):
    return all(b not in _FORBIDDEN for b in data)


def _safe_raw(rng, wide, unit):
    """Shipped catalog raw values: a count field may carry the high bit (read
    unsigned); every other field stays non negative."""
    width = 4 if wide else 2
    top = (1 << (8 * width)) - 1
    while True:
        if unit == "count":
            v = rng.rint(top // 2 + 1, top) if rng.nxt() % 2 else rng.rint(0, 30000)
        else:
            v = rng.rint(0, 2_000_000) if wide else rng.rint(0, 30000)
        if _clean_bytes(v.to_bytes(width, "little")):
            return v


def _safe_delta(rng):
    while True:
        d = rng.rint(-400, 400)
        if _clean_bytes(write_sleb128(d)):
            return d


def _safe_index(rng, hi):
    while True:
        i = rng.rint(0, hi)
        if i not in _FORBIDDEN:
            return i


def _key_unit(rec, revision):
    if rec["long_key"]:
        cid = SCHEMA["name_to_id"].get(rec["key_str"])
    else:
        cid = SCHEMA["remap"].get((revision, rec["raw_key"]), rec["raw_key"])
    return SCHEMA["id_to_unit"].get(cid)


def _same_key(a, b) -> bool:
    return (a["long_key"], a.get("key_str"), a.get("raw_key")) == \
           (b["long_key"], b.get("key_str"), b.get("raw_key"))


def _make_capture(rng, stream_id, revision, want_names):
    """One fresh single-segment capture (the catalog generator). A delta frame
    is written only as the first value setting frame or right after a raw or
    delta frame of the same key."""
    records = []
    count = 0
    last_setter = None
    plan = [("long", nm) for nm in want_names] + [("short", None)] * rng.rint(0, 2)
    for kind, name in plan:
        if kind == "long":
            rec = {"raw_key": None, "long_key": True, "key_str": name, "mode": "raw",
                   "wide": None, "extensions": []}
        else:
            rec = {"raw_key": rng.rint(1, 255), "long_key": False, "mode": "raw",
                   "wide": None, "extensions": []}
        mode = rng.pick(["raw", "delta", "dict"]) if count else rng.pick(["raw", "delta"])
        if mode == "delta" and last_setter is not None and not _same_key(last_setter, rec):
            mode = "raw"
        rec["mode"] = mode
        if rng.nxt() % 7 == 0:
            rec["extensions"] = [_ext(rng)]
        if mode == "raw":
            wide = bool(rng.nxt() % 2)
            rec["wide"] = wide
            rec["raw_value"] = _safe_raw(rng, wide, _key_unit(rec, revision))
        elif mode == "delta":
            d = _safe_delta(rng)
            rec["delta_raw"] = d
            rec["delta_raw_len"] = None
        else:
            rec["dict_index"] = _safe_index(rng, count - 1)
        if mode in ("raw", "delta"):
            last_setter = rec
        count += 1
        records.append(rec)
    if not records:
        records.append({"raw_key": 1, "long_key": False, "mode": "raw", "wide": False,
                        "raw_value": 0, "extensions": []})
    return {"stream_id": stream_id, "seq_no": 0, "revision": revision,
            "flags": {"stream_continues": False}, "records": records}


def _value_sum(doc) -> int:
    decoded = decode_segment(encode_segment(doc), SCHEMA)
    return sum(r["value"] for r in decoded["records"] if r["value"] is not None)


def _catalog_row(capture_id, doc, payload):
    return {"capture_id": capture_id, "stream_id": doc["stream_id"], "seq_no": 0,
            "revision": doc["revision"], "value_sum": _value_sum(doc), "hex": payload.hex()}


def _apply_damage(kind, payload):
    b = bytearray(payload)
    if kind == "bad_magic":
        b[0] ^= 0xFF
    elif kind == "unsupported_version":
        b[5] = 9
    elif kind == "reserved_not_zero":
        b[14] = 1
    elif kind == "record_count_overflow":
        struct.pack_into("<H", b, 11, 0xFFFF)
    elif kind == "trailer_crc_mismatch":
        b[-1] ^= 0xFF
    return bytes(b)


def build_catalog(layouts):
    rng = Rng(SAMPLE_SEED ^ 0x0C0FFEE)
    clean = []
    n = 0
    for (cid, name, unit, width) in layouts:
        hs = home_stream(cid)
        other = (hs % N_STREAMS) + 1
        for stream_id in (hs, other):
            n += 1
            doc = _make_capture(rng, stream_id, rng.pick(IDENTITY_REVS), [name])
            clean.append(_catalog_row(f"cap-{n:05d}", doc, encode_segment(doc)))
    while n < len(layouts) * 2 + 1500:
        n += 1
        doc = _make_capture(rng, rng.rint(1, N_STREAMS), rng.pick(IDENTITY_REVS), [])
        clean.append(_catalog_row(f"cap-{n:05d}", doc, encode_segment(doc)))
    names_all = [name for (_c, name, _u, _w) in layouts]
    while n < N_CLEAN:
        n += 1
        pick = [names_all[rng.nxt() % len(names_all)] for _ in range(rng.rint(1, 3))]
        doc = _make_capture(rng, rng.rint(1, N_STREAMS), rng.pick(IDENTITY_REVS), pick)
        clean.append(_catalog_row(f"cap-{n:05d}", doc, encode_segment(doc)))
    reject = []
    rrng = Rng(SAMPLE_SEED ^ 0xDEAD77)
    for i in range(1, N_REJECT + 1):
        doc = _make_capture(rrng, rrng.rint(1, N_STREAMS), rrng.pick(IDENTITY_REVS),
                            [names_all[rrng.nxt() % len(names_all)]])
        kind = rrng.pick(DAMAGE_KINDS)
        payload = _apply_damage(kind, encode_segment(doc))
        reject.append(_catalog_row(f"rej-{i:05d}", doc, payload))
    out = []
    ci = ri = 0
    mix = Rng(SAMPLE_SEED ^ 0x1337)
    while ci < len(clean) or ri < len(reject):
        if ri < len(reject) and (ci >= len(clean) or mix.nxt() % 7 == 0):
            out.append(reject[ri])
            ri += 1
        else:
            out.append(clean[ci])
            ci += 1
    return out


def _nonzero(rng, lo, hi):
    while True:
        v = rng.rint(lo, hi)
        if v:
            return v


def build_stream3(schema, revisions):
    """capture_alpha (rev 5, continues), capture_beta (rev 0, closes the run),
    capture_gamma (rev 2, a new run of the same stream). Every delta frame opens
    its run or sits right after a raw or delta frame of the same field."""
    rng = Rng(CHALLENGE_SEED)
    sid = 3
    rev5 = revisions[5]

    def plain(cid):
        return schema["id_to_unit"][cid] != "count" and home_stream(cid) != sid

    moved = sorted(k for k, c in rev5.items() if c != k and home_stream(c) != sid)
    unlisted = sorted(k for k in range(1, 256) if k not in rev5 and plain(k))
    plain_ids = [c for c in range(1, 256) if plain(c) and c not in (0x1B, 0xAA)]
    long_f = {"raw_key": None, "long_key": True, "key_str": schema["id_to_name"][42]}
    key_h = {"raw_key": rng.pick(plain_ids), "long_key": False}
    key_j = {"raw_key": rng.pick(plain_ids), "long_key": False}

    def rec(key, mode, **kw):
        return {**key, "mode": mode, "extensions": kw.pop("exts", []), **kw}

    alpha = [
        rec(long_f, "raw", wide=True, raw_value=rng.rint(0, 900_000)),
        rec(long_f, "delta", delta_raw=_nonzero(rng, -3000, 3000), delta_raw_len=None),
        rec({"raw_key": rng.pick(moved), "long_key": False}, "dict", dict_index=1),
        rec(long_f, "delta", delta_raw=_nonzero(rng, -3000, 3000), delta_raw_len=3),
        rec({"raw_key": rng.pick(unlisted), "long_key": False}, "raw", wide=False,
            raw_value=int.from_bytes(bytes([0xAA, 0x1B]), "little"),
            exts=[{"type": 9, "hex": "aa01"}]),
    ]
    beta = [
        rec(key_h, "raw", wide=False, raw_value=rng.rint(0, 30000)),
        rec({"raw_key": rng.pick(plain_ids), "long_key": False}, "dict", dict_index=2,
            exts=[{"type": 2, "hex": "0140"}]),
        rec(key_h, "delta", delta_raw=_nonzero(rng, -3000, 3000), delta_raw_len=None),
        rec(key_h, "delta", delta_raw=_nonzero(rng, -3000, 3000), delta_raw_len=None),
    ]
    gamma = [
        rec(key_j, "delta", delta_raw=27, delta_raw_len=None),
        rec(key_j, "delta", delta_raw=_nonzero(rng, -3000, 3000), delta_raw_len=None),
        rec({"raw_key": rng.pick(plain_ids), "long_key": False}, "dict", dict_index=1),
        rec(key_j, "delta", delta_raw=_nonzero(rng, -3000, 3000), delta_raw_len=None,
            exts=[{"type": 12, "hex": "07"}, {"type": 7, "hex": "1b00"}]),
        rec({"raw_key": None, "long_key": True, "key_str": "probe_vent_7"}, "raw", wide=False,
            raw_value=rng.rint(0, 30000)),
    ]
    segs = [(alpha, 0, 5, True), (beta, 1, 0, False), (gamma, 0, 2, False)]
    return [encode_segment({"stream_id": sid, "seq_no": seq, "revision": rev,
                            "flags": {"stream_continues": cont}, "records": recs})
            for recs, seq, rev, cont in segs]


STREAM3_FILES = ("capture_alpha.varc", "capture_beta.varc", "capture_gamma.varc")
STREAM3_MANIFEST = {"segments": [
    {"path": "/app/data/capture_alpha.varc"},
    {"path": " /app/data/capture_beta.varc", "stream_continues": "true",
     "note": "operator: keep stream 3 open"},
    {"path": "/app/data/capture_gamma.varc", "stream_continues": False},
]}


def _write_corpus(root: Path) -> None:
    """Write the agent-visible generated files into <root>/data (the hand
    written .md and .json files are not touched)."""
    data = Path(root) / "data"
    data.mkdir(parents=True, exist_ok=True)
    schema, layouts, symrows, revisions = build_schema()
    with (data / "capture_catalog.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for row in build_catalog(layouts):
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    with (data / "field_layouts.csv").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("canonical_id,name,unit,width\n")
        for (cid, name, unit, width) in layouts:
            fh.write(f"{cid},{name},{unit},{width}\n")
    with (data / "symbol_table.tsv").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("stream_id\tcanonical_id\talias\n")
        for (sid, cid, alias) in symrows:
            fh.write(f"{sid}\t{cid}\t{alias}\n")
    with (data / "revision_map.ini").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("; Field-id revision remap for short (one byte) keys.\n")
        fh.write("; Revisions 0 1 2 3 are identity. Revisions 4 5 6 7 move the key bytes\n")
        fh.write("; listed in their sections, one line raw_key = canonical_id per moved byte.\n")
        fh.write("; See revision_notes.md.\n")
        for rev in NONIDENTITY_REVS:
            fh.write(f"[revision_{rev}]\n")
            for raw in sorted(revisions[rev]):
                fh.write(f"{raw} = {revisions[rev][raw]}\n")
    for name, buf in zip(STREAM3_FILES, build_stream3(schema, revisions)):
        (data / name).write_bytes(buf)
    (data / "stream3_manifest.json").write_text(json.dumps(STREAM3_MANIFEST, indent=1) + "\n",
                                                encoding="utf-8")


SCHEMA, _LAYOUTS, _SYMROWS, _REVISIONS = build_schema()


# --------------------------------------------------------------------------- #
# running the agent's programs                                                 #
# --------------------------------------------------------------------------- #
_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_RUN_TIMEOUT = 20
_RUN_BUDGET = 2100.0
_STAGED: dict[str, Path | None] = {}
_CLOCK: dict[str, float] = {}
# rewardkit may run checks in parallel threads; agent runs are serialised so the
# kill-by-uid sweep after each run never hits another check's live process.
_RUN_LOCK = threading.RLock()


def _as_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _grant_read(path: Path) -> None:
    """Make a staged agent program readable for the dropped uid (TS-30): the
    agent's editor may write 0600; the verifier is root, so widening the copy
    and its folders changes no graded content."""
    path.chmod(0o644)
    for parent in path.parents:
        if parent == Path(tempfile.gettempdir()) or parent == parent.parent:
            break
        parent.chmod(parent.stat().st_mode | 0o555)


def _wrap(workspace, program: str, args: list[str]) -> list[str] | None:
    """Stage a readable copy of the agent program, then build the command.

    The agent's editor may leave /app/decode.py at mode 0600, so the verifier
    (root) copies it into a folder it made, chmods the copy 0644 and the folder
    0755, and runs the copy under _SETPRIV as nobody."""
    key = f"{workspace}/{program}"
    with _RUN_LOCK:
        return _wrap_locked(workspace, program, args, key)


def _wrap_locked(workspace, program: str, args: list[str], key: str) -> list[str] | None:
    if key not in _STAGED:
        src = Path(workspace) / program
        staged = None
        if src.is_file():
            folder = Path(tempfile.mkdtemp(prefix="varc-prog-"))
            folder.chmod(0o755)
            staged = folder / program
            shutil.copyfile(src, staged)
            _grant_read(staged)
        _STAGED[key] = staged
    staged = _STAGED[key]
    if staged is None:
        return None
    cmd = [sys.executable, "-I", str(staged), *args]
    return _SETPRIV + cmd if _as_root() else cmd


def _kill_leftovers(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if not _as_root():
        return
    import pwd
    uid = pwd.getpwnam("nobody").pw_uid
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / "status").read_text()
        except OSError:
            continue
        for line in status.splitlines():
            if line.startswith("Uid:") and int(line.split()[1]) == uid:
                try:
                    os.kill(int(entry.name), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass


def _run(cmd: list[str] | None, cwd: str) -> tuple[int, bytes] | None:
    if cmd is None:
        return None
    with _RUN_LOCK:
        return _run_locked(cmd, cwd)


def _run_locked(cmd: list[str], cwd: str) -> tuple[int, bytes] | None:
    start = _CLOCK.setdefault("start", time.monotonic())
    if time.monotonic() - start > _RUN_BUDGET:
        return None
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL, cwd=cwd, env=_ENV,
                            start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=_RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        _kill_leftovers(proc.pid)
        proc.communicate()
        return None
    _kill_leftovers(proc.pid)
    return proc.returncode, out


def _json_of(result) -> Any:
    if result is None or result[0] != 0:
        return None
    try:
        return json.loads(result[1].decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def _input_dir() -> Path:
    folder = Path(tempfile.mkdtemp(prefix="varc-in-"))
    folder.chmod(0o755)
    return folder


def _put(folder: Path, name: str, data: bytes) -> Path:
    path = folder / name
    path.write_bytes(data)
    path.chmod(0o644)
    return path


def _decode(workspace, buf: bytes, name: str = "segment.varc", flag: str | None = None):
    folder = _input_dir()
    path = _put(folder, name, buf)
    args = [flag, str(path)] if flag else [str(path)]
    out = _json_of(_run(_wrap(workspace, "decode.py", args), str(folder)))
    shutil.rmtree(folder, ignore_errors=True)
    return out


def _manifest_json(folder: Path, entries: list[dict]) -> Path:
    listed = []
    for i, entry in enumerate(entries):
        path = str(_put(folder, f"part_{i:02d}.varc", entry["buf"]))
        item = {"path": f"{entry['pad']}{path}{entry['pad']}" if entry.get("pad") else path}
        for key in ("stream_continues", "note"):
            if key in entry:
                item[key] = entry[key]
        listed.append(item)
    return _put(folder, "manifest.json", json.dumps({"segments": listed}).encode())


def _stream(workspace, entries: list[dict]):
    folder = _input_dir()
    manifest = _manifest_json(folder, entries)
    out = _json_of(_run(_wrap(workspace, "decode.py", ["--stream", str(manifest)]), str(folder)))
    shutil.rmtree(folder, ignore_errors=True)
    return out


def _encode(workspace, doc: dict) -> bytes | None:
    folder = _input_dir()
    folder.chmod(0o1777)
    src = _put(folder, "document.json", json.dumps(doc).encode())
    target = folder / "rebuilt.varc"
    result = _run(_wrap(workspace, "encode.py", [str(src), str(target)]), str(folder))
    data = target.read_bytes() if result is not None and result[0] == 0 and target.is_file() else None
    shutil.rmtree(folder, ignore_errors=True)
    return data


def _out_json(workspace, name: str):
    try:
        return json.loads((Path(workspace) / "out" / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _diff(expected, actual, path: str = "$") -> str | None:
    """First place where `actual` fails to carry `expected` (same rule as
    _matches): expected keys present with equal values and types; extra keys in
    the agent's objects are ignored."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return f"{path}: expected an object, got {type(actual).__name__}"
        for key, want in expected.items():
            if key not in actual:
                return f"{path}.{key}: missing"
            found = _diff(want, actual[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return f"{path}: expected a list, got {type(actual).__name__}"
        if len(actual) != len(expected):
            return f"{path}: expected {len(expected)} items, got {len(actual)}"
        for i, (want, got) in enumerate(zip(expected, actual)):
            found = _diff(want, got, f"{path}[{i}]")
            if found:
                return found
        return None
    if isinstance(expected, bool) or expected is None:
        return None if actual is expected else f"{path}: expected {expected!r}, got {actual!r}"
    if isinstance(expected, int):
        ok = isinstance(actual, int) and not isinstance(actual, bool) and actual == expected
        return None if ok else f"{path}: expected {expected!r}, got {actual!r}"
    ok = type(actual) is type(expected) and actual == expected
    return None if ok else f"{path}: expected {expected!r}, got {actual!r}"


def _matches(expected, actual) -> bool:
    return _diff(expected, actual) is None


class _Mismatch(Exception):
    """A graded value differs; the message names where."""


_FAILURES: dict[str, str] = {}


def _note(name: str, message: str) -> None:
    """Print why a check failed (or why a penalty fired) to the verifier's
    standard output, so a crash reads apart from a wrong value."""
    text = message[:400]
    _FAILURES[name] = text
    print(f"[check] {name}: {text}", flush=True)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise _Mismatch(message)


def _same(expected, actual, what: str) -> None:
    _require(actual is not None, f"{what}: the program exited non zero or printed no JSON")
    where = _diff(expected, actual)
    _require(where is None, f"{what}: {where}")


def _holds(name: str, fn) -> bool:
    try:
        fn()
        return True
    except _Mismatch as exc:
        _note(name, str(exc))
    except Exception as exc:
        _note(name, f"grader error {type(exc).__name__}: {exc}")
    return False


def _fires(name: str, fn) -> bool:
    """Negative checks: True means the penalised act happened."""
    try:
        fired = bool(fn())
    except Exception as exc:
        _note(name, f"stood down, grader error {type(exc).__name__}: {exc}")
        return False
    if fired:
        _note(name, "penalty fired")
    return fired


_CACHE: dict[str, Any] = {}


def _fix(name: str, builder):
    if name not in _CACHE:
        _CACHE[name] = builder()
    return _CACHE[name]


# --------------------------------------------------------------------------- #
# hidden evaluation inputs (drawn from EVAL_SEED at grade time)                #
# --------------------------------------------------------------------------- #
_OPAQUE = [7, 9, 12, 40, 200]
_STEMS = ["probe", "spare", "aux", "bench", "trial"]
_COUNT_IDS = sorted(c for c in range(1, 256) if SCHEMA["id_to_unit"][c] == "count")
_PLAIN_IDS = sorted(c for c in range(1, 256) if SCHEMA["id_to_unit"][c] != "count")


def _aliased_ids(sid: int) -> list[int]:
    return [c for c in range(1, N_FIELDS + 1) if home_stream(c) == sid]


def _pair_keys(rev: int, sid: int) -> list[int]:
    """Key bytes that revision `rev` moves onto an id aliased on `sid` while the
    key byte's own id is aliased on `sid` too."""
    return sorted(k for k, c in _REVISIONS[rev].items()
                  if home_stream(c) == sid and home_stream(k) == sid)


def _count_keys(rev: int) -> list[int]:
    return [k for k in range(1, 256)
            if SCHEMA["id_to_unit"].get(_REVISIONS[rev].get(k, k)) == "count"]


def _short(key: int) -> dict:
    return {"raw_key": key, "long_key": False}


def _long(name: str) -> dict:
    return {"raw_key": None, "long_key": True, "key_str": name}


class _Gen:
    def __init__(self, seed: int) -> None:
        self.r = Rng(seed)
        self.pool: list[dict] = []
        self.reset_rate = 20

    def payload(self, lo=1, hi=4) -> str:
        pool = [0xAA, 0x1B, 0x00, 0x7F, 0x80, 0xFF, 0x20, 0x8A, 0x3B]
        out = bytes(self.r.pick(pool) if self.r.nxt() % 2 else self.r.rint(0, 255)
                    for _ in range(self.r.rint(lo, hi)))
        return out.hex()

    def exts(self) -> list[dict]:
        r = self.r
        roll = r.nxt() % 6
        if roll == 0:
            hi, lo = r.pick(_OPAQUE[2:]), r.pick(_OPAQUE[:2])
            return [{"type": hi, "hex": self.payload()}, {"type": lo, "hex": self.payload()}]
        if roll == 1:
            return [{"type": r.rint(1, 3), "hex": self.payload()}]
        if roll == 2:
            return [{"type": r.pick(_OPAQUE), "hex": self.payload(0, 3)}]
        return []

    def key(self, sid: int, rev: int) -> dict:
        r = self.r
        if self.pool and r.nxt() % 3 == 0:
            return dict(r.pick(self.pool))
        roll = r.nxt() % 12
        if roll == 0:
            return _long(f"{r.pick(_STEMS)}_{r.rint(10, 99)}{chr(97 + r.rint(0, 25))}")
        if roll == 1:
            cid = r.pick(_aliased_ids(sid)) if r.nxt() % 2 else r.rint(1, N_FIELDS)
            return _long(SCHEMA["id_to_name"][cid])
        if roll in (2, 3):
            return _short(r.pick(_count_keys(rev)))
        if rev >= 4 and roll < 8:
            pairs = _pair_keys(rev, sid)
            if pairs and r.nxt() % 2:
                return _short(r.pick(pairs))
            moved = sorted(_REVISIONS[rev])
            unlisted = [k for k in range(1, 256) if k not in _REVISIONS[rev]]
            return _short(r.pick(moved if r.nxt() % 2 else unlisted))
        return _short(r.rint(1, 255))

    def raw_value(self, wide: bool, unit) -> int:
        bits = 32 if wide else 16
        if unit == "count":
            top = (1 << bits) - 1
            return self.r.rint(top // 2 + 1, top) if self.r.nxt() % 3 else self.r.rint(0, top // 2)
        half = 1 << (bits - 1)
        return self.r.rint(-half, half - 1)

    def record(self, mode: str, sid: int, rev: int, nres: int, **kw) -> dict:
        r = self.r
        rec = dict(kw.pop("key", None) or self.key(sid, rev))
        if mode in ("raw", "delta") and len(self.pool) < 4 and not any(
                _same_key(rec, p) for p in self.pool):
            self.pool.append(dict(rec))
        rec["mode"] = mode
        rec["wide"] = None
        if mode == "raw":
            wide = kw.get("wide", bool(r.nxt() % 2))
            rec["wide"] = wide
            rec["raw_value"] = kw.get("value", self.raw_value(wide, _key_unit(rec, rev)))
        elif mode == "delta":
            d = kw.get("value", _nonzero(r, -9000, 9000))
            rec["delta_raw"] = d
            extra = kw.get("pad", r.rint(1, 3) if r.nxt() % 4 == 0 else 0)
            rec["delta_raw_len"] = len(write_sleb128(d)) + extra if extra else None
        elif mode == "dict":
            rec["dict_index"] = kw.get("index", r.rint(0, min(nres - 1, 60)))
        rec["extensions"] = kw.get("exts", self.exts() if mode != "reset" or r.nxt() % 3 == 0
                                   else [])
        return rec

    def mode(self, nres: int, reset_ok: bool) -> str:
        roll = self.r.nxt() % 20
        if reset_ok and self.r.nxt() % self.reset_rate == 0:
            return "reset"
        if nres == 0:
            return "raw" if roll % 2 else "delta"
        return ["raw", "delta", "delta", "dict"][roll % 4]

    def records(self, sid: int, rev: int, nres: int, count: int, lead=(), reset_ok=True):
        recs = []
        for i in range(count):
            mode = lead[i] if i < len(lead) else self.mode(nres, reset_ok)
            if mode == "dict" and nres == 0:
                mode = "delta"
            recs.append(self.record(mode, sid, rev, nres))
            nres = 0 if mode == "reset" else nres + 1
        return recs, nres


def _seg(sid, seq, rev, cont, records) -> bytes:
    return encode_segment({"stream_id": sid, "seq_no": seq, "revision": rev,
                           "flags": {"stream_continues": cont}, "records": records})


_IGNORED_OVERRIDES = ["true", "false", " TRUE ", "False", 1, 0, None]


def _valid(entries: list[dict]) -> list[dict]:
    """Keep the entries the reference decodes cleanly in order (a resend copied
    from before a reset can point a dict index past the list; it is dropped)."""
    kept: list[dict] = []
    for entry in entries:
        try:
            decode_stream(kept + [entry], SCHEMA)
        except FrameError:
            continue
        kept.append(entry)
    return kept


def _manifest(g: _Gen, sids: list[int], count: int, *, revs=tuple(range(8)), resend=5,
              overrides=True, close=4, pad: str | None = None, reset_ok=True) -> list[dict]:
    """A hand-kept manifest: interleaved streams, runs that close and reopen,
    resent segments, and stream_continues overrides of every JSON type."""
    runs: dict[int, dict] = {}
    entries: list[dict] = []
    for _ in range(count):
        sid = g.r.pick(sids)
        run = runs.get(sid)
        if run is not None and resend and g.r.nxt() % resend == 0:
            entries.append({"buf": g.r.pick(run["taken"])})
            continue
        fresh = run is None
        seq = 0 if fresh else run["seq"] + (1 if g.r.nxt() % 5 else 2)
        rev = g.r.pick(list(revs))
        nres = 0 if fresh else run["nres"]
        lead = ("delta", "raw") if fresh else (("delta", "dict") if g.r.nxt() % 2 else
                                               ("dict", "delta"))
        recs, nres = g.records(sid, rev, nres, g.r.rint(4, 7), lead=lead, reset_ok=reset_ok)
        header_bit = g.r.nxt() % close != 0
        entry: dict[str, Any] = {}
        roll = g.r.nxt() % 6 if overrides else 9
        if roll == 0:
            entry["stream_continues"] = not header_bit
        elif roll == 1:
            entry["stream_continues"] = header_bit
        elif roll in (2, 3):
            entry["stream_continues"] = g.r.pick(_IGNORED_OVERRIDES)
        if pad and g.r.nxt() % 2:
            entry["pad"] = pad
        entry["buf"] = _seg(sid, seq, rev, header_bit, recs)
        if fresh:
            run = runs[sid] = {"nres": 0, "seq": 0, "taken": []}
        run.update(nres=nres, seq=seq)
        run["taken"].append(entry["buf"])
        if not entry_continues(entry, header_bit):
            del runs[sid]
        entries.append(entry)
    return _valid(entries)


def _streams(g: _Gen, n: int) -> list[int]:
    out: list[int] = []
    while len(out) < n:
        s = g.r.rint(1, N_STREAMS)
        if s not in out:
            out.append(s)
    return out


def fx_stream_interleaved():
    g = _Gen(EVAL_SEED ^ 0x11)
    return _manifest(g, _streams(g, 2), 14)


def fx_stream_new_runs():
    g = _Gen(EVAL_SEED ^ 0x22)
    return _manifest(g, _streams(g, 2), 14, close=2, pad="  ")


def fx_stream_remap_runs():
    g = _Gen(EVAL_SEED ^ 0x44)
    rev = g.r.rint(4, 7)
    key = g.r.pick(sorted(k for k in _REVISIONS[rev] if k % 8 == rev % 8))
    sid = home_stream(key)
    target = _REVISIONS[rev][key]
    g.pool = [_short(key), _long(SCHEMA["id_to_name"][target])]
    return _manifest(g, [sid], 8, revs=(rev, rev, 0, g.r.rint(4, 7)), resend=0)


def fx_stream_reset_runs():
    g = _Gen(EVAL_SEED ^ 0x55)
    g.reset_rate = 4
    return _manifest(g, _streams(g, 2), 14, resend=6)


def fx_stream_mix_a():
    g = _Gen(EVAL_SEED ^ 0x66)
    return _manifest(g, _streams(g, 4), 22)


def fx_stream_mix_b():
    g = _Gen(EVAL_SEED ^ CHALLENGE_SEED)
    return _manifest(g, _streams(g, 4), 22, resend=4, close=3)


def fx_single_remapped_modes():
    g = _Gen(EVAL_SEED ^ 0x77)
    rev = g.r.rint(4, 7)
    key = g.r.pick(sorted(k for k in _REVISIONS[rev] if k % 8 == rev % 8))
    sid = home_stream(key)
    pairs = _pair_keys(rev, sid)
    unlisted = [k for k in range(1, 256) if k not in _REVISIONS[rev]]
    long_alias = _long(SCHEMA["id_to_name"][g.r.pick(_aliased_ids(sid))])
    plan = [
        ("raw", dict(key=long_alias, wide=True)),
        ("delta", dict(key=_short(g.r.pick(pairs)), pad=2)),
        ("dict", dict(index=0)),
        ("raw", dict(key=_short(g.r.pick(_count_keys(rev))), wide=False)),
        ("delta", dict(key=_short(g.r.pick(unlisted)))),
        ("raw", dict(key=_short(g.r.pick(unlisted)), wide=False, value=-g.r.rint(1, 32768))),
        ("dict", dict(index=3)),
        ("delta", dict(key=long_alias)),
        ("reset", dict()),
        ("delta", dict(key=_short(g.r.pick(pairs)), pad=1)),
        ("raw", dict(key=_short(g.r.pick(_count_keys(rev))), wide=True)),
        ("dict", dict(index=1)),
        ("delta", dict(key=_long("spare_41q"))),
        ("delta", dict(key=_short(g.r.pick(pairs)))),
    ]
    recs = [g.record(mode, sid, rev, 8, **kw) for mode, kw in plan]
    return _seg(sid, 0, rev, bool(g.r.nxt() % 2), recs)


def fx_single_escapes_ext():
    g = _Gen(EVAL_SEED ^ 0x88)
    sid, rev = g.r.rint(1, N_STREAMS), g.r.rint(0, 7)
    recs = [g.record("raw", sid, rev, 0, wide=False,
                     value=struct.unpack("<h", bytes([0xAA, 0x1B]))[0], exts=[])]
    for i in range(1, 30):
        recs.append(g.record(g.r.pick(["raw", "delta"]), sid, rev, i, exts=[]))
    recs += [
        g.record("delta", sid, rev, 30, value=170, pad=0,
                 exts=[{"type": 12, "hex": "aa1baa"}, {"type": 7, "hex": "1b"}]),
        g.record("dict", sid, rev, 31, index=0x1B, exts=[{"type": 2, "hex": "aa"},
                                                         {"type": 40, "hex": ""}]),
        g.record("raw", sid, rev, 32, wide=True, key=_short(g.r.pick(_count_keys(rev))),
                 value=struct.unpack("<i", bytes([0x1B, 0x00, 0xAA, 0x90]))[0],
                 exts=[{"type": 200, "hex": "1b1b"}, {"type": 9, "hex": "00aa"}]),
        g.record("delta", sid, rev, 33, value=27, pad=2, exts=[]),
        g.record("raw", sid, rev, 34, wide=False,
                 value=struct.unpack("<h", bytes([0x05, 0xAA]))[0], exts=[]),
        g.record("raw", sid, rev, 35, wide=False, value=7, exts=[]),
    ]
    return _seg(sid, 0, rev, False, recs)


def _frame_offsets(buf: bytes) -> list[tuple[int, int, int]]:
    """(frame start, fchk offset, body_len offset) for each frame of a clean segment."""
    end = len(buf) - TRAILER_SIZE
    pos = HEADER_SIZE
    out = []
    while pos < end:
        sel = buf[pos + 1]
        p = pos + 2
        if sel & 0x08:
            klen, p = read_uvarint(buf, p, end)
            p += klen
        else:
            p += 1
        fchk_at = p
        bl, q = read_uvarint(buf, p + 1, end)
        out.append((pos, fchk_at, p + 1))
        pos = q + bl
    return out


def _damage(buf: bytes, hits: list[tuple[int, str]]) -> bytes:
    b = bytearray(buf)
    offsets = _frame_offsets(buf)
    for ordinal, kind in hits:
        start, fchk_at, bl_at = offsets[ordinal]
        if kind == "fchk":
            b[fchk_at] ^= 0x5A
        elif kind == "selector":
            b[start + 1] |= 0x20
        elif kind == "length":
            b[bl_at] = min(b[bl_at] + 3, 0x7F) if b[bl_at] < 0x7F else b[bl_at]
    return bytes(b)


def fx_salvage_state():
    g = _Gen(EVAL_SEED ^ 0x99)
    sid, rev = g.r.rint(1, N_STREAMS), g.r.rint(0, 7)
    modes = ["raw", "delta", "raw", "delta", "delta", "dict", "delta", "raw", "delta",
             "dict", "delta", "delta"]
    recs = []
    for i, mode in enumerate(modes):
        idx = 0 if mode == "dict" else None
        recs.append(g.record(mode, sid, rev, i, exts=[], **({"index": idx} if idx is not None
                                                             else {})))
    clean = _seg(sid, 0, rev, False, recs)
    return _damage(clean, [(3, "fchk"), (7, "selector"), (8, "length")])


def fx_salvage_mix():
    g = _Gen(EVAL_SEED ^ 0xAA)
    sid, rev = g.r.rint(1, N_STREAMS), g.r.rint(4, 7)
    recs, _n = g.records(sid, rev, 0, 24, lead=("raw", "delta"))
    for i in (5, 11, 17):
        recs[i] = dict(recs[i], raw_key=0xAA, long_key=False)
        recs[i].pop("key_str", None)
    clean = _seg(sid, 0, rev, True, recs)
    b = bytearray(_damage(clean, [(4, "length"), (12, "fchk"), (23, "fchk")]))
    b[14] = 1
    return bytes(b)


def _single(seed: int, cont: bool) -> bytes:
    g = _Gen(seed)
    sid, rev = g.r.rint(1, N_STREAMS), g.r.rint(0, 7)
    recs, _n = g.records(sid, rev, 0, g.r.rint(8, 14), lead=("raw", "delta"))
    for i in range(2, len(recs), 4):
        if recs[i]["mode"] == "delta":
            recs[i]["delta_raw_len"] = len(write_sleb128(recs[i]["delta_raw"])) + 2
    recs[1]["extensions"] = [{"type": 40, "hex": g.payload()}, {"type": 9, "hex": "aa"}]
    recs.append(g.record("raw", sid, rev, 0, key=_short(g.r.pick(_count_keys(rev))),
                         wide=bool(g.r.nxt() % 2), value=-g.r.rint(1, 30000)))
    return _seg(sid, g.r.rint(0, 9), rev, cont, recs)


def fx_encode_unmodified():
    return [_single(EVAL_SEED ^ 0xB1, True), _single(EVAL_SEED ^ 0xB2, False),
            _single(EVAL_SEED ^ 0xB3, True)]


def _edited(buf: bytes, edit, hand=None) -> tuple[dict, bytes]:
    """Decode a real segment, edit it, and return (document handed to encode.py,
    bytes the reference encoder writes for it)."""
    doc = decode_segment(buf, SCHEMA)
    touched = edit(doc)
    expected = encode_segment(doc)
    handed = decode_segment(expected, SCHEMA)
    for i in touched:
        if handed["records"][i]["mode"] == "delta":
            handed["records"][i]["delta_raw_len"] = None
    handed["record_count"] = doc["record_count"]
    if hand:
        hand(handed, touched)
    return handed, expected


def _first(doc, pred) -> int:
    return next(i for i, r in enumerate(doc["records"]) if pred(r))


def _hand_edit(handed: dict, touched: list[int]) -> None:
    """An operator's edit: the changed delta's length written as text, every
    extension hex in capitals with spaces around it."""
    for i in touched:
        if handed["records"][i]["mode"] == "delta":
            handed["records"][i]["delta_raw_len"] = str(len(write_sleb128(
                handed["records"][i]["delta_raw"])) + 2)
    for rec in handed["records"]:
        for ext in rec["extensions"]:
            ext["hex"] = f" {ext['hex'].upper()} "


def fx_encode_edited():
    def change_overlong(doc):
        i = _first(doc, lambda r: r["mode"] == "delta"
                   and r["delta_raw_len"] > len(write_sleb128(r["delta_raw"])))
        doc["records"][i]["delta_raw"] += 5
        doc["records"][i]["delta_raw_len"] = None
        return [i]

    def grow_delta(doc):
        i = _first(doc, lambda r: r["mode"] == "delta")
        doc["records"][i]["delta_raw"] = 9_000_000
        doc["records"][i]["delta_raw_len"] = None
        return [i]

    def edit_beside_ext(doc):
        rec = doc["records"][1]
        if rec["mode"] == "raw":
            rec["raw_value"] = -rec["raw_value"] - 1
        elif rec["mode"] == "delta":
            rec["delta_raw"] = rec["delta_raw"] * 3 + 1
            rec["delta_raw_len"] = None
        return [1]

    return [_edited(_single(EVAL_SEED ^ 0xC1, False), change_overlong, _hand_edit),
            _edited(_single(EVAL_SEED ^ 0xC2, True), grow_delta),
            _edited(_single(EVAL_SEED ^ 0xC3, False), edit_beside_ext, _hand_edit)]


def fx_encode_new_record():
    def insert(doc):
        recs = doc["records"]
        new = [
            {"raw_key": 0x1B, "long_key": False, "mode": "delta", "wide": None,
             "delta_raw": -170, "delta_raw_len": None, "ext_present": False, "extensions": []},
            {"raw_key": 0xAA, "long_key": False, "mode": "dict", "wide": None, "dict_index": 1,
             "ext_present": True, "extensions": [{"type": 12, "hex": "aa"},
                                                 {"type": 3, "hex": "1b20"}]},
            {"raw_key": None, "long_key": True, "key_str": "aux_77k", "mode": "raw",
             "wide": True, "raw_value": -2_000_000_001, "ext_present": True,
             "extensions": [{"type": 200, "hex": "0001"}]},
            {"raw_key": _COUNT_IDS[0], "long_key": False, "mode": "raw", "wide": False,
             "raw_value": 65000, "ext_present": False, "extensions": []},
        ]
        at = 3
        recs[at:at] = new
        return [at]

    def insert_reset(doc):
        recs = doc["records"]
        recs[len(recs):] = [{"raw_key": 9, "long_key": False, "mode": "reset", "wide": None,
                      "ext_present": False, "extensions": []},
                     {"raw_key": 9, "long_key": False, "mode": "delta", "wide": None,
                      "delta_raw": 64, "delta_raw_len": None, "ext_present": False,
                      "extensions": []}]
        return [len(recs) - 1]

    return [_edited(_single(EVAL_SEED ^ 0xD1, True), insert),
            _edited(_single(EVAL_SEED ^ 0xD2, False), insert_reset)]


# --------------------------------------------------------------------------- #
# rule inputs: each built so only one rule decides the observable              #
# --------------------------------------------------------------------------- #
def fx_rule_count_raw():
    """Raw records only, identity revision: count and other fields, values with
    the top bit of their value bytes set."""
    g = _Gen(EVAL_SEED ^ 0x1C1)
    sid, rev = g.r.rint(1, N_STREAMS), g.r.rint(0, 3)
    recs = []
    for i in range(10):
        key = _short(g.r.pick(_COUNT_IDS if i % 2 else _PLAIN_IDS))
        wide = bool(g.r.nxt() % 2)
        top = 1 << (31 if wide else 15)
        recs.append(g.record("raw", sid, rev, 0, key=key, wide=wide, exts=[],
                             value=-g.r.rint(1, top)))
    return _seg(sid, 0, rev, False, recs)


def fx_rule_field_cumulator():
    """Raw and delta records of three plain fields taking turns."""
    g = _Gen(EVAL_SEED ^ 0x1C2)
    sid, rev = g.r.rint(1, N_STREAMS), g.r.rint(0, 3)
    keys = [_short(k) for k in sorted({g.r.pick(_PLAIN_IDS) for _ in range(6)})[:3]]
    plan = [("raw", 0), ("raw", 1), ("delta", 0), ("delta", 2), ("delta", 1), ("raw", 2),
            ("delta", 0), ("delta", 2), ("delta", 1), ("delta", 1), ("delta", 0)]
    recs = []
    for mode, k in plan:
        kw = {"value": g.r.rint(0, 30000), "wide": False} if mode == "raw" else {}
        recs.append(g.record(mode, sid, rev, 0, key=keys[k], exts=[], **kw))
    return _seg(sid, 0, rev, False, recs)


def _one_field_segment(g, sid, seq, cont, key, count, lead_dict=False):
    recs = []
    for i in range(count):
        mode = "dict" if lead_dict and i == 1 else ("delta" if i % 3 else "raw")
        kw = {"index": 0} if mode == "dict" else (
            {"value": g.r.rint(0, 30000), "wide": False} if mode == "raw" else {})
        recs.append(g.record(mode, sid, 1, 1, key=key, exts=[], **kw))
    recs[0] = g.record("delta", sid, 1, 0, key=key, exts=[])
    return _seg(sid, seq, 1, cont, recs)


def fx_rule_resend():
    """One stream, one plain field: a run with two resent segments in it."""
    g = _Gen(EVAL_SEED ^ 0x1C3)
    sid = g.r.rint(1, N_STREAMS)
    key = _short(g.r.pick(_PLAIN_IDS))
    s0 = _one_field_segment(g, sid, 0, True, key, 5)
    s1 = _one_field_segment(g, sid, 1, True, key, 5, lead_dict=True)
    s2 = _one_field_segment(g, sid, 2, True, key, 5, lead_dict=True)
    s3 = _one_field_segment(g, sid, 3, False, key, 5, lead_dict=True)
    return [{"buf": s0}, {"buf": s1}, {"buf": s1}, {"buf": s2}, {"buf": s0}, {"buf": s3}]


def fx_rule_boolean_override():
    """One stream, one plain field: overrides as JSON booleans and as other types."""
    g = _Gen(EVAL_SEED ^ 0x1C4)
    sid = g.r.rint(1, N_STREAMS)
    key = _short(g.r.pick(_PLAIN_IDS))
    seg = [_one_field_segment(g, sid, i, cont, key, 4, lead_dict=i > 0)
           for i, cont in enumerate((False, True, True, False, True))]
    return [{"buf": seg[0], "stream_continues": True},
            {"buf": seg[1], "stream_continues": "false"},
            {"buf": seg[2], "stream_continues": 0},
            {"buf": seg[3], "stream_continues": " TRUE "},
            {"buf": _one_field_segment(g, sid, 0, True, key, 4), "stream_continues": False},
            {"buf": _one_field_segment(g, sid, 1, False, key, 4)}]


def fx_rule_length_integer():
    """An edited document of delta records: delta_raw_len as an integer, as
    null and as text."""
    g = _Gen(EVAL_SEED ^ 0x1C5)
    sid = g.r.rint(1, N_STREAMS)
    key = _short(g.r.pick(_PLAIN_IDS))
    recs = [g.record("delta", sid, 1, 0, key=key, exts=[], value=g.r.rint(-60, 60))
            for _ in range(6)]
    doc = decode_segment(_seg(sid, 0, 1, False, recs), SCHEMA)
    lengths = [3, None, "3", 4, " 2 ", None]
    for rec, length in zip(doc["records"], lengths):
        rec["delta_raw_len"] = length
    return doc, encode_segment(doc)


def _flip(entries: list[dict], at: int) -> list[dict]:
    twin = [dict(e) for e in entries]
    twin[at]["stream_continues"] = not twin[at]["stream_continues"]
    return twin


def fx_mutation_override():
    """Two streams; one JSON boolean override on stream A decides whether A's
    last segment continues the run. The pair differs only in that boolean."""
    g = _Gen(EVAL_SEED ^ 0x1D1)
    a, b = _streams(g, 2)
    key = _short(g.r.pick(_PLAIN_IDS))
    a0 = _one_field_segment(g, a, 0, True, key, 5)
    a1 = _one_field_segment(g, a, 1, True, key, 5)
    a2 = _one_field_segment(g, a, 2, False, key, 5)
    other = _manifest(g, [b], 4, resend=0, overrides=False, close=9)
    base = [{"buf": a0}, other[0], {"buf": a1, "stream_continues": True}, other[1],
            {"buf": a2}] + other[2:]
    return base, _flip(base, 2), a


def fx_mutation_count():
    """One raw frame moved from a plain field onto a count field (key byte
    only); the records it feeds follow."""
    g = _Gen(EVAL_SEED ^ 0x1D2)
    sid = g.r.rint(1, N_STREAMS)
    plain_key, count_key = g.r.pick(_PLAIN_IDS), g.r.pick(_COUNT_IDS)
    other = _short(g.r.pick([k for k in _PLAIN_IDS if k != plain_key]))

    def build(raw_key):
        recs = [g.record("raw", sid, 1, 0, key=other, wide=False, exts=[], value=1200),
                g.record("delta", sid, 1, 1, key=_short(count_key), exts=[], value=40)]
        recs.append(g.record("raw", sid, 1, 2, key=_short(raw_key), wide=False, exts=[],
                             value=-g.r.rint(1, 30000)))
        recs += [g.record("dict", sid, 1, 3, index=0, exts=[], key=other),
                 g.record("delta", sid, 1, 4, key=_short(count_key), exts=[], value=-7),
                 g.record("delta", sid, 1, 5, key=other, exts=[], value=3)]
        return recs

    plan_state = g.r.s
    base = _seg(sid, 0, 1, False, build(plain_key))
    g.r.s = plan_state
    moved = _seg(sid, 0, 1, False, build(count_key))
    return base, moved, 2


def _base(seed: int) -> bytes:
    """The gate segment for the rejection checks: one plain field under an
    identity revision, so only the basic frame rules decide its document."""
    g = _Gen(seed)
    sid, rev = g.r.rint(1, N_STREAMS), g.r.rint(0, 3)
    key = _short(g.r.pick(_PLAIN_IDS))
    modes = ("raw", "delta", "dict", "delta", "raw", "dict", "delta")
    recs = [g.record(m, sid, rev, i, key=key, exts=[],
                     **({"index": 0} if m == "dict" else
                        {"value": g.r.rint(0, 30000), "wide": False} if m == "raw" else {}))
            for i, m in enumerate(modes)]
    return _seg(sid, g.r.rint(0, 5), rev, False, recs)


def _mutate(buf: bytes, edits: dict[int, int], fix_crc: bool = False) -> bytes:
    b = bytearray(buf)
    for off, val in edits.items():
        b[off] = val
    if fix_crc:
        struct.pack_into("<I", b, len(b) - TRAILER_SIZE, crc_header(b))
    return bytes(b)


def fx_isolated():
    base = _base(EVAL_SEED ^ 0xE1)
    resets = bytes([SYNC, 0x03, 0x05, 0x00, 0x00]) * 6
    exact = (build_header(9, 0, 6, 1, False) + resets)
    exact += struct.pack("<I", crc_header(exact))
    over = bytearray(exact)
    struct.pack_into("<H", over, 11, 7)
    struct.pack_into("<I", over, len(over) - 4, crc_header(over))
    return {
        "base": base,
        "magic_version": _mutate(base, {0: base[0] ^ 0x0F, 5: 3}),
        "short": base[:HEADER_SIZE + 2],
        "version_reserved": _mutate(base, {5: 7, 14: 2}),
        "offset15": _mutate(base, {15: 3, 11: 0xFF, 12: 0xFF}),
        "both_reserved": _mutate(base, {14: 1, 15: 3}),
        "count_exact": exact,
        "count_over": bytes(over),
        "crc": _mutate(base, {9: base[9] ^ 0x01}),
    }


def fx_hidden_like_catalog():
    rng = Rng(EVAL_SEED ^ 0xF00D)
    names = [name for (_c, name, _u, _w) in _LAYOUTS]
    out = []
    for _ in range(6):
        doc = _make_capture(rng, rng.rint(1, N_STREAMS), rng.pick(IDENTITY_REVS),
                            [names[rng.nxt() % len(names)] for _ in range(rng.rint(1, 2))])
        out.append(encode_segment(doc))
    return out


# --------------------------------------------------------------------------- #
# expected reports                                                             #
# --------------------------------------------------------------------------- #
def _catalog_rows():
    return _fix("catalog", lambda: build_catalog(_LAYOUTS))


def _expected_format_report() -> dict:
    def build():
        errors: dict[str, int] = {}
        ok = err = frames = 0
        streams = set()
        modes = {"raw": 0, "delta": 0, "dict": 0, "reset": 0}
        names = set()
        canon = set()
        for row in _catalog_rows():
            doc = decode_segment(bytes.fromhex(row["hex"]), SCHEMA)
            if "error" in doc:
                err += 1
                errors[doc["error"]] = errors.get(doc["error"], 0) + 1
                continue
            ok += 1
            streams.add(doc["stream_id"])
            frames += len(doc["records"])
            for r in doc["records"]:
                modes[r["mode"]] += 1
                if r["field"] is not None:
                    names.add(r["field"])
                if r["canonical_id"] is not None:
                    canon.add(r["canonical_id"])
        pairs = sorted(f"{SCHEMA['id_to_name'][c]}\t{SCHEMA['id_to_unit'][c]}" for c in canon)
        return {
            "format_tag": "VARC", "magic_hex": MAGIC.hex(), "version": VERSION,
            "header_size": HEADER_SIZE, "trailer_size": TRAILER_SIZE,
            "sync_byte": "aa", "esc_byte": "1b", "crc_coverage": "header",
            "crc_covers_offsets": [5, 15],
            "mode_ids": {"raw": 0, "delta": 1, "dict": 2, "reset": 3},
            "catalog_count": ok + err, "catalog_ok_count": ok, "catalog_error_count": err,
            "catalog_mode_counts": modes, "stream_count": len(streams),
            "catalog_frame_count": frames, "catalog_errors": dict(sorted(errors.items())),
            "distinct_field_count": len(names),
            "field_name_sha256": hashlib.sha256("\n".join(sorted(names)).encode()).hexdigest(),
            "field_unit_sha256": hashlib.sha256("\n".join(pairs).encode()).hexdigest(),
        }
    return _fix("format_report", build)


_RESERVED_PREFIXES = ("cap", "rej", "eval", "sample", "field")
_ROW_CAP = 12


def _examples(workspace) -> list[dict]:
    try:
        text = (Path(workspace) / "out" / "decoded_examples.jsonl").read_text(encoding="utf-8")
    except OSError as exc:
        raise _Mismatch(f"decoded_examples.jsonl unreadable: {exc}") from exc
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise _Mismatch("decoded_examples.jsonl holds a line that is not JSON") from exc
        _require(isinstance(row, dict) and set(row) == {"name", "hex", "decoded"},
                 "decoded_examples.jsonl: a line without exactly name, hex and decoded")
        rows.append(row)
    return rows


def _error_mutations(buf: bytes) -> dict[str, bytes]:
    def m(fn):
        b = bytearray(buf)
        fn(b)
        return bytes(b)

    def all_five(b):
        b[0] ^= 0xFF
        b[5] = 9
        b[14] = 1
        struct.pack_into("<H", b, 11, 0xFFFF)
        b[-1] ^= 0xFF

    return {
        "bad_magic": m(lambda b: b.__setitem__(0, b[0] ^ 0xFF)),
        "unsupported_version": m(lambda b: b.__setitem__(5, 9)),
        "reserved_not_zero": m(lambda b: b.__setitem__(14, 1)),
        "record_count_overflow": m(lambda b: struct.pack_into("<H", b, 11, 0xFFFF)),
        "trailer_crc_mismatch": m(lambda b: b.__setitem__(len(b) - 1, b[-1] ^ 0xFF)),
        "all_defects": m(all_five),
    }


# --------------------------------------------------------------------------- #
# check helpers                                                                #
# --------------------------------------------------------------------------- #
def _check_stream(workspace, name: str, builder) -> None:
    entries = _fix(name, builder)
    _same(decode_stream(entries, SCHEMA), _stream(workspace, entries), "--stream document")


def _check_single(workspace, name: str, builder) -> None:
    buf = _fix(name, builder)
    _same(decode_segment(buf, SCHEMA), _decode(workspace, buf), "decode document")


def _check_salvage(workspace, name: str, builder) -> None:
    buf = _fix(name, builder)
    expected = salvage(buf, SCHEMA)
    expected["damaged"] = [{"from_offset": d["from_offset"], "resync_offset": d["resync_offset"]}
                           for d in expected["damaged"]]
    _same(expected, _decode(workspace, buf, flag="--salvage"), "salvage document")


def _check_encode(workspace, pairs: list[tuple[dict, bytes]]) -> None:
    for i, (doc, expected) in enumerate(pairs):
        got = _encode(workspace, doc)
        _require(got is not None, f"document {i}: encode.py exited non zero or wrote no file")
        _require(got == expected, f"document {i}: {len(got)} bytes differ from the "
                 f"{len(expected)} expected, first at offset "
                 f"{next((j for j, (x, y) in enumerate(zip(got, expected)) if x != y), min(len(got), len(expected)))}")


def _values(doc) -> list:
    return [r.get("value") for r in doc["records"]] if isinstance(doc, dict) and isinstance(
        doc.get("records"), list) and all(isinstance(r, dict) for r in doc["records"]) else None


def _base_decodes(workspace) -> None:
    key = f"base:{workspace}"
    if key not in _CACHE:
        base = fx_isolated_cached()["base"]
        _CACHE[key] = _diff(decode_segment(base, SCHEMA), _decode(workspace, base))
    _require(_CACHE[key] is None, f"gate: a clean hidden segment does not decode ({_CACHE[key]})")


def fx_isolated_cached():
    return _fix("isolated", fx_isolated)


def _rejects_as(workspace, case: str) -> None:
    buf = fx_isolated_cached()[case]
    _same(header_defect(buf), _decode(workspace, buf), f"error object for the {case} segment")


# --------------------------------------------------------------------------- #
# whole documents on hidden reseeded inputs                                    #
# --------------------------------------------------------------------------- #
@criterion(description="--stream document for a hidden manifest of two interleaved streams "
           "with resent segments and stream_continues overrides equals the reference.")
def stream_doc_interleaved(workspace):
    return _holds("stream_doc_interleaved",
                  lambda: _check_stream(workspace, "interleaved", fx_stream_interleaved))


@criterion(description="--stream document for a hidden manifest whose runs close and reopen "
           "often, with padded paths, equals the reference.")
def stream_doc_new_runs(workspace):
    return _holds("stream_doc_new_runs",
                  lambda: _check_stream(workspace, "new_runs", fx_stream_new_runs))


@criterion(description="--stream document for a hidden aliased stream whose segments change "
           "revision, one field written by short and long keys, equals the reference.")
def stream_doc_remap_runs(workspace):
    return _holds("stream_doc_remap_runs",
                  lambda: _check_stream(workspace, "remap_runs", fx_stream_remap_runs))


@criterion(description="--stream document for a hidden manifest with frequent reset frames "
           "inside runs of two streams equals the reference.")
def stream_doc_reset_runs(workspace):
    return _holds("stream_doc_reset_runs",
                  lambda: _check_stream(workspace, "reset_runs", fx_stream_reset_runs))


@criterion(description="--stream document for a hidden mixed manifest (four streams, every "
           "revision, resends, overrides) equals the reference.")
def stream_doc_mix_a(workspace):
    return _holds("stream_doc_mix_a", lambda: _check_stream(workspace, "mix_a", fx_stream_mix_a))


@criterion(description="--stream document for a second hidden mixed manifest drawn from "
           "another seed equals the reference.")
def stream_doc_mix_b(workspace):
    return _holds("stream_doc_mix_b", lambda: _check_stream(workspace, "mix_b", fx_stream_mix_b))


@criterion(description="decode document for a hidden segment under a remapping revision on "
           "an aliased stream (all modes, count fields, long keys) equals the reference.")
def decode_doc_remapped(workspace):
    return _holds("decode_doc_remapped",
                  lambda: _check_single(workspace, "remapped_modes", fx_single_remapped_modes))


@criterion(description="decode document for a hidden segment whose bodies and extension "
           "payloads carry 0xAA and 0x1B bytes equals the reference.")
def decode_doc_escapes(workspace):
    return _holds("decode_doc_escapes",
                  lambda: _check_single(workspace, "escapes_ext", fx_single_escapes_ext))


@criterion(description="salvage document for a hidden segment with damaged frames between "
           "delta and dict frames equals the reference.")
def salvage_doc_state(workspace):
    return _holds("salvage_doc_state",
                  lambda: _check_salvage(workspace, "salvage_state", fx_salvage_state))


@criterion(description="salvage document for a hidden segment with a header defect, several "
           "damaged spans and false sync bytes equals the reference.")
def salvage_doc_mix(workspace):
    return _holds("salvage_doc_mix",
                  lambda: _check_salvage(workspace, "salvage_mix", fx_salvage_mix))


@criterion(description="encode.py output for three unmodified hidden decode documents equals "
           "the original segment bytes.")
def encode_doc_unmodified(workspace):
    def run():
        bufs = _fix("encode_unmodified", fx_encode_unmodified)
        _check_encode(workspace, [(decode_segment(b, SCHEMA), b) for b in bufs])
    return _holds("encode_doc_unmodified", run)


@criterion(description="encode.py output for three hand edited hidden decode documents equals "
           "the reference bytes.")
def encode_doc_edited(workspace):
    return _holds("encode_doc_edited",
                  lambda: _check_encode(workspace, _fix("encode_edited", fx_encode_edited)))


@criterion(description="encode.py output for hidden decode documents with records added "
           "equals the reference bytes.")
def encode_doc_new_records(workspace):
    return _holds("encode_doc_new_records",
                  lambda: _check_encode(workspace, _fix("encode_new", fx_encode_new_record)))


# --------------------------------------------------------------------------- #
# isolated rule checks: one rule each, read on its own observable              #
# --------------------------------------------------------------------------- #
@criterion(description="Rule: the decoded value of each raw record in a segment of count and "
           "other fields with the top bit set follows each field's unit.")
def rule_count_raw_values(workspace):
    def run():
        buf = _fix("rule_count", fx_rule_count_raw)
        got = _decode(workspace, buf)
        _require(_values(got) is not None, "decode.py printed no records")
        _require(_values(got) == _values(decode_segment(buf, SCHEMA)),
                 f"raw values {_values(got)}")
    return _holds("rule_count_raw_values", run)


@criterion(description="Rule: each delta record in a segment where three fields take turns "
           "resolves against its own field's running value.")
def rule_field_cumulator(workspace):
    def run():
        buf = _fix("rule_cumulator", fx_rule_field_cumulator)
        got = _decode(workspace, buf)
        _require(_values(got) is not None, "decode.py printed no records")
        _require(_values(got) == _values(decode_segment(buf, SCHEMA)),
                 f"record values {_values(got)}")
    return _holds("rule_field_cumulator", run)


def _stream_values(workspace, entries) -> tuple[list, list]:
    got = _stream(workspace, entries)
    _require(isinstance(got, dict) and isinstance(got.get("segments"), list)
             and len(got["segments"]) == len(entries),
             "decode.py --stream printed no segments list of the manifest's length")
    want = decode_stream(entries, SCHEMA)["segments"]
    return [_values(d) for d in got["segments"]], [_values(d) for d in want]


@criterion(description="Rule: in a one field manifest with resent segments, the values of "
           "every segment follow the run ledger (a resend leaves the run as it was).")
def rule_resend_keeps_run(workspace):
    def run():
        got, want = _stream_values(workspace, _fix("rule_resend", fx_rule_resend))
        _require(got == want, f"segment values {got}")
    return _holds("rule_resend_keeps_run", run)


@criterion(description="Rule: in a one field manifest, only a JSON boolean stream_continues "
           "in an entry replaces the header bit; the segment values follow.")
def rule_boolean_override(workspace):
    def run():
        got, want = _stream_values(workspace, _fix("rule_override", fx_rule_boolean_override))
        _require(got == want, f"segment values {got}")
    return _holds("rule_boolean_override", run)


@criterion(description="Rule: encode.py writes a delta in exactly delta_raw_len bytes only "
           "when that key is a JSON integer, else in the shortest form.")
def rule_length_integer(workspace):
    return _holds("rule_length_integer",
                  lambda: _check_encode(workspace, [_fix("rule_length", fx_rule_length_integer)]))


@criterion(description="Rule: magic beats version, a file under 20 bytes is bad_magic, version "
           "beats reserved, and the first non zero reserved byte is the offset reported.")
def reject_precedence(workspace):
    def run():
        _base_decodes(workspace)
        for case in ("magic_version", "short", "version_reserved", "offset15", "both_reserved"):
            _rejects_as(workspace, case)
    return _holds("reject_precedence", run)


@criterion(description="Rule: a record count whose frames fit exactly decodes, one more is "
           "record_count_overflow.")
def reject_count_bound(workspace):
    def run():
        fx = fx_isolated_cached()
        _same(decode_segment(fx["count_exact"], SCHEMA), _decode(workspace, fx["count_exact"]),
              "decode document for the exact count segment")
        _rejects_as(workspace, "count_over")
    return _holds("reject_count_bound", run)


@criterion(description="Rule: an edited header field is trailer_crc_mismatch with the expected "
           "and found checksums.")
def reject_crc_fields(workspace):
    def run():
        _base_decodes(workspace)
        _rejects_as(workspace, "crc")
    return _holds("reject_crc_fields", run)


# --------------------------------------------------------------------------- #
# mutation checks: one governed input changes, only what depends on it moves   #
# --------------------------------------------------------------------------- #
@criterion(description="Mutation: flipping one JSON boolean stream_continues override moves "
           "only the later segments of that stream, to the reference values.")
def mutation_override_flip(workspace):
    def run():
        base, flipped, sid = _fix("mutation_override", fx_mutation_override)
        before, after = _stream(workspace, base), _stream(workspace, flipped)
        for doc in (before, after):
            _require(isinstance(doc, dict) and isinstance(doc.get("segments"), list)
                     and len(doc["segments"]) == len(base), "decode.py --stream printed no "
                     "segments list of the manifest's length")
        want = decode_stream(flipped, SCHEMA)["segments"]
        cut = 4
        for i, entry in enumerate(flipped):
            mine = header_fields(entry["buf"])["stream_id"] == sid
            if mine and i >= cut:
                _require(_values(after["segments"][i]) == _values(want[i]),
                         f"segment {i} of the flipped stream: values {_values(after['segments'][i])}")
            else:
                _require(after["segments"][i] == before["segments"][i],
                         f"segment {i} changed although the flip cannot reach it")
    return _holds("mutation_override_flip", run)


@criterion(description="Mutation: moving one raw frame onto a count field moves only that "
           "record and the records that read it, to the reference values.")
def mutation_count_field(workspace):
    def run():
        base, moved, at = _fix("mutation_count", fx_mutation_count)
        before, after = _decode(workspace, base), _decode(workspace, moved)
        _require(_values(before) is not None and _values(after) is not None,
                 "decode.py printed no records")
        _require(after["records"][:at] == before["records"][:at],
                 "records before the moved frame changed")
        _require(_values(after)[at:] == _values(decode_segment(moved, SCHEMA))[at:],
                 f"values from the moved frame on: {_values(after)[at:]}")
    return _holds("mutation_count_field", run)


# --------------------------------------------------------------------------- #
# reports                                                                      #
# --------------------------------------------------------------------------- #
@criterion(description="decoded_examples.jsonl: at least 4 self-built lines, no reserved name "
           "prefix, each decoded value equals the reference and decode.py's output, coverage met.")
def report_decoded_examples(workspace):
    def run():
        rows = _examples(workspace)
        _require(len(rows) >= 4, f"{len(rows)} example lines, at least 4 wanted")
        docs = []
        for row in rows:
            _require(isinstance(row["name"], str) and not row["name"].startswith(
                _RESERVED_PREFIXES), f"example name {row['name']!r} is not allowed")
            text = row["hex"]
            _require(isinstance(text, str) and text == text.lower(),
                     f"example {row['name']}: hex is not lowercase text")
            ref = decode_segment(bytes.fromhex(text), SCHEMA)
            _same(ref, row["decoded"], f"example {row['name']} decoded")
            docs.append(ref)
        recs = [r for d in docs if "records" in d for r in d["records"]]
        _require({r["mode"] for r in recs} == {"raw", "delta", "dict", "reset"},
                 "the examples do not use all four modes")
        _require(any(e["type"] not in EXT_TYPES for r in recs for e in r["extensions"]),
                 "no example carries an opaque extension")
        _require(any(r["long_key"] for r in recs), "no example carries a long key")
        for row, ref in list(zip(rows, docs))[:_ROW_CAP]:
            _same(ref, _decode(workspace, bytes.fromhex(row["hex"])),
                  f"decode.py on example {row['name']}")
    return _holds("report_decoded_examples", run)


@criterion(description="roundtrip_report.json: one entry per example line, hashes and lengths "
           "of the example bytes, and encode.py rebuilding each example's decoded value exactly.")
def report_roundtrip(workspace):
    def run():
        rows = _examples(workspace)
        rep = _out_json(workspace, "roundtrip_report.json")
        _require(bool(rows) and isinstance(rep, dict) and rep.get("all_roundtrips_equal") is True,
                 "roundtrip_report.json missing or all_roundtrips_equal is not true")
        entries = rep.get("examples")
        _require(isinstance(entries, list) and len(entries) == len(rows),
                 "roundtrip_report.json examples do not match the example lines")
        for row, entry in zip(rows, entries):
            buf = bytes.fromhex(row["hex"])
            digest = hashlib.sha256(buf).hexdigest()
            want = {"name": row["name"], "input_sha256": digest, "rebuilt_sha256": digest,
                    "byte_length": len(buf), "roundtrip_equal": True}
            _same(want, entry, f"roundtrip entry {row['name']}")
        for row in rows[:_ROW_CAP]:
            _require(_encode(workspace, row["decoded"]) == bytes.fromhex(row["hex"]),
                     f"encode.py does not rebuild example {row['name']}")
    return _holds("report_roundtrip", run)


@criterion(description="error_analysis.json cases: the six mutations of the first example "
           "line give the reference error objects, and decode.py prints the same objects.")
def report_error_analysis(workspace):
    def run():
        rows = _examples(workspace)
        ea = _out_json(workspace, "error_analysis.json")
        _require(bool(rows) and isinstance(ea, dict) and isinstance(ea.get("cases"), dict),
                 "error_analysis.json missing or without cases")
        for case, buf in _error_mutations(bytes.fromhex(rows[0]["hex"])).items():
            expected = header_defect(buf)
            _require(expected is not None, f"case {case} is not a rejection")
            _same(expected, ea["cases"].get(case), f"error_analysis case {case}")
            _same(expected, _decode(workspace, buf), f"decode.py on case {case}")
    return _holds("report_error_analysis", run)


@criterion(description="format_report.json carries every key the appendix lists with the "
           "values computed from the shipped catalog.")
def report_format(workspace):
    return _holds("report_format", lambda: _same(
        _expected_format_report(), _out_json(workspace, "format_report.json"), "format_report"))


# --------------------------------------------------------------------------- #
# negatives (each stands down unless the program ran cleanly every time)       #
# --------------------------------------------------------------------------- #
@criterion(description="Penalty: decode.py answers the shipped catalog captures exactly but "
           "gets every fresh capture of the same shape wrong (answers looked up, not decoded).")
def negative_hardcoded_sample_answers(workspace):
    def run():
        visible = [bytes.fromhex(r["hex"]) for r in _catalog_rows()
                   if r["capture_id"].startswith("cap-")][:6]
        hidden = _fix("hidden_like_catalog", fx_hidden_like_catalog)
        seen = [_decode(workspace, b) for b in visible]
        fresh = [_decode(workspace, b) for b in hidden]
        if any(out is None for out in seen + fresh):
            return False
        # inverted: True means the cheat happened; the negative weight applies the penalty
        return (all(_matches(decode_segment(b, SCHEMA), o) for b, o in zip(visible, seen))
                and not any(_matches(decode_segment(b, SCHEMA), o) for b, o in zip(hidden, fresh)))
    return _fires("negative_hardcoded_sample_answers", run)


@criterion(description="Penalty: decode.py prints different documents for one hidden segment "
           "file across three runs on the same path.")
def negative_nondeterministic_output(workspace):
    def run():
        folder = _input_dir()
        path = _put(folder, "segment.varc", fx_isolated_cached()["base"])
        outs = [_json_of(_run(_wrap(workspace, "decode.py", [str(path)]), str(folder)))
                for _ in range(3)]
        shutil.rmtree(folder, ignore_errors=True)
        if any(o is None for o in outs):
            return False
        # inverted: True means the cheat happened; the negative weight applies the penalty
        return not (outs[0] == outs[1] == outs[2])
    return _fires("negative_nondeterministic_output", run)


@criterion(description="Penalty: decode.py prints the same document on repeat runs under each "
           "of three file names, yet a different document for the same hidden segment bytes "
           "under a different file name or extension.")
def negative_filename_dependent_behaviour(workspace):
    def run():
        base = fx_isolated_cached()["base"]
        outs = []
        for n in ("cap-00001.varc", "copy_two.bin", "segment"):
            first, again = _decode(workspace, base, name=n), _decode(workspace, base, name=n)
            # a name whose repeat runs disagree is run-to-run variation, graded by
            # negative_nondeterministic_output alone, so this check stands down
            if first is None or again is None or first != again:
                return False
            outs.append(first)
        # inverted: True means the cheat happened; the negative weight applies the penalty
        return not (outs[0] == outs[1] == outs[2])
    return _fires("negative_filename_dependent_behaviour", run)


_POISON = "zz"


def _plant_tables(root: Path) -> None:
    """Write a copy of the tables whose field names all carry the _POISON prefix."""
    root.mkdir(parents=True)
    root.chmod(0o755)
    files = {
        "field_layouts.csv": "canonical_id,name,unit,width\n" + "".join(
            f"{c},{_POISON}{n},{u},{w}\n" for (c, n, u, w) in _LAYOUTS),
        "symbol_table.tsv": "stream_id\tcanonical_id\talias\n" + "".join(
            f"{s}\t{c}\t{_POISON}{a}\n" for (s, c, a) in _SYMROWS),
        "revision_map.ini": "".join(
            f"[revision_{rev}]\n" + "".join(f"{k} = {v}\n" for k, v in sorted(mp.items()))
            for rev, mp in sorted(_REVISIONS.items()) if mp),
    }
    for name, text in files.items():
        _put(root, name, text.encode())


@criterion(description="Penalty: decode.py reads the reference tables from /app/data while "
           "it runs (field names follow a planted copy of the tables).")
def negative_reads_training_corpus_at_runtime(workspace):
    def run():
        root = Path("/app/data")
        if not _as_root() or root.exists():
            return False
        buf = _fix("remapped_modes", fx_single_remapped_modes)
        with _RUN_LOCK:
            try:
                _plant_tables(root)
                out = _decode(workspace, buf)
            finally:
                shutil.rmtree(root, ignore_errors=True)
        if not isinstance(out, dict) or not isinstance(out.get("records"), list):
            return False
        # inverted: True means the cheat happened; the negative weight applies the penalty
        return any(isinstance(r, dict) and str(r.get("field") or "").startswith(_POISON)
                   for r in out["records"])
    return _fires("negative_reads_training_corpus_at_runtime", run)


_SHADOWS = {"sitecustomize", "usercustomize", "json", "zlib", "struct", "hashlib", "os",
            "sys", "subprocess", "shutil", "tempfile", "signal", "pathlib", "typing",
            "rewardkit", "encodings", "codecs", "io"}


@criterion(description="Penalty: the workspace holds a .pth file or a module named after a "
           "standard library or grader module (sitecustomize, zlib, json, rewardkit and so on).")
def negative_rebinds_verifier_dependencies(workspace):
    def run():
        # inverted: True means the cheat happened; the negative weight applies the penalty
        ws = Path(workspace)
        for folder in (ws, ws / "out"):
            if not folder.is_dir():
                continue
            for entry in folder.iterdir():
                if entry.suffix == ".pth":
                    return True
                if entry.suffix == ".py" and entry.stem in _SHADOWS:
                    return True
                if entry.is_dir() and entry.name in _SHADOWS:
                    return True
        return False
    return _fires("negative_rebinds_verifier_dependencies", run)


criteria.stream_doc_interleaved(weight=5)
criteria.stream_doc_new_runs(weight=5)
criteria.stream_doc_remap_runs(weight=5)
criteria.stream_doc_reset_runs(weight=5)
criteria.stream_doc_mix_a(weight=5)
criteria.stream_doc_mix_b(weight=5)
criteria.decode_doc_remapped(weight=5)
criteria.decode_doc_escapes(weight=5)
criteria.salvage_doc_state(weight=5)
criteria.salvage_doc_mix(weight=5)
criteria.encode_doc_unmodified(weight=5)
criteria.encode_doc_edited(weight=5)
criteria.encode_doc_new_records(weight=5)
criteria.rule_count_raw_values(weight=3)
criteria.rule_field_cumulator(weight=3)
criteria.rule_resend_keeps_run(weight=3)
criteria.rule_boolean_override(weight=3)
criteria.rule_length_integer(weight=3)
criteria.reject_precedence(weight=3)
criteria.reject_count_bound(weight=3)
criteria.reject_crc_fields(weight=3)
criteria.mutation_override_flip(weight=3)
criteria.mutation_count_field(weight=3)
criteria.report_decoded_examples(weight=3)
criteria.report_roundtrip(weight=3)
criteria.report_error_analysis(weight=3)
criteria.report_format(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_rebinds_verifier_dependencies(weight=-3)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 test_output.py <env_root>")
    _write_corpus(Path(sys.argv[1]))
    print(f"[test_output] wrote the generated data files under {sys.argv[1]}/data")
