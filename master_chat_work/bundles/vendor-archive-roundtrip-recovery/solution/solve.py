#!/usr/bin/env python3
"""Reference solver for the VARC1 recovery task.

solve.sh runs it twice in the agent container where /app/data exists:
  solve.py --build <data_dir> <decode_out> <encode_out>
  solve.py --emit-reports <data_dir> <out_dir>
--build writes two self contained programs, /app/decode.py and /app/encode.py,
each holding only the definitions its role uses, with the field schema baked
into the decoder. This is an independent implementation written from the
written contract under /app/data.
"""
from __future__ import annotations

import ast
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

SCHEMA_JSON = "{}"

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
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _uv_read(data, at, limit):
    total = 0
    bit = 0
    while at < limit:
        byte = data[at]
        at += 1
        total += (byte & 0x7F) << bit
        if byte < 0x80:
            return total, at
        bit += 7
    raise BadFrame("varint runs off the window")


def _sv_write(value, size=None):
    groups = []
    while True:
        low = value & 0x7F
        value >>= 7
        done = (value == 0 and low < 0x40) or (value == -1 and low >= 0x40)
        groups.append(low)
        if done:
            break
    pad = 0x7F if groups[-1] & 0x40 else 0x00
    while size is not None and len(groups) < size:
        groups.append(pad)
    return bytes([g | 0x80 for g in groups[:-1]] + [groups[-1]])


def _sv_read(data, at, limit):
    total = 0
    bit = 0
    first = at
    while at < limit:
        byte = data[at]
        at += 1
        total |= (byte & 0x7F) << bit
        bit += 7
        if byte < 0x80:
            if byte & 0x40:
                total -= 1 << bit
            return total, at - first
    raise BadFrame("signed varint runs off the body")


def _escape(raw):
    out = bytearray()
    for byte in raw:
        if byte == SYNC_B or byte == ESC_B:
            out.append(ESC_B)
            out.append(byte ^ 0x20)
        else:
            out.append(byte)
    return bytes(out)


def _unescape(data, at, count, limit):
    stop = at + count
    if stop > limit:
        raise BadFrame("body window crosses the trailer")
    out = bytearray()
    while at < stop:
        byte = data[at]
        if byte == ESC_B:
            if at + 1 == stop:
                raise BadFrame("escape at the end of the window")
            out.append(data[at + 1] ^ 0x20)
            at += 2
        else:
            out.append(byte)
            at += 1
    return bytes(out), stop


def _crc(data):
    return zlib.crc32(bytes(data[5:16])) & 0xFFFFFFFF


class Schema:
    def __init__(self, blob):
        self.id_name = {int(k): v for k, v in blob.get("id_name", {}).items()}
        self.id_unit = {int(k): v for k, v in blob.get("id_unit", {}).items()}
        self.name_id = {v: k for k, v in self.id_name.items()}
        self.alias = {tuple(int(p) for p in k.split(",")): v
                      for k, v in blob.get("alias", {}).items()}
        self.remap = {tuple(int(p) for p in k.split(",")): v
                      for k, v in blob.get("remap", {}).items()}

    def naming(self, long_key, key, stream_id, revision):
        if long_key:
            cid = self.name_id.get(key)
            if cid is None:
                return key, None, None
        else:
            cid = self.remap.get((revision, key), key)
        base = self.id_name.get(cid)
        return self.alias.get((stream_id, cid), base), self.id_unit.get(cid), cid


def _header_error(data):
    if len(data) < HDR + TRL or data[:5] != MAGIC:
        return {"error": "bad_magic"}
    if data[5] != GOOD_VERSION:
        return {"error": "unsupported_version", "version": data[5]}
    if data[14]:
        return {"error": "reserved_not_zero", "offset": 14}
    if data[15]:
        return {"error": "reserved_not_zero", "offset": 15}
    count = data[11] | (data[12] << 8)
    if count * MIN_FRAME > len(data) - HDR - TRL:
        return {"error": "record_count_overflow", "record_count": count}
    stored = struct.unpack("<I", data[-TRL:])[0]
    want = _crc(data)
    if stored != want:
        return {"error": "trailer_crc_mismatch", "expected": want, "found": stored}
    return None


