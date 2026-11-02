"""Verifier for the VARC recovery task (multi-mode HARDFMT container).

This file is self-contained: it carries the ground-truth encoder, a bit-exact
mirror of the reference decoder, a deterministic pseudo-random corpus builder,
and the complete test bank.

Harbor runs `test.sh` in a SEPARATE container that does NOT have /app/data.
`_corpus_root()` therefore regenerates the entire sample + field corpus from
the SAMPLE_SEED and CHALLENGE_SEED constants below (identical to what the
agent's container was baked with). Expected documents are derived inside the
verifier and never shipped into the agent-visible environment.

Test polarity for negative-weight tests: the assertion HOLDS when the cheat is
present.  Honest agent -> assertion fails -> test 'fails' -> weight NOT added
-> honest agent's score stays high.  Cheating agent -> assertion passes ->
weight IS added -> cheating agent's score drops (negative total 18 versus a
positive_total of 63).
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import struct
import sys
import tempfile
import threading
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion


# --------------------------------------------------------------------------- #
# Format constants (mirror templates/solution/solve.py).                      #
# --------------------------------------------------------------------------- #

MAGIC = b"PIPE1"
VERSION = 5
HEADER_SIZE = 16
TRAILER_SIZE = 4

@dataclass(frozen=True)
class Grammar:
    selector: dict[str, Any]
    header_order: list[str]
    delta_encoding: str
    dict_source: str
    dict_direction: str
    crc_coverage: str


GRAMMAR = Grammar(**{'selector': {'mode_bits': [2, 3], 'wide_bit': 1, 'long_key_bit': 7, 'mode_ids': {'raw': 1, 'delta': 2, 'dict': 0}}, 'header_order': ['record_count', 'reserved', 'version', 'flags', 'base_value'], 'delta_encoding': 'signed_leb128', 'dict_source': 'resolved_values', 'dict_direction': 'backward', 'crc_coverage': 'header_records'})
MODE_RAW = GRAMMAR.selector["mode_ids"]["raw"]
MODE_DELTA = GRAMMAR.selector["mode_ids"]["delta"]
MODE_DICT = GRAMMAR.selector["mode_ids"]["dict"]

DECODER_PATH = "/app/decode.py"
ENCODER_PATH = "/app/encode.py"
DECODED_EXAMPLES_PATH = Path("/app/out/decoded_examples.jsonl")
FORMAT_REPORT_PATH = Path("/app/out/format_report.json")
ROUNDTRIP_REPORT_PATH = Path("/app/out/roundtrip_report.json")
ERROR_ANALYSIS_PATH = Path("/app/out/error_analysis.json")

# Seeds are generator-substituted; keep them here for local `python3 tests/
# test_output.py environment` regeneration too.
SAMPLE_SEED = 6842771334212724028
CHALLENGE_SEED = 7392569321898501261
EVAL_SEED = 1592153744120012122

_CORPUS_DIR = Path(tempfile.gettempdir()) / "VARC_00000000000457c3_corpus"
_EVAL_DIR = Path(tempfile.gettempdir()) / "VARC_00000000000457c3_eval"


# --------------------------------------------------------------------------- #
# Deterministic PRNG (xorshift64*).                                           #
# CPython's `random` is not contractually stable across versions; xorshift64* #
# is fully specified so the corpus is byte-identical on every host.           #
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

    def rand_u32(self) -> int:
        return self._next() & 0xFFFFFFFF

    def rand_int(self, lo: int, hi: int) -> int:
        # inclusive both ends
        span = hi - lo + 1
        return lo + (self._next() % span)

    def rand_signed(self, bits: int) -> int:
        # returns int in [-2^(bits-1), 2^(bits-1) - 1]
        v = self._next() & ((1 << bits) - 1)
        limit = 1 << (bits - 1)
        return v - (1 << bits) if v >= limit else v

    def rand_choice(self, seq):
        return seq[self._next() % len(seq)]

    def rand_bool(self, prob: float = 0.5) -> bool:
        return (self._next() & 0xFFFFFFFF) < int(prob * 0x100000000)


# --------------------------------------------------------------------------- #
# Encoder helpers - MIRROR of templates/solution/solve.py.  These MUST stay   #
# bit-identical to the reference encoder or byte-perfect round-trip tests     #
# will diverge.                                                               #
# --------------------------------------------------------------------------- #

def _read_uvarint(buf: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError("truncated uvarint")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return value, pos
        shift += 7
        if shift > 70:
            raise ValueError("uvarint too long")


def _write_uvarint(value: int) -> bytes:
    if value < 0:
        raise ValueError("uvarint cannot encode negative")
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def _read_sleb128(buf: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError("truncated sleb128")
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not (byte & 0x80):
            if byte & 0x40:
                result |= - (1 << shift)
            return result, pos
        if shift > 70:
            raise ValueError("sleb128 too long")


def _write_sleb128(value: int) -> bytes:
    out = bytearray()
    more = True
    while more:
        byte = value & 0x7F
        value >>= 7
        sign_set = bool(byte & 0x40)
        if (value == 0 and not sign_set) or (value == -1 and sign_set):
            more = False
        else:
            byte |= 0x80
        out.append(byte & 0xFF)
    return bytes(out)


def _zigzag_encode(v: int) -> int:
    # THE bit trick Opus repeatedly gets wrong: LSB = sign, rest = magnitude.
    return (v << 1) ^ (v >> 63) if v >= 0 else ((-v) << 1) - 1


def _zigzag_decode(u: int) -> int:
    return (u >> 1) ^ -(u & 1)


def _mode_to_selector_bits(mode_id: int) -> int:
    lo_bit, hi_bit = GRAMMAR.selector["mode_bits"]
    selector = 0
    if mode_id & 0x01:
        selector |= 1 << lo_bit
    if mode_id & 0x02:
        selector |= 1 << hi_bit
    return selector


def _selector_to_mode(selector: int) -> int:
    lo_bit, hi_bit = GRAMMAR.selector["mode_bits"]
    return ((selector >> lo_bit) & 1) | (((selector >> hi_bit) & 1) << 1)


def _flag(bit_name: str) -> int:
    return 1 << int(GRAMMAR.selector[bit_name])


def _header_offsets() -> dict[str, int]:
    pos = len(MAGIC)
    offsets: dict[str, int] = {}
    widths = {"version": 1, "flags": 1, "record_count": 2, "base_value": 4, "reserved": 3}
    for field in GRAMMAR.header_order:
        offsets[field] = pos
        pos += widths[field]
    return offsets


HEADER_OFFSETS = _header_offsets()


def _build_header(version: int, flags_byte: int, record_count: int, base_value: int) -> bytes:
    parts = {
        "version": struct.pack("<B", version),
        "flags": struct.pack("<B", flags_byte),
        "record_count": struct.pack("<H", record_count),
        "base_value": struct.pack("<i", base_value),
        "reserved": b"\x00\x00\x00",
    }
    return MAGIC + b"".join(parts[name] for name in GRAMMAR.header_order)


def _crc_payload(prefix: bytes) -> bytes:
    if GRAMMAR.crc_coverage == "prefix":
        return prefix
    if GRAMMAR.crc_coverage == "header_records":
        return prefix[len(MAGIC):]
    raise ValueError(f"unknown crc coverage {GRAMMAR.crc_coverage!r}")


def _dict_actual_index(payload_index: int, length: int) -> int:
    if GRAMMAR.dict_direction == "forward":
        return payload_index
    if GRAMMAR.dict_direction == "backward":
        return length - 1 - payload_index
    raise ValueError(f"unknown dict direction {GRAMMAR.dict_direction!r}")


def _write_delta(delta: int) -> bytes:
    if GRAMMAR.delta_encoding == "zigzag_uvarint":
        return _write_uvarint(_zigzag_encode(delta))
    if GRAMMAR.delta_encoding == "signed_leb128":
        return _write_sleb128(delta)
    raise ValueError(f"unknown delta encoding {GRAMMAR.delta_encoding!r}")


def encode_doc(doc: dict) -> bytes:
    """Bit-exact mirror of solve.py::encode()."""
    version = VERSION
    flags = doc.get("flags", {"reserved_bit_0": False})
    flags_byte = 0x01 if flags.get("reserved_bit_0", False) else 0x00
    records = doc["records"]
    record_count = doc.get("record_count", len(records))
    if record_count != len(records):
        raise ValueError("record_count does not match records length")
    if record_count > 0xFFFF:
        raise ValueError("record_count exceeds u16 range")

    base_value = doc.get("base_value", 0)
    if not (-0x80000000 <= base_value <= 0x7FFFFFFF):
        raise ValueError("base_value out of signed i32 range")

    header = _build_header(version, flags_byte, record_count, base_value)

    body = bytearray()
    for record in records:
        mode = record["mode"]
        if mode == "raw":
            mode_bits = MODE_RAW
        elif mode == "delta":
            mode_bits = MODE_DELTA
        elif mode == "dict":
            mode_bits = MODE_DICT
        else:
            raise ValueError(f"unknown mode {mode!r}")

        wide = 1 if record.get("wide_value", True) else 0
        long_key = 1 if record.get("long_key", False) else 0

        selector = _mode_to_selector_bits(mode_bits)
        if mode == "raw" and wide:
            selector |= _flag("wide_bit")
        if long_key:
            selector |= _flag("long_key_bit")

        body.append(selector)

        key = record["key"]
        if long_key:
            key_bytes = key.encode("utf-8") if isinstance(key, str) else bytes(key)
            body += _write_uvarint(len(key_bytes))
            body += key_bytes
        else:
            if not isinstance(key, int) or not (0 <= key <= 0xFF):
                raise ValueError(f"short key must be u8, got {key!r}")
            body.append(key)

        if mode == "raw":
            raw = record["raw_value"]
            if wide:
                if not (-0x80000000 <= raw <= 0x7FFFFFFF):
                    raise ValueError("raw i32 out of range")
                body += struct.pack("<i", raw)
            else:
                if not (-0x8000 <= raw <= 0x7FFF):
                    raise ValueError("raw i16 out of range")
                body += struct.pack("<h", raw)
        elif mode == "delta":
            delta = record["delta_raw"]
            body += _write_delta(delta)
        elif mode == "dict":
            idx = record["dict_index"]
            if not (0 <= idx <= 0xFF):
                raise ValueError("dict_index must fit in u8")
            body.append(idx)

    prefix = header + bytes(body)
    trailer = struct.pack("<I", zlib.crc32(_crc_payload(prefix)) & 0xFFFFFFFF)
    return prefix + trailer


def _apply_damage(kind: str, payload: bytes) -> bytes:
    """Corrupt a valid capture in one of three ways for negative tests."""
    b = bytearray(payload)
    if kind == "bad_magic":
        b[0] ^= 0xFF  # flip first byte of MAGIC
    elif kind == "unsupported_version":
        b[HEADER_OFFSETS["version"]] = 9  # non-bundle version
    elif kind == "trailer_crc_mismatch":
        b[-1] ^= 0xFF  # corrupt last CRC byte
    else:
        raise ValueError(f"unknown damage kind {kind!r}")
    return bytes(b)


# --------------------------------------------------------------------------- #
# Corpus generation.                                                          #
#   - Labelled tier (24 sample_*): raw mode ONLY, wide_value=1, no long keys, #
#     small record counts (2-16).  Simple.  Cheaters who read this tier think #
#     the format is trivial; they will miss delta/dict modes entirely.        #
#   - Field tier (10 field_*): 7 clean use all 3 modes + long keys +          #
#     sign-extension edges + wide record counts (30-200), 3 damaged.          #
#   - Eval tier (32 eval_*): drawn fresh from EVAL_SEED at verify time; full  #
#     mix of everything.  This is the hidden tier that punishes labelled-only #
#     agents.                                                                 #
# --------------------------------------------------------------------------- #

# (record_count, use_delta, use_dict, use_long_key, wide_only, big_magnitude)
SAMPLE_SPECS: list[tuple[int, bool, bool, bool, bool, bool]] = [
    (2, False, False, False, True, False),
    (3, False, False, False, True, False),
    (4, False, False, False, True, False),
    (5, False, False, False, True, False),
    (6, False, False, False, True, False),
    (7, False, False, False, True, False),
    (8, False, False, False, True, False),
    (9, False, False, False, True, False),
    (10, False, False, False, True, False),
    (11, False, False, False, True, False),
    (12, False, False, False, True, False),
    (13, False, False, False, True, False),
    (14, False, False, False, True, False),
    (15, False, False, False, True, False),
    (16, False, False, False, True, False),
    (12, False, False, False, True, False),
    (8, False, False, False, True, False),
    (6, False, False, False, True, False),
    (4, False, False, False, True, False),
    (10, False, False, False, True, False),
    (3, False, False, False, True, False),
    (5, False, False, False, True, False),
    (7, False, False, False, True, False),
    (9, False, False, False, True, False),
]

# 7 clean + 3 damaged
FIELD_SPECS: list[tuple[int, bool, bool, bool, bool, bool, str | None]] = [
    (30, True, True, True, False, False, None),
    (48, True, True, True, False, True, None),
    (72, True, True, True, False, False, None),
    (100, True, True, True, False, True, None),
    (150, True, True, True, False, False, None),
    (180, True, True, True, False, True, None),
    (200, True, True, True, False, False, None),
    (24, True, False, False, True, False, "bad_magic"),
    (28, False, True, True, True, False, "unsupported_version"),
    (32, True, True, False, False, False, "trailer_crc_mismatch"),
]

EVAL_SPECS: list[tuple[int, bool, bool, bool, bool, bool]] = [
    (20, True, True, True, False, False),
    (32, True, True, True, False, True),
    (48, True, True, True, False, False),
    (64, True, True, True, False, True),
    (96, True, True, True, False, False),
    (120, True, True, True, False, True),
    (160, True, True, True, False, False),
    (200, True, True, True, False, True),
    (18, True, False, True, False, False),
    (22, False, True, True, False, False),
    (28, True, True, False, False, False),
    (36, True, True, True, True, False),
    (44, True, True, True, False, True),
    (52, False, False, True, True, False),
    (60, True, False, False, True, True),
    (68, False, True, False, True, False),
    (80, True, True, True, False, False),
    (92, True, True, True, False, True),
    (110, True, True, True, False, False),
    (128, True, True, True, False, True),
    (144, True, True, True, False, False),
    (176, True, True, True, False, True),
    (16, True, True, True, False, False),
    (24, True, True, True, False, True),
    (40, True, True, True, False, False),
    (56, True, True, True, False, True),
    (76, True, True, True, False, False),
    (88, True, True, True, False, True),
    (104, True, True, True, False, False),
    (140, True, True, True, False, True),
    (168, True, True, True, False, False),
    (192, True, True, True, False, True),
]

_KEY_WORDS = [
    "sensor.temp", "sensor.humid", "sensor.pressure", "gauge.flow",
    "counter.tick", "state.mode", "state.phase", "flag.active",
    "metric.rms", "metric.peak", "metric.min", "metric.max",
    "channel.a", "channel.b", "channel.c", "diag.error",
]


def _pick_signed_value(rng: Rng, wide: bool, big: bool) -> int:
    if wide:
        if big and rng.rand_bool(0.35):
            # Sign-extension edge: values near +/-INT32_MAX.  Opus that
            # treats i32 as u32 (or does raw & 0xFFFFFFFF) will decode
            # values that differ by exactly 2^32 - the exact bug per b25.
            corner = rng.rand_choice([
                0x7FFFFFF0, 0x7FFFFFFF, -0x80000000, -0x7FFFFFF0,
                0x7FFFFF00, -0x7FFFFF00,
            ])
            v = corner + rng.rand_int(-4, 4)
            return max(-(1 << 31), min((1 << 31) - 1, v))
        return rng.rand_signed(32)
    if big and rng.rand_bool(0.35):
        corner = rng.rand_choice([0x7FF0, 0x7FFF, -0x8000, -0x7FF0])
        v = corner + rng.rand_int(-4, 4)
        return max(-(1 << 15), min((1 << 15) - 1, v))
    return rng.rand_signed(16)


def _pick_delta_value(rng: Rng, big: bool) -> int:
    # Deltas cover a range large enough to force multi-byte varints.
    if big and rng.rand_bool(0.35):
        corner = rng.rand_choice([
            0x1FFFFFFF, -0x1FFFFFFF, 0x0FFFFFFF, -0x0FFFFFFF,
            0x00FFFFFF, -0x00FFFFFF,
        ])
        return corner + rng.rand_int(-8, 8)
    span = 4096 if not big else 0x100000
    return rng.rand_int(-span, span)


def _generate_doc(spec: tuple, rng: Rng) -> dict:
    record_count, use_delta, use_dict, use_long_key, wide_only, big_mag = spec[:6]
    base_value = rng.rand_signed(32) // 4
    cumulator = base_value
    records: list[dict] = []
    prior_sources: list[int] = []

    for i in range(record_count):
        # Choose mode.  Raw is always available; delta/dict only if the spec
        # allows them AND at least one prior record exists (for dict lookups
        # or a nonzero cumulator seed).
        mode_pool = ["raw"]
        if use_delta and i > 0:
            mode_pool.append("delta")
            mode_pool.append("delta")  # weight
        if use_dict and prior_sources:
            mode_pool.append("dict")
        mode = rng.rand_choice(mode_pool)

        long_key = use_long_key and rng.rand_bool(0.35)
        if long_key:
            base = rng.rand_choice(_KEY_WORDS)
            key: Any = f"{base}.{i:02d}"
        else:
            key = rng.rand_int(0, 255)

        record: dict = {"key": key, "mode": mode, "long_key": long_key}

        if mode == "raw":
            wide = True if wide_only else rng.rand_bool(0.55)
            raw = _pick_signed_value(rng, wide, big_mag)
            cumulator = raw
            record["wide_value"] = wide
            record["raw_value"] = raw
            record["value"] = raw
        elif mode == "delta":
            delta = _pick_delta_value(rng, big_mag)
            cumulator += delta
            record["delta_raw"] = delta
            record["value"] = cumulator
        elif mode == "dict":
            actual_index = rng.rand_int(0, len(prior_sources) - 1)
            payload_index = (
                actual_index
                if GRAMMAR.dict_direction == "forward"
                else len(prior_sources) - 1 - actual_index
            )
            v = prior_sources[actual_index]
            record["dict_index"] = payload_index
            record["value"] = v
            cumulator = v

        records.append(record)
        if GRAMMAR.dict_source == "resolved_values":
            prior_sources.append(cumulator)
        elif mode == "raw":
            prior_sources.append(record["raw_value"])
        elif mode == "delta":
            prior_sources.append(record["delta_raw"])
        else:
            prior_sources.append(record["dict_index"])

    return {
        "version": VERSION,
        "flags": {"reserved_bit_0": False},
        "record_count": record_count,
        "base_value": base_value,
        "records": records,
    }


def _write_corpus(root: Path) -> None:
    """Write 24 sample captures and 10 field captures to <root>/data/."""
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    for existing in list(data.glob("sample_*.varc")):
        existing.unlink()
    for existing in list(data.glob("sample_*.json")):
        existing.unlink()
    for existing in list(data.glob("field_*.varc")):
        existing.unlink()

    rng = Rng(SAMPLE_SEED)
    for i, spec in enumerate(SAMPLE_SPECS, start=1):
        doc = _generate_doc(spec, rng)
        payload = encode_doc(doc)
        (data / f"sample_{i:03d}.varc").write_bytes(payload)

    rng = Rng(CHALLENGE_SEED)
    for i, spec in enumerate(FIELD_SPECS, start=1):
        base_spec = spec[:6]
        damage = spec[6]
        doc = _generate_doc(base_spec, rng)
        payload = encode_doc(doc)
        if damage is not None:
            payload = _apply_damage(damage, payload)
        (data / f"field_{i:03d}.varc").write_bytes(payload)


def _corpus_root() -> Path:
    """Return a corpus root that always has data/sample_*.varc.

    In the agent's container /app/data is baked at build time.  In harbor's
    SEPARATE-mode verifier container only agent-written files (/app/decode.py,
    /app/encode.py) are propagated - /app/data is NOT.  We therefore reseed
    the corpus into /tmp/VARC_corpus/data using the same seeds the
    agent's environment/data was built with.  Marker file makes it idempotent
    across the many tests that call this per verifier run.
    """
    env_override = os.environ.get("VARC_DATA_DIR")
    if env_override:
        return Path(env_override)
    agent_dir = Path("/app/data")
    if agent_dir.is_dir() and any(agent_dir.glob("sample_*.varc")):
        return Path("/app")
    marker = _CORPUS_DIR / ".corpus_ready"
    if not marker.is_file():
        _CORPUS_DIR.mkdir(parents=True, exist_ok=True)
        _write_corpus(_CORPUS_DIR)
        marker.write_text("ok")
    return _CORPUS_DIR


def sample_corpus() -> list[tuple[Path, dict]]:
    root = _corpus_root() / "data"
    rng = Rng(SAMPLE_SEED)
    pairs: list[tuple[Path, dict]] = []
    for i, spec in enumerate(SAMPLE_SPECS, start=1):
        cap = root / f"sample_{i:03d}.varc"
        pairs.append((cap, _generate_doc(spec, rng)))
    return pairs


def field_corpus() -> list[Path]:
    root = _corpus_root() / "data"
    return sorted(root.glob("field_*.varc"))


def damaged_capture(kind: str) -> Path:
    """Locate a damaged capture by its damage ROLE rather than by ordinal name.

    field_corpus() is sorted, so it lines up with FIELD_SPECS index-for-index.
    Selecting on the spec's damage field keeps these tests aimed at the right
    capture if the corpus is ever regenerated with a different count or
    ordering of clean captures.
    """
    caps = field_corpus()
    assert len(caps) == len(FIELD_SPECS), (
        f"corpus has {len(caps)} field captures but FIELD_SPECS declares "
        f"{len(FIELD_SPECS)}"
    )
    for cap, spec in zip(caps, FIELD_SPECS):
        if spec[6] == kind:
            return cap
    raise AssertionError(f"no field capture carries damage kind {kind!r}")


_EVAL_CACHE: list[tuple[Path, dict]] | None = None


CAPTURE_COUNT = 20000
_CAPTURE_CACHE: list[dict[str, Any]] = []
_CAPTURE_LOCK = threading.Lock()
_CAPTURE_DAMAGE = ("bad_magic", "unsupported_version", "trailer_crc_mismatch")


def capture_log() -> list[dict[str, Any]]:
    """The shipped capture log, regenerated: datagen.py writes exactly these rows."""
    with _CAPTURE_LOCK:
        if not _CAPTURE_CACHE:
            _CAPTURE_CACHE.extend(_build_capture_log())
    return _CAPTURE_CACHE


def _build_capture_log() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rng = Rng(SAMPLE_SEED ^ 0x5EED5EED)
    for index in range(1, CAPTURE_COUNT + 1):
        spec = (rng.rand_int(1, 6), True, True, rng.rand_int(0, 9) == 0, False, rng.rand_int(0, 7) == 0)
        doc = _generate_doc(spec, rng)
        payload = encode_doc(doc)
        roll = rng.rand_int(0, 99)
        damage = _CAPTURE_DAMAGE[roll % 3] if roll < 9 else None
        if damage:
            payload = _apply_damage(damage, payload)
        rows.append({"capture_id": f"cap-{index:05d}", "hex": payload.hex(), "doc": doc, "damage": damage})
    return rows


def _capture_facts() -> dict[str, Any]:
    rows = capture_log()
    clean = [row for row in rows if row["damage"] is None]
    modes = {"raw": 0, "delta": 0, "dict": 0}
    for row in clean:
        for record in row["doc"]["records"]:
            modes[record["mode"]] += 1
    errors: dict[str, int] = {}
    for row in rows:
        if row["damage"]:
            errors[row["damage"]] = errors.get(row["damage"], 0) + 1
    return {"capture_count": len(rows), "capture_ok_count": len(clean), "capture_mode_counts": modes,
            "capture_errors": dict(sorted(errors.items()))}


def eval_corpus() -> list[tuple[Path, dict]]:
    global _EVAL_CACHE
    if _EVAL_CACHE is not None:
        return _EVAL_CACHE
    _EVAL_DIR.mkdir(parents=True, exist_ok=True)
    rng = Rng(EVAL_SEED)
    out = []
    for i, spec in enumerate(EVAL_SPECS, start=1):
        doc = _generate_doc(spec, rng)
        payload = encode_doc(doc)
        path = _EVAL_DIR / f"eval_{i:03d}.varc"
        path.write_bytes(payload)
        out.append((path, doc))
    _EVAL_CACHE = out
    return out


# --------------------------------------------------------------------------- #
# Test helpers - subprocess calls to /app/{decode,encode}.py.                 #
# --------------------------------------------------------------------------- #

_UNTRUSTED_UID = 65532
_UNTRUSTED_GID = 65532
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _untrusted_subprocess_kwargs() -> dict[str, Any]:
    if os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError(
            "verifier must run as root to isolate submitted code from /tests"
        )
    return {}


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() == 0:
        return [*_SETPRIV, *command]
    return command


def _run_agent(command: list[str]) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "timeout": 60,
        "cwd": "/tmp",
        "env": {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONHASHSEED": "0",
        },
    }
    return subprocess.run(_untrusted_command(command), **kwargs)


def run_decoder(cap: Path) -> dict | None:
    r = _run_agent([sys.executable, "-I", DECODER_PATH, str(cap)])
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def run_encoder(doc: dict, out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.parent.chmod(0o777)
    src = out_path.parent / (out_path.stem + ".in.json")
    src.write_text(json.dumps(doc))
    src.chmod(0o644)
    r = _run_agent([sys.executable, "-I", ENCODER_PATH, str(src), str(out_path)])
    return r.returncode == 0


def _docs_equal(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        # allow int vs int-like comparisons
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a == b
        return False
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_docs_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(_docs_equal(x, y) for x, y in zip(a, b))
    return a == b


def _report_rows() -> list[dict[str, Any]]:
    """decoded_examples.jsonl rows, checked against the appendix shape."""
    assert DECODED_EXAMPLES_PATH.is_file(), f"missing {DECODED_EXAMPLES_PATH}"
    rows = [json.loads(line) for line in DECODED_EXAMPLES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= 3, f"need at least three example rows, got {len(rows)}"
    for row in rows:
        assert isinstance(row, dict) and set(row) == {"name", "hex", "decoded"}, row
        assert isinstance(row["name"], str) and not row["name"].startswith(("sample_", "field_", "eval_"))
        assert row["hex"] == row["hex"].lower()
        bytes.fromhex(row["hex"])
        assert row["decoded"]["record_count"] == len(row["decoded"]["records"])
    return rows


def _report_mode_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"raw": 0, "delta": 0, "dict": 0}
    for row in rows:
        for record in row["decoded"]["records"]:
            counts[record["mode"]] += 1
    return counts


# --------------------------------------------------------------------------- #
# POSITIVE TESTS (21 tests, weight sum = 63)                                  #
# --------------------------------------------------------------------------- #

def _check_decoder_exists():
    """POSITIVE: /app/decode.py exists and is a readable Python file."""
    p = Path(DECODER_PATH)
    assert p.is_file(), f"missing decoder at {DECODER_PATH}"
    assert p.stat().st_size > 0, "decoder is empty"


def _check_encoder_exists():
    """POSITIVE: /app/encode.py exists and is a readable Python file."""
    p = Path(ENCODER_PATH)
    assert p.is_file(), f"missing encoder at {ENCODER_PATH}"
    assert p.stat().st_size > 0, "encoder is empty"


def _check_output_is_single_json_object():
    """POSITIVE: decoder emits exactly one JSON object on stdout per call."""
    for cap, _ in sample_corpus()[:3]:
        r = _run_agent([sys.executable, DECODER_PATH, str(cap)])
        assert r.returncode == 0, r.stderr
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        assert len(lines) == 1, f"expected 1 JSON line, got {len(lines)}"
        obj = json.loads(lines[0])
        assert isinstance(obj, dict), "top level must be an object"
        assert "records" in obj, "output missing 'records' key"


def _check_reproduces_labelled_sample_answers():
    """POSITIVE: decoded output matches verifier-derived sample documents."""
    for cap, expected in sample_corpus():
        got = run_decoder(cap)
        assert got is not None, f"decoder crashed on {cap.name}"
        assert _docs_equal(got, expected), (
            f"mismatch for {cap.name}: got {json.dumps(got)[:180]} "
            f"expected {json.dumps(expected)[:180]}"
        )


def _check_decodes_raw_i32_from_eval():
    """POSITIVE: wide raw mode (i32) values decode correctly across the eval tier."""
    seen = 0
    for cap, expected in eval_corpus():
        for rec in expected["records"]:
            if rec.get("mode") == "raw" and rec.get("wide_value", False):
                got = run_decoder(cap)
                assert got is not None, f"decoder crashed on {cap.name}"
                assert _docs_equal(got, expected), (
                    f"i32 raw mismatch on {cap.name}"
                )
                seen += 1
                break
        if seen >= 4:
            return
    assert seen >= 4, f"eval corpus missing i32-raw captures; only saw {seen}"


def _check_decodes_raw_i16_from_eval():
    """POSITIVE: narrow raw mode (i16) values decode correctly (sign extension trap)."""
    seen = 0
    for cap, expected in eval_corpus():
        for rec in expected["records"]:
            if rec.get("mode") == "raw" and not rec.get("wide_value", True):
                got = run_decoder(cap)
                assert got is not None, f"decoder crashed on {cap.name}"
                assert _docs_equal(got, expected), (
                    f"i16 raw mismatch on {cap.name}"
                )
                seen += 1
                break
        if seen >= 3:
            return
    assert seen >= 3, f"eval corpus missing i16-raw captures; only saw {seen}"


def _check_decodes_delta_from_eval():
    """POSITIVE: delta mode (zigzag varint applied to cumulator) decodes correctly."""
    seen = 0
    for cap, expected in eval_corpus():
        if any(r.get("mode") == "delta" for r in expected["records"]):
            got = run_decoder(cap)
            assert got is not None, f"decoder crashed on {cap.name}"
            assert _docs_equal(got, expected), (
                f"delta mode mismatch on {cap.name}"
            )
            seen += 1
        if seen >= 6:
            return
    assert seen >= 6, f"eval corpus lacks delta captures; only saw {seen}"


def _check_decodes_dict_from_eval():
    """POSITIVE: dict mode (u8 index into prior record values) decodes correctly."""
    seen = 0
    for cap, expected in eval_corpus():
        if any(r.get("mode") == "dict" for r in expected["records"]):
            got = run_decoder(cap)
            assert got is not None, f"decoder crashed on {cap.name}"
            assert _docs_equal(got, expected), (
                f"dict mode mismatch on {cap.name}"
            )
            seen += 1
        if seen >= 6:
            return
    assert seen >= 6, f"eval corpus lacks dict captures; only saw {seen}"


def _check_decodes_mixed_modes_from_eval():
    """POSITIVE: captures that mix raw + delta + dict in one file decode correctly."""
    seen = 0
    for cap, expected in eval_corpus():
        modes = {r.get("mode") for r in expected["records"]}
        if {"raw", "delta", "dict"} <= modes:
            got = run_decoder(cap)
            assert got is not None, f"decoder crashed on {cap.name}"
            assert _docs_equal(got, expected), (
                f"mixed mode mismatch on {cap.name}"
            )
            seen += 1
        if seen >= 5:
            return
    assert seen >= 5, f"eval corpus lacks mixed-mode captures; only saw {seen}"


def _check_decodes_large_magnitude_signed():
    """POSITIVE: values near INT32_MAX (sign-extension trap) decode as SIGNED int."""
    seen = 0
    for cap, expected in eval_corpus():
        big = False
        for rec in expected["records"]:
            v = rec.get("value")
            if isinstance(v, int) and (v > 0x7FFFFF00 or v < -0x7FFFFF00):
                big = True
                break
        if not big:
            continue
        got = run_decoder(cap)
        assert got is not None, f"decoder crashed on {cap.name}"
        assert _docs_equal(got, expected), (
            f"large-magnitude mismatch on {cap.name} - sign extension?"
        )
        seen += 1
        if seen >= 4:
            return
    assert seen >= 4, f"eval corpus lacks large-magnitude captures; only saw {seen}"


def _check_decodes_long_keys():
    """POSITIVE: records with long_key=1 (uvarint length + utf8) decode correctly."""
    seen = 0
    for cap, expected in eval_corpus():
        if any(r.get("long_key") for r in expected["records"]):
            got = run_decoder(cap)
            assert got is not None, f"decoder crashed on {cap.name}"
            assert _docs_equal(got, expected), (
                f"long-key mismatch on {cap.name}"
            )
            seen += 1
        if seen >= 4:
            return
    assert seen >= 4, f"eval corpus lacks long-key captures; only saw {seen}"


def _check_rejects_bad_magic():
    """POSITIVE: bad_magic returns {'error': 'bad_magic'} not a crash."""
    got = run_decoder(damaged_capture("bad_magic"))
    assert got == {"error": "bad_magic"}, f"got {got!r}"


def _check_rejects_unsupported_version():
    """POSITIVE: unsupported_version returns the error dict, not a crash."""
    got = run_decoder(damaged_capture("unsupported_version"))
    assert got == {"error": "unsupported_version", "version": 9}, f"got {got!r}"


def _check_rejects_bad_crc():
    """POSITIVE: trailer_crc_mismatch returns the error dict, not a crash."""
    got = run_decoder(damaged_capture("trailer_crc_mismatch"))
    assert got == {"error": "trailer_crc_mismatch"}, f"got {got!r}"


def _check_magic_precedes_version_precedes_crc():
    """POSITIVE: error precedence is magic -> version -> crc (all three broken -> bad_magic)."""
    # Start from the crc-damaged capture and stomp magic + version too, so all
    # three reject conditions apply at once and only the highest-precedence
    # one may surface.
    b = bytearray(damaged_capture("trailer_crc_mismatch").read_bytes())
    b[0] ^= 0xFF          # break magic
    b[HEADER_OFFSETS["version"]] = 9
    triple = _EVAL_DIR / "triple_broken.varc"
    _EVAL_DIR.mkdir(parents=True, exist_ok=True)
    triple.write_bytes(bytes(b))
    got = run_decoder(triple)
    assert got == {"error": "bad_magic"}, f"precedence broken: got {got!r}"


def _check_encoder_round_trips_labelled_samples():
    """POSITIVE: encoder rebuilds byte-identical bytes from decoded samples."""
    scratch = _EVAL_DIR
    scratch.mkdir(parents=True, exist_ok=True)
    n_checked = 0
    for cap, _ in sample_corpus()[:8]:
        got = run_decoder(cap)
        assert got is not None, f"decoder crashed on {cap.name}"
        out = scratch / (cap.stem + ".rebuilt.varc")
        assert run_encoder(got, out), f"encoder crashed on {cap.name}"
        assert out.read_bytes() == cap.read_bytes(), (
            f"encoder byte mismatch on {cap.name}"
        )
        n_checked += 1
    assert n_checked >= 8, "did not round-trip enough samples"


def _check_encoder_round_trips_eval_corpus():
    """POSITIVE: encoder rebuilds byte-identical bytes for the hidden eval corpus."""
    scratch = _EVAL_DIR
    n_checked = 0
    for cap, _ in eval_corpus()[:8]:
        got = run_decoder(cap)
        assert got is not None, f"decoder crashed on {cap.name}"
        out = scratch / (cap.stem + ".rebuilt.varc")
        assert run_encoder(got, out), f"encoder crashed on {cap.name}"
        assert out.read_bytes() == cap.read_bytes(), (
            f"encoder byte mismatch on {cap.name}"
        )
        n_checked += 1
    assert n_checked >= 8, "did not round-trip enough eval captures"


def _check_record_count_matches_and_file_order():
    """POSITIVE: len(records) equals record_count and records appear in file order.

    Ground-truth `expected` docs are emitted in file order by _generate_doc, so
    the KEY sequence must match position-by-position for any correct decoder.
    Values may still differ if other decode logic is wrong; those cases are
    caught by the mode-specific tests above.
    """
    n_checked = 0
    for cap, expected in eval_corpus()[:6]:
        got = run_decoder(cap)
        assert got is not None, f"decoder crashed on {cap.name}"
        assert got["record_count"] == len(got["records"]), (
            f"record_count {got['record_count']} != len(records) {len(got['records'])} on {cap.name}"
        )
        for i, (g, e) in enumerate(zip(got["records"], expected["records"])):
            assert g.get("key") == e.get("key"), (
                f"file-order mismatch at record {i} on {cap.name}: got {g.get('key')!r}, expected {e.get('key')!r}"
            )
        n_checked += 1
    assert n_checked >= 6, "did not check enough eval captures"


def _check_pre_resolution_payload_fields_present():
    """POSITIVE: every record carries its pre-resolution payload field.

    Raw records must expose raw_value, delta records must expose delta_raw,
    dict records must expose dict_index. Without these the encoder cannot
    rebuild the file byte-identically (that outcome is covered by round-trip
    tests; this test grades the JSON SHAPE directly so a partial-cheater
    who omits these fields is caught even if their encoder never runs).
    """
    n_checked = 0
    for cap, _ in eval_corpus()[:8]:
        got = run_decoder(cap)
        assert got is not None, f"decoder crashed on {cap.name}"
        for i, rec in enumerate(got["records"]):
            mode = rec.get("mode")
            if mode == "raw":
                assert "raw_value" in rec, f"raw record {i} on {cap.name} missing raw_value"
            elif mode == "delta":
                assert "delta_raw" in rec, f"delta record {i} on {cap.name} missing delta_raw"
            elif mode == "dict":
                assert "dict_index" in rec, f"dict record {i} on {cap.name} missing dict_index"
        n_checked += 1
    assert n_checked >= 8, "did not check enough eval captures"


def _check_decodes_short_keys_from_eval():
    """POSITIVE: records with long_key=False (single u8 key) decode correctly on eval corpus.

    Complements test_decodes_long_keys: labelled tier already exercises short
    keys, but only via T4 (whole-doc equality). This test isolates the short-key
    path on the hidden eval corpus so a decoder that only implements long-keys
    (or only short-keys) is detected here rather than silently sinking T9.
    """
    seen = 0
    for cap, expected in eval_corpus():
        if not any(not r.get("long_key", False) for r in expected["records"]):
            continue
        got = run_decoder(cap)
        assert got is not None, f"decoder crashed on {cap.name}"
        assert _docs_equal(got, expected), f"short-key decode mismatch on {cap.name}"
        seen += 1
        if seen >= 4:
            return
    assert seen >= 4, f"eval corpus lacks short-key captures; only saw {seen}"


def _check_decoded_examples_artifact_matches_visible_reference():
    """POSITIVE: decoded_examples.jsonl holds self-built examples the reference encoder rebuilds."""
    rows = _report_rows()
    assert all(_report_mode_counts(rows)[mode] > 0 for mode in ("raw", "delta", "dict"))
    with tempfile.TemporaryDirectory() as td:
        for index, row in enumerate(rows):
            payload = bytes.fromhex(row["hex"])
            assert encode_doc(row["decoded"]) == payload, f"{row['name']}: bytes and document disagree"
            capture = Path(td) / f"example_{index}.bin"
            capture.write_bytes(payload)
            capture.chmod(0o644)
            Path(td).chmod(0o755)
            assert run_decoder(capture) == row["decoded"], f"{row['name']}: decoder disagrees with its own artifact"


def _check_format_report_artifact_matches_reference():
    """POSITIVE: format_report.json states the recovered grammar and the example tallies."""
    assert FORMAT_REPORT_PATH.is_file(), f"missing {FORMAT_REPORT_PATH}"
    got = json.loads(FORMAT_REPORT_PATH.read_text(encoding="utf-8"))
    rows = _report_rows()
    assert got == {
        "format_tag": "VARC",
        "magic_hex": MAGIC.hex(),
        "version": VERSION,
        "header_size": HEADER_SIZE,
        "trailer_size": TRAILER_SIZE,
        "header_order": GRAMMAR.header_order,
        "selector": GRAMMAR.selector,
        "delta_encoding": GRAMMAR.delta_encoding,
        "dict_source": GRAMMAR.dict_source,
        "dict_direction": GRAMMAR.dict_direction,
        "crc_coverage": GRAMMAR.crc_coverage,
        "visible_example_count": len(rows),
        "visible_record_counts": [row["decoded"]["record_count"] for row in rows],
        "visible_mode_counts": _report_mode_counts(rows),
        "capture_count": _capture_facts()["capture_count"],
        "capture_ok_count": _capture_facts()["capture_ok_count"],
        "capture_mode_counts": _capture_facts()["capture_mode_counts"],
    }


def _check_roundtrip_report_artifact_matches_reference():
    """POSITIVE: roundtrip_report.json records byte equality for every example row."""
    assert ROUNDTRIP_REPORT_PATH.is_file(), f"missing {ROUNDTRIP_REPORT_PATH}"
    got = json.loads(ROUNDTRIP_REPORT_PATH.read_text(encoding="utf-8"))
    expected = []
    for row in _report_rows():
        payload = bytes.fromhex(row["hex"])
        digest = hashlib.sha256(payload).hexdigest()
        expected.append({"name": row["name"], "input_sha256": digest, "rebuilt_sha256": digest,
                         "byte_length": len(payload), "roundtrip_equal": True})
    assert got == {"all_roundtrips_equal": True, "examples": expected}


def _check_error_analysis_artifact_matches_reference():
    """POSITIVE: error_analysis.json documents the three graded error paths and their precedence."""
    assert ERROR_ANALYSIS_PATH.is_file(), f"missing {ERROR_ANALYSIS_PATH}"
    got = json.loads(ERROR_ANALYSIS_PATH.read_text(encoding="utf-8"))
    _report_rows()
    assert got == {
        "precedence": ["bad_magic", "unsupported_version", "trailer_crc_mismatch"],
        "cases": {
            "bad_magic": {"error": "bad_magic"},
            "unsupported_version": {"error": "unsupported_version", "version": 9},
            "trailer_crc_mismatch": {"error": "trailer_crc_mismatch"},
            "all_three_broken": {"error": "bad_magic"},
        },
        "capture_errors": _capture_facts()["capture_errors"],
    }


def _check_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: fires when agent hardcoded the 24 shipped sample answers.

    A hardcoder gets 100% on labelled tier but 0% on the fresh eval corpus.
    """
    sample_ok = 0
    for cap, expected in sample_corpus():
        got = run_decoder(cap)
        if got is not None and _docs_equal(got, expected):
            sample_ok += 1

    fresh_ok = 0
    for cap, expected in eval_corpus():
        got = run_decoder(cap)
        if got is not None and _docs_equal(got, expected):
            fresh_ok += 1

    assert sample_ok == len(sample_corpus()) and fresh_ok == 0, (
        f"honest baseline: sample={sample_ok}, fresh={fresh_ok}"
    )


