import json
import struct
import sys
import zlib

MAGIC = b"SEALB"
MODE_IDS = {"raw": 2, "delta": 1, "dict": 0}


def uvarint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def sleb128(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if (n == 0 and not b & 0x40) or (n == -1 and b & 0x40):
            out.append(b)
            return bytes(out)
        out.append(b | 0x80)


def encode_record(rec):
    mode_id = MODE_IDS[rec["mode"]]
    long_key = rec["long_key"]
    wide = rec["wide_value"]
    sel = ((mode_id & 1) << 3) | (((mode_id >> 1) & 1) << 7)
    if wide:
        sel |= 0x01
    if long_key:
        sel |= 0x20
    out = bytearray([sel])
    if long_key:
        kb = rec["key"].encode("utf-8")
        out += uvarint(len(kb)) + kb
    else:
        out.append(rec["key"])
    if mode_id == 2:
        out += struct.pack("<i" if wide else "<h", rec["raw_value"])
    elif mode_id == 1:
        out += sleb128(rec["delta_raw"])
    else:
        out.append(rec["dict_index"])
    return bytes(out)


def encode(doc):
    flags = 1 if doc["flags"]["reserved_bit_0"] else 0
    covered = bytearray()
    covered += struct.pack("<i", doc["base_value"])
    covered.append(flags)
    covered.append(doc["version"])
    covered += b"\x00\x00\x00"
    covered += struct.pack("<H", doc["record_count"])
    for rec in doc["records"]:
        covered += encode_record(rec)
    return MAGIC + bytes(covered) + struct.pack("<I", zlib.crc32(covered))


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        doc = json.load(f)
    with open(sys.argv[2], "wb") as f:
        f.write(encode(doc))


if __name__ == "__main__":
    main()