def _head(data):
    stream_id, seq_no, count = struct.unpack_from("<HHH", data, 7)
    return {"stream_id": stream_id, "seq_no": seq_no, "count": count,
            "revision": data[13], "continues": bool(data[6] & 1)}


class Carry:
    """Stream state: one running total per field name and the resolved list."""

    def __init__(self):
        self.totals = {}
        self.seen = []

    def clone(self):
        twin = Carry()
        twin.totals = dict(self.totals)
        twin.seen = list(self.seen)
        return twin

    def take(self, rec):
        if rec["mode"] == "reset":
            self.totals = {}
            self.seen = []
        else:
            self.seen.append(rec["value"])
            if rec["mode"] != "dict":
                self.totals[rec["field"]] = rec["value"]


def _read_frame(data, at, limit, carry, stream_id, revision, schema):
    """Read one frame at `at`; never changes `carry` (the caller applies it)."""
    if at >= limit or data[at] != SYNC_B:
        raise BadFrame("no frame starts here")
    if at + 1 >= limit:
        raise BadFrame("selector missing")
    selector = data[at + 1]
    if selector & 0xE0:
        raise BadFrame("selector high bits set")
    mode = MODES[selector & 3]
    wide = bool(selector & 4)
    if wide and mode != "raw":
        raise BadFrame("wide flag outside raw mode")
    long_key = bool(selector & 8)
    with_ext = bool(selector & 16)
    pos = at + 2
    if long_key:
        size, pos = _uv_read(data, pos, limit)
        if pos + size > limit:
            raise BadFrame("long key cut off")
        try:
            key = data[pos:pos + size].decode("utf-8")
        except UnicodeDecodeError:
            raise BadFrame("long key not utf-8")
        pos += size
    else:
        if pos >= limit:
            raise BadFrame("key byte missing")
        key = data[pos]
        pos += 1
    if pos >= limit:
        raise BadFrame("check byte missing")
    check = data[pos]
    body_len, pos = _uv_read(data, pos + 1, limit)
    body, pos = _unescape(data, pos, body_len, limit)
    if sum(body) % 256 != check:
        raise BadFrame("check byte disagrees")
    rec = {"raw_key": None if long_key else key, "long_key": long_key, "mode": mode,
           "wide": wide if mode == "raw" else None}
    if long_key:
        rec["key_str"] = key
    if mode == "reset":
        rec["field"] = rec["unit"] = rec["canonical_id"] = None
    else:
        rec["field"], rec["unit"], rec["canonical_id"] = schema.naming(
            long_key, key, stream_id, revision)
    used = 0
    if mode == "raw":
        used = 4 if wide else 2
        if len(body) < used:
            raise BadFrame("raw body too short")
        rec["raw_value"] = int.from_bytes(body[:used], "little", signed=rec["unit"] != "count")
        rec["value"] = rec["raw_value"]
    elif mode == "delta":
        step, used = _sv_read(body, 0, len(body))
        rec["delta_raw"] = step
        rec["delta_raw_len"] = used
        rec["value"] = carry.totals.get(rec["field"], 0) + step
    elif mode == "dict":
        if not body:
            raise BadFrame("dict body empty")
        back = body[0]
        if back >= len(carry.seen):
            raise BadFrame("dict index past the list")
        rec["dict_index"] = back
        rec["value"] = carry.seen[-1 - back]
        used = 1
    else:
        rec["value"] = None
    exts = []
    if with_ext:
        if used == len(body):
            raise BadFrame("extension flag with no extension")
        while used < len(body):
            kind, used = _uv_read(body, used, len(body))
            size, used = _uv_read(body, used, len(body))
            if used + size > len(body):
                raise BadFrame("extension cut off")
            exts.append({"type": kind, "hex": body[used:used + size].hex()})
            used += size
    elif used != len(body):
        raise BadFrame("bytes left in body")
    rec["ext_present"] = with_ext
    rec["extensions"] = exts
    return rec, pos


