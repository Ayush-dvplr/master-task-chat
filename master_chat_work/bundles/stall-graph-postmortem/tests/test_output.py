"""Verifier for stall-graph-postmortem.

Self-contained: stdlib only, a fully specified xorshift64 generator, and an
independent reference derivation. Every corpus this file grades is rebuilt from
a declared seed, so the verifier never reads the agent image's data tree.

    python3 test_output.py environment    # regenerate environment/data
"""
import ast
import hashlib
import subprocess
import tempfile
from pathlib import Path

from rewardkit import criteria, criterion

SAMPLE_SEED = 2249193832418705729
CALIBRATION_SEED = 7794052400146645557
CHALLENGE_SEED = 3135394734878491126
EVAL_SEED = 8794254200832843529
# ---------------------------------------------------------------- primitives
import json
import os
import sys
from collections import defaultdict

INPUT_DIR = "/app/data"
OUTPUT_DIR = "/app/out"

REQUIRED_FILES = (
    "stall_journal.psv",
    "thread_probe.csv",
    "park_reports.jsonl",
    "thread_registry.csv",
    "lock_ladder.csv",
    "pool_windows.csv",
    "host_cells.csv",
    "tenant_classes.csv",
)

CONTROL_FILES = (
    "calibration_stall_journal.psv",
    "calibration_thread_probe.csv",
    "calibration_park_reports.jsonl",
    "control-slice-figures.json",
)

BYTES_PER_SPIN = 24  # one park record per spin sample
HOP_LIMIT = 6

F_ZIGZAG_WAIT = 0x001    # segment : wait column carries zig-zag differences
F_XOR_CHAIN_HOLD = 0x002 # segment : hold column masked with the previous wait
F_STRIDE_INTERLEAVE = 0x004  # segment: event lines written at stride positions
F_BIASED_COUNT = 0x008   # header  : declared count carries a bias
F_LE_ORIGIN = 0x010      # header  : origin numeral written low pair first
F_CHAIN_ORIGIN = 0x020   # header  : origin written against the previous segment
F_SENTINEL_ESCAPE = 0x040  # event  : escaped symbol complements the next depth
F_RING_OWNER = 0x080     # event   : owner written as a rolling back reference
F_COARSE_SPINS = 0x100   # event   : spin count escaped into a coarse unit
F_ROT_TOKEN = 0x200      # event   : wait for token rotated before its check
F_POOL_ALIAS = 0x400     # header  : worker column carries a registry alias
F_SHADOW_SLOT = 0x800    # event   : slot column is a decoy

DOMAIN_COUNT_WINDOW = (2, 3, 4, 5, 6)                                # 5
DOMAIN_STRIDE = (3, 5, 7, 9, 11, 13)                                 # 6
DOMAIN_CHAIN_WIDTH = (6, 7, 8, 9, 10, 11)                            # 6
DOMAIN_DEPTH_WIDTH = (5, 6, 7, 8, 9, 10)                             # 6
DOMAIN_RING_WIDTH = (4, 6, 8, 12, 16)                                # 5
DOMAIN_COARSE_UNIT = (32, 64, 128, 256, 512)                         # 5
DOMAIN_TOKEN_OFFSET = tuple(range(0, 8))                             # 8
DOMAIN_HOLD_SCALE = (1, 2, 4, 5, 8, 10, 16)                          # 7
DOMAIN_EPOCH_SPAN = tuple(1 << k for k in range(20, 32))             # 12

PARAMS = {
    "count_window": 5,
    "stride": 7,
    "chain_width": 9,
    "depth_width": 8,
    "ring_width": 6,
    "coarse_unit": 128,
    "token_offset": 3,
    "hold_scale": 5,
    "epoch_span": 1 << 24,
}

CELLS = ("East", "North", "South", "West")
TENANT_SEGMENTS = ("commercial", "public")
LOCK_CLASSES = ("LCK-A", "LCK-B", "LCK-C", "LCK-D",
                "LCK-E", "LCK-F", "LCK-G", "LCK-H")
TOKEN_WIDTH = 16

REJECTION_REASONS = (
    "outside_window",
    "retired_worker",
    "unprobed_slot",
    "unreported_park",
    "unresolved_worker",
)


def checksum(text):
    return "%04x" % (sum(ord(c) for c in text) % 65536)


def rot_left(text, k):
    k %= len(text) or 1
    return text[k:] + text[:k]


def rot_right(text, k):
    k %= len(text) or 1
    return text[-k:] + text[:-k] if k else text


def zigzag(value):
    return (value << 1) ^ (value >> 63) if value < 0 else value << 1


def unzigzag(value):
    return (value >> 1) ^ -(value & 1)


def pair_reverse(text):
    """Rewrite a hex numeral with its byte pairs in the opposite order."""
    body = text if len(text) % 2 == 0 else "0" + text
    return "".join(body[i - 2:i] for i in range(len(body), 0, -2))


def interleave_order(n, stride):
    """Wire position of each logical event, always a bijection."""
    used = [False] * n
    order = []
    pos = 0
    for _ in range(n):
        while used[pos]:
            pos = (pos + 1) % n
        order.append(pos)
        used[pos] = True
        pos = (pos + stride) % n
    return order


def decode_journal(text, params=PARAMS, verify=True):
    """Recover every stall event the journal carries, in logical order."""
    window = params["count_window"]
    stride = params["stride"]
    mask = (1 << params["chain_width"]) - 1
    depth_width = params["depth_width"]
    ring_width = params["ring_width"]
    unit = params["coarse_unit"]
    tok_off = params["token_offset"]
    scale = params["hold_scale"]

    groups = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@|"):
            groups.append([line, []])
        elif groups:
            groups[-1][1].append(line)
        else:
            raise ValueError("event line before any segment header")

    ring = [""] * ring_width
    ring_pos = 0
    prev_origin = 0
    out = []

    for header, body in groups:
        h = header.split("|")
        if len(h) != 8:
            raise ValueError("malformed segment header")
        segment_id, worker_field, count_field, origin_field = h[1], h[2], h[3], h[4]
        sflags = int(h[5], 16)
        segment_key = int(h[6])
        group_check = int(h[7], 16)

        bias = segment_key % window if sflags & F_BIASED_COUNT else 0
        n = int(count_field) - bias
        if n < 1 or n > len(body):
            raise ValueError("declared count outside the segment")

        if verify:
            got = sum(int(ln.rsplit("|", 1)[1], 16) for ln in body) % 65536
            if got != group_check:
                raise ValueError("segment check total mismatch")

        wire = body[:n]
        if sflags & F_STRIDE_INTERLEAVE:
            order = interleave_order(n, stride)
            wire = [wire[order[k]] for k in range(n)]

        numeral = pair_reverse(origin_field) if sflags & F_LE_ORIGIN else origin_field
        value = int(numeral, 16)
        origin = prev_origin + value if sflags & F_CHAIN_ORIGIN else value
        prev_origin = origin

        rows = []
        for line in wire:
            f = line.split("|")
            if len(f) != 10:
                raise ValueError("malformed event line")
            if verify and checksum("|".join(f[:9])) != f[9]:
                raise ValueError("event check total mismatch")
            rows.append(f)

        events = []
        prev_wait = 0
        prev_raw_symbol = ""
        running_hold = 0
        for f in rows:
            raw_symbol = f[7]
            if sflags & F_SHADOW_SLOT:
                head, _, tail = raw_symbol.rpartition(":")
                slot = int(tail)
                symbol = head
            else:
                slot = int(f[0])
                symbol = raw_symbol
            if sflags & F_SENTINEL_ESCAPE and symbol.startswith("!"):
                symbol = symbol[1:]

            if sflags & F_ZIGZAG_WAIT:
                wait = int(f[1]) if not events else prev_wait + unzigzag(int(f[1]))
            else:
                wait = int(f[1])

            hold = int(f[2])
            if sflags & F_XOR_CHAIN_HOLD:
                hold ^= prev_wait & mask

            spins = int(f[3][1:]) * unit if f[3].startswith("~") else int(f[3])

            depth = int(f[4])
            if (sflags & F_SENTINEL_ESCAPE) and prev_raw_symbol.startswith("!"):
                depth ^= (1 << depth_width) - 1

            if f[6].startswith("^"):
                owner = ring[int(f[6][1:]) % ring_width]
            else:
                owner = f[6]
            ring[ring_pos % ring_width] = owner
            ring_pos += 1

            if sflags & F_ROT_TOKEN:
                token = rot_right(f[8], (slot + tok_off) % TOKEN_WIDTH)
            else:
                token = f[8]

            events.append({
                "slot": slot, "wait_ns": wait, "hold_ns": hold, "spins": spins,
                "depth": depth, "blocked_class": f[5], "owner_tag": owner,
                "symbol": symbol, "token": token,
                "tick": origin + running_hold // scale,
            })
            running_hold += hold
            prev_wait = wait
            prev_raw_symbol = raw_symbol

        # Padding lines are ordinary body lines after the events in logical
        # order: they carry no event but still read and write the owner window.
        for line in body[n:]:
            f = line.split("|")
            if len(f) != 10:
                raise ValueError("malformed padding line")
            if f[6].startswith("^"):
                owner = ring[int(f[6][1:]) % ring_width]
            else:
                owner = f[6]
            ring[ring_pos % ring_width] = owner
            ring_pos += 1

        out.append({"segment_id": segment_id, "worker_field": worker_field,
                    "origin": origin, "sflags": sflags, "events": events})
    return out


