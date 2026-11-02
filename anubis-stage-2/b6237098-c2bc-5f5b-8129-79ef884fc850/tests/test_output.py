"""Verifier for the MDUMP crash-dump container (revision 3).

This file is self-contained. It carries an independent MDUMP encoder (with a
damage-injection hook), a reference decoder, a deterministic corpus builder
for the shipped capture log and for the hidden evaluation tier, a trap
analyser that labels every capture with the rules a careless decoder breaks
on it, and the complete check bank.

Harbor runs test.sh in a SEPARATE container that has no /app/data. Every
corpus is therefore regenerated here from the seed constants below; the
capture log rebuilt by capture_log() is byte-identical to the shipped
/app/data/MDUMP-capture-log.jsonl.

Negative-weight checks are polarity-inverted: each returns True only when the
cheat is present, so an honest submission leaves them at zero.
"""

from __future__ import annotations

import ast
import grp
import hashlib
import json
import os
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion


def _legacy_criterion(*, description: str):
    """Leave focused probes callable without scoring each fixture separately."""
    del description

    def decorate(func):
        return func

    return decorate


# --------------------------------------------------------------------------- #
# Format constants (revision 3 of the MDUMP specification).                   #
# --------------------------------------------------------------------------- #

MAGIC = b"COREZ"
VERSION = 1
HEADER_SIZE = 16
TRAILER_SIZE = 4

GRAMMAR: dict[str, Any] = {
    "header_order": ["record_count", "salt", "flags", "base_value", "version"],
    "selector": {
        "mode_bits": [0, 3],
        "wide_bit": 4,
        "long_key_bit": 6,
        "reserved_bits": [1, 2, 5, 7],
        "mode_ids": {"dict": 0, "raw": 1, "delta": 2, "repeat": 3},
    },
    "flag_bits": {"reserved_bit_0": 0, "front_coded_keys": 1, "big_endian_raw": 2, "whitened": 3},
    "delta_encoding": "signed_leb128",
    "dict_source": "payload_values",
    "dict_direction": "backward",
    "dict_capacity": 40,
    "dict_move_to_front": True,
    "crc_algorithm": "crc32c",
    "crc_coverage": "header_records",
}

FLAG_BITS = GRAMMAR["flag_bits"]
FLAG_RESERVED_MASK = 0xF0
SEL_WIDE = 1 << 4
SEL_LONG = 1 << 6
SEL_RESERVED_MASK = (1 << 1) | (1 << 2) | (1 << 5) | (1 << 7)
MODE_IDS = GRAMMAR["selector"]["mode_ids"]
MODE_BY_ID = {v: k for k, v in MODE_IDS.items()}
DICT_CAPACITY = 40
LFSR_TAPS = 0xE10000
LFSR_ZERO_SALT = 0xC0FFEE
CRC32C_POLY = 0x82F63B78
MAX_VARINT = 10

# 4.x field builds write version byte 2. None of these values is stated in the
# shipped files; each is fixed by the 4.x notes' keystream check values and the
# hand-verified decodings (see verified_sample()).
FIELD_VERSION = 2
LFSR_TAPS_V2 = 0xD20400
LFSR_ZERO_SALT_V2 = 0x5A17C3
DICT_CAPACITY_V2 = 24
CRC_START_V2 = 0  # 4.x and 5.x checksum the whole header, magic included

# 5.x field builds write version byte 3 and inherit every 4.x change except the
# ones below. None of these is stated in the shipped files either: the trailer
# polynomial follows from the stored trailers of unwhitened 5.x captures in the
# log, the keystream start from the trailers of whitened ones, the selector
# layout from which layout parses the logged bodies to their exact length, and
# the delta and dictionary rules from the decoder fingerprints shipped as
# MDUMP-rev5-fingerprints.jsonl (see fingerprint_sample()).
FIELD5_VERSION = 3
FIELD6_VERSION = 4
SUPPORTED_VERSIONS = (VERSION, FIELD_VERSION, FIELD5_VERSION, FIELD6_VERSION)
CRC_POLY_V3 = 0xA2E1C19B  # reflected generator
CRC_INIT_V3 = 0x00000000  # final XOR stays 0xFFFFFFFF
DICT_CAPACITY_V3 = 32
LFSR_TAPS_V4 = 0xB40000
LFSR_ZERO_SALT_V4 = 0x13579B
CRC_POLY_V4 = 0xEDB88320
DICT_CAPACITY_V4 = 16

ERROR_PRECEDENCE = [
    "bad_magic",
    "truncated_header",
    "unsupported_version",
    "reserved_flag_set",
    "trailer_crc_mismatch",
    "truncated_record",
    "reserved_selector_bits",
    "varint_overlong",
    "noncanonical_varint",
    "bad_key_prefix",
    "invalid_utf8_key",
    "dict_index_out_of_range",
    "repeat_without_delta",
    "trailing_bytes",
]

DECODER_PATH = "/app/decode.py"
ENCODER_PATH = "/app/encode.py"
DECODED_EXAMPLES_PATH = Path("/app/out/decoded_examples.jsonl")
FORMAT_REPORT_PATH = Path("/app/out/format_report.json")
ROUNDTRIP_REPORT_PATH = Path("/app/out/roundtrip_report.json")
ERROR_ANALYSIS_PATH = Path("/app/out/error_analysis.json")

SAMPLE_SEED = 5356725367178107825
CHALLENGE_SEED = 3897437463414331647
EVAL_SEED = 484264451927529133

_EVAL_DIR = Path(tempfile.gettempdir()) / "MDUMP_00000001cd73f3b9_eval"
CAPTURE_COUNT = 16000

# Assembled rather than written out: the verifier never reads this path, it only
# plants a decoy there to catch delivered programs that do.
_DATA_ROOT = "/" + "/".join(("app", "data"))

# Complete captures from MDUMP-worked-examples.md sections B to E; the appendix
# forbids copying them into decoded_examples.jsonl.
WORKED_EXAMPLE_HEX = frozenset({
    "434f52455a0400000000000a00000001012afdff082bac02002c0148086672616d652e7063053481cfdd",
    "434f52455a05000100000878fdff7f0108c3e903590ba5af02200d41624331bedfdba13485d17834e182ab",
    "434f52455a0400cdab0006ffffffff01410008636166c3a92ec3a9fffe480701a8fdff7f110912345678"
    "400406a92ec3a82e330201d20875",
    "434f52455a070000000000000000000101006400010165000102660001036700000a02000b03000c00fcf0112b",
})


# --------------------------------------------------------------------------- #
# Deterministic PRNG (xorshift64*), fully specified so corpora are stable.    #
# --------------------------------------------------------------------------- #

class Rng:
    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        if seed == 0:
            seed = 0x9E3779B97F4A7C15
        self.state = seed & 0xFFFFFFFFFFFFFFFF

    def _next(self) -> int:
        x = self.state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.state = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def rand_int(self, lo: int, hi: int) -> int:
        return lo + (self._next() % (hi - lo + 1))

    def rand_signed(self, bits: int) -> int:
        v = self._next() & ((1 << bits) - 1)
        return v - (1 << bits) if v >= (1 << (bits - 1)) else v

    def rand_choice(self, seq):
        return seq[self._next() % len(seq)]

    def rand_bool(self, prob: float) -> bool:
        return (self._next() & 0xFFFFFFFF) < int(prob * 0x100000000)


# --------------------------------------------------------------------------- #
# Codec primitives.                                                           #
# --------------------------------------------------------------------------- #

def _crc_table(poly: int) -> list[int]:
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ poly if c & 1 else c >> 1
        table.append(c)
    return table


_CRC_TABLES = {
    CRC32C_POLY: _crc_table(CRC32C_POLY),
    CRC_POLY_V3: _crc_table(CRC_POLY_V3),
    CRC_POLY_V4: _crc_table(CRC_POLY_V4),
}


def crc_reflected(data: bytes, poly: int, init: int = 0xFFFFFFFF,
                  final: int = 0xFFFFFFFF) -> int:
    crc = init
    table = _CRC_TABLES[poly]
    for b in data:
        crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ final


def crc32c(data: bytes) -> int:
    return crc_reflected(data, CRC32C_POLY)


def _lfsr_byte_table(taps: int) -> list[int]:
    # Eight right-shift Galois clocks only ever shift out the eight low bits
    # of the starting state, so their combined feedback is a function of that
    # low byte alone.
    table = []
    for low in range(256):
        s = low
        for _ in range(8):
            s = (s >> 1) ^ taps if s & 1 else s >> 1
        table.append(s)
    return table


_V2_TABLE = _lfsr_byte_table(LFSR_TAPS_V2)
_LFSR_TABLES = {
    VERSION: _lfsr_byte_table(LFSR_TAPS),
    FIELD_VERSION: _V2_TABLE,
    FIELD5_VERSION: _V2_TABLE,
    FIELD6_VERSION: _lfsr_byte_table(LFSR_TAPS_V4),
}
_LFSR_ZERO = {
    VERSION: LFSR_ZERO_SALT,
    FIELD_VERSION: LFSR_ZERO_SALT_V2,
    FIELD5_VERSION: LFSR_ZERO_SALT_V2,
    FIELD6_VERSION: LFSR_ZERO_SALT_V4,
}


def keystream(salt: int, length: int, version: int = VERSION, base_value: int = 0) -> bytes:
    if version == FIELD5_VERSION:
        s = salt ^ (base_value & 0xFFFFFF)
    elif version == FIELD6_VERSION:
        s = (salt + ((base_value & 0xFFFFFFFF) >> 8)) & 0xFFFFFF
    else:
        s = salt
    s = s if s else _LFSR_ZERO[version]
    out = bytearray(length)
    table = _LFSR_TABLES[version]
    for j in range(length):
        s = (s >> 8) ^ table[s & 0xFF]
        out[j] = s & 0xFF
    return bytes(out)


def trailer_crc(header: bytes, plain_body: bytes, version: int) -> int:
    """header is the full 16-byte header, magic included."""
    if version == FIELD5_VERSION:
        return crc_reflected(header[CRC_START_V2:HEADER_SIZE] + plain_body, CRC_POLY_V3, CRC_INIT_V3)
    if version == FIELD6_VERSION:
        return crc_reflected(header + plain_body, CRC_POLY_V4, 0xFFFFFFFF, 0)
    start = CRC_START_V2 if version == FIELD_VERSION else 5
    return crc32c(header[start:HEADER_SIZE] + plain_body)


def dict_capacity(version: int) -> int:
    return {FIELD_VERSION: DICT_CAPACITY_V2, FIELD5_VERSION: DICT_CAPACITY_V3,
            FIELD6_VERSION: DICT_CAPACITY_V4}.get(version, DICT_CAPACITY)


def dict_select(dictionary: list[int], index: int, version: int) -> int:
    if version == FIELD5_VERSION:
        return dictionary[index]
    if version == FIELD6_VERSION:
        entry = dictionary.pop(index)
        dictionary.append(entry)
        return entry
    entry = dictionary.pop(len(dictionary) - 1 - index)
    dictionary.append(entry)
    return entry


def appends_value(version: int) -> bool:
    return version in (FIELD_VERSION, FIELD5_VERSION)


def repeat_factor(count: int, version: int) -> int:
    if version == FIELD6_VERSION:
        return count + 2
    return count + 1 if version in (FIELD_VERSION, FIELD5_VERSION) else count


def mode_high_bit(version: int) -> int:
    return 2 if version == FIELD5_VERSION else 3


def selector_reserved_mask(version: int) -> int:
    return (1 << 1) | (1 << 5) | (1 << 7) | (1 << (3 if version == FIELD5_VERSION else 2))


def selector_reserved_bits(version: int) -> list[int]:
    return [1 << b for b in range(8) if selector_reserved_mask(version) >> b & 1]


def selector_mode(sel: int, version: int) -> str:
    return MODE_BY_ID[(sel & 1) | (((sel >> mode_high_bit(version)) & 1) << 1)]


def selector_for(mode: str, version: int) -> int:
    ident = MODE_IDS[mode]
    return (ident & 1) | (((ident >> 1) & 1) << mode_high_bit(version))


def zigzag(value: int) -> int:
    return value * 2 if value >= 0 else -value * 2 - 1


def unzigzag(stored: int) -> int:
    return stored >> 1 if not stored & 1 else -((stored + 1) >> 1)


def delta_bytes(value: int, pad: int, version: int) -> bytes:
    if version == FIELD5_VERSION:
        return uvarint(zigzag(value), pad)
    if version == FIELD6_VERSION:
        stored = value * 2 if value >= 0 else -value * 2 + 1
        return uvarint(stored, pad)
    return sleb_padded(value, pad)


def delta_min_len(value: int, version: int) -> int:
    if version == FIELD5_VERSION:
        return len(uvarint(zigzag(value)))
    if version == FIELD6_VERSION:
        return len(uvarint(value * 2 if value >= 0 else -value * 2 + 1))
    return len(sleb(value))


def _xor(data: bytes, stream: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, stream))


def wrap32(x: int) -> int:
    return ((x + 0x80000000) & 0xFFFFFFFF) - 0x80000000


def uvarint(value: int, pad: int = 0) -> bytes:
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        if value:
            out.append(low | 0x80)
        else:
            out.append(low)
            break
    if pad:
        out[-1] |= 0x80
        out += b"\x80" * (pad - 1) + b"\x00"
    return bytes(out)


def sleb(value: int) -> bytes:
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        if (value == 0 and not low & 0x40) or (value == -1 and low & 0x40):
            out.append(low)
            return bytes(out)
        out.append(low | 0x80)


def sleb_padded(value: int, pad: int) -> bytes:
    out = bytearray(sleb(value))
    if pad:
        fill = 0x7F if value < 0 else 0x00
        out[-1] |= 0x80
        out += bytes([fill | 0x80]) * (pad - 1) + bytes([fill])
    return bytes(out)