def decode_one(data, schema, carry=None):
    problem = _header_error(data)
    if problem:
        return problem
    head = _head(data)
    carry = carry or Carry()
    limit = len(data) - TRL
    at = HDR
    records = []
    for _ in range(head["count"]):
        rec, at = _read_frame(data, at, limit, carry, head["stream_id"], head["revision"],
                              schema)
        carry.take(rec)
        records.append(rec)
    return {"magic_ok": True, "version": GOOD_VERSION, "stream_id": head["stream_id"],
            "seq_no": head["seq_no"], "revision": head["revision"],
            "flags": {"stream_continues": head["continues"]},
            "record_count": head["count"], "records": records}


def _clean_text(value):
    return value.strip() if isinstance(value, str) else value


def decode_stream(entries, schema):
    """Each stream has at most one open run: its Carry and the last seq_no taken."""
    open_runs = {}
    docs = []
    for entry in entries:
        entry = {name: _clean_text(value) for name, value in entry.items()}
        data = Path(entry["path"]).read_bytes()
        head = _head(data)
        run = open_runs.get(head["stream_id"])
        if run is not None and head["seq_no"] <= run[1]:
            docs.append(decode_one(data, schema, run[0].clone()))
            continue
        carry = run[0] if run is not None else Carry()
        docs.append(decode_one(data, schema, carry))
        flag = entry.get("stream_continues")
        keeps_open = flag if isinstance(flag, bool) else head["continues"]
        if keeps_open:
            open_runs[head["stream_id"]] = (carry, head["seq_no"])
        else:
            open_runs.pop(head["stream_id"], None)
    return {"segments": docs}


def salvage_one(data, schema):
    problem = _header_error(data)
    head = _head(data) if len(data) >= HDR else {"stream_id": 0, "revision": 0}
    limit = len(data) - TRL
    carry = Carry()
    records = []
    damaged = []
    at = HDR
    while at < limit:
        try:
            rec, nxt = _read_frame(data, at, limit, carry, head["stream_id"],
                                   head["revision"], schema)
        except BadFrame as why:
            back_at = _scan_sync(data, at + 1, limit, carry, head["stream_id"],
                                 head["revision"], schema)
            damaged.append({"from_offset": at, "resync_offset": back_at, "reason": str(why)})
            at = back_at
            continue
        carry.take(rec)
        records.append(rec)
        at = nxt
    return {"records": records, "damaged": damaged,
            "header_defect": problem["error"] if problem else None}


def _scan_sync(data, start, stop, carry, stream_id, revision, schema):
    for at in range(start, stop):
        if data[at] != SYNC_B:
            continue
        try:
            _read_frame(data, at, stop, carry, stream_id, revision, schema)
        except BadFrame:
            continue
        return at
    return stop


def encode_one(doc):
    frames = bytearray()
    records = doc["records"]
    for rec in records:
        mode = rec["mode"]
        wide = mode == "raw" and bool(rec.get("wide"))
        exts = rec.get("extensions") or []
        body = bytearray()
        if mode == "raw":
            size = 4 if wide else 2
            body += (int(rec["raw_value"]) % (1 << (8 * size))).to_bytes(size, "little")
        elif mode == "delta":
            length = rec.get("delta_raw_len")
            exact = length if isinstance(length, int) and not isinstance(length, bool) else None
            body += _sv_write(rec["delta_raw"], exact)
        elif mode == "dict":
            body.append(rec["dict_index"])
        for ext in exts:
            blob = bytes.fromhex(ext["hex"].strip())
            body += _uv_write(ext["type"]) + _uv_write(len(blob)) + blob
        selector = MODES.index(mode) | (4 if wide else 0)
        selector |= (8 if rec.get("long_key") else 0) | (16 if exts else 0)
        frames.append(SYNC_B)
        frames.append(selector)
        if rec.get("long_key"):
            name = rec["key_str"].encode("utf-8")
            frames += _uv_write(len(name)) + name
        else:
            frames.append(rec["raw_key"])
        frames.append(sum(body) % 256)
        packed = _escape(body)
        frames += _uv_write(len(packed)) + packed
    head = bytearray(MAGIC)
    head.append(GOOD_VERSION)
    head.append(1 if doc["flags"]["stream_continues"] else 0)
    head += struct.pack("<HHH", doc["stream_id"], doc["seq_no"], len(records))
    head += bytes([doc["revision"], 0, 0])
    return bytes(head) + bytes(frames) + struct.pack("<I", _crc(head))


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


