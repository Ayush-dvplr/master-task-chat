import json
import struct
import sys
import zlib

MAGIC = bytes.fromhex("4e554d504b")
HEADER_SIZE = 16
TRAILER_SIZE = 4
MODE_BITS = (2, 5)
WIDE_BIT = 0
LONG_KEY_BIT = 7
MODE_NAMES = {0: "raw", 1: "delta", 2: "dict"}
SELECTOR_KNOWN = (1 << MODE_BITS[0]) | (1 << MODE_BITS[1]) | (1 << WIDE_BIT) | (1 << LONG_KEY_BIT)


class Malformed(Exception):
    pass


def wrap_i32(n):
    return ((n + 0x80000000) & 0xFFFFFFFF) - 0x80000000


def read_uvarint(buf, pos):
    result = 0
    shift = 0
    start = pos
    while True:
        if pos >= len(buf):
            raise Malformed()
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            break
    # A non-canonical (overlong) encoding cannot be rebuilt byte for byte.
    if pos - start > 1 and byte == 0:
        raise Malformed()
    return result, pos


def parse_body(body, count, base_value):
    records = []
    dictionary = []
    running = base_value
    pos = 0
    for _ in range(count):
        if pos >= len(body):
            raise Malformed()
        selector = body[pos]
        pos += 1
        if selector & ~SELECTOR_KNOWN & 0xFF:
            raise Malformed()
        mode = ((selector >> MODE_BITS[0]) & 1) | (((selector >> MODE_BITS[1]) & 1) << 1)
        if mode not in MODE_NAMES:
            raise Malformed()
        wide = bool(selector >> WIDE_BIT & 1)
        long_key = bool(selector >> LONG_KEY_BIT & 1)
        if wide and mode != 0:
            raise Malformed()
        if long_key:
            length, pos = read_uvarint(body, pos)
            if pos + length > len(body):
                raise Malformed()
            try:
                key = body[pos:pos + length].decode("utf-8")
            except UnicodeDecodeError:
                raise Malformed()
            pos += length
        else:
            if pos >= len(body):
                raise Malformed()
            key = body[pos]
            pos += 1
        record = {"key": key, "mode": MODE_NAMES[mode], "wide_value": wide, "long_key": long_key}
        if mode == 0:
            width = 4 if wide else 2
            if pos + width > len(body):
                raise Malformed()
            raw = int.from_bytes(body[pos:pos + width], "little", signed=True)
            pos += width
            running = raw
            record["raw_value"] = raw
        elif mode == 1:
            zz, pos = read_uvarint(body, pos)
            delta = (zz >> 1) ^ -(zz & 1)
            running = wrap_i32(running + delta)
            record["delta_raw"] = delta
        else:
            if pos >= len(body):
                raise Malformed()
            index = body[pos]
            pos += 1
            if index >= len(dictionary):
                raise Malformed()
            running = dictionary[len(dictionary) - 1 - index]
            record["dict_index"] = index
        record["value"] = running
        dictionary.append(running)
        records.append(record)
    if pos != len(body):
        raise Malformed()
    return records


def decode(data):
    if data[:5] != MAGIC:
        return {"error": "bad_magic"}
    if len(data) > 12 and data[12] != 1:
        return {"error": "unsupported_version", "version": data[12]}
    if len(data) < HEADER_SIZE + TRAILER_SIZE:
        return {"error": "truncated_record"}
    stored = struct.unpack_from("<I", data, len(data) - TRAILER_SIZE)[0]
    if zlib.crc32(data[5:len(data) - TRAILER_SIZE]) & 0xFFFFFFFF != stored:
        return {"error": "trailer_crc_mismatch"}
    base_value, record_count, flags, version = struct.unpack_from("<iHBB", data, 5)
    if flags & 0xFE or data[13:16] != b"\x00\x00\x00":
        return {"error": "truncated_record"}
    try:
        records = parse_body(data[HEADER_SIZE:len(data) - TRAILER_SIZE], record_count, base_value)
    except Malformed:
        return {"error": "truncated_record"}
    return {
        "version": version,
        "flags": {"reserved_bit_0": bool(flags & 1)},
        "record_count": record_count,
        "base_value": base_value,
        "records": records,
    }


def main():
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    sys.stdout.write(json.dumps(decode(data), separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
