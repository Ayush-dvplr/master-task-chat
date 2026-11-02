#!/usr/bin/env python3
"""Reference VARC1 codec for datagen + verifier mirror (NOT shipped to the agent).

This is the ground-truth implementation of the VARC1 container used by
WORK/datagen.py (to write environment/data) and mirrored inside
tests/test_output.py (to build hidden corpora and expected values). The shipped
oracle solution/solve.py is an INDEPENDENT implementation of the same contract.
"""
from __future__ import annotations

import struct
import zlib
from typing import Any

MAGIC = b"VARC1"
VERSION = 2
HEADER_SIZE = 16
TRAILER_SIZE = 4
SYNC = 0xAA
ESC = 0x1B
MIN_FRAME = 5  # SYNC + selector + >=1 key byte + fchk + >=1 body_len byte (+ 0 body)

MODE_RAW, MODE_DELTA, MODE_DICT, MODE_RESET = 0, 1, 2, 3
MODE_NAME = {0: "raw", 1: "delta", 2: "dict", 3: "reset"}
NAME_MODE = {v: k for k, v in MODE_NAME.items()}


class Reject(Exception):
    def __init__(self, obj: dict) -> None:
        super().__init__(obj.get("error", "reject"))
        self.obj = obj


class FrameError(Exception):
    """Raised inside frame parsing to drive salvage; never leaves decode_segment."""


# --------------------------------------------------------------------------- #
# varints and escaping
# --------------------------------------------------------------------------- #
def write_uvarint(n: int) -> bytes:
    if n < 0:
        raise ValueError("uvarint negative")
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def read_uvarint(buf: bytes, pos: int) -> tuple[int, int]:
    val = shift = 0
    while True:
        if pos >= len(buf):
            raise FrameError("truncated uvarint")
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, pos
        shift += 7
        if shift > 63:
            raise FrameError("uvarint too long")


def shortest_sleb128_len(n: int) -> int:
    return len(write_sleb128(n))


def write_sleb128(n: int) -> bytes:
    """Shortest signed LEB128."""
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        sign = bool(b & 0x40)
        if (n == 0 and not sign) or (n == -1 and sign):
            out.append(b)
            return bytes(out)
        out.append(b | 0x80)


def _pad_sleb128(value: int, length: int) -> bytes:
    """Overlong signed LEB128 of exactly `length` bytes (sign-extended)."""
    out = bytearray(write_sleb128(value))
    if length < len(out):
        raise ValueError("length shorter than shortest")
    sign_byte = 0x7F if value < 0 else 0x00
    while len(out) < length:
        out[-1] |= 0x80
        out.append(sign_byte)
    out[-1] &= 0x7F
    return bytes(out)


def read_sleb128(buf: bytes, pos: int) -> tuple[int, int, int]:
    """Return (value, nbytes, end_pos)."""
    result = shift = 0
    start = pos
    while True:
        if pos >= len(buf):
            raise FrameError("truncated sleb128")
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        shift += 7
        if not (b & 0x80):
            if b & 0x40:
                result |= -(1 << shift)
            return result, pos - start, pos
        if shift > 70:
            raise FrameError("sleb128 too long")


def escape_body(raw: bytes) -> bytes:
    out = bytearray()
    for b in raw:
        if b in (SYNC, ESC):
            out.append(ESC)
            out.append(b ^ 0x20)
        else:
            out.append(b)
    return bytes(out)


def unescape_window(buf: bytes, pos: int, body_len: int) -> tuple[bytes, int]:
    """Unescape exactly body_len ESCAPED bytes starting at pos (bounded)."""
    end = pos + body_len
    if end > len(buf):
        raise FrameError("body runs past end")
    raw = bytearray()
    i = pos
    while i < end:
        b = buf[i]
        if b == ESC:
            if i + 1 >= end:
                raise FrameError("dangling escape at body boundary")
            raw.append(buf[i + 1] ^ 0x20)
            i += 2
        else:
            raw.append(b)
            i += 1
    return bytes(raw), end


# --------------------------------------------------------------------------- #
# header + crc
# --------------------------------------------------------------------------- #
def crc_header(buf: bytes) -> int:
    # coverage: offsets 5..15 inclusive = 11 header bytes after the magic
    return zlib.crc32(buf[5:16]) & 0xFFFFFFFF


def build_header(stream_id: int, seq_no: int, rec_count: int, revision: int,
                 stream_continues: bool) -> bytes:
    flags = 0x01 if stream_continues else 0x00
    return (MAGIC + struct.pack("<B", VERSION) + struct.pack("<B", flags)
            + struct.pack("<H", stream_id) + struct.pack("<H", seq_no)
            + struct.pack("<H", rec_count) + struct.pack("<B", revision)
            + b"\x00\x00")


