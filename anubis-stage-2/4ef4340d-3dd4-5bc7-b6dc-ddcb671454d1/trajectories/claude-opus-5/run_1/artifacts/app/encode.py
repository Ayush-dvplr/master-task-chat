import json
import struct
import sys
import zlib

MAGIC = bytes.fromhex("4e554d504b")
MODE_BITS = (2, 5)
WIDE_BIT = 0
LONG_KEY_BIT = 7
MODE_IDS = {"raw": 0, "delta": 1, "dict": 2}


def uvarint(n):
    if n < 0:
        raise ValueError("negative uvarint")
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def encode_record(rec):
    mode = MODE_IDS[rec["mode"]]
    long_key = bool(rec.get("long_key", isinstance(rec["key"], str)))
    wide = bool(rec.get("wide_value", False))
    selector = ((mode & 1) << MODE_BITS[0]) | ((mode >> 1 & 1) << MODE_BITS[1])
    if wide:
        selector |= 1 << WIDE_BIT
    if long_key:
        selector |= 1 << LONG_KEY_BIT
    out = bytearray([selector])
    key = rec["key"]
    if long_key:
        kb = str(key).encode("utf-8")
        out += uvarint(len(kb)) + kb
    else:
        out.append(int(key))
    if mode == 0:
        out += struct.pack("<i" if wide else "<h", rec["raw_value"])
    elif mode == 1:
        d = rec["delta_raw"]
        out += uvarint(2 * d if d >= 0 else -2 * d - 1)
    else:
        out.append(rec["dict_index"])
    return bytes(out)


def encode(doc):
    flags = 1 if doc.get("flags", {}).get("reserved_bit_0") else 0
    records = doc["records"]
    count = doc.get("record_count", len(records))
    header = struct.pack("<iHBB", doc["base_value"], count, flags, doc.get("version", 1)) + b"\x00\x00\x00"
    body = b"".join(encode_record(r) for r in records)
    covered = header + body
    return MAGIC + covered + struct.pack("<I", zlib.crc32(covered) & 0xFFFFFFFF)


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        doc = json.load(f)
    with open(sys.argv[2], "wb") as f:
        f.write(encode(doc))


if __name__ == "__main__":
    main()
