#!/usr/bin/env python3
"""MDUMP crash-dump encoder.

Reads a decoded document (the shape decode.py prints) and writes the capture
it came from, byte for byte. A document whose derived `offset` or `value`
fields disagree with its own records was edited by hand: no capture is
written, one JSON error object is printed and the exit status is 1.

usage: python3 encode.py <document.json> <capture>
"""
import json
import sys

MAGIC = b"COREZ"
FLAG_BITS = (("reserved_bit_0", 0), ("front_coded_keys", 1),
             ("big_endian_raw", 2), ("whitened", 3))

_CRC_TABLES = {}


def _crc_table(poly):
    table = _CRC_TABLES.get(poly)
    if table is None:
        table = []
        for i in range(256):
            x = i
            for _ in range(8):
                x = (x >> 1) ^ poly if x & 1 else x >> 1
            table.append(x)
        _CRC_TABLES[poly] = table
    return table


def crc_reflected(data, poly, init, xorout):
    table = _crc_table(poly)
    crc = init
    for b in data:
        crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ xorout


def keystream(seed, tap, zero_sub, count):
    """Low byte of a 24-bit Galois LFSR after every eight clocks."""
    reg = seed if seed else zero_sub
    out = bytearray()
    for _ in range(count):
        for _ in range(8):
            reg = (reg >> 1) ^ tap if reg & 1 else reg >> 1
        out.append(reg & 0xFF)
    return bytes(out)


def s32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def zigzag_enc(value):
    return value << 1 if value >= 0 else (-value << 1) - 1


def _sel_reserved(mode_hi_bit):
    """Selector bits that must be zero: all but mode, WIDE_VALUE, LONG_KEY."""
    return 0xFF & ~(1 | (1 << mode_hi_bit) | 0x10 | 0x40)


def _repeat_v1(running, last_delta, count):
    return running + last_delta * count


def _repeat_v2(running, last_delta, count):
    return running + last_delta * (count + 1)


PROFILES = {
    1: {
        "ks_tap": 0xE10000, "ks_zero": 0xC0FFEE, "ks_fold": False,
        "crc_poly": 0x82F63B78, "crc_init": 0xFFFFFFFF,
        "crc_xorout": 0xFFFFFFFF, "crc_start": 5,
        "dict_cap": 40, "dict_append": "payload", "dict_dir": "backward",
        "dict_mtf": True, "repeat": _repeat_v1, "delta": "sleb128",
        "mode_hi_bit": 3, "sel_reserved": _sel_reserved(3),
    },
    2: {
        "ks_tap": 0xD20400, "ks_zero": 0x5A17C3, "ks_fold": False,
        "crc_poly": 0x82F63B78, "crc_init": 0xFFFFFFFF,
        "crc_xorout": 0xFFFFFFFF, "crc_start": 0,
        "dict_cap": 24, "dict_append": "value", "dict_dir": "backward",
        "dict_mtf": True, "repeat": _repeat_v2, "delta": "sleb128",
        "mode_hi_bit": 3, "sel_reserved": _sel_reserved(3),
    },
    3: {
        "ks_tap": 0xD20400, "ks_zero": 0x5A17C3, "ks_fold": True,
        "crc_poly": 0xA2E1C19B, "crc_init": 0x00000000,
        "crc_xorout": 0xFFFFFFFF, "crc_start": 0,
        "dict_cap": 32, "dict_append": "value", "dict_dir": "forward",
        "dict_mtf": False, "repeat": _repeat_v2, "delta": "zigzag",
        "mode_hi_bit": 2, "sel_reserved": _sel_reserved(2),
    },
}


def seed_for(prof, salt, base_value):
    if prof["ks_fold"]:
        salt ^= base_value & 0xFFFFFF
    return salt & 0xFFFFFF


def whiten(prof, salt, base_value, body):
    ks = keystream(seed_for(prof, salt, base_value), prof["ks_tap"],
                   prof["ks_zero"], len(body))
    return bytes(a ^ b for a, b in zip(body, ks))


def crc_of(prof, header, body):
    return crc_reflected(header[prof["crc_start"]:16] + body, prof["crc_poly"],
                         prof["crc_init"], prof["crc_xorout"])


MODE_IDS = {"dict": 0, "raw": 1, "delta": 2, "repeat": 3}


class Inconsistent(Exception):
    """A document whose derived fields do not match its own records."""

    def __init__(self, record_index, field):
        super().__init__(field)
        self.obj = {"error": "inconsistent_document",
                    "record_index": record_index, "field": field}