def encode_segment(doc: dict) -> bytes:
    body = bytearray()
    for rec in doc["records"]:
        mode_name = rec["mode"]
        mode = NAME_MODE[mode_name]
        wide = bool(rec.get("wide")) if mode_name == "raw" else False
        long_key = bool(rec["long_key"])
        exts = rec.get("extensions") or []
        has_ext = bool(exts)
        sel = mode | (wide << 2) | (long_key << 3) | (has_ext << 4)
        raw = bytearray()
        if mode_name == "raw":
            raw += struct.pack("<i" if wide else "<h", rec["raw_value"])
        elif mode_name == "delta":
            length = rec.get("delta_raw_len")
            if length is not None and length > shortest_sleb128_len(rec["delta_raw"]):
                raw += _pad_sleb128(rec["delta_raw"], length)
            else:
                raw += write_sleb128(rec["delta_raw"])
        elif mode_name == "dict":
            raw.append(rec["dict_index"])
        # reset emits no value bytes
        for ext in exts:
            payload = bytes.fromhex(ext["hex"])
            raw += write_uvarint(ext["type"])
            raw += write_uvarint(len(payload))
            raw += payload
        fchk = sum(raw) & 0xFF
        esc = escape_body(bytes(raw))
        frame = bytearray([SYNC, sel])
        if long_key:
            kb = rec["key_str"].encode("utf-8")
            frame += write_uvarint(len(kb))
            frame += kb
        else:
            frame.append(rec["raw_key"])
        frame.append(fchk)
        frame += write_uvarint(len(esc))
        frame += esc
        body += frame
    header = build_header(doc["stream_id"], doc["seq_no"], doc["record_count"],
                          doc["revision"], doc["flags"]["stream_continues"])
    crc = crc_header(header)
    return bytes(header) + bytes(body) + struct.pack("<I", crc)


# --------------------------------------------------------------------------- #
# stream state + field remap
# --------------------------------------------------------------------------- #
class StreamState:
    __slots__ = ("cumulator", "resolved")

    def __init__(self) -> None:
        self.cumulator = 0
        self.resolved: list[int] = []

    def reset(self) -> None:
        self.cumulator = 0
        self.resolved = []


def empty_schema() -> dict:
    return {"id_to_name": {}, "name_to_id": {}, "id_to_unit": {}, "alias": {}, "remap": {}}


def resolve_field(rec: dict, stream_id: int, revision: int, schema: dict):
    """Return (field_name, unit, canonical_id). field_name is None for reset."""
    if rec["mode"] == "reset":
        return None, None, None
    if rec["long_key"]:
        name0 = rec.get("key_str")
        canonical = schema["name_to_id"].get(name0)
    else:
        raw_key = rec["raw_key"]
        canonical = schema["remap"].get((revision, raw_key), raw_key)
        name0 = schema["id_to_name"].get(canonical)
    final = schema["alias"].get((stream_id, canonical), name0)
    unit = schema["id_to_unit"].get(canonical)
    return final, unit, canonical


