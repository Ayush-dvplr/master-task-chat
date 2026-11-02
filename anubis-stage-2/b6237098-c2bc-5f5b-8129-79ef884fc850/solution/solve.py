#!/usr/bin/env python3
"""MDUMP codec for revision 3 and the 4.x, 5.x and 6.x field builds.

python3 solve.py <capture>               decode, print one JSON object
python3 solve.py <document.json> <out>   encode a decoded document back to bytes (exit 1 if inconsistent)
python3 solve.py --reports-json <log>    print the four /app/out report documents
python3 solve.py --derive-field-builds <data dir>   recover the 4.x and 5.x parameters
"""
import hashlib
import json
from pathlib import Path
import re
import sys

MAGIC = b"COREZ"
VERSION = 1
HEADER_LEN = 16
TRAILER_LEN = 4

# Grammar summary, transcribed from the container format specification.
GRAMMAR = {
    "header_order": ["record_count", "salt", "flags", "base_value", "version"],
    "selector": {"mode_bits": [0, 3], "wide_bit": 4, "long_key_bit": 6, "reserved_bits": [1, 2, 5, 7],
                 "mode_ids": {"dict": 0, "raw": 1, "delta": 2, "repeat": 3}},
    "flag_bits": {"reserved_bit_0": 0, "front_coded_keys": 1, "big_endian_raw": 2, "whitened": 3},
    "delta_encoding": "signed_leb128",
    "dict_source": "payload_values",
    "dict_direction": "backward",
    "dict_capacity": 40,
    "dict_move_to_front": True,
    "crc_algorithm": "crc32c",
    "crc_coverage": "header_records",
}
PRECEDENCE = ["bad_magic", "truncated_header", "unsupported_version", "reserved_flag_set",
              "trailer_crc_mismatch", "truncated_record", "reserved_selector_bits", "varint_overlong",
              "noncanonical_varint", "bad_key_prefix", "invalid_utf8_key", "dict_index_out_of_range",
              "repeat_without_delta", "trailing_bytes"]

FLAG_BIT = GRAMMAR["flag_bits"]
MODE_OF = {ident: name for name, ident in GRAMMAR["selector"]["mode_ids"].items()}
ID_OF = GRAMMAR["selector"]["mode_ids"]
WIDE = 0x10
LONG = 0x40
SELECTOR_SPARE_BITS = (1, 2, 3, 5, 7)
CASTAGNOLI = 0x82F63B78
VARINT_LIMIT = 10

# Per build: keystream taps, zero-salt stand-in and the header field folded into
# the salt, CRC polynomial and the first header byte it covers, the selector bit
# carrying mode value 2, delta storage, dictionary window and lookup, what each
# record appends to the dictionary, and the extra multiplier a repeat adds.
BUILDS = {
    1: {"taps": 0xE10000, "zero": 0xC0FFEE, "fold": None, "poly": CASTAGNOLI, "crc_init": 0xFFFFFFFF,
        "crc_final": 0xFFFFFFFF, "crc_from": 5, "mode_bit": 3, "delta": "sleb", "window": 40,
        "lookup": "back_mtf", "append": "payload", "repeat_extra": 0},
}
# The field builds are not in the specification. solve.sh recovers their
# parameters with --derive-field-builds from the shipped notes, decodings,
# fingerprints and capture log, and writes them here when it installs the codec.
FIELD_BUILDS = None
if FIELD_BUILDS is not None:
    for _version, _build in FIELD_BUILDS.items():
        BUILDS[int(_version)] = _build


_CRC_ROWS = {}


def crc_rows(poly):
    if poly not in _CRC_ROWS:
        rows = []
        for byte in range(256):
            reg = byte
            for _ in range(8):
                reg = (reg >> 1) ^ poly if reg & 1 else reg >> 1
            rows.append(reg)
        _CRC_ROWS[poly] = rows
    return _CRC_ROWS[poly]


def crc32r(data, poly, init=0xFFFFFFFF, final=0xFFFFFFFF):
    rows = crc_rows(poly)
    reg = init
    for byte in data:
        reg = rows[(reg ^ byte) & 0xFF] ^ (reg >> 8)
    return reg ^ final


def trailer_of(data, build):
    return crc32r(data, build["poly"], build["crc_init"], build["crc_final"])


HEADER_FIELDS = {
    "record_count": lambda h: int.from_bytes(h[5:7], "little"),
    "flags": lambda h: h[10],
    "base_low24": lambda h: int.from_bytes(h[11:14], "little"),
    "base_high24": lambda h: int.from_bytes(h[12:15], "little"),
    "version": lambda h: h[15],
}


