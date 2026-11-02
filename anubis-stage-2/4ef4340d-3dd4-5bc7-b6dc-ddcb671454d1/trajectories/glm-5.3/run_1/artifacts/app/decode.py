#!/usr/bin/env python3
"""POLYP container decoder.

Usage: python3 decode.py <input.vcm>

Prints one JSON object (the decoded document, or the specification's error
object) to stdout and exits 0.
"""
import json
import struct
import sys
import zlib

MAGIC = bytes([0x4E, 0x55, 0x4D, 0x50, 0x4B])
SUPPORTED_VERSION = 1
HEADER_SIZE = 16
TRAILER_SIZE = 4
WIDE_BIT = 0x01          # selector bit 0: 32-bit raw payload
MODE_BIT_LOW = 0x04      # selector bit 2: contributes 1 to the mode number
MODE_BIT_HIGH = 0x20     # selector bit 5: contributes 2 to the mode number
LONG_KEY_BIT = 0x80      # selector bit 7: varint-length UTF-8 key
FORBIDDEN_SELECTOR_MASK = 0x5A   # selector bits 1, 3, 4, 6 must be 0


class Rejected(Exception):
    """Body/header content is malformed: reported as truncated_record."""


def read_uvarint(buf, pos):
    """Read one unsigned LEB128 varint. Returns (value, new_pos) or None."""
    result = 0
    shift = 0
    count = 0
    while True:
        if pos >= len(buf):
            return None
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
        count += 1
        # Ten bytes is the widest encoding a 64-bit value can need; anything
        # longer is not a varint this format can carry.
        if count >= 10:
            return None


def decode(data):
    """Decode POLYP bytes into the JSON document, or an error object."""
    # Error precedence: bad magic, unsupported version, trailer CRC, then
    # any malformed/truncated record or header-field violation.
    if len(data) < 5 or bytes(data[:5]) != MAGIC:
        return {"error": "bad_magic"}
    if len(data) >= 13 and data[12] != SUPPORTED_VERSION:
        return {"error": "unsupported_version", "version": data[12]}
    if len(data) < HEADER_SIZE + TRAILER_SIZE:
        return {"error": "truncated_record"}
    trailer = bytes(data[-TRAILER_SIZE:])
    computed = zlib.crc32(bytes(data[5:-TRAILER_SIZE])) & 0xFFFFFFFF
    if struct.pack("<I", computed) != trailer:
        return {"error": "trailer_crc_mismatch"}

    base_value = struct.unpack("<i", data[5:9])[0]
    record_count = struct.unpack("<H", data[9:11])[0]
    flags = data[11]
    reserved = data[13:16]

    # Spec-mandated header constraints: flag bits 1..7 and the reserved
    # bytes must be zero. A violation cannot be represented in the document
    # shape (which carries only reserved_bit_0), so the file is rejected.
    if (flags & 0xFE) != 0 or bytes(reserved) != b"\x00\x00\x00":
        return {"error": "truncated_record"}

    body = data[HEADER_SIZE:-TRAILER_SIZE]
    try:
        records = decode_records(body, record_count, base_value)
    except Rejected:
        return {"error": "truncated_record"}

    return {
        "version": data[12],
        "flags": {"reserved_bit_0": bool(flags & 1)},
        "record_count": record_count,
        "base_value": base_value,
        "records": records,
    }


def decode_records(body, record_count, base_value):
    """Decode record_count records; raises Rejected on any malformed record."""
    pos = 0
    running = base_value
    dictionary = []
    records = []
    for _ in range(record_count):
        if pos >= len(body):
            raise Rejected("selector")
        selector = body[pos]
        pos += 1
        if selector & FORBIDDEN_SELECTOR_MASK:
            raise Rejected("selector bits")
        mode_num = 0
        if selector & MODE_BIT_LOW:
            mode_num += 1
        if selector & MODE_BIT_HIGH:
            mode_num += 2
        wide_value = bool(selector & WIDE_BIT)
        long_key = bool(selector & LONG_KEY_BIT)
        if mode_num == 3:
            raise Rejected("unknown mode")
        if long_key:
            r = read_uvarint(body, pos)
            if r is None:
                raise Rejected("key length")
            key_len, pos = r
            if pos + key_len > len(body):
                raise Rejected("key bytes")
            key_bytes = bytes(body[pos:pos + key_len])
            pos += key_len
            try:
                key = key_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raise Rejected("key is not UTF-8")
        else:
            if pos >= len(body):
                raise Rejected("short key")
            key = body[pos]
            pos += 1

        if mode_num == 0:
            width = 4 if wide_value else 2
            if pos + width > len(body):
                raise Rejected("raw payload")
            if width == 2:
                raw_value = struct.unpack("<h", body[pos:pos + 2])[0]
            else:
                raw_value = struct.unpack("<i", body[pos:pos + 4])[0]
            pos += width
            running = raw_value
            records.append({
                "key": key,
                "mode": "raw",
                "wide_value": wide_value,
                "long_key": long_key,
                "raw_value": raw_value,
                "value": raw_value,
            })
        elif mode_num == 1:
            r = read_uvarint(body, pos)
            if r is None:
                raise Rejected("delta payload")
            encoded, pos = r
            delta_raw = (encoded >> 1) ^ -(encoded & 1)
            running = running + delta_raw
            records.append({
                "key": key,
                "mode": "delta",
                "wide_value": wide_value,
                "long_key": long_key,
                "delta_raw": delta_raw,
                "value": running,
            })
        else:
            if pos >= len(body):
                raise Rejected("dictionary index")
            dict_index = body[pos]
            pos += 1
            if dict_index > len(dictionary) - 1:
                raise Rejected("dictionary index out of range")
            running = dictionary[len(dictionary) - 1 - dict_index]
            records.append({
                "key": key,
                "mode": "dict",
                "wide_value": wide_value,
                "long_key": long_key,
                "dict_index": dict_index,
                "value": running,
            })
        # Every resolved value grows the dictionary by one entry.
        dictionary.append(running)

    if pos != len(body):
        # Bytes left over after the last record: the body does not hold
        # exactly record_count records back-to-back.
        raise Rejected("trailing body bytes")
    return records


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: decode.py <input.vcm>\n")
        return 2
    try:
        with open(argv[1], "rb") as fh:
            data = fh.read()
    except OSError as exc:
        sys.stderr.write("decode.py: cannot read %s: %s\n" % (argv[1], exc))
        return 1
    document = decode(data)
    sys.stdout.write(json.dumps(document, separators=(",", ":")))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
