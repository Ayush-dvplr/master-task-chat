#!/usr/bin/env python3
"""Halvard playout centre: reconciliation of one workload of a close extract.

Usage: python3 optimize.py DATA_DIR WORKLOAD

Prints the scenario object of that workload as one JSON document on stdout.
Every rule parameter is read from DATA_DIR; nothing is written anywhere.
"""

import io
import json
import os
import re
import sys
from bisect import bisect_right, bisect_left
from datetime import date

TPS = 30000                      # ticks per second
MINUTE_TICKS = 60 * TPS
EPOCH_ORD = 719163               # date(1970, 1, 1).toordinal()
_OPEN_END = 1 << 62                # sentinel for an interval with no end

DISPOSITIONS = ("UNRESOLVED", "PREEMPTED", "MISSED", "PARTIAL", "WRONG_COPY",
                "AIRED", "OUT_OF_WINDOW")
REASON_CODES = ("BAD_TIMECODE", "DROPPED_LABEL", "MISSING_FIELD")
CHAIN_SOURCES = ("A", "B")
NON_CHAIN_SOURCES = ("LIVE1", "LIVE2", "SLATE")
WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")

_LABEL_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})([:;])(\d{2})$")
_HOUSE_RE = re.compile(r"^([A-Z]{3})(\d{1,5})$")
_INST_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")

_AS_RUN_FIELDS = ("seq", "date", "tc", "evt", "spot", "house", "frames", "status")


class InputError(Exception):
    pass


# ------------------------------------------------------------- primitives

def _days(iso_date):
    y, m, d = iso_date.split("-")
    return date(int(y), int(m), int(d)).toordinal() - EPOCH_ORD


def _iso(days):
    return date.fromordinal(days + EPOCH_ORD).isoformat()


def _instant_ticks(text):
    m = _INST_RE.match(text.strip())
    if not m:
        raise InputError("bad instant %r" % (text,))
    yy, mm, dd, hh, mi, ss = (int(m.group(i)) for i in range(1, 7))
    ticks = (_days("%04d-%02d-%02d" % (yy, mm, dd)) * 86400
             + hh * 3600 + mi * 60 + ss) * TPS
    if m.group(7):
        ticks += int(round(float("0." + m.group(7)[1:]) * TPS))
    tz = m.group(8)
    if tz and tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        body = tz[1:].replace(":", "")
        ticks -= sign * (int(body[:2]) * 60 + int(body[2:])) * MINUTE_TICKS
    return ticks


def normalize_house(raw):
    if raw is None:
        return None
    h = raw.strip().upper().replace(" ", "").replace("-", "")
    m = _HOUSE_RE.match(h)
    if not m:
        return None
    return "%s-%s" % (m.group(1), m.group(2).zfill(5))