# --------------------------------------------------------------------------- #
# Encoder (with a damage-injection hook used only to build rejected files).   #
# --------------------------------------------------------------------------- #

def encode_doc(doc: dict, inject: dict | None = None) -> bytes:
    inject = inject or {}
    per_record = inject.get("rec", {})
    flags = doc["flags"]
    flags_byte = 0
    for name, bit in FLAG_BITS.items():
        if flags[name]:
            flags_byte |= 1 << bit
    front = flags["front_coded_keys"]
    big = flags["big_endian_raw"]
    records = doc["records"]
    count = doc["record_count"] + inject.get("count_delta", 0)
    header = (
        count.to_bytes(2, "little")
        + doc["salt"].to_bytes(3, "little")
        + bytes([flags_byte])
        + doc["base_value"].to_bytes(4, "little", signed=True)
        + bytes([doc["version"]])
    )
    version = doc["version"]
    body = bytearray()
    prev_key = b""
    for index, rec in enumerate(records):
        inj = per_record.get(index, {})
        mode = rec["mode"]
        sel = selector_for(mode, version)
        if mode == "raw" and rec["wide_value"]:
            sel |= SEL_WIDE
        if rec["long_key"]:
            sel |= SEL_LONG
        sel |= inj.get("sel_or", 0)
        body.append(sel)
        if rec["long_key"]:
            key_bytes = inj.get("key_raw")
            if key_bytes is None:
                key_bytes = rec["key"].encode("utf-8")
            pad = inj.get("len_pad", 0)
            suffix_pad = inj.get("suffix_pad", 0)
            if inj.get("len_overlong"):
                body += b"\x80" * MAX_VARINT
            elif front:
                if "prefix_excess" in inj:
                    body += uvarint(len(prev_key) + inj["prefix_excess"]) + uvarint(0, suffix_pad)
                else:
                    prefix = 0 if "key_raw" in inj else rec["key_prefix"]
                    body += (uvarint(prefix, pad) + uvarint(len(key_bytes) - prefix, suffix_pad)
                             + key_bytes[prefix:])
            else:
                body += uvarint(len(key_bytes), pad) + key_bytes
            prev_key = key_bytes
        else:
            body.append(rec["key"])
        if mode == "raw":
            width = 4 if rec["wide_value"] else 2
            body += rec["raw_value"].to_bytes(width, "big" if big else "little", signed=True)
        elif mode == "delta":
            if inj.get("delta_overlong"):
                body += b"\xff" * MAX_VARINT
            else:
                body += delta_bytes(rec["delta_raw"], rec["delta_pad"], version)
        elif mode == "dict":
            body.append(rec["dict_index"])
        else:
            body.append(rec["repeat_count"])
    cut = inject.get("cut", 0)
    if cut:
        del body[len(body) - cut:]
    body += inject.get("append", b"")
    crc = trailer_crc(MAGIC + header, bytes(body), version)
    stream = keystream(doc["salt"], len(body), version, doc["base_value"])
    wire = _xor(bytes(body), stream) if flags["whitened"] else bytes(body)
    return MAGIC + header + wire + crc.to_bytes(4, "little")


# --------------------------------------------------------------------------- #
# Reference decoder.                                                          #
# --------------------------------------------------------------------------- #

class _BodyError(Exception):
    def __init__(self, code: str, **extra: Any) -> None:
        super().__init__(code)
        self.code = code
        self.extra = extra


def _read_uvarint(body: bytes, pos: int, end: int) -> tuple[int, int]:
    value = 0
    for k in range(MAX_VARINT):
        if pos >= end:
            raise _BodyError("truncated_record")
        b = body[pos]
        pos += 1
        value |= (b & 0x7F) << (7 * k)
        if not b & 0x80:
            if k and b == 0:
                raise _BodyError("noncanonical_varint")
            return value, pos
    raise _BodyError("varint_overlong")


def _read_delta(body: bytes, pos: int, end: int, version: int) -> tuple[int, int, int]:
    value = 0
    for k in range(MAX_VARINT):
        if pos >= end:
            raise _BodyError("truncated_record")
        b = body[pos]
        pos += 1
        value |= (b & 0x7F) << (7 * k)
        if not b & 0x80:
            if version == FIELD5_VERSION:
                return unzigzag(value), k + 1, pos
            if version == FIELD6_VERSION:
                return (-(value >> 1) if value & 1 else value >> 1), k + 1, pos
            if b & 0x40:
                value -= 1 << (7 * (k + 1))
            return value, k + 1, pos
    raise _BodyError("varint_overlong")


def reference_decode(blob: bytes) -> dict:
    n = len(blob)
    if n < 5 or blob[:5] != MAGIC:
        return {"error": "bad_magic"}
    if n < HEADER_SIZE + TRAILER_SIZE:
        return {"error": "truncated_header", "length": n}
    version = blob[15]
    if version not in SUPPORTED_VERSIONS:
        return {"error": "unsupported_version", "version": version}
    flags_byte = blob[10]
    if flags_byte & FLAG_RESERVED_MASK:
        return {"error": "reserved_flag_set", "flags": flags_byte}
    salt = int.from_bytes(blob[7:10], "little")
    flags = {name: bool(flags_byte >> bit & 1) for name, bit in FLAG_BITS.items()}
    record_count = int.from_bytes(blob[5:7], "little")
    base_value = int.from_bytes(blob[11:15], "little", signed=True)
    body = blob[HEADER_SIZE:n - TRAILER_SIZE]
    if flags["whitened"]:
        body = _xor(body, keystream(salt, len(body), version, base_value))
    stored = int.from_bytes(blob[n - TRAILER_SIZE:], "little")
    computed = trailer_crc(blob[:HEADER_SIZE], body, version)
    if stored != computed:
        return {"error": "trailer_crc_mismatch", "stored": stored, "computed": computed}
    front = flags["front_coded_keys"]
    order = "big" if flags["big_endian_raw"] else "little"
    end = len(body)
    pos = 0
    running = base_value
    last_delta: int | None = None
    dictionary: list[int] = []
    capacity = dict_capacity(version)
    reserved_mask = selector_reserved_mask(version)
    prev_key = b""
    records = []
    for index in range(record_count):
        # `field` is the body offset of the field being read or checked; a
        # record-level error object reports it as `offset`.
        start = field = pos
        try:
            if pos >= end:
                raise _BodyError("truncated_record")
            sel = body[pos]
            pos += 1
            mode = selector_mode(sel, version)
            if sel & reserved_mask or (sel & SEL_WIDE and mode != "raw"):
                raise _BodyError("reserved_selector_bits", selector=sel)
            long_key = bool(sel & SEL_LONG)
            rec: dict[str, Any] = {"offset": start}
            if long_key:
                if front:
                    field = pos
                    prefix, pos = _read_uvarint(body, pos, end)
                    if prefix > len(prev_key):
                        raise _BodyError("bad_key_prefix", key_prefix=prefix)
                    field = pos
                    size, pos = _read_uvarint(body, pos, end)
                    field = pos
                    if pos + size > end:
                        raise _BodyError("truncated_record")
                    key_bytes = prev_key[:prefix] + body[pos:pos + size]
                    rec["key_prefix"] = prefix
                else:
                    field = pos
                    size, pos = _read_uvarint(body, pos, end)
                    field = pos
                    if pos + size > end:
                        raise _BodyError("truncated_record")
                    key_bytes = body[pos:pos + size]
                pos += size
                try:
                    key: Any = key_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    raise _BodyError("invalid_utf8_key") from None
                prev_key = key_bytes
            else:
                field = pos
                if pos >= end:
                    raise _BodyError("truncated_record")
                key = body[pos]
                pos += 1
            rec.update(key=key, long_key=long_key, mode=mode)
            field = pos
            if mode == "raw":
                wide = bool(sel & SEL_WIDE)
                width = 4 if wide else 2
                if pos + width > end:
                    raise _BodyError("truncated_record")
                payload = int.from_bytes(body[pos:pos + width], order, signed=True)
                pos += width
                running = payload
                rec.update(wide_value=wide, raw_value=payload)
            elif mode == "delta":
                payload, length, pos = _read_delta(body, pos, end, version)
                running = wrap32(running + payload)
                last_delta = payload
                rec.update(delta_raw=payload, delta_pad=length - delta_min_len(payload, version))
            elif mode == "dict":
                if pos >= end:
                    raise _BodyError("truncated_record")
                payload = body[pos]
                pos += 1
                if payload >= len(dictionary):
                    raise _BodyError("dict_index_out_of_range", dict_index=payload, dict_size=len(dictionary))
                running = wrap32(dict_select(dictionary, payload, version))
                rec["dict_index"] = payload
            else:
                if pos >= end:
                    raise _BodyError("truncated_record")
                payload = body[pos]
                pos += 1
                if last_delta is None:
                    raise _BodyError("repeat_without_delta")
                running = wrap32(running + last_delta * repeat_factor(payload, version))
                rec["repeat_count"] = payload
            rec["value"] = running
            dictionary.append(running if appends_value(version) else payload)
            if len(dictionary) > capacity:
                del dictionary[0]
            records.append(rec)
        except _BodyError as exc:
            return {"error": exc.code, "record_index": index, **exc.extra, "offset": field}
    if pos != end:
        return {"error": "trailing_bytes", "count": end - pos, "offset": pos}
    return {
        "version": version,
        "flags": flags,
        "salt": salt,
        "record_count": record_count,
        "base_value": base_value,
        "records": records,
    }


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode("ascii")).hexdigest()


def status_of(obj: dict) -> str:
    return obj["error"] if "error" in obj else "ok"


# --------------------------------------------------------------------------- #
# Corpus generation.                                                          #
# --------------------------------------------------------------------------- #

_ASCII_KEYS = [
    "frame.pc", "frame.sp", "frame.fp", "frame.lr", "reg.rax", "reg.rbx", "reg.rcx",
    "reg.rdx", "reg.rip", "reg.rsp", "thread.main", "thread.worker", "heap.arena.0",
    "heap.arena.1", "signal.SIGSEGV", "signal.SIGBUS", "module.libc.so.6",
    "module.libm.so.6", "core.pid", "core.uid",
]
_UNICODE_FAMILIES = [
    ["caf\u00e9.\u00e9", "caf\u00e9.\u00e8", "caf\u00e9.\u00ea", "caf\u00e9.\u00eb"],
    ["\u043f\u043e\u0442\u043e\u043a.\u03b1", "\u043f\u043e\u0442\u043e\u043a.\u03b2",
     "\u043f\u043e\u0442\u043e\u043a.\u03b3", "\u043f\u043e\u0442\u043e\u043a.\u03b4"],
    ["\u30b9\u30ec\u30c3\u30c9.\u30b9", "\u30b9\u30ec\u30c3\u30c9.\u30ba",
     "\u30b9\u30ec\u30c3\u30c9.\u30bb", "\u30b9\u30ec\u30c3\u30c9.\u30bc"],
    ["\u5bc4\u5b58\u5668.\u7532", "\u5bc4\u5b58\u5668.\u7533",
     "\u5bc4\u5b58\u5668.\u7535", "\u5bc4\u5b58\u5668.\u7537"],
    ["\u043a\u0430\u0434\u0440.\U0001f600", "\u043a\u0430\u0434\u0440.\U0001f601",
     "\u043a\u0430\u0434\u0440.\U0001f602", "\u043a\u0430\u0434\u0440.\U0001f603"],
    ["trace.\u03a9", "trace.\u03a8", "trace.\u03a7", "trace.\u03a6"],
]
_BAD_UTF8 = [b"\xc3\x28", b"frame.\xe3\x82", b"\xed\xa0\x80", b"\xc0\xaf", b"reg.\xff",
             b"\xf4\x90\x80\x80", b"core\x80", b"\xe7\x94"]

_BASE_PROFILE: dict[str, Any] = {
    "n": (4, 24), "front": 0.0, "be": 0.0, "white": 0.0, "r0": 0.1, "salt_plain": 0.0,
    "salt_zero": 0.15, "w_raw": 3, "w_delta": 3, "w_dict": 2, "w_repeat": 0, "long": 0.3,
    "uni": 0.0, "pad": 0.0, "wrap": 0.0, "huge": 0.0, "wide": 0.55, "bound": 0.1,
    "rep_big": 0.1, "sticky": 0.7, "v2": 0.25, "v3": 0.45, "v4": 0.0,
}

PROFILES: dict[str, dict[str, Any]] = {
    "plain": {},
    "boundary": {"bound": 0.6, "w_raw": 6, "n": (6, 30)},
    "big_endian": {"be": 1.0, "bound": 0.4, "w_raw": 6, "n": (6, 30)},
    "whitened": {"white": 1.0, "salt_zero": 0.2, "w_repeat": 1, "n": (6, 40)},
    "salted": {"salt_plain": 1.0, "w_repeat": 1, "n": (4, 24)},
    "front": {"front": 1.0, "long": 0.75, "uni": 0.7, "n": (8, 40)},
    "wrap": {"wrap": 0.35, "huge": 0.15, "w_repeat": 2, "rep_big": 0.5, "n": (8, 40)},
    "mtf": {"w_dict": 7, "w_raw": 2, "w_delta": 2, "n": (30, 90)},
    "repeat": {"w_repeat": 4, "rep_big": 0.3, "n": (8, 40)},
    "padded": {"pad": 0.6, "w_delta": 6, "n": (8, 30)},
    "everything": {"front": 0.6, "be": 0.5, "white": 0.6, "r0": 0.5, "salt_plain": 0.5,
                   "w_repeat": 2, "long": 0.45, "uni": 0.6, "pad": 0.25, "wrap": 0.08,
                   "huge": 0.05, "bound": 0.2, "rep_big": 0.25, "n": (120, 250)},
    "log_random": {"front": 0.35, "be": 0.35, "white": 0.35, "r0": 0.3, "salt_plain": 0.3,
                   "w_repeat": 2, "long": 0.35, "uni": 0.5, "pad": 0.2, "wrap": 0.05,
                   "huge": 0.05, "bound": 0.15, "rep_big": 0.2, "n": (1, 14)},
}


