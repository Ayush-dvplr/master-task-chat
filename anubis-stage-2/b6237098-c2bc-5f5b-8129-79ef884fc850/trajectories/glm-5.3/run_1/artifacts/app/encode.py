#!/usr/bin/env python3
"""Coredrop MDUMP capture encoder.

Reads a decoded document and writes the capture it came from, byte for byte.
Refuses a document whose stored `offset` or `value` disagrees with the values
its own records imply, printing one error object and exiting 1.

usage: python3 encode.py <document.json> <capture>
"""
import json
import struct
import sys

MAGIC = b"COREZ"
MODE_IDS = {"dict": 0, "raw": 1, "delta": 2, "repeat": 3}


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


def whitening_seed(version, salt, base_value):
    """Register seed for whitening: the salt, with another header field folded in."""
    if version == 3:
        return (salt ^ (base_value & 0xFFFFFF)) & 0xFFFFFF
    if version == 4:
        return (salt + ((base_value & 0xFFFFFFFF) >> 8)) & 0xFFFFFF
    return salt


PROFILES = {
    1: {"mode_bits": (0, 3), "taps": 0xE10000, "zero_seed": 0xC0FFEE,
        "crc": crc32c, "crc_span": (5, 16), "dict_cap": 40, "dict_backward": True,
        "dict_mtf": True, "dict_payload": True, "repeat_plus": 0, "delta": "signed"},
    2: {"mode_bits": (0, 3), "taps": 0xD20400, "zero_seed": 0x5A17C3,
        "crc": crc32c, "crc_span": (0, 16), "dict_cap": 24, "dict_backward": True,
        "dict_mtf": True, "dict_payload": False, "repeat_plus": 1, "delta": "signed"},
    3: {"mode_bits": (0, 2), "taps": 0xD20400, "zero_seed": 0x5A17C3,
        "crc": crc_v3, "crc_span": (0, 16), "dict_cap": 32, "dict_backward": False,
        "dict_mtf": False, "dict_payload": False, "repeat_plus": 1, "delta": "zigzag"},
    4: {"mode_bits": (0, 3), "taps": 0xB40000, "zero_seed": 0x13579B,
        "crc": crc_v4, "crc_span": (0, 16), "dict_cap": 16, "dict_backward": False,
        "dict_mtf": True, "dict_payload": True, "repeat_plus": 2, "delta": "signlow"},
}


def keystream(reg, count, taps):
    out = bytearray()
    for _ in range(count):
        for _ in range(8):
            reg = (reg >> 1) ^ taps if reg & 1 else reg >> 1
        out.append(reg & 0xFF)
    return bytes(out)


def reduce32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


def encode_unsigned_varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def shortest_signed(value):
    n = 1
    while not (-(1 << (7 * n - 1)) <= value <= (1 << (7 * n - 1)) - 1):
        n += 1
    return n


def encode_signed_varint(value, pad):
    n = shortest_signed(value)
    out = bytearray()
    for i in range(n):
        byte = (value >> (7 * i)) & 0x7F
        out.append(byte | 0x80 if i < n - 1 else byte)
    if pad:
        out[-1] |= 0x80
        out.extend([0xFF if value < 0 else 0x80] * (pad - 1))
        out.append(0x7F if value < 0 else 0x00)
    return bytes(out)


def encode_unsigned_padded_varint(value, pad):
    out = bytearray(encode_unsigned_varint(value))
    if pad:
        out[-1] |= 0x80
        out.extend([0x80] * (pad - 1))
        out.append(0x00)
    return bytes(out)


def encode_zigzag_varint(value, pad):
    """Version 3: v<0 stores -2*v-1."""
    if value < 0:
        value = -2 * value - 1
    else:
        value = 2 * value
    return encode_unsigned_padded_varint(value, pad)


def encode_signlow_varint(value, pad):
    """Version 4: v<0 stores -2*v+1."""
    if value < 0:
        value = -2 * value + 1
    else:
        value = 2 * value
    return encode_unsigned_padded_varint(value, pad)


