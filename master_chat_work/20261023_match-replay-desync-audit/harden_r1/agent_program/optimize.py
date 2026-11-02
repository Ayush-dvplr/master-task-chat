#!/usr/bin/env python3
"""Settle a Ninefold Marches match from its replay captures.

    optimize.py <capture-dir> <report-dir>

The eleven quantities the engine withholds are recovered from the calibration
notes found in the capture directory on every run. Every amount, share, stock
and target is carried as an exact rational.
"""
import csv
import hashlib
import json
import os
import re
import sys
from fractions import Fraction

ENGINE_KEY = b"MRD-2031"
M32 = 0xFFFFFFFF
ECHO_KIND = 224
REVERSAL = 3

SEALED, CHAINED, STEPPED, DRIFTED, WOVEN, ECHOED = (1 << i for i in range(6))
FLIPPED, PADDED, SHADOWED, SPUN, ALIASED, WARDED = (
    1 << i for i in range(6, 12))


# ---------------------------------------------------------------- digests

def mask(label, nums):
    """A keyed mask: twelve bytes of a digest over the engine key, the mask
    label, and each number it covers in decimal preceded by a colon."""
    h = hashlib.sha256()
    h.update(ENGINE_KEY)
    h.update(label.encode())
    for x in nums:
        h.update(b":")
        h.update(str(x).encode())
    return h.digest()[:12]


def control(fragments):
    """A control figure: twelve hex characters of a digest over the engine key
    and every fragment, each preceded by a vertical bar."""
    h = hashlib.sha256()
    h.update(ENGINE_KEY)
    for f in fragments:
        h.update(b"|")
        h.update(str(f).encode("utf-8"))
    return h.hexdigest()[:12]


def xorb(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def rot_right(b, r):
    r %= len(b)
    return b if r == 0 else b[-r:] + b[:-r]


# ------------------------------------------------------------ shipped notes

def find_file(dirpath, *keywords):
    for name in sorted(os.listdir(dirpath)):
        low = name.lower()
        if all(k in low for k in keywords):
            return os.path.join(dirpath, name)
    raise SystemExit("no file matching %s under %s"
                     % ("+".join(keywords), dirpath))


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def paragraph(text, marker):
    i = text.index(marker)
    start = text.rfind("\n\n", 0, i)
    start = 0 if start < 0 else start + 2
    end = text.find("\n\n", i)
    return text[start:len(text) if end < 0 else end]


def backticked(text):
    return re.findall(r"`([a-z][a-z_]*)`", text)


def parse_tables(text):
    """The published word tables: unit words, label words, charters and the
    cadence classes, each in the order the engine publishes them."""
    words = backticked(paragraph(text, "unit words"))
    labels = backticked(paragraph(text, "label words"))
    charters = backticked(paragraph(text, "charters are"))
    cadences = backticked(paragraph(text, "cadence classes"))
    for name, lst in (("unit words", words), ("label words", labels),
                      ("charters", charters), ("cadence classes", cadences)):
        if not lst:
            raise SystemExit("the notes publish no %s" % name)
    return words, labels, charters, cadences


def parse_calibration(text):
    """The withheld quantities with their candidate sets and control names, in
    published order, and the published figure of every control."""
    quantities = []
    figures = {}
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) >= 3:
            m = re.match(r"`(\w+)`$", cells[0])
            r = re.match(r"(\d+)\s+through\s+(\d+)$", cells[1])
            if m and r:
                quantities.append({
                    "name": m.group(1),
                    "control": cells[2],
                    "candidates": list(range(int(r.group(1)),
                                             int(r.group(2)) + 1)),
                })
                continue
        if len(cells) == 2 and re.match(r"CTRL-\w+$", cells[0]):
            f = re.match(r"`([0-9a-f]+)`$", cells[1])
            if f:
                figures[cells[0]] = f.group(1)
    if not quantities or not figures:
        raise SystemExit("the calibration notes publish no slice")
    return quantities, figures


def load_roster(path):
    rows, order = {}, []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            word = r["word"].strip()
            rows[word] = {
                "word": word,
                "charter": r["charter"].strip(),
                "opened": int(r["opened"]),
                "closed": int(r["closed"]) if r["closed"].strip() else 0,
                "successor": r["successor"].strip(),
            }
            order.append(word)
    return rows, order


