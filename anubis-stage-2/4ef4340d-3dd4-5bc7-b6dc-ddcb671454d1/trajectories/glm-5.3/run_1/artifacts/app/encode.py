#!/usr/bin/env python3
"""POLYP container encoder.

Usage: python3 encode.py <document.json> <output.vcm>

Reads a JSON document in the shape the decoder prints and writes the
container it came from (byte for byte).
"""
import json
import struct
import sys
import zlib

MAGIC = bytes([0x4E, 0x55, 0x4D, 0x50, 0x4B])
SUPPORTED_VERSION = 1
WIDE_BIT = 0x01
MODE_BIT_LOW = 0x04
MODE_BIT_HIGH = 0x20
LONG_KEY_BIT = 0x80
MODE_NUMBERS = {"raw": 0, "delta": 1, "dict": 2}


def write_uvarint(value):
    """Write one unsigned LEB128 varint (minimal encoding)."""
    if value < 0:
        raise ValueError("varint value must be non-negative")
    out = bytearray()
    while True:
        group = value & 0x7F
        value >>= 7
        if value:
            out.append(group | 0x80)
        else:
            out.append(group)
            return bytes(out)


def zigzag_encode(n):
    return (n << 1) ^ (n >> 63) if n < 0 else (n << 1)


def _fits_i16(value):
    return -0x8000 <= int(value) <= 0x7FFF


def encode(document):
    records = document["records"]
    record_count = document.get("record_count", len(records))
    if len(records) != record_count:
        raise ValueError("record_count does not match the records array")
    if int(document.get("version", SUPPORTED_VERSION)) != SUPPORTED_VERSION:
        raise ValueError("unsupported version")

    flags_obj = document.get("flags") or {}
    flags = 1 if flags_obj.get("reserved_bit_0") else 0

    body = bytearray()
    running = document["base_value"]
    dictionary = []
    for record in records:
        mode = record["mode"]
        mode_num = MODE_NUMBERS.get(mode)
        if mode_num is None:
            raise ValueError("unknown record mode: %r" % (mode,))
        selector = 0
        if mode_num & 1:
            selector |= MODE_BIT_LOW
        if mode_num & 2:
            selector |= MODE_BIT_HIGH

        key = record["key"]
        # Honour an explicit flag bit; otherwise infer it from the key type /
        # payload width so a document can still be rebuilt exactly.
        long_key = record.get("long_key")
        if long_key is None:
            long_key = isinstance(key, str)

        if mode == "raw":
            raw_value = record.get("raw_value", record.get("value"))
            if raw_value is None:
                raise ValueError("raw record is missing raw_value")
            if record.get("wide_value") is None:
                wide_value = not _fits_i16(raw_value)
            else:
                wide_value = bool(record.get("wide_value"))
        else:
            wide_value = bool(record.get("wide_value"))
        if wide_value:
            selector |= WIDE_BIT
        if long_key:
            selector |= LONG_KEY_BIT
        body.append(selector)

        if long_key:
            key_bytes = key.encode("utf-8") if isinstance(key, str) else str(key).encode("utf-8")
            body += write_uvarint(len(key_bytes))
            body += key_bytes
        else:
            body.append(int(key) & 0xFF)

        if mode == "raw":
            if wide_value:
                body += struct.pack("<i", raw_value)
            else:
                body += struct.pack("<h", raw_value)
            running = raw_value
        elif mode == "delta":
            delta_raw = record.get("delta_raw")
            if delta_raw is None:
                # Fall back to the difference the record resolved to.
                delta_raw = record["value"] - running
            body += write_uvarint(zigzag_encode(int(delta_raw)))
            running = running + int(delta_raw)
        else:
            dict_index = record.get("dict_index")
            if dict_index is None:
                # Fall back to the most recent matching dictionary entry.
                dict_index = next((len(dictionary) - 1 - i
                                   for i, v in enumerate(reversed(dictionary))
                                   if v == record["value"]), None)
            if dict_index is None or dict_index < 0 or dict_index > len(dictionary) - 1:
                raise ValueError("dict record has no usable dictionary index")
            body.append(int(dict_index) & 0xFF)
            running = dictionary[len(dictionary) - 1 - int(dict_index)]
        dictionary.append(running)

    header = bytearray()
    header += MAGIC
    header += struct.pack("<i", document["base_value"])
    header += struct.pack("<H", record_count)
    header.append(flags)
    header.append(SUPPORTED_VERSION)
    header += b"\x00\x00\x00"

    payload = bytes(header) + bytes(body)
    trailer = struct.pack("<I", zlib.crc32(payload[5:]) & 0xFFFFFFFF)
    return payload + trailer


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: encode.py <document.json> <output.vcm>\n")
        return 2
    try:
        with open(argv[1], "r", encoding="utf-8") as fh:
            document = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.stderr.write("encode.py: cannot read %s: %s\n" % (argv[1], exc))
        return 1
    try:
        blob = encode(document)
    except (KeyError, TypeError, ValueError, struct.error) as exc:
        sys.stderr.write("encode.py: cannot encode document: %s\n" % (exc,))
        return 1
    try:
        with open(argv[2], "wb") as fh:
            fh.write(blob)
    except OSError as exc:
        sys.stderr.write("encode.py: cannot write %s: %s\n" % (argv[2], exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
