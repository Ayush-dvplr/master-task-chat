#!/usr/bin/env python3
"""Build /app/out/decoded_examples.jsonl and the three report files."""

import csv
import hashlib
import json
import sys

sys.path.insert(0, sys.argv[1])

import decode  # noqa: E402
import encode  # noqa: E402

DATA = sys.argv[2]
OUT = sys.argv[1] + "/out"


def record(mode, key, **kwargs):
    """Build an encoder-ready record; key is an int short key or a str name."""
    rec = {
        "raw_key": key if isinstance(key, int) else None,
        "long_key": isinstance(key, str),
        "mode": mode,
        "wide": kwargs.get("wide") if mode == "raw" else None,
        "ext_present": bool(kwargs.get("extensions")),
        "extensions": kwargs.get("extensions", []),
    }
    if isinstance(key, str):
        rec["key_str"] = key
    if mode == "raw":
        rec["raw_value"] = kwargs["raw_value"]
    elif mode == "delta":
        rec["delta_raw"] = kwargs["delta_raw"]
        rec["delta_raw_len"] = kwargs.get("delta_raw_len")
    elif mode == "dict":
        rec["dict_index"] = kwargs["dict_index"]
    return rec


def segment(stream_id, seq_no, revision, continues, records):
    return {"stream_id": stream_id, "seq_no": seq_no, "revision": revision,
            "flags": {"stream_continues": continues}, "records": records}


def examples():
    out = []

    out.append(("telemetry_basic", segment(7, 0, 3, False, [
        record("raw", 17, wide=False, raw_value=4096),
        record("delta", 17, delta_raw=-300),
        record("raw", 200, wide=True, raw_value=-1234567),
        record("dict", 42, dict_index=2),
    ])))

    out.append(("mixed_modes_reset", segment(12, 1, 0, True, [
        record("raw", 11, wide=True, raw_value=70000),
        record("delta", 11, delta_raw=321),
        record("reset", 3),
        record("raw", 250, wide=False, raw_value=-32768),
        record("delta", 250, delta_raw=32767),
        record("dict", 250, dict_index=0),
        record("reset", "shutdown_marker"),
    ])))

    out.append(("opaque_payload_frames", segment(3, 0, 5, False, [
        record("raw", 111, wide=False, raw_value=-21989,
               extensions=[{"type": 9, "hex": "aa011b"}]),
        record("delta", 23, delta_raw=170,
               extensions=[{"type": 1, "hex": "00ff"},
                           {"type": 2, "hex": ""},
                           {"type": 4096, "hex": "1baa1b20"}]),
        record("dict", 102, dict_index=1,
               extensions=[{"type": 3, "hex": "6f6b"}]),
        record("reset", 7, extensions=[{"type": 77, "hex": "aaaa"}]),
    ])))

    out.append(("long_key_mixture", segment(21, 2, 1, False, [
        record("raw", "freq_2100", wide=True, raw_value=123456),
        record("delta", "unregistered_probe_7", delta_raw=-7),
        record("raw", "pressure_0001", wide=False, raw_value=-1),
        record("dict", "freq_2100", dict_index=2),
    ])))

    out.append(("padded_delta_memory", segment(40, 0, 2, True, [
        record("raw", 1, wide=False, raw_value=1000),
        record("delta", 2, delta_raw=-2251, delta_raw_len=3),
        record("delta", 3, delta_raw=5, delta_raw_len=4),
        record("delta", 4, delta_raw=0, delta_raw_len=1),
        record("delta", 5, delta_raw=-1, delta_raw_len=5),
        record("dict", 6, dict_index=4),
    ])))

    out.append(("remapped_short_keys", segment(9, 3, 6, False, [
        record("raw", 1, wide=True, raw_value=2000000),
        record("delta", 2, delta_raw=-500000),
        record("dict", 3, dict_index=1),
        record("reset", 4),
        record("raw", 5, wide=False, raw_value=77),
    ])))

    lines = []
    for name, doc in out:
        data = encode.encode_document(doc)
        decoded = decode.decode_segment(data)
        assert "error" not in decoded, (name, decoded)
        assert encode.encode_document(decoded) == data, name
        lines.append({"name": name, "hex": data.hex(), "decoded": decoded})
    return lines


