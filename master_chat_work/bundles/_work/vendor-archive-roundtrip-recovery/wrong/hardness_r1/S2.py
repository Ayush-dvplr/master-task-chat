#!/usr/bin/env python3
"""Reference solver for the VARC1 recovery task.

Installed by solve.sh as the agent-visible /app/decode.py and /app/encode.py with
the field schema baked in, then used to emit the /app/out reports. This is an
independent implementation written from the written contract under /app/data.

Runtime roles (dispatched on argv):
  decode.py <file.varc>                 print one decode document
  decode.py --stream <manifest.json>    print {"segments": [...]}
  decode.py --salvage <file.varc>       print a salvage document
  encode.py <document.json> <out.varc>  write segment bytes
Build roles (used by solve.sh in the agent container where /app/data exists):
  solve.py --build <data_dir> <decode_out> <encode_out>
  solve.py --emit-reports <data_dir> <out_dir>
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

SCHEMA_JSON = "{}"  # BUILD_REPLACES_THIS

MAGIC = b"VARC1"
GOOD_VERSION = 2
HDR = 16
TRL = 4
SYNC_B = 0xAA
ESC_B = 0x1B
MIN_FRAME = 5
MODES = ("raw", "delta", "dict", "reset")


class BadFrame(Exception):
    pass


def _uv_write(value):
    chunks = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        chunks.append(low | (0x80 if value else 0))
        if not value:
            return bytes(chunks)


def _uv_read(data, at):
    result = 0
    offset = 0
    while True:
        if at >= len(data):
            raise BadFrame("uvarint ran off the end")
        octet = data[at]
        at += 1
        result |= (octet & 0x7F) << offset
        if not octet & 0x80:
            return result, at
        offset += 7
        if offset > 63:
            raise BadFrame("uvarint too wide")


def _sv_write(value):
    chunks = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        done = (value == 0 and not low & 0x40) or (value == -1 and low & 0x40)
        chunks.append(low if done else low | 0x80)
        if done:
            return bytes(chunks)


def _sv_pad(value, size):
    base = bytearray(_sv_write(value))
    filler = 0x7F if value < 0 else 0x00
    while len(base) < size:
        base[-1] |= 0x80
        base.append(filler)
    base[-1] &= 0x7F
    return bytes(base)


def _sv_read(data, at):
    result = 0
    offset = 0
    first = at
    while True:
        if at >= len(data):
            raise BadFrame("sleb128 ran off the end")
        octet = data[at]
        at += 1
        result |= (octet & 0x7F) << offset
        offset += 7
        if not octet & 0x80:
            if octet & 0x40:
                result |= -(1 << offset)
            return result, at - first
        if offset > 70:
            raise BadFrame("sleb128 too wide")


def _escape(raw):
    buf = bytearray()
    for byte in raw:
        if byte == SYNC_B or byte == ESC_B:
            buf.append(ESC_B)
            buf.append(byte ^ 0x20)
        else:
            buf.append(byte)
    return bytes(buf)


def _unescape_all(buf):
    out = bytearray()
    i = 0
    while i < len(buf):
        if buf[i] == ESC_B and i + 1 < len(buf):
            out.append(buf[i + 1] ^ 0x20)
            i += 2
        else:
            out.append(buf[i])
            i += 1
    return bytes(out)


def _unescape(data, at, count):
    stop = at + count
    if stop <= len(data):
        return bytes(data[at:stop]), stop
    if stop > len(data):
        raise BadFrame("body window past end")
    raw = bytearray()
    while at < stop:
        if data[at] == ESC_B:
            if at + 1 >= stop:
                raise BadFrame("escape at window edge")
            raw.append(data[at + 1] ^ 0x20)
            at += 2
        else:
            raw.append(data[at])
            at += 1
    return bytes(raw), stop


def _crc(data):
    return zlib.crc32(data[5:16]) & 0xFFFFFFFF


class Schema:
    def __init__(self, blob):
        self.id_name = {int(k): v for k, v in blob.get("id_name", {}).items()}
        self.name_id = {v: int(k) for k, v in blob.get("id_name", {}).items()}
        self.id_unit = {int(k): v for k, v in blob.get("id_unit", {}).items()}
        self.alias = {(int(p.split(",")[0]), int(p.split(",")[1])): v
                      for p, v in blob.get("alias", {}).items()}
        self.remap = {(int(p.split(",")[0]), int(p.split(",")[1])): int(v)
                      for p, v in blob.get("remap", {}).items()}

    def name_for(self, rec, stream_id, revision):
        if rec["mode"] == "reset":
            return None, None, None
        if rec["long_key"]:
            canon = self.name_id.get(rec["key_str"])
        else:
            canon = rec["raw_key"]  # reflex: identity remap
        base = rec["key_str"] if rec["long_key"] else self.id_name.get(canon)
        final = self.alias.get((stream_id, canon), base)
        return final, self.id_unit.get(canon), canon


def _header_error(data):
    if data[:5] != MAGIC:
        return {"error": "bad_magic"}
    if len(data) >= HDR + TRL and _crc(data) != struct.unpack("<I", data[-TRL:])[0]:
        return {"error": "trailer_crc_mismatch", "expected": _crc(data),
                "found": struct.unpack("<I", data[-TRL:])[0]}  # reflex: crc first
    ver = data[5] if len(data) > 5 else -1
    if ver != GOOD_VERSION:
        return {"error": "unsupported_version", "version": ver}
    if len(data) < HDR:
        rc = struct.unpack_from("<H", data, 11)[0] if len(data) >= 13 else -1
        return {"error": "record_count_overflow", "record_count": rc}
    if data[14] != 0:
        return {"error": "reserved_not_zero", "offset": 14}
    if data[15] != 0:
        return {"error": "reserved_not_zero", "offset": 15}
    count = struct.unpack_from("<H", data, 11)[0]
    room = len(data) - HDR - TRL
    if room < 0 or count * MIN_FRAME > room:
        return {"error": "record_count_overflow", "record_count": count}
    want = _crc(data)
    got = struct.unpack("<I", data[-TRL:])[0]
    if want != got:
        return {"error": "trailer_crc_mismatch", "expected": want, "found": got}
    return None


def _head(data):
    return {
        "stream_id": struct.unpack_from("<H", data, 7)[0],
        "seq_no": struct.unpack_from("<H", data, 9)[0],
        "record_count": struct.unpack_from("<H", data, 11)[0],
        "revision": data[13],
        "flags": {"stream_continues": bool(data[6] & 0x01)},
    }


def _read_frame(data, at, carry, stream_id, revision, schema):
    if at >= len(data) or data[at] != SYNC_B:
        raise BadFrame("expected sync")
    at += 1
    if at >= len(data):
        raise BadFrame("no selector")
    sel = data[at]
    at += 1
    if sel >> 5:
        raise BadFrame("selector high bits")
    mode = MODES[sel & 0x03]
    wide = bool(sel & 0x04)
    long_key = bool(sel & 0x08)
    has_ext = bool(sel & 0x10)
    rec = {"raw_key": None, "long_key": long_key, "mode": mode, "field": None,
           "unit": None, "canonical_id": None, "wide": None, "value": None,
           "ext_present": has_ext, "extensions": []}
    if long_key:
        klen, at = _uv_read(data, at)
        if at + klen > len(data):
            raise BadFrame("long key past end")
        rec["key_str"] = data[at:at + klen].decode("utf-8")
        at += klen
    else:
        if at >= len(data):
            raise BadFrame("no key byte")
        rec["raw_key"] = data[at]
        at += 1
    if at >= len(data):
        raise BadFrame("no fchk")
    fchk = data[at]
    at += 1
    blen, at = _uv_read(data, at)
    raw, at = _unescape(data, at, blen)
    if sum(raw) & 0xFF != fchk:
        raise BadFrame("fchk mismatch")
    cur = 0
    if mode == "raw":
        size = 4 if wide else 2
        if len(raw) < size:
            raise BadFrame("raw value short")
        rec["wide"] = wide
        rec["raw_value"] = struct.unpack_from("<i" if wide else "<h", raw, 0)[0]
        rec["value"] = rec["raw_value"]
        cur = size
    elif mode == "delta":
        delta, used = _sv_read(raw, 0)
        rec["delta_raw"] = delta
        rec["delta_raw_len"] = len(_sv_write(delta))  # reflex: length not remembered
        rec["value"] = carry["cum"] + delta
        carry["cum"] = rec["value"]
        cur = used
    elif mode == "dict":
        if not raw:
            raise BadFrame("dict byte missing")
        idx = raw[0]
        back = len(carry["res"]) - 1 - idx
        if back < 0 or back >= len(carry["res"]):
            raise BadFrame("dict index out of range")
        rec["dict_index"] = idx
        rec["value"] = carry["res"][back]
        carry["cum"] = rec["value"]
        cur = 1
    else:
        carry["cum"] = 0
        carry["res"] = []
    if has_ext:
        pos = cur
        while pos < len(raw):
            etype, pos = _uv_read(raw, pos)
            elen, pos = _uv_read(raw, pos)
            if pos + elen > len(raw):
                raise BadFrame("ext past body")
            rec["extensions"].append({"type": etype, "hex": raw[pos:pos + elen].hex()})
            pos += elen
    elif cur != len(raw):
        raise BadFrame("extra body bytes")
    rec["field"], rec["unit"], rec["canonical_id"] = schema.name_for(rec, stream_id, revision)
    if mode != "reset":
        carry["res"].append(rec["value"])
    return rec, at


def decode_one(data, schema, carry=None):
    err = _header_error(data)
    if err is not None:
        return err
    head = _head(data)
    data = data[:HDR] + _unescape_all(data[HDR:len(data) - TRL]) + data[len(data) - TRL:]
    carry = carry if carry is not None else {"cum": 0, "res": []}
    at = HDR
    records = []
    try:
        for _ in range(head["record_count"]):
            rec, at = _read_frame(data, at, carry, head["stream_id"], head["revision"], schema)
            records.append(rec)
    except BadFrame as exc:
        return {"error": "malformed_frame", "detail": str(exc)}
    return {"magic_ok": True, "version": GOOD_VERSION, "stream_id": head["stream_id"],
            "seq_no": head["seq_no"], "revision": head["revision"], "flags": head["flags"],
            "record_count": head["record_count"], "records": records}


def decode_stream(paths, schema):
    carries = {}
    docs = []
    for path in paths:
        data = Path(path).read_bytes()
        err = _header_error(data)
        if err is not None:
            docs.append(err)
            continue
        sid = struct.unpack_from("<H", data, 7)[0]
        carry = {"cum": 0, "res": []}  # reflex: fresh state per file
        docs.append(decode_one(data, schema, carry))
    return {"segments": docs}


def salvage_one(data, schema):
    defect = _header_error(data)
    if defect is not None:
        return defect  # reflex: early return
    stream_id = struct.unpack_from("<H", data, 7)[0] if len(data) >= 9 else 0
    revision = data[13] if len(data) > 13 else 0
    carry = {"cum": 0, "res": []}
    records = []
    damaged = []
    at = HDR
    stop = len(data) - TRL
    while at < stop:
        try:
            rec, at = _read_frame(data, at, carry, stream_id, revision, schema)
            records.append(rec)
        except BadFrame as exc:
            bad = at
            resume = None  # reflex: abort on first bad frame
            damaged.append({"from_offset": bad,
                            "resync_offset": resume if resume is not None else stop,
                            "reason": str(exc)})
            if resume is None:
                break
            at = resume
    return {"records": records, "damaged": damaged,
            "header_defect": defect["error"] if defect else None}


def _scan_sync(data, start, stop, carry, stream_id, revision, schema):
    at = start
    while at < stop:
        if data[at] == SYNC_B:
            probe = {"cum": carry["cum"], "res": list(carry["res"])}
            try:
                _read_frame(data, at, probe, stream_id, revision, schema)
                return at
            except BadFrame:
                pass
        at += 1
    return None


def encode_one(doc):
    body = bytearray()
    for rec in doc["records"]:
        mode = rec["mode"]
        wide = bool(rec.get("wide")) if mode == "raw" else False
        long_key = bool(rec["long_key"])
        exts = []  # reflex: frame rebuilt from value fields only
        sel = MODES.index(mode) | (wide << 2) | (long_key << 3) | (bool(exts) << 4)
        raw = bytearray()
        if mode == "raw":
            raw += struct.pack("<i" if wide else "<h", rec["raw_value"])
        elif mode == "delta":
            size = rec.get("delta_raw_len")
            short = _sv_write(rec["delta_raw"])
            raw += short  # reflex: always shortest
        elif mode == "dict":
            raw.append(rec["dict_index"])
        for ext in exts:
            payload = bytes.fromhex(ext["hex"])
            raw += _uv_write(ext["type"]) + _uv_write(len(payload)) + payload
        frame = bytearray([SYNC_B, sel])
        if long_key:
            kb = rec["key_str"].encode("utf-8")
            frame += _uv_write(len(kb)) + kb
        else:
            frame.append(rec["raw_key"])
        esc = _escape(bytes(raw))
        frame.append(sum(raw) & 0xFF)
        frame += _uv_write(len(esc)) + esc
        body += frame
    flags = 0x01 if doc["flags"]["stream_continues"] else 0x00
    head = (MAGIC + struct.pack("<BBHHHB", GOOD_VERSION, flags, doc["stream_id"],
            doc["seq_no"], doc["record_count"], doc["revision"]) + b"\x00\x00")
    return bytes(head) + bytes(body) + struct.pack("<I", _crc(head))


def load_schema(data_dir):
    data_dir = Path(data_dir)
    id_name = {}
    id_unit = {}
    for line in (data_dir / "field_layouts.csv").read_text().splitlines()[1:]:
        if not line.strip():
            continue
        cid, name, unit, _width = line.split(",")
        id_name[cid] = name
        id_unit[cid] = unit
    alias = {}
    for line in (data_dir / "symbol_table.tsv").read_text().splitlines()[1:]:
        if not line.strip():
            continue
        sid, cid, al = line.split("\t")
        alias[f"{sid},{cid}"] = al
    remap = {}
    rev = None
    for line in (data_dir / "revision_map.ini").read_text().splitlines():
        line = line.strip()
        if line.startswith("[revision_"):
            rev = line[len("[revision_"):-1]
        elif line and not line.startswith(";") and "=" in line and rev is not None:
            raw, tgt = [p.strip() for p in line.split("=", 1)]
            remap[f"{rev},{raw}"] = int(tgt)
    return {"id_name": id_name, "id_unit": id_unit, "alias": alias, "remap": remap}


def build_programs(data_dir, decode_out, encode_out):
    blob = json.dumps(load_schema(data_dir), separators=(",", ":"))
    source = Path(__file__).read_text()
    first = source.index('"""')
    second = source.index('"""', first + 3)
    source = source[:first] + source[second + 3:]
    source = source.replace('SCHEMA_JSON = "{}"  # BUILD_REPLACES_THIS',
                            "SCHEMA_JSON = " + repr(blob), 1)
    Path(decode_out).write_text(source)
    Path(encode_out).write_text(source)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _damage(data, kind):
    b = bytearray(data)
    if kind in ("bad_magic", "all"):
        b[0] ^= 0xFF
    if kind in ("unsupported_version", "all"):
        b[5] = 9
    if kind in ("reserved_not_zero", "all"):
        b[14] = 1
    if kind in ("record_count_overflow", "all"):
        struct.pack_into("<H", b, 11, 0xFFFF)
    if kind in ("trailer_crc_mismatch", "all"):
        b[-1] ^= 0xFF
    return bytes(b)


