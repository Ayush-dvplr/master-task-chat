#!/usr/bin/env python3
"""VARC1 segment decoder.

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
ESC_XOR = 0x20
MODE_RAW, MODE_DELTA, MODE_DICT, MODE_RESET = 0, 1, 2, 3
MODE_NAMES = ("raw", "delta", "dict", "reset")

# field_layouts.csv names are "<prefix>_<canonical_id as four digits>", the
# prefix cycling through this tuple by (canonical_id - 1) % 16.
_PREFIXES = (
    "pressure", "voltage", "current", "freq", "load", "ticks", "phase",
    "level", "flow", "rms", "peak", "humid", "angle", "speed", "power",
    "temp",
)
_UNIT_NAMES = (
    "ampere", "celsius", "count", "hertz", "meter", "pascal", "percent",
    "volt",
)
# zlib+base64 of the unit index per canonical id 1..2100 (field_layouts.csv)
_UNITS_B64 = (
    "eNotlQlyIzEMA79E8fz/z9I9zqZqbWskCgRATL7d2rmJV9s9cfEus/ZdvVd9zYOIx47iSefl6529"
    "rtxm00TF3Xt7N/eiLiIyc6M2q/dldFMtcnpyqN/TOZTv1xzrpvDWXEZsePfuJB9nqe3wqqxrtlc0"
    "WO9i5lHl8ZgvK86XbHhpUTBlsjrVU4CkPNcBpSNjlw4u51zjCO1VDP9x4TvR3fK7E9w37NnhTN08"
    "MBUFoCaCa1+wefnjF503nNDinTfm1cLJFuS8XHjhK7t6pvy91IqDb7iPbJoPnj820AI4wQdMtvKl"
    "GwEgI4aFkkU2CYf18WDTPEXGT6oB39s29w08BB1J0vDlpPHxTxaq1Cv8q0RdOKycj11EoRHupoYk"
    "oTAUAB5CkEMYnIRXhATKKOuD3GMPGvEHn7SFFPTfLgOHY8XF4D7KgpVe4QI3wX2yESLfaIvQHKMn"
    "f5p9gmoGdsEvPEXbGJ2U9XFdY7fReZgWLnEjernmMrK8ydRulIAf5Q9bBdpHIzg4N9kgyoJ2C0KD"
    "w/ABbK3Mbi2Bm7UL7CKnldh2cABo7ukPtv3h56eZ7V7NsDUXj7AqLQB9kEE7y2JhLQYFFr4P9GUY"
    "sIbKNCqpO8OIElmDfo6lJr5yBCWeXUwHbgx3Q18kxMRaADPDo6OCl1lk1N0QwuT0Z63lOCZD5/l1"
    "70O6dmgczKeTvk2wDOen72Ea8NwHtcw3LHMf0sIHPmdVj1R/0gP0YR+aQKFxyLATJqFTimIRzqSU"
    "++vaW7GSelFq6JbmW8pDG3ofNsflxgEPCSQUNEvik+Eb+XUEVPDTWO85ZTQIAF0He6qtofCyfaKH"
    "wxCKSSn5SUPpNB7KAVsDp07X7F9w6kCIADxzQQpxtZZ++s/Y42rHWdEAbegREXCD67/hWC0Nc61W"
    "DB+3qDHTwXAaUbQHMsMhv8A1/cAjNs6SC06ofNE3dcbggTSp4Bee5RyYwIecqCNdWsBO94sOqwDL"
    "hKdN/GiEI1UKKU0kGEXrxDTUEitWMbnVCqqYm/6Pdb5H2zJySK97GeFfaAPZKTDkCSHU9BWQojcq"
    "PugcIk4R1C4QG1vhFOfNqENYnIkwGIojpugz41NXfzm3v6t8hxCciM7K+r5ialXX/AaQ0/TNkZEI"
    "xi+EfXFA2ppOAqDJp4ppYJm1Jqz+U37eEnCe9hT6C5rve3UaWLT00x5wMomk//bTYniHpt9ncXkY"
    "p/UpPQlUDh1SGK5IZSlHXUdB3heE4iZEIg3n+14joa8ZzvUVDUWQVvm91HxN3OdtWnAknx5hSCDM"
    "4UFIVn0PcE8b8NvfGMiv8/bMGayKdzb+AKahpug="
)
# zlib+base64 of the revision remap (revision_map.ini), revisions 4..7
_REV_B64 = (
    "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"
)


def _units():
    seq = zlib.decompress(base64.b64decode(_UNITS_B64)).decode("ascii")
    return {i + 1: _UNIT_NAMES[int(c)] for i, c in enumerate(seq)}


def _revmaps():
    txt = zlib.decompress(base64.b64decode(_REV_B64)).decode("ascii")
    maps = {}
    for part in txt.split(";"):
        rev, body = part.split(":", 1)
        maps[int(rev)] = {
            int(k): int(v) for k, v in (p.split("=") for p in body.split(","))
        }
    return maps


UNIT_BY_ID = _units()
REVMAPS = _revmaps()
FIELD_COUNT = len(UNIT_BY_ID)


def base_name(cid):
    if cid is None or cid < 1 or cid > FIELD_COUNT:
        return None
    return "%s_%04d" % (_PREFIXES[(cid - 1) % 16], cid)


NAME_TO_ID = {base_name(i): i for i in range(1, FIELD_COUNT + 1)}


def alias_for(stream_id, cid):
    """symbol_table.tsv holds exactly one alias row per canonical id."""
    if cid is None or cid < 1 or cid > FIELD_COUNT:
        return None
    if stream_id != (cid % 40) + 1:
        return None
    return "%s@s%d" % (base_name(cid), stream_id)


def resolve_short_key(key, revision):
    return REVMAPS.get(revision, {}).get(key, key)


def field_info(stream_id, cid, key_text=None):
    """Return (field_name, unit, canonical_id)."""
    if cid is None:
        return key_text, None, None
    name = base_name(cid)
    if name is None:
        return key_text, None, None
    unit = UNIT_BY_ID[cid]
    alias = alias_for(stream_id, cid)
    return (alias or name), unit, cid


class Damaged(Exception):
    pass


def read_uleb(buf, i, end):
    val = 0
    shift = 0
    while True:
        if i >= end:
            raise Damaged("truncated uleb128")
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return val, i


def read_sleb(buf, i, end):
    val = 0
    shift = 0
    start = i
    while True:
        if i >= end:
            raise Damaged("truncated sleb128")
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            if b & 0x40:
                val -= 1 << shift
            return val, i, i - start





def unescape_body(window):
    out = bytearray()
    i = 0
    n = len(window)
    while i < n:
        b = window[i]
        if b == ESC:
            if i + 1 >= n:
                raise Damaged("escape byte without partner")
            out.append(window[i + 1] ^ ESC_XOR)
            i += 2
        else:
            out.append(b)
            i += 1
    return bytes(out)


class StreamState:
    def __init__(self):
        self.cums = {}
        self.resolved = []

    def copy(self):
        s = StreamState()
        s.cums = dict(self.cums)
        s.resolved = list(self.resolved)
        return s

    def apply(self, rec):
        mode = rec["mode"]
        if mode == "reset":
            self.cums.clear()
            del self.resolved[:]
            return
        self.resolved.append(rec["value"])
        if mode in ("raw", "delta"):
            self.cums[rec["field"]] = rec["value"]


def parse_extensions(body, pos):
    exts = []
    n = len(body)
    while pos < n:
        etype, pos = read_uleb(body, pos, n)
        elen, pos = read_uleb(body, pos, n)
        if pos + elen > n:
            raise Damaged("truncated extension payload")
        exts.append({"type": etype, "hex": body[pos:pos + elen].hex()})
        pos += elen
    return exts


def parse_frame(data, off, limit, state, stream_id, revision):
    """Parse one frame at off. Returns (record, next_off). Raises Damaged."""
    if off >= limit or data[off] != SYNC:
        raise Damaged("no sync byte")
    if off + 1 >= limit:
        raise Damaged("truncated selector")
    sel = data[off + 1]
    if sel & 0xE0:
        raise Damaged("reserved selector bits set")
    mode = sel & 0x03
    wide = bool(sel & 0x04)
    long_key = bool(sel & 0x08)
    has_ext = bool(sel & 0x10)
    if wide and mode != MODE_RAW:
        raise Damaged("wide bit set outside raw mode")
    pos = off + 2
    raw_key = None
    key_text = None
    if long_key:
        klen, pos = read_uleb(data, pos, limit)
        if pos + klen > limit:
            raise Damaged("truncated long key")
        try:
            key_text = data[pos:pos + klen].decode("utf-8")
        except UnicodeDecodeError:
            raise Damaged("long key is not valid utf-8")
        pos += klen
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
        raise Damaged("body runs past trailer")
    body = unescape_body(data[pos:pos + body_len])
    pos += body_len
    if (sum(body) & 0xFF) != fchk:
        raise Damaged("fchk mismatch")

    if long_key:
        cid = NAME_TO_ID.get(key_text)
    else:
        cid = resolve_short_key(raw_key, revision)
    if mode == MODE_RESET:
        field, unit, canonical = None, None, None
    else:
        field, unit, canonical = field_info(stream_id, cid, key_text)

    rec = {
        "raw_key": raw_key,
        "long_key": long_key,
        "mode": MODE_NAMES[mode],
        "field": field,
        "unit": unit,
        "canonical_id": canonical,
        "wide": wide if mode == MODE_RAW else None,
        "value": None,
        "ext_present": has_ext,
        "extensions": [],
    }
    if long_key:
        rec["key_str"] = key_text

    bpos = 0
    if mode == MODE_RAW:
        size = 4 if wide else 2
        if len(body) < size:
            raise Damaged("raw value truncated")
        signed = unit != "count"
        raw_value = int.from_bytes(body[0:size], "little", signed=signed)
        bpos = size
        rec["raw_value"] = raw_value
        rec["value"] = raw_value
    elif mode == MODE_DELTA:
        delta, bpos, nbytes = read_sleb(body, 0, len(body))
        rec["delta_raw"] = delta
        rec["delta_raw_len"] = nbytes
        rec["value"] = state.cums.get(field, 0) + delta
    elif mode == MODE_DICT:
        if len(body) < 1:
            raise Damaged("dict index truncated")
        idx = body[0]
        bpos = 1
        slot = len(state.resolved) - 1 - idx
        if slot < 0:
            raise Damaged("dict index outside resolved list")
        rec["dict_index"] = idx
        rec["value"] = state.resolved[slot]

    if has_ext:
        if bpos >= len(body):
            raise Damaged("has_ext set but no extension bytes")
        rec["extensions"] = parse_extensions(body, bpos)
    elif bpos != len(body):
        raise Damaged("trailing bytes with has_ext clear")
    return rec, pos


def header_defect(data):
    """Return the error object for the first failing header check, or None."""
    if len(data) < HEADER_SIZE + TRAILER_SIZE or data[0:5] != MAGIC:
        return {"error": "bad_magic"}
    version = data[5]
    if version != VERSION:
        return {"error": "unsupported_version", "version": version}
    for off in (14, 15):
        if data[off] != 0:
            return {"error": "reserved_not_zero", "offset": off}
    rec_count = int.from_bytes(data[11:13], "little")
    frame_space = len(data) - HEADER_SIZE - TRAILER_SIZE
    if rec_count * 5 > frame_space:
        return {"error": "record_count_overflow", "record_count": rec_count}
    expected = zlib.crc32(data[5:16]) & 0xFFFFFFFF
    found = int.from_bytes(data[-TRAILER_SIZE:], "little")
    if expected != found:
        return {"error": "trailer_crc_mismatch", "expected": expected,
                "found": found}
    return None


def read_header(data):
    return {
        "version": data[5],
        "flags_byte": data[6],
        "stream_id": int.from_bytes(data[7:9], "little"),
        "seq_no": int.from_bytes(data[9:11], "little"),
        "rec_count": int.from_bytes(data[11:13], "little"),
        "revision": data[13],
    }


def decode_segment(data, state):
    """Decode a segment whose header is good, updating state."""
    hdr = read_header(data)
    limit = len(data) - TRAILER_SIZE
    off = HEADER_SIZE
    records = []
    for _ in range(hdr["rec_count"]):
        try:
            rec, off = parse_frame(data, off, limit, state,
                                   hdr["stream_id"], hdr["revision"])
        except Damaged:
            break
        state.apply(rec)
        records.append(rec)
    return {
        "magic_ok": True,
        "version": hdr["version"],
        "stream_id": hdr["stream_id"],
        "seq_no": hdr["seq_no"],
        "revision": hdr["revision"],
        "flags": {"stream_continues": bool(hdr["flags_byte"] & 0x01)},
        "record_count": hdr["rec_count"],
        "records": records,
    }


def decode_file(data):
    defect = header_defect(data)
    if defect is not None:
        return defect
    return decode_segment(data, StreamState())


def salvage_file(data):
    defect = header_defect(data)
    stream_id = revision = 0
    if len(data) >= HEADER_SIZE:
        hdr = read_header(data)
        stream_id = hdr["stream_id"]
        revision = hdr["revision"]
    limit = max(len(data) - TRAILER_SIZE, HEADER_SIZE)
    state = StreamState()
    records = []
    damaged = []
    off = HEADER_SIZE
    while off < limit:
        try:
            rec, nxt = parse_frame(data, off, limit, state, stream_id, revision)
        except Damaged as exc:
            start = off
            reason = str(exc)
            scan = off + 1
            resync = limit
            while scan < limit:
                try:
                    rec, nxt = parse_frame(data, scan, limit, state,
                                           stream_id, revision)
                except Damaged:
                    scan += 1
                    continue
                resync = scan
                break
            damaged.append({"from_offset": start, "resync_offset": resync,
                            "reason": reason})
            if resync == limit:
                break
            state.apply(rec)
            records.append(rec)
            off = nxt
            continue
        state.apply(rec)
        records.append(rec)
        off = nxt
    return {
        "records": records,
        "damaged": damaged,
        "header_defect": None if defect is None else defect["error"],
    }


def _trim(value):
    return value.strip() if isinstance(value, str) else value


def decode_stream(manifest):
    runs = {}
    out = []
    for entry in manifest.get("segments", []):
        path = _trim(entry.get("path"))
        with open(path, "rb") as fh:
            data = fh.read()
        hdr = read_header(data)
        sid = hdr["stream_id"]
        continues = bool(hdr["flags_byte"] & 0x01)
        override = entry.get("stream_continues")
        if isinstance(override, bool):
            continues = override
        run = runs.get(sid)
        if run is None:
            state = StreamState()
            out.append(decode_segment(data, state))
            if continues:
                runs[sid] = {"state": state, "last_seq": hdr["seq_no"]}
        elif hdr["seq_no"] > run["last_seq"]:
            out.append(decode_segment(data, run["state"]))
            run["last_seq"] = hdr["seq_no"]
            if not continues:
                del runs[sid]
        else:
            out.append(decode_segment(data, run["state"].copy()))
    return {"segments": out}


def main(argv):
    if len(argv) == 3 and argv[1] == "--stream":
        with open(argv[2], "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        doc = decode_stream(manifest)
    elif len(argv) == 3 and argv[1] == "--salvage":
        with open(argv[2], "rb") as fh:
            doc = salvage_file(fh.read())
    elif len(argv) == 2:
        with open(argv[1], "rb") as fh:
            doc = decode_file(fh.read())
    else:
        sys.stderr.write(
            "usage: decode.py [--stream manifest.json | --salvage file.varc"
            " | file.varc]\n")
        return 2
    sys.stdout.write(json.dumps(doc) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
