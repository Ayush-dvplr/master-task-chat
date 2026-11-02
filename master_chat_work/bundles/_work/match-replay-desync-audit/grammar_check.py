"""Re-derive the eleven control figures from the shipped notes alone (F1 proof).

Reads only <data_dir>: calibration.md (candidates, published figures and the
fragment recipes), charter-scale.md (word tables, mask rule), the .rpl
captures and roster-register.csv. It never imports tests/ or solution/.
CTRL-J needs the settled tick total of every surviving unit, which is a
settlement output rather than a fragment rule; it is read from the
scenario_visible.json in <report_dir> (any correct settlement run).

Usage: python3 -B grammar_check.py <data_dir> <report_dir>
Prints one line per control: pinned value, candidates matching, figure match.
"""

import hashlib
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

KEY = b"MRD-2031"
data = Path(sys.argv[1])
report = Path(sys.argv[2])

calib = (data / "calibration.md").read_text()
charter = (data / "charter-scale.md").read_text()

candidates = []  # (quantity, low, high, control)
for m in re.finditer(r"^\| `(\w+)` \| (\d+) through (\d+) \| (CTRL-\w) \|", calib, re.M):
    candidates.append((m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)))
published = dict(re.findall(r"^\| (CTRL-\w) \| `([0-9a-f]{12})` \|", calib, re.M))


def word_list(intro):
    seg = charter.split(intro, 1)[1].split(".\n", 1)[0]
    return re.findall(r"`([a-z]+)`", seg)


WORDS = word_list("The twenty four unit words, in the order the engine publishes them, are")
LABELS = word_list("The twelve label words, in the order the engine publishes them, are")
CLASSES = ["peak", "steady", "burst", "latency"]
assert len(WORDS) == 24 and len(LABELS) == 12


def mask(label, *nums):
    h = hashlib.sha256(KEY + label.encode() + b"".join(b":" + str(n).encode() for n in nums))
    return h.digest()[:12]


def stamp(fragments):
    h = hashlib.sha256(KEY + b"".join(b"|" + f.encode("utf-8") for f in fragments))
    return h.hexdigest()[:12]


def xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def rot_right(body, k):
    k %= len(body)
    return body[-k:] + body[:-k] if k else body


# captures
caps = []
for path in sorted(data.glob("*.rpl")):
    lines = path.read_text().splitlines()
    head = dict(kv.split("=", 1) for kv in lines[0].split()[1:])
    blocks = []
    for line in lines[1:]:
        if line.startswith("B "):
            _, o, w, c = line.split()
            blocks.append({"ordinal": int(o), "width": int(w), "lines": []})
        elif line.startswith("R "):
            blocks[-1]["lines"].append(bytes.fromhex(line.split()[1]))
    caps.append({"number": int(head["number"]), "flags": int(head["flags"], 16),
                 "frames": int(head["frames"]), "words": head["words"].split(","),
                 "blocks": blocks})
caps.sort(key=lambda c: c["number"])
assert [c["number"] for c in caps] == list(range(6))


def bit(cap, b):
    return bool(cap["flags"] >> b & 1)


SEALED, CHAINED, STEPPED, DRIFTED, WOVEN, ECHOED, FLIPPED, PADDED, SHADOWED, SPUN, ALIASED, WARDED = range(12)

# entry check label: the format note says only "a digest over the ten bytes that
# precede it"; the flag-zero captures settle which mask label it is.
def check_label():
    for label in ("entry", "check"):
        ok = all(mask(label, *p[:10])[:2] == p[10:12]
                 for c in caps if c["flags"] == 0 for b in c["blocks"] for p in b["lines"])
        if ok:
            return label
    raise SystemExit("no check label fits the flag-zero captures")


CHECK = check_label()


def unpack(p, little):
    if len(p) != 12 or mask(CHECK, *p[:10])[:2] != p[10:12]:
        return None
    o = "little" if little else "big"
    return [int.from_bytes(p[0:2], o), int.from_bytes(p[2:4], o), p[4],
            int.from_bytes(p[5:9], o), p[9]]


def entry_text(e):
    return "none" if e is None else "/".join(str(x) for x in e)


def weave_order(offset, number, block, width):
    seed = (offset + 97 * number + 7 * block) & 0xFFFFFFFF
    seed = (seed * 2654435761 + 1013904223) & 0xFFFFFFFF
    if seed == 0:
        seed = 2654435769
    order = list(range(width))
    for pos in range(width - 1, 0, -1):
        seed ^= (seed << 13) & 0xFFFFFFFF
        seed ^= seed >> 17
        seed ^= (seed << 5) & 0xFFFFFFFF
        j = seed % (pos + 1)
        order[pos], order[j] = order[j], order[pos]
    return order


def unward(p, s):
    out, i = bytearray(), 0
    while i < len(p):
        if p[i] == s:
            if i + 1 < len(p) and p[i + 1] == s:
                out.append(s)
                i += 2
                continue
            return None
        out.append(p[i])
        i += 1
    return bytes(out) if len(out) == 12 else None


def payload_lists(v, depth):
    """per capture: list of blocks, each list of payloads after CTRL-B..D steps"""
    res = []
    for c in caps:
        n = c["number"]
        blocks = []
        for b in c["blocks"]:
            ls = list(b["lines"])
            if bit(c, WOVEN):
                order = weave_order(v["weave_seed_offset"], n, b["ordinal"], len(ls))
                plain = [None] * len(ls)
                for p, line in enumerate(ls):
                    plain[order[p]] = line
                ls = plain
            if depth >= 3 and bit(c, WARDED):
                ls = [unward(p, v["sentinel_code_value"]) or bytes(12) for p in ls]
            if depth >= 4 and bit(c, DRIFTED):
                ctr = (b["ordinal"] + 1 + 5 * n) % v["drift_modulus"]
                ls = [xor(p, mask("drift", n, ctr)) for p in ls]
            blocks.append(ls)
        res.append(blocks)
    return res