def stream_start(header, build):
    salt = int.from_bytes(header[7:10], "little")
    if build["fold"]:
        op, field = build["fold"]
        other = HEADER_FIELDS[field](header)
        salt = salt ^ other if op == "xor" else (salt + other) & 0xFFFFFF
    return salt or build["zero"]


def whiten(data, start, taps):
    state = start
    out = bytearray(len(data))
    for i, byte in enumerate(data):
        for _ in range(8):
            state = (state >> 1) ^ taps if state & 1 else state >> 1
        out[i] = byte ^ (state & 0xFF)
    return bytes(out)


def to_i32(number):
    number &= 0xFFFFFFFF
    return number - (1 << 32) if number & 0x80000000 else number


def put_uleb(number, pad=0):
    out = bytearray()
    while True:
        low = number & 0x7F
        number >>= 7
        out.append(low | (0x80 if number else 0))
        if not number:
            break
    if pad:
        out[-1] |= 0x80
        out += bytes([0x80] * (pad - 1)) + b"\x00"
    return bytes(out)


def put_sleb(number, pad=0):
    out = bytearray()
    negative = number < 0
    while True:
        low = number & 0x7F
        number >>= 7
        done = (number == 0 and not low & 0x40) or (number == -1 and low & 0x40)
        out.append(low if done else low | 0x80)
        if done:
            break
    if pad:
        fill = 0x7F if negative else 0x00
        out[-1] |= 0x80
        out += bytes([fill | 0x80] * (pad - 1)) + bytes([fill])
    return bytes(out)


# Unsigned-framed delta storages: stored integer -> value, value -> stored integer.
DELTA_FORMS = {
    "zigzag": (lambda u: -((u + 1) >> 1) if u & 1 else u >> 1, lambda v: 2 * v if v >= 0 else -2 * v - 1),
    "unsigned": (lambda u: u, lambda v: v),
    "sign_low_bit": (lambda u: -(u >> 1) if u & 1 else u >> 1, lambda v: 2 * v if v >= 0 else -2 * v + 1),
}


def put_delta(value, pad, build):
    if build["delta"] == "sleb":
        return put_sleb(value, pad)
    return put_uleb(DELTA_FORMS[build["delta"]][1](value), pad)


def selector_bits(build):
    reserved = 0
    for bit in SELECTOR_SPARE_BITS:
        if bit != build["mode_bit"]:
            reserved |= 1 << bit
    return reserved


class Reject(Exception):
    def __init__(self, code, **extra):
        super().__init__(code)
        self.code, self.extra = code, extra


class Reader:
    def __init__(self, data):
        self.data, self.at = data, 0

    def byte(self):
        if self.at >= len(self.data):
            raise Reject("truncated_record")
        self.at += 1
        return self.data[self.at - 1]

    def take(self, count):
        if self.at + count > len(self.data):
            raise Reject("truncated_record")
        self.at += count
        return self.data[self.at - count:self.at]

    def varint(self, minimal):
        total = 0
        for i in range(VARINT_LIMIT):
            byte = self.byte()
            total |= (byte & 0x7F) << (7 * i)
            if not byte & 0x80:
                if minimal and i > 0 and byte == 0:
                    raise Reject("noncanonical_varint")
                return total, i + 1
        raise Reject("varint_overlong")

    def sleb(self):
        total = 0
        for i in range(VARINT_LIMIT):
            byte = self.byte()
            total |= (byte & 0x7F) << (7 * i)
            if not byte & 0x80:
                if byte & 0x40:
                    total -= 1 << (7 * i + 7)
                return total, i + 1
        raise Reject("varint_overlong")

    def delta(self, build):
        if build["delta"] == "sleb":
            value, used = self.sleb()
            return value, used - len(put_sleb(value))
        stored, used = self.varint(minimal=False)
        return DELTA_FORMS[build["delta"]][0](stored), used - len(put_uleb(stored))


def pick_entry(table, index, lookup):
    position = len(table) - 1 - index if lookup.startswith("back") else index
    hit = table[position]
    if lookup.endswith("mtf"):
        table.pop(position)
        table.append(hit)
    return hit


def plain_body(blob, build):
    body = blob[HEADER_LEN:-TRAILER_LEN]
    if blob[10] & (1 << FLAG_BIT["whitened"]):
        body = whiten(body, stream_start(blob[:HEADER_LEN], build), build["taps"])
    return body


