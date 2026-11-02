#!/usr/bin/env python3
"""Coredrop MDUMP capture decoder.

Reads one MDUMP capture and prints exactly one JSON object on stdout:
the decoded document for a valid capture, or the single error object the
error-code reference defines for an invalid one. Exits 0 in both cases.

usage: python3 decode.py <capture>
"""
import json
import struct
import sys

MAGIC = b"COREZ"
MODES = {0: "dict", 1: "raw", 2: "delta", 3: "repeat"}


def _crc_table(poly):
    table = []
    for i in range(256):
        x = i
        for _ in range(8):
            x = (x >> 1) ^ poly if x & 1 else x >> 1
        table.append(x)
    return table


_CRC32C_TABLE = _crc_table(0x82F63B78)
_CRC5_TABLE = _crc_table(0xA2E1C19B)
_CRC4_TABLE = _crc_table(0xEDB88320)


def crc32c(data):
    crc = 0xFFFFFFFF
    for b in data:
        crc = _CRC32C_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def crc_v3(data):
    crc = 0
    for b in data:
        crc = _CRC5_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def crc_v4(data):
    crc = 0xFFFFFFFF
    for b in data:
        crc = _CRC4_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc


def keystream(reg, count, taps):
    """Eight clocks of the 24-bit Galois LFSR per keystream byte."""
    out = bytearray()
    for _ in range(count):
        for _ in range(8):
            reg = (reg >> 1) ^ taps if reg & 1 else reg >> 1
        out.append(reg & 0xFF)
    return bytes(out)


# Per-revision profiles: selector layout, keystream seed, trailer, dictionary, repeat, delta.
PROFILES = {
    1: {"mode_bits": (0, 3), "reserved_mask": 0xA6, "taps": 0xE10000,
        "zero_seed": 0xC0FFEE, "crc": crc32c, "crc_span": (5, 16),
        "dict_cap": 40, "dict_backward": True, "dict_mtf": True,
        "dict_payload": True, "repeat_plus": 0, "delta": "signed"},
    2: {"mode_bits": (0, 3), "reserved_mask": 0xA6, "taps": 0xD20400,
        "zero_seed": 0x5A17C3, "crc": crc32c, "crc_span": (0, 16),
        "dict_cap": 24, "dict_backward": True, "dict_mtf": True,
        "dict_payload": False, "repeat_plus": 1, "delta": "signed"},
    3: {"mode_bits": (0, 2), "reserved_mask": 0xAA, "taps": 0xD20400,
        "zero_seed": 0x5A17C3, "crc": crc_v3, "crc_span": (0, 16),
        "dict_cap": 32, "dict_backward": False, "dict_mtf": False,
        "dict_payload": False, "repeat_plus": 1, "delta": "zigzag"},
    4: {"mode_bits": (0, 3), "reserved_mask": 0xA6, "taps": 0xB40000,
        "zero_seed": 0x13579B, "crc": crc_v4, "crc_span": (0, 16),
        "dict_cap": 16, "dict_backward": False, "dict_mtf": True,
        "dict_payload": True, "repeat_plus": 2, "delta": "signlow"},
}


def whitening_seed(version, salt, base_value):
    """Register seed for whitening: the salt, with another header field folded in."""
    if version == 3:
        return (salt ^ (base_value & 0xFFFFFF)) & 0xFFFFFF
    if version == 4:
        return (salt + ((base_value & 0xFFFFFFFF) >> 8)) & 0xFFFFFF
    return salt


def reduce32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


class Failure(Exception):
    def __init__(self, obj):
        self.obj = obj


def shortest_signed(value):
    n = 1
    while not (-(1 << (7 * n - 1)) <= value <= (1 << (7 * n - 1)) - 1):
        n += 1
    return n


def shortest_unsigned(value):
    n = 1
    while value >= (1 << (7 * n)):
        n += 1
    return n


def read_unsigned_varint(body, pos, offset, idx):
    """Unsigned varint, rejecting overlong and non-minimal forms."""
    value = shift = count = 0
    byte = 0
    while True:
        if pos >= len(body):
            raise Failure({"error": "truncated_record", "record_index": idx, "offset": offset})
        byte = body[pos]
        pos += 1
        count += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            break
        if count == 10:
            raise Failure({"error": "varint_overlong", "record_index": idx, "offset": offset})
    if count >= 2 and (byte & 0x7F) == 0:
        raise Failure({"error": "noncanonical_varint", "record_index": idx, "offset": offset})
    return value, pos


