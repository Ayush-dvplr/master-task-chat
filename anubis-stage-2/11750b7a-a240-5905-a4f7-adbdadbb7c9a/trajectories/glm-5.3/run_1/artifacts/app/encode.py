#!/usr/bin/env python3
"""SEALB container encoder (KMS-9 envelope daemon, format v1.0).

Reads a JSON document in the shape produced by decode.py and writes the
container it came from, byte for byte.
"""
import json
import struct
import sys
import zlib

MAGIC = bytes([0x53, 0x45, 0x41, 0x4C, 0x42])
SUPPORTED_VERSION = 3
HEADER_SIZE = 16
TRAILER_SIZE = 4

MODE_IDS = {"raw": 2, "delta": 1, "dict": 0}
SEL_MODE_LOW_BIT = 3   # contributes 1
SEL_MODE_HIGH_BIT = 7  # contributes 2
SEL_WIDE_BIT = 0
SEL_LONG_KEY_BIT = 5


def write_uvarint(value):
    if value < 0:
        raise ValueError("uvarint cannot be negative")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def write_svarint(value):
    """Signed LEB128, minimal."""
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        sign_bit = bool(byte & 0x40)
        done = (value == 0 and not sign_bit) or (value == -1 and sign_bit)
        if done:
            out.append(byte)
            return bytes(out)
        out.append(byte | 0x80)


def encode_record(rec):
    mode_name = rec.get("mode")
    if mode_name is None:
        # Infer the mode from the pre-resolution payload the record carries.
        for candidate in ("raw_value", "delta_raw", "dict_index"):
            if candidate in rec:
                mode_name = {"raw_value": "raw", "delta_raw": "delta",
                             "dict_index": "dict"}[candidate]
                break
    mode = MODE_IDS[mode_name]
    key = rec["key"]
    if "long_key" in rec:
        long_key = bool(rec["long_key"])
    else:
        long_key = isinstance(key, str)
    if "wide_value" in rec:
        wide = bool(rec["wide_value"])
    elif mode == 2:
        wide = not (-32768 <= rec["raw_value"] <= 32767)
    else:
        wide = False
    selector = 0
    if mode & 1:
        selector |= 1 << SEL_MODE_LOW_BIT
    if mode & 2:
        selector |= 1 << SEL_MODE_HIGH_BIT
    if long_key:
        selector |= 1 << SEL_LONG_KEY_BIT
    if wide:
        if mode != 2:
            raise ValueError("wide_value set on non-raw record")
        selector |= 1 << SEL_WIDE_BIT
    out = bytearray([selector])
    if long_key:
        if not isinstance(key, str):
            raise ValueError("long_key record requires a string key")
        key_bytes = key.encode("utf-8")
        out += write_uvarint(len(key_bytes))
        out += key_bytes
    else:
        if isinstance(key, bool) or not isinstance(key, int):
            raise ValueError("short key must be an integer")
        if not 0 <= key <= 255:
            raise ValueError("short key out of range")
        out.append(key)
    if mode == 2:
        raw_value = rec["raw_value"]
        if wide:
            out += struct.pack("<i", raw_value)
        else:
            out += struct.pack("<h", raw_value)
    elif mode == 1:
        out += write_svarint(rec["delta_raw"])
    else:
        index = rec["dict_index"]
        if not 0 <= index <= 255:
            raise ValueError("dict_index out of range")
        out.append(index)
    return bytes(out)


def encode_document(doc):
    header = bytearray()
    header += MAGIC
    header += struct.pack("<i", doc["base_value"])
    flags_obj = doc.get("flags", {})
    reserved_bit_0 = flags_obj.get("reserved_bit_0", False)
    header.append(0x01 if reserved_bit_0 else 0x00)
    header.append(SUPPORTED_VERSION)
    header += b"\x00\x00\x00"
    records = doc.get("records", [])
    record_count = doc.get("record_count", len(records))
    if record_count != len(records):
        raise ValueError("record_count does not match the records array")
    header += struct.pack("<H", record_count)
    body = bytearray()
    for rec in records:
        body += encode_record(rec)
    crc = zlib.crc32(bytes(header[5:]) + bytes(body)) & 0xFFFFFFFF
    return bytes(header) + bytes(body) + struct.pack("<I", crc)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: encode.py <document.json> <output.nnc>\n")
        return 2
    with open(argv[1], "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    data = encode_document(doc)
    with open(argv[2], "wb") as handle:
        handle.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
