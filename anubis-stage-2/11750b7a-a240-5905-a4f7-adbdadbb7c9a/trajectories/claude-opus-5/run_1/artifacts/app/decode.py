import json
import struct
import sys
import zlib

MAGIC = b"SEALB"
VERSION = 3
HEADER_SIZE = 16
TRAILER_SIZE = 4
MODE_NAMES = {2: "raw", 1: "delta", 0: "dict"}
SELECTOR_RESERVED_MASK = 0b01010110


class Malformed(Exception):
    pass


def read_uvarint(buf, pos, end):
    result = 0
    shift = 0
    start = pos
    while True:
        if pos >= end:
            raise Malformed()
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            break
    if pos - start > 1 and buf[pos - 1] == 0:
        raise Malformed()
    return result, pos


def read_sleb128(buf, pos, end):
    result = 0
    shift = 0
    start = pos
    while True:
        if pos >= end:
            raise Malformed()
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            break
    if b & 0x40:
        result -= 1 << shift
    if pos - start > 1:
        prev = buf[pos - 2]
        if (b == 0x00 and not prev & 0x40) or (b == 0x7F and prev & 0x40):
            raise Malformed()
    return result, pos


def parse_records(data, count, base_value, end):
    pos = HEADER_SIZE
    running = base_value
    dictionary = []
    records = []
    for _ in range(count):
        if pos >= end:
            raise Malformed()
        sel = data[pos]
        pos += 1
        if sel & SELECTOR_RESERVED_MASK:
            raise Malformed()
        mode_id = ((sel >> 3) & 1) | (((sel >> 7) & 1) << 1)
        if mode_id not in MODE_NAMES:
            raise Malformed()
        wide = bool(sel & 0x01)
        long_key = bool(sel & 0x20)
        if long_key:
            length, pos = read_uvarint(data, pos, end)
            if pos + length > end:
                raise Malformed()
            try:
                key = data[pos:pos + length].decode("utf-8")
            except UnicodeDecodeError:
                raise Malformed()
            pos += length
        else:
            if pos >= end:
                raise Malformed()
            key = data[pos]
            pos += 1
        rec = {"key": key, "mode": MODE_NAMES[mode_id], "wide_value": wide, "long_key": long_key}
        if mode_id == 2:
            width = 4 if wide else 2
            if pos + width > end:
                raise Malformed()
            raw = struct.unpack_from("<i" if wide else "<h", data, pos)[0]
            pos += width
            running = raw
            rec["raw_value"] = raw
        elif mode_id == 1:
            delta, pos = read_sleb128(data, pos, end)
            running = running + delta
            rec["delta_raw"] = delta
        else:
            if pos >= end:
                raise Malformed()
            idx = data[pos]
            pos += 1
            if idx >= len(dictionary):
                raise Malformed()
            running = dictionary[idx]
            rec["dict_index"] = idx
        rec["value"] = running
        dictionary.append(running)
        records.append(rec)
    if pos != end:
        raise Malformed()
    return records


def decode(data):
    if data[:5] != MAGIC:
        return {"error": "bad_magic"}
    if len(data) < 11:
        return {"error": "truncated_record"}
    if data[10] != VERSION:
        return {"error": "unsupported_version", "version": data[10]}
    if len(data) < HEADER_SIZE + TRAILER_SIZE:
        return {"error": "truncated_record"}
    end = len(data) - TRAILER_SIZE
    if zlib.crc32(data[5:end]) != struct.unpack_from("<I", data, end)[0]:
        return {"error": "trailer_crc_mismatch"}
    base_value = struct.unpack_from("<i", data, 5)[0]
    flags = data[9]
    count = struct.unpack_from("<H", data, 14)[0]
    if flags & 0xFE or data[11:14] != b"\x00\x00\x00":
        return {"error": "truncated_record"}
    try:
        records = parse_records(data, count, base_value, end)
    except Malformed:
        return {"error": "truncated_record"}
    return {
        "version": data[10],
        "flags": {"reserved_bit_0": bool(flags & 1)},
        "record_count": count,
        "base_value": base_value,
        "records": records,
    }


def main():
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    sys.stdout.write(json.dumps(decode(data), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