def load_windows(path):
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.append({"window": r["window"].strip(),
                        "first": int(r["first_tick"]),
                        "last": int(r["last_tick"]),
                        "live": int(r["live"]) != 0})
    return out


def load_bench(path):
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.append((r["word"].strip(), int(r["upkeep"])))
    return out


# -------------------------------------------------------------- containers

def parse_capture(path):
    hdr, blocks, cur = {}, [], None
    with open(path, encoding="utf-8") as fh:
        lines = [l.rstrip("\n") for l in fh if l.strip()]
    toks = lines[0].split()
    if toks[0] != "#RPL1":
        raise SystemExit("%s is not an RPL1 capture" % path)
    for t in toks[1:]:
        k, v = t.split("=", 1)
        hdr[k] = v
    for l in lines[1:]:
        p = l.split()
        if p[0] == "B":
            cur = {"ordinal": int(p[1]), "width": int(p[2]), "check": p[3],
                   "rows": []}
            blocks.append(cur)
        else:
            cur["rows"].append(p[1])
    hdr["number"] = int(hdr["number"])
    hdr["flags"] = int(hdr["flags"], 16)
    hdr["blocks"] = int(hdr["blocks"])
    hdr["frames"] = int(hdr["frames"])
    hdr["words"] = hdr["words"].split(",")
    return {"hdr": hdr, "blocks": blocks, "stem": hdr["capture"],
            "number": hdr["number"], "flags": hdr["flags"]}


def load_captures(dirpath):
    caps = [parse_capture(os.path.join(dirpath, n))
            for n in sorted(os.listdir(dirpath)) if n.endswith(".rpl")]
    if not caps:
        raise SystemExit("no captures under %s" % dirpath)
    caps.sort(key=lambda c: c["number"])
    return caps


def true_entry_count(cap):
    """The number of entries a capture truly carries, read back from the
    header seal over the capture ordinal and that count."""
    want = cap["hdr"]["seal"]
    rows = sum(len(b["rows"]) for b in cap["blocks"])
    for cnt in range(rows, -1, -1):
        if mask("seal", [cap["number"], cnt]).hex()[:len(want)] == want:
            return cnt
    raise SystemExit("the seal of %s names no entry count" % cap["stem"])


# --------------------------------------------------------------- transforms

def weave_order(offset, number, block_ord, width):
    """The finished order the shuffle records for a block."""
    s = offset + 97 * number + 7 * block_ord
    s = (s * 2654435761 + 1013904223) & M32
    if s == 0:
        s = 2654435769
    state = s

    def draw():
        nonlocal state
        x = state
        x ^= (x << 13) & M32
        x &= M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        x &= M32
        state = x
        return x

    order = list(range(width))
    for i in range(width - 1, 0, -1):
        j = draw() % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def invert(order):
    inv = [0] * len(order)
    for pos, val in enumerate(order):
        inv[val] = pos
    return inv


def unescape(hexs, sentinel):
    """Undo the ward: a reserved byte written twice stands for one."""
    raw = bytes.fromhex(hexs)
    out = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] == sentinel:
            if i + 1 >= len(raw) or raw[i + 1] != sentinel:
                return None
            out.append(sentinel)
            i += 2
        else:
            out.append(raw[i])
            i += 1
    return bytes(out)


def restored_lines(cap, offset):
    """Per block, the wire payload lines with the weave restored."""
    out = []
    for b in cap["blocks"]:
        rows = b["rows"]
        if cap["flags"] & WOVEN:
            order = invert(weave_order(offset, cap["number"], b["ordinal"],
                                       b["width"]))
        else:
            order = list(range(b["width"]))
        if any(p >= len(rows) for p in order):
            return None
        out.append((b["ordinal"], [rows[p] for p in order]))
    return out


def lifted_blocks(cap, offset, sentinel, drift_mod=None):
    """Per block, the twelve byte payloads with the ward lifted and the weave
    restored, and the block mask lifted when a drift modulus is given."""
    blocks = restored_lines(cap, offset)
    if blocks is None:
        return None
    out = []
    for bord, lines in blocks:
        vals = []
        for line in lines:
            raw = unescape(line, sentinel) if (cap["flags"] & WARDED) \
                else bytes.fromhex(line)
            if raw is None or len(raw) != 12:
                return None
            vals.append(raw)
        if drift_mod is not None and (cap["flags"] & DRIFTED):
            ctr = (bord + 1 + 5 * cap["number"]) % drift_mod
            key = mask("drift", [cap["number"], ctr])
            vals = [xorb(v, key) for v in vals]
        out.append((bord, vals))
    return out