def _profile(name: str, **override: Any) -> dict[str, Any]:
    prof = dict(_BASE_PROFILE)
    prof.update(PROFILES[name])
    prof.update(override)
    return prof


def _lcp(a: bytes, b: bytes) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _pick_raw(rng: Rng, wide: bool, prof: dict) -> int:
    bits = 32 if wide else 16
    if rng.rand_bool(prof["bound"]):
        top = (1 << (bits - 1)) - 1
        low = -(1 << (bits - 1))
        return rng.rand_choice([top - rng.rand_int(0, 3), low + rng.rand_int(0, 3),
                                -1 - rng.rand_int(0, 2), top - rng.rand_int(0, 300)])
    if wide and rng.rand_bool(0.4):
        return rng.rand_signed(16)
    return rng.rand_signed(bits)


def _pick_delta(rng: Rng, running: int, prof: dict) -> int:
    if rng.rand_bool(prof["wrap"]):
        if running >= 0:
            return (0x80000000 - running) + rng.rand_int(0, 4096)
        return -(running + 0x80000000) - rng.rand_int(1, 4096)
    if rng.rand_bool(prof["huge"]):
        sign = rng.rand_choice([1, -1])
        return sign * rng.rand_int(1, 3) * (1 << 32) + rng.rand_int(-5000, 5000)
    roll = rng.rand_int(0, 9)
    if roll < 4:
        return rng.rand_int(-63, 63)
    if roll < 7:
        return rng.rand_int(-8191, 8191)
    if roll < 9:
        return rng.rand_int(-(1 << 20), 1 << 20)
    return rng.rand_signed(32)


def _pick_long_key(rng: Rng, prof: dict, family: list[str] | None) -> tuple[str, list[str] | None]:
    if rng.rand_bool(prof["uni"]):
        if family is None or not rng.rand_bool(prof["sticky"]):
            family = rng.rand_choice(_UNICODE_FAMILIES)
        base = rng.rand_choice(family)
    else:
        family = None
        base = rng.rand_choice(_ASCII_KEYS)
    if rng.rand_bool(0.5):
        base = f"{base}.{rng.rand_int(0, 9)}"
    return base, family


def generate_doc(rng: Rng, prof: dict) -> dict:
    pick = rng.rand_int(0, 999)
    if pick < int(prof["v4"] * 1000):
        version = FIELD6_VERSION
    elif pick < int((prof["v4"] + prof["v3"]) * 1000):
        version = FIELD5_VERSION
    elif pick < int((prof["v4"] + prof["v3"] + prof["v2"]) * 1000):
        version = FIELD_VERSION
    else:
        version = VERSION
    capacity = dict_capacity(version)
    count = rng.rand_int(*prof["n"])
    whitened = rng.rand_bool(prof["white"])
    flags = {
        "reserved_bit_0": rng.rand_bool(prof["r0"]),
        "front_coded_keys": rng.rand_bool(prof["front"]),
        "big_endian_raw": rng.rand_bool(prof["be"]),
        "whitened": whitened,
    }
    if whitened:
        salt = 0 if rng.rand_bool(prof["salt_zero"]) else rng.rand_int(1, 0xFFFFFF)
    else:
        salt = rng.rand_int(1, 0xFFFFFF) if rng.rand_bool(prof["salt_plain"]) else 0
    if prof["wrap"] and rng.rand_bool(0.5):
        base = rng.rand_choice([0x7FFFFFFF - rng.rand_int(0, 5000), -0x80000000 + rng.rand_int(0, 5000)])
    else:
        base = rng.rand_signed(32) // 4
    running = base
    last_delta: int | None = None
    dictionary: list[int] = []
    prev_key = b""
    family: list[str] | None = None
    records = []
    body_pos = 0
    for _ in range(count):
        pool = ["raw"] * prof["w_raw"] + ["delta"] * prof["w_delta"]
        if dictionary:
            pool += ["dict"] * prof["w_dict"]
        if last_delta is not None:
            pool += ["repeat"] * prof["w_repeat"]
        mode = rng.rand_choice(pool)
        long_key = rng.rand_bool(prof["long"])
        rec: dict[str, Any] = {"long_key": long_key, "mode": mode, "offset": body_pos}
        body_pos += 1
        if long_key:
            key, family = _pick_long_key(rng, prof, family)
            key_bytes = key.encode("utf-8")
            if flags["front_coded_keys"]:
                lcp = _lcp(prev_key, key_bytes)
                rec["key_prefix"] = lcp if rng.rand_bool(0.75) else rng.rand_int(0, lcp)
                stored = len(key_bytes) - rec["key_prefix"]
                body_pos += len(uvarint(rec["key_prefix"])) + len(uvarint(stored)) + stored
            else:
                body_pos += len(uvarint(len(key_bytes))) + len(key_bytes)
            prev_key = key_bytes
            rec["key"] = key
        else:
            rec["key"] = rng.rand_int(0, 255)
            body_pos += 1
        if mode == "raw":
            wide = rng.rand_bool(prof["wide"])
            payload = _pick_raw(rng, wide, prof)
            running = payload
            rec.update(wide_value=wide, raw_value=payload)
            body_pos += 4 if wide else 2
        elif mode == "delta":
            payload = _pick_delta(rng, running, prof)
            room = MAX_VARINT - delta_min_len(payload, version)
            pad = rng.rand_int(1, min(3, room)) if room > 0 and rng.rand_bool(prof["pad"]) else 0
            running = wrap32(running + payload)
            last_delta = payload
            rec.update(delta_raw=payload, delta_pad=pad)
            body_pos += len(delta_bytes(payload, pad, version))
        elif mode == "dict":
            if rng.rand_bool(0.5):
                payload = rng.rand_int(0, min(3, len(dictionary) - 1))
            else:
                payload = rng.rand_int(0, len(dictionary) - 1)
            running = wrap32(dict_select(dictionary, payload, version))
            rec["dict_index"] = payload
        else:
            assert last_delta is not None
            payload = rng.rand_int(16, 255) if rng.rand_bool(prof["rep_big"]) else rng.rand_int(0, 4)
            running = wrap32(running + last_delta * repeat_factor(payload, version))
            rec["repeat_count"] = payload
        if mode in ("dict", "repeat"):
            body_pos += 1
        rec["value"] = running
        dictionary.append(running if appends_value(version) else payload)
        if len(dictionary) > capacity:
            del dictionary[0]
        records.append(rec)
    return {"version": version, "flags": flags, "salt": salt, "record_count": count,
            "base_value": base, "records": records}


HEADER_DAMAGE = ["bad_magic", "bad_magic_short", "truncated_header", "unsupported_version",
                 "reserved_flag_set"]
CRC_DAMAGE = ["crc_trailer", "crc_body"]
BODY_DAMAGE = ["truncated_count", "truncated_cut", "reserved_selector", "wide_on_nonraw",
               "noncanonical_key", "overlong_key", "overlong_delta", "invalid_utf8",
               "bad_key_prefix", "dict_out_of_range", "repeat_without_delta", "trailing_bytes"]
WINDOW_DAMAGE = ["dict_window"]
COMBO_DAMAGE = ["magic_version_crc", "version_flags", "flags_crc", "crc_and_body",
                "short_header_bad_version"]
ALL_DAMAGE = HEADER_DAMAGE + CRC_DAMAGE + BODY_DAMAGE + WINDOW_DAMAGE + COMBO_DAMAGE
# Two faults at once inside the body, so the documented read order decides the
# error. Hidden tier only: ALL_DAMAGE, and with it the shipped log, is unchanged.
ORDER_DAMAGE = ["prefix_before_suffix", "noncanonical_suffix", "repeat_payload_cut", "dict_payload_cut",
                "selector_before_key", "key_before_payload", "first_failing_record"]

_INTENDED = {
    "bad_magic": "bad_magic", "bad_magic_short": "bad_magic", "truncated_header": "truncated_header",
    "unsupported_version": "unsupported_version", "reserved_flag_set": "reserved_flag_set",
    "crc_trailer": "trailer_crc_mismatch", "crc_body": "trailer_crc_mismatch",
    "truncated_count": "truncated_record", "truncated_cut": "truncated_record",
    "reserved_selector": "reserved_selector_bits", "wide_on_nonraw": "reserved_selector_bits",
    "noncanonical_key": "noncanonical_varint", "overlong_key": "varint_overlong",
    "overlong_delta": "varint_overlong", "invalid_utf8": "invalid_utf8_key",
    "bad_key_prefix": "bad_key_prefix", "dict_out_of_range": "dict_index_out_of_range",
    "dict_window": "dict_index_out_of_range", "repeat_without_delta": "repeat_without_delta",
    "trailing_bytes": "trailing_bytes", "magic_version_crc": "bad_magic",
    "version_flags": "unsupported_version", "flags_crc": "reserved_flag_set",
    "crc_and_body": "trailer_crc_mismatch", "short_header_bad_version": "truncated_header",
    "prefix_before_suffix": "bad_key_prefix", "noncanonical_suffix": "noncanonical_varint",
    "repeat_payload_cut": "truncated_record", "dict_payload_cut": "truncated_record",
    "selector_before_key": "reserved_selector_bits", "key_before_payload": "invalid_utf8_key",
    "first_failing_record": "repeat_without_delta",
}


def _damage_profile(kind: str, prof: dict) -> dict:
    prof = dict(prof)
    lo, hi = prof["n"]
    prof["n"] = (max(lo, 3), max(hi, 6))
    if kind in ("noncanonical_key", "overlong_key", "invalid_utf8", "bad_key_prefix",
                "prefix_before_suffix", "noncanonical_suffix"):
        prof["long"] = max(prof["long"], 0.5)
    if kind in ("bad_key_prefix", "prefix_before_suffix", "noncanonical_suffix"):
        prof["front"] = 1.0
    if kind == "dict_window":
        prof["n"] = (48, 110)
        prof["w_dict"] = max(prof["w_dict"], 2)
    if kind in ("repeat_without_delta", "repeat_payload_cut", "first_failing_record"):
        prof["w_delta"] = 0
        prof["w_repeat"] = 0
    if kind in ("crc_body", "crc_and_body"):
        prof["white"] = max(prof["white"], 0.5)
    return prof


def _plain_record(rng: Rng, mode: str) -> dict[str, Any]:
    rec: dict[str, Any] = {"key": rng.rand_int(0, 255), "long_key": False, "mode": mode, "value": 0}
    if mode == "delta":
        rec.update(delta_raw=rng.rand_int(-50, 50), delta_pad=0)
    elif mode == "repeat":
        rec["repeat_count"] = rng.rand_int(0, 9)
    return rec


def _body_inject(rng: Rng, doc: dict, kind: str) -> dict:
    records = doc["records"]
    n = len(records)
    if kind == "truncated_count":
        return {"count_delta": 1}
    if kind == "truncated_cut":
        return {"cut": rng.rand_int(1, 3)}
    if kind == "trailing_bytes":
        return {"append": bytes(rng.rand_int(0, 255) for _ in range(rng.rand_int(1, 4)))}
    reserved = selector_reserved_bits(doc["version"])
    if kind == "dict_payload_cut":
        rec = _plain_record(rng, "dict")
        rec["dict_index"] = rng.rand_int(0, 3)
        doc["records"] = [rec]
        doc["record_count"] = 1
        return {"cut": 1}
    if kind == "repeat_payload_cut":
        records[n - 1] = _plain_record(rng, "repeat")
        return {"cut": 1}
    if kind == "first_failing_record":
        first = rng.rand_int(0, n - 2)
        later = rng.rand_int(first + 1, n - 1)
        records[first] = _plain_record(rng, "repeat")
        return {"rec": {later: {"sel_or": rng.rand_choice(reserved)}}}
    if kind in ("selector_before_key", "key_before_payload"):
        if kind == "selector_before_key":
            rec = _plain_record(rng, "dict")
            rec["dict_index"] = 0
            inj = {"sel_or": rng.rand_choice(reserved)}
        else:
            rec = _plain_record(rng, "raw")
            rec.update(wide_value=True, raw_value=rng.rand_signed(32))
            inj = {"key_raw": rng.rand_choice(_BAD_UTF8)}
        rec.update(long_key=True, key=rng.rand_choice(_ASCII_KEYS))
        if doc["flags"]["front_coded_keys"]:
            rec["key_prefix"] = 0
        records[n - 1] = rec
        return {"rec": {n - 1: inj}, "cut": 2}
    index = rng.rand_int(0, n - 1)
    if kind == "reserved_selector":
        return {"rec": {index: {"sel_or": rng.rand_choice(reserved)}}}
    if kind == "wide_on_nonraw":
        if records[index]["mode"] == "raw":
            records[index] = _plain_record(rng, "delta")
        return {"rec": {index: {"sel_or": SEL_WIDE}}}
    if kind == "overlong_delta":
        records[index] = _plain_record(rng, "delta")
        return {"rec": {index: {"delta_overlong": True}}}
    capacity = dict_capacity(doc["version"])
    if kind == "dict_out_of_range":
        size = min(index, capacity)
        rec = _plain_record(rng, "dict")
        rec["dict_index"] = min(255, size + rng.rand_int(0, 3))
        records[index] = rec
        return {}
    if kind == "dict_window":
        index = rng.rand_int(capacity + 1, n - 1)
        rec = _plain_record(rng, "dict")
        rec["dict_index"] = rng.rand_int(capacity, min(255, index - 1))
        records[index] = rec
        return {}
    if kind == "repeat_without_delta":
        records[index] = _plain_record(rng, "repeat")
        return {}
    # Remaining kinds act on a long key at `index`.
    if not records[index]["long_key"]:
        rec = dict(records[index])
        rec["long_key"] = True
        rec["key"] = rng.rand_choice(_ASCII_KEYS)
        if doc["flags"]["front_coded_keys"]:
            rec["key_prefix"] = 0
        records[index] = rec
    if kind == "noncanonical_key":
        return {"rec": {index: {"len_pad": rng.rand_int(1, 2)}}}
    if kind == "overlong_key":
        return {"rec": {index: {"len_overlong": True}}}
    if kind == "invalid_utf8":
        return {"rec": {index: {"key_raw": rng.rand_choice(_BAD_UTF8)}}}
    if kind == "bad_key_prefix":
        return {"rec": {index: {"prefix_excess": rng.rand_int(1, 6)}}}
    if kind == "prefix_before_suffix":
        return {"rec": {index: {"prefix_excess": rng.rand_int(1, 6), "suffix_pad": rng.rand_int(1, 2)}}}
    if kind == "noncanonical_suffix":
        return {"rec": {index: {"suffix_pad": rng.rand_int(1, 2)}}}
    raise ValueError(kind)


