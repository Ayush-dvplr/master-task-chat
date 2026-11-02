#!/usr/bin/env python3
"""MDUMP crash-dump decoder.

Reads one MDUMP capture and prints exactly one JSON object on stdout: the
decoded document when the capture is valid, or the error object the MDUMP
error-code reference defines for the first rule it breaks. Exits 0 either
way, including on damaged or truncated input.

usage: python3 decode.py <capture>
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


MODE_NAMES = {0: "dict", 1: "raw", 2: "delta", 3: "repeat"}


class Reject(Exception):
    """Carries the one error object the decoder prints."""

    def __init__(self, obj):
        super().__init__(obj["error"])
        self.obj = obj


def rj(code, **fields):
    obj = {"error": code}
    obj.update(fields)
    return Reject(obj)


def sleb_minlen(value):
    n = 0
    while True:
        b = value & 0x7F
        value >>= 7
        n += 1
        if (value == 0 and not b & 0x40) or (value == -1 and b & 0x40):
            return n


def uleb_minlen(u):
    n = 1
    u >>= 7
    while u:
        n += 1
        u >>= 7
    return n


def read_uvarint(body, pos, idx):
    """Unsigned varint; returns (value, next_pos, length, first_byte_offset)."""
    start = pos
    value = 0
    shift = 0
    length = 0
    while True:
        if pos >= len(body):
            raise rj("truncated_record", record_index=idx, offset=start)
        b = body[pos]
        pos += 1
        length += 1
        value |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return value, pos, length, start
        if length == 10:
            raise rj("varint_overlong", record_index=idx, offset=start)


def read_key_varint(body, pos, idx):
    """A key length or prefix varint: unsigned and required to be minimal."""
    value, pos, length, start = read_uvarint(body, pos, idx)
    if length >= 2 and body[pos - 1] == 0x00:
        raise rj("noncanonical_varint", record_index=idx, offset=start)
    return value, pos, start


def read_delta(body, pos, idx, kind):
    """Delta payload; returns (value, next_pos, pad)."""
    value, pos, length, _ = read_uvarint(body, pos, idx)
    if kind == "sleb128":
        if body[pos - 1] & 0x40:
            value -= 1 << 7 * length
        return value, pos, length - sleb_minlen(value)
    value = (value >> 1) ^ -(value & 1)
    return value, pos, length - uleb_minlen(zigzag_enc(value))


def parse_header(blob):
    """Returns (document without its records, profile) or raises Reject."""
    if len(blob) < 5 or blob[:5] != MAGIC:
        raise rj("bad_magic")
    if len(blob) < 20:
        raise rj("truncated_header", length=len(blob))
    version = blob[15]
    if version not in PROFILES:
        raise rj("unsupported_version", version=version)
    flags_byte = blob[10]
    if flags_byte & 0xF0:
        raise rj("reserved_flag_set", flags=flags_byte)
    doc = {
        "version": version,
        "flags": {name: bool(flags_byte >> bit & 1) for name, bit in FLAG_BITS},
        "salt": int.from_bytes(blob[7:10], "little"),
        "record_count": int.from_bytes(blob[5:7], "little"),
        "base_value": s32(int.from_bytes(blob[11:15], "little")),
    }
    return doc, PROFILES[version]


def decode_records(prof, doc, body):
    front = doc["flags"]["front_coded_keys"]
    byteorder = "big" if doc["flags"]["big_endian_raw"] else "little"
    running = doc["base_value"]
    last_delta = None
    table = []
    prev_key = b""
    records = []
    pos = 0
    n = len(body)
    for idx in range(doc["record_count"]):
        if pos >= n:
            raise rj("truncated_record", record_index=idx, offset=n)
        rec = {"offset": pos}
        sel = body[pos]
        pos += 1
        if sel & prof["sel_reserved"]:
            raise rj("reserved_selector_bits", record_index=idx, selector=sel,
                     offset=rec["offset"])
        mode = MODE_NAMES[(sel & 1) | ((sel >> prof["mode_hi_bit"] & 1) << 1)]
        wide = bool(sel >> 4 & 1)
        if wide and mode != "raw":
            raise rj("reserved_selector_bits", record_index=idx, selector=sel,
                     offset=rec["offset"])
        long_key = bool(sel >> 6 & 1)

        if not long_key:
            if pos >= n:
                raise rj("truncated_record", record_index=idx, offset=n)
            rec["key"] = body[pos]
            pos += 1
        else:
            if front:
                prefix, pos, at = read_key_varint(body, pos, idx)
                if prefix > len(prev_key):
                    raise rj("bad_key_prefix", record_index=idx,
                             key_prefix=prefix, offset=at)
                size, pos, _ = read_key_varint(body, pos, idx)
                head = prev_key[:prefix]
                rec["key_prefix"] = prefix
            else:
                size, pos, _ = read_key_varint(body, pos, idx)
                head = b""
            if pos + size > n:
                raise rj("truncated_record", record_index=idx, offset=pos)
            key_bytes = head + body[pos:pos + size]
            try:
                rec["key"] = key_bytes.decode("utf-8", "strict")
            except UnicodeDecodeError:
                raise rj("invalid_utf8_key", record_index=idx, offset=pos)
            prev_key = key_bytes
            pos += size

        if mode == "raw":
            width = 4 if wide else 2
            if pos + width > n:
                raise rj("truncated_record", record_index=idx, offset=pos)
            rec["wide_value"] = wide
            rec["raw_value"] = int.from_bytes(body[pos:pos + width], byteorder,
                                              signed=True)
            pos += width
            running = s32(rec["raw_value"])
            payload = rec["raw_value"]
        elif mode == "delta":
            rec["delta_raw"], pos, rec["delta_pad"] = read_delta(
                body, pos, idx, prof["delta"])
            running = s32(running + rec["delta_raw"])
            last_delta = rec["delta_raw"]
            payload = rec["delta_raw"]
        elif mode == "dict":
            if pos >= n:
                raise rj("truncated_record", record_index=idx, offset=n)
            index = body[pos]
            rec["dict_index"] = index
            if index >= len(table):
                raise rj("dict_index_out_of_range", record_index=idx,
                         dict_index=index, dict_size=len(table), offset=pos)
            pos += 1
            at = len(table) - 1 - index if prof["dict_dir"] == "backward" else index
            entry = table[at]
            if prof["dict_mtf"]:
                table.pop(at)
                table.append(entry)
            running = s32(entry)
            payload = index
        else:
            if pos >= n:
                raise rj("truncated_record", record_index=idx, offset=n)
            count = body[pos]
            rec["repeat_count"] = count
            if last_delta is None:
                raise rj("repeat_without_delta", record_index=idx, offset=pos)
            pos += 1
            running = s32(prof["repeat"](running, last_delta, count))
            payload = count

        rec["long_key"] = long_key
        rec["mode"] = mode
        rec["value"] = running
        records.append(rec)
        table.append(payload if prof["dict_append"] == "payload" else running)
        if len(table) > prof["dict_cap"]:
            del table[0]
    if pos < n:
        raise rj("trailing_bytes", count=n - pos, offset=pos)
    return records


def decode(blob):
    """Returns the decoded document, or the error object for a bad capture."""
    try:
        doc, prof = parse_header(blob)
        body = blob[16:len(blob) - 4]
        if doc["flags"]["whitened"]:
            body = whiten(prof, doc["salt"], doc["base_value"], body)
        stored = int.from_bytes(blob[len(blob) - 4:], "little")
        computed = crc_of(prof, blob[:16], body)
        if stored != computed:
            raise rj("trailer_crc_mismatch", stored=stored, computed=computed)
        doc["records"] = decode_records(prof, doc, body)
    except Reject as exc:
        return exc.obj
    return doc


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: decode.py <capture>\n")
        return 2
    with open(argv[1], "rb") as handle:
        blob = handle.read()
    sys.stdout.write(json.dumps(decode(blob), sort_keys=True,
                                separators=(",", ":"), ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