def decode(blob, builds=None):
    builds = BUILDS if builds is None else builds
    if len(blob) < 5 or blob[:5] != MAGIC:
        return {"error": "bad_magic"}
    if len(blob) < HEADER_LEN + TRAILER_LEN:
        return {"error": "truncated_header", "length": len(blob)}
    if blob[15] not in builds:
        return {"error": "unsupported_version", "version": blob[15]}
    build = builds[blob[15]]
    flag_byte = blob[10]
    if flag_byte & 0xF0:
        return {"error": "reserved_flag_set", "flags": flag_byte}
    flags = {name: bool(flag_byte & (1 << bit)) for name, bit in FLAG_BIT.items()}
    salt = int.from_bytes(blob[7:10], "little")
    body = plain_body(blob, build)
    stored = int.from_bytes(blob[-TRAILER_LEN:], "little")
    computed = trailer_of(blob[build["crc_from"]:HEADER_LEN] + body, build)
    if stored != computed:
        return {"error": "trailer_crc_mismatch", "stored": stored, "computed": computed}
    count = int.from_bytes(blob[5:7], "little")
    base = int.from_bytes(blob[11:15], "little", signed=True)
    endian = "big" if flags["big_endian_raw"] else "little"
    reserved = selector_bits(build)
    cur = Reader(body)
    running, last_step, table, previous, rows = base, None, [], b"", []
    for index in range(count):
        mark = cur.at
        try:
            sel = cur.byte()
            mode = MODE_OF[(sel & 1) | (((sel >> build["mode_bit"]) & 1) << 1)]
            if sel & reserved or (mode != "raw" and sel & WIDE):
                raise Reject("reserved_selector_bits", selector=sel)
            row = {"mode": mode, "long_key": bool(sel & LONG), "offset": mark}
            if row["long_key"]:
                if flags["front_coded_keys"]:
                    mark = cur.at
                    shared = cur.varint(minimal=True)[0]
                    if shared > len(previous):
                        raise Reject("bad_key_prefix", key_prefix=shared)
                    mark = cur.at
                    length = cur.varint(minimal=True)[0]
                    mark = cur.at
                    name = previous[:shared] + cur.take(length)
                    row["key_prefix"] = shared
                else:
                    mark = cur.at
                    length = cur.varint(minimal=True)[0]
                    mark = cur.at
                    name = cur.take(length)
                try:
                    row["key"] = name.decode("utf-8")
                except UnicodeDecodeError:
                    raise Reject("invalid_utf8_key") from None
                previous = name
            else:
                mark = cur.at
                row["key"] = cur.byte()
            mark = cur.at
            if mode == "raw":
                wide = bool(sel & WIDE)
                payload = int.from_bytes(cur.take(4 if wide else 2), endian, signed=True)
                running = payload
                row.update(wide_value=wide, raw_value=payload)
            elif mode == "delta":
                payload, pad = cur.delta(build)
                running = to_i32(running + payload)
                last_step = payload
                row.update(delta_raw=payload, delta_pad=pad)
            elif mode == "dict":
                payload = cur.byte()
                if payload >= len(table):
                    raise Reject("dict_index_out_of_range", dict_index=payload, dict_size=len(table))
                running = to_i32(pick_entry(table, payload, build["lookup"]))
                row["dict_index"] = payload
            else:
                payload = cur.byte()
                if last_step is None:
                    raise Reject("repeat_without_delta")
                running = to_i32(running + last_step * (payload + build["repeat_extra"]))
                row["repeat_count"] = payload
            row["value"] = running
            table.append(running if build["append"] == "value" else payload)
            if len(table) > build["window"]:
                table.pop(0)
            rows.append(row)
        except Reject as exc:
            return {"error": exc.code, "record_index": index, **exc.extra, "offset": mark}
    if cur.at != len(body):
        return {"error": "trailing_bytes", "count": len(body) - cur.at, "offset": cur.at}
    return {"version": blob[15], "flags": flags, "salt": salt, "record_count": count,
            "base_value": base, "records": rows}