# --------------------------------------------------------------------------- #
# frame parse
# --------------------------------------------------------------------------- #
def parse_frame(buf, pos, state, stream_id, revision, schema):
    if pos >= len(buf) or buf[pos] != SYNC:
        raise FrameError("missing sync")
    start = pos
    pos += 1
    if pos >= len(buf):
        raise FrameError("truncated selector")
    sel = buf[pos]
    pos += 1
    if sel >> 5:
        raise FrameError("reserved selector bits set")
    mode = sel & 0x03
    wide = bool((sel >> 2) & 1)
    long_key = bool((sel >> 3) & 1)
    has_ext = bool((sel >> 4) & 1)

    if long_key:
        klen, pos = read_uvarint(buf, pos)
        if pos + klen > len(buf):
            raise FrameError("truncated key")
        key_str = buf[pos:pos + klen].decode("utf-8")
        pos += klen
        raw_key = None
    else:
        if pos >= len(buf):
            raise FrameError("truncated key")
        raw_key = buf[pos]
        pos += 1
        key_str = None

    if pos >= len(buf):
        raise FrameError("truncated fchk")
    fchk = buf[pos]
    pos += 1
    body_len, pos = read_uvarint(buf, pos)
    raw, pos = unescape_window(buf, pos, body_len)
    if (sum(raw) & 0xFF) != fchk:
        raise FrameError("fchk mismatch")

    rec: dict = {"raw_key": raw_key, "long_key": long_key, "mode": MODE_NAME[mode],
                 "wide": None, "ext_present": has_ext, "extensions": []}
    if long_key:
        rec["key_str"] = key_str
    off = 0
    if mode == MODE_RAW:
        if wide:
            if len(raw) < 4:
                raise FrameError("raw i32 short")
            val = struct.unpack_from("<i", raw, 0)[0]
            off = 4
        else:
            if len(raw) < 2:
                raise FrameError("raw i16 short")
            val = struct.unpack_from("<h", raw, 0)[0]
            off = 2
        rec["wide"] = wide
        rec["raw_value"] = val
        rec["value"] = val
    elif mode == MODE_DELTA:
        delta, nb, _ = read_sleb128(raw, 0)
        off = nb
        rec["delta_raw"] = delta
        rec["delta_raw_len"] = nb
        val = state.cumulator + delta
        rec["value"] = val
        state.cumulator = val
    elif mode == MODE_DICT:
        if len(raw) < 1:
            raise FrameError("dict index short")
        idx = raw[0]
        off = 1
        back = len(state.resolved) - 1 - idx
        if back < 0 or back >= len(state.resolved):
            raise FrameError("dict index out of range")
        val = state.resolved[back]
        rec["dict_index"] = idx
        rec["value"] = val
        state.cumulator = val
    else:  # reset
        val = None
        rec["value"] = None
        state.reset()

    if has_ext:
        exts = []
        p = off
        while p < len(raw):
            t, p = read_uvarint(raw, p)
            length, p = read_uvarint(raw, p)
            if p + length > len(raw):
                raise FrameError("ext payload truncated")
            exts.append({"type": t, "hex": raw[p:p + length].hex()})
            p += length
        rec["extensions"] = exts
    elif off != len(raw):
        raise FrameError("trailing body bytes without ext flag")

    rec["field"], rec["unit"], rec["canonical_id"] = resolve_field(rec, stream_id, revision, schema)
    if mode != MODE_RESET:
        state.resolved.append(val)
    return rec, pos, start


# --------------------------------------------------------------------------- #
# rejection checks (shared by decode_segment and salvage header_defect)
# --------------------------------------------------------------------------- #
def header_defect(buf: bytes):
    if buf[:5] != MAGIC:
        return {"error": "bad_magic"}
    v = buf[5] if len(buf) > 5 else -1
    if v != VERSION:
        return {"error": "unsupported_version", "version": v}
    if len(buf) < HEADER_SIZE:
        rc = struct.unpack_from("<H", buf, 11)[0] if len(buf) >= 13 else -1
        return {"error": "record_count_overflow", "record_count": rc}
    if buf[14] != 0:
        return {"error": "reserved_not_zero", "offset": 14}
    if buf[15] != 0:
        return {"error": "reserved_not_zero", "offset": 15}
    rec_count = struct.unpack_from("<H", buf, 11)[0]
    avail = len(buf) - HEADER_SIZE - TRAILER_SIZE
    if avail < 0 or rec_count * MIN_FRAME > avail:
        return {"error": "record_count_overflow", "record_count": rec_count}
    expected = crc_header(buf)
    found = struct.unpack("<I", buf[-TRAILER_SIZE:])[0]
    if expected != found:
        return {"error": "trailer_crc_mismatch", "expected": expected, "found": found}
    return None


def _header_fields(buf: bytes) -> dict:
    return {
        "stream_id": struct.unpack_from("<H", buf, 7)[0],
        "seq_no": struct.unpack_from("<H", buf, 9)[0],
        "record_count": struct.unpack_from("<H", buf, 11)[0],
        "revision": buf[13],
        "flags": {"stream_continues": bool(buf[6] & 0x01)},
    }


def decode_segment(buf: bytes, schema: dict | None = None,
                   state: StreamState | None = None) -> dict:
    schema = schema or empty_schema()
    defect = header_defect(buf)
    if defect is not None:
        return defect
    hf = _header_fields(buf)
    own_state = state if state is not None else StreamState()
    records = []
    pos = HEADER_SIZE
    try:
        for _ in range(hf["record_count"]):
            rec, pos, _start = parse_frame(buf, pos, own_state, hf["stream_id"],
                                           hf["revision"], schema)
            records.append(rec)
    except FrameError as exc:
        return {"error": "malformed_frame", "detail": str(exc)}
    return {"magic_ok": True, "version": VERSION, "stream_id": hf["stream_id"],
            "seq_no": hf["seq_no"], "revision": hf["revision"], "flags": hf["flags"],
            "record_count": hf["record_count"], "records": records}


def decode_stream(segments: list[bytes], schema: dict | None = None) -> dict:
    schema = schema or empty_schema()
    state = StreamState()
    docs = []
    for buf in segments:
        docs.append(decode_segment(buf, schema, state))
    return {"segments": docs}