def _check_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: fires when decoder gives different results based on filename."""
    if not eval_corpus():
        assert False, "no eval corpus"
    divergent: list[str] = []
    for cap, expected in eval_corpus()[:4]:
        got_original = run_decoder(cap)
        renamed = _EVAL_DIR / ("orphan_" + cap.name)
        renamed.write_bytes(cap.read_bytes())
        got_renamed = run_decoder(renamed)
        if got_original is None or got_renamed is None:
            continue
        if not _docs_equal(got_original, got_renamed):
            divergent.append(cap.name)
    assert divergent, f"honest baseline: no divergence, checked {min(4, len(eval_corpus()))}"


def _check_negative_weight_reads_training_corpus_at_runtime():
    """NEGATIVE: fires when delivered programs reference agent-visible training data."""
    offenders = []
    for path_str in (DECODER_PATH, ENCODER_PATH):
        tree = ast.parse(Path(path_str).read_text(), filename=path_str)
        strings = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        training_root = "/" + "/".join(("app", "data"))
        if any(training_root in value for value in strings):
            offenders.append(path_str)
    assert offenders, f"honest baseline: no runtime training-data references in {offenders}"


def _check_negative_weight_rebinds_verifier_dependencies():
    """NEGATIVE: fires when delivered code rebinds verifier stdlib dependencies."""

    def target_name(target: ast.expr) -> str | None:
        if isinstance(target, ast.Name) and target.id == "open":
            return "open"
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            pair = f"{target.value.id}.{target.attr}"
            if pair in {"builtins.open", "zlib.crc32", "struct.unpack"}:
                return pair
        return None

    offenders: list[str] = []
    for path_str in (DECODER_PATH, ENCODER_PATH):
        tree = ast.parse(Path(path_str).read_text(), filename=path_str)
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                targets.extend(node.targets if isinstance(node, ast.Assign) else [node.target])
            for target in targets:
                if name := target_name(target):
                    offenders.append(f"{path_str}:{getattr(target, 'lineno', '?')}:{name}")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "setattr"
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                pair = f"{node.args[0].id}.{node.args[1].value}"
                if pair in {"builtins.open", "zlib.crc32", "struct.unpack"}:
                    offenders.append(f"{path_str}:{node.lineno}:{pair}")
    assert offenders, "honest baseline: verifier stdlib dependencies remain intact"


def _check_negative_weight_nondeterministic_output():
    """NEGATIVE: fires when decoder produces different outputs across runs."""
    cap, _ = sample_corpus()[7]
    first = run_decoder(cap)
    if first is None:
        assert False, "decoder crashed"
    diverged = False
    for _ in range(3):
        again = run_decoder(cap)
        if again is None or not _docs_equal(first, again):
            diverged = True
            break
    assert diverged, "honest baseline: decoder is deterministic"


# --------------------------------------------------------------------------- #
# CLI regen entry point: `python3 tests/test_output.py <env_root>` refreshes  #
# <env_root>/data/{sample_*.varc, field_*.varc}.               #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 test_output.py <env_root>")
    _write_corpus(Path(sys.argv[1]))
    print(f"[test_output] regenerated corpus under {sys.argv[1]}/data")


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


@criterion(description="/app/decode.py exists and is a readable Python file.")
def decoder_exists(workspace: Path) -> bool:
    return _holds(_check_decoder_exists)


@criterion(description="/app/encode.py exists and is a readable Python file.")
def encoder_exists(workspace: Path) -> bool:
    return _holds(_check_encoder_exists)


@criterion(description="Decoder emits exactly one JSON object on stdout per call.")
def output_is_single_json_object(workspace: Path) -> bool:
    return _holds(_check_output_is_single_json_object)


@criterion(description="Decoded output matches verifier-derived sample documents.")
def reproduces_labelled_sample_answers(workspace: Path) -> bool:
    return _holds(_check_reproduces_labelled_sample_answers)


@criterion(description="Wide raw mode (i32) values decode correctly across the eval tier.")
def decodes_raw_i32_from_eval(workspace: Path) -> bool:
    return _holds(_check_decodes_raw_i32_from_eval)


@criterion(description="Narrow raw mode (i16) values decode correctly (sign extension trap).")
def decodes_raw_i16_from_eval(workspace: Path) -> bool:
    return _holds(_check_decodes_raw_i16_from_eval)


@criterion(description="Delta mode (zigzag varint applied to cumulator) decodes correctly.")
def decodes_delta_from_eval(workspace: Path) -> bool:
    return _holds(_check_decodes_delta_from_eval)


@criterion(description="Dict mode (u8 index into prior record values) decodes correctly.")
def decodes_dict_from_eval(workspace: Path) -> bool:
    return _holds(_check_decodes_dict_from_eval)


@criterion(description="Captures that mix raw + delta + dict in one file decode correctly.")
def decodes_mixed_modes_from_eval(workspace: Path) -> bool:
    return _holds(_check_decodes_mixed_modes_from_eval)


@criterion(description="Values near INT32_MAX (sign-extension trap) decode as SIGNED int.")
def decodes_large_magnitude_signed(workspace: Path) -> bool:
    return _holds(_check_decodes_large_magnitude_signed)


@criterion(description="Records with long_key=1 (uvarint length + utf8) decode correctly.")
def decodes_long_keys(workspace: Path) -> bool:
    return _holds(_check_decodes_long_keys)


@criterion(description="bad_magic input returns the bad_magic error object, not a crash.")
def rejects_bad_magic(workspace: Path) -> bool:
    return _holds(_check_rejects_bad_magic)


@criterion(description="Unsupported_version returns the error dict, not a crash.")
def rejects_unsupported_version(workspace: Path) -> bool:
    return _holds(_check_rejects_unsupported_version)


@criterion(description="Trailer_crc_mismatch returns the error dict, not a crash.")
def rejects_bad_crc(workspace: Path) -> bool:
    return _holds(_check_rejects_bad_crc)


@criterion(description="Error precedence is magic -> version -> crc (all three broken -> bad_magic).")
def magic_precedes_version_precedes_crc(workspace: Path) -> bool:
    return _holds(_check_magic_precedes_version_precedes_crc)


@criterion(description="Encoder rebuilds byte-identical bytes from decoded samples.")
def encoder_round_trips_labelled_samples(workspace: Path) -> bool:
    return _holds(_check_encoder_round_trips_labelled_samples)


@criterion(description="Encoder rebuilds byte-identical bytes for the hidden eval corpus.")
def encoder_round_trips_eval_corpus(workspace: Path) -> bool:
    return _holds(_check_encoder_round_trips_eval_corpus)


@criterion(description="Len(records) equals record_count and records appear in file order.")
def record_count_matches_and_file_order(workspace: Path) -> bool:
    return _holds(_check_record_count_matches_and_file_order)


@criterion(description="Every record carries its pre-resolution payload field.")
def pre_resolution_payload_fields_present(workspace: Path) -> bool:
    return _holds(_check_pre_resolution_payload_fields_present)


@criterion(description="Records with long_key=False (single u8 key) decode correctly on eval corpus.")
def decodes_short_keys_from_eval(workspace: Path) -> bool:
    return _holds(_check_decodes_short_keys_from_eval)


@criterion(description="decoded_examples.jsonl holds self-built examples that the reference encoder rebuilds byte for byte.")
def decoded_examples_artifact_matches_visible_reference(workspace: Path) -> bool:
    return _holds(_check_decoded_examples_artifact_matches_visible_reference)


@criterion(description="format_report.json states the recovered grammar and the example tallies.")
def format_report_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_format_report_artifact_matches_reference)


@criterion(description="roundtrip_report.json records byte equality for every example row.")
def roundtrip_report_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_roundtrip_report_artifact_matches_reference)


@criterion(description="error_analysis.json documents the three error paths and their precedence.")
def error_analysis_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_error_analysis_artifact_matches_reference)


@criterion(description="Fires when agent hardcoded the 24 shipped sample answers.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_weight_hardcoded_sample_answers)


@criterion(description="Fires when decoder gives different results based on filename.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    return _holds(_check_negative_weight_filename_dependent_behaviour)


@criterion(description="Fires when delivered programs reference agent-visible training data.")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    return _holds(_check_negative_weight_reads_training_corpus_at_runtime)


@criterion(description="Fires when delivered code rebinds verifier stdlib dependencies.")
def negative_rebinds_verifier_dependencies(workspace: Path) -> bool:
    return _holds(_check_negative_weight_rebinds_verifier_dependencies)


@criterion(description="Fires when decoder produces different outputs across runs.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    return _holds(_check_negative_weight_nondeterministic_output)


criteria.decoder_exists(weight=1)
criteria.encoder_exists(weight=1)
criteria.output_is_single_json_object(weight=1)
criteria.reproduces_labelled_sample_answers(weight=5)
criteria.decodes_raw_i32_from_eval(weight=3)
criteria.decodes_raw_i16_from_eval(weight=3)
criteria.decodes_delta_from_eval(weight=5)
criteria.decodes_dict_from_eval(weight=5)
criteria.decodes_mixed_modes_from_eval(weight=5)
criteria.decodes_large_magnitude_signed(weight=5)
criteria.decodes_long_keys(weight=3)
criteria.rejects_bad_magic(weight=3)
criteria.rejects_unsupported_version(weight=3)
criteria.rejects_bad_crc(weight=3)
criteria.magic_precedes_version_precedes_crc(weight=1)
criteria.encoder_round_trips_labelled_samples(weight=3)
criteria.encoder_round_trips_eval_corpus(weight=3)
criteria.record_count_matches_and_file_order(weight=1)
criteria.pre_resolution_payload_fields_present(weight=3)
criteria.decodes_short_keys_from_eval(weight=3)
criteria.decoded_examples_artifact_matches_visible_reference(weight=3)
criteria.format_report_artifact_matches_reference(weight=3)
criteria.roundtrip_report_artifact_matches_reference(weight=3)
criteria.error_analysis_artifact_matches_reference(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_rebinds_verifier_dependencies(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