def read_csv_rows(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    head = lines[0].split(",")
    return [dict(zip(head, ln.split(","))) for ln in lines[1:]]


def build_registry(text):
    index = defaultdict(list)
    for r in read_csv_rows(text):
        index[r["worker_tag"]].append((
            int(r["effective_from_epoch"]), int(r["effective_to_epoch"]),
            r["canonical_tag"], r["pool_key"], int(r["revision"]), r["status"]))
    return index


def resolve_identity(index, tag, epoch):
    """Return (canonical_tag, pool_key) or raise ValueError(reason)."""
    seen = set()
    cur = tag
    for _ in range(HOP_LIMIT):
        if cur in seen:
            raise ValueError("unresolved_worker")
        seen.add(cur)
        live = [row for row in index.get(cur, ()) if row[0] <= epoch <= row[1]]
        if not live:
            raise ValueError("unresolved_worker")
        lo, hi, canonical, pool_key, revision, status = min(live, key=lambda r: r[4])
        if canonical == cur:
            if status != "active":
                raise ValueError("retired_worker")
            return canonical, pool_key
        cur = canonical
    raise ValueError("unresolved_worker")


def resolve_owner(index, tag, epoch):
    """Follow alias rows from an owner tag; a walk that cannot finish leaves
    the tag as written."""
    seen = set()
    cur = tag
    for _ in range(HOP_LIMIT):
        if cur in seen:
            return tag
        seen.add(cur)
        live = [row for row in index.get(cur, ()) if row[0] <= epoch <= row[1]]
        if not live:
            return tag
        canonical = min(live, key=lambda r: r[4])[2]
        if canonical == cur:
            return cur
        cur = canonical
    return tag


def read_ladder(text):
    table = defaultdict(dict)
    for r in read_csv_rows(text):
        table[r["lock_class"]][int(r["rung_index"])] = int(r["budget_ns"])
    return dict((c, [table[c][i] for i in sorted(table[c])]) for c in table)


def read_windows(text):
    return dict((r["pool_key"], (int(r["open_tick"]), int(r["close_tick"])))
                for r in read_csv_rows(text))


def settle_blame(accepted, ladder):
    """Descend the rung of every lock class an implicated owner touches until
    the assignment stops moving."""
    by_class = defaultdict(list)
    owned = defaultdict(list)
    for row in accepted:
        by_class[row["blocked_class"]].append(row)
        owned[row["owner_tag"]].append(row)

    rung = dict((c, len(ladder[c]) - 1) for c in sorted(ladder))
    passes = 0
    while True:
        passes += 1
        budget = dict((c, ladder[c][rung[c]]) for c in rung)
        hot = {}
        for c in rung:
            rows = by_class.get(c, [])
            over = sum(1 for r in rows if r["wait_ns"] > budget[c])
            hot[c] = over > len(rows) - over
        suspect = {}
        for tag in sorted(owned):
            rows = owned[tag]
            heated = sum(1 for r in rows if hot.get(r["blocked_class"], False))
            suspect[tag] = heated > len(rows) - heated
        changed = False
        for c in sorted(rung):
            if rung[c] == 0:
                continue
            if any(suspect.get(r["owner_tag"], False)
                   for r in by_class.get(c, [])):
                rung[c] -= 1
                changed = True
        if not changed:
            return rung, budget, hot, suspect, passes


def derive(files, params=PARAMS, prefix="", search_record=None):
    segments = decode_journal(files[prefix + "stall_journal.psv"], params)
    index = build_registry(files["thread_registry.csv"])
    ladder = read_ladder(files["lock_ladder.csv"])
    windows = read_windows(files["pool_windows.csv"])
    cells = dict((r["host_id"], r["cell"])
                 for r in read_csv_rows(files["host_cells.csv"]))
    classes = dict((r["tenant_class"], r["tenant_segment"])
                   for r in read_csv_rows(files["tenant_classes.csv"]))
    probe_rows = {}
    for r in read_csv_rows(files[prefix + "thread_probe.csv"]):
        probe_rows[(r["worker_tag"], int(r["slot"]))] = (int(r["samples"]),
                                                         int(r["peak_wait_ns"]))
    park = {}
    for line in files[prefix + "park_reports.jsonl"].splitlines():
        if line.strip():
            row = json.loads(line)
            park[(row["worker_tag"], int(row["slot"]))] = row

    span = params["epoch_span"]
    rejections = dict((name, 0) for name in REJECTION_REASONS)
    accepted = []
    event_count = 0

    for segment in segments:
        for event in segment["events"]:
            event_count += 1
            epoch = event["tick"] // span
            try:
                canonical, pool_key = resolve_identity(
                    index, segment["worker_field"], epoch)
            except ValueError as exc:
                rejections[str(exc)] += 1
                continue
            bad = False
            lo, hi = windows[pool_key]
            if not (lo <= event["tick"] < hi):
                rejections["outside_window"] += 1
                bad = True
            key = (canonical, event["slot"])
            if key not in probe_rows:
                rejections["unprobed_slot"] += 1
                bad = True
            if key not in park:
                rejections["unreported_park"] += 1
                bad = True
            if bad:
                continue
            samples, peak = probe_rows[key]
            report = park[key]
            accepted.append({
                "blocked_class": event["blocked_class"],
                "bytes_emitted": BYTES_PER_SPIN * event["spins"],
                "bytes_logged": report["bytes_logged"],
                "canonical_tag": canonical,
                "cell": cells[report["host_id"]],
                "depth": event["depth"],
                "event_slot": event["slot"],
                "hold_ns": event["hold_ns"],
                "host_id": report["host_id"],
                "owner_tag": resolve_owner(index, event["owner_tag"], epoch),
                "peak_wait_ns": peak,
                "pool_key": pool_key,
                "samples": samples,
                "segment_id": segment["segment_id"],
                "spins": event["spins"],
                "symbol": event["symbol"],
                "tenant_segment": classes[report["tenant_class"]],
                "tick": event["tick"],
                "token": event["token"],
                "wait_ns": event["wait_ns"],
            })

    accepted.sort(key=lambda r: (r["segment_id"], r["event_slot"]))
    rung, budget, hot, suspect, passes = settle_blame(accepted, ladder)
    for row in accepted:
        row["within_budget"] = row["wait_ns"] <= budget[row["blocked_class"]]
    quarantined = [c for c in sorted(rung) if rung[c] == 0 and hot[c]]
    return build_reports(accepted, ladder, rung, budget, hot, suspect,
                         quarantined, rejections, event_count, passes,
                         search_record)


def _sum_by(rows, key, field):
    out = defaultdict(int)
    for r in rows:
        out[r[key]] += r[field]
    return dict((k, out[k]) for k in sorted(out))


def _count_by(rows, key):
    out = defaultdict(int)
    for r in rows:
        out[str(r[key])] += 1
    return dict((k, out[k]) for k in sorted(out))


def _token_total(rows):
    return sum(int(r["token"], 16) for r in rows) % 1000000007


def _group_report(rows, axis, label):
    return {
        "accepted_count": len(rows),
        "by_cell": _sum_by(rows, "cell", "bytes_logged"),
        "by_lock_class": _sum_by(rows, "blocked_class", "bytes_logged"),
        "by_tenant_segment": _sum_by(rows, "tenant_segment", "bytes_logged"),
        "lock_classes": sorted(set(r["blocked_class"] for r in rows)),
        "partition": label,
        "partition_axis": axis,
        "token_total": _token_total(rows),
        "total_bytes_logged": sum(r["bytes_logged"] for r in rows),
        "total_depth": sum(r["depth"] for r in rows),
        "total_wait_ns": sum(r["wait_ns"] for r in rows),
        "within_budget_count": sum(1 for r in rows if r["within_budget"]),
    }


def build_reports(accepted, ladder, rung, budget, hot, suspect, quarantined,
                  rejections, event_count, passes, search_record):
    reports = {}
    emitted_total = sum(r["bytes_emitted"] for r in accepted)
    logged_total = sum(r["bytes_logged"] for r in accepted)

    reports["summary.json"] = {
        "accepted_count": len(accepted),
        "by_cell": _sum_by(accepted, "cell", "bytes_logged"),
        "by_symbol": _count_by(accepted, "symbol"),
        "by_lock_class": _sum_by(accepted, "blocked_class", "bytes_logged"),
        "by_settled_rung": _count_by(
            [dict(r, settled_rung=rung[r["blocked_class"]]) for r in accepted],
            "settled_rung"),
        "by_tenant_segment": _sum_by(accepted, "tenant_segment", "bytes_logged"),
        "event_count": event_count,
        "rejected_count": event_count - len(accepted),
        "token_total": _token_total(accepted),
        "total_bytes_emitted": emitted_total,
        "total_bytes_logged": logged_total,
        "total_depth": sum(r["depth"] for r in accepted),
        "total_hold_ns": sum(r["hold_ns"] for r in accepted),
        "total_wait_ns": sum(r["wait_ns"] for r in accepted),
        "within_budget_count": sum(1 for r in accepted if r["within_budget"]),
    }

    by_class = defaultdict(list)
    owned = defaultdict(list)
    for row in accepted:
        by_class[row["blocked_class"]].append(row)
        owned[row["owner_tag"]].append(row)

    class_rows = []
    for c in sorted(ladder):
        rows = by_class.get(c, [])
        class_rows.append({
            "accepted_count": len(rows),
            "budget_ns": budget[c],
            "declared_rung": len(ladder[c]) - 1,
            "first_tick": min([r["tick"] for r in rows], default=0),
            "hot": hot[c],
            "last_tick": max([r["tick"] for r in rows], default=0),
            "lock_class": c,
            "owners": sorted(set(r["owner_tag"] for r in rows)),
            "quarantined": c in quarantined,
            "settled_rung": rung[c],
            "total_depth": sum(r["depth"] for r in rows),
            "total_wait_ns": sum(r["wait_ns"] for r in rows),
            "within_budget_count": sum(1 for r in rows if r["within_budget"]),
        })
    worker_rows = []
    for tag in sorted(set(list(owned) + [r["canonical_tag"] for r in accepted])):
        held = owned.get(tag, [])
        waited = [r for r in accepted if r["canonical_tag"] == tag]
        worker_rows.append({
            "canonical_tag": tag,
            "held_count": len(held),
            "implicated": bool(suspect.get(tag, False)),
            "pool_key": waited[0]["pool_key"] if waited else "",
            "total_bytes_logged": sum(r["bytes_logged"] for r in waited),
            "total_wait_ns": sum(r["wait_ns"] for r in waited),
            "waited_count": len(waited),
        })
    reports["policy_audit.json"] = {"lock_classes": class_rows,
                                    "workers": worker_rows}

    for cell in CELLS:
        picked = [r for r in accepted if r["cell"] == cell]
        reports["region_%s.json" % cell] = _group_report(picked, "cell", cell)
    for seg in TENANT_SEGMENTS:
        picked = [r for r in accepted if r["tenant_segment"] == seg]
        reports["segment_%s.json" % seg] = _group_report(
            picked, "tenant_segment", seg)

    reports["data_quality.json"] = {
        "accepted_count": len(accepted),
        "calibration_comparison": (search_record or {}).get(
            "calibration_comparison", []),
        "candidate_search": (search_record or {}).get(
            "candidate_search", {"evaluations": 0, "parameters": []}),
        "event_count": event_count,
        "reconciliation": {
            "emitted_bytes": emitted_total,
            "logged_bytes": logged_total,
            "residual_bytes": emitted_total - logged_total,
        },
        "rejections": dict((k, rejections[k]) for k in sorted(rejections)),
        "settlement": {"passes": passes, "quarantined_classes": quarantined},
    }
    return reports


ARTIFACT_NAMES = (
    ["summary.json", "policy_audit.json", "data_quality.json"]
    + ["region_%s.json" % c for c in ("North", "South", "West", "East")]
    + ["segment_%s.json" % s for s in TENANT_SEGMENTS]
)


def render(reports):
    """Serialize every report exactly as the post mortem contract requires."""
    return dict((name, json.dumps(payload, sort_keys=True, indent=2) + "\n")
                for name, payload in reports.items())


CONTROL_NAMES = ("CTRL-A", "CTRL-B", "CTRL-C", "CTRL-D", "CTRL-E", "CTRL-F",
                 "CTRL-G", "CTRL-H", "CTRL-I", "CTRL-J", "CTRL-K")

PARAMETER_LABELS = {
    "count_window": "count bias window",
    "stride": "interleave stride",
    "chain_width": "chain mask width",
    "depth_width": "depth complement width",
    "ring_width": "owner ring width",
    "coarse_unit": "coarse spin unit",
    "token_offset": "token rotation offset",
    "hold_scale": "hold scale",
    "epoch_span": "epoch span",
}

STAGES = (
    ("count_window", DOMAIN_COUNT_WINDOW, "CTRL-A"),
    ("stride", DOMAIN_STRIDE, "CTRL-B"),
    ("chain_width", DOMAIN_CHAIN_WIDTH, "CTRL-C"),
    ("depth_width", DOMAIN_DEPTH_WIDTH, "CTRL-D"),
    ("ring_width", DOMAIN_RING_WIDTH, "CTRL-E"),
    ("coarse_unit", DOMAIN_COARSE_UNIT, "CTRL-F"),
    ("token_offset", DOMAIN_TOKEN_OFFSET, "CTRL-G"),
    ("hold_scale", DOMAIN_HOLD_SCALE, "CTRL-H"),
    ("epoch_span", DOMAIN_EPOCH_SPAN, "CTRL-I"),
)

START = {
    "count_window": DOMAIN_COUNT_WINDOW[0],
    "stride": DOMAIN_STRIDE[0],
    "chain_width": DOMAIN_CHAIN_WIDTH[0],
    "depth_width": DOMAIN_DEPTH_WIDTH[0],
    "ring_width": DOMAIN_RING_WIDTH[0],
    "coarse_unit": DOMAIN_COARSE_UNIT[0],
    "token_offset": DOMAIN_TOKEN_OFFSET[0],
    "hold_scale": DOMAIN_HOLD_SCALE[0],
    "epoch_span": DOMAIN_EPOCH_SPAN[0],
}

DOMAINS = {
    "count_window": DOMAIN_COUNT_WINDOW,
    "stride": DOMAIN_STRIDE,
    "chain_width": DOMAIN_CHAIN_WIDTH,
    "depth_width": DOMAIN_DEPTH_WIDTH,
    "ring_width": DOMAIN_RING_WIDTH,
    "coarse_unit": DOMAIN_COARSE_UNIT,
    "token_offset": DOMAIN_TOKEN_OFFSET,
    "hold_scale": DOMAIN_HOLD_SCALE,
    "epoch_span": DOMAIN_EPOCH_SPAN,
}


def _tag_number(tag):
    tail = tag.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def probe(text, params):
    """Return the observable figures a candidate parameter set produces."""
    segments = decode_journal(text, params)
    events = [e for s in segments for e in s["events"]]
    return {
        "CTRL-A": len(events),
        "CTRL-B": sum(e["wait_ns"] for e in events),
        "CTRL-C": sum(e["hold_ns"] for e in events),
        "CTRL-D": sum(e["depth"] for e in events),
        "CTRL-E": sum(_tag_number(e["owner_tag"]) for e in events),
        "CTRL-F": sum(e["spins"] for e in events),
        "CTRL-G": sum(int(e["token"], 16) for e in events) % 1000000007,
        "CTRL-H": sum(e["tick"] for e in events),
    }


def controls(files, prefix="calibration_", params=None):
    params = params or PARAMS
    reports = derive(files, params, prefix)
    observed = probe(files[prefix + "stall_journal.psv"], params)
    quality = reports["data_quality.json"]
    observed["CTRL-I"] = quality["accepted_count"]
    observed["CTRL-J"] = len(quality["settlement"]["quarantined_classes"])
    observed["CTRL-K"] = quality["reconciliation"]["residual_bytes"]
    return dict((name, observed[name]) for name in CONTROL_NAMES)


def recover(files, published, prefix="calibration_", verbose=False):
    """Stage the search; return (params, derivation record, evaluation count)."""
    text = files[prefix + "stall_journal.psv"]
    params = dict(START)
    record = []
    evaluations = 0
    for name, domain, control in STAGES:
        survivors = []
        for value in domain:
            evaluations += 1
            trial = dict(params)
            trial[name] = value
            try:
                if control == "CTRL-I":
                    got = controls(files, prefix, trial)[control]
                else:
                    got = probe(text, trial)[control]
            except Exception:
                got = None
            if got == published[control]:
                survivors.append(value)
        if len(survivors) != 1:
            raise SystemExit("stage %s left %d survivors: %s"
                             % (name, len(survivors), survivors[:8]))
        params[name] = survivors[0]
        record.append({"name": PARAMETER_LABELS[name], "candidates": len(domain),
                       "control": control, "selected": survivors[0],
                       "rejected": [{"control": control, "value": v}
                                    for v in domain if v != survivors[0]]})
        if verbose:
            print("  %-14s candidates=%-3d survivors=1 -> %s"
                  % (name, len(domain), survivors[0]))
    return params, record, evaluations


def carried_record():
    return {
        "candidate_search": {
            "evaluations": 0,
            "parameters": [{"name": PARAMETER_LABELS[name],
                            "candidates": len(DOMAINS[name]), "control": "",
                            "selected": PARAMS[name], "rejected": []}
                           for name, _d, _c in STAGES],
        },
        "calibration_comparison": [],
    }


def settle(files):
    if not all(name in files for name in CONTROL_FILES):
        return dict(PARAMS), carried_record()
    published = json.loads(files["control-slice-figures.json"])
    params, parameters, evaluations = recover(files, published)
    reproduced = controls(files, "calibration_", params)
    record = {
        "candidate_search": {"evaluations": evaluations,
                             "parameters": parameters},
        "calibration_comparison": [
            {"control": name, "published": published[name],
             "reproduced": reproduced[name]} for name in CONTROL_NAMES],
    }
    return params, record


# --------------------------------------------------------------- corpus side
ORIGIN_BASE = 700000000
ORIGIN_STEP = 1500000
MAIN_WORKERS = tuple("WRK-1%03d" % i for i in range(1, 25))
SAMPLE_WORKERS = tuple("WRK-1%03d" % i for i in range(901, 909))
POOLS = tuple("POOL-%02d" % i for i in range(1, 7))
EPOCH_STRADDLE_INDEX = 14
EPOCH_STRADDLE_ORIGIN = (43 << 24) - 1000
STRADDLE_POOLS = ("POOL-91", "POOL-92")
SAMPLE_POOL = "POOL-90"
HOSTS = tuple("HST-%02d" % i for i in range(1, 13))
TENANT_CLASSES = tuple("TC-%d" % i for i in range(1, 7))
SYMBOLS = ("park_wait", "futex_wait", "mutex_lock", "cond_wait",
           "rw_acquire", "sem_down", "barrier_join", "queue_pop")
ALIAS_SKIP = ("WRK-1006", "WRK-1012", "WRK-1018")
ALL_FLAGS = (F_ZIGZAG_WAIT, F_XOR_CHAIN_HOLD, F_STRIDE_INTERLEAVE,
             F_BIASED_COUNT, F_LE_ORIGIN, F_CHAIN_ORIGIN, F_SENTINEL_ESCAPE,
             F_RING_OWNER, F_COARSE_SPINS, F_ROT_TOKEN, F_POOL_ALIAS,
             F_SHADOW_SLOT)

LADDER = {
    "LCK-A": (4600, 5800, 7000, 8200),
    "LCK-B": (1100, 2000, 2600, 3300),
    "LCK-C": (1400, 2400, 3300, 4200),
    "LCK-D": (5000, 6600, 8200, 10400),
    "LCK-E": (900, 2000, 3200),
    "LCK-F": (1800, 3000, 5200, 8000),
    "LCK-G": (4800, 5200, 5600, 6000),
    "LCK-H": (1200, 2400, 3600, 4800),
}

WINDOWS = {
    "POOL-01": (700000000, 743500000),
    "POOL-02": (700000000, 736000000),
    "POOL-03": (703000000, 743500000),
    "POOL-04": (700000000, 740500000),
    "POOL-05": (701500000, 743500000),
    "POOL-06": (700000000, 743500000),
    SAMPLE_POOL: (0, 4611686018427387904),
}


class Rng:
    """xorshift64: fully specified, stable across Python releases."""

    def __init__(self, seed):
        self.state = (seed & 0xFFFFFFFFFFFFFFFF) or 0x9E3779B97F4A7C15

    def next(self):
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
        x ^= x >> 7
        x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
        self.state = x
        return x

    def below(self, n):
        return self.next() % n

    def between(self, lo, hi):
        return lo + self.next() % (hi - lo + 1)


def registry_rows(mutation=None):
    rows = []
    for i, tag in enumerate(MAIN_WORKERS, start=1):
        pool_a = POOLS[i % 6]
        pool_b = POOLS[(i + 3) % 6]
        if i % 8 == 0:
            rows.append((tag, tag, pool_a, 38, 52, 1, "retired"))
            rows.append((tag, tag, pool_b, 38, 52, 2, "active"))
        elif i % 5 == 0:
            rows.append((tag, tag, pool_a, 38, 52, 1, "active"))
            rows.append((tag, tag, pool_b, 40, 52, 2, "active"))
        elif i % 7 == 0:
            rows.append((tag, tag, pool_a, 38, 42, 1, "active"))
            rows.append((tag, tag, pool_b, 43, 52, 1, "active"))
        elif i % 6 == 0:
            rows.append((tag, tag, pool_a, 38, 42, 1, "active"))
        else:
            rows.append((tag, tag, pool_a, 38, 52, 1, "active"))
    for k, tag in enumerate(MAIN_WORKERS, start=1):
        rows.append(("ALS-2%03d" % k, tag, "-", 38, 52, 1, "alias"))
    rows.append(("ALS-2101", "ALS-2001", "-", 38, 52, 1, "alias"))
    for tag in SAMPLE_WORKERS:
        rows.append((tag, tag, SAMPLE_POOL, 0, 4294967295, 1, "active"))
    if mutation == "cycle":
        rows.append(("ALS-2900", "ALS-2901", "-", 38, 52, 1, "alias"))
        rows.append(("ALS-2901", "ALS-2900", "-", 38, 52, 1, "alias"))
    if mutation == "nonapplying_rule":
        for k in range(1, 5):
            rows.append(("ALS-280%d" % k, "ALS-280%d" % (k + 1), "-",
                         38, 52, 1, "alias"))
        rows.append(("ALS-2805", MAIN_WORKERS[1], "-", 38, 52, 1, "alias"))
        for k in range(1, 6):
            rows.append(("ALS-270%d" % k, "ALS-270%d" % (k + 1), "-",
                         38, 52, 1, "alias"))
        rows.append(("ALS-2706", MAIN_WORKERS[2], "-", 38, 52, 1, "alias"))
    if mutation == "new_entity":
        rows.append(("WRK-1030", "WRK-1030", POOLS[2], 38, 52, 1, "active"))
    if mutation == "boundary_shift":
        straddler = MAIN_WORKERS[6]
        rows = [row for row in rows if row[0] != straddler]
        rows.append((straddler, straddler, STRADDLE_POOLS[0], 38, 42, 1, "active"))
        rows.append((straddler, straddler, STRADDLE_POOLS[1], 43, 52, 1, "active"))
    if mutation == "single_revision":
        # Only revision 1 survives, so no tag ever carries two live rows at one
        # epoch and the lowest-revision tiebreak stops deciding anything.
        rows = [row for row in rows if row[5] == 1]
    if mutation == "rule_order":
        rows.reverse()
    return rows


def ladder_table(mutation=None):
    table = dict((c, list(v)) for c, v in LADDER.items())
    if mutation == "tie_config":
        table = dict((c, [b + (400 if i % 2 else 900) for b in v])
                     for i, (c, v) in enumerate(sorted(table.items())))
    return table


def window_table(mutation=None):
    table = dict(WINDOWS)
    if mutation == "boundary_shift":
        table = dict((p, (lo + 1, hi + 1)) if p != SAMPLE_POOL else (p, (lo, hi))
                     for p, (lo, hi) in table.items())
    if mutation == "contradict_calibration":
        table = dict((p, (lo, hi - 6000000)) if p != SAMPLE_POOL else (p, (lo, hi))
                     for p, (lo, hi) in table.items())
    if mutation == "boundary_shift":
        table[STRADDLE_POOLS[0]] = (0, EPOCH_STRADDLE_ORIGIN + 700)
        table[STRADDLE_POOLS[1]] = (0, 4611686018427387904)
    return table


def host_cell_table(mutation=None, plants=None):
    order = CELLS
    if mutation == "empty_group":
        order = ("East", "North", "South")
    if mutation == "partition_count":
        order = ("North", "South")
    if plants and "cells" in plants:
        order = tuple(c for c in order if c in plants["cells"])
    return dict((h, order[i % len(order)]) for i, h in enumerate(HOSTS))


def side_tables(mutation=None, plants=None):
    lines = ["worker_tag,canonical_tag,pool_key,effective_from_epoch,"
             "effective_to_epoch,revision,status"]
    for row in registry_rows(mutation):
        lines.append(",".join(str(part) for part in row))
    registry = "\n".join(lines) + "\n"

    ladder = ["lock_class,rung_index,budget_ns"]
    for lock_class in sorted(ladder_table(mutation)):
        for index, budget in enumerate(ladder_table(mutation)[lock_class]):
            ladder.append("%s,%d,%d" % (lock_class, index, budget))

    windows = ["pool_key,open_tick,close_tick"]
    for pool in sorted(window_table(mutation)):
        lo, hi = window_table(mutation)[pool]
        windows.append("%s,%d,%d" % (pool, lo, hi))

    cells = ["host_id,cell"]
    for host in HOSTS:
        cells.append("%s,%s" % (host, host_cell_table(mutation, plants)[host]))

    segments = TENANT_SEGMENTS
    if plants and "segments" in plants:
        segments = tuple(s for s in segments if s in plants["segments"])
    tenants = ["tenant_class,tenant_segment"]
    for index, name in enumerate(TENANT_CLASSES):
        tenants.append("%s,%s" % (name, segments[(index // 3) % len(segments)]))

    return {
        "thread_registry.csv": registry,
        "lock_ladder.csv": "\n".join(ladder) + "\n",
        "pool_windows.csv": "\n".join(windows) + "\n",
        "host_cells.csv": "\n".join(cells) + "\n",
        "tenant_classes.csv": "\n".join(tenants) + "\n",
    }


def _preferred_classes(tag):
    """Every worker keeps to a home pair of lock classes."""
    number = int(tag.rsplit("-", 1)[-1]) if tag.rsplit("-", 1)[-1].isdigit() else 0
    first = number % len(LOCK_CLASSES)
    second = (number * 3 + 1) % len(LOCK_CLASSES)
    return (LOCK_CLASSES[first], LOCK_CLASSES[second])


def _owner_alias(tag):
    """The alias tag whose rows lead to a main worker live at every epoch."""
    if tag not in MAIN_WORKERS or tag in ALIAS_SKIP:
        return tag
    place = MAIN_WORKERS.index(tag)
    return "ALS-2101" if place == 0 else "ALS-2%03d" % (place + 1)


def build_plan(seed, tier, mutation=None, force_s=None, plants=None):
    rng = Rng(seed)
    ladder = ladder_table(mutation)
    if tier == "sample":
        workers = list(SAMPLE_WORKERS)
        segment_count, low, high = 20, 1, 1
    elif tier == "calibration":
        workers = list(MAIN_WORKERS)
        segment_count, low, high = 16, 5, 9
    else:
        workers = list(MAIN_WORKERS)
        segment_count, low, high = 30, 6, 10
    if mutation == "scale_population" and tier == "challenge":
        low, high = 60, 100
    planted = {"new_entity": "WRK-1030", "cycle": "ALS-2900"}.get(mutation)

    slot_counter = defaultdict(lambda: 100)
    recent = []
    plan = []
    for index in range(segment_count):
        canonical = workers[rng.below(len(workers))]
        if planted and tier == "challenge" and index % 7 == 3:
            canonical = planted
        if force_s is not None:
            sflags = force_s
        elif tier == "sample":
            sflags = 0
        else:
            sflags = 0
            for bit in ALL_FLAGS:
                if rng.below(100) < 45:
                    sflags |= bit
            if sflags == 0:
                sflags = ALL_FLAGS[rng.below(len(ALL_FLAGS))]
        if tier == "calibration":
            if index < segment_count // 2:
                sflags &= ~F_BIASED_COUNT
            else:
                sflags &= ~F_RING_OWNER
        field = canonical
        if sflags & F_POOL_ALIAS and canonical in MAIN_WORKERS:
            place = MAIN_WORKERS.index(canonical)
            field = "ALS-2101" if place == 0 else "ALS-2%03d" % (place + 1)
        straddle = (mutation == "boundary_shift" and tier == "challenge"
                    and index == EPOCH_STRADDLE_INDEX)
        if mutation == "nonapplying_rule" and tier == "challenge":
            if index % 7 == 3:
                canonical, field = MAIN_WORKERS[1], "ALS-2801"
            elif index % 7 == 5:
                canonical, field = MAIN_WORKERS[2], "ALS-2701"
        if straddle:
            canonical, field = MAIN_WORKERS[6], MAIN_WORKERS[6]
        if tier == "sample":
            origin = 500000 + index * 1000
        elif straddle:
            origin = EPOCH_STRADDLE_ORIGIN
        else:
            origin = ORIGIN_BASE + index * ORIGIN_STEP
        count = rng.between(low, high)
        events = []
        for position in range(count):
            slot_counter[canonical] += 1
            if recent and rng.below(100) < 55:
                owner = recent[-(1 + rng.below(min(4, len(recent))))]
            else:
                owner = workers[rng.below(len(workers))]
            recent.append(owner)
            if len(recent) > 8:
                del recent[0]
            preferred = _preferred_classes(owner)
            if rng.below(100) < 78:
                lock_class = preferred[rng.below(len(preferred))]
            else:
                lock_class = LOCK_CLASSES[rng.below(len(LOCK_CLASSES))]
            wait = rng.between(150, 9000)
            if mutation == "cap_edge" and rng.below(3) == 0:
                wait = ladder[lock_class][rng.below(len(ladder[lock_class]))]
            if rng.below(100) < 60:
                spins = rng.between(1, 40) * 128
            else:
                spins = rng.between(20, 600)
            events.append({
                "slot": slot_counter[canonical],
                "decoy_slot": position,
                "wait_ns": wait,
                "hold_ns": rng.between(200, 6000),
                "spins": spins,
                "depth": rng.between(1, 18),
                "blocked_class": lock_class,
                "owner_tag": owner,
                "symbol": SYMBOLS[rng.below(len(SYMBOLS))],
                "token": "%016x" % rng.next(),
                "escape": rng.below(4) == 0,
            })
        plan.append({
            "segment_id": "SEG-%04d" % (index + 1),
            "canonical": canonical,
            "worker_field": field,
            "origin": origin,
            "sflags": sflags,
            "segment_key": rng.below(100000),
            "events": events,
        })
    if plants and plants.get("alias_owner") and tier == "challenge":
        for index, segment in enumerate(plan):
            for position, event in enumerate(segment["events"]):
                if (index + position) % 3 == 0:
                    event["owner_tag"] = _owner_alias(event["owner_tag"])
    return plan


def _pad_line(rng):
    fields = [str(rng.between(1, 90)), str(rng.between(150, 9000)),
              str(rng.between(200, 6000)), str(rng.between(20, 600)),
              str(rng.between(1, 18)),
              LOCK_CLASSES[rng.below(len(LOCK_CLASSES))],
              MAIN_WORKERS[rng.below(len(MAIN_WORKERS))],
              SYMBOLS[rng.below(len(SYMBOLS))], "%016x" % rng.next()]
    body = "|".join(fields)
    return body + "|" + checksum(body)


def encode_journal(plan, params=PARAMS, pad_seed=0x51A11):
    window = params["count_window"]
    stride = params["stride"]
    mask = (1 << params["chain_width"]) - 1
    depth_width = params["depth_width"]
    ring_width = params["ring_width"]
    unit = params["coarse_unit"]
    tok_off = params["token_offset"]

    pad_rng = Rng(pad_seed)
    ring = [""] * ring_width
    ring_pos = 0
    prev_origin = 0
    lines = ["# stall journal export"]

    for segment in plan:
        sflags = segment["sflags"]
        events = segment["events"]
        count = len(events)
        rows = []
        prev_wait = 0
        prev_raw_symbol = ""
        for position, event in enumerate(events):
            raw_symbol = event["symbol"]
            if sflags & F_SENTINEL_ESCAPE and event["escape"]:
                raw_symbol = "!" + raw_symbol
            if sflags & F_SHADOW_SLOT:
                slot_field = str(event["decoy_slot"])
                raw_symbol = raw_symbol + ":" + str(event["slot"])
            else:
                slot_field = str(event["slot"])

            if sflags & F_ZIGZAG_WAIT and position:
                wait_field = str(zigzag(event["wait_ns"] - prev_wait))
            else:
                wait_field = str(event["wait_ns"])

            hold = event["hold_ns"]
            if sflags & F_XOR_CHAIN_HOLD:
                hold ^= prev_wait & mask

            if sflags & F_COARSE_SPINS and event["spins"] % unit == 0:
                spins_field = "~" + str(event["spins"] // unit)
            else:
                spins_field = str(event["spins"])

            depth = event["depth"]
            if sflags & F_SENTINEL_ESCAPE and prev_raw_symbol.startswith("!"):
                depth ^= (1 << depth_width) - 1

            owner = event["owner_tag"]
            owner_field = owner
            if sflags & F_RING_OWNER:
                for slot_index in range(ring_width):
                    if ring[slot_index] == owner:
                        owner_field = "^%d" % slot_index
                        break
            ring[ring_pos % ring_width] = owner
            ring_pos += 1

            if sflags & F_ROT_TOKEN:
                token_field = rot_left(event["token"],
                                       (event["slot"] + tok_off) % TOKEN_WIDTH)
            else:
                token_field = event["token"]

            body = "|".join([slot_field, wait_field, str(hold), spins_field,
                             str(depth), event["blocked_class"], owner_field,
                             raw_symbol, token_field])
            rows.append(body + "|" + checksum(body))
            prev_wait = event["wait_ns"]
            prev_raw_symbol = raw_symbol

        if sflags & F_STRIDE_INTERLEAVE:
            order = interleave_order(count, stride)
            wire = [""] * count
            for logical in range(count):
                wire[order[logical]] = rows[logical]
        else:
            wire = list(rows)

        bias = segment["segment_key"] % window if sflags & F_BIASED_COUNT else 0
        padding = [_pad_line(pad_rng) for _ in range(bias)]
        for line in padding:
            ring[ring_pos % ring_width] = line.split("|")[6]
            ring_pos += 1
        body_lines = wire + padding

        if sflags & F_CHAIN_ORIGIN:
            value = segment["origin"] - prev_origin
        else:
            value = segment["origin"]
        numeral = "%08x" % value
        if sflags & F_LE_ORIGIN:
            numeral = pair_reverse(numeral)
        prev_origin = segment["origin"]

        check = sum(int(ln.rsplit("|", 1)[1], 16) for ln in body_lines) % 65536
        lines.append("@|%s|%s|%d|%s|%03x|%d|%04x" % (
            segment["segment_id"], segment["worker_field"], count + bias,
            numeral, sflags, segment["segment_key"], check))
        lines.extend(body_lines)

    return "\n".join(lines) + "\n"


def materialise(plan, seed, mutation=None, prefix=""):
    rng = Rng(seed ^ 0x2545F4914F6CDD1D)
    probe_lines = ["worker_tag,slot,samples,peak_wait_ns"]
    park_lines = []
    for segment in plan:
        for event in segment["events"]:
            roll = 99 if prefix == "sample_" else rng.below(100)
            if roll >= 4:
                probe_lines.append("%s,%d,%d,%d" % (
                    segment["canonical"], event["slot"], rng.between(1, 40),
                    event["wait_ns"] + rng.below(500)))
            if 4 <= roll < 8:
                continue
            park_lines.append(json.dumps({
                "bytes_logged": BYTES_PER_SPIN * event["spins"] - rng.below(240),
                "host_id": HOSTS[rng.below(len(HOSTS))],
                "slot": event["slot"],
                "tenant_class": TENANT_CLASSES[rng.below(len(TENANT_CLASSES))],
                "worker_tag": segment["canonical"],
            }, sort_keys=True))
    return {
        prefix + "stall_journal.psv": encode_journal(plan),
        prefix + "thread_probe.csv": "\n".join(probe_lines) + "\n",
        prefix + "park_reports.jsonl": "\n".join(park_lines) + "\n",
    }


# ------------------------------------------------------------------ harness
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
PROGRAM = "derive_report.py"
FALLBACK_INPUT = "/app/data"
FALLBACK_OUTPUT = "/app/out"
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

DELIVERABLES = [PROGRAM] + list(ARTIFACT_NAMES)
ANSWER_FILES = ("sample_summary_answer.json", "sample_audit_answer.json")


def _grant_read(command):
    """Make an agent-written program readable by the unprivileged uid the run
    drops to. An editor writes through a temp file and renames it, so the
    program lands at mode 0600 which nobody cannot open; chmod it and make its
    parents traversable (the verifier runs as root). The interpreter is never
    touched: chmod 0644 on it would strip its execute bit."""
    interpreter = Path(sys.executable).resolve()
    for arg in command:
        try:
            path = Path(arg)
            if not path.is_file() or path.resolve() == interpreter:
                continue
            path.chmod(0o644)
            for parent in path.parents:
                parent.chmod(parent.stat().st_mode | 0o055)
                if str(parent) in ("/", "/app"):
                    break
        except OSError:
            continue


def _untrusted_command(command):
    if os.name == "posix" and os.geteuid() == 0:
        _grant_read(command)
        return [*_SETPRIV, *command]
    return command


def _mix(seed, label):
    return int(hashlib.blake2b(label.encode(), digest_size=8,
                               key=str(seed).encode()).hexdigest(), 16) >> 1


def _population(tier, seed, mutation=None, prefix="", force_s=None,
                plants=None):
    plan = build_plan(seed, tier, mutation, force_s, plants)
    files = materialise(plan, seed, mutation, prefix)
    files.update(side_tables(mutation, plants))
    return files


def shipped_population():
    files = _population("challenge", CHALLENGE_SEED)
    files.update(_population("calibration", CALIBRATION_SEED, None,
                             "calibration_"))
    files.update(_population("sample", SAMPLE_SEED, None, "sample_"))
    sample = derive(files, PARAMS, "sample_")
    files["sample_summary_answer.json"] = json.dumps(
        sample["summary.json"], sort_keys=True, indent=2) + "\n"
    files["sample_audit_answer.json"] = json.dumps(
        sample["policy_audit.json"], sort_keys=True, indent=2) + "\n"
    files["control-slice-figures.json"] = json.dumps(
        controls(files, "calibration_"), sort_keys=True, indent=2) + "\n"
    return files


def reference(files, prefix=""):
    return render(derive(files, PARAMS, prefix))


def _reachable(path):
    """Grading stages its corpora as root and runs the graded program under an
    unprivileged account, so every path handed to that program has to stay
    readable from outside the staging account."""
    try:
        path.chmod(0o755 if path.is_dir() else 0o644)
    except OSError:
        pass


def _stage(files, name=None):
    root = Path(tempfile.mkdtemp(prefix="stall-in-"))
    _reachable(root)
    if name is not None:
        root = root / name
        root.mkdir(parents=True)
        _reachable(root)
    for fname in sorted(files):
        path = root / fname
        path.write_text(files[fname], encoding="utf-8", newline="\n")
        _reachable(path)
    return root


def _run(input_dir, output_dir, script):
    assert Path(script).is_file(), "%s is missing" % PROGRAM
    _reachable(Path(script))
    output_dir = Path(output_dir)
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        parent.chmod(0o777)
    except PermissionError:
        pass
    before = set(p.resolve() for p in parent.rglob("*"))
    proc = subprocess.run(
        _untrusted_command([sys.executable, str(script), str(input_dir),
                            str(output_dir)]),
        text=True, capture_output=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-600:]
    stray = [p for p in set(p.resolve() for p in parent.rglob("*")) - before
             if output_dir.resolve() not in [p, *p.parents]]
    assert not stray, "the program wrote outside its output directory: %s" % stray
    return dict((name, (output_dir / name).read_text(encoding="utf-8"))
                for name in ARTIFACT_NAMES)


def _delivered(out_dir):
    return dict((name, (Path(out_dir) / name).read_text(encoding="utf-8"))
                for name in ARTIFACT_NAMES)


def _delivered_code(out_dir):
    """The delivered program's executable text, comments and docstrings dropped.
    A name that survives here is one the program can act on; a name an honest
    author only mentioned in prose is not a runtime read and must not be
    penalised."""
    text = (Path(out_dir) / PROGRAM).read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef))
                and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body[0].value.value = ""
    return ast.unparse(tree)


def _residual_holds(rendered):
    summary = json.loads(rendered["summary.json"])
    quality = json.loads(rendered["data_quality.json"])
    emitted = summary["total_bytes_emitted"]
    logged = summary["total_bytes_logged"]
    assert quality["reconciliation"]["emitted_bytes"] == emitted
    assert quality["reconciliation"]["logged_bytes"] == logged
    assert quality["reconciliation"]["residual_bytes"] == emitted - logged
    assert quality["accepted_count"] == summary["accepted_count"]
    cells = sum(json.loads(rendered["region_%s.json" % c])["accepted_count"]
                for c in CELLS)
    assert cells == summary["accepted_count"], "cell reports lose events"
    segments = sum(
        json.loads(rendered["segment_%s.json" % s])["accepted_count"]
        for s in TENANT_SEGMENTS)
    assert segments == summary["accepted_count"], "segment reports lose events"


def _match(got, want, names):
    for name in names:
        assert got[name] == want[name], "%s differs from the reference" % name


GRADED_QUALITY_KEYS = ("accepted_count", "event_count", "rejections",
                       "reconciliation")
POST_MORTEM_REPORTS = [n for n in ARTIFACT_NAMES if n != "data_quality.json"]


def _match_post_mortem(got, want):
    _match(got, want, POST_MORTEM_REPORTS)
    mine = json.loads(got["data_quality.json"])
    theirs = json.loads(want["data_quality.json"])
    for key in GRADED_QUALITY_KEYS:
        assert mine[key] == theirs[key], "data_quality %s differs" % key
    assert mine["settlement"]["quarantined_classes"] == \
        theirs["settlement"]["quarantined_classes"], "quarantine set differs"


# Side-table shapes and owner spellings each hidden window carries.
PLANTS = {
    "trap-zigzag_wait": {"cells": ("North", "South", "West")},
    "trap-sentinel": {"cells": ("East", "South", "West")},
    "new_entity": {"cells": ("East", "North", "West")},
    "trap-stride": {"segments": ("public",)},
    "trap-coarse_spins": {"segments": ("commercial",)},
    "fresh": {"segments": ("public",)},
    "scale_population": {"segments": ("commercial",)},
    "trap-le_origin": {"cells": ("East", "West"), "segments": ("commercial",)},
    "trap-alias": {"cells": ("South",), "segments": ("public",)},
    "partition_count": {"segments": ("public",)},
    "tie_config": {"cells": ("East", "North", "South"),
                   "segments": ("commercial",)},
    "trap-chain_hold": {"alias_owner": True},
    "trap-count_bias": {"alias_owner": True},
    "trap-chain_origin": {"alias_owner": True},
    "trap-ring_owner": {"alias_owner": True},
    "trap-rot_token": {"alias_owner": True},
    "trap-shadow_slot": {"alias_owner": True},
    "cap_edge": {"alias_owner": True},
    "boundary_shift": {"alias_owner": True},
    "rule_order": {"alias_owner": True},
    "nonapplying_rule": {"alias_owner": True},
    "contradict_calibration": {"alias_owner": True},
    "single_revision": {"alias_owner": True},
}


def _end_to_end(label, mutation, program, plants=None):
    seed = _mix(EVAL_SEED, label)
    files = _population("challenge", seed, mutation, "", None, plants)
    root = _stage(files)
    out = Path(tempfile.mkdtemp(prefix="stall-out-")) / "post"
    got = _run(root, out, program)
    _match_post_mortem(got, reference(files))
    _residual_holds(got)


def _trap_probe(label, flag, program, plants=None):
    seed = _mix(EVAL_SEED, "trap-" + label)
    files = _population("challenge", seed, None, "", flag, plants)
    root = _stage(files)
    out = Path(tempfile.mkdtemp(prefix="stall-trap-")) / "post"
    got = _run(root, out, program)
    _match_post_mortem(got, reference(files))
    _residual_holds(got)


# -------------------------------------------------------------------- format
@criterion(description="every declared deliverable of the post mortem set is present at the output root")
def post_mortem_set_is_complete(workspace):
    out_dir = Path(workspace) / "out"
    try:
        return all((out_dir / name).is_file() for name in DELIVERABLES)
    except Exception:
        return False


@criterion(description="the delivered program carries the no-argument fallback input and output locations it owes")
def post_mortem_program_carries_its_promised_fallback_locations(workspace):
    out_dir = Path(workspace) / "out"
    try:
        text = _delivered_code(out_dir)
        return FALLBACK_INPUT in text and FALLBACK_OUTPUT in text
    except Exception:
        return False


# ------------------------------------------------------------------ instance
@criterion(description="the delivered incident window summary for the shipped corpus is exact")
def shipped_window_summary_matches_the_reference(workspace):
    out_dir = Path(workspace) / "out"
    try:
        files = shipped_population()
        _match(_delivered(out_dir), reference(files), ["summary.json"])
        return True
    except Exception:
        return False


@criterion(description="the delivered lock class and worker audit for the shipped corpus is exact")
def shipped_policy_audit_matches_the_reference(workspace):
    out_dir = Path(workspace) / "out"
    try:
        files = shipped_population()
        _match(_delivered(out_dir), reference(files), ["policy_audit.json"])
        return True
    except Exception:
        return False


@criterion(description="every delivered service cell report for the shipped corpus is exact")
def shipped_cell_reports_match_the_reference(workspace):
    out_dir = Path(workspace) / "out"
    try:
        files = shipped_population()
        _match(_delivered(out_dir), reference(files),
               ["region_%s.json" % c for c in CELLS])
        return True
    except Exception:
        return False


@criterion(description="every delivered tenant segment report for the shipped corpus is exact")
def shipped_tenant_segment_reports_match_the_reference(workspace):
    out_dir = Path(workspace) / "out"
    try:
        files = shipped_population()
        _match(_delivered(out_dir), reference(files),
               ["segment_%s.json" % s for s in TENANT_SEGMENTS])
        return True
    except Exception:
        return False


@criterion(description="the delivered reconciliation record carries the shipped tallies and its schema")
def shipped_reconciliation_record_matches_the_reference(workspace):
    out_dir = Path(workspace) / "out"
    try:
        files = shipped_population()
        got = _delivered(out_dir)
        want = json.loads(reference(files)["data_quality.json"])
        quality = json.loads(got["data_quality.json"])
        for key in GRADED_QUALITY_KEYS:
            if quality[key] != want[key]:
                return False
        return (isinstance(quality["calibration_comparison"], list)
                and isinstance(quality["candidate_search"], dict)
                and isinstance(quality["candidate_search"].get("evaluations"), int)
                and isinstance(quality["candidate_search"].get("parameters"), list)
                and isinstance(quality["settlement"], dict)
                and isinstance(quality["settlement"].get("passes"), int)
                and isinstance(quality["settlement"].get("quarantined_classes"), list))
    except Exception:
        return False


# ---------------------------------------------------------------------- trap
@criterion(description="wait spans written as zig-zag differences are recovered")
def trap_zigzag_wait_inverse(workspace):
    try:
        _trap_probe("zigzag_wait", F_ZIGZAG_WAIT, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-zigzag_wait"))
        return True
    except Exception:
        return False


@criterion(description="hold spans masked with the previous wait are recovered")
def trap_chained_hold_mask_inverse(workspace):
    try:
        _trap_probe("chain_hold", F_XOR_CHAIN_HOLD, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-chain_hold"))
        return True
    except Exception:
        return False


@criterion(description="event lines written at stride positions are restored to logical order")
def trap_stride_interleave_inverse(workspace):
    try:
        _trap_probe("stride", F_STRIDE_INTERLEAVE, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-stride"))
        return True
    except Exception:
        return False


@criterion(description="the biased declared count is corrected before events split from padding")
def trap_biased_declared_count_inverse(workspace):
    try:
        _trap_probe("count_bias", F_BIASED_COUNT, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-count_bias"))
        return True
    except Exception:
        return False


@criterion(description="an origin numeral written low pair first is read correctly")
def trap_reversed_origin_pairs_inverse(workspace):
    try:
        _trap_probe("le_origin", F_LE_ORIGIN, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-le_origin"))
        return True
    except Exception:
        return False


@criterion(description="an origin written against the previous segment is accumulated")
def trap_chained_segment_origin_inverse(workspace):
    try:
        _trap_probe("chain_origin", F_CHAIN_ORIGIN, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-chain_origin"))
        return True
    except Exception:
        return False


@criterion(description="the depth following an escaped symbol is uncomplemented")
def trap_sentinel_escape_inverse(workspace):
    try:
        _trap_probe("sentinel", F_SENTINEL_ESCAPE, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-sentinel"))
        return True
    except Exception:
        return False


@criterion(description="an owner written as a rolling window reference is resolved")
def trap_ring_owner_reference_inverse(workspace):
    try:
        _trap_probe("ring_owner", F_RING_OWNER, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-ring_owner"))
        return True
    except Exception:
        return False


@criterion(description="a spin count escaped into a coarse unit is restored")
def trap_coarse_spin_escape_inverse(workspace):
    try:
        _trap_probe("coarse_spins", F_COARSE_SPINS, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-coarse_spins"))
        return True
    except Exception:
        return False


@criterion(description="a rotated wait for token is restored after its check total holds")
def trap_rotated_token_inverse(workspace):
    try:
        _trap_probe("rot_token", F_ROT_TOKEN, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-rot_token"))
        return True
    except Exception:
        return False


@criterion(description="an aliased worker column resolves through the registry")
def trap_registry_alias_worker_inverse(workspace):
    try:
        _trap_probe("alias", F_POOL_ALIAS, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-alias"))
        return True
    except Exception:
        return False


@criterion(description="the authoritative slot is taken from the symbol column")
def trap_shadow_slot_inverse(workspace):
    try:
        _trap_probe("shadow_slot", F_SHADOW_SLOT, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("trap-shadow_slot"))
        return True
    except Exception:
        return False


# ------------------------------------------------------------ generalisation
@criterion(description="an unseen stall window is reconstructed exactly")
def generalises_to_a_fresh_stall_window(workspace):
    try:
        _end_to_end("fresh", None, Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("fresh"))
        return True
    except Exception:
        return False


@criterion(description="a window whose budget ladder moves its ties is reconstructed exactly")
def generalises_when_budget_ties_move(workspace):
    try:
        _end_to_end("tie_config", "tie_config", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("tie_config"))
        return True
    except Exception:
        return False


@criterion(description="a window whose waits sit on the budget edge is reconstructed exactly")
def generalises_when_waits_sit_on_the_budget(workspace):
    try:
        _end_to_end("cap_edge", "cap_edge", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("cap_edge"))
        return True
    except Exception:
        return False


@criterion(description="a window whose registry rows arrive in inverted order is reconstructed exactly")
def generalises_when_registry_presentation_order_inverts(workspace):
    try:
        _end_to_end("rule_order", "rule_order", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("rule_order"))
        return True
    except Exception:
        return False


@criterion(description="a window that leaves one service cell empty is reconstructed exactly")
def generalises_when_a_service_cell_empties(workspace):
    try:
        _end_to_end("empty_group", "empty_group", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("empty_group"))
        return True
    except Exception:
        return False


@criterion(description="a window whose registry carries an alias cycle is reconstructed exactly")
def generalises_when_the_registry_carries_a_cycle(workspace):
    try:
        _end_to_end("cycle", "cycle", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("cycle"))
        return True
    except Exception:
        return False


@criterion(description="a window whose pool boundary shifts by one tick is reconstructed exactly")
def generalises_when_the_pool_boundary_shifts(workspace):
    try:
        _end_to_end("boundary_shift", "boundary_shift", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("boundary_shift"))
        return True
    except Exception:
        return False


@criterion(description="a window carrying a worker the registry newly admits is reconstructed exactly")
def generalises_when_a_new_worker_enters(workspace):
    try:
        _end_to_end("new_entity", "new_entity", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("new_entity"))
        return True
    except Exception:
        return False


@criterion(description="a window that wakes the dormant hop limit rule is reconstructed exactly")
def generalises_when_a_dormant_rule_fires(workspace):
    try:
        _end_to_end("nonapplying_rule", "nonapplying_rule", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("nonapplying_rule"))
        return True
    except Exception:
        return False


@criterion(description="a window whose cell partition count changes is reconstructed exactly")
def generalises_when_the_partition_count_changes(workspace):
    try:
        _end_to_end("partition_count", "partition_count", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("partition_count"))
        return True
    except Exception:
        return False


@criterion(description="a window an order of magnitude larger is reconstructed exactly")
def generalises_when_the_window_scales(workspace):
    try:
        _end_to_end("scale_population", "scale_population", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("scale_population"))
        return True
    except Exception:
        return False


@criterion(description="a window whose pool ranges contradict the shipped tallies is reconstructed exactly")
def generalises_when_the_window_contradicts_the_control_slice(workspace):
    try:
        _end_to_end("contradict_calibration", "contradict_calibration", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("contradict_calibration"))
        return True
    except Exception:
        return False


@criterion(description="a window whose registry carries one live row per tag is reconstructed exactly")
def generalises_when_every_tag_has_one_live_row(workspace):
    try:
        _end_to_end("single_revision", "single_revision", Path(workspace) / "out" / PROGRAM,
                    PLANTS.get("single_revision"))
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ negative
@criterion(description="the delivered program embeds shipped-corpus totals, seeds or the summary digest as literals")
def negative_hardcoded_sample_answers(workspace):
    # inverted: returns True only when a shipped marker is baked into the
    # delivered code; an honest program has none and escapes the penalty
    try:
        text = _delivered_code(Path(workspace) / "out")
        files = shipped_population()
        want = json.loads(reference(files)["summary.json"])
        digest = hashlib.sha256(json.dumps(want, sort_keys=True).encode()).hexdigest()
        markers = [digest, str(EVAL_SEED), str(CHALLENGE_SEED),
                   str(want["total_bytes_logged"]), str(want["total_bytes_emitted"])]
        return any(marker in text for marker in markers)
    except Exception:
        return False


@criterion(description="the delivered program produces different output when the input directory is renamed")
def negative_filename_dependent_behaviour(workspace):
    # inverted: returns True only when the output changes with the directory
    # name; a name-independent program stays equal and escapes the penalty
    program = Path(workspace) / "out" / PROGRAM
    try:
        files = _population("challenge", _mix(EVAL_SEED, "filename"))
        first = _stage(files)
        second = _stage(files, "journal-drop-2")
        out_a = Path(tempfile.mkdtemp(prefix="stall-a-")) / "d"
        out_b = Path(tempfile.mkdtemp(prefix="stall-b-")) / "d"
        out_c = Path(tempfile.mkdtemp(prefix="stall-c-")) / "d"
        settled = _run(first, out_a, program)
        return settled == _run(first, out_c, program) and settled != _run(second, out_b, program)
    except Exception:
        return False


@criterion(description="the delivered program reads the labelled sample answer files at run time")
def negative_reads_supplied_answer_data_at_runtime(workspace):
    # inverted: returns True only when the executable text names an answer
    # file; an honest program names none and escapes the penalty
    try:
        text = _delivered_code(Path(workspace) / "out")
        return any(name in text for name in ANSWER_FILES)
    except Exception:
        return False


@criterion(description="the delivered program emits a different post mortem set on two identical runs")
def negative_nondeterministic_output(workspace):
    # inverted: returns True only when two identical runs disagree; a stable
    # program returns equal sets and escapes the penalty
    program = Path(workspace) / "out" / PROGRAM
    try:
        files = _population("challenge", _mix(EVAL_SEED, "determinism"))
        root = _stage(files)
        out_a = Path(tempfile.mkdtemp(prefix="stall-d1-")) / "d"
        out_b = Path(tempfile.mkdtemp(prefix="stall-d2-")) / "d"
        return _run(root, out_a, program) != _run(root, out_b, program)
    except Exception:
        return False


def _write_corpus(target):
    """Rewrite the generated files under environment/data from the seeds this
    module declares. The authored rule documents and the worked example are
    left alone."""
    target = Path(target)
    if target.name != "data":
        target = target / "data"
    target.mkdir(parents=True, exist_ok=True)
    written = 0
    for name, text in sorted(shipped_population().items()):
        (target / name).write_text(text, encoding="utf-8", newline=chr(10))
        written += 1
    print(json.dumps({"written": written}, sort_keys=True))
    return written


criteria.post_mortem_set_is_complete(weight=1)
criteria.post_mortem_program_carries_its_promised_fallback_locations(weight=1)
criteria.shipped_window_summary_matches_the_reference(weight=3)
criteria.shipped_policy_audit_matches_the_reference(weight=3)
criteria.shipped_cell_reports_match_the_reference(weight=3)
criteria.shipped_tenant_segment_reports_match_the_reference(weight=3)
criteria.shipped_reconciliation_record_matches_the_reference(weight=3)
criteria.trap_zigzag_wait_inverse(weight=5)
criteria.trap_chained_hold_mask_inverse(weight=5)
criteria.trap_stride_interleave_inverse(weight=5)
criteria.trap_biased_declared_count_inverse(weight=5)
criteria.trap_reversed_origin_pairs_inverse(weight=5)
criteria.trap_chained_segment_origin_inverse(weight=5)
criteria.trap_sentinel_escape_inverse(weight=5)
criteria.trap_ring_owner_reference_inverse(weight=5)
criteria.trap_coarse_spin_escape_inverse(weight=5)
criteria.trap_rotated_token_inverse(weight=5)
criteria.trap_registry_alias_worker_inverse(weight=5)
criteria.trap_shadow_slot_inverse(weight=5)
criteria.generalises_to_a_fresh_stall_window(weight=5)
criteria.generalises_when_budget_ties_move(weight=5)
criteria.generalises_when_waits_sit_on_the_budget(weight=5)
criteria.generalises_when_registry_presentation_order_inverts(weight=5)
criteria.generalises_when_a_service_cell_empties(weight=5)
criteria.generalises_when_the_registry_carries_a_cycle(weight=5)
criteria.generalises_when_the_pool_boundary_shifts(weight=5)
criteria.generalises_when_a_new_worker_enters(weight=5)
criteria.generalises_when_a_dormant_rule_fires(weight=5)
criteria.generalises_when_the_partition_count_changes(weight=5)
criteria.generalises_when_the_window_scales(weight=5)
criteria.generalises_when_the_window_contradicts_the_control_slice(weight=5)
criteria.generalises_when_every_tag_has_one_live_row(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_supplied_answer_data_at_runtime(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]) if len(sys.argv) > 1
                  else Path("environment/data"))
