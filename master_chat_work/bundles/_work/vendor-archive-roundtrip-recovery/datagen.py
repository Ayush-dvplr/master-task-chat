#!/usr/bin/env python3
"""Seeded generator for environment/data (NOT shipped). Uses WORK/ref_codec.py.

The verifier (tests/test_output.py) carries a verbatim copy of the schema
builders and the catalog builder, regenerating the same bytes from the same
seed, so shipped data and the verifier's expectation agree. Visible captures are
built so no lever's reflex reading is separable on them: every varint shortest,
revisions 0-3 are identity, no escapable byte at a body boundary, no in-band
frame damage, and every dict/delta reference stays inside one segment.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import ref_codec as rc

SEED = 284611
N_FIELDS = 2100
N_STREAMS = 40
N_CLEAN = 15200
N_REJECT = 2500
BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/vendor-archive-roundtrip-recovery")
DATA = BUNDLE / "environment" / "data"
MASK = (1 << 64) - 1
IDENTITY_REVS = [0, 1, 2, 3]
NONIDENTITY_REVS = [4, 5, 6, 7]
EXT_TYPES = {1: "span", 2: "quality", 3: "source"}
DAMAGE_KINDS = ["bad_magic", "unsupported_version", "reserved_not_zero",
                "record_count_overflow", "trailer_crc_mismatch"]
_UNITS = ["celsius", "pascal", "volt", "ampere", "hertz", "percent", "count", "meter"]
_BASES = ["temp", "pressure", "voltage", "current", "freq", "load", "ticks", "phase",
          "level", "flow", "rms", "peak", "humid", "angle", "speed", "power"]


class Rng:
    __slots__ = ("s",)

    def __init__(self, seed: int) -> None:
        self.s = seed & MASK or 0x9E3779B97F4A7C15

    def nxt(self) -> int:
        x = self.s
        x ^= (x >> 12) & MASK
        x ^= (x << 25) & MASK
        x ^= (x >> 27) & MASK
        self.s = x & MASK
        return (self.s * 0x2545F4914F6CDD1D) & MASK

    def rint(self, lo: int, hi: int) -> int:
        return lo + self.nxt() % (hi - lo + 1)

    def pick(self, seq):
        return seq[self.nxt() % len(seq)]


def build_field_layouts():
    rng = Rng(SEED ^ 0xF1E1D5)
    rows = []
    for cid in range(1, N_FIELDS + 1):
        name = f"{_BASES[cid % len(_BASES)]}_{cid:04d}"
        unit = _UNITS[rng.nxt() % len(_UNITS)]
        width = 4 if rng.nxt() % 2 else 2
        rows.append((cid, name, unit, width))
    return rows


def home_stream(cid: int) -> int:
    return (cid % N_STREAMS) + 1


def build_symbol_table(layouts):
    return [(home_stream(cid), cid, f"{name}@s{home_stream(cid)}")
            for (cid, name, unit, width) in layouts]


def build_revision_map():
    revisions = {rev: {} for rev in IDENTITY_REVS}
    for rev in NONIDENTITY_REVS:
        rng = Rng(SEED ^ (0xB0 + rev))
        revisions[rev] = {raw: rng.rint(1, N_FIELDS) for raw in range(1, 256)}
    return revisions


def build_schema():
    layouts = build_field_layouts()
    symrows = build_symbol_table(layouts)
    revisions = build_revision_map()
    schema = rc.empty_schema()
    schema["id_to_name"] = {cid: name for (cid, name, unit, width) in layouts}
    schema["name_to_id"] = {name: cid for (cid, name, unit, width) in layouts}
    schema["id_to_unit"] = {cid: unit for (cid, name, unit, width) in layouts}
    schema["alias"] = {(sid, cid): alias for (sid, cid, alias) in symrows}
    schema["remap"] = {(rev, raw): tgt for rev, mp in revisions.items() for raw, tgt in mp.items()}
    return schema, layouts, symrows, revisions


def _ext(rng):
    payload = bytes(rng.pick(_SAFE) for _ in range(rng.rint(1, 3)))
    return {"type": rng.pick([1, 2, 3, 7, 9]), "hex": payload.hex()}


_FORBIDDEN = (0xAA, 0x1B)
_SAFE = [b for b in range(0x80) if b not in _FORBIDDEN]


def _clean_bytes(data):
    return all(b not in _FORBIDDEN for b in data)


def _safe_raw(rng, wide):
    while True:
        v = rng.rint(-30000, 30000) if not wide else rng.rint(-2_000_000, 2_000_000)
        if _clean_bytes(struct.pack("<i" if wide else "<h", v)):
            return v


def _safe_delta(rng):
    while True:
        d = rng.rint(-400, 400)
        if _clean_bytes(rc.write_sleb128(d)):
            return d


def _safe_index(rng, hi):
    while True:
        i = rng.rint(0, hi)
        if i not in _FORBIDDEN:
            return i


def _make_capture(rng, stream_id, revision, want_names):
    records = []
    resolved = []
    cumulator = 0
    plan = [("long", nm) for nm in want_names] + [("short", None)] * rng.rint(0, 2)
    for slot, (kind, name) in enumerate(plan):
        if kind == "long":
            rec = {"raw_key": 0, "long_key": True, "key_str": name, "mode": "raw",
                   "wide": None, "ext_present": False, "extensions": []}
        else:
            rec = {"raw_key": rng.rint(1, 255), "long_key": False, "mode": "raw",
                   "wide": None, "ext_present": False, "extensions": []}
        mode = rng.pick(["raw", "delta", "dict"]) if resolved else rng.pick(["raw", "delta"])
        rec["mode"] = mode
        if rng.nxt() % 7 == 0:
            rec["ext_present"] = True
            rec["extensions"] = [_ext(rng)]
        if mode == "raw":
            wide = bool(rng.nxt() % 2)
            rec["wide"] = wide
            v = _safe_raw(rng, wide)
            rec["raw_value"] = v
            rec["value"] = v
            cumulator = v
            resolved.append(v)
        elif mode == "delta":
            d = _safe_delta(rng)
            rec["delta_raw"] = d
            rec["delta_raw_len"] = len(rc.write_sleb128(d))
            cumulator += d
            rec["value"] = cumulator
            resolved.append(cumulator)
        else:
            idx = _safe_index(rng, len(resolved) - 1)
            rec["dict_index"] = idx
            v = resolved[len(resolved) - 1 - idx]
            rec["value"] = v
            cumulator = v
            resolved.append(v)
        records.append(rec)
    if not records:
        records.append({"raw_key": 1, "long_key": False, "mode": "raw", "wide": False,
                        "raw_value": 0, "value": 0, "ext_present": False, "extensions": []})
    return {"stream_id": stream_id, "seq_no": 0, "revision": revision,
            "flags": {"stream_continues": False}, "record_count": len(records),
            "records": records}


def _apply_damage(kind, payload):
    b = bytearray(payload)
    if kind == "bad_magic":
        b[0] ^= 0xFF
    elif kind == "unsupported_version":
        b[5] = 9
    elif kind == "reserved_not_zero":
        b[14] = 1
    elif kind == "record_count_overflow":
        struct.pack_into("<H", b, 11, 0xFFFF)
    elif kind == "trailer_crc_mismatch":
        b[-1] ^= 0xFF
    return bytes(b)


def build_catalog():
    schema, layouts, symrows, revisions = build_schema()
    rng = Rng(SEED ^ 0x0C0FFEE)
    clean = []
    n = 0
    for (cid, name, unit, width) in layouts:
        hs = home_stream(cid)
        other = (hs % N_STREAMS) + 1
        for stream_id in (hs, other):
            n += 1
            doc = _make_capture(rng, stream_id, rng.pick(IDENTITY_REVS), [name])
            clean.append({"capture_id": f"cap-{n:05d}", "stream_id": stream_id,
                          "seq_no": 0, "revision": doc["revision"],
                          "hex": rc.encode_segment(doc).hex()})
    while n < len(layouts) * 2 + 1500:
        n += 1
        doc = _make_capture(rng, rng.rint(1, N_STREAMS), rng.pick(IDENTITY_REVS), [])
        clean.append({"capture_id": f"cap-{n:05d}", "stream_id": doc["stream_id"],
                      "seq_no": 0, "revision": doc["revision"], "hex": rc.encode_segment(doc).hex()})
    names_all = [name for (_c, name, _u, _w) in layouts]
    while n < N_CLEAN:
        n += 1
        pick = [names_all[rng.nxt() % len(names_all)] for _ in range(rng.rint(1, 3))]
        doc = _make_capture(rng, rng.rint(1, N_STREAMS), rng.pick(IDENTITY_REVS), pick)
        clean.append({"capture_id": f"cap-{n:05d}", "stream_id": doc["stream_id"],
                      "seq_no": 0, "revision": doc["revision"], "hex": rc.encode_segment(doc).hex()})
    reject = []
    rrng = Rng(SEED ^ 0xDEAD77)
    for i in range(1, N_REJECT + 1):
        doc = _make_capture(rrng, rrng.rint(1, N_STREAMS), rrng.pick(IDENTITY_REVS),
                            [names_all[rrng.nxt() % len(names_all)]])
        kind = rrng.pick(DAMAGE_KINDS)
        payload = _apply_damage(kind, rc.encode_segment(doc))
        reject.append({"capture_id": f"rej-{i:05d}", "stream_id": doc["stream_id"],
                       "seq_no": 0, "revision": doc["revision"], "hex": payload.hex(),
                       "transit_note": kind})
    return clean, reject, schema, layouts, symrows, revisions


if __name__ == "__main__":
    clean, reject, schema, layouts, symrows, revisions = build_catalog()
    print("clean", len(clean), "reject", len(reject), "fields", len(layouts), "symbols", len(symrows))
    ok = 0
    final_names = set()
    for row in clean:
        buf = bytes.fromhex(row["hex"])
        doc = rc.decode_segment(buf, schema)
        assert "records" in doc, doc
        assert rc.encode_segment(doc) == buf, row["capture_id"]
        for r in doc["records"]:
            if r["field"] is not None:
                final_names.add(r["field"])
        ok += 1
    print("roundtrip all clean OK", ok, "distinct final field names", len(final_names))
    for row in reject:
        doc = rc.decode_segment(bytes.fromhex(row["hex"]), schema)
        assert "error" in doc, (row["transit_note"], doc)
    print("reject all produce error objects OK")


# --------------------------------------------------------------------------- #
# writing shipped data
# --------------------------------------------------------------------------- #
def build_alpha_beta(schema):
    """One valid 2-segment stream (stream_continues on seg0), NO cross-file refs."""
    rng = Rng(SEED ^ 0xA1B2)
    sid = 3
    seg0 = _make_capture(rng, sid, 2, ["temp_0003", "flow_0009"])
    seg0["seq_no"] = 0
    seg0["flags"] = {"stream_continues": True}
    seg0["record_count"] = len(seg0["records"])
    seg1 = _make_capture(rng, sid, 2, ["pressure_0001"])
    seg1["seq_no"] = 1
    seg1["flags"] = {"stream_continues": False}
    seg1["record_count"] = len(seg1["records"])
    return rc.encode_segment(seg0), rc.encode_segment(seg1)


def _interleave(clean, reject):
    out = []
    ci = ri = 0
    rng = Rng(SEED ^ 0x1337)
    while ci < len(clean) or ri < len(reject):
        if ri < len(reject) and (ci >= len(clean) or rng.nxt() % 7 == 0):
            row = reject[ri]; ri += 1
        else:
            row = clean[ci]; ci += 1
        out.append({k: row[k] for k in ("capture_id", "stream_id", "seq_no", "revision", "hex")})
    return out


def write_all():
    clean, reject, schema, layouts, symrows, revisions = build_catalog()
    DATA.mkdir(parents=True, exist_ok=True)
    for stale in DATA.iterdir():
        if stale.suffix == ".md":
            continue  # hand-written spec files are preserved
        stale.unlink()
    catalog = _interleave(clean, reject)
    with (DATA / "capture_catalog.jsonl").open("w", encoding="utf-8") as fh:
        for row in catalog:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    with (DATA / "field_layouts.csv").open("w", encoding="utf-8") as fh:
        fh.write("canonical_id,name,unit,width\n")
        for (cid, name, unit, width) in layouts:
            fh.write(f"{cid},{name},{unit},{width}\n")
    with (DATA / "symbol_table.tsv").open("w", encoding="utf-8") as fh:
        fh.write("stream_id\tcanonical_id\talias\n")
        for (sid, cid, alias) in symrows:
            fh.write(f"{sid}\t{cid}\t{alias}\n")
    with (DATA / "revision_map.ini").open("w", encoding="utf-8") as fh:
        fh.write("; Field-id revision remap for short (one byte) keys.\n")
        fh.write("; Revisions 0 1 2 3 are identity: a short key maps to the canonical\n")
        fh.write("; field id equal to the key byte. Revisions 4 5 6 7 remap as below:\n")
        fh.write("; raw_key = canonical_id, one line per short key in force for that revision.\n")
        for rev in NONIDENTITY_REVS:
            fh.write(f"[revision_{rev}]\n")
            for raw in sorted(revisions[rev]):
                fh.write(f"{raw} = {revisions[rev][raw]}\n")
    (DATA / "schema_registry.json").write_text(json.dumps({
        "extension_types": {str(k): v for k, v in EXT_TYPES.items()},
        "opaque_rule": "An extension whose type is not listed here is opaque: keep its "
                       "bytes unchanged and in their original position.",
        "canonical_field_count": N_FIELDS,
        "stream_count": N_STREAMS,
    }, indent=2) + "\n", encoding="utf-8")
    (DATA / "crc_profiles.json").write_text(json.dumps({
        "algorithm": "crc32",
        "coverage": "header",
        "covers_offsets": [5, 15],
        "byte_order": "little",
        "note": "The 4 byte trailer is crc32 over header offsets 5 through 15 inclusive "
                "(the 11 header bytes after the five byte magic). Frame bytes are not covered.",
    }, indent=2) + "\n", encoding="utf-8")
    alpha, beta = build_alpha_beta(schema)
    (DATA / "capture_alpha.varc").write_bytes(alpha)
    (DATA / "capture_beta.varc").write_bytes(beta)
    return catalog, layouts, symrows


if __name__ == "__main__" and False:
    pass