def flipped_block(c):
    return c["number"] % len(c["blocks"]) if bit(c, FLIPPED) else None


def entries(v, c, blocks):
    n = c["number"]
    blks = [list(b) for b in blocks]
    if bit(c, SHADOWED):
        filler = v["shadow_pad_base"] - 3
        blks[0] = blks[0][:max(0, len(blks[0]) - filler)]
    out, prev, idx = [], (0, 0), 0
    for bo, b in enumerate(blks):
        for p in b:
            if bit(c, CHAINED):
                p = xor(p, mask("chain", n, prev[0], prev[1]))
            if bit(c, SEALED):
                p = xor(p, mask(LABELS[v["seal_label_index"]], n, idx))
            if bit(c, SPUN):
                p = rot_right(p, ((idx + 1) * v["spin_modulus"]) % 12)
            e = unpack(p, bo == flipped_block(c))
            out.append(e)
            prev = (0, 0) if e is None else (e[0], e[3])
            idx += 1
    return out


def lifted(v, c, es):
    if bit(c, STEPPED):
        stored = [0 if e is None else e[0] for e in es]
        ticks = []
        for i, s in enumerate(stored):
            if i == 0:
                t = s
            elif i == 1:
                t = s + ticks[0]
            else:
                t = s + 2 * ticks[-1] - ticks[-2]
            ticks.append(t % 65536)
    else:
        ticks = [None if e is None else e[0] for e in es]
    if bit(c, ALIASED):
        shift = v["alias_donor_shift"]
        donor = caps[(c["number"] + shift) % 6]["words"]
        table = donor[shift % len(donor):] + donor[:shift % len(donor)]
    else:
        table = WORDS
    return [None if e is None else [ticks[i], table[e[1] % len(table)], e[2], e[3], e[4]]
            for i, e in enumerate(es)]


def echoes(v, c, ws):
    ws = [None if w is None else list(w) for w in ws]
    if not bit(c, ECHOED):
        return ws
    span = v["echo_window_span"]
    for i, w in enumerate(ws):
        if w is None or w[2] != 224:
            continue
        d = i % (span - 1) + 1
        if i - d < 0 or ws[i - d] is None:
            continue
        src = ws[i - d]
        ws[i] = [w[0], src[1], src[2], src[3], src[4]]
    return ws


def fragments(control, v):
    if control == "CTRL-A":
        lim = v["frame_bias_limit"]
        return ["%d:%d" % (c["number"], (3 * c["number"] + 1) % lim if bit(c, PADDED) else 0) for c in caps]
    depth = "ABCDEFGHI".index(control[-1]) + 1
    pls = payload_lists(v, min(depth, 4))
    if depth <= 4:
        return ["%d:%s" % (c["number"], ",".join(p.hex() for b in bl for p in b)) for c, bl in zip(caps, pls)]
    if depth in (5, 6):
        out = []
        for c, bl in zip(caps, pls):
            n, head = c["number"], bl[0][0]
            if bit(c, CHAINED):
                head = xor(head, mask("chain", n, 0, 0))
            if bit(c, SEALED):
                head = xor(head, mask(LABELS[v["seal_label_index"]], n, 0))
            if depth == 5:
                out.append("%d:%s" % (n, head.hex()))
                continue
            if bit(c, SPUN):
                head = rot_right(head, v["spin_modulus"] % 12)
            out.append("%d:%s" % (n, entry_text(unpack(head, flipped_block(c) == 0))))
        return out
    out = []
    for c, bl in zip(caps, pls):
        es = entries(v, c, bl)
        if depth >= 8:
            es = lifted(v, c, es)
        if depth >= 9:
            es = echoes(v, c, es)
        out.append("%d:%s" % (c["number"], ",".join(entry_text(e) for e in es)))
    return out


def j_fragments(v):
    units = json.loads((report / "scenario_visible.json").read_text())["units"]
    return ["%s:%s" % (u["unit"], CLASSES[(u["tick_total"] // v["cadence_modulus"]) % 4])
            for u in sorted(units, key=lambda u: u["unit"])]


def k_fragments(v):
    rows = (data / "roster-register.csv").read_text().splitlines()[1:]
    base = sum(int(r.split(",")[2]) for r in rows if r)
    t = Fraction(v["upkeep_target_scale"] * base)
    return ["%d/%d" % (t.numerator, t.denominator)]


pinned, ok_all = {}, True
for q, lo, hi, ctrl in candidates:
    hits = []
    for cand in range(lo, hi + 1):
        trial = dict(pinned, **{q: cand})
        if ctrl == "CTRL-J":
            fr = j_fragments(trial)
        elif ctrl == "CTRL-K":
            fr = k_fragments(trial)
        else:
            fr = fragments(ctrl, trial)
        if stamp(fr) == published[ctrl]:
            hits.append(cand)
    pinned[q] = hits[0] if hits else None
    ok = bool(hits)
    ok_all &= ok
    print("%s %-22s hits=%s %s" % (ctrl, q, hits, "MATCH" if ok else "NO MATCH"))
print("check label:", CHECK)
print("RESULT %d/11" % sum(1 for q, *_ in candidates if pinned[q] is not None))
print(json.dumps(pinned))