def check_ok(raw):
    """The check field is a digest over the ten bytes that precede it."""
    return mask("entry", list(raw[0:10]))[:2] == raw[10:12]


def unflip(raw):
    """Restate a little endian payload as big endian."""
    return (raw[0:2][::-1] + raw[2:4][::-1] + raw[4:5] + raw[5:9][::-1]
            + raw[9:10] + raw[10:12][::-1])


def flipped_block(cap):
    if not (cap["flags"] & FLIPPED):
        return None
    return cap["number"] % cap["hdr"]["blocks"]


def decode_capture(cap, q, true_count=None):
    """Every true entry of a capture, byte decoded: the ward lifted, the weave
    restored, the block, label and chain masks lifted, the spin set straight,
    the filler set aside, the flipped block set to big endian and the stepped
    tick series accumulated.

    The chain mask reads the tick field as written rather than the accumulated
    tick. Unit indices are not yet read against a table and echoes are not yet
    resolved.
    """
    blocks = lifted_blocks(cap, q["weave_seed_offset"],
                           q["sentinel_code_value"], q["drift_modulus"])
    if blocks is None:
        return None
    payloads = []
    for bord, vals in blocks:
        vs = vals
        if bord == 0 and (cap["flags"] & SHADOWED):
            n = q["shadow_pad_base"] - 3
            if n < 0 or n >= len(vs):
                return None
            vs = vs[:len(vs) - n]
        payloads.extend((bord, v) for v in vs)
    if true_count is not None and len(payloads) != true_count:
        return None

    label = q["_labels"][q["seal_label_index"]]
    flipped = flipped_block(cap)
    out = []
    prev_t = prev_a = 0
    tick = diff = 0
    for e, (bord, p) in enumerate(payloads):
        x = p
        if cap["flags"] & SEALED:
            x = xorb(x, mask(label, [cap["number"], e]))
        if cap["flags"] & CHAINED:
            x = xorb(x, mask("chain", [cap["number"], prev_t, prev_a]))
        if cap["flags"] & SPUN:
            x = rot_right(x, (e + 1) * q["spin_modulus"] % 12)
        if not check_ok(x):
            return None
        raw = unflip(x) if flipped == bord else x
        f_tick = int.from_bytes(raw[0:2], "big")
        amount = int.from_bytes(raw[5:9], "big")

        if cap["flags"] & STEPPED:
            if e == 0:
                tick = f_tick
            elif e == 1:
                diff = f_tick
                tick = (tick + diff) & 0xFFFF
            else:
                diff = (diff + f_tick) & 0xFFFF
                tick = (tick + diff) & 0xFFFF
        else:
            tick = f_tick

        out.append({"ordinal": e, "block": bord, "tick": tick,
                    "field_tick": f_tick,
                    "unit": int.from_bytes(raw[2:4], "big"),
                    "kind": raw[4], "amount": amount, "mark": raw[9]})
        prev_t = f_tick
        prev_a = amount
    return out


def resolve_echoes(entries, span):
    """An echo takes the unit, kind, amount and mark of the entry its distance
    earlier while keeping its own tick."""
    if span < 2:
        return None
    out = []
    for e, ent in enumerate(entries):
        new = dict(ent)
        new["echo"] = False
        if ent["kind"] == ECHO_KIND:
            src = e - ((e % (span - 1)) + 1)
            if src < 0:
                return None
            s = out[src]
            new.update({"unit": s["unit"], "kind": s["kind"],
                        "amount": s["amount"], "mark": s["mark"],
                        "echo": True})
        out.append(new)
    return out


def alias_table(cap, by_number, ring_size, shift, words):
    """The word list a capture's unit index selects from. An aliased capture
    indexes the donor capture's published list rotated left by the shift."""
    if not (cap["flags"] & ALIASED):
        return words
    donor = by_number.get((cap["number"] + shift) % ring_size)
    if donor is None:
        return None
    lst = donor["hdr"]["words"]
    r = shift % len(lst)
    return lst[r:] + lst[:r]


# -------------------------------------------------------------- settlement

