#!/usr/bin/env python3
"""VARC1 container encoder.

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
MODE_IDS = {"raw": 0, "delta": 1, "dict": 2, "reset": 3}


def write_uleb(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def write_sleb(value, length=None):
    out = bytearray()
    more = True
    while more:
        byte = value & 0x7F
        value >>= 7
        if (value == 0 and not byte & 0x40) or (value == -1 and byte & 0x40):
            more = False
        else:
            byte |= 0x80
        out.append(byte)
    if length is None or length == len(out):
        return bytes(out)
    if length < len(out):
        raise ValueError("delta_raw_len too small for delta")
    pad = 0x7F if out[-1] & 0x40 else 0x00
    out[-1] |= 0x80
    for _ in range(length - len(out) - 1):
        out.append(pad | 0x80)
    out.append(pad)
    return bytes(out)


def escape(body):
    out = bytearray()
    for byte in body:
        if byte in (SYNC, ESC):
            out.append(ESC)
            out.append(byte ^ 0x20)
        else:
            out.append(byte)
    return bytes(out)


def encode_frame(record):
    mode = record["mode"]
    long_key = bool(record["long_key"])
    has_ext = bool(record["ext_present"])
    selector = MODE_IDS[mode]
    if mode == "raw" and record["wide"]:
        selector |= 0x04
    if long_key:
        selector |= 0x08
    if has_ext:
        selector |= 0x10

    frame = bytearray([SYNC, selector])
    if long_key:
        key_bytes = record["key_str"].encode("utf-8")
        frame += write_uleb(len(key_bytes))
        frame += key_bytes
    else:
        frame.append(record["raw_key"])

    body = bytearray()
    if mode == "raw":
        size = 4 if record["wide"] else 2
        body += int(record["raw_value"]).to_bytes(size, "little", signed=True)
    elif mode == "delta":
        body += write_sleb(int(record["delta_raw"]), record["delta_raw_len"])
    elif mode == "dict":
        body.append(int(record["dict_index"]))
    if has_ext:
        for extension in record["extensions"]:
            payload = bytes.fromhex(extension["hex"])
            body += write_uleb(int(extension["type"]))
            body += write_uleb(len(payload))
            body += payload

    frame.append(sum(body) & 0xFF)
    escaped = escape(bytes(body))
    frame += write_uleb(len(escaped))
    frame += escaped
    return bytes(frame)


def encode_document(doc):
    records = doc["records"]
    header = bytearray(MAGIC)
    header.append(VERSION)
    header.append(1 if doc["flags"]["stream_continues"] else 0)
    header += int(doc["stream_id"]).to_bytes(2, "little")
    header += int(doc["seq_no"]).to_bytes(2, "little")
    header += len(records).to_bytes(2, "little")
    header.append(int(doc["revision"]))
    header += b"\x00\x00"
    out = bytearray(header)
    for record in records:
        out += encode_frame(record)
    out += (zlib.crc32(bytes(header[5:16])) & 0xFFFFFFFF).to_bytes(4, "little")
    return bytes(out)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write(__doc__)
        return 2
    with open(argv[1], "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    with open(argv[2], "wb") as handle:
        handle.write(encode_document(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
