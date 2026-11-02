#!/usr/bin/env python3
"""SEALB container decoder (KMS-9 envelope daemon, format v1.0).

Reads a .nnc capture and prints a single JSON object to stdout: either the
decoded document or one of the documented error objects. Always exits 0.

Grammar (from SEALB-container-format.md):
  header  magic[5]="SEALB", base_value i32 LE, flags u8, version u8 (=3),
          reserved[3]=0, record_count u16 LE
  body    record_count records back-to-back
  trailer u32 LE = zlib.crc32 over (header bytes after the magic) + body
  record  selector u8: bit3|bit7<<1 = mode (2 raw, 1 delta, 0 dict), bit0 =
          WIDE_VALUE (raw only), bit5 = LONG_KEY, bits 1,2,4,6 reserved
  key     u8 (short) or uvarint length + UTF-8 bytes (long)
  payload raw: i32/i16 LE signed; delta: signed LEB128 added to the running
          value; dict: u8 forward index into the resolved-value dictionary

Situations the specification leaves open, resolved here by the rule that any
byte the decoded document cannot carry cannot round-trip byte for byte, so the
container is rejected as truncated_record (the only remaining documented
error string):
  1. valid magic but too few bytes to hold the version byte;
  2. valid magic and version but shorter than header + trailer;
  3. nonzero reserved header bytes (11..13);
  4. nonzero reserved flag bits (flags bits 1..7);
  5. WIDE_VALUE set on a non-raw record;
  6. body bytes left over after the last record (record_count 0 with a
     non-empty body included);
  7. a long key whose bytes are not valid UTF-8;
  8. a varint that runs off the end of the body or exceeds 10 bytes.
"""
import json
import struct
import sys
import zlib

MAGIC = bytes([0x53, 0x45, 0x41, 0x4C, 0x42])
SUPPORTED_VERSION = 3
HEADER_SIZE = 16
TRAILER_SIZE = 4
MAGIC_SIZE = 5

MODE_RAW = 2
MODE_DELTA = 1
MODE_DICT = 0

SEL_MODE_LOW_BIT = 3   # contributes 1
SEL_MODE_HIGH_BIT = 7  # contributes 2
SEL_WIDE_BIT = 0
SEL_LONG_KEY_BIT = 5
SEL_RESERVED_MASK = 0xFF & ~(
    (1 << SEL_MODE_LOW_BIT) | (1 << SEL_MODE_HIGH_BIT) |
    (1 << SEL_WIDE_BIT) | (1 << SEL_LONG_KEY_BIT)
)

# Structural limits: a varint longer than this is malformed, not merely long.
MAX_VARINT_BYTES = 10


class Malformed(Exception):
    """Any body/header structure problem reported as truncated_record."""


def error_obj(code, version=None):
    obj = {"error": code}
    if version is not None:
        obj["version"] = version
    return obj


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")))
    sys.stdout.write("\n")


def read_uvarint(data, pos):
    """Unsigned LEB128 (7 bits/byte, high bit = continue)."""
    result = 0
    shift = 0
    count = 0
    while True:
        if pos >= len(data):
            raise Malformed()
        byte = data[pos]
        pos += 1
        count += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        if count >= MAX_VARINT_BYTES:
            raise Malformed()
        shift += 7


def read_svarint(data, pos):
    """Signed LEB128: payload sign-extended from the final byte."""
    result = 0
    shift = 0
    count = 0
    while True:
        if pos >= len(data):
            raise Malformed()
        byte = data[pos]
        pos += 1
        count += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not (byte & 0x80):
            if byte & 0x40:
                result -= 1 << shift
            return result, pos
        if count >= MAX_VARINT_BYTES:
            raise Malformed()