def resolve_identity(word, tick, roster):
    """Chase a recorded word to the identity in force at a tick. Returns
    (canonical word, canonical charter, depth), or None when the entry reaches
    a retired word and leaves the simulation."""
    cur, depth = word, 0
    while True:
        row = roster.get(cur)
        if row is None:
            return None
        if row["successor"] == cur:          # a cycle, settled first of all
            return cur, row["charter"], depth
        if row["closed"] == 0 or tick <= row["closed"]:
            return cur, row["charter"], depth
        if not row["successor"]:
            return None
        cur = row["successor"]
        depth += 1


def in_live_window(tick, windows):
    for w in windows:
        if w["live"] and w["first"] <= w["last"] \
                and w["first"] <= tick <= w["last"]:
            return True
    return False


def charter_baselines(roster, order, charters):
    base = {c: 0 for c in charters}
    count = {c: 0 for c in charters}
    for w in order:
        row = roster[w]
        base[row["charter"]] = base.get(row["charter"], 0) + row["opened"]
        count[row["charter"]] = count.get(row["charter"], 0) + 1
    return base, count


def settling_passes(roster, order):
    """Sweeps over the register until no canonical charter is stale. The sweep
    that finds nothing stale proves stability and counts as a pass."""
    canon = {w: roster[w]["charter"] for w in order}
    passes = 0
    while True:
        passes += 1
        stale = 0
        for w in order:
            row = roster[w]
            if row["successor"] and row["successor"] != w \
                    and row["closed"] != 0 and row["successor"] in canon:
                want = canon[row["successor"]]
            else:
                want = row["charter"]
            if canon[w] != want:
                canon[w] = want
                stale += 1
        if stale == 0:
            return passes


def cancel(walk, scope="earliest"):
    """Resolve the reversals of every canonical unit. A reversal cancels the
    still uncancelled entry of the kind its mark names recorded by the same
    canonical unit; a reversal that cancels nothing counts as an entry of that
    kind and joins the pool."""
    for e in walk:
        e["cancelled"] = False
        e["promoted"] = False
        e["settled_kind"] = e["kind"]
    pools = {}
    promoted = []
    for pos, e in enumerate(walk):
        if e["kind"] == REVERSAL:
            pool = pools.setdefault((e["canon"], e["mark"]), [])
            if pool:
                victim = pool.pop(0 if scope == "earliest" else -1)
                walk[victim]["cancelled"] = True
                e["cancelled"] = True
            else:
                e["promoted"] = True
                e["settled_kind"] = e["mark"]
                promoted.append(pos)
                pool.append(pos)
        else:
            pools.setdefault((e["canon"], e["kind"]), []).append(pos)
    return promoted


def first_divergence(walk):
    """The walk position of the earliest entry at which cancelling the earliest
    uncancelled entry of its kind and cancelling the most recent one would
    strike different entries."""
    early, late = {}, {}
    for pos, e in enumerate(walk):
        if e["kind"] == REVERSAL:
            key = (e["canon"], e["mark"])
            pe = early.setdefault(key, [])
            pl = late.setdefault(key, [])
            if pe:
                if pe[0] != pl[-1]:
                    return pos, e["tick"]
                pe.pop(0)
                pl.pop(-1)
            else:
                pe.append(pos)
                pl.append(pos)
        else:
            key = (e["canon"], e["kind"])
            early.setdefault(key, []).append(pos)
            late.setdefault(key, []).append(pos)
    return None, None


def solve_stocks(charters, baselines, shares):
    """The unique stable assignment of charter stocks, solved exactly.

    stock[c] = baseline[c] + sum over the other charters of that charter's
    stock multiplied by the share it gives to c.
    """
    n = len(charters)
    idx = {c: i for i, c in enumerate(charters)}
    rows = []
    for c in charters:
        row = [Fraction(0)] * (n + 1)
        row[idx[c]] = Fraction(1)
        for o in charters:
            if o != c and shares.get((o, c)):
                row[idx[o]] -= shares[(o, c)]
        row[n] = Fraction(baselines[c])
        rows.append(row)
    for col in range(n):
        piv = next((r for r in range(col, n) if rows[r][col] != 0), None)
        if piv is None:
            raise SystemExit("the charter relations admit no unique stocks")
        rows[col], rows[piv] = rows[piv], rows[col]
        pv = rows[col][col]
        rows[col] = [x / pv for x in rows[col]]
        for r in range(n):
            if r != col and rows[r][col] != 0:
                f = rows[r][col]
                rows[r] = [a - f * b for a, b in zip(rows[r], rows[col])]
    return {c: rows[idx[c]][n] for c in charters}


