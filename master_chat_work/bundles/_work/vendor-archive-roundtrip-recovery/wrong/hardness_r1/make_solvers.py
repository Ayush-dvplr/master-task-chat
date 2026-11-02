#!/usr/bin/env python3
"""Hardness audit r1: build wrong solvers as exact-string edits of the bundle's solve.py.

Each edit must match exactly once, so the only difference from the oracle is the
lever reading. Output: one <id>.py per solver beside this script.
Written independently from the contract (format_contract.md, escape_rules.md,
decoder_appendix.md, revision_notes.md) and DESIGN.md's named reflex structures.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/"
             "vendor-archive-roundtrip-recovery/solution/solve.py")

# ---- lever reflex edits (old, new) -------------------------------------------------
E = {}
# LV-VA-1 reflex: one fresh decoder state per file inside the --stream loop.
E["LV1"] = [("        carry = carries.setdefault(sid, {\"cum\": 0, \"res\": []})\n",
             "        carry = {\"cum\": 0, \"res\": []}  # reflex: fresh state per file\n")]
# LV-VA-2 reflex: encoder rebuilt from the decoded value fields only (extensions not folded back).
E["LV2"] = [("        exts = rec.get(\"extensions\") or []\n        sel = MODES.index",
             "        exts = []  # reflex: frame rebuilt from value fields only\n        sel = MODES.index")]
# LV-VA-2 variant: extensions kept but re-sorted by type.
E["LV2b"] = [("        exts = rec.get(\"extensions\") or []\n        sel = MODES.index",
              "        exts = sorted(rec.get(\"extensions\") or [], key=lambda e: e[\"type\"])\n        sel = MODES.index")]
# LV-VA-3 reflex (DESIGN W-VA3): unescape the whole frame region first, then walk frames
# with body_len taken over the already-unescaped bytes.
E["LV3"] = [
    ("    head = _head(data)\n    carry = carry if carry is not None else {\"cum\": 0, \"res\": []}\n",
     "    head = _head(data)\n    data = data[:HDR] + _unescape_all(data[HDR:len(data) - TRL]) + data[len(data) - TRL:]\n"
     "    carry = carry if carry is not None else {\"cum\": 0, \"res\": []}\n"),
    ("def _unescape(data, at, count):\n    stop = at + count\n",
     "def _unescape_all(buf):\n    out = bytearray()\n    i = 0\n    while i < len(buf):\n"
     "        if buf[i] == ESC_B and i + 1 < len(buf):\n            out.append(buf[i + 1] ^ 0x20)\n            i += 2\n"
     "        else:\n            out.append(buf[i])\n            i += 1\n    return bytes(out)\n\n\n"
     "def _unescape(data, at, count):\n    stop = at + count\n    if stop <= len(data):\n        return bytes(data[at:stop]), stop\n"),
]
# LV-VA-3 variant (TRUTH trap): no escaping at all (decoder never unescapes, encoder never escapes).
E["LV3b"] = [
    ("def _unescape(data, at, count):\n    stop = at + count\n",
     "def _unescape(data, at, count):\n    stop = at + count\n    if stop <= len(data):\n        return bytes(data[at:stop]), stop  # reflex: no unescape\n"),
    ("def _escape(raw):\n    buf = bytearray()\n",
     "def _escape(raw):\n    return bytes(raw)  # reflex: no escape\n    buf = bytearray()\n"),
]
# LV-VA-4 reflex: encoder always writes shortest LEB128 and the decoder reports the shortest length.
E["LV4"] = [
    ("            raw += _sv_pad(rec[\"delta_raw\"], size) if (size and size > len(short)) else short\n",
     "            raw += short  # reflex: always shortest\n"),
    ("        rec[\"delta_raw_len\"] = used\n",
     "        rec[\"delta_raw_len\"] = len(_sv_write(delta))  # reflex: length not remembered\n"),
]
# LV-VA-5 reflex (DESIGN W-VA5): integrity (CRC) checked right after the magic.
E["LV5"] = [("    ver = data[5] if len(data) > 5 else -1\n",
             "    if len(data) >= HDR + TRL and _crc(data) != struct.unpack(\"<I\", data[-TRL:])[0]:\n"
             "        return {\"error\": \"trailer_crc_mismatch\", \"expected\": _crc(data),\n"
             "                \"found\": struct.unpack(\"<I\", data[-TRL:])[0]}  # reflex: crc first\n"
             "    ver = data[5] if len(data) > 5 else -1\n")]
# LV-VA-5 variant: size sanity (record_count_overflow) checked before the reserved bytes.
E["LV5b"] = [("    if data[14] != 0:\n        return {\"error\": \"reserved_not_zero\", \"offset\": 14}\n",
              "    count0 = struct.unpack_from(\"<H\", data, 11)[0]\n"
              "    if len(data) - HDR - TRL < 0 or count0 * MIN_FRAME > len(data) - HDR - TRL:\n"
              "        return {\"error\": \"record_count_overflow\", \"record_count\": count0}  # reflex: size first\n"
              "    if data[14] != 0:\n        return {\"error\": \"reserved_not_zero\", \"offset\": 14}\n")]
# LV-VA-6 reflex: abort on the first bad frame (one damage entry to the trailer, no resync).
E["LV6"] = [("            resume = _scan_sync(data, at + 1, stop, carry, stream_id, revision, schema)\n",
             "            resume = None  # reflex: abort on first bad frame\n")]
# LV-VA-6 variant: resync to the first 0xAA byte without re-validating the frame there.
E["LV6b"] = [("            probe = {\"cum\": carry[\"cum\"], \"res\": list(carry[\"res\"])}\n            try:\n"
              "                _read_frame(data, at, probe, stream_id, revision, schema)\n                return at\n",
              "            probe = {\"cum\": carry[\"cum\"], \"res\": list(carry[\"res\"])}\n            try:\n"
              "                return at  # reflex: first sync byte accepted\n")]
# REMAP reflex: identity field ids under every revision.
E["REMAP"] = [("            canon = self.remap.get((revision, rec[\"raw_key\"]), rec[\"raw_key\"])\n",
               "            canon = rec[\"raw_key\"]  # reflex: identity remap\n")]
# Composition reflex CR1 (LV-VA-5 x LV-VA-6): salvage shares the decode early-return gate.
E["CR1"] = [("    defect = _header_error(data)\n    stream_id = struct.unpack_from",
             "    defect = _header_error(data)\n    if defect is not None:\n        return defect  # reflex: early return\n"
             "    stream_id = struct.unpack_from")]
# Contract-literal probe CUM: format_contract.md "The cumulator is set to the resolved value for
# raw, delta and dict frames" (solve.py and the verifier skip it for raw).
E["CUM"] = [("        rec[\"value\"] = rec[\"raw_value\"]\n        cur = size\n",
             "        rec[\"value\"] = rec[\"raw_value\"]\n        carry[\"cum\"] = rec[\"value\"]  # contract: raw sets cumulator\n        cur = size\n")]
# Downstream-isolation probe DS: stage-1 single-file decode broken (fields never named).
E["DS"] = [("    rec[\"field\"], rec[\"unit\"], rec[\"canonical_id\"] = schema.name_for(rec, stream_id, revision)\n",
            "    rec[\"field\"], rec[\"unit\"], rec[\"canonical_id\"] = None, None, None  # stage-1 wrong\n")]

PRIMARY = ["LV1", "LV2", "LV3", "LV4", "LV5", "LV6", "REMAP"]
# From the underivability run: primary reflexes that give identical output on all visible data.
# LV2, LV3, LV5 primary reflexes are DERIVABLE (a self-testing agent sees them fail), so S4 fixes them.
HIDDEN_ONLY = ["LV1", "LV4", "LV6", "REMAP"]

SOLVERS = {f"S3_{k}": [k] for k in PRIMARY}
SOLVERS.update({f"S3v_{k}": [k] for k in ("LV2b", "LV3b", "LV5b", "LV6b")})
SOLVERS["S2"] = PRIMARY + ["CR1"]
# S4: careful self-tester. Right on every rule the visible data can confirm; the natural
# reflex structure on every HIDDEN-ONLY lever and at the composition point (CR1).
SOLVERS["S4"] = HIDDEN_ONLY + ["CR1"]
SOLVERS["S4b"] = ["CR1"]
SOLVERS["PAIR_LV1_REMAP"] = ["LV1", "REMAP"]
SOLVERS["PAIR_LV3_LV4"] = ["LV3", "LV4"]
SOLVERS["DS"] = ["DS"]


def build(edits):
    src = SOLVE.read_text()
    for key in edits:
        for old, new in E[key]:
            n = src.count(old)
            assert n == 1, (key, n, old[:60])
            src = src.replace(old, new, 1)
    return src


def main(extra=None):
    table = dict(SOLVERS)
    if extra:
        table.update(extra)
    for sid, edits in table.items():
        (HERE / f"{sid}.py").write_text(build(edits))
    print("built", len(table), "solvers")


if __name__ == "__main__":
    import json
    import sys
    main(json.loads(sys.argv[1]) if len(sys.argv) > 1 else None)