def _build_examples(schema):
    docs = [
        {"stream_id": 1, "seq_no": 0, "revision": 0, "flags": {"stream_continues": False},
         "record_count": 3, "records": [
            {"raw_key": 1, "long_key": False, "mode": "raw", "wide": True,
             "raw_value": 1234, "value": 1234, "ext_present": False, "extensions": []},
            {"raw_key": 2, "long_key": False, "mode": "delta", "wide": None,
             "delta_raw": -10, "delta_raw_len": 1, "value": 1224, "ext_present": False, "extensions": []},
            {"raw_key": 3, "long_key": False, "mode": "dict", "wide": None,
             "dict_index": 1, "value": 1234, "ext_present": True,
             "extensions": [{"type": 42, "hex": "00ff"}]}]},
        {"stream_id": 1, "seq_no": 0, "revision": 0, "flags": {"stream_continues": False},
         "record_count": 2, "records": [
            {"raw_key": None, "long_key": True, "key_str": "temp_0001", "mode": "raw",
             "wide": False, "raw_value": 5, "value": 5, "ext_present": False, "extensions": []},
            {"raw_key": 0, "long_key": False, "mode": "reset", "wide": None,
             "value": None, "ext_present": False, "extensions": []}]},
        {"stream_id": 2, "seq_no": 0, "revision": 0, "flags": {"stream_continues": False},
         "record_count": 3, "records": [
            {"raw_key": None, "long_key": True, "key_str": "flow_0009", "mode": "raw",
             "wide": True, "raw_value": 70000, "value": 70000, "ext_present": True,
             "extensions": [{"type": 55, "hex": "1234"}]},
            {"raw_key": 4, "long_key": False, "mode": "delta", "wide": None,
             "delta_raw": 12, "delta_raw_len": 1, "value": 70012, "ext_present": False, "extensions": []},
            {"raw_key": 5, "long_key": False, "mode": "dict", "wide": None,
             "dict_index": 0, "value": 70012, "ext_present": False, "extensions": []}]},
        {"stream_id": 2, "seq_no": 0, "revision": 0, "flags": {"stream_continues": False},
         "record_count": 2, "records": [
            {"raw_key": 6, "long_key": False, "mode": "raw", "wide": False,
             "raw_value": -42, "value": -42, "ext_present": False, "extensions": []},
            {"raw_key": 7, "long_key": False, "mode": "reset", "wide": None,
             "value": None, "ext_present": False, "extensions": []}]},
    ]
    out = []
    for i, doc in enumerate(docs):
        payload = encode_one(doc)
        out.append({"name": f"example_{i}", "hex": payload.hex(), "decoded": decode_one(payload, schema)})
    return out