def encode(doc):
    if doc["record_count"] != len(doc["records"]):
        raise ValueError("record_count does not match the records array")
    build = BUILDS[doc["version"]]
    flags = doc["flags"]
    flag_byte = sum(1 << bit for name, bit in FLAG_BIT.items() if flags[name])
    header = (MAGIC + doc["record_count"].to_bytes(2, "little") + doc["salt"].to_bytes(3, "little")
              + bytes([flag_byte]) + doc["base_value"].to_bytes(4, "little", signed=True)
              + bytes([doc["version"]]))
    endian = "big" if flags["big_endian_raw"] else "little"
    body = bytearray()
    for row in doc["records"]:
        ident = ID_OF[row["mode"]]
        sel = (ident & 1) | (((ident >> 1) & 1) << build["mode_bit"])
        if row["mode"] == "raw" and row["wide_value"]:
            sel |= WIDE
        if row["long_key"]:
            sel |= LONG
        body.append(sel)
        if row["long_key"]:
            name = row["key"].encode("utf-8")
            if flags["front_coded_keys"]:
                shared = row["key_prefix"]
                body += put_uleb(shared) + put_uleb(len(name) - shared) + name[shared:]
            else:
                body += put_uleb(len(name)) + name
        else:
            body.append(row["key"])
        if row["mode"] == "raw":
            body += row["raw_value"].to_bytes(4 if row["wide_value"] else 2, endian, signed=True)
        elif row["mode"] == "delta":
            body += put_delta(row["delta_raw"], row["delta_pad"], build)
        elif row["mode"] == "dict":
            body.append(row["dict_index"])
        else:
            body.append(row["repeat_count"])
    trailer = trailer_of(header[build["crc_from"]:] + bytes(body), build).to_bytes(4, "little")
    wire = whiten(bytes(body), stream_start(header, build), build["taps"]) if flags["whitened"] else bytes(body)
    return header + wire + trailer


def refusal(doc, blob):
    rebuilt = decode(blob)["records"]
    for index, (given, actual) in enumerate(zip(doc["records"], rebuilt)):
        for field in ("offset", "value"):
            stored = given.get(field)
            if type(stored) is not int or stored != actual[field]:
                return {"error": "inconsistent_document", "record_index": index, "field": field}
    return None


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(obj):
    return hashlib.sha256(canonical(obj).encode("ascii")).hexdigest()


# --------------------------------------------------------------------------- #
# Recovery of the 4.x build from its notes and hand-verified decodings.       #
# --------------------------------------------------------------------------- #

def keystream_bytes(start, taps, count):
    return whiten(bytes(count), start, taps)


def recover_taps(salt_one_bytes, other_salt, other_bytes):
    # From salt 1 the first clock loads the register with the taps themselves,
    # and the low byte after eight clocks only sees tap bits 0..14, so the low
    # 15 bits are searched first and the high 9 bits only for the survivors.
    found = []
    for low in range(1 << 15):
        if keystream_bytes(1, low, 1)[0] != salt_one_bytes[0]:
            continue
        for high in range(1 << 9):
            taps = (high << 15) | low
            if (keystream_bytes(1, taps, len(salt_one_bytes)) == salt_one_bytes
                    and keystream_bytes(other_salt, taps, len(other_bytes)) == other_bytes):
                found.append(taps)
    if len(found) != 1:
        raise SystemExit(f"keystream taps not unique: {[hex(t) for t in found]}")
    return found[0]


def recover_zero_salt_start(taps, zero_bytes):
    # The state after the first eight clocks ends in the first keystream byte,
    # so only its high 16 bits are unknown; the clocks are then run backwards.
    # Undoing a clock needs tap bit 23, which makes bit 23 of the new state
    # equal to the bit that was shifted out.
    if not taps & 0x800000:
        raise SystemExit("taps without bit 23 cannot be run backwards")
    hits = [state for state in ((high << 8) | zero_bytes[0] for high in range(1 << 16))
            if keystream_bytes(state, taps, len(zero_bytes) - 1) == zero_bytes[1:]]
    if len(hits) != 1:
        raise SystemExit(f"zero-salt stand-in not unique: {len(hits)} candidates")
    state = hits[0]
    for _ in range(8):
        out_bit = state >> 23 & 1
        state = (((state ^ (taps if out_bit else 0)) << 1) | out_bit) & 0xFFFFFF
    return state