def enc_uvarint(value):
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if not value:
            out.append(b)
            return bytes(out)
        out.append(b | 0x80)


def enc_delta(value, pad, kind):
    out = bytearray()
    if kind == "sleb128":
        filler = 0x7F if value < 0 else 0x00
        while True:
            b = value & 0x7F
            value >>= 7
            out.append(b)
            if (value == 0 and not b & 0x40) or (value == -1 and b & 0x40):
                break
            out[-1] |= 0x80
    else:
        filler = 0x00
        out += enc_uvarint(zigzag_enc(value))
    if pad:
        out[-1] |= 0x80
        out += bytes([filler | 0x80]) * (pad - 1)
        out.append(filler)
    return bytes(out)


def encode(doc):
    """Returns the capture bytes for a document, or raises Inconsistent."""
    prof = PROFILES[doc["version"]]
    flags = doc["flags"]
    flags_byte = 0
    for name, bit in FLAG_BITS:
        if flags[name]:
            flags_byte |= 1 << bit
    header = bytearray(MAGIC)
    header += (doc["record_count"] & 0xFFFF).to_bytes(2, "little")
    header += (doc["salt"] & 0xFFFFFF).to_bytes(3, "little")
    header.append(flags_byte)
    header += (doc["base_value"] & 0xFFFFFFFF).to_bytes(4, "little")
    header.append(doc["version"])

    front = flags["front_coded_keys"]
    byteorder = "big" if flags["big_endian_raw"] else "little"
    body = bytearray()
    running = doc["base_value"]
    last_delta = None
    table = []
    for idx, rec in enumerate(doc["records"]):
        if rec["offset"] != len(body):
            raise Inconsistent(idx, "offset")
        mode = rec["mode"]
        mode_id = MODE_IDS[mode]
        wide = mode == "raw" and rec["wide_value"]
        sel = (mode_id & 1) | ((mode_id >> 1) << prof["mode_hi_bit"])
        if wide:
            sel |= 0x10
        if rec["long_key"]:
            sel |= 0x40
        body.append(sel)

        if not rec["long_key"]:
            body.append(rec["key"])
        else:
            key_bytes = rec["key"].encode("utf-8")
            prefix = rec["key_prefix"] if front else 0
            if front:
                body += enc_uvarint(prefix)
            body += enc_uvarint(len(key_bytes) - prefix)
            body += key_bytes[prefix:]

        if mode == "raw":
            width = 4 if wide else 2
            body += (rec["raw_value"] & (1 << 8 * width) - 1).to_bytes(
                width, byteorder)
            running = s32(rec["raw_value"])
            payload = rec["raw_value"]
        elif mode == "delta":
            body += enc_delta(rec["delta_raw"], rec["delta_pad"], prof["delta"])
            running = s32(running + rec["delta_raw"])
            last_delta = rec["delta_raw"]
            payload = rec["delta_raw"]
        elif mode == "dict":
            index = rec["dict_index"]
            body.append(index)
            if index >= len(table):
                raise Inconsistent(idx, "value")
            at = len(table) - 1 - index if prof["dict_dir"] == "backward" else index
            entry = table[at]
            if prof["dict_mtf"]:
                table.pop(at)
                table.append(entry)
            running = s32(entry)
            payload = index
        else:
            count = rec["repeat_count"]
            body.append(count)
            if last_delta is None:
                raise Inconsistent(idx, "value")
            running = s32(prof["repeat"](running, last_delta, count))
            payload = count

        if rec["value"] != running:
            raise Inconsistent(idx, "value")
        table.append(payload if prof["dict_append"] == "payload" else running)
        if len(table) > prof["dict_cap"]:
            del table[0]

    body = bytes(body)
    trailer = crc_of(prof, bytes(header), body)
    if flags["whitened"]:
        body = whiten(prof, doc["salt"], doc["base_value"], body)
    return bytes(header) + body + trailer.to_bytes(4, "little")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: encode.py <document.json> <capture>\n")
        return 2
    with open(argv[1], "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    try:
        blob = encode(doc)
    except Inconsistent as exc:
        sys.stdout.write(json.dumps(exc.obj, sort_keys=True,
                                    separators=(",", ":"), ensure_ascii=True) + "\n")
        return 1
    with open(argv[2], "wb") as handle:
        handle.write(blob)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