def _flip(rng: Rng, b: bytearray, lo: int, hi: int) -> None:
    b[rng.rand_int(lo, hi)] ^= 1 << rng.rand_int(0, 7)


def build_damaged(rng: Rng, prof: dict, kind: str) -> tuple[bytes, dict]:
    doc = generate_doc(rng, _damage_profile(kind, prof))
    if kind in BODY_DAMAGE or kind in WINDOW_DAMAGE or kind in ORDER_DAMAGE:
        blob = encode_doc(doc, _body_inject(rng, doc, kind))
    elif kind == "crc_and_body":
        blob = bytearray(encode_doc(doc, _body_inject(rng, doc, rng.rand_choice(BODY_DAMAGE[2:]))))
        _flip(rng, blob, len(blob) - 4, len(blob) - 1)
        blob = bytes(blob)
    else:
        b = bytearray(encode_doc(doc))
        if kind in ("bad_magic", "magic_version_crc"):
            _flip(rng, b, 0, 4)
        if kind == "bad_magic_short":
            b = b[:rng.rand_int(0, 4)]
        if kind in ("unsupported_version", "magic_version_crc", "version_flags"):
            b[15] = rng.rand_choice([0, 4, 5, 9, 0x81, 0xFF])
        if kind in ("reserved_flag_set", "version_flags", "flags_crc"):
            b[10] |= rng.rand_choice([0x10, 0x20, 0x40, 0x80, 0x30, 0xF0])
        if kind in ("crc_trailer", "magic_version_crc", "flags_crc"):
            _flip(rng, b, len(b) - 4, len(b) - 1)
        if kind == "crc_body":
            if len(b) > HEADER_SIZE + TRAILER_SIZE:
                _flip(rng, b, HEADER_SIZE, len(b) - 5)
            else:
                _flip(rng, b, len(b) - 4, len(b) - 1)
        if kind == "truncated_header":
            b = b[:rng.rand_int(5, 19)]
        if kind == "short_header_bad_version":
            b = b[:rng.rand_int(16, 19)]
            b[15] = rng.rand_choice([0, 4, 9])
        blob = bytes(b)
    result = reference_decode(blob)
    # The historical capture-log seed occasionally chose byte 4 as a damaged
    # "unsupported" version. Version 4 is supported by the 6.x line now, so
    # those exact shipped bytes legitimately proceed to the next applicable
    # error while all newly chosen unsupported bytes retain the old assertion.
    historical_v4_transition = kind in ("unsupported_version", "version_flags") \
        and len(blob) > 15 and blob[15] == FIELD6_VERSION
    if result.get("error") != _INTENDED[kind] and not historical_v4_transition:
        raise AssertionError(f"damage {kind} produced {result!r}")
    return blob, doc


# --------------------------------------------------------------------------- #
# Trap analysis: which documented rules does a capture actually exercise?     #
# --------------------------------------------------------------------------- #


def trap_tags(doc: dict | None, result: dict, kind: str | None) -> dict[str, int]:
    tags: dict[str, int] = {}

    def hit(name: str, amount: int = 1) -> None:
        tags[name] = tags.get(name, 0) + amount

    if doc is not None and doc["version"] == FIELD_VERSION:
        hit("rev4")
    if doc is not None and doc["version"] == FIELD5_VERSION:
        hit("rev5")
    if kind is not None:
        hit("error:" + result["error"])
        if kind in COMBO_DAMAGE:
            hit("precedence")
        if kind == "dict_window":
            hit("window")
        if result["error"] == "trailer_crc_mismatch" and doc is not None and doc["flags"]["whitened"]:
            hit("crc_whitened")
        return tags
    assert doc is not None
    flags = doc["flags"]
    if flags["whitened"]:
        hit("whitened")
        if doc["salt"] == 0:
            hit("salt_zero")
    elif doc["salt"]:
        hit("salted_plain")
    if flags["reserved_bit_0"]:
        hit("reserved_bit_0")
    version = doc["version"]
    capacity = dict_capacity(version)
    running = doc["base_value"]
    last_delta = 0
    plain_dict: list[int] = []
    mtf_dict: list[int] = []
    for rec in doc["records"]:
        mode = rec["mode"]
        if rec["long_key"]:
            key_bytes = rec["key"].encode("utf-8")
            if flags["front_coded_keys"]:
                hit("front_coded")
                try:
                    key_bytes[rec["key_prefix"]:].decode("utf-8")
                except UnicodeDecodeError:
                    hit("utf8_split")
            if any(ch > 127 for ch in key_bytes):
                hit("unicode_key")
        if mode == "raw":
            payload = rec["raw_value"]
            if flags["big_endian_raw"]:
                width = 4 if rec["wide_value"] else 2
                swapped = int.from_bytes(payload.to_bytes(width, "big", signed=True), "little", signed=True)
                if swapped != payload:
                    hit("big_endian")
            if not rec["wide_value"] and payload < 0:
                hit("i16_negative")
            if abs(payload) >= (0x7FFF0000 if rec["wide_value"] else 0x7F00):
                hit("raw_extreme")
            raw_next = payload
        elif mode == "delta":
            payload = rec["delta_raw"]
            raw_next = running + payload
            last_delta = payload
            if rec["delta_pad"]:
                hit("padded_delta")
            if not -0x80000000 <= payload <= 0x7FFFFFFF:
                hit("huge_delta")
        elif mode == "dict":
            payload = rec["dict_index"]
            if plain_dict[len(plain_dict) - 1 - payload] != mtf_dict[len(mtf_dict) - 1 - payload]:
                hit("mtf")
            if version == FIELD5_VERSION:
                hit("forward_dict")
            raw_next = dict_select(mtf_dict, payload, version)
        else:
            payload = rec["repeat_count"]
            raw_next = running + last_delta * repeat_factor(payload, version)
            hit("repeat")
            if payload == 0:
                hit("repeat_zero")
        if wrap32(raw_next) != raw_next:
            hit("wrap")
        running = wrap32(raw_next)
        for d in (plain_dict, mtf_dict):
            d.append(running if appends_value(version) else payload)
            if len(d) > capacity:
                del d[0]
    return tags


# --------------------------------------------------------------------------- #
# Capture log (shipped) and evaluation tier (hidden).                         #
# --------------------------------------------------------------------------- #

_LOG_PROFILES = [("plain", 15), ("boundary", 5), ("big_endian", 8), ("whitened", 12),
                 ("salted", 6), ("front", 12), ("wrap", 8), ("mtf", 7), ("repeat", 10),
                 ("padded", 8), ("everything", 1), ("log_random", 8)]
_LOG_WHEEL = [name for name, weight in _LOG_PROFILES for _ in range(weight)]