def salvage(buf: bytes, schema: dict | None = None) -> dict:
    schema = schema or empty_schema()
    defect = header_defect(buf)
    hf = _header_fields(buf) if len(buf) >= HEADER_SIZE else {"revision": 0, "stream_id": 0}
    state = StreamState()
    records = []
    damaged = []
    pos = HEADER_SIZE
    end = len(buf) - TRAILER_SIZE
    while pos < end:
        try:
            rec, newpos, _start = parse_frame(buf, pos, state, hf["stream_id"],
                                              hf["revision"], schema)
            records.append(rec)
            pos = newpos
        except FrameError as exc:
            bad_from = pos
            resync = _next_valid_sync(buf, pos + 1, end, state, hf["stream_id"],
                                      hf["revision"], schema)
            damaged.append({"from_offset": bad_from,
                            "resync_offset": resync if resync is not None else end,
                            "reason": str(exc)})
            if resync is None:
                break
            pos = resync
    return {"records": records, "damaged": damaged,
            "header_defect": defect["error"] if defect else None}


def _next_valid_sync(buf, start, end, state, stream_id, revision, schema):
    """Scan for the next SYNC that begins a parseable frame (re-validated)."""
    i = start
    while i < end:
        if buf[i] == SYNC:
            trial = StreamState()
            trial.cumulator = state.cumulator
            trial.resolved = list(state.resolved)
            try:
                parse_frame(buf, i, trial, stream_id, revision, schema)
                return i
            except FrameError:
                pass
        i += 1
    return None


if __name__ == "__main__":
    # self-test
    schema = empty_schema()
    schema["id_to_name"] = {10: "temp", 11: "humid", 100: "temp_c", 101: "humid_pct", 5: "flow"}
    schema["name_to_id"] = {v: k for k, v in schema["id_to_name"].items()}
    schema["id_to_unit"] = {10: "celsius", 11: "percent", 100: "celsius", 101: "percent", 5: "meter"}
    schema["alias"] = {(7, 100): "temp_c@s7"}
    schema["remap"] = {(3, 10): 100, (3, 11): 101}
    doc = {
        "stream_id": 7, "seq_no": 0, "revision": 3,
        "flags": {"stream_continues": False}, "record_count": 5,
        "records": [
            {"raw_key": 10, "long_key": False, "mode": "raw", "wide": True,
             "raw_value": 100000, "value": 100000, "ext_present": False, "extensions": []},
            {"raw_key": 11, "long_key": False, "mode": "delta", "wide": None,
             "delta_raw": 5, "delta_raw_len": 1, "value": None, "ext_present": False, "extensions": []},
            {"raw_key": 5, "long_key": False, "mode": "dict", "wide": None,
             "dict_index": 1, "value": None, "ext_present": True,
             "extensions": [{"type": 9, "hex": "aa1b"}]},
            {"raw_key": 0, "long_key": False, "mode": "reset", "wide": None,
             "value": None, "ext_present": False, "extensions": []},
            {"raw_key": 0, "long_key": True, "key_str": "flow", "mode": "raw",
             "wide": False, "raw_value": -7, "value": -7, "ext_present": False, "extensions": []},
        ],
    }
    raw = encode_segment(doc)
    back = decode_segment(raw, schema)
    re = encode_segment(back)
    assert re == raw, "roundtrip byte mismatch"
    print("single-file roundtrip OK, bytes:", len(raw))
    print("rec0 field:", back["records"][0]["field"], "unit:", back["records"][0]["unit"],
          "val:", back["records"][0]["value"])
    print("rec2 value (dict):", back["records"][2]["value"], "ext:", back["records"][2]["extensions"])
    doc2 = {k: v for k, v in doc.items()}
    doc2["records"] = [dict(doc["records"][1])]
    doc2["records"][0]["delta_raw_len"] = 3
    doc2["record_count"] = 1
    r2 = encode_segment(doc2)
    b2 = decode_segment(r2, schema)
    assert b2["records"][0]["delta_raw_len"] == 3, b2["records"][0]
    assert encode_segment(b2) == r2, "overlong roundtrip mismatch"
    print("overlong delta roundtrip OK, len token:", b2["records"][0]["delta_raw_len"])
    bad = bytearray(raw); bad[0] ^= 0xFF
    assert decode_segment(bytes(bad)) == {"error": "bad_magic"}
    bad = bytearray(raw); bad[5] = 9
    assert decode_segment(bytes(bad)) == {"error": "unsupported_version", "version": 9}
    bad = bytearray(raw); bad[14] = 1
    assert decode_segment(bytes(bad)) == {"error": "reserved_not_zero", "offset": 14}
    print("rejection precedence OK")
    seg = bytearray(raw)
    seg[HEADER_SIZE + 6] ^= 0xFF
    sv = salvage(bytes(seg), schema)
    print("salvage: records", len(sv["records"]), "damaged", sv["damaged"])
