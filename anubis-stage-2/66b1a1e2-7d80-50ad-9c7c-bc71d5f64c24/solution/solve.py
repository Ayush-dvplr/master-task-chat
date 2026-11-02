#!/usr/bin/env python3
'''Reference schedule repair program for the EXEC-OPS calendar store.

Usage: python3 schedule_repair.py DATA_DIR OUT_DIR

Finds the store index inside DATA_DIR by its format tag, resolves every role
file from that index, replays the outbox, merges the two replicas of every
collection, expands the series against the shipped VTIMEZONE rules, settles
conflicts and writes the twenty-five reports, manifest last, into OUT_DIR.
Standard library only.
'''

import bisect
import csv
import hashlib
import io
import json
import os
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

EPOCH = datetime(1970, 1, 1)
WEEKDAY_CODES = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
DEFAULT_WORKING_DAYS = ("MO", "TU", "WE", "TH", "FR")
def sha256_hex(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- ICS parsing


def unfold_lines(blob):
    """Unfold on raw octets, then decode each logical line.

    A fold may split a multi octet UTF-8 character, so decoding before
    unfolding would fail or corrupt the text.
    """
    out = []
    for physical in blob.split(b"\n"):
        if physical[:1] in (b" ", b"\t") and out:
            out[-1] = out[-1] + physical[1:]
        else:
            out.append(physical)
    return [ln.decode("utf-8") for ln in out if ln.strip()]


def parse_content_line(line):
    quoted = False
    idx = len(line)
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif ch == ":" and not quoted:
            idx = i
            break
    head = line[:idx]
    value = line[idx + 1:] if idx < len(line) else ""
    parts = []
    cur = ""
    quoted = False
    for ch in head:
        if ch == '"':
            quoted = not quoted
            cur += ch
        elif ch == ";" and not quoted:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    name = parts[0].strip().upper()
    params = {}
    for piece in parts[1:]:
        if "=" in piece:
            key, val = piece.split("=", 1)
        else:
            key, val = piece, ""
        key = key.strip().upper()
        vals = []
        cur = ""
        quoted = False
        for ch in val:
            if ch == '"':
                quoted = not quoted
            elif ch == "," and not quoted:
                vals.append(cur)
                cur = ""
            else:
                cur += ch
        vals.append(cur)
        params.setdefault(key, []).extend(v.strip() for v in vals)
    return name, params, value


def unescape_text(value):
    out = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt in ("n", "N"):
                out.append("\n")
            elif nxt == "\\":
                out.append("\\")
            elif nxt in (",", ";"):
                out.append(nxt)
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_ics(blob):
    root = {"name": "ROOT", "props": [], "children": []}
    stack = [root]
    for line in unfold_lines(blob):
        name, _params, value = parse_content_line(line)
        if name == "BEGIN":
            comp = {"name": value.strip().upper(), "props": [], "children": []}
            stack[-1]["children"].append(comp)
            stack.append(comp)
        elif name == "END":
            if len(stack) > 1:
                stack.pop()
        else:
            stack[-1]["props"].append((name, _params, value))
    return root


def walk(comp):
    yield comp
    for child in comp["children"]:
        for item in walk(child):
            yield item


def prop_entries(comp, name):
    return [(p, v) for (n, p, v) in comp["props"] if n == name]


def prop_value(comp, name, default=""):
    for (n, _p, v) in comp["props"]:
        if n == name:
            return v
    return default


def prop_params(comp, name):
    for (n, p, _v) in comp["props"]:
        if n == name:
            return p
    return {}


# ------------------------------------------------------------ time primitives


def parse_dt_value(value):
    value = value.strip()
    if value.endswith("Z"):
        return "utc", datetime.strptime(value[:-1], "%Y%m%dT%H%M%S")
    if len(value) == 8:
        return "date", datetime.strptime(value, "%Y%m%d")
    return "local", datetime.strptime(value, "%Y%m%dT%H%M%S")


def fmt_utc(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


def fmt_local(dt):
    return dt.strftime("%Y%m%dT%H%M%S")


def epoch_minutes(dt):
    return int((dt - EPOCH).total_seconds() // 60)


def parse_offset(text):
    text = text.strip()
    sign = -1 if text.startswith("-") else 1
    body = text[1:] if text[:1] in ("+", "-") else text
    hours = int(body[0:2])
    minutes = int(body[2:4])
    seconds = int(body[4:6]) if len(body) >= 6 else 0
    return sign * (hours * 60 + minutes + seconds // 60)


def nth_weekday(year, month, ordinal, weekday):
    if ordinal > 0:
        first = date(year, month, 1)
        delta = (weekday - first.weekday()) % 7
        result = first + timedelta(days=delta + 7 * (ordinal - 1))
    else:
        if month == 12:
            nxt = date(year + 1, 1, 1)
        else:
            nxt = date(year, month + 1, 1)
        last = nxt - timedelta(days=1)
        delta = (last.weekday() - weekday) % 7
        result = last - timedelta(days=delta + 7 * (-ordinal - 1))
    if result.month != month or result.year != year:
        return None
    return result


def parse_rrule(value):
    rule = {}
    for chunk in value.split(";"):
        if not chunk.strip():
            continue
        if "=" not in chunk:
            continue
        key, val = chunk.split("=", 1)
        rule[key.strip().upper()] = val.strip()
    return rule


# ------------------------------------------------------------------- timezone


class Zone(object):
    __slots__ = ("tzid", "transitions", "onsets", "offsets", "observance_count")

    def __init__(self, tzid, transitions, observance_count):
        self.tzid = tzid
        self.transitions = transitions
        self.onsets = [t[0] for t in transitions]
        offs = set()
        for _o, frm, to in transitions:
            offs.add(frm)
            offs.add(to)
        self.offsets = sorted(offs)
        self.observance_count = observance_count


def _tz_yearly_onsets(rule, dtstart_local, from_offset, last_year):
    freq = rule.get("FREQ", "YEARLY").upper()
    if freq != "YEARLY":
        return []
    interval = int(rule.get("INTERVAL", "1") or 1)
    wkst = WEEKDAY_CODES.get(rule.get("WKST", "MO").upper(), 0)
    parts = _rule_parts(rule)
    until_raw = rule.get("UNTIL", "")
    until = parse_dt_value(until_raw)[1] if until_raw else None
    count = int(rule["COUNT"]) if "COUNT" in rule else None
    out = []
    produced = 0
    year = dtstart_local.year
    while year <= last_year:
        days = _set_positions(_year_days(year, parts, dtstart_local.date(), wkst), parts["bysetpos"])
        for day in days:
            onset = datetime(
                day.year, day.month, day.day,
                dtstart_local.hour, dtstart_local.minute, dtstart_local.second,
            )
            if onset < dtstart_local:
                continue
            if until is not None and (onset - timedelta(minutes=from_offset)) > until:
                return out
            if count is not None and produced >= count:
                return out
            out.append(onset)
            produced += 1
        year += interval
    return out


def build_zones(blob, last_year=2040):
    root = parse_ics(blob)
    zones = {}
    for comp in walk(root):
        if comp["name"] != "VTIMEZONE":
            continue
        tzid = prop_value(comp, "TZID").strip()
        transitions = []
        observances = 0
        for sub in comp["children"]:
            if sub["name"] not in ("STANDARD", "DAYLIGHT"):
                continue
            observances += 1
            frm = parse_offset(prop_value(sub, "TZOFFSETFROM"))
            to = parse_offset(prop_value(sub, "TZOFFSETTO"))
            _kind, dtstart = parse_dt_value(prop_value(sub, "DTSTART"))
            onsets = [dtstart]
            rrule_raw = prop_value(sub, "RRULE")
            if rrule_raw:
                onsets.extend(_tz_yearly_onsets(parse_rrule(rrule_raw), dtstart, frm, last_year))
            for _params, value in prop_entries(sub, "RDATE"):
                for piece in value.split(","):
                    if piece.strip():
                        onsets.append(parse_dt_value(piece)[1])
            for onset in onsets:
                transitions.append((onset - timedelta(minutes=frm), frm, to))
        transitions = sorted(set(transitions), key=lambda item: (item[0], item[1], item[2]))
        zones[tzid] = Zone(tzid, transitions, observances)
    return zones


def offset_at(zone, instant_utc):
    if not zone.transitions:
        return 0
    if instant_utc < zone.transitions[0][0]:
        return zone.transitions[0][1]
    idx = bisect.bisect_right(zone.onsets, instant_utc) - 1
    return zone.transitions[idx][2]


def resolve_local(zone, local_dt):
    candidates = []
    for off in zone.offsets:
        cand = local_dt - timedelta(minutes=off)
        if offset_at(zone, cand) == off:
            candidates.append((cand, off))
    seen = []
    for item in candidates:
        if item not in seen:
            seen.append(item)
    seen.sort()
    if len(seen) == 1:
        return seen[0][0], "unique", 0, seen[0][1]
    if len(seen) > 1:
        return seen[0][0], "ambiguous", 0, seen[0][1]
    for onset, frm, to in zone.transitions:
        gap = to - frm
        if gap <= 0:
            continue
        low = onset + timedelta(minutes=frm)
        high = onset + timedelta(minutes=to)
        if low <= local_dt < high:
            shifted = local_dt + timedelta(minutes=gap)
            return shifted - timedelta(minutes=to), "nonexistent", gap, to
    off = offset_at(zone, local_dt)
    return local_dt - timedelta(minutes=off), "unique", 0, off


def to_local(zone, instant_utc):
    return instant_utc + timedelta(minutes=offset_at(zone, instant_utc))


# ---------------------------------------------------------------- rrule engine


def _byday_tokens(raw):
    out = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        ordinal = 0
        code = token
        if len(token) > 2:
            ordinal = int(token[:-2])
            code = token[-2:]
        out.append((ordinal, WEEKDAY_CODES[code.upper()]))
    return out


def _week_start(day, wkst):
    return day - timedelta(days=(day.weekday() - wkst) % 7)


def _add_months(anchor, months):
    total = (anchor.year * 12 + (anchor.month - 1)) + months
    return total // 12, (total % 12) + 1


def _int_list(raw):
    return [int(x) for x in raw.split(",") if x.strip()]


def _rule_parts(rule):
    return {
        "bymonth": _int_list(rule.get("BYMONTH", "")),
        "byweekno": _int_list(rule.get("BYWEEKNO", "")),
        "byyearday": _int_list(rule.get("BYYEARDAY", "")),
        "bymonthday": _int_list(rule.get("BYMONTHDAY", "")),
        "byday": _byday_tokens(rule.get("BYDAY", "")),
        "byhour": _int_list(rule.get("BYHOUR", "")),
        "byminute": _int_list(rule.get("BYMINUTE", "")),
        "bysetpos": _int_list(rule.get("BYSETPOS", "")),
    }


def _set_positions(items, bysetpos):
    if not bysetpos:
        return items
    picked = []
    for pos in bysetpos:
        if 0 < pos <= len(items):
            picked.append(items[pos - 1])
        elif pos < 0 and -pos <= len(items):
            picked.append(items[len(items) + pos])
    return sorted(set(picked))


def _month_length(year, month):
    year2, month2 = _add_months(date(year, month, 1), 1)
    return (date(year2, month2, 1) - date(year, month, 1)).days


def _monthday_listed(day, bymonthday):
    length = _month_length(day.year, day.month)
    return any(day.day == (n if n > 0 else length + 1 + n) for n in bymonthday)


def _year_weeks(year, wkst):
    """Start dates of the numbered weeks of a year: week 1 is the first WKST
    week with at least four days inside the year."""
    jan1 = date(year, 1, 1)
    start = _week_start(jan1, wkst)
    if 7 - (jan1 - start).days < 4:
        start += timedelta(days=7)
    weeks = []
    while sum(1 for k in range(7) if (start + timedelta(days=k)).year == year) >= 4:
        weeks.append(start)
        start += timedelta(days=7)
    return weeks


def _year_days(year, parts, start_date, wkst):
    if not parts["byyearday"] and not parts["byweekno"]:
        days = []
        for month in sorted(set(parts["bymonth"] or [start_date.month])):
            days.extend(_month_days(year, month, parts["bymonthday"], parts["byday"], start_date))
        return sorted(set(days))
    jan1 = date(year, 1, 1)
    length = (date(year + 1, 1, 1) - jan1).days
    selected = set(jan1 + timedelta(days=k) for k in range(length))
    if parts["byyearday"]:
        selected &= set(
            jan1 + timedelta(days=n - 1 if n > 0 else length + n)
            for n in parts["byyearday"]
            if 0 < n <= length or (n < 0 and -n <= length))
    if parts["byweekno"]:
        weeks = _year_weeks(year, wkst)
        selected &= set(
            weeks[n - 1 if n > 0 else len(weeks) + n] + timedelta(days=k)
            for n in parts["byweekno"]
            if 0 < n <= len(weeks) or (n < 0 and -n <= len(weeks))
            for k in range(7))
    days = sorted(selected)
    if parts["bymonth"]:
        days = [d for d in days if d.month in parts["bymonth"]]
    if parts["bymonthday"]:
        days = [d for d in days if _monthday_listed(d, parts["bymonthday"])]
    if parts["byday"]:
        wanted = set(wd for (_o, wd) in parts["byday"])
        days = [d for d in days if d.weekday() in wanted]
    elif parts["byweekno"]:
        days = [d for d in days if d.weekday() == start_date.weekday()]
    return days


def expand_rrule(rule, dtstart_local, horizon_end, max_instances=20000):
    freq = rule.get("FREQ", "DAILY").upper()
    interval = int(rule.get("INTERVAL", "1") or 1)
    wkst = WEEKDAY_CODES.get(rule.get("WKST", "MO").upper(), 0)
    parts = _rule_parts(rule)
    count = int(rule["COUNT"]) if "COUNT" in rule else None
    start_date = dtstart_local.date()
    times = sorted(set(
        (hour, minute)
        for hour in (parts["byhour"] or [dtstart_local.hour])
        for minute in (parts["byminute"] or [dtstart_local.minute])
    ))
    results = []
    period = 0
    while period < 100000:
        days = []
        if freq == "DAILY":
            day = start_date + timedelta(days=period * interval)
            if day > horizon_end:
                break
            days = [day]
        elif freq == "WEEKLY":
            week = _week_start(start_date, wkst) + timedelta(days=7 * period * interval)
            if week > horizon_end:
                break
            targets = [wd for (_o, wd) in parts["byday"]] if parts["byday"] else [start_date.weekday()]
            days = [week + timedelta(days=(wd - wkst) % 7) for wd in sorted(set(targets))]
        elif freq == "MONTHLY":
            year, month = _add_months(start_date, period * interval)
            if date(year, month, 1) > horizon_end:
                break
            if not parts["bymonth"] or month in parts["bymonth"]:
                days = _month_days(year, month, parts["bymonthday"], parts["byday"], start_date)
        elif freq == "YEARLY":
            year = start_date.year + period * interval
            if date(year, 1, 1) > horizon_end:
                break
            days = _year_days(year, parts, start_date, wkst)
        else:
            break
        period += 1
        if freq in ("DAILY", "WEEKLY"):
            if parts["bymonth"]:
                days = [d for d in days if d.month in parts["bymonth"]]
            if parts["bymonthday"]:
                days = [d for d in days if _monthday_listed(d, parts["bymonthday"])]
            if parts["byday"] and freq == "DAILY":
                wanted = set(wd for (_o, wd) in parts["byday"])
                days = [d for d in days if d.weekday() in wanted]
        candidates = sorted(set(
            datetime(day.year, day.month, day.day, hour, minute, dtstart_local.second)
            for day in days for (hour, minute) in times
        ))
        for cand in _set_positions(candidates, parts["bysetpos"]):
            if cand < dtstart_local or cand.date() > horizon_end:
                continue
            results.append(cand)
            if count is not None and len(results) >= count:
                return results
            if len(results) >= max_instances:
                return results
    return results


def _month_days(year, month, bymonthday, byday, start_date):
    days = []
    if bymonthday:
        for mday in bymonthday:
            try:
                if mday > 0:
                    days.append(date(year, month, mday))
                else:
                    if month == 12:
                        nxt = date(year + 1, 1, 1)
                    else:
                        nxt = date(year, month + 1, 1)
                    last = nxt - timedelta(days=1)
                    days.append(date(year, month, last.day + 1 + mday))
            except ValueError:
                continue
    if byday:
        byday_days = []
        for ordinal, wd in byday:
            if ordinal == 0:
                if month == 12:
                    nxt = date(year + 1, 1, 1)
                else:
                    nxt = date(year, month + 1, 1)
                cur = date(year, month, 1)
                while cur < nxt:
                    if cur.weekday() == wd:
                        byday_days.append(cur)
                    cur += timedelta(days=1)
            else:
                got = nth_weekday(year, month, ordinal, wd)
                if got is not None:
                    byday_days.append(got)
        if bymonthday:
            allowed = set(days)
            days = [d for d in byday_days if d in allowed]
        else:
            days = byday_days
    if not bymonthday and not byday:
        try:
            days = [date(year, month, start_date.day)]
        except ValueError:
            days = []
    return sorted(set(days))


# ------------------------------------------------------------- store loading


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def read_json(path):
    return json.loads(read_text(path))


def parse_duration(text):
    text = text.strip()
    sign = 1
    if text.startswith("-"):
        sign = -1
        text = text[1:]
    elif text.startswith("+"):
        text = text[1:]
    if not text.startswith("P"):
        return 0, 0, 0
    body = text[1:]
    date_part = body
    time_part = ""
    if "T" in body:
        date_part, time_part = body.split("T", 1)
    weeks = 0
    days = 0
    num = ""
    for ch in date_part:
        if ch.isdigit():
            num += ch
        elif ch == "W":
            weeks = int(num or 0)
            num = ""
        elif ch == "D":
            days = int(num or 0)
            num = ""
        else:
            num = ""
    hms = 0
    num = ""
    for ch in time_part:
        if ch.isdigit():
            num += ch
        elif ch == "H":
            hms += int(num or 0) * 3600
            num = ""
        elif ch == "M":
            hms += int(num or 0) * 60
            num = ""
        elif ch == "S":
            hms += int(num or 0)
            num = ""
        else:
            num = ""
    return sign * (weeks * 7 + days), sign * hms, sign


def solar_offset_minutes(longitude_text):
    value = Decimal(longitude_text) * Decimal(4)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ------------------------------------------------------------ event encodings

XCAL_NS = "{urn:ietf:params:xml:ns:icalendar-2.0}"


def iso_to_basic(text):
    text = text.strip()
    return text.replace("-", "").replace(":", "")


def _recur_text(pairs):
    parts = []
    for key, value in pairs:
        values = value if isinstance(value, list) else [value]
        rendered = [iso_to_basic(str(v)) if key.upper() == "UNTIL" else str(v) for v in values]
        parts.append("%s=%s" % (key.upper(), ",".join(rendered)))
    return ";".join(parts)


def _typed_text(vtype, values):
    if vtype in ("date-time", "date"):
        return ",".join(iso_to_basic(v) for v in values)
    if vtype == "period":
        out = []
        for start, second in values:
            second = second if second.startswith(("P", "+P", "-P")) else iso_to_basic(second)
            out.append(iso_to_basic(start) + "/" + second)
        return ",".join(out)
    return ",".join(str(v) for v in values)


def ics_components(blob):
    root = parse_ics(blob)
    out = []
    for comp in walk(root):
        if comp["name"] == "VEVENT":
            out.append([(n, p, v, True) for (n, p, v) in comp["props"]])
    return out


def xcal_components(blob):
    tree = ET.fromstring(blob)
    out = []
    for vevent in tree.iter(XCAL_NS + "vevent"):
        props = []
        holder = vevent.find(XCAL_NS + "properties")
        for prop in (holder if holder is not None else []):
            name = prop.tag[len(XCAL_NS):].upper()
            params = {}
            values = []
            vtype = "text"
            for child in prop:
                tag = child.tag[len(XCAL_NS):]
                if tag == "parameters":
                    for param in child:
                        params.setdefault(param.tag[len(XCAL_NS):].upper(), []).extend(
                            (t.text or "") for t in param)
                    continue
                vtype = tag
                if tag == "recur":
                    pairs = []
                    for part in child:
                        key = part.tag[len(XCAL_NS):]
                        if pairs and pairs[-1][0] == key:
                            pairs[-1] = (key, (pairs[-1][1] if isinstance(pairs[-1][1], list) else [pairs[-1][1]]) + [part.text or ""])
                        else:
                            pairs.append((key, part.text or ""))
                    values.append(_recur_text(pairs))
                elif tag == "period":
                    start = child.find(XCAL_NS + "start").text or ""
                    second = child.find(XCAL_NS + "end")
                    if second is None:
                        second = child.find(XCAL_NS + "duration")
                    values.append((start, second.text or ""))
                else:
                    values.append(child.text or "")
            if vtype == "recur":
                text = values[0] if values else ""
            else:
                text = _typed_text(vtype, values)
            props.append((name, params, text, False))
        out.append(props)
    return out


def jcal_components(blob):
    doc = json.loads(blob.decode("utf-8"))
    out = []
    stack = [doc]
    while stack:
        node = stack.pop(0)
        if not isinstance(node, list) or len(node) < 3:
            continue
        if node[0] == "vevent":
            props = []
            for entry in node[1]:
                name = entry[0].upper()
                params = {}
                for key, value in entry[1].items():
                    params[key.upper()] = value if isinstance(value, list) else [value]
                vtype = entry[2]
                values = entry[3:]
                if vtype == "recur":
                    text = _recur_text(list(values[0].items()))
                else:
                    text = _typed_text(vtype, values)
                props.append((name, params, text, False))
            out.append(props)
        stack.extend(node[2])
    return out


def decode_events(blob):
    head = blob.lstrip()[:1]
    if head == b"<":
        return xcal_components(blob)
    if head == b"[":
        return jcal_components(blob)
    return ics_components(blob)


def _first(props, name):
    for n, p, v, esc in props:
        if n == name:
            return p, v, esc
    return {}, "", False


def _entries(props, name):
    return [(p, v) for (n, p, v, _esc) in props if n == name]


def component_record(props, collection_id, replica, canon):
    def tzid_of(params):
        return canon(params.get("TZID", [""])[0])

    uid = _first(props, "UID")[1].strip()
    rid_params, rid_raw, _e = _first(props, "RECURRENCE-ID")
    dt_params, dtstart_raw, _e = _first(props, "DTSTART")
    dtstart_raw = dtstart_raw.strip()
    dt_kind, dtstart = parse_dt_value(dtstart_raw)
    dtend_params, dtend_raw, _e = _first(props, "DTEND")
    exdates = []
    for params, value in _entries(props, "EXDATE"):
        for piece in value.split(","):
            if piece.strip():
                exdates.append((tzid_of(params), parse_dt_value(piece.strip())))
    rdates = []
    for params, value in _entries(props, "RDATE"):
        for piece in value.split(","):
            piece = piece.strip()
            if not piece:
                continue
            end = None
            period_duration = ""
            if "/" in piece:
                piece, right = piece.split("/", 1)
                if right.startswith(("P", "+P", "-P")):
                    period_duration = right
                else:
                    end = parse_dt_value(right)
            rdates.append({"tzid": tzid_of(params), "start": parse_dt_value(piece), "end": end,
                           "duration": period_duration, "period": end is not None or bool(period_duration)})
    refs = []
    for params, _value in _entries(props, "ATTENDEE"):
        role = params.get("ROLE", ["REQ-PARTICIPANT"])[0].upper()
        ref = params.get("X-ATT-ID", [""])[0]
        if ref and role == "REQ-PARTICIPANT":
            refs.append(ref)
    _p, summary, escaped = _first(props, "SUMMARY")
    last_mod_raw = _first(props, "LAST-MODIFIED")[1].strip()
    dtstamp_raw = _first(props, "DTSTAMP")[1].strip()
    sequence_raw = _first(props, "SEQUENCE")[1].strip()
    return {
        "collection": collection_id,
        "replica": replica,
        "uid": uid,
        "recurrence_id": rid_raw.strip(),
        "recurrence_tzid": tzid_of(rid_params),
        "recurrence_range": rid_params.get("RANGE", [""])[0].upper(),
        "dtstart_raw": dtstart_raw,
        "dtstart": dtstart,
        "dtstart_kind": dt_kind,
        "dtstart_tzid": tzid_of(dt_params),
        "dtend_raw": dtend_raw.strip(),
        "dtend_tzid": tzid_of(dtend_params),
        "duration": _first(props, "DURATION")[1].strip(),
        "rrule": _first(props, "RRULE")[1].strip(),
        "exdates": exdates,
        "rdates": rdates,
        "sequence": int(sequence_raw or 0),
        "last_modified": parse_dt_value(last_mod_raw)[1] if last_mod_raw else None,
        "dtstamp": parse_dt_value(dtstamp_raw)[1] if dtstamp_raw else None,
        "pinned": _first(props, "X-PINNED")[1].strip() == "TRUE",
        "summary": unescape_text(summary) if escaped else summary,
        "office": _first(props, "X-OFFICE")[1].strip(),
        "series_class": _first(props, "X-SERIES-CLASS")[1].strip(),
        "attendees": sorted(set(refs)),
        "status": _first(props, "STATUS")[1].strip(),
    }


# -------------------------------------------------------------- the PDF schedule


def _pdf_objects(blob):
    objects = {}
    pos = 0
    while True:
        start = blob.find(b" 0 obj", pos)
        if start < 0:
            break
        num_start = start
        while num_start > 0 and blob[num_start - 1:num_start].isdigit():
            num_start -= 1
        number = int(blob[num_start:start])
        end = blob.find(b"endobj", start)
        body = blob[start + len(b" 0 obj"):end]
        objects[number] = body
        pos = end + len(b"endobj")
    return objects


def _pdf_stream(body):
    head, _sep, rest = body.partition(b"stream")
    rest = rest[1:] if rest[:1] == b"\n" else rest[2:] if rest[:2] == b"\r\n" else rest
    length = int(head.split(b"/Length", 1)[1].split()[0])
    data = rest[:length]
    if b"/FlateDecode" in head:
        data = zlib.decompress(data)
    return data


def _pdf_ref(body, key):
    after = body.split(key, 1)[1].split()
    return int(after[0])


def _pdf_tokens(data):
    i = 0
    n = len(data)
    while i < n:
        ch = data[i:i + 1]
        if ch in b" \t\r\n":
            i += 1
        elif ch == b"(":
            depth = 1
            out = bytearray()
            i += 1
            while i < n and depth:
                c = data[i:i + 1]
                if c == b"\\":
                    nxt = data[i + 1:i + 2]
                    if nxt in b"01234567":
                        j = i + 1
                        while j < i + 4 and data[j:j + 1] in b"01234567":
                            j += 1
                        out.append(int(data[i + 1:j], 8) & 0xFF)
                        i = j
                        continue
                    out += {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}.get(nxt, nxt)
                    i += 2
                    continue
                if c == b"(":
                    depth += 1
                elif c == b")":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                out += c
                i += 1
            yield ("str", bytes(out).decode("latin-1"))
        elif ch == b"<" and data[i + 1:i + 2] != b"<":
            j = data.index(b">", i)
            hexed = b"".join(data[i + 1:j].split())
            if len(hexed) % 2:
                hexed += b"0"
            yield ("str", bytes.fromhex(hexed.decode("ascii")).decode("latin-1"))
            i = j + 1
        elif ch in b"[]":
            yield (ch.decode(), None)
            i += 1
        else:
            j = i
            while j < n and data[j:j + 1] not in b" \t\r\n()<>[]/" or (j == i and data[j:j + 1] == b"/"):
                j += 1
            word = data[i:j].decode("latin-1")
            i = j
            try:
                yield ("num", float(word))
            except ValueError:
                yield ("op", word)


def pdf_rows(path):
    blob = read_bytes(path)
    objects = _pdf_objects(blob)
    catalog = next(body for body in objects.values() if b"/Type /Catalog" in body)
    pages = objects[_pdf_ref(catalog, b"/Pages")]
    kids = [int(x) for x in pages.split(b"/Kids", 1)[1].split(b"[", 1)[1].split(b"]", 1)[0].split()[0::3]]
    rows = []
    for kid in kids:
        content = _pdf_stream(objects[_pdf_ref(objects[kid], b"/Contents")])
        runs = []
        operands = []
        x = y = 0.0
        array = None
        for kind, value in _pdf_tokens(content):
            if kind == "[":
                array = []
            elif kind == "]":
                operands.append(("arr", "".join(s for s in array if isinstance(s, str))))
                array = None
            elif array is not None:
                if kind == "str":
                    array.append(value)
            elif kind == "op":
                if value == "Tm":
                    x, y = operands[-2][1], operands[-1][1]
                elif value in ("Tj", "TJ"):
                    runs.append((y, x, operands[-1][1]))
                operands = []
            else:
                operands.append((kind, value))
        by_line = {}
        for ry, rx, text in runs:
            by_line.setdefault(ry, []).append((rx, text))
        for ry in sorted(by_line, reverse=True):
            rows.append([text for _x, text in sorted(by_line[ry])])
    return rows


def pdf_tables(path):
    tables = {}
    current = None
    expect_header = False
    for row in pdf_rows(path):
        if len(row) == 1 and row[0].startswith("page ") and " of " in row[0]:
            continue
        if len(row) == 1 and row[0].startswith("Table "):
            caption = row[0]
            if caption.endswith(" (continued)"):
                caption = caption[:-len(" (continued)")]
            current = caption.split(". ", 1)[1]
            tables.setdefault(current, [])
            expect_header = True
            continue
        if current is None:
            continue
        if expect_header:
            expect_header = False
            continue
        tables[current].append(row)
    return tables


# --------------------------------------------------------- the XLSX register

XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
XLSX_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _cell_ref(ref):
    letters = "".join(ch for ch in ref if ch.isalpha())
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - 64)
    return int(ref[len(letters):]), col - 1


def read_xlsx(path):
    with zipfile.ZipFile(path) as zf:
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        props = workbook.find(XLSX_NS + "workbookPr")
        date1904 = props is not None and props.get("date1904") in ("1", "true")
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        target_of = dict((rel.get("Id"), rel.get("Target")) for rel in rels.iter(PKG_REL + "Relationship"))
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).iter(XLSX_NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(XLSX_NS + "t")))
        sheets = []
        for sheet in workbook.iter(XLSX_NS + "sheet"):
            target = target_of[sheet.get(XLSX_REL + "id")]
            part = target.lstrip("/") if target.startswith("/") else "xl/" + target
            grid = {}
            for cell in ET.fromstring(zf.read(part)).iter(XLSX_NS + "c"):
                row, col = _cell_ref(cell.get("r"))
                kind = cell.get("t")
                if kind == "s":
                    value = shared[int(cell.find(XLSX_NS + "v").text)]
                elif kind == "inlineStr":
                    value = "".join(t.text or "" for t in cell.iter(XLSX_NS + "t"))
                else:
                    node = cell.find(XLSX_NS + "v")
                    value = node.text if node is not None else ""
                grid.setdefault(row, {})[col] = value
            sheets.append((sheet.get("name"), grid))
    return date1904, sheets


def serial_date(value, date1904):
    epoch = date(1904, 1, 1) if date1904 else date(1899, 12, 30)
    return epoch + timedelta(days=int(float(value)))


def _sheet_rows(grid):
    header_row = 4
    header = [grid.get(header_row, {}).get(c, "") for c in range(max(grid.get(header_row, {0: ""})) + 1)]
    rows = []
    for r in sorted(k for k in grid if k > header_row):
        rows.append(dict((name, grid[r].get(c, "")) for c, name in enumerate(header)))
    return rows


def in_force_sheet(sheets, kind, edition):
    for _name, grid in sheets:
        first = grid.get(1, {})
        second = grid.get(2, {})
        if first.get(0, "") == kind and first.get(1, "") == edition and second.get(1, "") == "in force":
            return grid
    raise SystemExit("no in force %s sheet for edition %s" % (kind, edition))


def _int_text(value):
    return int(float(value.replace(",", "")))


def load_register(path, edition):
    date1904, sheets = read_xlsx(path)
    offices = {}
    for row in _sheet_rows(in_force_sheet(sheets, "office register", edition)):
        code = row["office"]
        office = offices.setdefault(code, {"code": code, "tzid": row["tzid"], "longitude": row["longitude"],
                                           "rows": dict((wd, []) for wd in range(7))})
        office["rows"][WEEKDAY_CODES[row["weekday"]]].append((
            serial_date(row["effective from"], date1904), row["working"] == "Y",
            _int_text(row["open minute"]), _int_text(row["close minute"]),
            _int_text(row["solar open"]), _int_text(row["solar close"])))
    for office in offices.values():
        office["solar_offset"] = solar_offset_minutes(office["longitude"])
        for wd in office["rows"]:
            office["rows"][wd].sort()
    rates = {}
    for row in _sheet_rows(in_force_sheet(sheets, "attendee rates", edition)):
        rates.setdefault(row["attendee"], []).append(
            (serial_date(row["effective from"], date1904), _int_text(row["cents per hour"])))
    for att in rates:
        rates[att].sort()
    return offices, rates


def office_row(state, code, day):
    rows = state["offices"][code]["rows"][day.weekday()]
    chosen = None
    for row in rows:
        if row[0] <= day:
            chosen = row
    if chosen is None:
        return (None, False, 0, 0, 0, 0)
    return chosen


# ------------------------------------------------------------ governance


def load_governance(path, policy_revision):
    tables = pdf_tables(path)
    status = dict((int(r[0]), r[2]) for r in tables["Revision register"])
    approved = sorted(r for r, s in status.items() if s == "approved")
    effective = min(policy_revision, approved[-1])
    usable = set(r for r in approved if r <= effective)

    def latest(rows):
        best = None
        for revision, value in rows:
            if revision in usable and (best is None or revision > best[0]):
                best = (revision, value)
        return best[1] if best else None

    params = latest((int(r[0]), r) for r in tables["Settling parameters"])
    ranks_by_class = {}
    for cls, revision, rank in tables["Series class ranks"]:
        ranks_by_class.setdefault(cls, []).append((int(revision), int(rank)))
    fx_by_office = {}
    for office, revision, bps in tables["Office conversion"]:
        fx_by_office.setdefault(office, []).append((int(revision), int(bps)))
    ranks = {}
    for cls, rows in ranks_by_class.items():
        value = latest(rows)
        if value is not None:
            ranks[cls] = value
    fx = {}
    for office, rows in fx_by_office.items():
        value = latest(rows)
        if value is not None:
            fx[office] = value
    return {
        "effective_revision": effective,
        "buffer": int(params[1]),
        "quantum": int(params[2]),
        "round_cap": int(params[3]),
        "pin_rank": int(params[4]),
        "default_rank": int(params[5]),
        "ranks": ranks,
        "fx": fx,
        "classes": sorted(ranks_by_class),
        "fx_offices": sorted(fx_by_office),
    }


# ------------------------------------------------------- the YAML status book


def _yaml_scalar(text):
    text = text.strip()
    if text.startswith("'"):
        return text[1:text.rindex("'")].replace("''", "'")
    if text.startswith('"'):
        body = text[1:text.rindex('"')]
        out = []
        i = 0
        while i < len(body):
            if body[i] == "\\" and i + 1 < len(body):
                out.append({"n": "\n", "t": "\t"}.get(body[i + 1], body[i + 1]))
                i += 2
            else:
                out.append(body[i])
                i += 1
        return "".join(out)
    if " #" in text:
        text = text.split(" #", 1)[0].rstrip()
    return text


def _strip_comment(line):
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def parse_yaml(text):
    lines = []
    for raw in text.split("\n"):
        line = _strip_comment(raw)
        if line.strip():
            lines.append((len(line) - len(line.lstrip(" ")), line.strip()))

    def block(i, indent):
        if lines[i][1].startswith("- "):
            out = []
            while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
                inner_indent = indent + 2
                lines[i] = (inner_indent, lines[i][1][2:])
                value, i = block(i, inner_indent)
                out.append(value)
            return out, i
        out = {}
        while i < len(lines) and lines[i][0] == indent and not lines[i][1].startswith("- "):
            key, _sep, rest = lines[i][1].partition(":")
            key = _yaml_scalar(key)
            if rest.strip():
                out[key] = _yaml_scalar(rest)
                i += 1
            else:
                i += 1
                if i < len(lines) and lines[i][0] > indent:
                    out[key], i = block(i, lines[i][0])
                elif i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
                    out[key], i = block(i, indent)
                else:
                    out[key] = None
        return out, i

    value, _i = block(0, lines[0][0])
    return value


# ------------------------------------------------------- journals and outbox


def load_journals(current_path, legacy_path):
    records = {}
    for line in read_text(legacy_path).split("\n"):
        if not line.strip():
            continue
        rec = json.loads(line)
        rid = iso_to_basic(rec["rid"]) if rec.get("rid") else ""
        key = (rec["cal"], {"L": "local", "S": "server"}[rec["side"]], rec["object"], rid, int(rec["rev"]))
        records[key] = rec["action"] == "DEL"
    for line in read_text(current_path).split("\n"):
        if not line.strip():
            continue
        rec = json.loads(line)
        key = (rec["collection"], rec["replica"], rec["uid"], rec.get("recurrence_id") or "", int(rec["revision"]))
        records[key] = rec["op"] == "delete"
    return [{"collection": k[0], "replica": k[1], "uid": k[2], "recurrence_id": k[3], "revision": k[4],
             "op": "delete" if deleted else "update"} for k, deleted in sorted(records.items())]


def _psv_fields(line):
    fields = []
    cur = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            cur.append(line[i + 1])
            i += 2
            continue
        if ch == "|":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    fields.append("".join(cur))
    return fields


def load_outbox(path):
    ops = []
    header = None
    for line in read_text(path).split("\n"):
        if not line.strip() or line.startswith("#"):
            continue
        fields = _psv_fields(line)
        if header is None:
            header = fields
            continue
        ops.append(dict(zip(header, fields)))
    ops.sort(key=lambda op: int(op["op_seq"]))
    return ops


def replay_outbox(state):
    by_key = {}
    for comp in state["components"]:
        if comp["replica"] == "server":
            by_key[(comp["collection"], comp["uid"], comp["recurrence_id"])] = comp
    collections = set(c["id"] for c in state["store"]["collections"])
    outcomes = []
    removed = set()
    for op in state["outbox"]:
        if op["collection"] not in collections:
            continue
        key = (op["collection"], op["uid"], op["recurrence_id"])
        comp = by_key.get(key)
        row = {"op_seq": int(op["op_seq"]), "collection": op["collection"], "uid": op["uid"],
               "recurrence_id": op["recurrence_id"], "op": op["op"], "field": op["field"]}
        if comp is None:
            row.update(outcome="missing", sequence_after=None)
        elif comp["sequence"] != int(op["base_sequence"]):
            row.update(outcome="stale-base", sequence_after=comp["sequence"])
        else:
            stamp = parse_dt_value(op["stamp"])[1]
            if op["op"] == "DELETE":
                del by_key[key]
                removed.add(id(comp))
                row.update(outcome="applied", sequence_after=None)
            else:
                field = op["field"]
                if field == "SUMMARY":
                    comp["summary"] = op["value"]
                elif field == "SEQUENCE":
                    comp["sequence"] = int(op["value"])
                elif field == "STATUS":
                    comp["status"] = op["value"]
                elif field == "X-SERIES-CLASS":
                    comp["series_class"] = op["value"]
                elif field == "DURATION":
                    comp["duration"] = op["value"]
                    comp["dtend_raw"] = ""
                comp["last_modified"] = stamp
                row.update(outcome="applied", sequence_after=comp["sequence"])
        outcomes.append(row)
    state["components"] = [c for c in state["components"] if id(c) not in removed]
    return outcomes


# ------------------------------------------------------------- identities


def load_aliases(path):
    links = {}
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["status"].strip() != "active":
                continue
            links.setdefault(row["handle"].strip(), []).append(
                (date.fromisoformat(row["effective_from"].strip()), row["target"].strip()))
    return links


def resolve_ref(state, ref, day):
    links = state["aliases"]
    visited = [ref]
    current = ref
    hops = 0
    outcome = None
    while True:
        best = None
        for when, target in links.get(current, []):
            if when <= day and (best is None or when > best[0] or (when == best[0] and target < best[1])):
                best = (when, target)
        if best is None:
            break
        hops += 1
        target = best[1]
        if target in visited:
            current = min(visited[visited.index(target):])
            outcome = "cycle"
            break
        visited.append(target)
        current = target
    if outcome is None:
        outcome = "direct" if hops == 0 else "resolved"
    if current not in state["attendees"]:
        return None, hops, "unresolved"
    return current, hops, outcome


def load_people(path):
    people = {}
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            people[row["id"]] = {"id": row["id"], "home_office": row["home_office"]}
    return people


def load_zone_aliases(path):
    doc = read_json(path)
    links = dict((a["alias"], a["target"]) for a in doc["aliases"] if a.get("status") == "active")

    def canon(tzid):
        seen = set()
        while tzid in links and tzid not in seen:
            seen.add(tzid)
            tzid = links[tzid]
        return tzid
    return canon


def load_closures(path):
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    best = {}
    for office, day, name, revision, state in con.execute("SELECT office, day, name, revision, state FROM closures"):
        key = (office, day)
        if key not in best or revision > best[key][0]:
            best[key] = (revision, state, name)
    con.close()
    closures = {}
    for (office, day), (_rev, state, name) in best.items():
        if state != "withdrawn":
            closures.setdefault(office, {})[day] = name
    return closures


def load_busy(path):
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    blocks = []
    for attendee, fbtype, start, finish, withdrawn in con.execute(
            "SELECT attendee, fbtype, start, finish, withdrawn FROM periods"):
        if withdrawn:
            continue
        begin = parse_dt_value(start)[1]
        if finish.startswith("P"):
            days, hms, _sign = parse_duration(finish)
            end = begin + timedelta(days=days, seconds=hms)
        else:
            end = parse_dt_value(finish)[1]
        blocks.append({"attendee": attendee, "fbtype": fbtype or "BUSY", "start": begin, "end": end})
    con.close()
    return blocks


def load_legs_xml(path):
    legs = []
    for leg in ET.parse(path).getroot().iter("leg"):
        if leg.get("status", "confirmed") != "confirmed":
            continue
        dep = leg.find("depart")
        arr = leg.find("arrive")
        legs.append({"leg_id": leg.get("id"), "attendee": leg.get("attendee"),
                     "depart_office": dep.get("office"), "arrive_office": arr.get("office"),
                     "depart_local": dep.get("local"), "arrive_local": arr.get("local")})
    return {"legs": legs}


def find_index(store_dir):
    found = []
    for name in sorted(os.listdir(store_dir)):
        path = os.path.join(store_dir, name)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as fh:
            head = fh.read(64).lstrip()
        if not head.startswith(b"{"):
            continue
        try:
            doc = read_json(path)
        except ValueError:
            continue
        if isinstance(doc, dict) and doc.get("format") == "exec-ops-store/2":
            found.append(doc)
    if len(found) != 1:
        raise SystemExit("expected exactly one store index, found %d" % len(found))
    return found[0]


def load_store(store_dir):
    index = find_index(store_dir)
    files = index["files"]
    store = index["store"]
    path = lambda role: os.path.join(store_dir, files[role])
    canon = load_zone_aliases(path("zone_aliases"))
    zones = build_zones(read_bytes(path("zones")))
    offices, rates = load_register(path("register"), store["register_edition"])
    governance = load_governance(path("governance"), int(store["policy_revision"]))
    status_doc = parse_yaml(read_text(path("status")))
    statuses = {}
    for cid, sides in status_doc["collections"].items():
        for side, body in sides.items():
            statuses[(cid, side)] = {"entries": [
                {"href": e["href"], "etag": e["etag"], "revision": int(e["revision"])} for e in (body.get("entries") or [])]}
    components = []
    for collection in store["collections"]:
        for replica in ("local", "server"):
            for props in decode_events(read_bytes(os.path.join(store_dir, collection["replicas"][replica]))):
                components.append(component_record(props, collection["id"], replica, canon))
    state = {
        "index": index,
        "store": store,
        "zones": zones,
        "offices": offices,
        "rates": rates,
        "governance": governance,
        "attendees": load_people(path("attendees")),
        "aliases": load_aliases(path("aliases")),
        "ranks": governance["ranks"],
        "default_rank": governance["default_rank"],
        "pin_rank": governance["pin_rank"],
        "itineraries": load_legs_xml(path("itineraries")),
        "holidays": load_closures(path("closures")),
        "change_log": load_journals(path("journal"), path("journal_legacy")),
        "outbox": load_outbox(path("outbox")),
        "components": components,
        "statuses": statuses,
        "freebusy": load_busy(path("freebusy")),
        "window_start": datetime.strptime(store["window"]["start"], "%Y-%m-%d"),
        "window_end": datetime.strptime(store["window"]["end"], "%Y-%m-%d"),
        "files": files,
        "store_dir": store_dir,
    }
    return state


# ------------------------------------------------------------------- merging


def revision_for(change_log, collection, replica, uid, recurrence_id, deletes=False):
    """Largest revision of the replica's records for the key; delete records
    are counted only when deletes is true, and only they are counted then."""
    best = -1
    for entry in change_log:
        if ((entry.get("op") == "delete") == deletes
                and entry.get("collection") == collection
                and entry.get("replica") == replica
                and entry.get("uid") == uid
                and (entry.get("recurrence_id") or "") == recurrence_id):
            rev = int(entry.get("revision", -1))
            if rev > best:
                best = rev
    return best


def reconcile(state):
    store = state["store"]
    policy = store["conflict_policy"]
    authority = store["authority_replica"]
    change_log = state["change_log"]
    grouped = {}
    for comp in state["components"]:
        key = (comp["collection"], comp["uid"], comp["recurrence_id"])
        grouped.setdefault(key, {})[comp["replica"]] = comp
    decisions = []
    merged = {}
    contested = 0
    sole = 0
    tombstoned = 0
    for key in sorted(grouped):
        collection, uid, rid = key
        replicas = grouped[key]
        href = href_for(state, collection, uid)
        if len(replicas) == 1:
            replica = list(replicas)[0]
            other = "server" if replica == "local" else "local"
            deleted_at = revision_for(change_log, collection, other, uid, rid, deletes=True)
            if deleted_at > revision_for(change_log, collection, replica, uid, rid):
                # The other replica deleted the object after the holder last wrote it.
                tombstoned += 1
                decisions.append({
                    "collection": collection,
                    "uid": uid,
                    "recurrence_id": rid,
                    "href": href,
                    "winner": other,
                    "loser": replica,
                    "rule": "tombstone",
                    "winning_sequence": -1,
                    "losing_sequence": replicas[replica]["sequence"],
                })
                continue
            merged[key] = replicas[replica]
            sole += 1
            decisions.append({
                "collection": collection,
                "uid": uid,
                "recurrence_id": rid,
                "href": href,
                "winner": replica,
                "loser": "",
                "rule": "sole-replica",
                "winning_sequence": replicas[replica]["sequence"],
                "losing_sequence": -1,
            })
            continue
        contested += 1
        local = replicas["local"]
        server = replicas["server"]
        winner, rule = pick_winner(policy, authority, change_log, collection, uid, rid, local, server)
        loser = "server" if winner == "local" else "local"
        merged[key] = replicas[winner]
        decisions.append({
            "collection": collection,
            "uid": uid,
            "recurrence_id": rid,
            "href": href,
            "winner": winner,
            "loser": loser,
            "rule": rule,
            "winning_sequence": replicas[winner]["sequence"],
            "losing_sequence": replicas[loser]["sequence"],
        })
    uid_map = {}
    for (collection, uid, _rid) in merged:
        uid_map.setdefault(uid, set()).add(collection)
    order = [c["id"] for c in store["collections"]]
    duplicates = []
    shadow = set()
    for uid in sorted(uid_map):
        cols = sorted(uid_map[uid], key=lambda c: order.index(c))
        if len(cols) > 1:
            duplicates.append({
                "uid": uid,
                "collections": cols,
                "primary_collection": cols[0],
            })
            for extra in cols[1:]:
                shadow.add((extra, uid))
    report = {
        "policy": policy,
        "decisions": decisions,
        "duplicate_uids": duplicates,
        "counts": {
            "components": len(merged),
            "contested": contested,
            "sole_replica": sole,
            "tombstoned": tombstoned,
        },
    }
    return report, merged, shadow


def pick_winner(policy, authority, change_log, collection, uid, rid, local, server):
    if policy == "sequence-major":
        if local["sequence"] != server["sequence"]:
            return ("local" if local["sequence"] > server["sequence"] else "server"), "sequence"
    elif policy == "mtime-major":
        # LAST-MODIFIED, else DTSTAMP; a component with neither is older than any with one.
        lm_local = local["last_modified"] or local["dtstamp"]
        lm_server = server["last_modified"] or server["dtstamp"]
        if lm_local is not None or lm_server is not None:
            if lm_server is None or (lm_local is not None and lm_local > lm_server):
                return "local", "last-modified"
            if lm_local is None or lm_server > lm_local:
                return "server", "last-modified"
    else:
        raise SystemExit("unsupported conflict policy: " + str(policy))
    rev_local = revision_for(change_log, collection, "local", uid, rid)
    rev_server = revision_for(change_log, collection, "server", uid, rid)
    if rev_local != rev_server:
        return ("local" if rev_local > rev_server else "server"), "revision"
    return authority, "authority"


def href_for(state, collection_id, uid):
    for collection in state["store"]["collections"]:
        if collection["id"] == collection_id:
            return collection["href"] + uid + ".ics"
    return "/" + collection_id + "/" + uid + ".ics"


# ------------------------------------------------------------------ expansion


def zone_for_office(state, office_code):
    office = state["offices"][office_code]
    return state["zones"][office["tzid"]]


def resolve_property_instant(state, kind, value, tzid):
    if kind == "utc":
        return value, "unique", 0, 0
    zone = state["zones"].get(tzid)
    if zone is None:
        return value, "unique", 0, 0
    return resolve_local(zone, value)


def duration_end(state, text, start_utc, office_code, semantics):
    days, hms, _sign = parse_duration(text)
    # With no week or day part there is nothing to add on the wall clock.
    if semantics == "nominal" and days:
        zone = zone_for_office(state, office_code)
        local_shift = to_local(zone, start_utc) + timedelta(days=days)
        return resolve_local(zone, local_shift)[0] + timedelta(seconds=hms)
    return start_utc + timedelta(days=days, seconds=hms)


def component_duration(state, comp, start_utc, office_code, semantics):
    if comp["dtend_raw"]:
        kind, value = parse_dt_value(comp["dtend_raw"])
        end_utc = resolve_property_instant(state, kind, value, comp["dtend_tzid"])[0]
        base_start = resolve_property_instant(
            state, comp["dtstart_kind"], comp["dtstart"], comp["dtstart_tzid"])[0]
        seconds = int((end_utc - base_start).total_seconds())
        return start_utc + timedelta(seconds=seconds), seconds, "DTEND"
    if comp["duration"]:
        end_utc = duration_end(state, comp["duration"], start_utc, office_code, semantics)
        return end_utc, int((end_utc - start_utc).total_seconds()), "DURATION"
    end_utc = start_utc + timedelta(hours=1)
    return end_utc, 3600, "DEFAULT"


def period_duration(state, period, original, start_utc, office_code, semantics):
    if period["end"] is not None:
        kind, value = period["end"]
        end_instant = resolve_property_instant(state, kind, value, period["tzid"])[0]
        seconds = int((end_instant - original).total_seconds())
        return start_utc + timedelta(seconds=seconds), seconds, "RDATE"
    end_utc = duration_end(state, period["duration"], start_utc, office_code, semantics)
    return end_utc, int((end_utc - start_utc).total_seconds()), "RDATE"


def shown_content(comp, master):
    return {
        "comp": comp,
        "office": comp["office"] or master["office"],
        "summary": comp["summary"] or master["summary"],
        "attendees": comp["attendees"] or master["attendees"],
        "series_class": comp["series_class"] or master["series_class"],
    }


def expand(state, merged, shadow):
    store = state["store"]
    semantics = store["duration_semantics"]
    window_start = state["window_start"]
    window_end = state["window_end"] + timedelta(days=1)
    # The window is bounded in UTC, so a candidate whose local date is the day
    # after the window end can still resolve inside it; generate past that day
    # and let the UTC window test below decide.
    horizon_end = (state["window_end"] + timedelta(days=2)).date()
    series = {}
    for (collection, uid, rid), comp in merged.items():
        if (collection, uid) in shadow:
            continue
        series.setdefault((collection, uid), {"master": None, "overrides": []})
        if rid:
            series[(collection, uid)]["overrides"].append(comp)
        else:
            series[(collection, uid)]["master"] = comp
    occurrences = []
    resolutions = []
    exdates_applied = []
    exdates_unmatched = []
    overrides_applied = []
    overrides_rejected = []
    shift_ledger = []
    for key in sorted(series):
        collection, uid = key
        master = series[key]["master"]
        if master is None:
            for override in series[key]["overrides"]:
                kind, value = parse_dt_value(override["recurrence_id"])
                rid_utc = resolve_property_instant(state, kind, value, override["recurrence_tzid"])[0]
                overrides_rejected.append({
                    "uid": uid,
                    "collection": collection,
                    "recurrence_id_utc": fmt_utc(rid_utc),
                    "reason": "missing-master",
                })
            continue
        office_code = master["office"]
        zone = zone_for_office(state, office_code)
        # Candidates resolve in the zone named by the master DTSTART.
        rule_zone = state["zones"].get(master["dtstart_tzid"], zone)
        if master["rrule"]:
            rule = parse_rrule(master["rrule"])
            candidates = expand_rrule(rule, master["dtstart"], horizon_end)
            until_raw = rule.get("UNTIL", "")
            until = parse_dt_value(until_raw)[1] if until_raw else None
        else:
            candidates = [master["dtstart"]]
            until = None
        originals = []
        for local_dt in candidates:
            if master["dtstart_kind"] == "utc":
                instant, classification, shift = local_dt, "unique", 0
                offset = offset_at(rule_zone, instant)
            else:
                instant, classification, shift, offset = resolve_local(rule_zone, local_dt)
            if until is not None and instant > until:
                continue
            if not (window_start <= instant < window_end):
                continue
            originals.append(instant)
            resolutions.append({
                "occurrence_id": "%s:%s:%s" % (collection, uid, fmt_utc(instant)),
                "tzid": rule_zone.tzid,
                "nominal_local": fmt_local(local_dt),
                "classification": classification,
                "shift_minutes": shift,
                "utc_offset_minutes": offset,
            })
        # RDATE candidates ignore COUNT, UNTIL and DTSTART; only the window drops
        # them, and one that lands on an instant already kept adds nothing.
        periods = {}
        for rdate in master["rdates"]:
            kind, value = rdate["start"]
            if kind == "utc":
                rd_zone = rule_zone
                instant, classification, shift = value, "unique", 0
                nominal = to_local(rd_zone, instant)
                offset = offset_at(rd_zone, instant)
            else:
                rd_zone = state["zones"].get(rdate["tzid"], rule_zone)
                nominal = value
                instant, classification, shift, offset = resolve_local(rd_zone, value)
            if not (window_start <= instant < window_end) or instant in originals:
                continue
            originals.append(instant)
            if rdate["period"]:
                periods[instant] = rdate
            resolutions.append({
                "occurrence_id": "%s:%s:%s" % (collection, uid, fmt_utc(instant)),
                "tzid": rd_zone.tzid,
                "nominal_local": fmt_local(nominal),
                "classification": classification,
                "shift_minutes": shift,
                "utc_offset_minutes": offset,
            })
        original_set = set(originals)
        exdate_instants = set()
        for tzid, (kind, value) in master["exdates"]:
            instant = resolve_property_instant(state, kind, value, tzid)[0]
            record = {"collection": collection, "uid": uid, "exdate_utc": fmt_utc(instant)}
            if instant in original_set:
                exdates_applied.append(record)
                exdate_instants.add(instant)
            else:
                exdates_unmatched.append(record)
        # Exclusions come first: an override can only match an instant that
        # survived them.
        remaining = original_set - exdate_instants
        by_instant = {}
        for override in series[key]["overrides"]:
            kind, value = parse_dt_value(override["recurrence_id"])
            rid_utc = resolve_property_instant(state, kind, value, override["recurrence_tzid"])[0]
            if rid_utc not in remaining:
                overrides_rejected.append({
                    "uid": uid,
                    "collection": collection,
                    "recurrence_id_utc": fmt_utc(rid_utc),
                    "reason": "orphan-recurrence-id",
                })
                continue
            by_instant.setdefault(rid_utc, []).append(override)
        overridden = {}
        cancelled = set()
        thisandfuture = []
        for rid_utc in sorted(by_instant):
            contenders = sorted(by_instant[rid_utc], key=lambda c: (c["sequence"], c["recurrence_id"]))
            winner = contenders[-1]
            for loser in contenders[:-1]:
                overrides_rejected.append({
                    "uid": uid,
                    "collection": collection,
                    "recurrence_id_utc": fmt_utc(rid_utc),
                    "reason": "superseded-recurrence-id",
                })
            new_start = resolve_property_instant(
                state, winner["dtstart_kind"], winner["dtstart"],
                winner["dtstart_tzid"])[0]
            delta_seconds = int((new_start - rid_utc).total_seconds())
            overrides_applied.append({
                "uid": uid,
                "collection": collection,
                "recurrence_id_utc": fmt_utc(rid_utc),
                "range": winner["recurrence_range"],
                "delta_minutes": delta_seconds // 60,
            })
            if winner["status"] == "CANCELLED":
                # A cancelling override removes its instance and moves nothing.
                cancelled.add(rid_utc)
                continue
            overridden[rid_utc] = (winner, new_start)
            if winner["recurrence_range"] == "THISANDFUTURE":
                thisandfuture.append((rid_utc, delta_seconds, shown_content(winner, master)))
        for original in sorted(remaining - cancelled):
            earlier_ranged = [item for item in thisandfuture if item[0] < original]
            if original in overridden:
                override, start_utc = overridden[original]
                shown = shown_content(override, master)
                shift_seconds = 0
                is_override = True
            else:
                shift_seconds = sum(delta for _rid, delta, _shown in earlier_ranged)
                start_utc = original + timedelta(seconds=shift_seconds)
                is_override = False
                # Amendment A3: the latest earlier ranged override hands its content forward.
                shown = earlier_ranged[-1][2] if earlier_ranged else shown_content(master, master)
            applied_shift = shift_seconds // 60
            occ_office = shown["office"]
            occ_zone = zone_for_office(state, occ_office)
            if shown["comp"] is master and original in periods:
                end_utc, duration_seconds, duration_source = period_duration(
                    state, periods[original], original, start_utc, occ_office, semantics)
            else:
                end_utc, duration_seconds, duration_source = component_duration(
                    state, shown["comp"], start_utc, occ_office, semantics)
            local_start = to_local(occ_zone, start_utc)
            local_end = to_local(occ_zone, end_utc)
            office = state["offices"][occ_office]
            solar = (epoch_minutes(start_utc) + office["solar_offset"]) % 1440
            solar_row = office_row(state, occ_office, local_start.date())
            occ_id = "%s:%s:%s" % (collection, uid, fmt_utc(original))
            resolved = set()
            for ref in shown["attendees"]:
                person, hops, outcome = resolve_ref(state, ref, original.date())
                state["alias_records"].append({"occurrence_id": occ_id, "ref": ref, "resolved": person or "",
                                               "hops": hops, "outcome": outcome})
                if person is not None:
                    resolved.add(person)
            if shift_seconds:
                shift_ledger.append({
                    "occurrence_id": occ_id,
                    "applied_shift_minutes": applied_shift,
                })
            occurrences.append({
                "occurrence_id": occ_id,
                "collection": collection,
                "uid": uid,
                "office": occ_office,
                "original_utc": fmt_utc(original),
                "start_utc": fmt_utc(start_utc),
                "end_utc": fmt_utc(end_utc),
                "duration_seconds": duration_seconds,
                "duration_source": duration_source,
                "applied_shift_minutes": applied_shift,
                "override": is_override,
                "local_start": fmt_local(local_start),
                "local_end": fmt_local(local_end),
                "utc_offset_minutes": offset_at(occ_zone, start_utc),
                "solar_minutes": solar,
                "solar_in_window": solar_row[4] <= solar < solar_row[5],
                "summary": shown["summary"],
                "required_attendees": sorted(resolved),
                "series_class": shown["series_class"],
                "_start": start_utc,
                "_end": end_utc,
                "_pinned": master["pinned"],
            })
    occurrences.sort(key=lambda o: (o["start_utc"], o["occurrence_id"]))
    audit = {
        "exdates_applied": sorted(exdates_applied, key=lambda r: (r["collection"], r["uid"], r["exdate_utc"])),
        "exdates_unmatched": sorted(exdates_unmatched, key=lambda r: (r["collection"], r["uid"], r["exdate_utc"])),
        "overrides_applied": sorted(overrides_applied, key=lambda r: (r["collection"], r["uid"], r["recurrence_id_utc"])),
        "overrides_rejected": sorted(
            overrides_rejected,
            key=lambda r: (r["collection"], r["uid"], r["recurrence_id_utc"], r["reason"])),
        "shift_ledger": sorted(shift_ledger, key=lambda r: r["occurrence_id"]),
        "counts": {
            "exdates_applied": len(exdates_applied),
            "exdates_unmatched": len(exdates_unmatched),
            "overrides_applied": len(overrides_applied),
            "overrides_rejected": len(overrides_rejected),
        },
    }
    return occurrences, resolutions, audit


def build_timezone_audit(state, resolutions):
    window_start = state["window_start"]
    window_end = state["window_end"] + timedelta(days=1)
    zones = []
    for tzid in sorted(state["zones"]):
        zone = state["zones"][tzid]
        rows = []
        history = []
        for onset, frm, to in zone.transitions:
            if onset >= window_end:
                continue
            item = {"onset_utc": fmt_utc(onset), "from_offset_minutes": frm, "to_offset_minutes": to}
            history.append(item)
            if window_start <= onset:
                rows.append(item)
        zones.append({
            "tzid": tzid,
            "observance_count": zone.observance_count,
            "transitions_in_window": rows,
            "transitions_through_window": history,
        })
    ordered = sorted(resolutions, key=lambda r: (r["occurrence_id"], r["nominal_local"]))
    counts = {"ambiguous": 0, "nonexistent": 0, "unique": 0}
    for row in ordered:
        counts[row["classification"]] += 1
    return {"zones": zones, "resolutions": ordered, "counts": counts}


# ------------------------------------------------------------------ conflicts


def conflict_pairs(state, occurrences):
    buffer_minutes = state["governance"]["buffer"]
    by_attendee = {}
    for occ in occurrences:
        for attendee in occ["required_attendees"]:
            by_attendee.setdefault(attendee, []).append(occ)
    seen = set()
    pairs = []
    reach = timedelta(minutes=buffer_minutes)
    for attendee in sorted(by_attendee):
        items = sorted(by_attendee[attendee], key=lambda o: (o["_start"], o["occurrence_id"]))
        for i in range(len(items)):
            first = items[i]
            for j in range(i + 1, len(items)):
                second = items[j]
                if second["_start"] >= first["_end"] + reach:
                    break
                key = (first["occurrence_id"], second["occurrence_id"])
                if key in seen:
                    continue
                buffer_applied = buffer_minutes if first["office"] != second["office"] else 0
                effective_end = first["_end"] + timedelta(minutes=buffer_applied)
                if effective_end > second["_start"]:
                    seen.add(key)
                    pairs.append({
                        "first": first["occurrence_id"],
                        "second": second["occurrence_id"],
                        "shared_attendees": sorted(set(first["required_attendees"]) & set(second["required_attendees"])),
                        "offices": [first["office"], second["office"]],
                        "buffer_applied": buffer_applied,
                        "overlap_minutes": int((effective_end - second["_start"]).total_seconds() // 60),
                    })
    pairs.sort(key=lambda p: (p["first"], p["second"]))
    return pairs


def rank_of(state, occurrence):
    return state["ranks"].get(occurrence["series_class"], state["default_rank"])


def is_pinned(state, occurrence):
    return occurrence["_pinned"] or rank_of(state, occurrence) >= state["pin_rank"]


def is_open_day(state, office_code, day):
    return office_row(state, office_code, day)[1] and \
        day.isoformat() not in state["holidays"].get(office_code, {})


def deferral_target(state, occurrence):
    zone = zone_for_office(state, occurrence["office"])
    old_local = to_local(zone, occurrence["_start"])
    target_local = old_local + timedelta(minutes=state["governance"]["quantum"])
    new_start = resolve_local(zone, target_local)[0]
    local_start = to_local(zone, new_start)
    local_end = to_local(zone, new_start + timedelta(seconds=occurrence["duration_seconds"]))
    day_zero = datetime(local_start.year, local_start.month, local_start.day)
    closing = office_row(state, occurrence["office"], local_start.date())[3]
    if int((local_end - day_zero).total_seconds() // 60) > closing:
        day = local_start.date() + timedelta(days=1)
        while not is_open_day(state, occurrence["office"], day):
            day += timedelta(days=1)
        opening = office_row(state, occurrence["office"], day)[2]
        target_local = datetime(day.year, day.month, day.day) + timedelta(minutes=opening)
    return old_local, target_local, zone


def stabilize(state, occurrences):
    current = [dict(occ) for occ in occurrences]
    by_id = dict((o["occurrence_id"], o) for o in current)
    moves = []
    rounds = 0
    stop = "clear"
    residual = []
    cap = state["governance"]["round_cap"]
    while True:
        pairs = conflict_pairs(state, current)
        if not pairs:
            break
        if rounds >= cap:
            stop = "cap"
            residual = pairs
            break
        ordered = sorted(pairs, key=lambda p: (by_id[p["first"]]["_start"], p["first"], p["second"]))
        movable = [
            p for p in ordered
            if not (is_pinned(state, by_id[p["first"]]) and is_pinned(state, by_id[p["second"]]))
        ]
        if not movable:
            stop = "pinned"
            residual = pairs
            break
        rounds += 1
        target_pair = movable[0]
        first = by_id[target_pair["first"]]
        second = by_id[target_pair["second"]]
        rank_first = rank_of(state, first)
        rank_second = rank_of(state, second)
        if is_pinned(state, first):
            victim = second
        elif is_pinned(state, second):
            victim = first
        elif rank_first < rank_second:
            victim = first
        elif rank_second < rank_first:
            victim = second
        else:
            victim = first if first["occurrence_id"] > second["occurrence_id"] else second
        old_local, target_local, zone = deferral_target(state, victim)
        new_start, _classification, gap_shift, _offset = resolve_local(zone, target_local)
        old_start = victim["_start"]
        victim["_start"] = new_start
        victim["_end"] = new_start + timedelta(seconds=victim["duration_seconds"])
        victim["start_utc"] = fmt_utc(victim["_start"])
        victim["end_utc"] = fmt_utc(victim["_end"])
        moves.append({
            "round": rounds,
            "occurrence_id": victim["occurrence_id"],
            "from_utc": fmt_utc(old_start),
            "to_utc": fmt_utc(new_start),
            "deferred_minutes": int((target_local - old_local).total_seconds() // 60),
            "gap_shift_minutes": gap_shift,
            "reason_first": target_pair["first"],
            "reason_second": target_pair["second"],
        })
    gov = state["governance"]
    summary = {
        "rounds": rounds,
        "converged": stop == "clear",
        "stop_reason": stop,
        "buffer_minutes": gov["buffer"],
        "quantum_minutes": gov["quantum"],
        "round_cap": cap,
        "pin_rank": gov["pin_rank"],
        "default_rank": gov["default_rank"],
        "effective_revision": gov["effective_revision"],
        "residual_conflicts": residual,
    }
    return summary, moves, current


# ------------------------------------------------- itineraries and presence

CIRCADIAN_FLOOR = -30
CIRCADIAN_DECAY = 3
CIRCADIAN_UNIT = 15
CIRCADIAN_CAP = 8
TRAVEL_PRE_MINUTES = 120
TRAVEL_POST_MINUTES = 90


def build_legs(state):
    legs = []
    for leg in state["itineraries"]["legs"]:
        depart_zone = zone_for_office(state, leg["depart_office"])
        arrive_zone = zone_for_office(state, leg["arrive_office"])
        depart_local = parse_dt_value(leg["depart_local"])[1]
        arrive_local = parse_dt_value(leg["arrive_local"])[1]
        depart_utc, depart_class, depart_shift, _o1 = resolve_local(depart_zone, depart_local)
        arrive_utc, arrive_class, arrive_shift, _o2 = resolve_local(arrive_zone, arrive_local)
        local_shift_days = (arrive_local.date() - depart_local.date()).days
        utc_shift_days = (arrive_utc.date() - depart_utc.date()).days
        legs.append({
            "leg_id": leg["leg_id"],
            "attendee": leg["attendee"],
            "depart_office": leg["depart_office"],
            "arrive_office": leg["arrive_office"],
            "depart_utc": fmt_utc(depart_utc),
            "arrive_utc": fmt_utc(arrive_utc),
            "depart_classification": depart_class,
            "arrive_classification": arrive_class,
            "depart_shift_minutes": depart_shift,
            "arrive_shift_minutes": arrive_shift,
            "duration_minutes": int((arrive_utc - depart_utc).total_seconds() // 60),
            "local_date_shift_days": local_shift_days,
            "utc_date_shift_days": utc_shift_days,
            "date_line_crossing": local_shift_days != utc_shift_days,
            "blocked_from_utc": fmt_utc(depart_utc - timedelta(minutes=TRAVEL_PRE_MINUTES)),
            "blocked_to_utc": fmt_utc(arrive_utc + timedelta(minutes=TRAVEL_POST_MINUTES)),
            "_depart": depart_utc,
            "_arrive": arrive_utc,
        })
    legs.sort(key=lambda leg: (leg["depart_utc"], leg["leg_id"]))
    return legs


def effective_office(state, legs, attendee, instant):
    office = state["attendees"][attendee]["home_office"]
    best = None
    for leg in legs:
        if leg["attendee"] != attendee:
            continue
        if leg["_arrive"] <= instant:
            if best is None or leg["_arrive"] > best["_arrive"]:
                best = leg
    if best is not None:
        office = best["arrive_office"]
    return office


def build_circadian(state, legs, occurrences):
    per_attendee = {}
    for occ in occurrences:
        for attendee in occ["required_attendees"]:
            per_attendee.setdefault(attendee, []).append(occ)
    rows = []
    over_cap = []
    for attendee in sorted(per_attendee):
        items = sorted(per_attendee[attendee], key=lambda o: (o["_start"], o["occurrence_id"]))
        debt = 0
        peak = 0
        previous_end_date = None
        previous_office = None
        steps = []
        for occ in items:
            office_code = effective_office(state, legs, attendee, occ["_start"])
            office = state["offices"][office_code]
            zone = zone_for_office(state, office_code)
            local_start = to_local(zone, occ["_start"])
            row = office_row(state, office_code, local_start.date())
            solar = (epoch_minutes(occ["_start"]) + office["solar_offset"]) % 1440
            deviation = max(row[4] - solar, solar - row[5])
            cost_units = deviation // CIRCADIAN_UNIT
            local_end = to_local(zone, occ["_end"])
            if previous_end_date is None:
                rest_days = 0
            else:
                rest_days = (local_start.date() - previous_end_date).days - 1
            # Amendment A1: a single free day earns no decay.
            decay_applied = CIRCADIAN_DECAY * (rest_days - 1) if rest_days > 1 else 0
            office_changed = previous_office is not None and previous_office != office_code
            debt = max(CIRCADIAN_FLOOR, debt - decay_applied + cost_units)
            if office_changed:
                debt = 0
            steps.append({
                "occurrence_id": occ["occurrence_id"],
                "effective_office": office_code,
                "deviation_minutes": deviation,
                "cost_units": cost_units,
                "rest_days": rest_days,
                "decay_applied": decay_applied,
                "office_changed": office_changed,
                "debt_after": debt,
            })
            if debt > peak:
                peak = debt
            previous_end_date = local_end.date()
            previous_office = office_code
        final_debt = steps[-1]["debt_after"] if steps else 0
        rows.append({
            "attendee": attendee,
            "steps": steps,
            "peak_debt": peak,
            "final_debt": final_debt,
        })
        if peak > CIRCADIAN_CAP:
            over_cap.append({
                "attendee": attendee,
                "peak_debt": peak,
                "excess": peak - CIRCADIAN_CAP,
            })
    return {
        "floor": CIRCADIAN_FLOOR,
        "decay_per_rest_day": CIRCADIAN_DECAY,
        "unit_minutes": CIRCADIAN_UNIT,
        "cap": CIRCADIAN_CAP,
        "attendees": rows,
        "over_cap": sorted(over_cap, key=lambda r: r["attendee"]),
    }


def build_attendance(state, legs, occurrences):
    per_attendee = {}
    for occ in occurrences:
        for attendee in occ["required_attendees"]:
            per_attendee.setdefault(attendee, []).append(occ)
    rows = []
    total_violations = 0
    with_violations = 0
    for attendee in sorted(state["attendees"]):
        items = sorted(per_attendee.get(attendee, []), key=lambda o: (o["_start"], o["occurrence_id"]))
        violations = []
        for occ in items:
            office_code = effective_office(state, legs, attendee, occ["_start"])
            office = state["offices"][office_code]
            zone = zone_for_office(state, office_code)
            local_start = to_local(zone, occ["_start"])
            local_end = to_local(zone, occ["_end"])
            day_zero = datetime(local_start.year, local_start.month, local_start.day)
            start_min = int((local_start - day_zero).total_seconds() // 60)
            end_min = int((local_end - day_zero).total_seconds() // 60)
            row = office_row(state, office_code, local_start.date())
            closed = local_start.date().isoformat() in state["holidays"].get(office_code, {})
            resting = not row[1]
            for kind, applies in (("non-working-day", resting), ("office-holiday", closed)):
                if applies:
                    violations.append({
                        "occurrence_id": occ["occurrence_id"],
                        "effective_office": office_code,
                        "kind": kind,
                        "local_start": fmt_local(local_start),
                        "minutes_outside": 0,
                    })
            # Amendment A2: a closed or non working day skips the working window test.
            if closed or resting:
                continue
            if start_min < row[2] or end_min > row[3]:
                violations.append({
                    "occurrence_id": occ["occurrence_id"],
                    "effective_office": office_code,
                    "kind": "outside-working-window",
                    "local_start": fmt_local(local_start),
                    "minutes_outside": max(
                        row[2] - start_min, end_min - row[3]),
                })
        violations.sort(key=lambda v: (v["occurrence_id"], v["kind"]))
        total_violations += len(violations)
        if violations:
            with_violations += 1
        rows.append({
            "attendee": attendee,
            "occurrence_count": len(items),
            "violations": violations,
            "violation_count": len(violations),
        })
    return {
        "attendees": rows,
        "counts": {
            "attendees": len(rows),
            "violations": total_violations,
            "attendees_with_violations": with_violations,
        },
    }


FBTYPE_PRECEDENCE = {"BUSY-UNAVAILABLE": 0, "BUSY": 1, "BUSY-TENTATIVE": 2}


def coalesce_freebusy(blocks):
    by_attendee = {}
    for block in blocks:
        if block["fbtype"] != "FREE":
            by_attendee.setdefault(block["attendee"], []).append(block)
    merged = []
    for attendee in sorted(by_attendee):
        current = None
        for block in sorted(by_attendee[attendee], key=lambda b: (b["start"], b["end"])):
            if current is not None and block["start"] <= current["end"]:
                current["end"] = max(current["end"], block["end"])
                current["fbtype"] = min(
                    (current["fbtype"], block["fbtype"]),
                    key=lambda t: (FBTYPE_PRECEDENCE.get(t, 3), t))
                continue
            current = dict(block)
            merged.append(current)
    return merged


def build_travel(state, legs, occurrences):
    blocked = []
    for leg in legs:
        low = leg["_depart"] - timedelta(minutes=TRAVEL_PRE_MINUTES)
        high = leg["_arrive"] + timedelta(minutes=TRAVEL_POST_MINUTES)
        for occ in occurrences:
            if leg["attendee"] not in occ["required_attendees"]:
                continue
            if occ["_start"] < high and occ["_end"] > low:
                airborne = occ["_start"] < leg["_arrive"] and occ["_end"] > leg["_depart"]
                blocked.append({
                    "occurrence_id": occ["occurrence_id"],
                    "attendee": leg["attendee"],
                    "leg_id": leg["leg_id"],
                    "kind": "airborne" if airborne else "ground-buffer",
                })
    freebusy_hits = []
    for block in coalesce_freebusy(state["freebusy"]):
        for occ in occurrences:
            if block["attendee"] not in occ["required_attendees"]:
                continue
            if occ["_start"] < block["end"] and occ["_end"] > block["start"]:
                freebusy_hits.append({
                    "occurrence_id": occ["occurrence_id"],
                    "attendee": block["attendee"],
                    "block_start_utc": fmt_utc(block["start"]),
                    "block_end_utc": fmt_utc(block["end"]),
                    "fbtype": block["fbtype"],
                })
    clean_legs = []
    for leg in legs:
        row = dict(leg)
        row.pop("_depart", None)
        row.pop("_arrive", None)
        clean_legs.append(row)
    blocked.sort(key=lambda r: (r["occurrence_id"], r["leg_id"]))
    freebusy_hits.sort(key=lambda r: (r["occurrence_id"], r["block_start_utc"], r["attendee"]))
    return {
        "legs": clean_legs,
        "blocked_occurrences": blocked,
        "freebusy_conflicts": freebusy_hits,
        "counts": {
            "legs": len(clean_legs),
            "date_line_crossings": sum(1 for leg in clean_legs if leg["date_line_crossing"]),
            "blocked_occurrences": len(blocked),
            "freebusy_conflicts": len(freebusy_hits),
        },
    }


# ----------------------------------------------------------------- sync state


def project_components(state, comps, semantics):
    rows = []
    for comp in sorted(comps, key=lambda c: (c["recurrence_id"], c["sequence"])):
        start_utc = resolve_property_instant(
            state, comp["dtstart_kind"], comp["dtstart"], comp["dtstart_tzid"])[0]
        office_code = comp["office"] or list(state["offices"])[0]
        _end, duration_seconds, _source = component_duration(
            state, comp, start_utc, office_code, semantics)
        rows.append({
            "attendees": comp["attendees"],
            "duration_seconds": duration_seconds,
            "office": comp["office"],
            "recurrence_id": comp["recurrence_id"],
            "sequence": comp["sequence"],
            "start_utc": fmt_utc(start_utc),
            "summary": comp["summary"],
            "uid": comp["uid"],
        })
    return rows


def build_sync_state(state, merged):
    semantics = state["store"]["duration_semantics"]
    by_replica = {}
    for comp in state["components"]:
        by_replica.setdefault((comp["collection"], comp["replica"], comp["uid"]), []).append(comp)
    by_resource = dict(((comp["collection"], comp["uid"]), []) for comp in state["components"])
    for (collection, uid, _rid), comp in merged.items():
        by_resource[(collection, uid)].append(comp)
    collections = []
    total_entries = 0
    changed_total = 0
    for collection in state["store"]["collections"]:
        cid = collection["id"]
        status_local = state["statuses"][(cid, "local")]
        status_server = state["statuses"][(cid, "server")]
        rev_local = dict((e["href"], int(e["revision"])) for e in status_local["entries"])
        rev_server = dict((e["href"], int(e["revision"])) for e in status_server["entries"])
        entries = []
        for (col, uid) in sorted(by_resource):
            if col != cid:
                continue
            href = href_for(state, cid, uid)
            merged_projection = project_components(state, by_resource[(col, uid)], semantics)
            local_projection = project_components(
                state, by_replica.get((cid, "local", uid), []), semantics)
            server_projection = project_components(
                state, by_replica.get((cid, "server", uid), []), semantics)
            etag = '"' + sha256_hex(canonical_dumps(merged_projection)) + '"'
            changed_local = merged_projection != local_projection
            changed_server = merged_projection != server_projection
            base = max(rev_local.get(href, 0), rev_server.get(href, 0))
            revision = base + 1 if (changed_local or changed_server) else base
            if changed_local or changed_server:
                changed_total += 1
            entries.append({
                "href": href,
                "etag": etag,
                "revision": revision,
                "changed_local": changed_local,
                "changed_server": changed_server,
            })
        entries.sort(key=lambda e: e["href"])
        payload = "".join("%s\t%s\n" % (e["href"], e["etag"]) for e in entries)
        collections.append({
            "collection": cid,
            "href": collection["href"],
            "sync_token": cid + "-" + sha256_hex(payload),
            "entries": entries,
        })
        total_entries += len(entries)
    return {
        "collections": collections,
        "counts": {
            "collections": len(collections),
            "resources": total_entries,
            "changed_resources": changed_total,
        },
    }


# ------------------------------------------------------------------ chargeback


def rate_on(state, attendee, day):
    cents = 0
    for when, value in state["rates"].get(attendee, []):
        if when <= day:
            cents = value
    return cents


def half_even_div(numerator, denominator):
    quotient, remainder = divmod(numerator, denominator)
    if 2 * remainder > denominator or (2 * remainder == denominator and quotient % 2 == 1):
        quotient += 1
    return quotient


def half_up_div(numerator, denominator):
    quotient, remainder = divmod(numerator, denominator)
    if 2 * remainder >= denominator:
        quotient += 1
    return quotient


def build_chargeback(state, settled):
    fx = state["governance"]["fx"]
    offices = {}
    base_by = {}
    for occ in settled:
        office = occ["office"]
        bps = fx.get(office, 10000)
        day = occ["_start"].date()
        for attendee in occ["required_attendees"]:
            line = half_even_div(rate_on(state, attendee, day) * occ["duration_seconds"], 3600)
            converted = half_up_div(line * bps, 10000)
            entry = offices.setdefault(office, {"lines": 0, "base_cents": 0, "converted_cents": 0, "fx_bps": bps})
            entry["lines"] += 1
            entry["base_cents"] += line
            entry["converted_cents"] += converted
            key = (office, occ["collection"])
            base_by[key] = base_by.get(key, 0) + line
    allocations = {}
    for office, entry in sorted(offices.items()):
        shares = []
        total_base = entry["base_cents"]
        for (off, collection), base in sorted(base_by.items()):
            if off != office:
                continue
            numerator = entry["converted_cents"] * base
            whole, rest = divmod(numerator, total_base) if total_base else (0, 0)
            shares.append([collection, whole, rest])
        remainder = entry["converted_cents"] - sum(s[1] for s in shares)
        for share in sorted(shares, key=lambda s: (-s[2], s[0]))[:remainder]:
            share[1] += 1
        for collection, whole, _rest in shares:
            allocations.setdefault(collection, {})[office] = whole
    totals = dict((c, sum(v.values())) for c, v in allocations.items())
    office_doc = {
        "offices": offices,
        "totals": {
            "lines": sum(e["lines"] for e in offices.values()),
            "base_cents": sum(e["base_cents"] for e in offices.values()),
            "converted_cents": sum(e["converted_cents"] for e in offices.values()),
        },
    }
    return office_doc, {"allocations": allocations, "totals": totals}


# -------------------------------------------------------- authority audit


def _lower_yaml(state):
    return parse_yaml(read_text(os.path.join(state["store_dir"], state["files"]["escalation_draft"])))


def build_authority_audit(state, transitions):
    gov = state["governance"]
    draft = _lower_yaml(state)
    rows = []

    def add(subject, key, in_force, source, lower):
        rows.append([subject, key, in_force, source, lower, in_force == lower])

    settling = draft.get("settling") or {}
    for key, value in (("buffer_minutes", gov["buffer"]), ("quantum_minutes", gov["quantum"]),
                       ("round_cap", gov["round_cap"]), ("pin_rank", gov["pin_rank"]),
                       ("default_rank", gov["default_rank"])):
        add("settling-parameter", key, str(value), "escalation_draft", str(settling.get(key, "")))
    draft_ranks = draft.get("class_ranks") or {}
    for cls in sorted(set(gov["classes"]) | set(draft_ranks)):
        add("class-rank", cls, str(gov["ranks"].get(cls, gov["default_rank"])), "escalation_draft",
            str(draft_ranks.get(cls, "")))
    draft_fx = draft.get("conversion_bps") or {}
    for office in sorted(set(gov["fx_offices"]) | set(draft_fx)):
        add("conversion-bps", office, str(gov["fx"].get(office, "")), "escalation_draft", str(draft_fx.get(office, "")))
    snapshot = {}
    with open(os.path.join(state["store_dir"], state["files"]["office_snapshot"]), "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            snapshot[(row["code"], row["weekday"])] = row
    start = state["window_start"].date()
    for code in sorted(state["offices"]):
        office = state["offices"][code]
        lower = snapshot.get((code, "MO"))
        add("office-longitude", code, office["longitude"], "office_snapshot", lower["longitude"] if lower else "")
    names = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
    for code in sorted(state["offices"]):
        for wd in names:
            day = start + timedelta(days=(WEEKDAY_CODES[wd] - start.weekday()) % 7)
            row = office_row(state, code, day)
            lower = snapshot.get((code, wd))
            add("office-window", "%s:%s" % (code, wd), "%d-%d" % (row[2], row[3]), "office_snapshot",
                "%s-%s" % (lower["open_minute"], lower["close_minute"]) if lower else "")
    payroll = {}
    with open(os.path.join(state["store_dir"], state["files"]["payroll_export"]), "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            payroll[row["attendee"]] = row["cents_per_hour"]
    for attendee in sorted(set(state["attendees"]) | set(payroll)):
        add("attendee-rate", attendee, str(rate_on(state, attendee, start)), "payroll_export", payroll.get(attendee, ""))
    cache = {}
    window_start = state["window_start"]
    window_end = state["window_end"] + timedelta(days=1)
    for line in read_text(os.path.join(state["store_dir"], state["files"]["zone_cache"])).split("\n"):
        if not line.strip() or line.startswith("#") or line.startswith("tzid\t"):
            continue
        tzid, onset, frm, to = line.split("\t")
        when = parse_dt_value(onset)[1]
        if window_start <= when < window_end:
            cache.setdefault(tzid, []).append("%s/%s/%s" % (onset, frm, to))
    for zone in transitions:
        in_force = ";".join("%s/%d/%d" % (t["onset_utc"], t["from_offset_minutes"], t["to_offset_minutes"])
                            for t in zone["transitions_in_window"])
        add("zone-transitions", zone["tzid"], in_force, "zone_cache", ";".join(sorted(cache.get(zone["tzid"], []))))
    order = dict((s, i) for i, s in enumerate(("settling-parameter", "class-rank", "conversion-bps", "office-longitude",
                                               "office-window", "attendee-rate", "zone-transitions")))
    rows.sort(key=lambda r: (order[r[0]], r[1]))
    return rows


def build_drift(state, occurrences, series_keys):
    previous = read_json(os.path.join(state["store_dir"], state["files"]["previous_run"]))
    v3 = dict(((r["collection"], r["uid"]), int(r["occurrence_count"])) for r in previous["series_summary"])
    counts = {}
    for occ in occurrences:
        key = (occ["collection"], occ["uid"])
        counts[key] = counts.get(key, 0) + 1
    rows = []
    for key in sorted(set(v3) | set(series_keys)):
        now = counts.get(key, 0)
        before = v3.get(key)
        rows.append([key[0], key[1], "" if before is None else before, now, "" if before is None else now - before])
    return rows


# --------------------------------------------------------------------- writers


def canonical_dumps(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _cell(value):
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(str(v) for v in value)
    return str(value)


def write_table(path, header, rows, delimiter):
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(header)
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(buf.getvalue())


def write_json(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(canonical_dumps(obj) + "\n")


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(canonical_dumps(row) + "\n")


ARTIFACTS = [
    "decisions.jsonl", "reconciliation.json", "outbox_replay.jsonl", "occurrences.csv", "alias_resolutions.tsv",
    "resolutions.tsv", "exceptions.jsonl", "zone_transitions.tsv", "conflicts.jsonl", "settle_moves.csv",
    "settled_schedule.csv", "settle_summary.json", "load_steps.tsv", "load_summary.json", "attendance.psv",
    "legs.json", "travel_blocks.csv", "busy_conflicts.tsv", "sync_entries.tsv", "sync_tokens.json",
    "chargeback_offices.json", "chargeback_collections.json", "authority_audit.csv", "drift.csv",
]


def build_manifest(out_dir):
    chain = sha256_hex(b"")
    root = chain
    links = []
    for name in ARTIFACTS:
        with open(os.path.join(out_dir, name), "rb") as fh:
            digest = sha256_hex(fh.read())
        chain = sha256_hex(chain + "\n" + name + "\n" + digest)
        links.append({"name": name, "file_sha256": digest, "chain_sha256": chain})
    return {"algorithm": "sha256-chain", "order": list(ARTIFACTS), "links": links,
            "chain_root": root, "chain_head": chain}


OCCURRENCE_FIELDS = ["occurrence_id", "collection", "uid", "office", "original_utc", "start_utc", "end_utc",
                     "duration_seconds", "duration_source", "applied_shift_minutes", "override", "local_start",
                     "local_end", "utc_offset_minutes", "solar_minutes", "solar_in_window", "series_class",
                     "required_attendees", "summary"]


def run(store_dir, out_dir):
    state = load_store(store_dir)
    state["alias_records"] = []
    os.makedirs(out_dir, exist_ok=True)
    replay = replay_outbox(state)
    reconciliation, merged, shadow = reconcile(state)
    occurrences, resolutions, exceptions = expand(state, merged, shadow)
    timezone_audit = build_timezone_audit(state, resolutions)
    conflicts = conflict_pairs(state, occurrences)
    settle, moves, settled = stabilize(state, occurrences)
    legs = build_legs(state)
    circadian = build_circadian(state, legs, occurrences)
    attendance = build_attendance(state, legs, settled)
    travel = build_travel(state, legs, settled)
    sync_state = build_sync_state(state, merged)
    charge_offices, charge_collections = build_chargeback(state, settled)
    series_keys = set((c, u) for (c, u, _r), comp in merged.items() if (c, u) not in shadow)
    out = lambda name: os.path.join(out_dir, name)

    write_jsonl(out("decisions.jsonl"), reconciliation["decisions"])
    write_json(out("reconciliation.json"), {
        "policy": reconciliation["policy"], "counts": reconciliation["counts"],
        "duplicate_uids": reconciliation["duplicate_uids"],
        "effective_revision": state["governance"]["effective_revision"]})
    write_jsonl(out("outbox_replay.jsonl"), replay)
    write_table(out("occurrences.csv"), OCCURRENCE_FIELDS,
                [[occ[f] for f in OCCURRENCE_FIELDS] for occ in occurrences], ",")
    alias_rows = sorted(state["alias_records"], key=lambda r: (r["occurrence_id"], r["ref"]))
    write_table(out("alias_resolutions.tsv"), ["occurrence_id", "ref", "resolved", "hops", "outcome"],
                [[r["occurrence_id"], r["ref"], r["resolved"], r["hops"], r["outcome"]] for r in alias_rows], "\t")
    res_fields = ["occurrence_id", "tzid", "nominal_local", "classification", "shift_minutes", "utc_offset_minutes"]
    write_table(out("resolutions.tsv"), res_fields,
                [[r[f] for f in res_fields] for r in timezone_audit["resolutions"]], "\t")
    records = []
    for kind, key in (("exdate-applied", "exdates_applied"), ("exdate-unmatched", "exdates_unmatched"),
                      ("override-applied", "overrides_applied"), ("override-rejected", "overrides_rejected"),
                      ("shift", "shift_ledger")):
        for row in exceptions[key]:
            item = dict(row)
            item["kind"] = kind
            records.append(item)
    write_jsonl(out("exceptions.jsonl"), records)
    zone_rows = []
    for zone in timezone_audit["zones"]:
        for t in zone["transitions_through_window"]:
            zone_rows.append([zone["tzid"], zone["observance_count"], t["onset_utc"],
                              t["from_offset_minutes"], t["to_offset_minutes"]])
    write_table(out("zone_transitions.tsv"),
                ["tzid", "observance_count", "onset_utc", "from_offset_minutes", "to_offset_minutes"], zone_rows, "\t")
    write_jsonl(out("conflicts.jsonl"), conflicts)
    move_fields = ["round", "occurrence_id", "from_utc", "to_utc", "deferred_minutes", "gap_shift_minutes",
                   "reason_first", "reason_second"]
    write_table(out("settle_moves.csv"), move_fields, [[m[f] for f in move_fields] for m in moves], ",")
    write_table(out("settled_schedule.csv"), ["occurrence_id", "office", "start_utc", "end_utc"],
                [[o["occurrence_id"], o["office"], o["start_utc"], o["end_utc"]]
                 for o in sorted(settled, key=lambda o: o["occurrence_id"])], ",")
    write_json(out("settle_summary.json"), settle)
    step_fields = ["occurrence_id", "effective_office", "deviation_minutes", "cost_units", "rest_days",
                   "decay_applied", "office_changed", "debt_after"]
    steps = []
    for person in circadian["attendees"]:
        for number, step in enumerate(person["steps"], 1):
            steps.append([person["attendee"], number] + [step[f] for f in step_fields])
    write_table(out("load_steps.tsv"), ["attendee", "step"] + step_fields, steps, "\t")
    write_json(out("load_summary.json"), {
        "floor": circadian["floor"], "decay_per_rest_day": circadian["decay_per_rest_day"],
        "unit_minutes": circadian["unit_minutes"], "cap": circadian["cap"], "over_cap": circadian["over_cap"],
        "attendees": dict((p["attendee"], {"peak_debt": p["peak_debt"], "final_debt": p["final_debt"]})
                          for p in circadian["attendees"])})
    violations = []
    for person in attendance["attendees"]:
        for v in person["violations"]:
            violations.append([person["attendee"], v["occurrence_id"], v["effective_office"], v["kind"],
                               v["local_start"], v["minutes_outside"]])
    write_table(out("attendance.psv"),
                ["attendee", "occurrence_id", "effective_office", "kind", "local_start", "minutes_outside"],
                violations, "|")
    write_json(out("legs.json"), {"legs": travel["legs"], "counts": travel["counts"]})
    write_table(out("travel_blocks.csv"), ["occurrence_id", "attendee", "leg_id", "kind"],
                [[b["occurrence_id"], b["attendee"], b["leg_id"], b["kind"]] for b in travel["blocked_occurrences"]], ",")
    write_table(out("busy_conflicts.tsv"), ["occurrence_id", "attendee", "block_start_utc", "block_end_utc", "fbtype"],
                [[b["occurrence_id"], b["attendee"], b["block_start_utc"], b["block_end_utc"], b["fbtype"]]
                 for b in travel["freebusy_conflicts"]], "\t")
    entries = []
    for coll in sync_state["collections"]:
        for e in coll["entries"]:
            entries.append([coll["collection"], e["href"], e["etag"], e["revision"], e["changed_local"], e["changed_server"]])
    write_table(out("sync_entries.tsv"), ["collection", "href", "etag", "revision", "changed_local", "changed_server"],
                entries, "\t")
    write_json(out("sync_tokens.json"), {
        "collections": [{"collection": c["collection"], "href": c["href"], "sync_token": c["sync_token"],
                         "resources": len(c["entries"])} for c in sync_state["collections"]],
        "counts": sync_state["counts"]})
    write_json(out("chargeback_offices.json"), charge_offices)
    write_json(out("chargeback_collections.json"), charge_collections)
    write_table(out("authority_audit.csv"), ["subject", "key", "in_force", "source", "lower_value", "agrees"],
                build_authority_audit(state, timezone_audit["zones"]), ",")
    write_table(out("drift.csv"), ["collection", "uid", "v3_count", "v5_count", "delta"],
                build_drift(state, occurrences, series_keys), ",")
    write_json(out("manifest.json"), build_manifest(out_dir))
    return state


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: schedule_repair.py DATA_DIR OUT_DIR")
    run(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