DECODE_DOC = '''"""Decode VARC1 segments to JSON documents.

Usage:
  python3 decode.py <file.varc>                 print one decode document
  python3 decode.py --stream <manifest.json>    print {"segments": [...]}
  python3 decode.py --salvage <file.varc>       print a salvage document
"""'''

ENCODE_DOC = '''"""Encode a VARC1 decode document back to segment bytes.

Usage:
  python3 encode.py <document.json> <output.varc>
"""'''


def _defined_names(node):
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, ast.Assign):
        return {t.id for t in node.targets if isinstance(t, ast.Name)}
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return {(a.asname or a.name).split(".")[0] for a in node.names}
    return set()


def _program_source(source, entry, doc, schema_blob):
    tree = ast.parse(source)
    by_name = {}
    for node in tree.body:
        for name in _defined_names(node):
            by_name[name] = node
    wanted = []
    pending = [entry]
    while pending:
        node = by_name.get(pending.pop())
        if node is None or node in wanted:
            continue
        wanted.append(node)
        pending.extend(n.id for n in ast.walk(node) if isinstance(n, ast.Name))
    wanted.sort(key=lambda n: n.lineno)
    parts = [doc, "from __future__ import annotations"]
    after_import = False
    for node in wanted:
        if _defined_names(node) == {"SCHEMA_JSON"}:
            text = "SCHEMA_JSON = " + repr(schema_blob)
        else:
            text = ast.get_source_segment(source, node)
        is_import = isinstance(node, (ast.Import, ast.ImportFrom))
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            spacing = "\n\n\n"
        else:
            spacing = "\n\n" if after_import and not is_import else "\n"
        after_import = is_import
        parts.append(spacing + text)
    parts.append(f'\n\n\nif __name__ == "__main__":\n    sys.exit({entry}(sys.argv[1:]))\n')
    return "\n".join(parts[:2]) + "\n" + "".join(parts[2:])


def build_programs(data_dir, decode_out, encode_out):
    blob = json.dumps(load_schema(data_dir), separators=(",", ":"))
    source = Path(__file__).read_text()
    Path(decode_out).write_text(_program_source(source, "decode_main", DECODE_DOC, blob))
    Path(encode_out).write_text(_program_source(source, "encode_main", ENCODE_DOC, blob))


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
    err_doc = {"cases": cases}
    (out_dir / "error_analysis.json").write_text(
        json.dumps(err_doc, sort_keys=True, separators=(",", ":")) + "\n")


def decode_main(argv):
    schema = Schema(json.loads(SCHEMA_JSON))
    if len(argv) == 2 and argv[0] == "--stream":
        manifest = json.loads(Path(argv[1]).read_text())
        print(json.dumps(decode_stream(manifest["segments"], schema)))
        return 0
    if len(argv) == 2 and argv[0] == "--salvage":
        print(json.dumps(salvage_one(Path(argv[1]).read_bytes(), schema)))
        return 0
    if len(argv) == 1:
        print(json.dumps(decode_one(Path(argv[0]).read_bytes(), schema)))
        return 0
    sys.stderr.write("usage: decode.py [--stream | --salvage] <path>\n")
    return 2


def encode_main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: encode.py <document.json> <output.varc>\n")
        return 2
    Path(argv[1]).write_bytes(encode_one(json.loads(Path(argv[0]).read_text())))
    return 0


def main(argv):
    if len(argv) == 4 and argv[0] == "--build":
        build_programs(argv[1], argv[2], argv[3])
        return 0
    if len(argv) == 3 and argv[0] == "--emit-reports":
        emit_reports(argv[1], argv[2])
        return 0
    sys.stderr.write("usage: solve.py --build <data> <decode> <encode> | "
                     "--emit-reports <data> <out>\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