def bench_subset(bench, target):
    """The one subset of the bench candidates whose upkeep meets the target."""
    reach = {0: None}
    for i, (_, up) in enumerate(bench):
        for s in list(reach):
            t = s + up
            if t <= target and t not in reach:
                reach[t] = (s, i)
    if target not in reach:
        return None
    picked = []
    s = target
    while reach[s] is not None:
        prev, i = reach[s]
        picked.append(bench[i][0])
        s = prev
    return sorted(picked)


def settle(ctx, q):
    """Decode and settle the whole capture set. Returns None when the
    quantities on offer do not decode the set."""
    caps = ctx["caps"]
    decoded = {}
    for cap in caps:
        d = decode_capture(cap, q, ctx["true"][cap["number"]])
        if d is None:
            return None
        r = resolve_echoes(d, q["echo_window_span"])
        if r is None or any(e["kind"] > REVERSAL for e in r):
            return None
        decoded[cap["number"]] = r

    tables = {}
    for cap in caps:
        t = alias_table(cap, ctx["by_number"], len(caps),
                        q["alias_donor_shift"], ctx["words"])
        if t is None:
            return None
        tables[cap["number"]] = t

    entries = []
    for cap in caps:
        n = cap["number"]
        for e in decoded[n]:
            if e["unit"] >= len(tables[n]):
                return None
            entries.append({"capture": n, "ordinal": e["ordinal"],
                            "tick": e["tick"], "kind": e["kind"],
                            "amount": e["amount"], "mark": e["mark"],
                            "word": tables[n][e["unit"]]})

    roster, order = ctx["roster"], ctx["order"]
    windows = ctx["windows"]
    surviving, dropped_retired, dropped_offwindow = [], [], []
    depths = {}
    for en in entries:
        r = resolve_identity(en["word"], en["tick"], roster)
        if r is None:
            dropped_retired.append(en)
            continue
        canon, charter, depth = r
        if depth > depths.get(en["word"], -1):
            depths[en["word"]] = depth
        if not in_live_window(en["tick"], windows):
            dropped_offwindow.append(en)
            continue
        e2 = dict(en)
        e2.update({"canon": canon, "charter": charter, "depth": depth})
        surviving.append(e2)

    walk = sorted(surviving, key=lambda e: (e["tick"], e["capture"],
                                            e["ordinal"]))
    promoted = cancel(walk, "earliest")
    div_pos, div_tick = first_divergence(walk)

    base, count = ctx["baselines"], ctx["unit_counts"]
    caps_by_charter = {c: Fraction(base[c] * count[c]) for c in ctx["charters"]}

    settled = [e for e in walk if not e["cancelled"]]
    for e in settled:
        limit = caps_by_charter[e["charter"]]
        raw = Fraction(e["amount"])
        e["settled_amount"] = limit if raw >= limit else raw
        e["surplus"] = raw - e["settled_amount"]

    ticks, amounts, charters_of, kinds = {}, {}, {}, {}
    for e in settled:
        u = e["canon"]
        ticks[u] = ticks.get(u, 0) + e["tick"]
        amounts[u] = amounts.get(u, Fraction(0)) + e["settled_amount"]
        charters_of[u] = e["charter"]
        k = e["settled_kind"]
        if k in (0, 1, 2):
            kk = kinds.setdefault(u, [Fraction(0)] * 3)
            kk[k] += e["settled_amount"]

    base_sum = sum(base.values())
    pair = {}
    for e in settled:
        if e["settled_kind"] != 1:
            continue
        opened = roster[e["word"]]["charter"]
        if opened != e["charter"]:
            key = (opened, e["charter"])
            pair[key] = pair.get(key, Fraction(0)) + e["settled_amount"]
    shares = {k: v / base_sum for k, v in pair.items()} if base_sum else {}
    stocks = solve_stocks(ctx["charters"], base, shares)

    decoded_amount = sum((Fraction(e["amount"]) for e in entries),
                         Fraction(0))
    settled_amount = sum((e["settled_amount"] for e in settled), Fraction(0))
    dropped_amount = sum((Fraction(e["amount"]) for e in
                          dropped_retired + dropped_offwindow), Fraction(0))

    return {
        "decoded": decoded, "entries": entries, "walk": walk,
        "settled": settled, "promoted": promoted,
        "dropped_retired": dropped_retired,
        "dropped_offwindow": dropped_offwindow,
        "depths": depths, "ticks": ticks, "amounts": amounts,
        "charters_of": charters_of, "kinds": kinds, "stocks": stocks,
        "decoded_amount": decoded_amount, "settled_amount": settled_amount,
        "dropped_amount": dropped_amount,
        "divergence": (div_pos, div_tick),
        "reversal_count": sum(1 for e in entries if e["kind"] == REVERSAL),
        "echo_kind_count": sum(
            1 for n in decoded for e in ctx["raw"][n] if e["kind"] == ECHO_KIND
        ) if ctx.get("raw") else None,
    }