def read_delta_varint(body, pos, offset, idx):
    """Read the delta varint bytes; the value interpretation is per revision."""
    out = bytearray()
    while True:
        if pos >= len(body):
            raise Failure({"error": "truncated_record", "record_index": idx, "offset": offset})
        byte = body[pos]
        pos += 1
        out.append(byte)
        if len(out) == 10 and (byte & 0x80):
            raise Failure({"error": "varint_overlong", "record_index": idx, "offset": offset})
        if not byte & 0x80:
            return bytes(out), pos


def decode_delta(blob, style):
    """Return (delta_raw, delta_pad) for a delta varint.

    Versions 1 and 2 store signed LEB128; versions 3 and 4 store an unsigned varint
    whose low bit carries the sign. Version 3 maps v<0 to -2*v-1, version 4 to
    -2*v+1, so the two differ for negative deltas.
    """
    if style == "signed":
        value = shift = 0
        for byte in blob:
            value |= (byte & 0x7F) << shift
            shift += 7
        if blob[-1] & 0x40:
            value -= 1 << shift
        return value, len(blob) - shortest_signed(value)
    uvalue = shift = 0
    for byte in blob:
        uvalue |= (byte & 0x7F) << shift
        shift += 7
    if not (uvalue & 1):
        value = uvalue >> 1
    elif style == "signlow":
        value = -((uvalue - 1) >> 1)
    else:
        value = -((uvalue + 1) >> 1)
    return value, len(blob) - shortest_unsigned(uvalue)


def strict_utf8(raw):
    text = raw.decode("utf-8")
    for ch in text:
        if 0xD800 <= ord(ch) <= 0xDFFF:
            raise ValueError("surrogate")
    return text


def parse_records(body, record_count, flags, base_value, profile):
    records = []
    pos = 0
    running = base_value
    last_delta = None
    dictionary = []
    prev_long = b""
    front = flags["front_coded_keys"]
    big_endian = flags["big_endian_raw"]
    low, high = profile["mode_bits"]
    reserved = profile["reserved_mask"]
    length = len(body)

    for idx in range(record_count):
        try:
            start = pos
            if pos >= length:
                raise Failure({"error": "truncated_record", "offset": pos})
            selector = body[pos]
            pos += 1
            mode = MODES[((selector >> low) & 1) | (((selector >> high) & 1) << 1)]
            if (selector & reserved) or (selector & 0x10 and mode != "raw"):
                raise Failure({"error": "reserved_selector_bits", "selector": selector,
                               "offset": start})
            record = {"key": None, "long_key": bool(selector & 0x40), "mode": mode}
            key_bytes = None
            if selector & 0x40:
                if front:
                    first = pos
                    prefix, pos = read_unsigned_varint(body, pos, first, idx)
                    if prefix > len(prev_long):
                        raise Failure({"error": "bad_key_prefix", "key_prefix": prefix,
                                       "offset": first})
                    suffix_len, pos = read_unsigned_varint(body, pos, pos, idx)
                    if pos + suffix_len > length:
                        raise Failure({"error": "truncated_record", "offset": pos})
                    key_bytes = prev_long[:prefix] + body[pos:pos + suffix_len]
                    key_start = pos
                    pos += suffix_len
                else:
                    first = pos
                    key_len, pos = read_unsigned_varint(body, pos, first, idx)
                    if pos + key_len > length:
                        raise Failure({"error": "truncated_record", "offset": pos})
                    key_start = pos
                    key_bytes = body[pos:pos + key_len]
                    pos += key_len
                try:
                    record["key"] = strict_utf8(key_bytes)
                except (UnicodeDecodeError, ValueError):
                    raise Failure({"error": "invalid_utf8_key", "offset": key_start})
                if front:
                    record["key_prefix"] = prefix
            else:
                if pos >= length:
                    raise Failure({"error": "truncated_record", "offset": pos})
                record["key"] = body[pos]
                pos += 1

            if mode == "raw":
                wide = bool(selector & 0x10)
                width = 4 if wide else 2
                if pos + width > length:
                    raise Failure({"error": "truncated_record", "offset": pos})
                chunk = body[pos:pos + width]
                if wide:
                    fmt = ">i" if big_endian else "<i"
                else:
                    fmt = ">h" if big_endian else "<h"
                raw_value = struct.unpack(fmt, chunk)[0]
                pos += width
                running = raw_value
                record["wide_value"] = wide
                record["raw_value"] = raw_value
                stored_payload = raw_value
            elif mode == "delta":
                first = pos
                blob, pos = read_delta_varint(body, pos, first, idx)
                delta_raw, delta_pad = decode_delta(blob, profile["delta"])
                running = reduce32(running + delta_raw)
                last_delta = delta_raw
                record["delta_raw"] = delta_raw
                record["delta_pad"] = delta_pad
                stored_payload = delta_raw
            elif mode == "dict":
                if pos >= length:
                    raise Failure({"error": "truncated_record", "offset": pos})
                index = body[pos]
                at = pos
                pos += 1
                size = len(dictionary)
                if index >= size:
                    raise Failure({"error": "dict_index_out_of_range", "dict_index": index,
                                   "dict_size": size, "offset": at})
                slot = size - 1 - index if profile["dict_backward"] else index
                entry = dictionary[slot]
                running = reduce32(entry)
                if profile["dict_mtf"]:
                    dictionary.pop(slot)
                    dictionary.append(entry)
                record["dict_index"] = index
                stored_payload = index
            else:
                if pos >= length:
                    raise Failure({"error": "truncated_record", "offset": pos})
                count = body[pos]
                at = pos
                pos += 1
                if last_delta is None:
                    raise Failure({"error": "repeat_without_delta", "offset": at})
                running = reduce32(running + last_delta * (count + profile["repeat_plus"]))
                record["repeat_count"] = count
                stored_payload = count

            record["value"] = running
            record["offset"] = start
            records.append(record)
            dictionary.append(stored_payload if profile["dict_payload"] else running)
            if len(dictionary) > profile["dict_cap"]:
                dictionary.pop(0)
            if record["long_key"]:
                prev_long = key_bytes
        except Failure as failure:
            obj = dict(failure.obj)
            obj.setdefault("record_index", idx)
            return obj
    return records, pos