def derive_4x(data):
    notes = (data / "MDUMP-rev4-field-notes.md").read_text(encoding="utf-8")
    measured = {int(salt, 16): bytes.fromhex(stream)
                for salt, stream in re.findall(r"salt `0x([0-9a-fA-F]{6})`: `([0-9a-f ]+)`", notes)}
    other_salt = next(salt for salt in measured if salt not in (0, 1))
    taps = recover_taps(measured[1], other_salt, measured[other_salt])
    zero = recover_zero_salt_start(taps, measured[0])
    verified = [json.loads(line) for line in (data / "MDUMP-rev4-verified.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()]
    base = dict(BUILDS[1], taps=taps, zero=zero)
    documents = [bytes.fromhex(row["hex"]) for row in verified if "error" not in row["decoded"]]
    starts = [start for start in range(HEADER_LEN)
              if all(crc32r(blob[start:HEADER_LEN] + plain_body(blob, base), CASTAGNOLI)
                     == int.from_bytes(blob[-TRAILER_LEN:], "little") for blob in documents)]
    if len(starts) != 1:
        raise SystemExit(f"4.x trailer start not unique: {starts}")
    fits = []
    for window in range(1, 41):
        for append in ("payload", "value"):
            for repeat_extra in (0, 1, 2):
                build = dict(base, crc_from=starts[0], window=window, append=append, repeat_extra=repeat_extra)
                if all(canonical(decode(bytes.fromhex(row["hex"]), {2: build})) == canonical(row["decoded"])
                       for row in verified):
                    fits.append(build)
    if len(fits) != 1:
        raise SystemExit(f"{len(fits)} 4.x rule sets fit every verified decoding")
    return fits[0]


# --------------------------------------------------------------------------- #
# Recovery of the 5.x build from raw logged captures and fingerprints.        #
# --------------------------------------------------------------------------- #

def layout_parses(blob, mode_bit):
    """True when the body splits into exactly record_count records under this selector layout."""
    body, front = blob[HEADER_LEN:-TRAILER_LEN], bool(blob[10] & (1 << FLAG_BIT["front_coded_keys"]))
    reserved = selector_bits({"mode_bit": mode_bit})
    cur = Reader(body)
    try:
        for _ in range(int.from_bytes(blob[5:7], "little")):
            sel = cur.byte()
            mode = (sel & 1) | (((sel >> mode_bit) & 1) << 1)
            if sel & reserved or (mode != ID_OF["raw"] and sel & WIDE):
                return False
            if sel & LONG:
                if front:
                    cur.varint(minimal=True)
                cur.take(cur.varint(minimal=True)[0])
            else:
                cur.byte()
            if mode == ID_OF["raw"]:
                cur.take(4 if sel & WIDE else 2)
            elif mode == ID_OF["delta"]:
                cur.varint(minimal=False)
            else:
                cur.byte()
    except Reject:
        return False
    return cur.at == len(body)


def bit_poly(data):
    """The message as a GF(2) polynomial in transmission order (each byte low bit first)."""
    value = 0
    for byte in data:
        for i in range(8):
            value = (value << 1) | ((byte >> i) & 1)
    return value


def rev32(x):
    return int(f"{x:032b}"[::-1], 2)


def poly_mod(a, b):
    width = b.bit_length()
    while a.bit_length() >= width:
        a ^= b << (a.bit_length() - width)
    return a


def poly_gcd(a, b):
    while b:
        a, b = b, poly_mod(a, b)
    return a


def recover_polynomial(samples):
    # For a reflected CRC the init and final XOR cancel between two messages of
    # equal length, so rev32(crc(a) ^ crc(b)) == (bits(a ^ b) * x^32) mod P.
    # Every such pair therefore gives a multiple of P; the gcd of a few
    # undamaged pairs is P itself.
    by_length = {}
    for message, stored in samples:
        by_length.setdefault(len(message), []).append((message, stored))
    multiples = []
    for group in by_length.values():
        for (a, ca), (b, cb) in zip(group[::2], group[1::2]):
            diff = bytes(x ^ y for x, y in zip(a, b))
            multiples.append((bit_poly(diff) << 32) ^ rev32(ca ^ cb))
    for i, first in enumerate(multiples):
        for second in multiples[i + 1:i + 6]:
            g = poly_gcd(first, second)
            if g.bit_length() != 33:
                continue
            poly = rev32(g & 0xFFFFFFFF)
            conventions = recover_conventions(samples, poly)
            if conventions is not None:
                return (poly, *conventions)
    raise SystemExit("no 32-bit generator fits the unwhitened 5.x trailers")


def solve_gf2(columns, target):
    """Solve sum(x_j * columns[j]) == target over GF(2) for a 32-bit x, or None."""
    rows = []
    for bit in range(32):
        row = sum(((columns[j] >> bit) & 1) << j for j in range(32))
        rows.append([row, (target >> bit) & 1])
    x, pivots = 0, []
    for col in range(32):
        pivot = next((r for r in range(len(pivots), 32) if rows[r][0] >> col & 1), None)
        if pivot is None:
            continue
        rank = len(pivots)
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for r in range(32):
            if r != rank and rows[r][0] >> col & 1:
                rows[r][0] ^= rows[rank][0]
                rows[r][1] ^= rows[rank][1]
        pivots.append(col)
    if any(row[0] == 0 and row[1] for row in rows):
        return None
    for rank, col in enumerate(pivots):
        x |= rows[rank][1] << col
    return x


def recover_conventions(samples, poly):
    # With the polynomial known, crc(m) ^ crc_raw(m) depends only on len(m):
    # it is Z_len(init) ^ final, where Z_len runs the register over len zero
    # bytes and is linear in init. Two lengths give a linear system for init.
    def offset(message, stored):
        return stored ^ crc32r(message, poly, 0, 0)

    def zeros(length, init):
        return crc32r(bytes(length), poly, init, 0)

    lengths = {}
    for message, stored in samples:
        lengths.setdefault(len(message), (message, stored))
    pairs = list(lengths.values())
    for (m1, s1), (m2, s2) in zip(pairs, pairs[1:]):
        columns = [zeros(len(m1), 1 << j) ^ zeros(len(m2), 1 << j) for j in range(32)]
        init = solve_gf2(columns, offset(m1, s1) ^ offset(m2, s2))
        if init is None:
            continue
        final = offset(m1, s1) ^ zeros(len(m1), init)
        hits = sum(crc32r(m, poly, init, final) == s for m, s in samples)
        if hits * 10 >= len(samples) * 8:
            return init, final
    return None


FOLDS = [None] + [(op, field) for op in ("xor", "add") for field in HEADER_FIELDS]


def derive_5x(data, four):
    log = [bytes.fromhex(json.loads(line)["hex"])
           for line in (data / "MDUMP-capture-log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    v3 = [b for b in log if len(b) >= HEADER_LEN + TRAILER_LEN and b[:5] == MAGIC and b[15] == 3
          and not b[10] & 0xF0]
    plain = [b for b in v3 if not b[10] & (1 << FLAG_BIT["whitened"])]
    whitened = [b for b in v3 if b[10] & (1 << FLAG_BIT["whitened"])]

    scores = sorted(((sum(layout_parses(b, bit) for b in plain), bit) for bit in SELECTOR_SPARE_BITS), reverse=True)
    if scores[0][0] <= 2 * scores[1][0]:
        raise SystemExit(f"5.x selector layout not unique: {scores}")
    mode_bit = scores[0][1]

    crc_from = four["crc_from"]
    poly, crc_init, crc_final = recover_polynomial(
        [(b[crc_from:-TRAILER_LEN], int.from_bytes(b[-TRAILER_LEN:], "little")) for b in plain])

    base = dict(four, poly=poly, crc_init=crc_init, crc_final=crc_final, mode_bit=mode_bit)
    fold_hits = []
    for fold in FOLDS:
        build = dict(base, fold=fold)
        hits = sum(trailer_of(b[crc_from:HEADER_LEN] + plain_body(b, build), build)
                   == int.from_bytes(b[-TRAILER_LEN:], "little") for b in whitened)
        fold_hits.append((hits, fold))
    fold_hits.sort(key=lambda item: item[0], reverse=True)
    if fold_hits[0][0] <= 2 * fold_hits[1][0]:
        raise SystemExit(f"5.x keystream start not unique: {fold_hits[:3]}")
    base["fold"] = fold_hits[0][1]

    prints = [json.loads(line) for line in (data / "MDUMP-rev5-fingerprints.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    prints = [(bytes.fromhex(row["hex"]), row["sha256"]) for row in prints]

    def matches(build):
        return sum(fingerprint(decode(blob, {3: build})) == want for blob, want in prints)

    delta_hits = sorted(((matches(dict(base, delta=form)), form) for form in ("sleb", *DELTA_FORMS)), reverse=True)
    if delta_hits[0][0] == delta_hits[1][0]:
        raise SystemExit(f"5.x delta storage not unique: {delta_hits}")
    base["delta"] = delta_hits[0][1]

    fits = []
    for window in range(1, 65):
        for lookup in ("back_mtf", "back_static", "forward_mtf", "forward_static"):
            for append in ("payload", "value"):
                build = dict(base, window=window, lookup=lookup, append=append)
                if matches(build) == len(prints):
                    fits.append(build)
    if len(fits) != 1:
        raise SystemExit(f"{len(fits)} 5.x dictionary rule sets fit every fingerprint")
    return fits[0]


def derive_field_builds(data_dir):
    data = Path(data_dir)
    four = derive_4x(data)
    six = {
        "taps": 0xB40000,
        "zero": 0x13579B,
        "fold": ("add", "base_high24"),
        "poly": 0xEDB88320,
        "crc_init": 0xFFFFFFFF,
        "crc_final": 0x00000000,
        "crc_from": 0,
        "mode_bit": 3,
        "delta": "sign_low_bit",
        "window": 16,
        "lookup": "forward_mtf",
        "append": "payload",
        "repeat_extra": 2,
    }
    return {"2": four, "3": derive_5x(data, four), "4": six}


# --------------------------------------------------------------------------- #
# Reports.                                                                    #
# --------------------------------------------------------------------------- #

def build(flags, salt, base, rows, version=VERSION):
    full = {"reserved_bit_0": False, "front_coded_keys": False, "big_endian_raw": False, "whitened": False}
    full.update(flags)
    return encode({"version": version, "flags": full, "salt": salt, "record_count": len(rows),
                   "base_value": base, "records": rows})


def own_examples():
    return [
        ("plain_raw_delta_dict", build({}, 0, 100, [
            {"key": 7, "long_key": False, "mode": "raw", "wide_value": False, "raw_value": -2},
            {"key": 8, "long_key": False, "mode": "delta", "delta_raw": 300, "delta_pad": 0},
            {"key": 9, "long_key": False, "mode": "dict", "dict_index": 0},
            {"key": "frame.pc", "long_key": True, "mode": "raw", "wide_value": True, "raw_value": 2147483647},
        ])),
        ("whitened_repeat_wrap", build({"whitened": True}, 0x00BEEF, 2147483000, [
            {"key": 1, "long_key": False, "mode": "delta", "delta_raw": 1000, "delta_pad": 0},
            {"key": 2, "long_key": False, "mode": "repeat", "repeat_count": 3},
            {"key": 3, "long_key": False, "mode": "delta", "delta_raw": -5, "delta_pad": 2},
            {"key": 4, "long_key": False, "mode": "repeat", "repeat_count": 0},
        ])),
        ("front_coded_utf8_split", build({"front_coded_keys": True}, 0, -7, [
            {"key": "caf\u00e9.\u00e9", "long_key": True, "mode": "raw", "wide_value": False, "raw_value": 5, "key_prefix": 0},
            {"key": "caf\u00e9.\u00e8", "long_key": True, "mode": "delta", "delta_raw": 7, "delta_pad": 0, "key_prefix": 7},
            {"key": "caf\u00e9.\u00e8.3", "long_key": True, "mode": "dict", "dict_index": 1, "key_prefix": 8},
        ])),
        ("big_endian_move_to_front", build({"big_endian_raw": True, "reserved_bit_0": True}, 0x123456, 0, [
            {"key": 16, "long_key": False, "mode": "raw", "wide_value": True, "raw_value": 0x01020304},
            {"key": 17, "long_key": False, "mode": "raw", "wide_value": False, "raw_value": -300},
            {"key": 18, "long_key": False, "mode": "raw", "wide_value": False, "raw_value": 77},
            {"key": 19, "long_key": False, "mode": "dict", "dict_index": 2},
            {"key": 20, "long_key": False, "mode": "dict", "dict_index": 3},
        ])),
        ("rev4_whitened_zero_salt", build({"whitened": True}, 0, 40, [
            {"key": 1, "long_key": False, "mode": "delta", "delta_raw": 12, "delta_pad": 0},
            {"key": 2, "long_key": False, "mode": "repeat", "repeat_count": 0},
            {"key": 3, "long_key": False, "mode": "raw", "wide_value": False, "raw_value": -9},
            {"key": 4, "long_key": False, "mode": "dict", "dict_index": 1},
        ], version=2)),
        ("rev5_whitened_folded_seed", build({"whitened": True}, 0x00ABCD, -123456, [
            {"key": 5, "long_key": False, "mode": "delta", "delta_raw": -77, "delta_pad": 1},
            {"key": 6, "long_key": False, "mode": "repeat", "repeat_count": 2},
            {"key": 7, "long_key": False, "mode": "raw", "wide_value": True, "raw_value": 99},
            {"key": 8, "long_key": False, "mode": "dict", "dict_index": 0},
            {"key": 9, "long_key": False, "mode": "dict", "dict_index": 2},
        ], version=3)),
        ("rev6_forward_dictionary", build({"whitened": True}, 0, 0x12345678, [
            {"key": 10, "long_key": False, "mode": "raw", "wide_value": False, "raw_value": 12},
            {"key": 11, "long_key": False, "mode": "delta", "delta_raw": -9, "delta_pad": 1},
            {"key": 12, "long_key": False, "mode": "repeat", "repeat_count": 0},
            {"key": 13, "long_key": False, "mode": "dict", "dict_index": 0},
        ], version=4)),
    ]


def reports(log_path):
    lines, trips, counts = [], [], {"raw": 0, "delta": 0, "dict": 0, "repeat": 0}
    for name, blob in own_examples():
        doc = decode(blob)
        for row in doc["records"]:
            counts[row["mode"]] += 1
        lines.append({"name": name, "hex": blob.hex(), "decoded": doc})
        again = encode(doc)
        trips.append({"name": name, "input_sha256": hashlib.sha256(blob).hexdigest(),
                      "rebuilt_sha256": hashlib.sha256(again).hexdigest(),
                      "byte_length": len(blob), "roundtrip_equal": again == blob})
    status, digests, failures, ok = {}, {}, {}, 0
    modes = {"raw": 0, "delta": 0, "dict": 0, "repeat": 0}
    flag_counts = {name: 0 for name in FLAG_BIT}
    for raw_line in Path(log_path).read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        entry = json.loads(raw_line)
        result = decode(bytes.fromhex(entry["hex"]))
        digests[entry["capture_id"]] = fingerprint(result)
        if "error" in result:
            status[entry["capture_id"]] = result["error"]
            failures[result["error"]] = failures.get(result["error"], 0) + 1
            continue
        status[entry["capture_id"]] = "ok"
        ok += 1
        for row in result["records"]:
            modes[row["mode"]] += 1
        for name, value in result["flags"].items():
            flag_counts[name] += int(value)
    first = own_examples()[0][1]

    def damaged(*kinds):
        out = bytearray(first)
        for kind in kinds:
            if kind == "magic":
                out[0] ^= 0xFF
            elif kind == "version":
                out[15] = 9
            elif kind == "flags":
                out[10] |= 0x80
            else:
                out[-1] ^= 0xFF
        return decode(bytes(out))

    def one_byte_longer():
        build_rules = BUILDS[first[15]]
        whitened = bool(first[10] & (1 << FLAG_BIT["whitened"]))
        start = stream_start(first[:HEADER_LEN], build_rules)
        plain = plain_body(first, build_rules) + b"\x00"
        trailer = trailer_of(first[build_rules["crc_from"]:HEADER_LEN] + plain, build_rules).to_bytes(4, "little")
        wire = whiten(plain, start, build_rules["taps"]) if whitened else plain
        return decode(first[:HEADER_LEN] + wire + trailer)

    format_report = {"format_tag": "MDUMP", "magic_hex": MAGIC.hex(), "version": VERSION,
                     "header_size": HEADER_LEN, "trailer_size": TRAILER_LEN}
    format_report.update(GRAMMAR)
    format_report.update({
        "visible_example_count": len(lines),
        "visible_record_counts": [line["decoded"]["record_count"] for line in lines],
        "visible_mode_counts": counts,
        "capture_count": len(status), "capture_ok_count": ok,
        "capture_mode_counts": modes, "capture_flag_counts": flag_counts,
        "capture_status": status, "capture_sha256": digests,
    })
    return {
        "decoded_examples": lines,
        "format_report": format_report,
        "roundtrip_report": {"all_roundtrips_equal": all(t["roundtrip_equal"] for t in trips), "examples": trips},
        "error_analysis": {
            "precedence": PRECEDENCE,
            "cases": {"bad_magic": damaged("magic"), "unsupported_version": damaged("version"),
                      "reserved_flag_set": damaged("flags"), "trailer_crc_mismatch": damaged("crc"),
                      "all_three_broken": damaged("magic", "version", "crc"),
                      "trailing_bytes": one_byte_longer()},
            "capture_errors": dict(sorted(failures.items())),
        },
    }


def main(args):
    if len(args) == 2 and args[0] == "--derive-field-builds":
        print(json.dumps(derive_field_builds(args[1]), sort_keys=True))
        return 0
    if len(args) == 2 and args[0] == "--reports-json":
        print(json.dumps(reports(args[1]), sort_keys=True, separators=(",", ":")))
        return 0
    if len(args) == 1:
        with open(args[0], "rb") as stream:
            print(json.dumps(decode(stream.read())))
        return 0
    if len(args) == 2:
        with open(args[0], encoding="utf-8") as stream:
            doc = json.load(stream)
        blob = encode(doc)
        problem = refusal(doc, blob)
        if problem is not None:
            print(json.dumps(problem))
            return 1
        with open(args[1], "wb") as stream:
            stream.write(blob)
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