def write_examples(lines):
    with open("%s/decoded_examples.jsonl" % OUT, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")


def roundtrip_report(lines):
    entries = []
    for line in lines:
        data = bytes.fromhex(line["hex"])
        rebuilt = encode.encode_document(line["decoded"])
        entries.append({
            "name": line["name"],
            "input_sha256": hashlib.sha256(data).hexdigest(),
            "rebuilt_sha256": hashlib.sha256(rebuilt).hexdigest(),
            "byte_length": len(data),
            "roundtrip_equal": data == rebuilt,
        })
    return {"all_roundtrips_equal": all(e["roundtrip_equal"] for e in entries),
            "examples": entries}


def error_analysis(lines):
    data = bytearray(bytes.fromhex(lines[0]["hex"]))

    def damaged(*defects):
        buf = bytearray(data)
        if "magic" in defects:
            buf[0] ^= 0xFF
        if "version" in defects:
            buf[5] = 9
        if "reserved" in defects:
            buf[14] = 1
        if "count" in defects:
            buf[11:13] = (65535).to_bytes(2, "little")
        if "crc" in defects:
            buf[-1] ^= 0xFF
        return decode.decode_segment(bytes(buf))

    return {"cases": {
        "bad_magic": damaged("magic"),
        "unsupported_version": damaged("version"),
        "reserved_not_zero": damaged("reserved"),
        "record_count_overflow": damaged("count"),
        "trailer_crc_mismatch": damaged("crc"),
        "all_defects": damaged("magic", "version", "reserved", "count", "crc"),
    }}


def format_report():
    with open("%s/field_layouts.csv" % DATA, newline="") as handle:
        layouts = {int(r["canonical_id"]): r for r in csv.DictReader(handle)}
    counts = {"raw": 0, "delta": 0, "dict": 0, "reset": 0}
    errors = {}
    ok_count = 0
    total = 0
    frames = 0
    streams = set()
    field_names = set()
    canonical_ids = set()
    with open("%s/capture_catalog.jsonl" % DATA, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            total += 1
            doc = decode.decode_segment(bytes.fromhex(json.loads(line)["hex"]))
            if "error" in doc:
                errors[doc["error"]] = errors.get(doc["error"], 0) + 1
                continue
            ok_count += 1
            streams.add(doc["stream_id"])
            frames += len(doc["records"])
            for rec in doc["records"]:
                counts[rec["mode"]] += 1
                if rec["field"] is not None:
                    field_names.add(rec["field"])
                if rec["canonical_id"] is not None:
                    canonical_ids.add(rec["canonical_id"])
    names_text = "\n".join(sorted(field_names))
    units_text = "\n".join(sorted(
        "%s\t%s" % (layouts[cid]["name"], layouts[cid]["unit"])
        for cid in canonical_ids))
    return {
        "format_tag": "VARC",
        "magic_hex": "5641524331",
        "version": 2,
        "header_size": 16,
        "trailer_size": 4,
        "sync_byte": "aa",
        "esc_byte": "1b",
        "crc_coverage": "header",
        "crc_covers_offsets": [5, 15],
        "mode_ids": {"raw": 0, "delta": 1, "dict": 2, "reset": 3},
        "catalog_count": total,
        "catalog_ok_count": ok_count,
        "catalog_error_count": total - ok_count,
        "catalog_mode_counts": counts,
        "stream_count": len(streams),
        "catalog_frame_count": frames,
        "catalog_errors": errors,
        "distinct_field_count": len(field_names),
        "field_name_sha256": hashlib.sha256(names_text.encode()).hexdigest(),
        "field_unit_sha256": hashlib.sha256(units_text.encode()).hexdigest(),
    }


def main():
    lines = examples()
    write_examples(lines)
    for name, payload in (("roundtrip_report.json", roundtrip_report(lines)),
                          ("error_analysis.json", error_analysis(lines)),
                          ("format_report.json", format_report())):
        with open("%s/%s" % (OUT, name), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
    print("wrote %d examples" % len(lines))


if __name__ == "__main__":
    main()