# -------------------------------------------------------------- derivation

def cap_frags(caps, per_capture, sep=","):
    """One fragment per capture in ring order: the ordinal then its values."""
    return ["%d:%s" % (c["number"], sep.join(per_capture[c["number"]]))
            for c in caps]


def render(ent, unit, tick_key):
    return "/".join(str(x) for x in (ent[tick_key], unit, ent["kind"],
                                     ent["amount"], ent["mark"]))


def t_frame_bias(ctx, q):
    L = q["frame_bias_limit"]
    vals = {}
    for c in ctx["caps"]:
        bias = (3 * c["number"] + 1) % L if (c["flags"] & PADDED) else 0
        vals[c["number"]] = [str(bias)]
    return control(cap_frags(ctx["caps"], vals))


def t_weave(ctx, q):
    vals = {}
    for c in ctx["caps"]:
        blocks = restored_lines(c, q["weave_seed_offset"])
        if blocks is None:
            return None
        vals[c["number"]] = [l for _, lines in blocks for l in lines]
    return control(cap_frags(ctx["caps"], vals))


def _lifted_hex(ctx, q, drift_mod):
    vals = {}
    for c in ctx["caps"]:
        blocks = lifted_blocks(c, q["weave_seed_offset"],
                               q["sentinel_code_value"], drift_mod)
        if blocks is None:
            return None
        vals[c["number"]] = [v.hex() for _, vs in blocks for v in vs]
    return vals


def t_sentinel(ctx, q):
    vals = _lifted_hex(ctx, q, None)
    return None if vals is None else control(cap_frags(ctx["caps"], vals))


def t_drift(ctx, q):
    vals = _lifted_hex(ctx, q, q["drift_modulus"])
    return None if vals is None else control(cap_frags(ctx["caps"], vals))


def _opening(cap, q):
    blocks = lifted_blocks(cap, q["weave_seed_offset"],
                           q["sentinel_code_value"], q["drift_modulus"])
    if not blocks or not blocks[0][1]:
        return None
    p = blocks[0][1][0]
    if cap["flags"] & SEALED:
        p = xorb(p, mask(q["_labels"][q["seal_label_index"]],
                         [cap["number"], 0]))
    if cap["flags"] & CHAINED:
        p = xorb(p, mask("chain", [cap["number"], 0, 0]))
    return p


def t_seal_label(ctx, q):
    vals = {}
    for c in ctx["caps"]:
        p = _opening(c, q)
        if p is None:
            return None
        vals[c["number"]] = [p.hex()]
    return control(cap_frags(ctx["caps"], vals))


def t_spin(ctx, q):
    vals = {}
    for c in ctx["caps"]:
        p = _opening(c, q)
        if p is None:
            return None
        if c["flags"] & SPUN:
            p = rot_right(p, q["spin_modulus"] % 12)
        if flipped_block(c) == 0:
            p = unflip(p)
        ent = {"field_tick": int.from_bytes(p[0:2], "big"), "kind": p[4],
               "amount": int.from_bytes(p[5:9], "big"), "mark": p[9]}
        vals[c["number"]] = [render(ent, int.from_bytes(p[2:4], "big"),
                                    "field_tick")]
    return control(cap_frags(ctx["caps"], vals))


def t_shadow(ctx, q):
    vals = {}
    for c in ctx["caps"]:
        d = decode_capture(c, q, ctx["true"][c["number"]])
        if d is None:
            return None
        vals[c["number"]] = [render(e, e["unit"], "field_tick") for e in d]
    return control(cap_frags(ctx["caps"], vals))