class Channel(object):
    """Timecode arithmetic of one workload's channel."""

    def __init__(self, frame_rate, timecode, plain30=False):
        if frame_rate == "30000/1001":
            self.nominal = 30
            self.frame_ticks = 1001
        else:
            self.nominal = int(frame_rate)
            self.frame_ticks = TPS // self.nominal
        self.drop = (timecode == "drop")
        self.sep = ";" if self.drop else ":"
        self.plain30 = plain30 and self.drop
        self.start_count = 0

    def count(self, hh, mi, ss, ff):
        if self.drop:
            if self.plain30:
                return ((hh * 60 + mi) * 60 + ss) * 30 + ff
            t = hh * 60 + mi
            return ((hh * 60 + mi) * 60 + ss) * 30 + ff - 2 * (t - t // 10)
        return ((hh * 60 + mi) * 60 + ss) * self.nominal + ff

    @property
    def day(self):
        return self.count(24, 0, 0, 0)

    def parse_label(self, tc):
        """(hh, mm, ss, ff) of a valid label, else None."""
        m = _LABEL_RE.match(tc)
        if not m or m.group(4) != self.sep:
            return None
        hh, mi, ss, ff = (int(m.group(i)) for i in (1, 2, 3, 5))
        if hh > 23 or mi > 59 or ss > 59 or ff >= self.nominal:
            return None
        return (hh, mi, ss, ff)

    def is_dropped_label(self, parsed):
        hh, mi, ss, ff = parsed
        return (self.drop and ss == 0 and ff < 2 and mi % 10 != 0)

    def bound(self, text):
        """Frame count of an HH:MM or HH:MM:SS bound."""
        parts = text.strip().split(":")
        hh = int(parts[0])
        mi = int(parts[1]) if len(parts) > 1 else 0
        ss = int(parts[2]) if len(parts) > 2 else 0
        return self.count(hh, mi, ss, 0)

    def index_of(self, iso_date, parsed):
        return _days(iso_date) * self.day + self.count(*parsed)

    def local_ticks(self, iso_date, parsed):
        return (_days(iso_date) * 86400 * TPS
                + self.count(*parsed) * self.frame_ticks)

    def broadcast_clock(self, index):
        """(broadcast date as day number, broadcast clock count)."""
        d, cnt = divmod(index, self.day)
        if cnt < self.start_count:
            return (d - 1, cnt + self.day)
        return (d, cnt)


class Zone(object):
    """Local to UTC conversion for one zone's transitions."""

    def __init__(self, transitions):
        rows = sorted((_instant_ticks(t["from_utc"]), int(t["offset_minutes"]))
                      for t in transitions)
        self.starts = [r[0] for r in rows]
        self.offsets = [r[1] for r in rows]
        self.local_starts = [r[0] + r[1] * MINUTE_TICKS for r in rows]

    def utc_from_local(self, local_ticks):
        i = bisect_right(self.local_starts, local_ticks) - 1
        if i < 0:
            i = 0
        return local_ticks - self.offsets[i] * MINUTE_TICKS


# ------------------------------------------------------------------ loading

def _read_text(path):
    try:
        with open(path, "r") as fh:
            return fh.read()
    except OSError:
        raise InputError("missing file %s" % path)


def _read_json(path):
    return json.loads(_read_text(path))


def _read_csv_rows(path, delimiter=","):
    import csv
    return list(csv.DictReader(io.StringIO(_read_text(path)), delimiter=delimiter))


def _read_jsonl(path):
    return [json.loads(line) for line in _read_text(path).splitlines()
            if line.strip()]


def _read_ini(path):
    sections = {}
    name = None
    for raw in _read_text(path).splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            sections.setdefault(name, {})
            continue
        if "=" in line and name is not None:
            key, value = line.split("=", 1)
            sections[name][key.strip()] = value.strip()
    return sections


_PRIOR_CACHE = {}


def _prior_records(data_dir):
    key = os.path.abspath(data_dir)
    if key not in _PRIOR_CACHE:
        _PRIOR_CACHE[key] = _read_jsonl(
            os.path.join(data_dir, "prior_close_decisions.jsonl"))
    return _PRIOR_CACHE[key]


# -------------------------------------------------- prior close settlements

_WINDOW_FORMS = (
    ("span", lambda s, bc, e, eframes: s <= bc and bc + eframes <= e),
    ("start", lambda s, bc, e, eframes: s <= bc < e),
    ("span_strict", lambda s, bc, e, eframes: s < bc and bc + eframes < e),
    ("end", lambda s, bc, e, eframes: s <= bc + eframes <= e),
)
_STRADDLE_FORMS = (
    ("complete_le", lambda complete, off, tol: complete and off <= tol),
    ("complete_lt", lambda complete, off, tol: complete and off < tol),
    ("off_le", lambda complete, off, tol: off <= tol),
    ("complete_or_le", lambda complete, off, tol: complete or off <= tol),
)
_TIE_FORMS = (
    ("traffic", lambda top: [v for v in top if v[1] == "traffic"]),
    ("mcr", lambda top: [v for v in top if v[1] == "mcr"]),
    ("later", lambda top: [max(top, key=lambda v: v[2])]),
    ("earlier", lambda top: [min(top, key=lambda v: v[2])]),
)


def _settlements(records):
    chosen = {"window": "span", "straddle": "complete_le", "tie": "traffic"}
    edges = [r for r in records if r.get("kind") == "window_edge"]
    for plain30 in (False, True):
        found = None
        for key, form in _WINDOW_FORMS:
            ok = True
            for r in edges:
                drop = r["rate"] == "30000/1001"
                chan = Channel("30000/1001" if drop else str(r["rate"]),
                               "drop" if drop else "nondrop", plain30=plain30)
                parsed = chan.parse_label(r["start_tc"])
                if parsed is None:
                    ok = False
                    break
                bc = chan.count(*parsed)
                if r["after_local_midnight"]:
                    bc += chan.day
                lo, hi = r["window"].split("-")
                inside = form(chan.bound(lo), bc, chan.bound(hi), r["frames"])
                if ("in_window" if inside else "out_of_window") != r["outcome"]:
                    ok = False
                    break
            if ok:
                found = key
                break
        if found:
            chosen["window"] = found
            break
    straddles = [r for r in records if r.get("kind") == "failover_straddle"]
    for key, form in _STRADDLE_FORMS:
        ok = True
        for r in straddles:
            drop = r["rate"] == "30000/1001"
            chan = Channel("30000/1001" if drop else str(r["rate"]),
                           "drop" if drop else "nondrop")
            a = chan.parse_label(r["on_air_start_tc"])
            b = chan.parse_label(r["other_start_tc"])
            if a is None or b is None:
                ok = False
                break
            aired = form(bool(r["other_complete"]),
                         abs(chan.count(*b) - chan.count(*a)),
                         int(r["tolerance_frames"]))
            if ("aired" if aired else "partial") != r["outcome"]:
                ok = False
                break
        if ok:
            chosen["straddle"] = key
            break
    ties = [r for r in records if r.get("kind") == "correction_tie"]
    for key, form in _TIE_FORMS:
        ok = True
        for r in ties:
            versions = r["versions"]
            top_rev = max(int(v["rev"]) for v in versions)
            top = [v for v in versions if int(v["rev"]) == top_rev]
            rows = [(v["rev"], v.get("desk"), _instant_ticks(v["recorded_at"]),
                     v.get("recorded_at"), v["order_line"]) for v in top]
            picks = set(row[4] for row in form(rows))
            if len(picks) != 1 or picks.pop() != r["outcome_order_line"]:
                ok = False
                break
        if ok:
            chosen["tie"] = key
            break
    return chosen


# -------------------------------------------------------------- the context

class Context(object):
    pass


def _load_context(data_dir, workload, variant=None):
    variant = variant or {}
    sections = _read_ini(os.path.join(data_dir, "channels.ini"))
    if workload not in sections:
        raise InputError("no workload %s" % workload)
    conf = sections[workload]
    for key in ("channel", "frame_rate", "timecode", "zone", "week_start",
                "broadcast_days", "broadcast_day_start", "daypart_set",
                "sync_tolerance_frames"):
        if key not in conf:
            raise InputError("channels.ini key %s" % key)

    ctx = Context()
    ctx.variant = variant
    ctx.data_dir = data_dir
    ctx.workload = workload
    ctx.channel_code = conf["channel"]
    ctx.chan = Channel(conf["frame_rate"], conf["timecode"],
                       plain30=variant.get("plain30", False))
    ctx.chan.start_count = ctx.chan.bound(conf["broadcast_day_start"])
    ctx.tolerance = int(conf["sync_tolerance_frames"])

    zones = _read_json(os.path.join(data_dir, "utc_offsets.json"))["zones"]
    if conf["zone"] not in zones:
        raise InputError("zone %s" % conf["zone"])
    ctx.zone = Zone(zones[conf["zone"]])

    daypart_sets = _read_json(os.path.join(data_dir, "dayparts.json"))["sets"]
    if conf["daypart_set"] not in daypart_sets:
        raise InputError("daypart set %s" % conf["daypart_set"])
    ctx.dayparts = [(d["daypart"], ctx.chan.bound(d["start"]),
                     ctx.chan.bound(d["end"]))
                    for d in daypart_sets[conf["daypart_set"]]]

    holidays = _read_json(os.path.join(data_dir, "holidays.json"))
    ctx.blackout = set(
        holidays.get("blackout_broadcast_dates", {}).get(ctx.channel_code, ()))

    policy = _read_json(os.path.join(data_dir, "close_policy.json"))
    ctx.cutoff = _instant_ticks(policy["cutoff_utc"][workload])
    ctx.grace_days = int(policy["makegood_grace_days"])

    ctx.advertisers = _read_json(
        os.path.join(data_dir, "advertisers.json"))["advertisers"]

    ctx.orders = {}
    for row in _read_csv_rows(os.path.join(data_dir, "orders.csv")):
        if row["workload"] == workload:
            ctx.orders[row["order_line"]] = row
    ctx.order_names = sorted(ctx.orders)

    ctx.registry = {}
    for row in _read_csv_rows(os.path.join(data_dir, "copy_registry.csv")):
        ctx.registry[normalize_house(row["house_id"])] = (
            int(row["frames"]), int(row["master_rate"]))

    alias_best = {}
    for row in _read_csv_rows(os.path.join(data_dir, "house_aliases.csv")):
        old = normalize_house(row["old_house_id"])
        new = normalize_house(row["new_house_id"]) or ""
        eff = row["effective_from"]
        if old not in alias_best or (eff, new) > alias_best[old][:2]:
            alias_best[old] = (eff, new, eff)
    ctx.aliases = dict((k, v[1] or None) for k, v in alias_best.items())
    ctx.alias_eff = dict((k, v[0]) for k, v in alias_best.items())
    ctx.undated_aliases = variant.get("undated_aliases", False)
    ctx.expected_raw = variant.get("expected_raw", False)
    ctx.onair_mode = variant.get("onair_mode", "real")
    ctx.admit_late = variant.get("admit_late", False)
    ctx.b_uncorrected = variant.get("b_uncorrected", False)
    ctx.relock_printed = variant.get("relock_printed", False)
    ctx.settle = _settlements(_prior_records(data_dir))
    if variant.get("window_form"):
        ctx.settle = dict(ctx.settle)
        ctx.settle["window"] = variant["window_form"]
    if variant.get("straddle_form"):
        ctx.settle = dict(ctx.settle)
        ctx.settle["straddle"] = variant["straddle_form"]

    first = _days(conf["week_start"])
    count = int(conf["broadcast_days"])
    ctx.dates = [_iso(first + i) for i in range(count)]
    ctx.date_set = set(ctx.dates)
    ctx.last_day = first + count - 1

    _load_workload_files(ctx)
    _load_corrections(ctx)
    _load_amendments(ctx)
    return ctx


def _load_workload_files(ctx):
    d, w, chan = ctx.data_dir, ctx.workload, ctx.chan

    ctx.schedule = _read_csv_rows(os.path.join(d, "%s_schedule.csv" % w))
    ctx.break_rows = _read_csv_rows(os.path.join(d, "%s_breaks.tsv" % w),
                                   delimiter="\t")

    ctx.break_info = {}
    for row in ctx.break_rows:
        parsed = chan.parse_label(row["open_tc"])
        if parsed is None:
            raise InputError("bad open_tc %r" % (row["open_tc"],))
        index = chan.index_of(row["local_date"], parsed)
        bday, bcc = chan.broadcast_clock(index)
        daypart = None
        for name, lo, hi in ctx.dayparts:
            if lo <= bcc < hi:
                daypart = name
                break
        ctx.break_info[row["break_id"]] = {
            "broadcast_date": _iso(bday), "day": _days(_iso(bday)), "bcc": bcc,
            "capacity": int(row["capacity_frames"]), "daypart": daypart,
        }

    # master control switcher: on-air intervals
    pgm = []
    for line in _read_text(os.path.join(d, "%s_switcher.log" % w)).splitlines():
        line = line.strip()
        if not line or "BUS=PGM" not in line:
            continue
        fields = dict(token.split("=", 1) for token in line.split(" ")
                      if "=" in token)
        src = fields.get("SRC")
        if not src:
            continue
        pgm.append((_instant_ticks(line.split(" ")[0]), src))
    pgm.sort(key=lambda row: row[0])
    starts, sources = [], []
    for instant, src in pgm:
        if sources and sources[-1] == src:
            continue
        starts.append(instant)
        sources.append(src)
    ctx.air_starts = starts
    ctx.air_sources = sources
    ctx.air_by_src = {}
    for s_src in set(sources):
        lo_list, hi_list = [], []
        for j, s in enumerate(sources):
            if s != s_src:
                continue
            end = starts[j + 1] if j + 1 < len(starts) else _OPEN_END
            if lo_list and hi_list[-1] == starts[j]:
                hi_list[-1] = end
            else:
                lo_list.append(starts[j])
                hi_list.append(end)
        ctx.air_by_src[s_src] = (lo_list, hi_list)

    # chain B sync probes
    ctx.relock_probes = 0
    ctx.stale_probes = 0
    ctx.probe_instants = []
    ctx.probe_offsets = []
    if not ctx.b_uncorrected:
        rows = []
        for line in _read_text(os.path.join(d, "%s_sync_probes.log"
                                            % w)).splitlines():
            line = line.strip()
            if not line:
                continue
            fields = dict(token.split("=", 1) for token in line.split(" ")
                          if "=" in token)
            if fields.get("chain") != "B":
                continue
            instant = _instant_ticks(line.split(" ")[0])
            lock = fields.get("lock")
            if lock == "STALE":
                ctx.stale_probes += 1
                continue
            if lock == "RELOCK":
                ctx.relock_probes += 1
                offset = (int(fields.get("offset_frames", "0"))
                          if ctx.relock_printed else 0)
            else:
                offset = int(fields.get("offset_frames", "0"))
            rows.append((instant, offset))
        rows.sort(key=lambda r: r[0])
        for instant, offset in rows:
            ctx.probe_instants.append(instant)
            ctx.probe_offsets.append(offset)

    # as-run logs, de-duplicated byte for byte
    ctx.asrun_lines = {}
    ctx.duplicate_lines = 0
    ctx.lines = {}
    for chain in ("A", "B"):
        path = os.path.join(d, "%s_asrun_%s.log" % (w, chain.lower()))
        seen = set()
        kept = []
        raw = 0
        for line in _read_text(path).splitlines():
            if not line.strip():
                continue
            raw += 1
            if line in seen:
                ctx.duplicate_lines += 1
                continue
            seen.add(line)
            kept.append(line)
        ctx.asrun_lines[chain] = raw
        ctx.lines[chain] = kept


def _load_corrections(ctx):
    cutoff = ctx.cutoff
    by_spot = {}
    retracts = set()
    admitted = 0
    late = 0
    admit_late = ctx.admit_late
    for rec in _read_jsonl(os.path.join(ctx.data_dir,
                                        "%s_corrections.jsonl" % ctx.workload)):
        recorded = _instant_ticks(rec["recorded_at"])
        ok = admit_late or recorded < cutoff
        if ok:
            admitted += 1
        else:
            late += 1
        kind = rec.get("kind")
        if kind == "retract":
            if not ok:
                continue
            target = rec.get("target") or ""
            if ":" in target:
                chain, evt = target.split(":", 1)
                retracts.add((chain, evt))
            continue
        if kind not in ("reattribute", "restore"):
            continue
        if not ok or int(rec.get("rev", 0)) <= 0:
            continue
        by_spot.setdefault(rec.get("target"), []).append(
            (int(rec["rev"]), rec.get("desk"), recorded,
             rec.get("correction_id") or "", kind,
             (rec.get("payload") or {}).get("order_line")))
    ctx.corrections_admitted = admitted
    ctx.corrections_late = late
    ctx.retracts = retracts

    governing = {}
    tie_form = dict(_TIE_FORMS)[ctx.settle["tie"]]
    for spot, entries in by_spot.items():
        top_rev = max(e[0] for e in entries)
        top = [e for e in entries if e[0] == top_rev]
        picks = list(tie_form(top))
        if len(picks) == 1:
            pick = picks[0]
        else:
            pick = max(picks if picks else top, key=lambda e: (e[2], e[3]))
        governing[spot] = pick[5] if pick[4] == "reattribute" else None
    ctx.correction_governing = governing


def _load_amendments(ctx):
    by_line = {}
    admitted = 0
    late = 0
    for rec in _read_jsonl(os.path.join(ctx.data_dir, "order_amendments.jsonl")):
        if rec["order_line"] not in ctx.orders:
            continue
        recorded = _instant_ticks(rec["recorded_at"])
        if recorded >= ctx.cutoff:
            late += 1
            continue
        admitted += 1
        by_line.setdefault(rec["order_line"], []).append(
            (rec["effective_from"], recorded, int(rec["spots_per_day"])))
    ctx.amendments = by_line
    ctx.amendments_admitted = admitted
    ctx.amendments_late = late


# ------------------------------------------------------------ as-run lines

def _parse_asrun(ctx):
    chan = ctx.chan
    frame_ticks = chan.frame_ticks
    zone = ctx.zone
    plays = {"A": {}, "B": {}}
    rejects = []
    total_plays = 0
    retracted = 0
    for chain in ("A", "B"):
        is_b = chain == "B"
        for line in ctx.lines[chain]:
            fields = {}
            for part in line.split("|"):
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key] = value
            if fields.get("type") != "SPOT":
                continue
            if (chain, fields.get("evt")) in ctx.retracts:
                retracted += 1
                continue
            reason = None
            for key in _AS_RUN_FIELDS:
                if not fields.get(key):
                    reason = "MISSING_FIELD"
                    break
            parsed = None
            if reason is None:
                parsed = chan.parse_label(fields["tc"])
                if parsed is None:
                    reason = "BAD_TIMECODE"
                elif chan.is_dropped_label(parsed):
                    reason = "DROPPED_LABEL"
            if reason is not None:
                rejects.append((chain, fields.get("seq", ""), reason))
                continue
            if fields["status"] != "PLAYED":
                continue
            total_plays += 1
            utc = zone.utc_from_local(chan.local_ticks(fields["date"], parsed))
            index = chan.index_of(fields["date"], parsed)
            if is_b and not ctx.b_uncorrected:
                offset = 0
                if ctx.probe_instants:
                    i = bisect_right(ctx.probe_instants, utc) - 1
                    if i >= 0:
                        offset = ctx.probe_offsets[i]
                utc -= offset * frame_ticks
                index -= offset
            spot = fields["spot"]
            key = (utc, int(fields["seq"]), fields["evt"])
            current = plays[chain].get(spot)
            if current is None or key < current[0]:
                plays[chain][spot] = (key, index, fields["house"],
                                      int(fields["frames"]))
    ctx.rejects = rejects
    ctx.plays = plays
    ctx.total_plays = total_plays
    ctx.retracted_lines = retracted
    governing = sum(len(plays[chain]) for chain in ("A", "B"))
    ctx.reairs = total_plays - governing


