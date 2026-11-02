#!/usr/bin/env python3
"""VARC1 container decoder.

Usage:
    python3 decode.py <file.varc>
    python3 decode.py --stream <manifest.json>
    python3 decode.py --salvage <file.varc>
"""

import base64
import json
import sys
import zlib

MAGIC = b"VARC1"
VERSION = 2
HEADER_SIZE = 16
TRAILER_SIZE = 4
SYNC = 0xAA
ESC = 0x1B
MODES = ("raw", "delta", "dict", "reset")
KNOWN_EXT_TYPES = {1: "span", 2: "quality", 3: "source"}
ALIAS_STREAM_MOD = 40

PREFIXES = ("angle", "current", "flow", "freq", "humid", "level", "load",
            "peak", "phase", "power", "pressure", "rms", "speed", "temp",
            "ticks", "voltage")
UNITS = ("ampere", "celsius", "count", "hertz", "meter", "pascal", "percent",
         "volt")

# One byte per canonical id 1..2100: (prefix index << 3) | unit index.
FIELD_BLOB = "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"
# Per revision 4..7: entry count, then (key byte, canonical id low, high)*.
REV_BLOB = "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"


def _load_tables():
    packed = zlib.decompress(base64.b64decode(FIELD_BLOB))
    names = {}
    units = {}
    for idx, byte in enumerate(packed):
        cid = idx + 1
        names[cid] = "%s_%04d" % (PREFIXES[byte >> 3], cid)
        units[cid] = UNITS[byte & 7]
    ids_by_name = {name: cid for cid, name in names.items()}
    packed = zlib.decompress(base64.b64decode(REV_BLOB))
    revisions = {}
    pos = 0
    for revision in range(4, 8):
        count = packed[pos]
        pos += 1
        remap = {}
        for _ in range(count):
            remap[packed[pos]] = packed[pos + 1] | (packed[pos + 2] << 8)
            pos += 3
        revisions[revision] = remap
    return names, units, ids_by_name, revisions


FIELD_NAMES, FIELD_UNITS, FIELD_IDS_BY_NAME, REVISIONS = _load_tables()


def canonical_for_short_key(key, revision):
    return REVISIONS.get(revision, {}).get(key, key)


def field_name(canonical_id, stream_id):
    base = FIELD_NAMES[canonical_id]
    if canonical_id % ALIAS_STREAM_MOD + 1 == stream_id:
        return "%s@s%d" % (base, stream_id)
    return base


class Damaged(Exception):
    pass


class State:
    def __init__(self):
        self.cumulator = 0
        self.resolved = []


def read_uleb(buf, pos, end):
    value = 0
    shift = 0
    while True:
        if pos >= end:
            raise Damaged("truncated leb128")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, pos


def read_sleb(buf, pos, end):
    value = 0
    shift = 0
    start = pos
    while True:
        if pos >= end:
            raise Damaged("truncated leb128")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            if byte & 0x40:
                value -= 1 << shift
            return value, pos, pos - start


def unescape(window):
    out = bytearray()
    i = 0
    size = len(window)
    while i < size:
        byte = window[i]
        if byte == ESC:
            if i + 1 >= size:
                raise Damaged("escape without partner")
            out.append(window[i + 1] ^ 0x20)
            i += 2
        else:
            out.append(byte)
            i += 1
    return bytes(out)


def parse_extensions(body, pos):
    extensions = []
    end = len(body)
    while pos < end:
        ext_type, pos = read_uleb(body, pos, end)
        length, pos = read_uleb(body, pos, end)
        if pos + length > end:
            raise Damaged("extension overruns body")
        extensions.append({"type": ext_type, "hex": body[pos:pos + length].hex()})
        pos += length
    return extensions


