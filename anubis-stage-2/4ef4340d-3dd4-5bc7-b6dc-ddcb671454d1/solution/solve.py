#!/usr/bin/env python3
"""POLYP codec, written from the container specification and its appendices.

python3 solve.py <capture>              decode, print one JSON object
python3 solve.py <document.json> <out>  encode a decoded document back to bytes
python3 solve.py --reports-json <log>   print the four /app/out report documents
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

MAGIC = b"NUMPK"
VERSION = 1
SPEC = {'selector': {'mode_bits': [2, 5], 'wide_bit': 0, 'long_key_bit': 7, 'mode_ids': {'raw': 0, 'delta': 1, 'dict': 2}}, 'header_order': ['base_value', 'record_count', 'flags', 'version', 'reserved'], 'delta_encoding': 'zigzag_uvarint', 'dict_source': 'resolved_values', 'dict_direction': 'backward', 'crc_coverage': 'header_records'}

FIELD_FORMATS = {"version": "B", "flags": "B", "record_count": "H", "base_value": "i", "reserved": "3s"}
LAYOUT = "<" + "".join(FIELD_FORMATS[name] for name in SPEC["header_order"])
HEADER_LEN = len(MAGIC) + struct.calcsize(LAYOUT)
CRC_LEN = 4
MODE_BY_ID = {ident: name for name, ident in SPEC["selector"]["mode_ids"].items()}
LOW_BIT, HIGH_BIT = SPEC["selector"]["mode_bits"]
WIDE_MASK = 1 << SPEC["selector"]["wide_bit"]
LONG_MASK = 1 << SPEC["selector"]["long_key_bit"]


class Malformed(Exception):
    pass


class Cursor:
    def __init__(self, blob, stop):
        self.blob, self.at, self.stop = blob, len(MAGIC) + struct.calcsize(LAYOUT), stop

    def take(self, count):
        if self.at + count > self.stop:
            raise Malformed("record runs past the trailer")
        piece = self.blob[self.at:self.at + count]
        self.at += count
        return piece

    def byte(self):
        return self.take(1)[0]

    def leb(self, signed=False):
        total, shift, prev = 0, 0, None
        while shift <= 70:
            octet = self.byte()
            total |= (octet & 0x7F) << shift
            shift += 7
            if not octet & 0x80:
                if prev is not None:
                    redundant = (octet == 0 and not prev & 0x40) or (octet == 0x7F and prev & 0x40) if signed else octet == 0
                    if redundant:
                        raise Malformed("varint carries a redundant trailing byte")
                return total, shift, octet
            prev = octet
        raise Malformed("varint longer than 70 bits")


def read_delta(cur):
    zigzag = SPEC["delta_encoding"] == "zigzag_uvarint"
    total, shift, last = cur.leb(signed=not zigzag)
    if zigzag:
        return (total >> 1) if total % 2 == 0 else -((total + 1) >> 1)
    return total - (1 << shift) if last & 0x40 else total


def put_uleb(number):
    if number < 0:
        raise ValueError("unsigned varint cannot hold a negative number")
    chunks = bytearray()
    while True:
        low = number & 0x7F
        number >>= 7
        chunks.append(low | (0x80 if number else 0))
        if not number:
            return bytes(chunks)


def put_delta(delta):
    if SPEC["delta_encoding"] == "zigzag_uvarint":
        return put_uleb(2 * delta if delta >= 0 else -2 * delta - 1)
    chunks = bytearray()
    while True:
        low = delta & 0x7F
        delta >>= 7
        finished = (delta == 0 and not low & 0x40) or (delta == -1 and low & 0x40)
        chunks.append(low if finished else low | 0x80)
        if finished:
            return bytes(chunks)


def crc_of(body):
    covered = body if SPEC["crc_coverage"] == "prefix" else body[len(MAGIC):]
    return zlib.crc32(covered) & 0xFFFFFFFF


def remembered(record):
    if SPEC["dict_source"] == "resolved_values":
        return record["value"]
    return {"raw": record.get("raw_value"), "delta": record.get("delta_raw"), "dict": record.get("dict_index")}[record["mode"]]


def slot(index, size):
    return index if SPEC["dict_direction"] == "forward" else size - 1 - index


def decode(blob):
    if blob[:len(MAGIC)] != MAGIC:
        return {"error": "bad_magic"}
    offset = _version_offset()
    if offset < len(blob) and blob[offset] != VERSION:
        return {"error": "unsupported_version", "version": blob[offset]}
    if len(blob) < HEADER_LEN + CRC_LEN or crc_of(blob[:-CRC_LEN]) != int.from_bytes(blob[-CRC_LEN:], "little"):
        return {"error": "trailer_crc_mismatch"}
    header = dict(zip(SPEC["header_order"], struct.unpack(LAYOUT, blob[len(MAGIC):HEADER_LEN])))
    cur = Cursor(blob, len(blob) - CRC_LEN)
    seen, rows, current = [], [], header["base_value"]
    if header["flags"] & 0xFE:
        return {"error": "truncated_record"}
    try:
        for _ in range(header["record_count"]):
            sel = cur.byte()
            mode = MODE_BY_ID.get(((sel >> LOW_BIT) & 1) | (((sel >> HIGH_BIT) & 1) << 1))
            if mode is None:
                raise Malformed("unassigned mode id")
            if mode != "raw" and sel & WIDE_MASK:
                raise Malformed("wide bit on a record that carries no raw value")
            is_long = bool(sel & LONG_MASK)
            key = cur.take(cur.leb()[0]).decode("utf-8", "replace") if is_long else cur.byte()
            row = {"key": key, "mode": mode, "long_key": is_long}
            if mode == "raw":
                is_wide = bool(sel & WIDE_MASK)
                current = int.from_bytes(cur.take(4 if is_wide else 2), "little", signed=True)
                row.update(wide_value=is_wide, raw_value=current)
            elif mode == "delta":
                step = read_delta(cur)
                current += step
                row["delta_raw"] = step
            else:
                pointer = cur.byte()
                where = slot(pointer, len(seen))
                if not 0 <= where < len(seen):
                    raise Malformed("dictionary index outside the dictionary")
                current = seen[where]
                row["dict_index"] = pointer
            row["value"] = current
            seen.append(remembered(row))
            rows.append(row)
    except Malformed:
        return {"error": "truncated_record"}
    return {"version": header["version"], "flags": {"reserved_bit_0": bool(header["flags"] & 1)},
            "record_count": header["record_count"], "base_value": header["base_value"], "records": rows}


def encode(doc):
    if doc["record_count"] != len(doc["records"]):
        raise ValueError("record_count does not match the records array")
    fields = {"version": doc["version"], "flags": 1 if doc["flags"].get("reserved_bit_0") else 0,
              "record_count": doc["record_count"], "base_value": doc["base_value"], "reserved": bytes(3)}
    body = bytearray(MAGIC + struct.pack(LAYOUT, *(fields[n] for n in SPEC["header_order"])))
    ids = SPEC["selector"]["mode_ids"]
    for row in doc["records"]:
        ident = ids[row["mode"]]
        sel = ((ident & 1) << LOW_BIT) | ((ident >> 1 & 1) << HIGH_BIT)
        wide = row["mode"] == "raw" and bool(row.get("wide_value"))
        sel |= (WIDE_MASK if wide else 0) | (LONG_MASK if row.get("long_key") else 0)
        body.append(sel)
        if row.get("long_key"):
            name = row["key"].encode("utf-8")
            body += put_uleb(len(name)) + name
        else:
            body.append(row["key"])
        if row["mode"] == "raw":
            body += int(row["raw_value"]).to_bytes(4 if wide else 2, "little", signed=True)
        elif row["mode"] == "delta":
            body += put_delta(int(row["delta_raw"]))
        else:
            body.append(row["dict_index"])
    return bytes(body) + crc_of(bytes(body)).to_bytes(CRC_LEN, "little")


def build(base, rows):
    doc = {"version": VERSION, "flags": {"reserved_bit_0": False}, "record_count": len(rows),
           "base_value": base, "records": rows}
    return encode(doc)


def own_examples():
    first_slot = slot(0, 2)
    return [
        ("raw_narrow_and_wide", build(0, [
            {"key": 3, "mode": "raw", "long_key": False, "wide_value": False, "raw_value": 32767},
            {"key": 4, "mode": "raw", "long_key": False, "wide_value": True, "raw_value": 2147483647},
        ])),
        ("delta_from_long_key", build(-40, [
            {"key": "probe.alpha", "mode": "raw", "long_key": True, "wide_value": True, "raw_value": -40},
            {"key": 9, "mode": "delta", "long_key": False, "delta_raw": 300},
            {"key": 9, "mode": "delta", "long_key": False, "delta_raw": -1},
        ])),
        ("dictionary_reuse", build(5, [
            {"key": 20, "mode": "raw", "long_key": False, "wide_value": False, "raw_value": -12},
            {"key": 21, "mode": "raw", "long_key": False, "wide_value": True, "raw_value": 77},
            {"key": "probe.beta", "mode": "dict", "long_key": True, "dict_index": first_slot},
        ])),
    ]


def capture_tally(log):
    total, good, modes, failures = 0, 0, {"raw": 0, "delta": 0, "dict": 0}, {}
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        result = decode(bytes.fromhex(json.loads(line)["hex"]))
        if "error" in result:
            failures[result["error"]] = failures.get(result["error"], 0) + 1
            continue
        good += 1
        for row in result["records"]:
            modes[row["mode"]] += 1
    return total, good, modes, dict(sorted(failures.items()))


def reports(log):
    lines, trips, counts = [], [], {"raw": 0, "delta": 0, "dict": 0}
    for name, blob in own_examples():
        doc = decode(blob)
        for row in doc["records"]:
            counts[row["mode"]] += 1
        lines.append({"name": name, "hex": blob.hex(), "decoded": doc})
        again = encode(doc)
        trips.append({"name": name, "input_sha256": hashlib.sha256(blob).hexdigest(),
                      "rebuilt_sha256": hashlib.sha256(again).hexdigest(),
                      "byte_length": len(blob), "roundtrip_equal": again == blob})
    total, good, modes, failures = capture_tally(log)
    sample = own_examples()[0][1]
    def damaged(*kinds):
        out = bytearray(sample)
        for kind in kinds:
            if kind == "magic":
                out[0] ^= 0xFF
            elif kind == "version":
                out[_version_offset()] = 9
            else:
                out[-1] ^= 0xFF
        return decode(bytes(out))
    return {
        "decoded_examples": lines,
        "format_report": {
            "format_tag": "POLYP", "magic_hex": MAGIC.hex(), "version": VERSION,
            "header_size": HEADER_LEN, "trailer_size": CRC_LEN,
            "header_order": SPEC["header_order"], "selector": SPEC["selector"],
            "delta_encoding": SPEC["delta_encoding"], "dict_source": SPEC["dict_source"],
            "dict_direction": SPEC["dict_direction"], "crc_coverage": SPEC["crc_coverage"],
            "visible_example_count": len(lines),
            "visible_record_counts": [line["decoded"]["record_count"] for line in lines],
            "visible_mode_counts": counts,
            "capture_count": total, "capture_ok_count": good, "capture_mode_counts": modes,
        },
        "roundtrip_report": {"all_roundtrips_equal": all(t["roundtrip_equal"] for t in trips), "examples": trips},
        "error_analysis": {
            "precedence": ["bad_magic", "unsupported_version", "trailer_crc_mismatch"],
            "cases": {"bad_magic": damaged("magic"), "unsupported_version": damaged("version"),
                      "trailer_crc_mismatch": damaged("crc"), "all_three_broken": damaged("magic", "version", "crc")},
            "capture_errors": failures,
        },
    }


def _version_offset():
    ahead = SPEC["header_order"][:SPEC["header_order"].index("version")]
    return len(MAGIC) + struct.calcsize("<" + "".join(FIELD_FORMATS[n] for n in ahead))


def main(args):
    if len(args) == 2 and args[0] == "--reports-json":
        print(json.dumps(reports(Path(args[1])), sort_keys=True, separators=(",", ":")))
        return 0
    if len(args) == 1:
        with open(args[0], "rb") as stream:
            print(json.dumps(decode(stream.read())))
        return 0
    if len(args) == 2:
        with open(args[0], encoding="utf-8") as stream:
            doc = json.load(stream)
        with open(args[1], "wb") as stream:
            stream.write(encode(doc))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