# --------------------------------------------------------------------- air

def _on_air_at(ctx, instant):
    if ctx.onair_mode == "a_always":
        return "A"
    i = bisect_right(ctx.air_starts, instant) - 1
    if i < 0:
        return None
    return ctx.air_sources[i]


def _intervals_hit(ctx, src, lo, hi):
    if hi <= lo:
        return False
    if ctx.onair_mode == "a_always":
        return src == "A"
    lo_list, hi_list = ctx.air_by_src.get(src, ((), ()))
    i = bisect_left(hi_list, lo)
    return i < len(lo_list) and lo_list[i] < hi


def _non_chain_hit(ctx, lo, hi):
    if ctx.onair_mode == "a_always":
        return False
    for src in NON_CHAIN_SOURCES:
        if _intervals_hit(ctx, src, lo, hi):
            return True
    return False


# ------------------------------------------------------------------ copies

def _resolve(ctx, raw, as_of):
    """(canonical copy id or None, alias rows walked)."""
    current = normalize_house(raw)
    walked = 0
    steps = 0
    while current is not None and current in ctx.aliases:
        if not ctx.undated_aliases and ctx.alias_eff[current] > as_of:
            break
        current = ctx.aliases[current]
        walked += 1
        steps += 1
        if steps > 64:
            return None, walked
    if current is not None and current in ctx.registry:
        return current, walked
    return None, walked


