#!/usr/bin/env python3
"""Coredrop postmortem pipeline: legacy MDUMP decoder.

Written against revision 1 of the MDUMP container specification and kept in
the pipeline since then. It has not been updated for revisions 2 or 3, and
triage has traced several mis-decoded crash dumps back to it. Where this file
and the current container format specification disagree, the specification
is right and this file is wrong.

usage: python3 MDUMP-legacy-decoder.py <capture>
"""
import json
import struct
import sys
import zlib

MAGIC = b"COREZ"
HEADER = struct.Struct("<5sH3sBiB")   # magic, record_count, reserved, flags, base_value, version
MODES = {0: "dict", 1: "raw", 2: "delta"}


class Bad(Exception):
    pass


def uvarint(buf, pos):
    value = shift = 0
    while True:
        if pos >= len(buf):
            raise Bad("truncated_record")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, pos


def svarint(buf, pos):
    value = shift = 0
    while True:
        if pos >= len(buf):
            raise Bad("truncated_record")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            if byte & 0x40:
                value -= 1 << shift
            return value, pos


def decode(blob):
    if blob[:5] != MAGIC:
        return {"error": "bad_magic"}
    if zlib.crc32(blob[5:-4]) & 0xFFFFFFFF != struct.unpack("<I", blob[-4:])[0]:
        return {"error": "trailer_crc_mismatch"}
    _, count, reserved, flags, base, version = HEADER.unpack(blob[:16])
    if version != 1:
        return {"error": "unsupported_version", "version": version}
    if reserved != b"\x00\x00\x00":
        return {"error": "unsupported_version", "version": version}
    body = blob[16:-4]
    pos, running, table, records = 0, base, [], []
    try:
        for _ in range(count):
            sel = body[pos]
            pos += 1
            mode = MODES.get((sel & 1) | ((sel >> 2) & 2))
            if mode is None:
                raise Bad("truncated_record")
            long_key = bool(sel & 0x40)
            if long_key:
                size, pos = uvarint(body, pos)
                key = body[pos:pos + size].decode("utf-8", errors="replace")
                pos += size
            else:
                key = body[pos]
                pos += 1
            rec = {"key": key, "mode": mode, "long_key": long_key}
            if mode == "raw":
                wide = bool(sel & 0x10)
                if wide:
                    running = struct.unpack("<i", body[pos:pos + 4])[0]
                    pos += 4
                else:
                    running = struct.unpack("<H", body[pos:pos + 2])[0]
                    pos += 2
                rec.update(wide_value=wide, raw_value=running)
                table.append(running)
            elif mode == "delta":
                step, pos = svarint(body, pos)
                running += step
                rec["delta_raw"] = step
                table.append(step)
            else:
                index = body[pos]
                pos += 1
                running = table[len(table) - 1 - index]
                rec["dict_index"] = index
                table.append(index)
            rec["value"] = running
            records.append(rec)
    except (Bad, IndexError, struct.error):
        return {"error": "truncated_record"}
    return {"version": version, "flags": {"reserved_bit_0": bool(flags & 1)},
            "record_count": count, "base_value": base, "records": records}


if __name__ == "__main__":
    with open(sys.argv[1], "rb") as handle:
        print(json.dumps(decode(handle.read())))
