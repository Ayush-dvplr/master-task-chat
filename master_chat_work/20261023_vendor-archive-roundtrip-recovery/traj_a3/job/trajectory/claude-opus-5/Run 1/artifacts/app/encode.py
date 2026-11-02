#!/usr/bin/env python3
"""VARC1 segment encoder.

Usage:
    python3 encode.py <document.json> <output.varc>
"""
import json
import sys
import zlib

MAGIC = b"VARC1"
VERSION = 2
SYNC = 0xAA
ESC = 0x1B
ESC_XOR = 0x20
MODE_IDS = {"raw": 0, "delta": 1, "dict": 2, "reset": 3}


def write_uleb(val):
    out = bytearray()
    while True:
        b = val & 0x7F
        val >>= 7
        if val:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def write_sleb(val, length=None):
    out = bytearray()
    more = True
    while more:
        b = val & 0x7F
        val >>= 7
        if (val == 0 and not b & 0x40) or (val == -1 and b & 0x40):
            more = False
        else:
            b |= 0x80
        out.append(b)
    if length is not None and length > len(out):
        pad = 0x7F if out[-1] & 0x40 else 0x00
        out[-1] |= 0x80
        for _ in range(length - len(out) - 1):
            out.append(pad | 0x80)
        out.append(pad)
    return bytes(out)


def escape_body(raw):
    out = bytearray()
    for b in raw:
        if b == SYNC or b == ESC:
            out.append(ESC)
            out.append(b ^ ESC_XOR)
        else:
            out.append(b)
    return bytes(out)


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def encode_extensions(exts):
    out = bytearray()
    for ext in exts:
        payload = bytes.fromhex(str(ext["hex"]).strip())
        out += write_uleb(int(ext["type"]))
        out += write_uleb(len(payload))
        out += payload
    return bytes(out)


def encode_frame(rec):
    mode_name = rec["mode"]
    mode = MODE_IDS[mode_name]
    long_key = bool(rec["long_key"])
    wide = bool(rec.get("wide")) and mode_name == "raw"
    exts = list(rec.get("extensions") or []) if rec.get("ext_present") else []

    body = bytearray()
    if mode_name == "raw":
        size = 4 if wide else 2
        mask = (1 << (size * 8)) - 1
        body += (int(rec["raw_value"]) & mask).to_bytes(size, "little")
    elif mode_name == "delta":
        length = rec.get("delta_raw_len")
        body += write_sleb(int(rec["delta_raw"]),
                           length if is_int(length) else None)
    elif mode_name == "dict":
        body.append(int(rec["dict_index"]) & 0xFF)
    body += encode_extensions(exts)

    selector = mode
    if wide:
        selector |= 0x04
    if long_key:
        selector |= 0x08
    if exts:
        selector |= 0x10

    frame = bytearray([SYNC, selector])
    if long_key:
        key_bytes = str(rec["key_str"]).encode("utf-8")
        frame += write_uleb(len(key_bytes))
        frame += key_bytes
    else:
        frame.append(int(rec["raw_key"]) & 0xFF)
    escaped = escape_body(bytes(body))
    frame.append(sum(body) & 0xFF)
    frame += write_uleb(len(escaped))
    frame += escaped
    return bytes(frame)


def encode_document(doc):
    records = doc.get("records") or []
    flags = 0
    if (doc.get("flags") or {}).get("stream_continues"):
        flags |= 0x01
    out = bytearray(MAGIC)
    out.append(VERSION)
    out.append(flags)
    out += (int(doc["stream_id"]) & 0xFFFF).to_bytes(2, "little")
    out += (int(doc["seq_no"]) & 0xFFFF).to_bytes(2, "little")
    out += (len(records) & 0xFFFF).to_bytes(2, "little")
    out.append(int(doc["revision"]) & 0xFF)
    out += b"\x00\x00"
    for rec in records:
        out += encode_frame(rec)
    out += (zlib.crc32(bytes(out[5:16])) & 0xFFFFFFFF).to_bytes(4, "little")
    return bytes(out)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: encode.py <document.json> <out.varc>\n")
        return 2
    with open(argv[1], "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    with open(argv[2], "wb") as fh:
        fh.write(encode_document(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