def decode_records(body, record_count, base_value):
    records = []
    running = base_value
    dictionary = []
    pos = 0
    for _ in range(record_count):
        if pos >= len(body):
            raise Malformed()
        selector = body[pos]
        pos += 1
        if selector & SEL_RESERVED_MASK:
            raise Malformed()
        mode = (1 if selector & (1 << SEL_MODE_LOW_BIT) else 0) + \
               (2 if selector & (1 << SEL_MODE_HIGH_BIT) else 0)
        wide = bool(selector & (1 << SEL_WIDE_BIT))
        long_key = bool(selector & (1 << SEL_LONG_KEY_BIT))
        if mode not in (MODE_RAW, MODE_DELTA, MODE_DICT):
            raise Malformed()
        if wide and mode != MODE_RAW:
            # WIDE_VALUE is defined for raw records only.
            raise Malformed()
        if long_key:
            length, pos = read_uvarint(body, pos)
            if pos + length > len(body):
                raise Malformed()
            raw_key = body[pos:pos + length]
            pos += length
            try:
                key = raw_key.decode("utf-8")
            except UnicodeDecodeError:
                raise Malformed()
        else:
            if pos >= len(body):
                raise Malformed()
            key = body[pos]
            pos += 1

        rec = {"key": key, "mode": {MODE_RAW: "raw", MODE_DELTA: "delta",
                                   MODE_DICT: "dict"}[mode],
               "wide_value": wide, "long_key": long_key}
        if mode == MODE_RAW:
            if wide:
                if pos + 4 > len(body):
                    raise Malformed()
                value = struct.unpack_from("<i", body, pos)[0]
                pos += 4
            else:
                if pos + 2 > len(body):
                    raise Malformed()
                value = struct.unpack_from("<h", body, pos)[0]
                pos += 2
            rec["raw_value"] = value
            rec["value"] = value
            running = value
        elif mode == MODE_DELTA:
            delta, pos = read_svarint(body, pos)
            rec["delta_raw"] = delta
            running = running + delta
            rec["value"] = running
        else:
            if pos >= len(body):
                raise Malformed()
            index = body[pos]
            pos += 1
            if index >= len(dictionary):
                raise Malformed()
            rec["dict_index"] = index
            running = dictionary[index]
            rec["value"] = running
        dictionary.append(running)
        records.append(rec)
    if pos != len(body):
        # Body must hold exactly record_count records back-to-back.
        raise Malformed()
    return records


def decode_bytes(data):
    """Return (document_dict, None) or (None, error_dict)."""
    if len(data) < MAGIC_SIZE or data[:MAGIC_SIZE] != MAGIC:
        return None, error_obj("bad_magic")
    if len(data) <= 10:
        # Header too short to hold the version byte: magic already accepted,
        # so the file is structurally truncated.
        return None, error_obj("truncated_record")
    version = data[10]
    if version != SUPPORTED_VERSION:
        return None, error_obj("unsupported_version", version=version)
    if len(data) < HEADER_SIZE + TRAILER_SIZE:
        return None, error_obj("truncated_record")
    expected = zlib.crc32(data[MAGIC_SIZE:len(data) - TRAILER_SIZE]) & 0xFFFFFFFF
    stored = struct.unpack_from("<I", data, len(data) - TRAILER_SIZE)[0]
    if expected != stored:
        return None, error_obj("trailer_crc_mismatch")
    base_value = struct.unpack_from("<i", data, 5)[0]
    flags = data[9]
    if flags & 0xFE:
        # Bits 1..7 of the flag byte are reserved and must be zero.
        return None, error_obj("truncated_record")
    if data[11] != 0 or data[12] != 0 or data[13] != 0:
        # Reserved header bytes must be 0x00 0x00 0x00.
        return None, error_obj("truncated_record")
    record_count = struct.unpack_from("<H", data, 14)[0]
    body = data[HEADER_SIZE:len(data) - TRAILER_SIZE]
    try:
        records = decode_records(body, record_count, base_value)
    except Malformed:
        return None, error_obj("truncated_record")
    doc = {
        # Document shape version (the container's version byte is fixed at 3
        # by the check above; the printed document reports shape version 1).
        "version": 1,
        "flags": {"reserved_bit_0": bool(flags & 0x01)},
        "record_count": record_count,
        "base_value": base_value,
        "records": records,
    }
    return doc, None


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: decode.py <input.nnc>\n")
        return 2
    try:
        with open(argv[1], "rb") as handle:
            data = handle.read()
    except OSError:
        # Unreadable input yields no bytes at all, so no magic can be present.
        data = b""
    doc, err = decode_bytes(data)
    emit(doc if doc is not None else err)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