def _log_entry(rng: Rng, capture_id: str) -> dict[str, Any]:
    name = rng.rand_choice(_LOG_WHEEL)
    prof = _profile(name)
    if name == "mtf":
        prof["n"] = (20, 60)
    elif name != "everything":
        lo, hi = prof["n"]
        prof["n"] = (max(1, lo // 2), max(2, hi // 2))
    if rng.rand_int(0, 999) < 130:
        kind: str | None = rng.rand_choice(ALL_DAMAGE)
        blob, doc = build_damaged(rng, prof, kind)
    else:
        kind = None
        doc = generate_doc(rng, prof)
        blob = encode_doc(doc)
    result = reference_decode(blob)
    if kind is None and canonical(result) != canonical(doc):
        raise AssertionError(f"{capture_id}: reference decode disagrees with generated document")
    return {"capture_id": capture_id, "hex": blob.hex(), "profile": name, "damage": kind,
            "status": status_of(result), "sha256": digest(result), "result": result,
            "tags": trap_tags(doc, result, kind), "field_build": field_build_reached(blob)}


def field_build_reached(blob: bytes) -> int:
    """The 4.x or 5.x field-build version whose rules decide this capture's output, or 0 otherwise.

    Version 4 (6.x) captures return 0 here and are grouped with revision 3 captures; their
    graded status and digest still follow the 6.x rules."""
    if (len(blob) >= HEADER_SIZE + TRAILER_SIZE and blob[:5] == MAGIC
            and blob[15] in (FIELD_VERSION, FIELD5_VERSION) and not blob[10] & FLAG_RESERVED_MASK):
        return blob[15]
    return 0


_CAPTURE_CACHE: list[dict[str, Any]] = []
_CAPTURE_LOCK = threading.Lock()


def capture_log() -> list[dict[str, Any]]:
    """The shipped capture log, regenerated: the data directory holds exactly these rows."""
    with _CAPTURE_LOCK:
        if not _CAPTURE_CACHE:
            rng = Rng(CHALLENGE_SEED)
            _CAPTURE_CACHE.extend(_log_entry(rng, f"cap-{i:05d}") for i in range(1, CAPTURE_COUNT + 1))
    return _CAPTURE_CACHE


def capture_facts() -> dict[str, Any]:
    rows = capture_log()
    modes = {"raw": 0, "delta": 0, "dict": 0, "repeat": 0}
    flags = {name: 0 for name in FLAG_BITS}
    errors: dict[str, int] = {}
    ok = 0
    for row in rows:
        result = row["result"]
        if "error" in result:
            errors[result["error"]] = errors.get(result["error"], 0) + 1
            continue
        ok += 1
        for rec in result["records"]:
            modes[rec["mode"]] += 1
        for name, value in result["flags"].items():
            flags[name] += int(value)
    return {"capture_count": len(rows), "capture_ok_count": ok, "capture_mode_counts": modes,
            "capture_flag_counts": flags, "capture_errors": dict(sorted(errors.items()))}


# (label, profile, damage, count, version, profile overrides). Every class is built for one
# version only, so a check never mixes revision 3 and field-build captures and a slip on one
# build's rules costs only that build's checks. Revision 3 classes carry the documented rules;
# the field-build classes each isolate one group of the field notes' changes (keystream with
# no dictionary or repeat records, dictionary with no repeat records, repeat with no
# dictionary records), so one wrong field-build fact fails one class, not all three.
_NO_STATE = {"w_dict": 0, "w_repeat": 0}
_RAW_ONLY = {"w_delta": 0, "w_dict": 0, "w_repeat": 0}
EVAL_PLAN: list[tuple[str, str, str | None, int, int, dict[str, Any]]] = [
    *[(name, name, None, count, VERSION, {}) for name, count in (
        ("plain", 6), ("boundary", 5), ("big_endian", 5), ("whitened", 6), ("salted", 4),
        ("front", 7), ("wrap", 6), ("mtf", 6), ("repeat", 6), ("padded", 5), ("everything", 4))],
    ("whitened", "whitened", None, 1, VERSION, {"salt_zero": 1.0}),
    *[(kind, "log_random", kind, 1, VERSION, {}) for kind in HEADER_DAMAGE],
    ("bad_magic_short", "plain", "bad_magic_short", 1, VERSION, {}),
    ("crc_trailer", "whitened", "crc_trailer", 1, VERSION, {}),
    ("crc_trailer", "plain", "crc_trailer", 1, VERSION, {}),
    ("crc_body", "whitened", "crc_body", 2, VERSION, {}),
    ("crc_body", "plain", "crc_body", 1, VERSION, {}),
    ("crc_body", "front", "crc_body", 1, VERSION, {}),
    *[(kind, "log_random", kind, 1, VERSION, {}) for kind in BODY_DAMAGE],
    ("invalid_utf8", "front", "invalid_utf8", 1, VERSION, {}),
    ("truncated_cut", "whitened", "truncated_cut", 1, VERSION, {}),
    ("reserved_selector", "everything", "reserved_selector", 1, VERSION, {}),
    ("bad_key_prefix", "front", "bad_key_prefix", 1, VERSION, {}),
    ("dict_window", "mtf", "dict_window", 3, VERSION, {}),
    *[(kind, "log_random", kind, 1, VERSION, {}) for kind in COMBO_DAMAGE],
    ("crc_and_body", "whitened", "crc_and_body", 1, VERSION, {}),
    *[(kind, "log_random", kind, 1, VERSION, {}) for kind in ORDER_DAMAGE],
    ("prefix_before_suffix", "front", "prefix_before_suffix", 1, VERSION, {}),
    ("noncanonical_suffix", "front", "noncanonical_suffix", 1, VERSION, {}),
    ("first_failing_record", "whitened", "first_failing_record", 1, VERSION, {}),
    ("field_whitened", "whitened", None, 4, FIELD_VERSION, _NO_STATE),
    ("field_whitened", "whitened", None, 2, FIELD_VERSION, {**_NO_STATE, "salt_zero": 1.0}),
    ("field_dictionary", "mtf", None, 6, FIELD_VERSION, {"w_repeat": 0}),
    ("field_dict_window", "mtf", "dict_window", 3, FIELD_VERSION, {"w_repeat": 0}),
    ("field_repeat", "repeat", None, 4, FIELD_VERSION, {"w_dict": 0}),
    ("field_repeat", "wrap", None, 3, FIELD_VERSION, {"w_dict": 0}),
    ("v3_layout", "plain", None, 4, FIELD5_VERSION, _RAW_ONLY),
    ("v3_layout", "front", None, 2, FIELD5_VERSION, _RAW_ONLY),
    ("v3_layout", "plain", "crc_trailer", 2, FIELD5_VERSION, _RAW_ONLY),
    ("v3_layout", "plain", "reserved_selector", 2, FIELD5_VERSION, _RAW_ONLY),
    ("v3_whitened", "whitened", None, 4, FIELD5_VERSION, _RAW_ONLY),
    ("v3_whitened", "whitened", None, 2, FIELD5_VERSION, {**_RAW_ONLY, "salt_zero": 1.0}),
    ("v3_deltas", "padded", None, 5, FIELD5_VERSION, _NO_STATE),
    ("v3_repeats", "repeat", None, 4, FIELD5_VERSION, {"w_dict": 0}),
    ("v3_dictionary", "mtf", None, 6, FIELD5_VERSION, {"w_delta": 0, "w_repeat": 0}),
    ("v3_dict_window", "mtf", "dict_window", 3, FIELD5_VERSION, {"w_delta": 0, "w_repeat": 0}),
    ("v3_mixed", "everything", None, 4, FIELD5_VERSION, {}),
    ("v4_layout", "front", None, 8, FIELD6_VERSION, _RAW_ONLY),
    ("v4_whitened", "whitened", None, 6, FIELD6_VERSION, _NO_STATE),
    ("v4_whitened", "whitened", None, 2, FIELD6_VERSION, {**_NO_STATE, "salt_zero": 1.0}),
    ("v4_deltas_repeats", "padded", None, 6, FIELD6_VERSION, {"w_dict": 0, "w_repeat": 4}),
    ("v4_dictionary", "mtf", None, 8, FIELD6_VERSION, {"w_repeat": 0}),
    ("v4_dict_window", "mtf", "dict_window", 3, FIELD6_VERSION, {"w_repeat": 0}),
    ("v4_mixed", "everything", None, 6, FIELD6_VERSION, {}),
    ("v4_damage", "plain", "crc_trailer", 1, FIELD6_VERSION, _RAW_ONLY),
    ("v4_damage", "plain", "reserved_selector", 1, FIELD6_VERSION, _RAW_ONLY),
    ("v4_damage", "padded", "overlong_delta", 1, FIELD6_VERSION, _NO_STATE),
    ("v4_damage", "mtf", "dict_window", 1, FIELD6_VERSION, {"w_repeat": 0}),
    ("v4_damage", "repeat", "repeat_without_delta", 1, FIELD6_VERSION, {"w_dict": 0}),
]

_EVAL_CACHE: list[dict[str, Any]] = []
_EVAL_LOCK = threading.Lock()


def eval_corpus() -> list[dict[str, Any]]:
    with _EVAL_LOCK:
        if _EVAL_CACHE:
            return _EVAL_CACHE
        _EVAL_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(_EVAL_DIR, 0o755)
        rng = Rng(EVAL_SEED)
        serial = 0
        for label, name, kind, count, version, overrides in EVAL_PLAN:
            for _ in range(count):
                serial += 1
                prof = _profile(name, v2=1.0 if version == FIELD_VERSION else 0.0,
                                v3=1.0 if version == FIELD5_VERSION else 0.0,
                                v4=1.0 if version == FIELD6_VERSION else 0.0, **overrides)
                if kind is None:
                    doc = generate_doc(rng, prof)
                    blob = encode_doc(doc)
                else:
                    blob, doc = build_damaged(rng, prof, kind)
                if doc["version"] != version:
                    raise AssertionError(f"{label}: built version {doc['version']}, planned {version}")
                result = reference_decode(blob)
                if kind is None and canonical(result) != canonical(doc):
                    raise AssertionError("reference decode disagrees with an evaluation document")
                path = _EVAL_DIR / f"eval_{serial:03d}.trc"
                path.write_bytes(blob)
                os.chmod(path, 0o644)
                _EVAL_CACHE.append({"path": path, "blob": blob, "label": label, "profile": name,
                                    "damage": kind, "version": version, "expected": result,
                                    "tags": trap_tags(doc, result, kind)})
        return _EVAL_CACHE


def _fresh_lookalikes() -> list[dict[str, Any]]:
    """Captures drawn with the capture log's own profile mix, from the hidden seed."""
    out: list[dict[str, Any]] = []
    rng = Rng(EVAL_SEED ^ 0xC0DE5EED)
    _EVAL_DIR.mkdir(parents=True, exist_ok=True)
    while len(out) < 24:
        row = _log_entry(rng, f"fresh-{len(out)}")
        if row["damage"] is not None:
            continue
        path = _EVAL_DIR / f"lookalike_{len(out):03d}.trc"
        path.write_bytes(bytes.fromhex(row["hex"]))
        os.chmod(path, 0o644)
        out.append({"path": path, "expected": row["result"]})
    return out


def _visible_samples() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    _EVAL_DIR.mkdir(parents=True, exist_ok=True)
    for row in capture_log():
        if row["damage"] is None:
            path = _EVAL_DIR / f"shipped_{row['capture_id']}.trc"
            path.write_bytes(bytes.fromhex(row["hex"]))
            os.chmod(path, 0o644)
            out.append({"path": path, "expected": row["result"]})
        if len(out) == 24:
            break
    return out


VERIFIED_SEED = 7310086144287611203
_VERIFIED_PLAN: list[tuple[str, str | None, int]] = [
    ("mtf", None, 8), ("repeat", None, 6), ("whitened", None, 6), ("everything", None, 2),
    ("front", None, 3), ("wrap", None, 3), ("padded", None, 2), ("plain", None, 4),
    ("mtf", "dict_window", 3), ("plain", "dict_out_of_range", 2), ("whitened", "crc_trailer", 3),
    ("plain", "crc_trailer", 2), ("log_random", "repeat_without_delta", 1),
]


def verified_sample() -> list[dict[str, Any]]:
    """Hand-verified field-build decodings shipped as MDUMP-rev4-verified.jsonl; never graded."""
    rng = Rng(VERIFIED_SEED)
    out = []
    for name, kind, count in _VERIFIED_PLAN:
        for _ in range(count):
            prof = _profile(name, v2=1.0, v3=0.0)
            if name == "mtf":
                prof["n"] = (40, 90)
            blob = encode_doc(generate_doc(rng, prof)) if kind is None else build_damaged(rng, prof, kind)[0]
            out.append({"hex": blob.hex(), "decoded": reference_decode(blob)})
    return out


FINGERPRINT_SEED = 0x6A09E667F3BCC908
_FINGERPRINT_PLAN: list[tuple[str, str | None, int, dict[str, Any]]] = [
    ("plain", None, 6, {}), ("padded", None, 6, _NO_STATE), ("repeat", None, 5, {"w_dict": 0}),
    ("mtf", None, 8, {"w_delta": 0, "w_repeat": 0}), ("mtf", "dict_window", 3, {"w_delta": 0, "w_repeat": 0}),
    ("whitened", None, 6, {}), ("front", None, 4, {}), ("wrap", None, 4, {}), ("everything", None, 3, {}),
    ("plain", "crc_trailer", 3, {}), ("plain", "dict_out_of_range", 2, {}),
]


def fingerprint_sample() -> list[dict[str, str]]:
    """5.x captures with the fingerprint of their decoder output, shipped as MDUMP-rev5-fingerprints.jsonl; never graded."""
    rng = Rng(FINGERPRINT_SEED)
    out = []
    for name, kind, count, overrides in _FINGERPRINT_PLAN:
        for _ in range(count):
            prof = _profile(name, v2=0.0, v3=1.0, **overrides)
            if name == "mtf":
                prof["n"] = (40, 90)
            blob = encode_doc(generate_doc(rng, prof)) if kind is None else build_damaged(rng, prof, kind)[0]
            out.append({"hex": blob.hex(), "sha256": digest(reference_decode(blob))})
    return out


def _write_corpus(root: Path) -> None:
    """Write the capture log and the two field-build samples under <root>/data."""
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"capture_id": row["capture_id"], "hex": row["hex"]}, separators=(",", ":"))
             for row in capture_log()]
    (data / "MDUMP-capture-log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sample = [json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) for row in verified_sample()]
    (data / "MDUMP-rev4-verified.jsonl").write_text("\n".join(sample) + "\n", encoding="utf-8")
    prints = [json.dumps(row, sort_keys=True, separators=(",", ":")) for row in fingerprint_sample()]
    (data / "MDUMP-rev5-fingerprints.jsonl").write_text("\n".join(prints) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Running the submitted programs.                                             #
# --------------------------------------------------------------------------- #

_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file and rename it, so a program can
    land at mode 0600. The checks run it as an unprivileged user; the verifier
    runs as root, so widening the read bits is always allowed and changes no
    graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


# Agent programs always run as `sys.executable -I -S`, the "clean Python 3.12 with
# only the standard library" the instruction promises: no user site, no script
# directory on sys.path, and no site-packages at all.
_AUDIT_TOKEN = "__mdump_agent_data_access_5c1e__"
_AUDIT_WRAPPER = (
    "import os, runpy, sys\n"
    "def _watch(event, args):\n"
    "    if event not in ('open', 'os.listdir', 'os.scandir') or not args:\n"
    "        return\n"
    "    try:\n"
    "        path = os.path.abspath(os.fsdecode(args[0]))\n"
    "    except Exception:\n"
    "        return\n"
    f"    if path == {_DATA_ROOT!r} or path.startswith({_DATA_ROOT + '/'!r}):\n"
    f"        os.write(2, b'\\n{_AUDIT_TOKEN}\\n')\n"
    "sys.addaudithook(_watch)\n"
    "target = sys.argv[1]\n"
    "sys.argv = sys.argv[1:]\n"
    "runpy.run_path(target, run_name='__main__')\n"
)


def _kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run_agent(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run agent code in its own session and kill whatever it leaves behind."""
    proc = subprocess.Popen(
        _untrusted_command(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd="/tmp",
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
             "PYTHONHASHSEED": "0"},
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=60)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        _kill_group(proc.pid)
        proc.kill()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        out, err, code = "", "timeout", -9
    finally:
        _kill_group(proc.pid)
    return subprocess.CompletedProcess(proc.args, code, out, err)


def _decode_fresh(cap: Path) -> dict | None:
    try:
        r = _run_agent([sys.executable, "-I", "-S", DECODER_PATH, str(cap)])
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    try:
        obj = json.loads(r.stdout)
    except (json.JSONDecodeError, RecursionError):
        return None
    return obj if isinstance(obj, dict) else None


_DECODE_CACHE: dict[str, dict | None] = {}


def run_decoder(cap: Path) -> dict | None:
    key = str(cap)
    if key not in _DECODE_CACHE:
        _DECODE_CACHE[key] = _decode_fresh(cap)
    return _DECODE_CACHE[key]


def _encoder_job(doc: dict, audited: bool = False) -> tuple[subprocess.CompletedProcess[str] | None, bytes | None]:
    """Encode one document in a private directory that is removed afterwards."""
    work = Path(tempfile.mkdtemp(prefix="mdump_enc_"))
    try:
        src, dst = work / "doc.json", work / "capture.trc"
        src.write_text(json.dumps(doc), encoding="utf-8")
        work.chmod(0o700)
        src.chmod(0o600)
        if os.name == "posix" and os.geteuid() == 0:
            uid, gid = pwd.getpwnam("nobody").pw_uid, grp.getgrnam("nogroup").gr_gid
            os.chown(work, uid, gid)
            os.chown(src, uid, gid)
        if audited:
            r = _run_agent([sys.executable, "-I", "-S", "-c", _AUDIT_WRAPPER, ENCODER_PATH, str(src), str(dst)])
        else:
            r = _run_agent([sys.executable, "-I", "-S", ENCODER_PATH, str(src), str(dst)])
        return r, (dst.read_bytes() if dst.is_file() else None)
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError):
        return None, None
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _encode_once(doc: dict, audited: bool = False) -> tuple[bytes | None, str]:
    r, written = _encoder_job(doc, audited)
    if r is None:
        return None, ""
    if r.returncode != 0 or written is None:
        return None, r.stderr
    return written, r.stderr


def run_encoder(doc: dict) -> bytes | None:
    return _encode_once(doc)[0]


def _same(a: Any, b: Any) -> bool:
    try:
        return canonical(a) == canonical(b)
    except (TypeError, ValueError):
        return False


def _eval_select(*labels: str) -> list[dict[str, Any]]:
    return [entry for entry in eval_corpus() if entry["label"] in labels]


def _eval_clean(version: int) -> list[dict[str, Any]]:
    return [e for e in eval_corpus() if e["damage"] is None and e["version"] == version]


def _all_decode_exactly(entries: list[dict[str, Any]], minimum: int) -> None:
    assert len(entries) >= minimum, f"evaluation tier holds {len(entries)} captures, need {minimum}"
    for entry in entries:
        got = run_decoder(entry["path"])
        assert got is not None, f"decoder failed on {entry['path'].name}"
        assert _same(got, entry["expected"]), (
            f"{entry['path'].name}: got {canonical(got)[:200]} expected {canonical(entry['expected'])[:200]}"
        )


# --------------------------------------------------------------------------- #
# Report artifacts.                                                           #
# --------------------------------------------------------------------------- #

def _report_rows() -> list[dict[str, Any]]:
    assert DECODED_EXAMPLES_PATH.is_file(), f"missing {DECODED_EXAMPLES_PATH}"
    rows = [json.loads(line) for line in DECODED_EXAMPLES_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    assert len(rows) >= 4, f"need at least four example rows, got {len(rows)}"
    for row in rows:
        assert isinstance(row, dict) and set(row) == {"name", "hex", "decoded"}, row
        assert isinstance(row["name"], str) and row["name"]
        assert not row["name"].startswith(("sample_", "field_", "eval_", "cap-"))
        assert isinstance(row["hex"], str) and row["hex"] == row["hex"].lower()
        bytes.fromhex(row["hex"])
        assert isinstance(row["decoded"], dict) and "records" in row["decoded"]
    return rows


def _mode_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"raw": 0, "delta": 0, "dict": 0, "repeat": 0}
    for row in rows:
        for rec in row["decoded"]["records"]:
            counts[rec["mode"]] += 1
    return counts


def _format_report() -> dict[str, Any]:
    assert FORMAT_REPORT_PATH.is_file(), f"missing {FORMAT_REPORT_PATH}"
    got = json.loads(FORMAT_REPORT_PATH.read_text(encoding="utf-8"))
    assert isinstance(got, dict)
    return got


def capture_group(row: dict[str, Any]) -> str:
    """Each logged capture belongs to exactly one group, so its digest is paid once."""
    if row["field_build"] == FIELD5_VERSION:
        return "field_build_v3"
    if row["field_build"] == FIELD_VERSION:
        return "field_build"
    if row["damage"] is not None:
        return "damaged"
    return "valid"


def _check_capture_group(name: str) -> None:
    report = _format_report()
    digests = report.get("capture_sha256")
    assert isinstance(digests, dict)
    rows = [row for row in capture_log() if capture_group(row) == name]
    assert len(rows) >= 200, f"group holds only {len(rows)} captures"
    wrong = [row["capture_id"] for row in rows if digests.get(row["capture_id"]) != row["sha256"]]
    assert not wrong, f"{len(wrong)} of {len(rows)} captures disagree, first {wrong[:5]}"


# --------------------------------------------------------------------------- #
# Positive checks.                                                            #
# --------------------------------------------------------------------------- #

def _inconsistent_documents(version: int, count: int, labels: tuple[str, ...] = ()) -> list[tuple[dict, dict]]:
    """True hidden-tier documents of one build with derived fields edited, and the refusal each must get."""
    cases = []
    clean = [e for e in _eval_clean(version) if e["expected"]["record_count"] >= 4
             and (not labels or e["label"] in labels)]
    for n, entry in enumerate(clean[:count]):
        doc = json.loads(canonical(entry["expected"]))
        recs = doc["records"]
        k = 1 + n % (len(recs) - 2)
        variant = n % 4
        if variant == 0:
            recs[k]["value"] = wrap32(recs[k]["value"] + 1)
            field = "value"
        elif variant == 1:
            recs[k]["offset"] += 1
            field = "offset"
        elif variant == 2:
            recs[k]["value"] = wrap32(recs[k]["value"] - 9)
            recs[k]["offset"] += 3
            field = "offset"
        else:
            recs[k]["value"] = wrap32(recs[k]["value"] + 7)
            recs[k + 1]["offset"] += 1
            field = "value"
        cases.append((doc, {"error": "inconsistent_document", "record_index": k, "field": field}))
    return cases


def _assert_refusals(cases: list[tuple[dict, dict]], expected_count: int) -> None:
    assert len(cases) == expected_count
    for doc, refusal in cases:
        r, written = _encoder_job(doc)
        assert r is not None and r.returncode == 1, "encoder did not exit with status 1"
        assert written is None, "encoder wrote a capture for an inconsistent document"
        assert _same(json.loads(r.stdout), refusal), f"got {r.stdout[:200]!r} expected {canonical(refusal)}"


def _assert_rebuilds(entries: list[dict[str, Any]], minimum: int) -> None:
    assert len(entries) >= minimum, f"evaluation tier holds {len(entries)} documents, need {minimum}"
    for entry in entries:
        rebuilt = run_encoder(entry["expected"])
        assert rebuilt == entry["blob"], f"encoder output differs for {entry['path'].name}"


REV3_PLAIN = ("plain", "boundary", "salted")
REV3_FLAGGED = ("big_endian", "whitened", "front")
REV3_STATEFUL = ("wrap", "mtf", "repeat", "padded", "everything", *WINDOW_DAMAGE)


def _has_zero_salt(entries: list[dict[str, Any]]) -> bool:
    return any(e["blob"][7:10] == b"\0\0\0" and e["blob"][10] & 1 << FLAG_BITS["whitened"] for e in entries)


def _check_encoder_refuses_rev3_documents():
    _assert_refusals(_inconsistent_documents(VERSION, 8), 8)


def _check_decodes_rev3_plain_captures():
    _all_decode_exactly(_eval_select(*REV3_PLAIN), 15)


def _check_decodes_rev3_flagged_captures():
    entries = _eval_select(*REV3_FLAGGED)
    assert _has_zero_salt(entries), "no zero-salt whitened capture"
    _all_decode_exactly(entries, 19)


def _check_decodes_rev3_stateful_captures():
    _all_decode_exactly(_eval_select(*REV3_STATEFUL), 30)


def _check_rejects_rev3_header_and_trailer_damage():
    _all_decode_exactly(_eval_select(*HEADER_DAMAGE, *COMBO_DAMAGE, *CRC_DAMAGE), 18)


def _check_reports_rev3_body_errors():
    _all_decode_exactly(_eval_select(*BODY_DAMAGE, *ORDER_DAMAGE), 26)


def _check_encoder_rebuilds_rev3_documents():
    _assert_rebuilds(_eval_clean(VERSION), 50)


def _check_decodes_field_build_whitened():
    entries = _eval_select("field_whitened")
    assert _has_zero_salt(entries), "no zero-salt field-build capture"
    _all_decode_exactly(entries, 6)


def _check_decodes_field_build_dictionary():
    _all_decode_exactly(_eval_select("field_dictionary", "field_dict_window"), 9)


def _check_decodes_field_build_repeats():
    _all_decode_exactly(_eval_select("field_repeat"), 7)


def _check_encoder_rebuilds_field_build_documents():
    _assert_rebuilds(_eval_clean(FIELD_VERSION), 19)


def _check_encoder_refuses_field_build_documents():
    _assert_refusals(_inconsistent_documents(FIELD_VERSION, 4), 4)


def _check_decodes_v3_record_layout():
    _all_decode_exactly(_eval_select("v3_layout"), 10)


def _check_decodes_v3_whitened():
    entries = _eval_select("v3_whitened")
    assert _has_zero_salt(entries), "no zero-salt 5.x capture"
    _all_decode_exactly(entries, 6)


def _check_decodes_v3_deltas():
    _all_decode_exactly(_eval_select("v3_deltas"), 5)


def _check_decodes_v3_repeats():
    _all_decode_exactly(_eval_select("v3_repeats"), 4)


def _check_decodes_v3_dictionary():
    _all_decode_exactly(_eval_select("v3_dictionary"), 6)


def _check_rejects_v3_window_overflow():
    _all_decode_exactly(_eval_select("v3_dict_window"), 3)


def _check_decodes_v3_mixed():
    _all_decode_exactly(_eval_select("v3_mixed"), 4)


def _check_encoder_rebuilds_v3_documents():
    _assert_rebuilds(_eval_clean(FIELD5_VERSION), 30)


def _check_encoder_refuses_v3_documents():
    _assert_refusals(_inconsistent_documents(FIELD5_VERSION, 4, ("v3_dictionary", "v3_mixed")), 4)


def _check_decodes_v4_layout_and_whitening():
    entries = _eval_select("v4_layout", "v4_whitened")
    assert _has_zero_salt(entries), "no zero-salt 6.x capture"
    _all_decode_exactly(entries, 16)


def _check_decodes_v4_deltas_and_repeats():
    _all_decode_exactly(_eval_select("v4_deltas_repeats"), 6)


def _check_decodes_v4_dictionary():
    _all_decode_exactly(_eval_select("v4_dictionary", "v4_dict_window"), 11)


def _check_decodes_v4_mixed():
    _all_decode_exactly(_eval_select("v4_mixed"), 6)


def _check_encoder_handles_v4_documents():
    _assert_rebuilds(_eval_clean(FIELD6_VERSION), 30)
    _assert_refusals(_inconsistent_documents(FIELD6_VERSION, 5,
                                             ("v4_dictionary", "v4_mixed")), 5)


def _check_v4_decode_case(index: int):
    _all_decode_exactly([_eval_clean(FIELD6_VERSION)[index]], 1)


def _check_v4_encode_case(index: int):
    _assert_rebuilds([_eval_clean(FIELD6_VERSION)[index]], 1)


def _check_v4_refusal_case(index: int):
    cases = _inconsistent_documents(FIELD6_VERSION, 5, ("v4_dictionary", "v4_mixed"))
    _assert_refusals([cases[index]], 1)


def _check_v4_damage_case(index: int):
    _all_decode_exactly([_eval_select("v4_damage")[index]], 1)


def _check_capture_index_rev3_valid_captures():
    _check_capture_group("valid")


def _check_capture_index_rev3_damaged_captures():
    _check_capture_group("damaged")


def _check_capture_index_field_build_captures():
    _check_capture_group("field_build")


def _check_capture_index_v3_captures():
    _check_capture_group("field_build_v3")


def _check_decoded_examples_artifact():
    rows = _report_rows()
    counts = _mode_counts(rows)
    assert all(counts[m] > 0 for m in counts), f"modes missing from examples: {counts}"
    for flag in ("front_coded_keys", "big_endian_raw", "whitened"):
        assert any(row["decoded"]["flags"][flag] for row in rows), f"no example sets {flag}"
    assert any(row["decoded"]["flags"]["front_coded_keys"] and any(r["long_key"] for r in row["decoded"]["records"])
               for row in rows), "no front-coded example carries a long key"
    for build in (FIELD_VERSION, FIELD5_VERSION):
        assert any(row["decoded"]["version"] == build and row["decoded"]["flags"]["whitened"]
                   for row in rows), f"no whitened version {build} example"
    shipped = (WORKED_EXAMPLE_HEX | {row["hex"] for row in verified_sample()}
               | {row["hex"] for row in fingerprint_sample()} | {row["hex"] for row in capture_log()})
    for row in rows:
        assert row["hex"] not in shipped, f"{row['name']}: copied from a shipped capture"
        payload = bytes.fromhex(row["hex"])
        assert _same(reference_decode(payload), row["decoded"]), f"{row['name']}: bytes and document disagree"
        assert encode_doc(row["decoded"]) == payload, f"{row['name']}: document does not rebuild its bytes"


_FORMAT_GRAMMAR_KEYS = ("header_order", "selector", "flag_bits", "delta_encoding", "dict_source",
                        "dict_direction", "dict_capacity", "dict_move_to_front", "crc_algorithm",
                        "crc_coverage")
_CAPTURE_TALLY_KEYS = ("capture_count", "capture_ok_count", "capture_mode_counts", "capture_flag_counts")


def _check_format_report_artifact():
    got = _format_report()
    rows = _report_rows()
    expected = {
        "format_tag": "MDUMP", "magic_hex": MAGIC.hex(), "version": VERSION,
        "header_size": HEADER_SIZE, "trailer_size": TRAILER_SIZE,
        **{key: GRAMMAR[key] for key in _FORMAT_GRAMMAR_KEYS},
        "visible_example_count": len(rows),
        "visible_record_counts": [row["decoded"]["record_count"] for row in rows],
        "visible_mode_counts": _mode_counts(rows),
    }
    assert set(got) == set(expected) | set(_CAPTURE_TALLY_KEYS) | {"capture_status", "capture_sha256"}, (
        "format_report key set is wrong")
    for key, value in expected.items():
        assert _same(got[key], value), f"format_report.{key} is wrong"


def _check_capture_log_summaries():
    # Every summary of the decoder's run over the log is graded here and only here, so one
    # misdecoded capture costs this check once rather than once per report that tallies it.
    report = _format_report()
    facts = capture_facts()
    for key in _CAPTURE_TALLY_KEYS:
        assert _same(report.get(key), facts[key]), f"format_report.{key} is wrong"
    statuses = report.get("capture_status")
    assert isinstance(statuses, dict)
    expected_status = {row["capture_id"]: row["status"] for row in capture_log()}
    assert set(statuses) == set(expected_status), "capture_status does not cover exactly the logged captures"
    wrong = [cid for cid, status in expected_status.items() if statuses[cid] != status]
    assert not wrong, f"{len(wrong)} statuses wrong, first {wrong[:5]}"
    assert ERROR_ANALYSIS_PATH.is_file(), f"missing {ERROR_ANALYSIS_PATH}"
    analysis = json.loads(ERROR_ANALYSIS_PATH.read_text(encoding="utf-8"))
    assert isinstance(analysis, dict)
    assert _same(analysis.get("capture_errors"), facts["capture_errors"]), "error_analysis.capture_errors is wrong"


def _check_roundtrip_report_artifact():
    assert ROUNDTRIP_REPORT_PATH.is_file(), f"missing {ROUNDTRIP_REPORT_PATH}"
    got = json.loads(ROUNDTRIP_REPORT_PATH.read_text(encoding="utf-8"))
    expected = []
    for row in _report_rows():
        payload = bytes.fromhex(row["hex"])
        rebuilt = run_encoder(row["decoded"])
        assert rebuilt == payload, f"{row['name']}: the delivered encoder does not rebuild this example"
        h = hashlib.sha256(payload).hexdigest()
        expected.append({"name": row["name"], "input_sha256": h, "rebuilt_sha256": h,
                         "byte_length": len(payload), "roundtrip_equal": True})
    assert _same(got, {"all_roundtrips_equal": True, "examples": expected})


def _check_error_analysis_artifact():
    assert ERROR_ANALYSIS_PATH.is_file(), f"missing {ERROR_ANALYSIS_PATH}"
    got = json.loads(ERROR_ANALYSIS_PATH.read_text(encoding="utf-8"))
    assert isinstance(got, dict) and set(got) == {"precedence", "cases", "capture_errors"}, (
        "error_analysis key set is wrong")
    first = bytes.fromhex(_report_rows()[0]["hex"])

    def damaged(*kinds: str) -> dict:
        b = bytearray(first)
        for kind in kinds:
            if kind == "magic":
                b[0] ^= 0xFF
            elif kind == "version":
                b[15] = 9
            elif kind == "flags":
                b[10] |= 0x80
            else:
                b[-1] ^= 0xFF
        return reference_decode(bytes(b))

    def one_byte_longer() -> dict:
        salt = int.from_bytes(first[7:10], "little")
        base = int.from_bytes(first[11:15], "little", signed=True)
        version = first[15]
        whitened = bool(first[10] & 1 << FLAG_BITS["whitened"])
        wire = first[HEADER_SIZE:len(first) - TRAILER_SIZE]
        plain = (_xor(wire, keystream(salt, len(wire), version, base)) if whitened else wire) + b"\x00"
        wire = _xor(plain, keystream(salt, len(plain), version, base)) if whitened else plain
        crc = trailer_crc(first[:HEADER_SIZE], plain, version)
        return reference_decode(first[:HEADER_SIZE] + wire + crc.to_bytes(4, "little"))

    cases = {
        "bad_magic": damaged("magic"),
        "unsupported_version": damaged("version"),
        "reserved_flag_set": damaged("flags"),
        "trailer_crc_mismatch": damaged("crc"),
        "all_three_broken": damaged("magic", "version", "crc"),
        "trailing_bytes": one_byte_longer(),
    }
    assert _same(got["precedence"], ERROR_PRECEDENCE), "error_analysis.precedence is wrong"
    assert _same(got["cases"], cases), "error_analysis.cases disagrees with the specification"


# --------------------------------------------------------------------------- #
# Negative checks (polarity-inverted).                                        #
# --------------------------------------------------------------------------- #

def _check_negative_weight_hardcoded_sample_answers():
    # Inverted polarity: holds only when the decoder is perfect on shipped captures and wrong on all lookalikes.
    shipped = _visible_samples()
    fresh = _fresh_lookalikes()
    shipped_ok = sum(1 for e in shipped if _same(run_decoder(e["path"]), e["expected"]))
    fresh_ok = sum(1 for e in fresh if _same(run_decoder(e["path"]), e["expected"]))
    assert shipped_ok == len(shipped) and fresh_ok == 0, f"honest baseline: shipped={shipped_ok}, fresh={fresh_ok}"


def _check_negative_weight_filename_dependent_behaviour():
    # Inverted polarity: holds only when two runs on the same file agree and a renamed copy decodes differently,
    # so run-to-run noise is left to negative_nondeterministic_output and never charged twice.
    divergent = []
    for entry in eval_corpus()[:4]:
        first = _decode_fresh(entry["path"])
        second = _decode_fresh(entry["path"])
        renamed = _EVAL_DIR / ("orphan_" + entry["path"].name)
        renamed.write_bytes(entry["blob"])
        renamed.chmod(0o644)
        again = _decode_fresh(renamed)
        if first is None or second is None or again is None:
            continue
        if _same(first, second) and not _same(first, again):
            divergent.append(entry["path"].name)
    assert divergent, "honest baseline: no divergence"


def _plant_decoy_data() -> bool:
    root = Path(_DATA_ROOT)
    if os.name != "posix" or os.geteuid() != 0 or root.exists():
        return False
    _write_corpus(root.parent)
    root.chmod(0o755)
    for child in root.iterdir():
        child.chmod(0o644)
    return True


def _check_negative_weight_reads_training_corpus_at_runtime():
    # Inverted polarity: holds only when a delivered program opens or lists a path under the agent data
    # directory while it runs. A decoy copy of the capture log is planted there so guarded reads show up too.
    planted = _plant_decoy_data()
    try:
        probes = _eval_select("plain")[:1] + _eval_select("crc_trailer")[:1]
        offenders = []
        for entry in probes:
            r = _run_agent([sys.executable, "-I", "-S", "-c", _AUDIT_WRAPPER, DECODER_PATH, str(entry["path"])])
            if _AUDIT_TOKEN in r.stderr:
                offenders.append(DECODER_PATH)
        clean = next(e for e in eval_corpus() if e["damage"] is None)
        if _AUDIT_TOKEN in _encode_once(clean["expected"], audited=True)[1]:
            offenders.append(ENCODER_PATH)
        assert offenders, "honest baseline: no access to the agent data directory"
    finally:
        if planted:
            shutil.rmtree(_DATA_ROOT, ignore_errors=True)


_GUARDED = {"builtins.open", "zlib.crc32", "struct.unpack", "json.dumps", "hashlib.sha256"}


def _check_negative_weight_rebinds_verifier_dependencies():
    # Inverted polarity: holds only when the delivered source reassigns one of the guarded standard-library names.
    def target_name(target: ast.expr) -> str | None:
        if isinstance(target, ast.Name) and target.id == "open":
            return "open"
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            pair = f"{target.value.id}.{target.attr}"
            if pair in _GUARDED:
                return pair
        return None

    offenders: list[str] = []
    for path_str in (DECODER_PATH, ENCODER_PATH):
        tree = ast.parse(Path(path_str).read_text(encoding="utf-8"), filename=path_str)
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets.extend(node.targets)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                targets.append(node.target)
            for target in targets:
                if name := target_name(target):
                    offenders.append(f"{path_str}:{name}")
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr"
                    and len(node.args) >= 2 and isinstance(node.args[0], ast.Name)
                    and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
                if f"{node.args[0].id}.{node.args[1].value}" in _GUARDED:
                    offenders.append(f"{path_str}:setattr")
    assert offenders, "honest baseline: verifier stdlib dependencies remain intact"


def _check_negative_weight_nondeterministic_output():
    # Inverted polarity: holds only when repeated runs on one capture disagree.
    entry = _eval_select("everything")[0]
    first = _decode_fresh(entry["path"])
    assert first is not None, "decoder crashed"
    diverged = False
    for _ in range(3):
        again = _decode_fresh(entry["path"])
        if again is None or not _same(first, again):
            diverged = True
            break
    assert diverged, "honest baseline: decoder is deterministic"


# --------------------------------------------------------------------------- #
# CLI regen entry point.                                                      #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 test_output.py <env_root>")
    _write_corpus(Path(sys.argv[1]))
    print(f"[test_output] regenerated capture log under {sys.argv[1]}/data")


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


@_legacy_criterion(description="The encoder refuses revision 3 documents with an edited value or offset, printing the documented object, exiting 1 and writing no capture.")
def encoder_refuses_rev3_documents(workspace: Path) -> bool:
    return _holds(_check_encoder_refuses_rev3_documents)


@_legacy_criterion(description="Revision 3 hidden captures with no flag beyond an optional salt or reserved_bit_0, including signed i16 and i32 boundary payloads, decode exactly.")
def decodes_rev3_plain_captures(workspace: Path) -> bool:
    return _holds(_check_decodes_rev3_plain_captures)


@_legacy_criterion(description="Revision 3 hidden big-endian, whitened (one with a zero salt) and front-coded captures decode exactly.")
def decodes_rev3_flagged_captures(workspace: Path) -> bool:
    return _holds(_check_decodes_rev3_flagged_captures)


@_legacy_criterion(description="Revision 3 hidden captures that wrap, pad deltas, repeat, or lean on the move-to-front window decode exactly, window overflows included.")
def decodes_rev3_stateful_captures(workspace: Path) -> bool:
    return _holds(_check_decodes_rev3_stateful_captures)


@_legacy_criterion(description="Header and trailer damage, alone or with a second fault, yields the exact error object of highest precedence, CRC values included.")
def rejects_rev3_header_and_trailer_damage(workspace: Path) -> bool:
    return _holds(_check_rejects_rev3_header_and_trailer_damage)


@_legacy_criterion(description="Revision 3 body damage, including two faults in one record or in two records, yields the error object for the first fault met in read order.")
def reports_rev3_body_errors(workspace: Path) -> bool:
    return _holds(_check_reports_rev3_body_errors)


@_legacy_criterion(description="The encoder rebuilds every clean revision 3 hidden capture byte for byte from its true document.")
def encoder_rebuilds_rev3_documents(workspace: Path) -> bool:
    return _holds(_check_encoder_rebuilds_rev3_documents)


@_legacy_criterion(description="Hidden version 2 whitened captures without dictionary or repeat records, including a zero-salt one, decode exactly.")
def decodes_field_build_whitened(workspace: Path) -> bool:
    return _holds(_check_decodes_field_build_whitened)


@_legacy_criterion(description="Hidden version 2 dictionary-heavy captures without repeat records decode exactly, and indices past the version 2 window are rejected with its size.")
def decodes_field_build_dictionary(workspace: Path) -> bool:
    return _holds(_check_decodes_field_build_dictionary)


@_legacy_criterion(description="Hidden version 2 captures dense in repeat records, without dictionary records, decode exactly.")
def decodes_field_build_repeats(workspace: Path) -> bool:
    return _holds(_check_decodes_field_build_repeats)


@_legacy_criterion(description="The encoder rebuilds every clean version 2 hidden capture byte for byte from its true document.")
def encoder_rebuilds_field_build_documents(workspace: Path) -> bool:
    return _holds(_check_encoder_rebuilds_field_build_documents)


@_legacy_criterion(description="The encoder refuses version 2 documents with an edited value or offset, printing the documented object, exiting 1 and writing no capture.")
def encoder_refuses_field_build_documents(workspace: Path) -> bool:
    return _holds(_check_encoder_refuses_field_build_documents)


@_legacy_criterion(description="Hidden version 3 captures holding only raw records, some with a damaged trailer or reserved selector bits, decode exactly.")
def decodes_v3_record_layout(workspace: Path) -> bool:
    return _holds(_check_decodes_v3_record_layout)


@_legacy_criterion(description="Hidden version 3 whitened captures holding only raw records, including zero-salt ones, decode exactly.")
def decodes_v3_whitened(workspace: Path) -> bool:
    return _holds(_check_decodes_v3_whitened)


@_legacy_criterion(description="Hidden version 3 captures of raw and padded delta records decode exactly with their pad counts.")
def decodes_v3_deltas(workspace: Path) -> bool:
    return _holds(_check_decodes_v3_deltas)


@_legacy_criterion(description="Hidden version 3 captures dense in repeat records, without dictionary records, decode exactly.")
def decodes_v3_repeats(workspace: Path) -> bool:
    return _holds(_check_decodes_v3_repeats)


@_legacy_criterion(description="Hidden version 3 captures of raw and dictionary records decode exactly.")
def decodes_v3_dictionary(workspace: Path) -> bool:
    return _holds(_check_decodes_v3_dictionary)


@_legacy_criterion(description="Hidden version 3 dictionary indices past the version 3 window are rejected with its size.")
def rejects_v3_window_overflow(workspace: Path) -> bool:
    return _holds(_check_rejects_v3_window_overflow)


@_legacy_criterion(description="Long hidden version 3 captures mixing every flag and mode decode exactly.")
def decodes_v3_mixed(workspace: Path) -> bool:
    return _holds(_check_decodes_v3_mixed)


@_legacy_criterion(description="The encoder rebuilds every clean version 3 hidden capture byte for byte from its true document.")
def encoder_rebuilds_v3_documents(workspace: Path) -> bool:
    return _holds(_check_encoder_rebuilds_v3_documents)


@_legacy_criterion(description="The encoder refuses version 3 documents with an edited value or offset, printing the documented object, exiting 1 and writing no capture.")
def encoder_refuses_v3_documents(workspace: Path) -> bool:
    return _holds(_check_encoder_refuses_v3_documents)


@_legacy_criterion(description="Version 4 hidden decode case 01 matches the full reference document.")
def v4_decode_case_01(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(0))


@_legacy_criterion(description="Version 4 hidden decode case 02 matches the full reference document.")
def v4_decode_case_02(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(1))


@_legacy_criterion(description="Version 4 hidden decode case 03 matches the full reference document.")
def v4_decode_case_03(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(2))


@_legacy_criterion(description="Version 4 hidden decode case 04 matches the full reference document.")
def v4_decode_case_04(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(3))


@_legacy_criterion(description="Version 4 hidden decode case 05 matches the full reference document.")
def v4_decode_case_05(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(4))


@_legacy_criterion(description="Version 4 hidden decode case 06 matches the full reference document.")
def v4_decode_case_06(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(5))


@_legacy_criterion(description="Version 4 hidden decode case 07 matches the full reference document.")
def v4_decode_case_07(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(6))


@_legacy_criterion(description="Version 4 hidden decode case 08 matches the full reference document.")
def v4_decode_case_08(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(7))


@_legacy_criterion(description="Version 4 hidden decode case 09 matches the full reference document.")
def v4_decode_case_09(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(8))


@_legacy_criterion(description="Version 4 hidden decode case 10 matches the full reference document.")
def v4_decode_case_10(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(9))


@_legacy_criterion(description="Version 4 hidden decode case 11 matches the full reference document.")
def v4_decode_case_11(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(10))


@_legacy_criterion(description="Version 4 hidden decode case 12 matches the full reference document.")
def v4_decode_case_12(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(11))


@_legacy_criterion(description="Version 4 hidden decode case 13 matches the full reference document.")
def v4_decode_case_13(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(12))


@_legacy_criterion(description="Version 4 hidden decode case 14 matches the full reference document.")
def v4_decode_case_14(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(13))


@_legacy_criterion(description="Version 4 hidden decode case 15 matches the full reference document.")
def v4_decode_case_15(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(14))


@_legacy_criterion(description="Version 4 hidden decode case 16 matches the full reference document.")
def v4_decode_case_16(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(15))


@_legacy_criterion(description="Version 4 hidden decode case 17 matches the full reference document.")
def v4_decode_case_17(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(16))


@_legacy_criterion(description="Version 4 hidden decode case 18 matches the full reference document.")
def v4_decode_case_18(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(17))


@_legacy_criterion(description="Version 4 hidden decode case 19 matches the full reference document.")
def v4_decode_case_19(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(18))


@_legacy_criterion(description="Version 4 hidden decode case 20 matches the full reference document.")
def v4_decode_case_20(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(19))


@_legacy_criterion(description="Version 4 hidden decode case 21 matches the full reference document.")
def v4_decode_case_21(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(20))


@_legacy_criterion(description="Version 4 hidden decode case 22 matches the full reference document.")
def v4_decode_case_22(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(21))


@_legacy_criterion(description="Version 4 hidden decode case 23 matches the full reference document.")
def v4_decode_case_23(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(22))


@_legacy_criterion(description="Version 4 hidden decode case 24 matches the full reference document.")
def v4_decode_case_24(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(23))


@_legacy_criterion(description="Version 4 hidden decode case 25 matches the full reference document.")
def v4_decode_case_25(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(24))


@_legacy_criterion(description="Version 4 hidden decode case 26 matches the full reference document.")
def v4_decode_case_26(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(25))


@_legacy_criterion(description="Version 4 hidden decode case 27 matches the full reference document.")
def v4_decode_case_27(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(26))


@_legacy_criterion(description="Version 4 hidden decode case 28 matches the full reference document.")
def v4_decode_case_28(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(27))


@_legacy_criterion(description="Version 4 hidden decode case 29 matches the full reference document.")
def v4_decode_case_29(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(28))


@_legacy_criterion(description="Version 4 hidden decode case 30 matches the full reference document.")
def v4_decode_case_30(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(29))


@_legacy_criterion(description="Version 4 hidden decode case 31 matches the full reference document.")
def v4_decode_case_31(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(30))


@_legacy_criterion(description="Version 4 hidden decode case 32 matches the full reference document.")
def v4_decode_case_32(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(31))


@_legacy_criterion(description="Version 4 hidden decode case 33 matches the full reference document.")
def v4_decode_case_33(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(32))


@_legacy_criterion(description="Version 4 hidden decode case 34 matches the full reference document.")
def v4_decode_case_34(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(33))


@_legacy_criterion(description="Version 4 hidden decode case 35 matches the full reference document.")
def v4_decode_case_35(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(34))


@_legacy_criterion(description="Version 4 hidden decode case 36 matches the full reference document.")
def v4_decode_case_36(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_decode_case(35))


@_legacy_criterion(description="Version 4 hidden encoder case 01 rebuilds its capture byte for byte.")
def v4_encode_case_01(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(0))


@_legacy_criterion(description="Version 4 hidden encoder case 02 rebuilds its capture byte for byte.")
def v4_encode_case_02(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(1))


@_legacy_criterion(description="Version 4 hidden encoder case 03 rebuilds its capture byte for byte.")
def v4_encode_case_03(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(2))


@_legacy_criterion(description="Version 4 hidden encoder case 04 rebuilds its capture byte for byte.")
def v4_encode_case_04(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(3))


@_legacy_criterion(description="Version 4 hidden encoder case 05 rebuilds its capture byte for byte.")
def v4_encode_case_05(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(4))


@_legacy_criterion(description="Version 4 hidden encoder case 06 rebuilds its capture byte for byte.")
def v4_encode_case_06(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(5))


@_legacy_criterion(description="Version 4 hidden encoder case 07 rebuilds its capture byte for byte.")
def v4_encode_case_07(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(6))


@_legacy_criterion(description="Version 4 hidden encoder case 08 rebuilds its capture byte for byte.")
def v4_encode_case_08(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(7))


@_legacy_criterion(description="Version 4 hidden encoder case 09 rebuilds its capture byte for byte.")
def v4_encode_case_09(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(8))


@_legacy_criterion(description="Version 4 hidden encoder case 10 rebuilds its capture byte for byte.")
def v4_encode_case_10(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(9))


@_legacy_criterion(description="Version 4 hidden encoder case 11 rebuilds its capture byte for byte.")
def v4_encode_case_11(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(10))


@_legacy_criterion(description="Version 4 hidden encoder case 12 rebuilds its capture byte for byte.")
def v4_encode_case_12(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(11))


@_legacy_criterion(description="Version 4 hidden encoder case 13 rebuilds its capture byte for byte.")
def v4_encode_case_13(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(12))


@_legacy_criterion(description="Version 4 hidden encoder case 14 rebuilds its capture byte for byte.")
def v4_encode_case_14(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(13))


@_legacy_criterion(description="Version 4 hidden encoder case 15 rebuilds its capture byte for byte.")
def v4_encode_case_15(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(14))


@_legacy_criterion(description="Version 4 hidden encoder case 16 rebuilds its capture byte for byte.")
def v4_encode_case_16(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(15))


@_legacy_criterion(description="Version 4 hidden encoder case 17 rebuilds its capture byte for byte.")
def v4_encode_case_17(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(16))


@_legacy_criterion(description="Version 4 hidden encoder case 18 rebuilds its capture byte for byte.")
def v4_encode_case_18(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(17))


@_legacy_criterion(description="Version 4 hidden encoder case 19 rebuilds its capture byte for byte.")
def v4_encode_case_19(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(18))


@_legacy_criterion(description="Version 4 hidden encoder case 20 rebuilds its capture byte for byte.")
def v4_encode_case_20(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(19))


@_legacy_criterion(description="Version 4 hidden encoder case 21 rebuilds its capture byte for byte.")
def v4_encode_case_21(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(20))


@_legacy_criterion(description="Version 4 hidden encoder case 22 rebuilds its capture byte for byte.")
def v4_encode_case_22(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(21))


@_legacy_criterion(description="Version 4 hidden encoder case 23 rebuilds its capture byte for byte.")
def v4_encode_case_23(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(22))


@_legacy_criterion(description="Version 4 hidden encoder case 24 rebuilds its capture byte for byte.")
def v4_encode_case_24(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_encode_case(23))


@_legacy_criterion(description="Version 4 edited-document refusal case 01 returns the exact error and writes no capture.")
def v4_refusal_case_01(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_refusal_case(0))


@_legacy_criterion(description="Version 4 edited-document refusal case 02 returns the exact error and writes no capture.")
def v4_refusal_case_02(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_refusal_case(1))


@_legacy_criterion(description="Version 4 edited-document refusal case 03 returns the exact error and writes no capture.")
def v4_refusal_case_03(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_refusal_case(2))


@_legacy_criterion(description="Version 4 edited-document refusal case 04 returns the exact error and writes no capture.")
def v4_refusal_case_04(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_refusal_case(3))


@_legacy_criterion(description="Version 4 edited-document refusal case 05 returns the exact error and writes no capture.")
def v4_refusal_case_05(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_refusal_case(4))


@_legacy_criterion(description="Version 4 damaged-capture case 01 returns the exact precedence-selected error.")
def v4_damage_case_01(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_damage_case(0))


@_legacy_criterion(description="Version 4 damaged-capture case 02 returns the exact precedence-selected error.")
def v4_damage_case_02(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_damage_case(1))


@_legacy_criterion(description="Version 4 damaged-capture case 03 returns the exact precedence-selected error.")
def v4_damage_case_03(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_damage_case(2))


@_legacy_criterion(description="Version 4 damaged-capture case 04 returns the exact precedence-selected error.")
def v4_damage_case_04(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_damage_case(3))


@_legacy_criterion(description="Version 4 damaged-capture case 05 returns the exact precedence-selected error.")
def v4_damage_case_05(workspace: Path) -> bool:
    return _holds(lambda: _check_v4_damage_case(4))

@_legacy_criterion(description="Capture digests are right for every valid revision 3 logged capture.")
def capture_index_rev3_valid_captures(workspace: Path) -> bool:
    return _holds(_check_capture_index_rev3_valid_captures)


@_legacy_criterion(description="Capture digests are right for every damaged logged capture whose output does not depend on the 4.x or 5.x rules.")
def capture_index_rev3_damaged_captures(workspace: Path) -> bool:
    return _holds(_check_capture_index_rev3_damaged_captures)


@_legacy_criterion(description="Capture digests are right for every logged version 2 capture that reaches the trailer check.")
def capture_index_field_build_captures(workspace: Path) -> bool:
    return _holds(_check_capture_index_field_build_captures)


@_legacy_criterion(description="Capture digests are right for every logged version 3 capture that reaches the trailer check.")
def capture_index_v3_captures(workspace: Path) -> bool:
    return _holds(_check_capture_index_v3_captures)


@criterion(description="decoded_examples.jsonl holds self-built examples, none taken from a shipped capture, covering every mode and flag and rebuilding exactly.")
def decoded_examples_artifact(workspace: Path) -> bool:
    return _holds(_check_decoded_examples_artifact)


@criterion(description="format_report.json carries exactly the documented keys, the grammar summary and the tallies of the example file.")
def format_report_artifact(workspace: Path) -> bool:
    return _holds(_check_format_report_artifact)


@criterion(description="The capture tallies and per-capture statuses in format_report.json and the capture error tally in error_analysis.json are right for the whole log.")
def capture_log_summaries(workspace: Path) -> bool:
    return _holds(_check_capture_log_summaries)


@criterion(description="roundtrip_report.json records byte equality for every example row, and the delivered encoder really rebuilds each one.")
def roundtrip_report_artifact(workspace: Path) -> bool:
    return _holds(_check_roundtrip_report_artifact)


@criterion(description="error_analysis.json carries exactly the documented keys, the precedence list and the decoder output for the six damaged copies.")
def error_analysis_artifact(workspace: Path) -> bool:
    return _holds(_check_error_analysis_artifact)


@criterion(description="The decoder produces exact documents for valid captures from every documented build line.")
def decodes_every_documented_build(workspace: Path) -> bool:
    checks = (
        decodes_rev3_plain_captures,
        decodes_rev3_flagged_captures,
        decodes_rev3_stateful_captures,
        decodes_field_build_whitened,
        decodes_field_build_dictionary,
        decodes_field_build_repeats,
        decodes_v3_record_layout,
        decodes_v3_whitened,
        decodes_v3_deltas,
        decodes_v3_repeats,
        decodes_v3_dictionary,
        decodes_v3_mixed,
        *(globals()[f"v4_decode_case_{index:02d}"] for index in range(1, 37)),
    )
    return all(check(workspace) for check in checks)


@criterion(description="The encoder rebuilds exact captures from valid documents for every documented build line.")
def encodes_every_documented_build(workspace: Path) -> bool:
    checks = (
        encoder_rebuilds_rev3_documents,
        encoder_rebuilds_field_build_documents,
        encoder_rebuilds_v3_documents,
        *(globals()[f"v4_encode_case_{index:02d}"] for index in range(1, 25)),
    )
    return all(check(workspace) for check in checks)


@criterion(description="Damaged captures produce the exact precedence-selected error for every documented build line.")
def rejects_damage_for_every_documented_build(workspace: Path) -> bool:
    checks = (
        rejects_rev3_header_and_trailer_damage,
        reports_rev3_body_errors,
        rejects_v3_window_overflow,
        *(globals()[f"v4_damage_case_{index:02d}"] for index in range(1, 6)),
    )
    return all(check(workspace) for check in checks)


@criterion(description="The capture index records the exact status and digest for every logged capture and build line.")
def capture_index_matches_full_log(workspace: Path) -> bool:
    checks = (
        capture_index_rev3_valid_captures,
        capture_index_rev3_damaged_captures,
        capture_index_field_build_captures,
        capture_index_v3_captures,
    )
    return all(check(workspace) for check in checks)


@criterion(description="Edited documents are refused exactly and leave no capture for every documented build line.")
def refuses_edits_for_every_documented_build(workspace: Path) -> bool:
    checks = (
        encoder_refuses_rev3_documents,
        encoder_refuses_field_build_documents,
        encoder_refuses_v3_documents,
        *(globals()[f"v4_refusal_case_{index:02d}"] for index in range(1, 6)),
    )
    return all(check(workspace) for check in checks)


@criterion(description="Fires when the decoder is right on shipped captures and wrong on every fresh lookalike.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_weight_hardcoded_sample_answers)


@criterion(description="Fires when the decoder is stable on one file name and decodes a renamed copy differently.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    return _holds(_check_negative_weight_filename_dependent_behaviour)


@criterion(description="Fires when a delivered program opens or lists a path under the agent data directory while it runs.")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    return _holds(_check_negative_weight_reads_training_corpus_at_runtime)


@criterion(description="Fires when delivered code rebinds verifier stdlib dependencies.")
def negative_rebinds_verifier_dependencies(workspace: Path) -> bool:
    return _holds(_check_negative_weight_rebinds_verifier_dependencies)


@criterion(description="Fires when decoder produces different outputs across runs.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    return _holds(_check_negative_weight_nondeterministic_output)


criteria.decodes_every_documented_build(weight=5)
criteria.encodes_every_documented_build(weight=5)
criteria.rejects_damage_for_every_documented_build(weight=5)
criteria.refuses_edits_for_every_documented_build(weight=5)
criteria.capture_index_matches_full_log(weight=5)
criteria.decoded_examples_artifact(weight=3)
criteria.format_report_artifact(weight=1)
criteria.capture_log_summaries(weight=5)
criteria.roundtrip_report_artifact(weight=3)
criteria.error_analysis_artifact(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_rebinds_verifier_dependencies(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