def emit_reports(data_dir, out_dir):
    data_dir = Path(data_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    schema = Schema(load_schema(data_dir))
    mode_counts = {m: 0 for m in MODES}
    errors = {}
    ok = err = frames = 0
    streams = set()
    names = set()
    canon_seen = set()
    for line in (data_dir / "capture_catalog.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        doc = decode_one(bytes.fromhex(row["hex"]), schema)
        if "error" in doc:
            err += 1
            errors[doc["error"]] = errors.get(doc["error"], 0) + 1
            continue
        ok += 1
        streams.add(doc["stream_id"])
        frames += len(doc["records"])
        for rec in doc["records"]:
            mode_counts[rec["mode"]] += 1
            if rec["field"] is not None:
                names.add(rec["field"])
            if rec["canonical_id"] is not None:
                canon_seen.add(rec["canonical_id"])
    unit_pairs = sorted(f"{schema.id_name[c]}\t{schema.id_unit[c]}" for c in canon_seen)
    report = {
        "format_tag": "VARC", "magic_hex": MAGIC.hex(), "version": GOOD_VERSION,
        "header_size": HDR, "trailer_size": TRL, "sync_byte": "aa", "esc_byte": "1b",
        "crc_coverage": "header", "crc_covers_offsets": [5, 15],
        "mode_ids": {"raw": 0, "delta": 1, "dict": 2, "reset": 3},
        "catalog_count": ok + err, "catalog_ok_count": ok, "catalog_error_count": err,
        "catalog_mode_counts": mode_counts, "stream_count": len(streams),
        "catalog_frame_count": frames, "catalog_errors": dict(sorted(errors.items())),
        "distinct_field_count": len(names),
        "field_name_sha256": _sha("\n".join(sorted(names))),
        "field_unit_sha256": _sha("\n".join(unit_pairs)),
    }
    (out_dir / "format_report.json").write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    examples = _build_examples(schema)
    with (out_dir / "decoded_examples.jsonl").open("w") as fh:
        for ex in examples:
            fh.write(json.dumps(ex, separators=(",", ":")) + "\n")
    rt = {"all_roundtrips_equal": True, "examples": []}
    for ex in examples:
        payload = bytes.fromhex(ex["hex"])
        rebuilt = encode_one(ex["decoded"])
        equal = rebuilt == payload
        rt["all_roundtrips_equal"] = rt["all_roundtrips_equal"] and equal
        rt["examples"].append({
            "name": ex["name"], "input_sha256": hashlib.sha256(payload).hexdigest(),
            "rebuilt_sha256": hashlib.sha256(rebuilt).hexdigest(),
            "byte_length": len(payload), "roundtrip_equal": equal})
    (out_dir / "roundtrip_report.json").write_text(
        json.dumps(rt, sort_keys=True, separators=(",", ":")) + "\n")
    first = bytes.fromhex(examples[0]["hex"])
    cases = {k: decode_one(_damage(first, k), schema) for k in
             ("bad_magic", "unsupported_version", "reserved_not_zero",
              "record_count_overflow", "trailer_crc_mismatch", "all")}
    cases["all_defects"] = cases.pop("all")
    err_doc = {
        "precedence": ["bad_magic", "unsupported_version", "reserved_not_zero",
                       "record_count_overflow", "trailer_crc_mismatch"],
        "cases": cases, "catalog_errors": dict(sorted(errors.items())),
    }
    (out_dir / "error_analysis.json").write_text(
        json.dumps(err_doc, sort_keys=True, separators=(",", ":")) + "\n")


def main(argv):
    if argv and argv[0] == "--build":
        build_programs(argv[1], argv[2], argv[3])
        return 0
    if argv and argv[0] == "--emit-reports":
        emit_reports(argv[1], argv[2])
        return 0
    schema = Schema(json.loads(SCHEMA_JSON))
    if argv and argv[0] == "--stream":
        manifest = json.loads(Path(argv[1]).read_text())
        print(json.dumps(decode_stream([s["path"] for s in manifest["segments"]], schema)))
        return 0
    if argv and argv[0] == "--salvage":
        print(json.dumps(salvage_one(Path(argv[1]).read_bytes(), schema)))
        return 0
    if len(argv) == 2:
        Path(argv[1]).write_bytes(encode_one(json.loads(Path(argv[0]).read_text())))
        return 0
    if len(argv) == 1:
        print(json.dumps(decode_one(Path(argv[0]).read_bytes(), schema)))
        return 0
    sys.stderr.write("usage error\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