def parse_frame(data, pos, limit, state, stream_id, revision):
    """Parse one frame at pos. Returns (record, next_pos) or raises Damaged."""
    if pos >= limit or data[pos] != SYNC:
        raise Damaged("no sync byte")
    pos += 1
    if pos >= limit:
        raise Damaged("truncated selector")
    selector = data[pos]
    pos += 1
    if selector & 0xE0:
        raise Damaged("selector high bits set")
    mode = MODES[selector & 0x03]
    wide = bool(selector & 0x04)
    long_key = bool(selector & 0x08)
    has_ext = bool(selector & 0x10)
    if wide and mode != "raw":
        raise Damaged("wide bit set outside raw mode")

    raw_key = None
    key_str = None
    if long_key:
        length, pos = read_uleb(data, pos, limit)
        if pos + length > limit:
            raise Damaged("truncated long key")
        try:
            key_str = data[pos:pos + length].decode("utf-8")
        except UnicodeDecodeError:
            raise Damaged("long key not utf-8")
        pos += length
    else:
        if pos >= limit:
            raise Damaged("truncated short key")
        raw_key = data[pos]
        pos += 1

    if pos >= limit:
        raise Damaged("truncated fchk")
    fchk = data[pos]
    pos += 1
    body_len, pos = read_uleb(data, pos, limit)
    if pos + body_len > limit:
        raise Damaged("body overruns trailer")
    body = unescape(data[pos:pos + body_len])
    pos += body_len
    if sum(body) & 0xFF != fchk:
        raise Damaged("fchk mismatch")

    record = {
        "raw_key": raw_key,
        "long_key": long_key,
        "mode": mode,
        "wide": wide if mode == "raw" else None,
        "ext_present": has_ext,
    }
    if long_key:
        record["key_str"] = key_str

    if mode == "raw":
        size = 4 if wide else 2
        if len(body) < size:
            raise Damaged("raw value truncated")
        raw_value = int.from_bytes(body[:size], "little", signed=True)
        record["raw_value"] = raw_value
        value = raw_value
        body_pos = size
    elif mode == "delta":
        delta, body_pos, delta_len = read_sleb(body, 0, len(body))
        record["delta_raw"] = delta
        record["delta_raw_len"] = delta_len
        value = state.cumulator + delta
    elif mode == "dict":
        if not body:
            raise Damaged("dict index missing")
        index = body[0]
        record["dict_index"] = index
        slot = len(state.resolved) - 1 - index
        if slot < 0:
            raise Damaged("dict index outside resolved list")
        value = state.resolved[slot]
        body_pos = 1
    else:
        value = None
        body_pos = 0

    if has_ext:
        extensions = parse_extensions(body, body_pos)
        if not extensions:
            raise Damaged("has_ext set with no extension")
    else:
        if body_pos != len(body):
            raise Damaged("trailing body bytes without has_ext")
        extensions = []
    record["extensions"] = extensions

    if mode == "reset":
        record["field"] = None
        record["unit"] = None
        record["canonical_id"] = None
    else:
        if long_key:
            canonical_id = FIELD_IDS_BY_NAME.get(key_str)
        else:
            cid = canonical_for_short_key(raw_key, revision)
            canonical_id = cid if cid in FIELD_NAMES else None
        if canonical_id is None:
            record["field"] = key_str if long_key else None
            record["unit"] = None
            record["canonical_id"] = None
        else:
            record["field"] = field_name(canonical_id, stream_id)
            record["unit"] = FIELD_UNITS[canonical_id]
            record["canonical_id"] = canonical_id
    record["value"] = value

    if mode == "reset":
        state.resolved = []
        state.cumulator = 0
    else:
        state.resolved.append(value)
        if mode in ("raw", "delta"):
            state.cumulator = value
    return record, pos