def _worded(ctx, q, resolve):
    vals = {}
    for c in ctx["caps"]:
        d = decode_capture(c, q, ctx["true"][c["number"]])
        if d is None:
            return None
        if resolve:
            d = resolve_echoes(d, q["echo_window_span"])
            if d is None or any(e["kind"] > REVERSAL for e in d):
                return None
        table = alias_table(c, ctx["by_number"], len(ctx["caps"]),
                            q["alias_donor_shift"], ctx["words"])
        if table is None or any(e["unit"] >= len(table) for e in d):
            return None
        vals[c["number"]] = [render(e, table[e["unit"]], "tick") for e in d]
    return vals


def t_alias(ctx, q):
    vals = _worded(ctx, q, False)
    return None if vals is None else control(cap_frags(ctx["caps"], vals))


def t_echo(ctx, q):
    vals = _worded(ctx, q, True)
    return None if vals is None else control(cap_frags(ctx["caps"], vals))


def t_cadence(ctx, q):
    s = ctx["settled_cache"].get("S")
    if s is None:
        s = settle(ctx, q)
        if s is None:
            return None
        ctx["settled_cache"]["S"] = s
    mod = q["cadence_modulus"]
    cad = ctx["cadences"]
    return control(["%s:%s" % (u, cad[(s["ticks"][u] // mod) % len(cad)])
                    for u in sorted(s["ticks"])])


def t_upkeep(ctx, q):
    target = q["upkeep_target_scale"] * sum(ctx["baselines"].values())
    return control(["%d/1" % target])


TESTERS = {
    "frame_bias_limit": t_frame_bias,
    "weave_seed_offset": t_weave,
    "sentinel_code_value": t_sentinel,
    "drift_modulus": t_drift,
    "seal_label_index": t_seal_label,
    "spin_modulus": t_spin,
    "shadow_pad_base": t_shadow,
    "alias_donor_shift": t_alias,
    "echo_window_span": t_echo,
    "cadence_modulus": t_cadence,
    "upkeep_target_scale": t_upkeep,
}


def derive(ctx, quantities, figures):
    """Pin every withheld quantity against its own control figure, in the
    published order, recording the candidates each control rules out."""
    q = {"_labels": ctx["labels"]}
    record, table = [], []
    for row in quantities:
        name, cname = row["name"], row["control"]
        tester = TESTERS.get(name)
        if tester is None:
            raise SystemExit("no reading for the quantity %s" % name)
        published = figures.get(cname)
        if published is None:
            raise SystemExit("%s publishes no figure" % cname)
        matched, rejected, produced = [], [], None
        for cand in row["candidates"]:
            trial = dict(q)
            trial[name] = cand
            got = tester(ctx, trial)
            if got == published:
                matched.append(cand)
                produced = got
            else:
                rejected.append({"candidate": cand, "falsifier": cname})
        if len(matched) != 1:
            raise SystemExit("%s does not single out %s (%d values reproduce "
                             "its figure)" % (cname, name, len(matched)))
        q[name] = matched[0]
        ctx["settled_cache"].clear()
        record.append({"name": name, "value": matched[0], "control": cname,
                       "rejected": rejected})
        table.append({"control": cname, "published": published,
                      "produced": produced})
    return q, record, table


# ------------------------------------------------------------------ reports

def rat(f):
    f = Fraction(f)
    return "%d/%d" % (f.numerator, f.denominator)


def write_report(report_dir, name, obj):
    path = os.path.join(report_dir, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, indent=2) + "\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: %s <capture-dir> <report-dir>\n" % argv[0])
        return 2
    capture_dir, report_dir = argv[1], argv[2]
    os.makedirs(report_dir, exist_ok=True)

    words, labels, charter_words, cadences = parse_tables(
        read_text(find_file(capture_dir, "charter")))
    quantities, figures = parse_calibration(
        read_text(find_file(capture_dir, "calibration")))
    roster, order = load_roster(find_file(capture_dir, "roster"))
    windows = load_windows(find_file(capture_dir, "schedule"))
    bench = load_bench(find_file(capture_dir, "bench"))
    caps = load_captures(capture_dir)

    charters = sorted(set(charter_words) | {roster[w]["charter"]
                                            for w in order})
    base, count = charter_baselines(roster, order, charters)

    ctx = {
        "caps": caps,
        "by_number": {c["number"]: c for c in caps},
        "true": {c["number"]: true_entry_count(c) for c in caps},
        "words": words, "labels": labels, "charters": charters,
        "cadences": cadences, "roster": roster, "order": order,
        "windows": windows, "baselines": base, "unit_counts": count,
        "settled_cache": {},
    }

    q, record, table = derive(ctx, quantities, figures)

    raw = {}
    for cap in caps:
        raw[cap["number"]] = decode_capture(cap, q, ctx["true"][cap["number"]])
    ctx["raw"] = raw
    ctx["settled_cache"].clear()
    s = settle(ctx, q)
    if s is None:
        raise SystemExit("the settled quantities do not decode the set")

    mod = q["cadence_modulus"]
    units = sorted(s["ticks"])
    cadence_of = {u: cadences[(s["ticks"][u] // mod) % len(cadences)]
                  for u in units}

    write_report(report_dir, "scenario_visible.json", {
        "capture_count": len(caps),
        "entry_total": len(s["entries"]),
        "settled_total": len(s["settled"]),
        "units": [{
            "unit": u,
            "charter": s["charters_of"][u],
            "tick_total": s["ticks"][u],
            "amount_total": rat(s["amounts"][u]),
            "cadence": cadence_of[u],
            "kind_totals": [rat(x) for x in
                            s["kinds"].get(u, [Fraction(0)] * 3)],
        } for u in units],
    })

    for cad in cadences:
        members = [u for u in units if cadence_of[u] == cad]
        write_report(report_dir, "scenario_%s.json" % cad, {
            "cadence": cad,
            "unit_count": len(members),
            "amount_total": rat(sum((s["amounts"][u] for u in members),
                                    Fraction(0))),
            "units": [{"unit": u, "charter": s["charters_of"][u],
                       "tick_total": s["ticks"][u],
                       "amount_total": rat(s["amounts"][u])}
                      for u in members],
        })

    write_report(report_dir, "perf_report.json", {
        "charter_stocks": [{"charter": c, "stock": rat(s["stocks"][c])}
                           for c in sorted(charters)],
        "settled_total": rat(s["settled_amount"]),
        "decoded_total": rat(s["decoded_amount"]),
        "reversal_count": s["reversal_count"],
        "promoted_reversal_count": len(s["promoted"]),
    })

    target = Fraction(q["upkeep_target_scale"] * sum(base.values()))
    picked = bench_subset(bench, int(target))
    if picked is None:
        raise SystemExit("no bench subset meets the upkeep target")
    upkeep = Fraction(sum(u for w, u in bench if w in set(picked)))
    write_report(report_dir, "recommendations.json", {
        "target": rat(target),
        "bench": picked,
        "bench_upkeep": rat(upkeep),
        "residual_after_bench": rat(target - upkeep),
    })

    write_report(report_dir, "data_quality.json", {
        "dropped_retired": len(s["dropped_retired"]),
        "dropped_offwindow": len(s["dropped_offwindow"]),
        "dropped_amount_total": rat(s["dropped_amount"]),
        "decoded_amount_total": rat(s["decoded_amount"]),
        "settled_amount_total": rat(s["settled_amount"]),
        "conservation_residual": rat(s["decoded_amount"]
                                     - s["settled_amount"]
                                     - s["dropped_amount"]),
    })

    write_report(report_dir, "bottleneck_analysis.json", {
        "quantities": record,
        "settling_passes": settling_passes(roster, order),
        "calibration_table": table,
    })

    # settlement history, for the operator rather than the reports
    div_pos, div_tick = s["divergence"]
    deepest = min(sorted(s["depths"]),
                  key=lambda w: (-s["depths"][w], w)) if s["depths"] else None
    print("quantities: " + ", ".join("%s=%d" % (r["name"], r["value"])
                                     for r in record))
    print("entries decoded=%d surviving=%d settled=%d"
          % (len(s["entries"]), len(s["walk"]), len(s["settled"])))
    print("first divergence: position=%s tick=%s" % (div_pos, div_tick))
    if deepest is not None:
        print("deepest recorded word: %s depth=%d"
              % (deepest, s["depths"][deepest]))
    print("last promotion: position=%s"
          % (max(s["promoted"]) if s["promoted"] else None))
    print("entries whose kind byte marks an inherited payload: %d"
          % sum(1 for n in raw for e in raw[n] if e["kind"] == ECHO_KIND))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