def _expected_frames(ctx, copy_id):
    frames, master_rate = ctx.registry[copy_id]
    if ctx.expected_raw:
        return frames
    return -(-frames * ctx.chan.nominal // master_rate)


# ------------------------------------------------------------------- spots

def _spots(ctx):
    chan = ctx.chan
    frame_ticks = chan.frame_ticks
    window_form = dict(_WINDOW_FORMS)[ctx.settle["window"]]
    straddle_form = dict(_STRADDLE_FORMS)[ctx.settle["straddle"]]
    daypart_bounds = dict((name, (lo, hi)) for name, lo, hi in ctx.dayparts)
    a_plays = ctx.plays["A"]
    b_plays = ctx.plays["B"]
    governing = ctx.correction_governing
    on_air_at = _on_air_at
    alias_spots = 0
    results = []

    for row in ctx.schedule:
        spot = row["spot_id"]
        sched_date = row["broadcast_date"]
        sched_copy, sched_alias = _resolve(ctx, row["house_id"], sched_date)
        if sched_alias:
            alias_spots += 1
        order_line = governing.get(spot)
        if order_line is None:
            order_line = row["order_line"]
        order = ctx.orders.get(order_line)

        a_play = a_plays.get(spot)
        b_play = b_plays.get(spot)
        ref = None
        ref_chain = None
        if a_play is not None and on_air_at(ctx, a_play[0][0]) == "A":
            ref, ref_chain = a_play, "A"
        elif b_play is not None and on_air_at(ctx, b_play[0][0]) == "B":
            ref, ref_chain = b_play, "B"

        item = {
            "spot_id": spot, "order_line": order_line, "chain": None,
            "broadcast_date": sched_date, "disposition": None, "frames": None,
            "break_id": row["break_id"],
        }
        results.append(item)

        if sched_copy is None:
            item["disposition"] = "UNRESOLVED"
            if ref is not None:
                item["chain"] = ref_chain
                item["broadcast_date"] = _iso(chan.broadcast_clock(ref[1])[0])
                item["frames"] = ref[3]
            continue

        if ref is None:
            found = None
            if a_play is not None:
                src = on_air_at(ctx, a_play[0][0])
                if src is not None and src not in CHAIN_SOURCES:
                    found = ("A", a_play)
            if found is None and b_play is not None:
                src = on_air_at(ctx, b_play[0][0])
                if src is not None and src not in CHAIN_SOURCES:
                    found = ("B", b_play)
            if found is not None:
                item["disposition"] = "PREEMPTED"
                item["chain"] = found[0]
                item["broadcast_date"] = _iso(chan.broadcast_clock(found[1][1])[0])
            else:
                item["disposition"] = "MISSED"
            continue

        instant = ref[0][0]
        expected = _expected_frames(ctx, sched_copy)
        span_lo = instant
        span_hi = instant + expected * frame_ticks
        item["chain"] = ref_chain
        item["broadcast_date"] = _iso(chan.broadcast_clock(ref[1])[0])
        item["frames"] = ref[3]
        if _non_chain_hit(ctx, span_lo, span_hi):
            item["disposition"] = "PREEMPTED"
            continue
        if ref[3] < expected:
            item["disposition"] = "PARTIAL"
            other = "B" if ref_chain == "A" else "A"
            partner = ctx.plays[other].get(spot)
            if partner is not None and _intervals_hit(ctx, other, span_lo, span_hi):
                if straddle_form(partner[3] >= expected,
                                 abs(partner[1] - ref[1]), ctx.tolerance):
                    item["disposition"] = None
            if item["disposition"] is not None:
                continue
        play_copy, play_alias = _resolve(ctx, ref[2], sched_date)
        if play_alias:
            alias_spots += 1
        if play_copy is None:
            item["disposition"] = "UNRESOLVED"
        elif play_copy != sched_copy:
            item["disposition"] = "WRONG_COPY"
        else:
            bounds = daypart_bounds.get(order["daypart"] if order else None)
            bcc = chan.broadcast_clock(ref[1])[1]
            if bounds is not None and window_form(bounds[0], bcc, bounds[1],
                                                  expected):
                item["disposition"] = "AIRED"
            else:
                item["disposition"] = "OUT_OF_WINDOW"
    ctx.alias_spots = alias_spots
    return results


# ------------------------------------------------------------ commitments

def _committed(ctx, order_line, iso_date):
    order = ctx.orders[order_line]
    if not (order["flight_start"] <= iso_date < order["flight_end"]):
        return 0
    weekday = WEEKDAY_CODES[date(int(iso_date[0:4]), int(iso_date[5:7]),
                               int(iso_date[8:10])).weekday()]
    if weekday not in order["weekdays"].split():
        return 0
    if iso_date in ctx.blackout:
        return 0
    best = None
    for eff, recorded, spots in ctx.amendments.get(order_line, ()):
        if eff > iso_date:
            continue
        key = (eff, recorded, spots)
        if best is None or key > best:
            best = key
    if best is None:
        return int(order["spots_per_day"])
    return best[2]


def _deliveries(ctx, spots):
    delivered = {}
    held = {}
    for item in spots:
        if item["broadcast_date"] not in ctx.date_set:
            continue
        key = (item["order_line"], item["broadcast_date"])
        if item["disposition"] == "AIRED":
            delivered[key] = delivered.get(key, 0) + 1
        elif item["disposition"] == "UNRESOLVED":
            held[key] = held.get(key, 0) + 1
    rows = []
    for order_line in ctx.order_names:
        for iso_date in ctx.dates:
            committed = _committed(ctx, order_line, iso_date)
            got = delivered.get((order_line, iso_date), 0)
            kept = held.get((order_line, iso_date), 0)
            if committed == 0 and got == 0 and kept == 0:
                continue
            effective = max(committed - kept, 0)
            billable = min(got, effective)
            rows.append({
                "order_line": order_line, "broadcast_date": iso_date,
                "committed": committed, "held": kept, "delivered": got,
                "billable": billable, "shortfall": effective - billable,
                "bonus": got - billable,
            })
    return rows


def _makegoods(ctx, deliveries, spots):
    occupied = {}
    for item in spots:
        if (item["disposition"] in ("AIRED", "OUT_OF_WINDOW", "WRONG_COPY",
                                    "UNRESOLVED")
                and item["frames"] is not None):
            occupied[item["break_id"]] = (occupied.get(item["break_id"], 0)
                                         + item["frames"])
    spare = dict((bid, max(info["capacity"] - occupied.get(bid, 0), 0))
                 for bid, info in ctx.break_info.items())
    units = []
    for row in deliveries:
        for unit in range(1, row["shortfall"] + 1):
            units.append({
                "order_line": row["order_line"],
                "from_date": row["broadcast_date"], "unit": unit,
                "status": None, "break_id": None, "broadcast_date": None,
                "need": 0,
            })
    units.sort(key=lambda u: (
        int(ctx.orders[u["order_line"]]["priority"]), u["from_date"],
        -int(ctx.orders[u["order_line"]]["unit_rate_cents"]), u["order_line"],
        u["unit"]))

    # breaks grouped by daypart, ordered by date, clock and id
    groups = {}
    for bid, info in ctx.break_info.items():
        group = groups.get(info["daypart"])
        if group is None:
            group = groups[info["daypart"]] = ([], [])
        group[0].append(info["day"])
        group[1].append((info["day"], info["bcc"], bid))
    for key in list(groups):
        days, entries = groups[key]
        order = sorted(range(len(entries)), key=lambda i: entries[i])
        groups[key] = ([days[i] for i in order], [entries[i] for i in order])
    max_spare = dict((dp, max(spare[e[2]] for e in groups[dp][1]))
                     for dp in groups)
    # memo[(daypart, need)] indexes the breaks proven too full for that need
    memo = {}

    for unit in units:
        order = ctx.orders[unit["order_line"]]
        daypart = order["daypart"]
        group = groups.get(daypart)
        copy_id, _ = _resolve(ctx, order["house_id"], unit["from_date"])
        need = _expected_frames(ctx, copy_id) if copy_id else 0
        unit["need"] = need
        chosen = None
        if group is not None and max_spare[daypart] >= need:
            days, entries = group
            limit = min(ctx.last_day,
                        _days(order["flight_end"]) - 1 + ctx.grace_days)
            lo = bisect_right(days, _days(unit["from_date"]))
            hi = bisect_right(days, limit)
            key = (daypart, need)
            proven = memo.get(key, 0)
            start = lo if lo > proven else proven
            for i in range(start, hi):
                bid = entries[i][2]
                if spare[bid] >= need:
                    chosen = bid
                    break
            if start == proven:
                memo[key] = i if chosen is not None else hi
        if chosen is None:
            unit["status"] = "credited"
        else:
            unit["status"] = "placed"
            unit["break_id"] = chosen
            unit["broadcast_date"] = ctx.break_info[chosen]["broadcast_date"]
            before = spare[chosen]
            spare[chosen] = before - need
            if before == max_spare[daypart]:
                max_spare[daypart] = max(
                    spare[e[2]] for e in groups[daypart][1])
    units.sort(key=lambda u: (u["order_line"], u["from_date"], u["unit"]))
    return units, spare, occupied


def _billing(ctx, deliveries, units):
    credited = {}
    billable = {}
    lines = set()
    for row in deliveries:
        lines.add(row["order_line"])
        billable[row["order_line"]] = (billable.get(row["order_line"], 0)
                                       + row["billable"])
    for unit in units:
        if unit["status"] == "credited":
            credited[unit["order_line"]] = (credited.get(unit["order_line"], 0)
                                            + 1)
    rows = []
    for order_line in sorted(lines):
        order = ctx.orders[order_line]
        rate = int(order["unit_rate_cents"])
        gross = billable[order_line] * rate
        bps = int(ctx.advertisers[order["advertiser"]]["commission_bps"])
        commission = (2 * gross * bps + 10000) // 20000
        credit = credited.get(order_line, 0) * rate
        rows.append({
            "order_line": order_line, "advertiser": order["advertiser"],
            "gross_cents": gross, "commission_cents": commission,
            "credit_cents": credit, "net_cents": gross - commission - credit,
        })
    return rows


# ------------------------------------------------------------------ output

def _reject_rows(ctx):
    rows = [{"chain": chain, "seq": seq, "reason": reason}
            for chain, seq, reason in ctx.rejects]

    def sort_key(row):
        seq = row["seq"]
        if seq.isdigit():
            return (row["chain"], 0, int(seq), "")
        return (row["chain"], 1, 0, seq)
    rows.sort(key=sort_key)
    return rows


def _scenario(ctx, spots, deliveries, units, billing):
    counts = dict((code, 0) for code in DISPOSITIONS)
    spot_rows = []
    for item in spots:
        counts[item["disposition"]] += 1
        spot_rows.append({
            "spot_id": item["spot_id"], "order_line": item["order_line"],
            "broadcast_date": item["broadcast_date"], "chain": item["chain"],
            "disposition": item["disposition"],
        })
    spot_rows.sort(key=lambda r: r["spot_id"])
    makegood_rows = [{
        "order_line": u["order_line"], "from_date": u["from_date"],
        "unit": u["unit"], "status": u["status"], "break_id": u["break_id"],
        "broadcast_date": u["broadcast_date"],
    } for u in units]
    totals = {
        "scheduled_spots": len(spots),
        "aired": counts["AIRED"],
        "committed": sum(r["committed"] for r in deliveries),
        "held": sum(r["held"] for r in deliveries),
        "delivered": sum(r["delivered"] for r in deliveries),
        "billable": sum(r["billable"] for r in deliveries),
        "shortfall": sum(r["shortfall"] for r in deliveries),
        "bonus": sum(r["bonus"] for r in deliveries),
        "placed_units": sum(1 for u in units if u["status"] == "placed"),
        "credited_units": sum(1 for u in units if u["status"] == "credited"),
        "gross_cents": sum(r["gross_cents"] for r in billing),
        "commission_cents": sum(r["commission_cents"] for r in billing),
        "credit_cents": sum(r["credit_cents"] for r in billing),
        "net_cents": sum(r["net_cents"] for r in billing),
    }
    return {
        "workload": ctx.workload,
        "channel": ctx.channel_code,
        "spots": spot_rows,
        "deliveries": deliveries,
        "makegoods": makegood_rows,
        "billing": billing,
        "rejects": _reject_rows(ctx),
        "totals": totals,
    }


def _extras(ctx, spots, units, spare, occupied):
    counts = dict((code, 0) for code in DISPOSITIONS)
    for item in spots:
        counts[item["disposition"]] += 1
    reasons = dict((code, 0) for code in REASON_CODES)
    for _chain, _seq, reason in ctx.rejects:
        reasons[reason] += 1
    scheduled = {}
    for row in ctx.schedule:
        scheduled[row["spot_id"]] = row["order_line"]
    reattributed = sum(1 for item in spots
                       if item["order_line"] != scheduled[item["spot_id"]])
    return {
        "asrun_lines": dict(ctx.asrun_lines),
        "duplicate_lines": ctx.duplicate_lines,
        "rejects": reasons,
        "reairs": ctx.reairs,
        "retracted_lines": ctx.retracted_lines,
        "corrections": {
            "admitted": ctx.corrections_admitted,
            "late": ctx.corrections_late,
            "reattributed_spots": reattributed,
        },
        "amendments": {"admitted": ctx.amendments_admitted,
                       "late": ctx.amendments_late},
        "alias_spots": ctx.alias_spots,
        "relock_probes": ctx.relock_probes,
        "stale_probes": ctx.stale_probes,
        "dispositions": counts,
        "partition_residual": len(ctx.schedule) - sum(counts.values()),
        "spare": spare,
        "occupied": occupied,
        "units": units,
    }


def reconcile_full(data_dir, workload, variant=None):
    ctx = _load_context(data_dir, workload, variant)
    _parse_asrun(ctx)
    spots = _spots(ctx)
    deliveries = _deliveries(ctx, spots)
    units, spare, occupied = _makegoods(ctx, deliveries, spots)
    billing = _billing(ctx, deliveries, units)
    scenario = _scenario(ctx, spots, deliveries, units, billing)
    extras = _extras(ctx, spots, units, spare, occupied)
    return scenario, extras, ctx


def reconcile(data_dir, workload):
    return reconcile_full(data_dir, workload)[0]


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: optimize.py DATA_DIR WORKLOAD\n")
        return 2
    try:
        scenario = reconcile(argv[1], argv[2])
    except Exception as exc:                      # noqa: BLE001
        sys.stderr.write("error: %s\n" % (exc,))
        return 1
    sys.stdout.write(json.dumps(scenario, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