def parse_header(data):
    """Return (header dict, error dict). Exactly one of the two is None."""
    if len(data) < 20 or data[0:5] != MAGIC:
        return None, {"error": "bad_magic"}
    version = data[5]
    if version != VERSION:
        return None, {"error": "unsupported_version", "version": version}
    for offset in (14, 15):
        if data[offset] != 0:
            return None, {"error": "reserved_not_zero", "offset": offset}
    header = {
        "magic_ok": True,
        "version": version,
        "stream_id": int.from_bytes(data[7:9], "little"),
        "seq_no": int.from_bytes(data[9:11], "little"),
        "revision": data[13],
        "flags": {"stream_continues": bool(data[6] & 0x01)},
        "record_count": int.from_bytes(data[11:13], "little"),
    }
    frame_bytes = len(data) - HEADER_SIZE - TRAILER_SIZE
    if header["record_count"] * 5 > frame_bytes:
        return None, {"error": "record_count_overflow",
                      "record_count": header["record_count"]}
    expected = zlib.crc32(data[5:16]) & 0xFFFFFFFF
    found = int.from_bytes(data[-TRAILER_SIZE:], "little")
    if expected != found:
        return None, {"error": "trailer_crc_mismatch", "expected": expected,
                      "found": found}
    return header, None


def header_defect(data):
    _, error = parse_header(data)
    return None if error is None else error["error"]


def decode_segment(data, state=None):
    header, error = parse_header(data)
    if error is not None:
        return error
    if state is None:
        state = State()
    limit = len(data) - TRAILER_SIZE
    pos = HEADER_SIZE
    records = []
    for _ in range(header["record_count"]):
        try:
            record, pos = parse_frame(data, pos, limit, state,
                                      header["stream_id"], header["revision"])
        except Damaged:
            # A segment with damaged frames belongs on the salvage path; here
            # we keep the frames read so far rather than failing the run.
            break
        records.append(record)
    doc = dict(header)
    doc["records"] = records
    return doc


def decode_stream(manifest_path):
    with open(manifest_path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    states = {}
    continues = {}
    documents = []
    for entry in manifest["segments"]:
        with open(entry["path"], "rb") as handle:
            data = handle.read()
        header, error = parse_header(data)
        if error is not None:
            documents.append(error)
            continue
        stream_id = header["stream_id"]
        if continues.get(stream_id):
            state = states[stream_id]
        else:
            state = State()
        documents.append(decode_segment(data, state))
        states[stream_id] = state
        continues[stream_id] = header["flags"]["stream_continues"]
    return {"segments": documents}


def salvage_segment(data):
    defect = header_defect(data)
    header, _ = parse_header(data)
    if header is not None:
        stream_id = header["stream_id"]
        revision = header["revision"]
    else:
        if len(data) >= HEADER_SIZE:
            stream_id = int.from_bytes(data[7:9], "little")
            revision = data[13]
        else:
            stream_id = 0
            revision = 0
    limit = max(len(data) - TRAILER_SIZE, HEADER_SIZE)
    state = State()
    records = []
    damaged = []
    pos = HEADER_SIZE
    while pos < limit:
        try:
            record, next_pos = parse_frame(data, pos, limit, state, stream_id,
                                           revision)
        except Damaged as exc:
            from_offset = pos
            reason = str(exc)
            scan = pos + 1
            resync = limit
            while scan < limit:
                probe = State()
                probe.cumulator = state.cumulator
                probe.resolved = list(state.resolved)
                try:
                    parse_frame(data, scan, limit, probe, stream_id, revision)
                except Damaged:
                    scan += 1
                    continue
                resync = scan
                break
            damaged.append({"from_offset": from_offset,
                            "resync_offset": resync, "reason": reason})
            pos = resync
            continue
        records.append(record)
        pos = next_pos
    return {"records": records, "damaged": damaged, "header_defect": defect}


def main(argv):
    if len(argv) == 2:
        with open(argv[1], "rb") as handle:
            result = decode_segment(handle.read())
    elif len(argv) == 3 and argv[1] == "--stream":
        result = decode_stream(argv[2])
    elif len(argv) == 3 and argv[1] == "--salvage":
        with open(argv[2], "rb") as handle:
            result = salvage_segment(handle.read())
    else:
        sys.stderr.write(__doc__)
        return 2
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