def decode(blob):
    if len(blob) < 5 or blob[:5] != MAGIC:
        return {"error": "bad_magic"}
    if len(blob) < 20:
        return {"error": "truncated_header", "length": len(blob)}
    version = blob[15]
    profile = PROFILES.get(version)
    if profile is None:
        return {"error": "unsupported_version", "version": version}
    flags = blob[10]
    if flags & 0xF0:
        return {"error": "reserved_flag_set", "flags": flags}
    record_count = struct.unpack_from("<H", blob, 5)[0]
    salt = blob[7] | (blob[8] << 8) | (blob[9] << 16)
    base_value = struct.unpack_from("<i", blob, 11)[0]
    flag_bits = {"reserved_bit_0": bool(flags & 1), "front_coded_keys": bool(flags & 2),
                 "big_endian_raw": bool(flags & 4), "whitened": bool(flags & 8)}
    stored = struct.unpack_from("<I", blob, len(blob) - 4)[0]
    wire = blob[16:-4]
    if flag_bits["whitened"]:
        seed = whitening_seed(version, salt, base_value)
        reg = seed if seed else profile["zero_seed"]
        body = bytes(a ^ b for a, b in zip(
            wire, keystream(reg, len(wire), profile["taps"])))
    else:
        body = wire
    span_start, span_end = profile["crc_span"]
    computed = profile["crc"](blob[span_start:span_end] + body)
    if computed != stored:
        return {"error": "trailer_crc_mismatch", "stored": stored, "computed": computed}
    result = parse_records(body, record_count, flag_bits, base_value, profile)
    if isinstance(result, dict):
        return result
    records, pos = result
    if pos < len(body):
        return {"error": "trailing_bytes", "count": len(body) - pos, "offset": pos}
    return {"version": version, "flags": flag_bits, "salt": salt,
            "record_count": record_count, "base_value": base_value, "records": records}


def main():
    with open(sys.argv[1], "rb") as handle:
        blob = handle.read()
    print(json.dumps(decode(blob)))


if __name__ == "__main__":
    main()