def encode(document, out_path):
    version = document["version"]
    profile = PROFILES[version]
    flags = document["flags"]
    records = document["records"]
    low, high = profile["mode_bits"]
    front = flags["front_coded_keys"]
    big_endian = flags["big_endian_raw"]

    body = bytearray()
    running = document["base_value"]
    last_delta = None
    dictionary = []
    for index, record in enumerate(records):
        offset = len(body)
        if record.get("offset") != offset:
            return {"error": "inconsistent_document", "record_index": index, "field": "offset"}
        mode = record["mode"]
        mode_id = MODE_IDS[mode]
        selector = (mode_id & 1) << low | ((mode_id >> 1) << high)
        if record["long_key"]:
            selector |= 0x40
        if mode == "raw" and record["wide_value"]:
            selector |= 0x10
        body.append(selector)
        if record["long_key"]:
            key_bytes = record["key"].encode("utf-8")
            if front:
                prefix = record["key_prefix"]
                suffix = key_bytes[prefix:]
                body += encode_unsigned_varint(prefix)
                body += encode_unsigned_varint(len(suffix))
                body += suffix
            else:
                body += encode_unsigned_varint(len(key_bytes))
                body += key_bytes
            prev_long = key_bytes
        else:
            body.append(record["key"] & 0xFF)
        if mode == "raw":
            width = 4 if record["wide_value"] else 2
            fmt = (">i" if big_endian else "<i") if width == 4 else (">h" if big_endian else "<h")
            packed = record["raw_value"] & ((1 << (8 * width)) - 1)
            if packed >= 1 << (8 * width - 1):
                packed -= 1 << (8 * width)
            body += struct.pack(fmt, packed)
            running = record["raw_value"]
            payload = record["raw_value"]
        elif mode == "delta":
            if profile["delta"] == "signed":
                body += encode_signed_varint(record["delta_raw"], record["delta_pad"])
            elif profile["delta"] == "zigzag":
                body += encode_zigzag_varint(record["delta_raw"], record["delta_pad"])
            else:
                body += encode_signlow_varint(record["delta_raw"], record["delta_pad"])
            running = reduce32(running + record["delta_raw"])
            last_delta = record["delta_raw"]
            payload = record["delta_raw"]
        elif mode == "dict":
            index_value = record["dict_index"]
            body.append(index_value & 0xFF)
            size = len(dictionary)
            if index_value >= size:
                return {"error": "inconsistent_document", "record_index": index, "field": "value"}
            slot = size - 1 - index_value if profile["dict_backward"] else index_value
            entry = dictionary[slot]
            running = reduce32(entry)
            if profile["dict_mtf"]:
                dictionary.pop(slot)
                dictionary.append(entry)
            payload = index_value
        else:
            count = record["repeat_count"]
            body.append(count & 0xFF)
            if last_delta is None:
                return {"error": "inconsistent_document", "record_index": index, "field": "value"}
            running = reduce32(running + last_delta * (count + profile["repeat_plus"]))
            payload = count
        if record.get("value") != running:
            return {"error": "inconsistent_document", "record_index": index, "field": "value"}
        dictionary.append(payload if profile["dict_payload"] else running)
        if len(dictionary) > profile["dict_cap"]:
            dictionary.pop(0)

    header = bytearray(MAGIC)
    header += struct.pack("<H", document["record_count"] & 0xFFFF)
    salt = document["salt"] & 0xFFFFFF
    header += bytes([salt & 0xFF, (salt >> 8) & 0xFF, (salt >> 16) & 0xFF])
    header.append((1 if flags["reserved_bit_0"] else 0) | (2 if flags["front_coded_keys"] else 0)
                  | (4 if flags["big_endian_raw"] else 0) | (8 if flags["whitened"] else 0))
    base_bits = document["base_value"] & 0xFFFFFFFF
    header += struct.pack("<I", base_bits)
    header.append(version)
    plaintext = bytes(body)
    span_start, span_end = profile["crc_span"]
    checksum = profile["crc"](bytes(header[span_start:span_end]) + plaintext)
    if flags["whitened"]:
        seed = whitening_seed(version, salt, document["base_value"])
        reg = seed if seed else profile["zero_seed"]
        wire = bytes(a ^ b for a, b in zip(plaintext, keystream(reg, len(plaintext), profile["taps"])))
    else:
        wire = plaintext
    with open(out_path, "wb") as handle:
        handle.write(bytes(header) + wire + struct.pack("<I", checksum))
    return None


def main():
    with open(sys.argv[1], "r") as handle:
        document = json.load(handle)
    result = encode(document, sys.argv[2])
    if result is not None:
        print(json.dumps(result))
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
