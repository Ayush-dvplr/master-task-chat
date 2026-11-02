#!/usr/bin/env python3
"""EXEC-OPS calendar store reconciliation pass (revision v5)."""

import bisect
import hashlib
import json
import os
import re
import sqlite3
import sys
import urllib.parse
import zipfile
import zlib
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP

EPOCH_ORD = date(1970, 1, 1).toordinal()
WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
WD_INDEX = {w: i for i, w in enumerate(WEEKDAYS)}


# --------------------------------------------------------------------------
# basic time helpers.  A "wall" value is an integer count of seconds of a
# naive calendar clock; an "instant" is an integer count of seconds UTC.
# --------------------------------------------------------------------------

def parse_basic(value):
    """Return (wall_seconds, is_utc, is_date) for a basic date-time value."""
    v = value.strip()
    is_utc = v.endswith("Z")
    if is_utc:
        v = v[:-1]
    if len(v) == 8 and v.isdigit():
        return day_secs(int(v[0:4]), int(v[4:6]), int(v[6:8])), is_utc, True
    m = re.match(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$", v)
    if not m:
        raise ValueError("bad date-time value %r" % (value,))
    y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
    return day_secs(y, mo, d) + hh * 3600 + mm * 60 + ss, is_utc, False


def day_secs(y, mo, d):
    return (date(y, mo, d).toordinal() - EPOCH_ORD) * 86400


def to_basic(value):
    """Normalise an extended or basic ISO value to basic form."""
    v = value.strip()
    suffix = ""
    if v.endswith("Z"):
        suffix = "Z"
        v = v[:-1]
    v = v.replace("-", "").replace(":", "")
    return v + suffix


def fmt_wall(secs):
    days, rem = divmod(secs, 86400)
    d = date.fromordinal(EPOCH_ORD + days)
    hh, rem = divmod(rem, 3600)
    mm, ss = divmod(rem, 60)
    return "%04d%02d%02dT%02d%02d%02d" % (d.year, d.month, d.day, hh, mm, ss)


def fmt_utc(secs):
    return fmt_wall(secs) + "Z"


def wall_date(secs):
    return date.fromordinal(EPOCH_ORD + (secs // 86400))


def wall_midnight(secs):
    return (secs // 86400) * 86400


def floordiv(a, b):
    return a // b


BUSY_ORDER = {"BUSY-UNAVAILABLE": 0, "BUSY": 1, "BUSY-TENTATIVE": 2}


def busy_type(kinds):
    best = None
    for kind in kinds:
        rank = BUSY_ORDER.get(kind.upper(), 3)
        key = (rank, kind if rank == 3 else "")
        if best is None or key < best[0]:
            best = (key, kind)
    return best[1]


def parse_offset(text):
    """iCalendar UTC offset ("+0530", "-0800", "+053045") to minutes."""
    t = text.strip()
    sign = 1
    if t[0] in "+-":
        sign = -1 if t[0] == "-" else 1
        t = t[1:]
    hh = int(t[0:2])
    mm = int(t[2:4])
    ss = int(t[4:6]) if len(t) >= 6 else 0
    return sign * (hh * 3600 + mm * 60 + ss)


DUR_RE = re.compile(
    r"^(?P<sign>[+-])?P(?:(?P<w>\d+)W)?(?:(?P<d>\d+)D)?"
    r"(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$")


def parse_duration(text):
    """Return (sign, weeks, days, seconds_of_time_part)."""
    m = DUR_RE.match(text.strip())
    if not m:
        raise ValueError("bad duration %r" % (text,))
    sign = -1 if m.group("sign") == "-" else 1
    w = int(m.group("w") or 0)
    d = int(m.group("d") or 0)
    h = int(m.group("h") or 0)
    mi = int(m.group("m") or 0)
    s = int(m.group("s") or 0)
    return sign, w, d, h * 3600 + mi * 60 + s


def is_duration_value(text):
    t = text.strip()
    if t[:1] in "+-":
        t = t[1:]
    return t[:1] == "P"


# --------------------------------------------------------------------------
# iCalendar content line grammar
# --------------------------------------------------------------------------

def unfold_octets(data):
    """Unfold raw octets: delete each LF plus the single whitespace after it."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0x0A and i + 1 < n and data[i + 1] in (0x20, 0x09):
            i += 2
            continue
        if (b == 0x0D and i + 2 < n and data[i + 1] == 0x0A
                and data[i + 2] in (0x20, 0x09)):
            i += 3
            continue
        out.append(b)
        i += 1
    return bytes(out)


def split_unquoted(text, delim):
    parts = []
    cur = []
    quoted = False
    for ch in text:
        if ch == '"':
            quoted = not quoted
            cur.append(ch)
        elif ch == delim and not quoted:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def strip_quotes(text):
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def parse_content_line(line):
    """Return (NAME, params dict lower->list of values, raw value string)."""
    quoted = False
    idx = -1
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif ch == ":" and not quoted:
            idx = i
            break
    if idx < 0:
        return line.strip().upper(), {}, ""
    head = line[:idx]
    value = line[idx + 1:]
    pieces = split_unquoted(head, ";")
    name = pieces[0].strip().upper()
    params = {}
    for piece in pieces[1:]:
        if not piece:
            continue
        eq = piece.find("=")
        if eq < 0:
            pname, pval = piece.strip().lower(), ""
        else:
            pname = piece[:eq].strip().lower()
            pval = piece[eq + 1:]
        vals = [strip_quotes(v) for v in split_unquoted(pval, ",")]
        params.setdefault(pname, []).extend(vals)
    return name, params, value


def unescape_text(value):
    out = []
    i = 0
    n = len(value)
    while i < n:
        ch = value[i]
        if ch == "\\" and i + 1 < n:
            nxt = value[i + 1]
            if nxt in ("n", "N"):
                out.append("\n")
            else:
                out.append(nxt)
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def split_text_list(value):
    """Split a multi valued property on unescaped commas."""
    parts = []
    cur = []
    i = 0
    n = len(value)
    while i < n:
        ch = value[i]
        if ch == "\\" and i + 1 < n:
            cur.append(ch)
            cur.append(value[i + 1])
            i += 2
            continue
        if ch == ",":
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts


def parse_recur_text(value):
    parts = {}
    for chunk in value.split(";"):
        if not chunk:
            continue
        if "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        parts[k.strip().upper()] = [x for x in v.split(",") if x != ""]
    return parts


def parse_ical_components(data):
    """Parse iCalendar octets into a tree of components.

    A component is {'name': NAME, 'props': [(NAME, params, vtype, values)],
    'subs': [component, ...]} where values are already normalised:
    date-time/date values are basic strings, a period is a ('period', a, b)
    tuple, a recur is a dict and everything else is a decoded string.
    """
    text = unfold_octets(data).decode("utf-8")
    stack = []
    root = {"name": "ROOT", "props": [], "subs": []}
    stack.append(root)
    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        name, params, value = parse_content_line(line)
        if name == "BEGIN":
            comp = {"name": value.strip().upper(), "props": [], "subs": []}
            stack[-1]["subs"].append(comp)
            stack.append(comp)
            continue
        if name == "END":
            if len(stack) > 1:
                stack.pop()
            continue
        stack[-1]["props"].append(ical_property(name, params, value))
    return root


DT_PROPS = ("DTSTART", "DTEND", "RECURRENCE-ID", "EXDATE", "RDATE",
            "LAST-MODIFIED", "DTSTAMP", "CREATED", "UNTIL")


def ical_property(name, params, value):
    if name == "RRULE":
        return (name, params, "recur", [parse_recur_text(value)])
    if name in ("EXDATE", "RDATE"):
        vals = []
        for item in split_text_list(value):
            item = item.strip()
            if not item:
                continue
            if "/" in item:
                a, b = item.split("/", 1)
                vals.append(("period", to_basic(a), to_basic(b)))
            else:
                vals.append(to_basic(item))
        return (name, params, "date-time", vals)
    if name in DT_PROPS:
        return (name, params, "date-time", [to_basic(value.strip())])
    if name == "SEQUENCE":
        return (name, params, "integer", [value.strip()])
    if name == "DURATION":
        return (name, params, "duration", [value.strip()])
    if name == "ATTENDEE":
        return (name, params, "cal-address", [value.strip()])
    return (name, params, "text", [unescape_text(value)])


# --------------------------------------------------------------------------
# the XML calendar encoding
# --------------------------------------------------------------------------

XCAL_NS = "{urn:ietf:params:xml:ns:icalendar-2.0}"


def xcal_local(tag):
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def parse_xcal(data):
    root = ET.fromstring(data)
    comp = {"name": "ROOT", "props": [], "subs": []}
    if xcal_local(root.tag).upper() == "ICALENDAR":
        for child in root:
            comp["subs"].append(xcal_component(child))
    else:
        comp["subs"].append(xcal_component(root))
    return comp


def xcal_component(elem):
    comp = {"name": xcal_local(elem.tag).upper(), "props": [], "subs": []}
    for child in elem:
        tag = xcal_local(child.tag)
        if tag == "properties":
            for prop in child:
                comp["props"].append(xcal_property(prop))
        elif tag == "components":
            for sub in child:
                comp["subs"].append(xcal_component(sub))
        else:
            comp["subs"].append(xcal_component(child))
    return comp


def xcal_property(elem):
    name = xcal_local(elem.tag).upper()
    params = {}
    values = []
    vtype = "text"
    for child in elem:
        tag = xcal_local(child.tag)
        if tag == "parameters":
            for p in child:
                pname = xcal_local(p.tag).lower()
                pvals = [(t.text or "") for t in p if xcal_local(t.tag) == "text"]
                if not pvals:
                    pvals = [p.text or ""]
                params.setdefault(pname, []).extend(pvals)
            continue
        vtype = tag
        if tag in ("date-time", "date"):
            values.append(to_basic(child.text or ""))
            vtype = "date-time"
        elif tag == "period":
            start = None
            second = None
            for q in child:
                qt = xcal_local(q.tag)
                if qt == "start":
                    start = to_basic(q.text or "")
                elif qt == "end":
                    second = to_basic(q.text or "")
                elif qt == "duration":
                    second = (q.text or "").strip()
            values.append(("period", start, second))
            vtype = "date-time"
        elif tag == "recur":
            parts = {}
            for q in child:
                qt = xcal_local(q.tag).upper()
                parts.setdefault(qt, []).append((q.text or "").strip())
            if "UNTIL" in parts:
                parts["UNTIL"] = [to_basic(v) for v in parts["UNTIL"]]
            values.append(parts)
            vtype = "recur"
        else:
            values.append((child.text or "").strip() if tag != "text"
                          else (child.text or ""))
    return (name, params, vtype, values)


# --------------------------------------------------------------------------
# the JSON calendar encoding
# --------------------------------------------------------------------------

def parse_jcal(data):
    doc = json.loads(data.decode("utf-8"))
    comp = {"name": "ROOT", "props": [], "subs": []}
    comp["subs"].append(jcal_component(doc))
    return comp


def jcal_component(node):
    name = node[0].upper()
    comp = {"name": name, "props": [], "subs": []}
    for prop in node[1]:
        comp["props"].append(jcal_property(prop))
    for sub in node[2]:
        comp["subs"].append(jcal_component(sub))
    return comp


def jcal_property(prop):
    name = prop[0].upper()
    params = {}
    for k, v in (prop[1] or {}).items():
        if isinstance(v, list):
            params.setdefault(k.lower(), []).extend([str(x) for x in v])
        else:
            params.setdefault(k.lower(), []).append(str(v))
    vtype = prop[2]
    raw = prop[3:]
    values = []
    if vtype in ("date-time", "date"):
        for item in raw:
            if isinstance(item, list):
                second = item[1]
                values.append(("period", to_basic(item[0]),
                               second if is_duration_value(str(second))
                               else to_basic(second)))
            else:
                values.append(to_basic(item))
        vtype = "date-time"
    elif vtype == "period":
        for item in raw:
            second = item[1]
            values.append(("period", to_basic(item[0]),
                           second if is_duration_value(str(second))
                           else to_basic(second)))
        vtype = "date-time"
    elif vtype == "recur":
        for item in raw:
            parts = {}
            for k, v in item.items():
                key = k.upper()
                if isinstance(v, list):
                    parts[key] = [str(x) for x in v]
                else:
                    parts[key] = [str(v)]
            if "UNTIL" in parts:
                parts["UNTIL"] = [to_basic(v) for v in parts["UNTIL"]]
            values.append(parts)
    elif vtype == "integer":
        values = [str(x) for x in raw]
    else:
        values = [x if isinstance(x, str) else str(x) for x in raw]
    return (name, params, vtype, values)


def decode_replica(data):
    i = 0
    while i < len(data) and data[i] in (0x20, 0x09, 0x0A, 0x0D, 0xEF, 0xBB, 0xBF):
        i += 1
    first = data[i:i + 1]
    if first == b"<":
        return parse_xcal(data)
    if first == b"[":
        return parse_jcal(data)
    return parse_ical_components(data)


# --------------------------------------------------------------------------
# recurrence expansion
# --------------------------------------------------------------------------

def parse_byday_token(tok):
    t = tok.strip().upper()
    m = re.match(r"^([+-]?\d+)?([A-Z]{2})$", t)
    if not m:
        raise ValueError("bad BYDAY token %r" % (tok,))
    ordinal = int(m.group(1)) if m.group(1) else None
    return ordinal, WD_INDEX[m.group(2)]


def month_days(y, mo):
    if mo == 12:
        return (date(y + 1, 1, 1) - date(y, 12, 1)).days
    return (date(y, mo + 1, 1) - date(y, mo, 1)).days


def monthday_matches(d, numbers):
    dim = month_days(d.year, d.month)
    for n in numbers:
        if n > 0 and d.day == n:
            return True
        if n < 0 and d.day == dim + 1 + n:
            return True
    return False


def select_month_days(y, mo, bymonthday, byday, default_day):
    dim = month_days(y, mo)
    if bymonthday is None and byday is None:
        if default_day is None or default_day > dim:
            return []
        return [date(y, mo, default_day)]
    sets = []
    if bymonthday is not None:
        chosen = set()
        for n in bymonthday:
            if n > 0:
                if n <= dim:
                    chosen.add(n)
            elif n < 0:
                dd = dim + 1 + n
                if 1 <= dd <= dim:
                    chosen.add(dd)
        sets.append(chosen)
    if byday is not None:
        chosen = set()
        for ordinal, wd in byday:
            matching = [dd for dd in range(1, dim + 1)
                        if date(y, mo, dd).weekday() == wd]
            if ordinal is None:
                chosen.update(matching)
            elif ordinal > 0:
                if ordinal <= len(matching):
                    chosen.add(matching[ordinal - 1])
            elif ordinal < 0:
                if -ordinal <= len(matching):
                    chosen.add(matching[len(matching) + ordinal])
        sets.append(chosen)
    result = sets[0]
    for s in sets[1:]:
        result = result & s
    return [date(y, mo, dd) for dd in sorted(result)]


def year_week_starts(y, wkst):
    """Ordinals of the first day of every numbered week of year y."""
    jan1 = date(y, 1, 1)
    start = jan1.toordinal() - ((jan1.weekday() - wkst) % 7)
    last = date(y, 12, 31).toordinal()
    starts = []
    cur = start
    # locate week 1
    while True:
        inside = sum(1 for k in range(7)
                     if jan1.toordinal() <= cur + k <= last)
        if inside >= 4:
            break
        cur += 7
        if cur > last:
            return []
    while True:
        inside = sum(1 for k in range(7)
                     if jan1.toordinal() <= cur + k <= last)
        if inside < 4:
            break
        starts.append(cur)
        cur += 7
    return starts


def expand_rule(rule, dtstart_wall, bound_wall):
    """Ordered wall clock candidates of a rule, including ones before DTSTART."""
    freq = rule.get("FREQ", ["DAILY"])[0].upper()
    interval = int(rule.get("INTERVAL", ["1"])[0])
    wkst = WD_INDEX[rule.get("WKST", ["MO"])[0].strip().upper()]
    bymonth = ([int(x) for x in rule["BYMONTH"]] if "BYMONTH" in rule else None)
    bymonthday = ([int(x) for x in rule["BYMONTHDAY"]]
                  if "BYMONTHDAY" in rule else None)
    byday = ([parse_byday_token(x) for x in rule["BYDAY"]]
             if "BYDAY" in rule else None)
    byyearday = ([int(x) for x in rule["BYYEARDAY"]]
                 if "BYYEARDAY" in rule else None)
    byweekno = ([int(x) for x in rule["BYWEEKNO"]]
                if "BYWEEKNO" in rule else None)
    byhour = sorted(int(x) for x in rule["BYHOUR"]) if "BYHOUR" in rule else None
    byminute = (sorted(int(x) for x in rule["BYMINUTE"])
                if "BYMINUTE" in rule else None)
    bysetpos = ([int(x) for x in rule["BYSETPOS"]]
                if "BYSETPOS" in rule else None)

    start_date = wall_date(dtstart_wall)
    tod = dtstart_wall - wall_midnight(dtstart_wall)
    base_h = tod // 3600
    base_m = (tod % 3600) // 60
    base_s = tod % 60
    hours = byhour if byhour is not None else [base_h]
    minutes = byminute if byminute is not None else [base_m]
    bound_date = wall_date(bound_wall)
    bare_byday = (set(wd for _, wd in byday) if byday is not None else None)

    candidates = []

    def finish_period(days):
        items = []
        for d in days:
            for hh in hours:
                for mm in minutes:
                    items.append((d.toordinal() - EPOCH_ORD) * 86400
                                 + hh * 3600 + mm * 60 + base_s)
        items.sort()
        if bysetpos is not None:
            picked = []
            n = len(items)
            for p in bysetpos:
                if p > 0 and p <= n:
                    picked.append(items[p - 1])
                elif p < 0 and -p <= n:
                    picked.append(items[n + p])
            items = sorted(set(picked))
        candidates.extend(items)

    def keep_filter(days, use_byday=True):
        out = []
        for d in days:
            if bymonth is not None and d.month not in bymonth:
                continue
            if bymonthday is not None and not monthday_matches(d, bymonthday):
                continue
            if use_byday and bare_byday is not None and d.weekday() not in bare_byday:
                continue
            out.append(d)
        return out

    if freq == "DAILY":
        k = 0
        while True:
            d = date.fromordinal(start_date.toordinal() + k * interval)
            if d > bound_date:
                break
            finish_period(keep_filter([d]))
            k += 1
    elif freq == "WEEKLY":
        week0 = start_date.toordinal() - ((start_date.weekday() - wkst) % 7)
        k = 0
        while True:
            wstart = week0 + k * 7 * interval
            if date.fromordinal(wstart) > bound_date:
                break
            days = [date.fromordinal(wstart + i) for i in range(7)]
            if byday is not None:
                days = [d for d in days if d.weekday() in bare_byday]
            else:
                days = [d for d in days if d.weekday() == start_date.weekday()]
            out = []
            for d in days:
                if bymonth is not None and d.month not in bymonth:
                    continue
                if bymonthday is not None and not monthday_matches(d, bymonthday):
                    continue
                out.append(d)
            finish_period(out)
            k += 1
    elif freq == "MONTHLY":
        k = 0
        while True:
            total = (start_date.year * 12 + start_date.month - 1) + k * interval
            y, mo = divmod(total, 12)
            mo += 1
            if date(y, mo, 1) > bound_date:
                break
            if bymonth is not None and mo not in bymonth:
                k += 1
                continue
            finish_period(select_month_days(y, mo, bymonthday, byday,
                                            start_date.day))
            k += 1
    elif freq == "YEARLY":
        k = 0
        while True:
            y = start_date.year + k * interval
            if date(y, 1, 1) > bound_date:
                break
            if byyearday is None and byweekno is None:
                months = bymonth if bymonth is not None else [start_date.month]
                days = []
                for mo in sorted(months):
                    days.extend(select_month_days(y, mo, bymonthday, byday,
                                                  start_date.day))
                finish_period(sorted(days))
            else:
                ylen = (date(y, 12, 31).toordinal() - date(y, 1, 1).toordinal() + 1)
                base = date(y, 1, 1).toordinal()
                sets = []
                if byyearday is not None:
                    chosen = set()
                    for n in byyearday:
                        if n > 0 and n <= ylen:
                            chosen.add(base + n - 1)
                        elif n < 0 and -n <= ylen:
                            chosen.add(base + ylen + n)
                    sets.append(chosen)
                if byweekno is not None:
                    starts = year_week_starts(y, wkst)
                    chosen = set()
                    for n in byweekno:
                        if n > 0 and n <= len(starts):
                            ws = starts[n - 1]
                        elif n < 0 and -n <= len(starts):
                            ws = starts[len(starts) + n]
                        else:
                            continue
                        for i in range(7):
                            o = ws + i
                            if base <= o <= base + ylen - 1:
                                chosen.add(o)
                    sets.append(chosen)
                result = sets[0]
                for s in sets[1:]:
                    result = result & s
                days = [date.fromordinal(o) for o in sorted(result)]
                if byweekno is not None and byday is None:
                    days = [d for d in days
                            if d.weekday() == start_date.weekday()]
                finish_period(keep_filter(days))
            k += 1
    else:
        raise ValueError("unsupported FREQ %r" % (freq,))
    return candidates


# --------------------------------------------------------------------------
# zones
# --------------------------------------------------------------------------

class Zone(object):
    def __init__(self, tzid, observances, transitions):
        self.tzid = tzid
        self.observance_count = observances
        self.transitions = transitions
        self.onsets = [t[0] for t in transitions]
        self.offsets = sorted(set([t[1] for t in transitions]
                                  + [t[2] for t in transitions]))

    def offset_at(self, instant):
        if not self.transitions:
            return 0
        i = bisect.bisect_right(self.onsets, instant)
        if i == 0:
            return self.transitions[0][1]
        return self.transitions[i - 1][2]

    def to_wall(self, instant):
        return instant + self.offset_at(instant)

    def resolve(self, wall):
        survivors = []
        for off in self.offsets:
            cand = wall - off
            if self.offset_at(cand) == off:
                survivors.append(cand)
        survivors = sorted(set(survivors))
        if len(survivors) == 1:
            return survivors[0], "unique", 0
        if len(survivors) > 1:
            return survivors[0], "ambiguous", 0
        for onset, frm, to in self.transitions:
            gap = to - frm
            if gap > 0 and onset + frm <= wall < onset + to:
                return (wall + gap) - to, "nonexistent", gap // 60
        raise ValueError("cannot resolve %s in %s" % (fmt_wall(wall), self.tzid))


def build_zones(data, bound_wall):
    root = parse_ical_components(data)
    zones = {}
    stack = [root]
    while stack:
        comp = stack.pop()
        for sub in comp["subs"]:
            if sub["name"] == "VTIMEZONE":
                zone = build_zone(sub, bound_wall)
                zones[zone.tzid] = zone
            else:
                stack.append(sub)
    return zones


def props_of(comp, name):
    return [p for p in comp["props"] if p[0] == name]


def first_value(comp, name):
    for p in comp["props"]:
        if p[0] == name:
            return p[3][0] if p[3] else None
    return None


def build_zone(comp, bound_wall):
    tzid = first_value(comp, "TZID")
    transitions = []
    observances = 0
    for sub in comp["subs"]:
        if sub["name"] not in ("STANDARD", "DAYLIGHT"):
            continue
        observances += 1
        dtstart = first_value(sub, "DTSTART")
        frm = parse_offset(first_value(sub, "TZOFFSETFROM"))
        to = parse_offset(first_value(sub, "TZOFFSETTO"))
        base_wall = parse_basic(dtstart)[0]
        onsets = {base_wall}
        for prop in props_of(sub, "RRULE"):
            rule = prop[3][0]
            until = None
            if "UNTIL" in rule:
                until = parse_basic(rule["UNTIL"][0])[0]
            count = int(rule["COUNT"][0]) if "COUNT" in rule else None
            cands = expand_rule(rule, base_wall, bound_wall)
            kept = [c for c in cands if c >= base_wall]
            if count is not None:
                kept = kept[:count]
            for c in kept:
                if until is not None and (c - frm) > until:
                    continue
                onsets.add(c)
        for prop in props_of(sub, "RDATE"):
            for val in prop[3]:
                if isinstance(val, tuple):
                    val = val[1]
                w = parse_basic(val)[0]
                if w >= base_wall:
                    onsets.add(w)
        for w in onsets:
            transitions.append((w - frm, frm, to))
    transitions = sorted(set(transitions))
    return Zone(tzid, observances, transitions)


class ZoneTable(object):
    def __init__(self, zones, aliases):
        self.zones = zones
        self.alias_map = {}
        for entry in aliases.get("aliases", []):
            if entry.get("status") != "active":
                continue
            self.alias_map[entry["alias"]] = entry["target"]

    def canonical(self, name):
        seen = set()
        cur = name
        while cur in self.alias_map and cur not in seen:
            seen.add(cur)
            cur = self.alias_map[cur]
        return cur

    def zone(self, name):
        canon = self.canonical(name)
        if canon not in self.zones:
            raise KeyError("unknown zone %r" % (name,))
        return self.zones[canon]


# --------------------------------------------------------------------------
# the office register workbook
# --------------------------------------------------------------------------

SS_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
PR_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def col_of(ref):
    letters = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def row_of(ref):
    return int("".join(ch for ch in ref if ch.isdigit()))


class Workbook(object):
    def __init__(self, path):
        self.zf = zipfile.ZipFile(path)
        wb = ET.fromstring(self.zf.read("xl/workbook.xml"))
        pr = wb.find(SS_NS + "workbookPr")
        self.date1904 = bool(pr is not None and pr.get("date1904") in ("1", "true"))
        rels = {}
        rel_root = ET.fromstring(self.zf.read("xl/_rels/workbook.xml.rels"))
        for rel in rel_root:
            rels[rel.get("Id")] = rel.get("Target")
        self.shared = []
        if "xl/sharedStrings.xml" in self.zf.namelist():
            sst = ET.fromstring(self.zf.read("xl/sharedStrings.xml"))
            for si in sst.findall(SS_NS + "si"):
                self.shared.append("".join(t.text or "" for t in si.iter(SS_NS + "t")))
        self.sheets = []
        for sheet in wb.iter(SS_NS + "sheet"):
            rid = None
            for key, val in sheet.attrib.items():
                if key.endswith("}id"):
                    rid = val
            target = rels.get(rid, "")
            if target.startswith("/"):
                part = target[1:]
            else:
                part = "xl/" + target
            self.sheets.append((sheet.get("name"), part))

    def cells(self, part):
        root = ET.fromstring(self.zf.read(part))
        out = {}
        for c in root.iter(SS_NS + "c"):
            ref = c.get("r")
            t = c.get("t")
            if t == "s":
                v = c.find(SS_NS + "v")
                val = self.shared[int(v.text)] if v is not None else ""
            elif t == "inlineStr":
                node = c.find(SS_NS + "is")
                val = ("".join(x.text or "" for x in node.iter(SS_NS + "t"))
                       if node is not None else "")
            elif t == "str":
                v = c.find(SS_NS + "v")
                val = v.text if v is not None else ""
            else:
                v = c.find(SS_NS + "v")
                val = v.text if v is not None else ""
            out[ref] = val if val is not None else ""
        return out

    def table(self, table_name, edition):
        for name, part in self.sheets:
            cells = self.cells(part)
            if (cells.get("A1", "").strip() == table_name
                    and cells.get("B1", "").strip() == edition
                    and cells.get("B2", "").strip() == "in force"):
                return self.rows(cells)
        raise KeyError("no sheet in force for %r %r" % (table_name, edition))

    def rows(self, cells):
        header = {}
        for ref, val in cells.items():
            if row_of(ref) == 4 and val.strip():
                header[col_of(ref)] = val.strip()
        max_row = max((row_of(r) for r in cells), default=4)
        out = []
        for r in range(5, max_row + 1):
            row = {}
            present = False
            for col, cname in header.items():
                ref = col_letters(col) + str(r)
                if ref in cells:
                    row[cname] = cells[ref]
                    if cells[ref] != "":
                        present = True
                else:
                    row[cname] = ""
            if present:
                out.append(row)
        return out

    def serial_date(self, value):
        n = int(Decimal(str(value).replace(",", "").strip()))
        base = date(1904, 1, 1) if self.date1904 else date(1899, 12, 30)
        return date.fromordinal(base.toordinal() + n)


def col_letters(n):
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def parse_int_cell(value):
    text = str(value).replace(",", "").strip()
    if text == "":
        return None
    return int(Decimal(text))


class Register(object):
    def __init__(self, path, edition):
        wb = Workbook(path)
        self.wb = wb
        self.office_rows = {}
        self.office_order = []
        for row in wb.table("office register", edition):
            code = row["office"].strip()
            wd = row["weekday"].strip().upper()
            eff = wb.serial_date(row["effective from"])
            entry = {
                "office": code,
                "tzid": row["tzid"].strip(),
                "longitude": str(row["longitude"]).strip(),
                "weekday": wd,
                "working": row["working"].strip().upper(),
                "open": parse_int_cell(row["open minute"]),
                "close": parse_int_cell(row["close minute"]),
                "solar_open": parse_int_cell(row["solar open"]),
                "solar_close": parse_int_cell(row["solar close"]),
                "effective_from": eff,
            }
            if code not in self.office_rows:
                self.office_rows[code] = {}
                self.office_order.append(code)
            self.office_rows[code].setdefault(wd, []).append(entry)
        for code in self.office_rows:
            for wd in self.office_rows[code]:
                self.office_rows[code][wd].sort(key=lambda e: e["effective_from"])
        self.rates = {}
        for row in wb.table("attendee rates", edition):
            att = row["attendee"].strip()
            self.rates.setdefault(att, []).append(
                (wb.serial_date(row["effective from"]),
                 parse_int_cell(row["cents per hour"])))
        for att in self.rates:
            self.rates[att].sort(key=lambda e: e[0])
        self.solar_offsets = {}
        for code in self.office_rows:
            lon = Decimal(self.longitude(code))
            product = lon * 4
            self.solar_offsets[code] = int(
                product.quantize(Decimal(1), rounding=ROUND_HALF_UP))

    def offices(self):
        return list(self.office_order)

    def longitude(self, code):
        for wd in WEEKDAYS:
            rows = self.office_rows[code].get(wd)
            if rows:
                return rows[0]["longitude"]
        raise KeyError(code)

    def tzid(self, code):
        for wd in WEEKDAYS:
            rows = self.office_rows[code].get(wd)
            if rows:
                return rows[0]["tzid"]
        raise KeyError(code)

    def row_in_force(self, code, local_date):
        wd = WEEKDAYS[local_date.weekday()]
        rows = self.office_rows.get(code, {}).get(wd, [])
        best = None
        for entry in rows:
            if entry["effective_from"] <= local_date:
                best = entry
        return best

    def working_window(self, code, local_date):
        row = self.row_in_force(code, local_date)
        if row is None:
            return None
        if row["working"] != "Y":
            return (0, 0, row)
        return (row["open"], row["close"], row)

    def solar_minute(self, instant, code):
        return (instant // 60 + self.solar_offsets[code]) % 1440

    def rate_in_force(self, attendee, on_date):
        best = None
        for eff, cents in self.rates.get(attendee, []):
            if eff <= on_date:
                best = cents
        return best


# --------------------------------------------------------------------------
# the governance schedule PDF
# --------------------------------------------------------------------------

def pdf_objects(data):
    objs = {}
    for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj\b", data):
        num = int(m.group(1))
        start = m.end()
        end = data.find(b"endobj", start)
        objs[num] = data[start:end]
    return objs


def pdf_page_streams(data):
    objs = pdf_objects(data)
    pages = []
    root = None
    for num, body in objs.items():
        if b"/Type /Pages" in body or b"/Type/Pages" in body:
            root = body
    order = []
    if root is not None:
        m = re.search(rb"/Kids\s*\[(.*?)\]", root, re.S)
        if m:
            order = [int(x) for x in re.findall(rb"(\d+)\s+0\s+R", m.group(1))]
    if not order:
        order = sorted(n for n, b in objs.items()
                       if b"/Type /Page" in b or b"/Type/Page" in b)
    for num in order:
        body = objs.get(num, b"")
        m = re.search(rb"/Contents\s+(\d+)\s+0\s+R", body)
        if not m:
            continue
        stream = objs.get(int(m.group(1)), b"")
        sm = re.search(rb"stream\r?\n", stream)
        if not sm:
            continue
        raw = stream[sm.end():]
        raw = re.sub(rb"\s*endstream\s*$", b"", raw)
        if b"FlateDecode" in stream[:sm.start()]:
            raw = zlib.decompress(raw)
        pages.append(raw)
    return pages


def pdf_literal(text):
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt in "01234567":
                digits = ""
                j = i + 1
                while j < n and len(digits) < 3 and text[j] in "01234567":
                    digits += text[j]
                    j += 1
                out.append(chr(int(digits, 8)))
                i = j
                continue
            mapping = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}
            out.append(mapping.get(nxt, nxt))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def pdf_show_text(operand):
    """Decode the operand of a Tj or TJ operator into its text."""
    out = []
    i = 0
    n = len(operand)
    while i < n:
        ch = operand[i]
        if ch == "(":
            depth = 1
            j = i + 1
            buf = []
            while j < n:
                c = operand[j]
                if c == "\\" and j + 1 < n:
                    buf.append(c)
                    buf.append(operand[j + 1])
                    j += 2
                    continue
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
                buf.append(c)
                j += 1
            out.append(pdf_literal("".join(buf)))
            i = j + 1
            continue
        if ch == "<":
            j = operand.find(">", i)
            hexs = re.sub(r"\s", "", operand[i + 1:j])
            if len(hexs) % 2:
                hexs += "0"
            out.append(bytes.fromhex(hexs).decode("latin-1"))
            i = j + 1
            continue
        i += 1
    return "".join(out)


RUN_RE = re.compile(
    r"1\s+0\s+0\s+1\s+(-?[\d.]+)\s+(-?[\d.]+)\s+Tm\s*(.*?)\s*(TJ|Tj)",
    re.S)


def pdf_rows(data):
    rows = []
    for page in pdf_page_streams(data):
        text = page.decode("latin-1")
        runs = []
        for m in RUN_RE.finditer(text):
            x = Decimal(m.group(1))
            y = Decimal(m.group(2))
            runs.append((y, x, pdf_show_text(m.group(3))))
        by_y = {}
        for y, x, s in runs:
            by_y.setdefault(y, []).append((x, s))
        for y in sorted(by_y, reverse=True):
            cells = [s for _, s in sorted(by_y[y], key=lambda e: e[0])]
            rows.append(cells)
    return rows


CAPTION_RE = re.compile(r"^Table\s+(\d+)\.\s+(.*)$")


def pdf_tables(data):
    tables = {}
    current = None
    skip_header = False
    for cells in pdf_rows(data):
        joined = " ".join(cells).strip()
        if re.match(r"^page\s+\d+\s+of\s+\d+$", joined):
            continue
        m = CAPTION_RE.match(joined)
        if m:
            name = m.group(2).strip()
            if name.endswith("(continued)"):
                name = name[:-len("(continued)")].strip()
            current = name
            tables.setdefault(current, [])
            skip_header = True
            continue
        if current is None:
            continue
        if skip_header:
            skip_header = False
            continue
        tables[current].append(cells)
    return tables


class Governance(object):
    def __init__(self, path, policy_revision):
        tables = pdf_tables(open(path, "rb").read())
        self.revisions = {}
        for row in tables.get("Revision register", []):
            self.revisions[int(row[0])] = row[2].strip()
        approved = sorted(r for r, s in self.revisions.items() if s == "approved")
        self.effective_revision = min(policy_revision, max(approved))
        self.usable = [r for r in approved if r <= self.effective_revision]
        self.settling = self._pick_single(tables.get("Settling parameters", []))
        self.class_ranks = {}
        for cls, rev, rank in self._triples(tables.get("Series class ranks", [])):
            self.class_ranks.setdefault(cls, {})[rev] = rank
        self.conversion = {}
        for office, rev, bps in self._triples(tables.get("Office conversion", [])):
            self.conversion.setdefault(office, {})[rev] = bps
        self.buffer_minutes = self.settling[0]
        self.quantum_minutes = self.settling[1]
        self.round_cap = self.settling[2]
        self.pin_rank = self.settling[3]
        self.default_rank = self.settling[4]

    def _pick_single(self, rows):
        best = None
        best_rev = None
        for row in rows:
            rev = int(row[0])
            if rev not in self.usable:
                continue
            if best_rev is None or rev > best_rev:
                best_rev = rev
                best = [int(x.replace(",", "")) for x in row[1:6]]
        return best

    def _triples(self, rows):
        for row in rows:
            yield row[0].strip(), int(row[1]), int(row[2].replace(",", ""))

    def _lookup(self, table, key):
        entries = table.get(key)
        if not entries:
            return None
        best_rev = None
        for rev in entries:
            if rev in self.usable and (best_rev is None or rev > best_rev):
                best_rev = rev
        if best_rev is None:
            return None
        return entries[best_rev]

    def rank_of(self, cls):
        value = self._lookup(self.class_ranks, cls)
        return self.default_rank if value is None else value

    def listed_rank(self, cls):
        return self._lookup(self.class_ranks, cls)

    def bps_of(self, office):
        value = self._lookup(self.conversion, office)
        return 10000 if value is None else value

    def listed_bps(self, office):
        return self._lookup(self.conversion, office)


# --------------------------------------------------------------------------
# tabular inputs
# --------------------------------------------------------------------------

def read_delimited(path, delim):
    with open(path, "r", encoding="utf-8") as fh:
        lines = [l.rstrip("\n").rstrip("\r") for l in fh]
    lines = [l for l in lines if l.strip() != "" and not l.startswith("#")]
    if not lines:
        return []
    header = lines[0].split(delim)
    out = []
    for line in lines[1:]:
        fields = line.split(delim)
        row = {}
        for i, name in enumerate(header):
            row[name.strip()] = fields[i] if i < len(fields) else ""
        out.append(row)
    return out


def split_escaped(line, delim):
    parts = []
    cur = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and i + 1 < n:
            cur.append(line[i + 1])
            i += 2
            continue
        if ch == delim:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts


def read_outbox(path):
    with open(path, "r", encoding="utf-8") as fh:
        lines = [l.rstrip("\n").rstrip("\r") for l in fh]
    header = None
    out = []
    for line in lines:
        if line.strip() == "":
            continue
        if line[0] == "#":
            continue
        fields = split_escaped(line, "|")
        if header is None:
            header = [f.strip() for f in fields]
            continue
        row = {}
        for i, name in enumerate(header):
            row[name] = fields[i] if i < len(fields) else ""
        out.append(row)
    return out


def open_sqlite(path):
    uri = "file:" + urllib.parse.quote(os.path.abspath(path)) + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def read_jsonl(path):
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip() == "":
                continue
            out.append(json.loads(line))
    return out


# --------------------------------------------------------------------------
# the YAML subset of the status book
# --------------------------------------------------------------------------

def yaml_scalar(text):
    t = text.strip()
    if t.startswith("'"):
        end = 1
        out = []
        while end < len(t):
            if t[end] == "'":
                if end + 1 < len(t) and t[end + 1] == "'":
                    out.append("'")
                    end += 2
                    continue
                break
            out.append(t[end])
            end += 1
        return "".join(out)
    if t.startswith('"'):
        out = []
        i = 1
        while i < len(t):
            if t[i] == "\\" and i + 1 < len(t):
                out.append(t[i + 1])
                i += 2
                continue
            if t[i] == '"':
                break
            out.append(t[i])
            i += 1
        return "".join(out)
    # strip a trailing comment
    idx = None
    for i, ch in enumerate(t):
        if ch == "#" and (i == 0 or t[i - 1] in " \t"):
            idx = i
            break
    if idx is not None:
        t = t[:idx]
    return t.strip()


def yaml_strip_comment(line):
    out = []
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            out.append(ch)
            if ch == quote:
                if quote == "'" and i + 1 < len(line) and line[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
        i += 1
    return "".join(out).rstrip()


def parse_yaml(text):
    raw_lines = []
    for line in text.split("\n"):
        stripped = yaml_strip_comment(line)
        if stripped.strip() == "":
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        raw_lines.append((indent, stripped.strip()))
    value, _ = yaml_block(raw_lines, 0, 0)
    return value


def yaml_block(lines, pos, indent):
    if pos < len(lines) and lines[pos][1].startswith("- "):
        items = []
        while pos < len(lines) and lines[pos][0] == indent \
                and lines[pos][1].startswith("- "):
            item_indent = indent + 2
            inner = [(item_indent, lines[pos][1][2:].strip())]
            pos += 1
            while pos < len(lines) and lines[pos][0] >= item_indent:
                inner.append(lines[pos])
                pos += 1
            value, _ = yaml_block(inner, 0, item_indent)
            items.append(value)
        return items, pos
    mapping = {}
    while pos < len(lines) and lines[pos][0] == indent:
        text = lines[pos][1]
        if text.startswith("- "):
            break
        if ":" not in text:
            pos += 1
            continue
        key, rest = text.split(":", 1)
        key = yaml_scalar(key)
        rest = rest.strip()
        if rest != "":
            mapping[key] = yaml_scalar(rest)
            pos += 1
            continue
        pos += 1
        if pos < len(lines) and lines[pos][0] > indent:
            child_indent = lines[pos][0]
            inner = []
            while pos < len(lines) and lines[pos][0] >= child_indent:
                inner.append(lines[pos])
                pos += 1
            value, _ = yaml_block(inner, 0, child_indent)
            mapping[key] = value
        else:
            mapping[key] = None
    return mapping, pos


# --------------------------------------------------------------------------
# calendar component model
# --------------------------------------------------------------------------

class Component(object):
    __slots__ = ("uid", "rid_raw", "rid_tzid", "rid_range", "dtstart",
                 "dtstart_tzid", "dtend", "dtend_tzid", "duration", "rrule",
                 "rdates", "exdates", "sequence", "last_modified", "dtstamp",
                 "summary", "status", "refs", "office", "series_class",
                 "pinned", "has_sequence")

    def __init__(self):
        self.uid = None
        self.rid_raw = ""
        self.rid_tzid = None
        self.rid_range = ""
        self.dtstart = None
        self.dtstart_tzid = None
        self.dtend = None
        self.dtend_tzid = None
        self.duration = None
        self.rrule = None
        self.rdates = []
        self.exdates = []
        self.sequence = 0
        self.has_sequence = False
        self.last_modified = None
        self.dtstamp = None
        self.summary = None
        self.status = None
        self.refs = []
        self.office = None
        self.series_class = None
        self.pinned = False

    def clone(self):
        other = Component()
        for name in self.__slots__:
            value = getattr(self, name)
            if isinstance(value, list):
                value = list(value)
            setattr(other, name, value)
        return other

    @property
    def mtime(self):
        if self.last_modified is not None:
            return self.last_modified
        return self.dtstamp


def param(params, name):
    vals = params.get(name)
    if not vals:
        return None
    return vals[0]


def build_component(comp):
    out = Component()
    for name, params, vtype, values in comp["props"]:
        if name == "UID":
            out.uid = values[0] if values else ""
        elif name == "RECURRENCE-ID":
            out.rid_raw = values[0] if values else ""
            out.rid_tzid = param(params, "tzid")
            rng = param(params, "range")
            out.rid_range = rng.upper() if rng else ""
        elif name == "DTSTART":
            out.dtstart = values[0]
            out.dtstart_tzid = param(params, "tzid")
        elif name == "DTEND":
            out.dtend = values[0]
            out.dtend_tzid = param(params, "tzid")
        elif name == "DURATION":
            out.duration = values[0]
        elif name == "RRULE":
            out.rrule = values[0]
        elif name == "RDATE":
            tzid = param(params, "tzid")
            for v in values:
                out.rdates.append((v, tzid))
        elif name == "EXDATE":
            tzid = param(params, "tzid")
            for v in values:
                out.exdates.append((v if not isinstance(v, tuple) else v[1], tzid))
        elif name == "SEQUENCE":
            out.sequence = int(values[0])
            out.has_sequence = True
        elif name == "LAST-MODIFIED":
            out.last_modified = values[0]
        elif name == "DTSTAMP":
            out.dtstamp = values[0]
        elif name == "SUMMARY":
            out.summary = values[0]
        elif name == "STATUS":
            out.status = values[0]
        elif name == "ATTENDEE":
            role = param(params, "role")
            required = (role is None or role.strip().upper() == "REQ-PARTICIPANT")
            att = param(params, "x-att-id")
            if required and att:
                out.refs.append(att)
        elif name == "X-OFFICE":
            out.office = values[0]
        elif name == "X-SERIES-CLASS":
            out.series_class = values[0]
        elif name == "X-PINNED":
            out.pinned = (values[0].strip().upper() == "TRUE")
    return out


def load_replica(path):
    data = open(path, "rb").read()
    root = decode_replica(data)
    comps = []
    stack = list(root["subs"])
    while stack:
        comp = stack.pop(0)
        if comp["name"] == "VEVENT":
            comps.append(build_component(comp))
        else:
            stack = list(comp["subs"]) + stack
    return comps


# --------------------------------------------------------------------------
# serialisation helpers
# --------------------------------------------------------------------------

def json_text(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def field_text(value):
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (list, tuple)):
        return ";".join(field_text(v) for v in value)
    return str(value)


def table_text(header, rows, delim):
    out = []
    for record in [header] + list(rows):
        cells = []
        for value in record:
            text = field_text(value)
            if delim in text or '"' in text or "\r" in text or "\n" in text:
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        out.append(delim.join(cells))
    return "".join(line + "\n" for line in out)


class Writer(object):
    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.written = []

    def write(self, name, text):
        path = os.path.join(self.out_dir, name)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        self.written.append(name)

    def json(self, name, obj):
        self.write(name, json_text(obj) + "\n")

    def jsonl(self, name, objs):
        self.write(name, "".join(json_text(o) + "\n" for o in objs))

    def table(self, name, header, rows, delim):
        self.write(name, table_text(header, rows, delim))


# --------------------------------------------------------------------------
# store discovery
# --------------------------------------------------------------------------

def find_index(data_dir):
    found = []
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            if b"exec-ops-store/2" not in data:
                continue
            doc = json.loads(data.decode("utf-8"))
        except Exception:
            continue
        if isinstance(doc, dict) and doc.get("format") == "exec-ops-store/2":
            found.append((name, doc))
    if len(found) != 1:
        raise SystemExit("the directory %s is not a store" % (data_dir,))
    return found[0][1]


class Resolver(object):
    def __init__(self, zone_table):
        self.zt = zone_table

    def resolve(self, value, tzid, fallback_tzid=None):
        wall, is_utc, _is_date = parse_basic(value)
        if is_utc:
            name = (self.zt.canonical(tzid or fallback_tzid)
                    if (tzid or fallback_tzid) else None)
            return wall, name, "unique", 0
        name = tzid if tzid else fallback_tzid
        if name is None:
            return wall, None, "unique", 0
        zone = self.zt.zone(name)
        instant, kind, shift = zone.resolve(wall)
        return instant, zone.tzid, kind, shift

    def instant(self, value, tzid, fallback_tzid=None):
        return self.resolve(value, tzid, fallback_tzid)[0]


# --------------------------------------------------------------------------
# the reconciliation pass
# --------------------------------------------------------------------------

class Pass(object):
    def __init__(self, data_dir, out_dir):
        self.data_dir = data_dir
        self.out_dir = out_dir
        self.index = find_index(data_dir)
        self.files = self.index["files"]
        self.store = self.index["store"]
        self.collections = self.store["collections"]
        self.col_order = [c["id"] for c in self.collections]
        self.col_href = {c["id"]: c["href"] for c in self.collections}
        self.col_rank = {c["id"]: i for i, c in enumerate(self.collections)}
        win = self.store["window"]
        self.win_start_date = date(*[int(x) for x in win["start"].split("-")])
        self.win_end_date = date(*[int(x) for x in win["end"].split("-")])
        self.win_start = day_secs(self.win_start_date.year,
                                  self.win_start_date.month,
                                  self.win_start_date.day)
        self.win_end = (self.win_end_date.toordinal() + 1 - EPOCH_ORD) * 86400

    def path(self, role):
        return os.path.join(self.data_dir, self.files[role])

    # ---------------- stage 1: authorities ----------------

    def load_authorities(self):
        zone_bound = day_secs(self.win_end_date.year + 2, 1, 1)
        aliases = json.load(open(self.path("zone_aliases"), encoding="utf-8"))
        zones = build_zones(open(self.path("zones"), "rb").read(), zone_bound)
        self.zt = ZoneTable(zones, aliases)
        self.res = Resolver(self.zt)
        self.gov = Governance(self.path("governance"),
                              self.store["policy_revision"])
        self.reg = Register(self.path("register"),
                            self.store["register_edition"])
        self.default_office = self.reg.offices()[0]
        self.attendees = {}
        self.home_office = {}
        for row in read_delimited(self.path("attendees"), "\t"):
            self.attendees[row["id"].strip()] = row
            self.home_office[row["id"].strip()] = row["home_office"].strip()
        self.links = {}
        for row in read_delimited(self.path("aliases"), ","):
            if row["status"].strip() != "active":
                continue
            eff = date(*[int(x) for x in row["effective_from"].strip().split("-")])
            self.links.setdefault(row["handle"].strip(), []).append(
                (eff, row["target"].strip()))
        self.closures = {}
        conn = open_sqlite(self.path("closures"))
        rows = {}
        for office, day, _name, revision, state in conn.execute(
                "SELECT office, day, name, revision, state FROM closures"):
            key = (office, day)
            if key not in rows or revision > rows[key][0]:
                rows[key] = (revision, state)
        conn.close()
        for (office, day), (_rev, state) in rows.items():
            if state == "withdrawn":
                continue
            self.closures.setdefault(office, set()).add(
                date(*[int(x) for x in day.split("-")]))

    def office_code(self, office):
        return office if office in self.reg.office_rows else self.default_office

    def office_zone(self, office):
        return self.zt.zone(self.reg.tzid(self.office_code(office)))

    def resolve_ref(self, ref, on_date):
        visited = [ref]
        hops = 0
        cur = ref
        outcome = "direct"
        while True:
            best_eff = None
            for eff, _target in self.links.get(cur, []):
                if eff <= on_date and (best_eff is None or eff > best_eff):
                    best_eff = eff
            if best_eff is None:
                break
            target = min(t for eff, t in self.links[cur] if eff == best_eff)
            hops += 1
            if target in visited:
                idx = visited.index(target)
                result = min(visited[idx:])
                if result not in self.attendees:
                    return None, hops, "unresolved"
                return result, hops, "cycle"
            visited.append(target)
            cur = target
            outcome = "resolved"
        if cur not in self.attendees:
            return None, hops, "unresolved"
        return cur, hops, outcome

    # ---------------- stage 2: replicas and the outbox ----------------

    def load_replicas(self):
        self.local = {}
        self.server = {}
        for col in self.collections:
            cid = col["id"]
            self.local[cid] = {}
            for comp in load_replica(os.path.join(
                    self.data_dir, col["replicas"]["local"])):
                self.local[cid][(comp.uid, comp.rid_raw)] = comp
            self.server[cid] = {}
            for comp in load_replica(os.path.join(
                    self.data_dir, col["replicas"]["server"])):
                self.server[cid][(comp.uid, comp.rid_raw)] = comp

    def replay_outbox(self):
        rows = read_outbox(self.path("outbox"))
        rows = [r for r in rows if r["collection"] in self.local]
        rows.sort(key=lambda r: int(r["op_seq"]))
        report = []
        for row in rows:
            cid = row["collection"]
            key = (row["uid"], row["recurrence_id"])
            target = self.server[cid].get(key)
            op = row["op"].strip().upper()
            field = row["field"].strip()
            if target is None:
                outcome, after = "missing", None
            else:
                base = (int(row["base_sequence"])
                        if row["base_sequence"].strip() != "" else 0)
                if target.sequence != base:
                    outcome, after = "stale-base", target.sequence
                elif op == "DELETE":
                    del self.server[cid][key]
                    outcome, after = "applied", None
                else:
                    name = field.upper()
                    if name == "SUMMARY":
                        target.summary = row["value"]
                    elif name == "SEQUENCE":
                        target.sequence = int(row["value"])
                        target.has_sequence = True
                    elif name == "STATUS":
                        target.status = row["value"]
                    elif name == "X-SERIES-CLASS":
                        target.series_class = row["value"]
                    elif name == "DURATION":
                        target.duration = row["value"]
                        target.dtend = None
                        target.dtend_tzid = None
                    target.last_modified = row["stamp"]
                    outcome, after = "applied", target.sequence
            report.append({
                "op_seq": int(row["op_seq"]),
                "collection": cid,
                "uid": row["uid"],
                "recurrence_id": row["recurrence_id"],
                "op": op,
                "field": "" if op == "DELETE" else field,
                "outcome": outcome,
                "sequence_after": after,
            })
        self.outbox_report = report

    # ---------------- stage 3: the change log ----------------

    def load_journal(self):
        current = read_jsonl(self.path("journal"))
        legacy = read_jsonl(self.path("journal_legacy"))
        records = []
        identities = set()
        for rec in current:
            rid = rec.get("recurrence_id") or ""
            item = (rec["collection"], rec["replica"], rec["uid"], rid,
                    int(rec["revision"]), rec["op"])
            identities.add(item[:5])
            records.append(item)
        for rec in legacy:
            rid = rec.get("rid")
            rid = to_basic(rid) if rid else ""
            replica = "local" if str(rec["side"]).upper() == "L" else "server"
            op = "delete" if str(rec["action"]).upper() == "DEL" else "update"
            item = (rec["cal"], replica, rec["object"], rid, int(rec["rev"]), op)
            if item[:5] in identities:
                continue
            records.append(item)
        self.revision_of = {}
        self.delete_rev = {}
        for col, replica, uid, rid, rev, op in records:
            key = (col, replica, uid, rid)
            if op == "delete":
                if key not in self.delete_rev or rev > self.delete_rev[key]:
                    self.delete_rev[key] = rev
            else:
                if rev > self.revision_of.get(key, -1):
                    self.revision_of[key] = rev

    def revision(self, col, replica, uid, rid):
        return self.revision_of.get((col, replica, uid, rid), -1)

    # ---------------- stage 4: the merge ----------------

    def merge(self):
        policy = self.store["conflict_policy"]
        authority = self.store["authority_replica"]
        self.decisions = []
        self.merged = {}
        self.tombstoned = set()
        counts = {"components": 0, "contested": 0, "sole_replica": 0,
                  "tombstoned": 0}
        for col in self.collections:
            cid = col["id"]
            keys = set(self.local[cid]) | set(self.server[cid])
            for uid, rid in sorted(keys):
                lcomp = self.local[cid].get((uid, rid))
                scomp = self.server[cid].get((uid, rid))
                href = self.col_href[cid] + uid + ".ics"
                if lcomp is not None and scomp is not None:
                    counts["contested"] += 1
                    winner, rule = self.contest(cid, uid, rid, lcomp, scomp,
                                                policy, authority)
                    loser = "server" if winner == "local" else "local"
                    wcomp = lcomp if winner == "local" else scomp
                    ocomp = scomp if winner == "local" else lcomp
                    self.merged[(cid, uid, rid)] = wcomp
                    counts["components"] += 1
                    self.decisions.append({
                        "collection": cid, "uid": uid, "recurrence_id": rid,
                        "href": href, "winner": winner, "loser": loser,
                        "rule": rule,
                        "winning_sequence": wcomp.sequence,
                        "losing_sequence": ocomp.sequence,
                    })
                    continue
                holder = "local" if lcomp is not None else "server"
                other = "server" if holder == "local" else "local"
                comp = lcomp if lcomp is not None else scomp
                del_rev = self.delete_rev.get((cid, other, uid, rid))
                hold_rev = self.revision(cid, holder, uid, rid)
                if del_rev is not None and del_rev > hold_rev:
                    counts["tombstoned"] += 1
                    self.tombstoned.add((cid, uid, rid))
                    self.decisions.append({
                        "collection": cid, "uid": uid, "recurrence_id": rid,
                        "href": href, "winner": other, "loser": holder,
                        "rule": "tombstone",
                        "winning_sequence": -1,
                        "losing_sequence": comp.sequence,
                    })
                    continue
                counts["sole_replica"] += 1
                counts["components"] += 1
                self.merged[(cid, uid, rid)] = comp
                self.decisions.append({
                    "collection": cid, "uid": uid, "recurrence_id": rid,
                    "href": href, "winner": holder, "loser": "",
                    "rule": "sole-replica",
                    "winning_sequence": comp.sequence,
                    "losing_sequence": -1,
                })
        self.decisions.sort(key=lambda d: (d["collection"], d["uid"],
                                           d["recurrence_id"]))
        self.counts = counts
        holders = {}
        for (cid, uid, _rid) in self.merged:
            holders.setdefault(uid, set()).add(cid)
        self.duplicate_uids = []
        self.shadow = set()
        for uid in sorted(holders):
            if len(holders[uid]) < 2:
                continue
            cols = sorted(holders[uid], key=lambda c: self.col_rank[c])
            self.duplicate_uids.append({
                "uid": uid, "collections": cols,
                "primary_collection": cols[0],
            })
            for cid in cols[1:]:
                self.shadow.add((cid, uid))
        self.holders = holders

    def contest(self, cid, uid, rid, lcomp, scomp, policy, authority):
        if policy == "sequence-major":
            if lcomp.sequence != scomp.sequence:
                return ("local" if lcomp.sequence > scomp.sequence
                        else "server"), "sequence"
        else:
            lm, sm = lcomp.mtime, scomp.mtime
            if lm is None and sm is not None:
                return "server", "last-modified"
            if sm is None and lm is not None:
                return "local", "last-modified"
            if lm is not None and sm is not None and lm != sm:
                return ("local" if lm > sm else "server"), "last-modified"
        lrev = self.revision(cid, "local", uid, rid)
        srev = self.revision(cid, "server", uid, rid)
        if lrev != srev:
            return ("local" if lrev > srev else "server"), "revision"
        return authority, "authority"


    # ---------------- stage 5: expansion ----------------

    def duration_seconds(self, text, start_instant, office):
        sign, weeks, days, tail = parse_duration(text)
        calendar_days = weeks * 7 + days
        if calendar_days == 0 or self.store["duration_semantics"] == "exact":
            return sign * (calendar_days * 86400 + tail)
        zone = self.office_zone(office)
        wall = zone.to_wall(start_instant)
        shifted = wall + sign * calendar_days * 86400
        return (zone.resolve(shifted)[0] - start_instant) + sign * tail

    def component_duration(self, comp, start_instant, office):
        if comp.dtend:
            own = self.res.instant(comp.dtstart, comp.dtstart_tzid)
            end = self.res.instant(comp.dtend, comp.dtend_tzid or comp.dtstart_tzid)
            return end - own, "DTEND"
        if comp.duration:
            return (self.duration_seconds(comp.duration, start_instant, office),
                    "DURATION")
        return 3600, "DEFAULT"

    def period_duration(self, period, start_instant, office, tzid):
        second = period[2]
        if second is None:
            return 3600
        if is_duration_value(second):
            return self.duration_seconds(second, start_instant, office)
        first_instant = self.res.instant(period[1], tzid)
        second_instant = self.res.instant(second, tzid)
        return second_instant - first_instant

    def expand(self):
        bound_wall = self.win_end + 3 * 86400
        series = {}
        for (cid, uid, rid), comp in self.merged.items():
            entry = series.setdefault((cid, uid), {"master": None,
                                                   "overrides": []})
            if rid == "":
                entry["master"] = comp
            else:
                entry["overrides"].append(comp)
        self.series_keys = sorted(series, key=lambda k: (self.col_rank[k[0]], k[1]))
        self.occurrences = []
        self.resolution_rows = []
        self.exdate_applied = []
        self.exdate_unmatched = []
        self.override_applied = []
        self.override_rejected = []
        self.shift_records = []
        self.alias_rows = []
        self.series_counts = {}
        for (cid, uid) in self.series_keys:
            if (cid, uid) in self.shadow:
                continue
            entry = series[(cid, uid)]
            master = entry["master"]
            overrides = sorted(entry["overrides"], key=lambda c: c.rid_raw)
            if master is None:
                for comp in overrides:
                    instant = self.res.instant(comp.rid_raw, comp.rid_tzid)
                    self.override_rejected.append({
                        "kind": "override-rejected", "collection": cid,
                        "uid": uid, "recurrence_id_utc": fmt_utc(instant),
                        "reason": "missing-master"})
                continue
            self.series_counts[(cid, uid)] = 0
            self.expand_series(cid, uid, master, overrides, bound_wall)
        self.occurrences.sort(key=lambda o: (o["start"], o["id"]))

    def expand_series(self, cid, uid, master, overrides, bound_wall):
        mz_name = master.dtstart_tzid
        dt_wall, dt_is_utc, _ = parse_basic(master.dtstart)
        master_zone_name = self.res.resolve(master.dtstart, mz_name)[1]
        kept = []
        kept_instants = set()

        until_instant = None
        if master.rrule and "UNTIL" in master.rrule:
            raw = master.rrule["UNTIL"][0]
            wall, is_utc, _ = parse_basic(raw)
            until_instant = wall if is_utc else self.res.instant(raw, mz_name)

        if master.rrule:
            cands = expand_rule(master.rrule, dt_wall, bound_wall)
            cands = [c for c in cands if c >= dt_wall]
            if "COUNT" in master.rrule:
                cands = cands[:int(master.rrule["COUNT"][0])]
        else:
            cands = [dt_wall]

        for wall in cands:
            if dt_is_utc:
                instant, zname, kind, shift = wall, master_zone_name, "unique", 0
            else:
                instant, zname, kind, shift = self.res.resolve(
                    fmt_wall(wall), mz_name)
            if until_instant is not None and instant > until_instant:
                continue
            if not (self.win_start <= instant < self.win_end):
                continue
            kept.append({"instant": instant, "wall": wall, "tzid": zname,
                         "class": kind, "shift": shift, "period": None,
                         "period_tzid": None})
            kept_instants.add(instant)

        for value, tzid in master.rdates:
            if isinstance(value, tuple):
                head = value[1]
                period = value
            else:
                head = value
                period = None
            _wall, is_utc, _ = parse_basic(head)
            if is_utc:
                instant = _wall
                zone = self.zt.zone(tzid or mz_name)
                nominal = zone.to_wall(instant)
                zname, kind, shift = zone.tzid, "unique", 0
            else:
                instant, zname, kind, shift = self.res.resolve(
                    head, tzid, mz_name)
                nominal = _wall
            if not (self.win_start <= instant < self.win_end):
                continue
            if instant in kept_instants:
                continue
            kept.append({"instant": instant, "wall": nominal, "tzid": zname,
                         "class": kind, "shift": shift, "period": period,
                         "period_tzid": tzid or mz_name})
            kept_instants.add(instant)

        order = []
        records = {}
        for rec in kept:
            if rec["instant"] not in records:
                order.append(rec["instant"])
                records[rec["instant"]] = rec

        excluded = set()
        for value, tzid in master.exdates:
            instant = self.res.instant(value, tzid, mz_name)
            if instant in records:
                excluded.add(instant)
                self.exdate_applied.append({
                    "kind": "exdate-applied", "collection": cid, "uid": uid,
                    "exdate_utc": fmt_utc(instant)})
            else:
                self.exdate_unmatched.append({
                    "kind": "exdate-unmatched", "collection": cid, "uid": uid,
                    "exdate_utc": fmt_utc(instant)})
        remaining = [i for i in order if i not in excluded]
        remaining_set = set(remaining)

        groups = {}
        for comp in overrides:
            instant = self.res.instant(comp.rid_raw, comp.rid_tzid, mz_name)
            if instant not in remaining_set:
                self.override_rejected.append({
                    "kind": "override-rejected", "collection": cid, "uid": uid,
                    "recurrence_id_utc": fmt_utc(instant),
                    "reason": "orphan-recurrence-id"})
                continue
            groups.setdefault(instant, []).append(comp)
        applied = {}
        for instant in sorted(groups):
            comps = groups[instant]
            best = max(comps, key=lambda c: (c.sequence, c.rid_raw))
            for comp in comps:
                if comp is not best:
                    self.override_rejected.append({
                        "kind": "override-rejected", "collection": cid,
                        "uid": uid, "recurrence_id_utc": fmt_utc(instant),
                        "reason": "superseded-recurrence-id"})
            applied[instant] = best

        ov_start = {}
        for instant, comp in applied.items():
            start = self.res.instant(comp.dtstart, comp.dtstart_tzid, mz_name)
            ov_start[instant] = start
            self.override_applied.append({
                "kind": "override-applied", "collection": cid, "uid": uid,
                "recurrence_id_utc": fmt_utc(instant),
                "range": comp.rid_range,
                "delta_minutes": floordiv(start - instant, 60)})

        ranged = []
        for instant in sorted(applied):
            comp = applied[instant]
            if comp.rid_range != "THISANDFUTURE":
                continue
            if (comp.status or "").strip().upper() == "CANCELLED":
                continue
            ranged.append((instant, comp, ov_start[instant] - instant))

        for instant in remaining:
            rec = records[instant]
            if instant in applied:
                comp = applied[instant]
                if (comp.status or "").strip().upper() == "CANCELLED":
                    continue
                start = ov_start[instant]
                office = comp.office if comp.office is not None else master.office
                summary = comp.summary if comp.summary is not None else master.summary
                cls = (comp.series_class if comp.series_class is not None
                       else master.series_class)
                refs = comp.refs if comp.refs else master.refs
                if comp.dtend or comp.duration:
                    duration, source = self.component_duration(comp, start, office)
                else:
                    duration, source = self.base_duration(rec, master, start,
                                                          office)
                shift = 0
                is_override = True
            else:
                applicable = [r for r in ranged if r[0] < instant]
                shift = sum(r[2] for r in applicable)
                start = instant + shift
                if applicable:
                    comp = applicable[-1][1]
                    office = (comp.office if comp.office is not None
                              else master.office)
                    summary = (comp.summary if comp.summary is not None
                               else master.summary)
                    cls = (comp.series_class if comp.series_class is not None
                           else master.series_class)
                    refs = comp.refs if comp.refs else master.refs
                    if comp.dtend:
                        own = self.res.instant(comp.dtstart, comp.dtstart_tzid,
                                               mz_name)
                        end = self.res.instant(comp.dtend,
                                               comp.dtend_tzid
                                               or comp.dtstart_tzid or mz_name)
                        duration, source = end - own, "DTEND"
                    elif comp.duration:
                        duration = self.duration_seconds(comp.duration, start,
                                                         office)
                        source = "DURATION"
                    else:
                        duration, source = 3600, "DEFAULT"
                else:
                    office = master.office
                    summary = master.summary
                    cls = master.series_class
                    refs = master.refs
                    duration, source = self.base_duration(rec, master, start,
                                                          office)
                is_override = False
            occ_id = "%s:%s:%s" % (cid, uid, fmt_utc(instant))
            distinct_refs = sorted(set(refs))
            on_date = wall_date(instant)
            resolved = []
            for ref in distinct_refs:
                who, hops, outcome = self.resolve_ref(ref, on_date)
                self.alias_rows.append((occ_id, ref, who or "", hops, outcome))
                if who:
                    resolved.append(who)
            rank = self.gov.rank_of(cls)
            self.occurrences.append({
                "id": occ_id, "collection": cid, "uid": uid,
                "office": office or "", "original": instant, "start": start,
                "end": start + duration, "duration": duration,
                "source": source, "shift": shift, "override": is_override,
                "class": cls or "", "refs": distinct_refs,
                "attendees": sorted(set(resolved)), "summary": summary or "",
                "rank": rank,
                "pinned": (rank >= self.gov.pin_rank) or master.pinned,
            })
            self.series_counts[(cid, uid)] = self.series_counts.get((cid, uid),
                                                                    0) + 1
            if shift != 0:
                self.shift_records.append({
                    "kind": "shift", "occurrence_id": occ_id,
                    "applied_shift_minutes": floordiv(shift, 60)})

        for rec in kept:
            instant = rec["instant"]
            occ_id = "%s:%s:%s" % (cid, uid, fmt_utc(instant))
            zone = self.zt.zones[rec["tzid"]] if rec["tzid"] else None
            offset = zone.offset_at(instant) // 60 if zone else 0
            self.resolution_rows.append((occ_id, rec["tzid"] or "",
                                         fmt_wall(rec["wall"]), rec["class"],
                                         rec["shift"], offset))

    def base_duration(self, rec, master, start, office):
        if rec["period"] is not None:
            return (self.period_duration(rec["period"], start, office,
                                         rec["period_tzid"]), "RDATE")
        return self.component_duration(master, start, office)


    # ---------------- stage 6: conflicts and settling ----------------

    def conflict_pairs(self, schedule):
        buffer_secs = self.gov.buffer_minutes * 60
        by_att = {}
        for occ in schedule:
            for att in occ["attendees"]:
                by_att.setdefault(att, []).append(occ)
        pairs = {}
        for att in by_att:
            occs = sorted(by_att[att], key=lambda o: (o["start"], o["id"]))
            n = len(occs)
            for i in range(n):
                first = occs[i]
                limit = first["end"] + buffer_secs
                for j in range(i + 1, n):
                    second = occs[j]
                    if second["start"] >= limit:
                        break
                    buf = (buffer_secs
                           if first["office"] != second["office"] else 0)
                    eff_end = first["end"] + buf
                    if eff_end <= second["start"]:
                        continue
                    key = (first["id"], second["id"])
                    entry = pairs.get(key)
                    if entry is None:
                        entry = {
                            "first": first["id"], "second": second["id"],
                            "shared_attendees": set(),
                            "offices": [first["office"], second["office"]],
                            "buffer_applied": buf // 60,
                            "overlap_minutes": (eff_end - second["start"]) // 60,
                        }
                        pairs[key] = entry
                    entry["shared_attendees"].add(att)
        out = []
        for key in sorted(pairs):
            entry = pairs[key]
            entry["shared_attendees"] = sorted(entry["shared_attendees"])
            out.append(entry)
        return out

    def settle(self):
        schedule = []
        for occ in self.occurrences:
            item = dict(occ)
            schedule.append(item)
        by_id = {o["id"]: o for o in schedule}
        quantum = self.gov.quantum_minutes
        cap = self.gov.round_cap
        rounds = 0
        self.settle_moves = []
        self.conflicts_before = None
        while True:
            pairs = self.conflict_pairs(schedule)
            if self.conflicts_before is None:
                self.conflicts_before = pairs
            if not pairs:
                stop, converged, residual = "clear", True, []
                break
            if rounds >= cap:
                stop, converged, residual = "cap", False, pairs
                break
            movable = [p for p in pairs
                       if not (by_id[p["first"]]["pinned"]
                               and by_id[p["second"]]["pinned"])]
            if not movable:
                stop, converged, residual = "pinned", False, pairs
                break
            rounds += 1
            chosen = min(movable, key=lambda p: (by_id[p["first"]]["start"],
                                                 p["first"], p["second"]))
            first = by_id[chosen["first"]]
            second = by_id[chosen["second"]]
            if first["pinned"] != second["pinned"]:
                target = second if first["pinned"] else first
            elif first["rank"] != second["rank"]:
                target = first if first["rank"] < second["rank"] else second
            else:
                target = first if first["id"] > second["id"] else second
            old_start = target["start"]
            new_start, deferred, gap = self.defer(target, quantum)
            target["start"] = new_start
            target["end"] = new_start + target["duration"]
            self.settle_moves.append((rounds, target["id"], fmt_utc(old_start),
                                      fmt_utc(new_start), deferred, gap,
                                      chosen["first"], chosen["second"]))
        self.settled = schedule
        self.settle_rounds = rounds
        self.settle_stop = stop
        self.settle_converged = converged
        self.residual = residual

    def defer(self, occ, quantum):
        code = self.office_code(occ["office"])
        zone = self.office_zone(occ["office"])
        old_wall = zone.to_wall(occ["start"])
        target_wall = old_wall + quantum * 60
        instant, _kind, shift = zone.resolve(target_wall)
        new_wall = zone.to_wall(instant)
        local_date = wall_date(new_wall)
        row = self.reg.row_in_force(code, local_date)
        close = row["close"] if (row is not None and row["working"] == "Y") else 0
        end_wall = zone.to_wall(instant + occ["duration"])
        end_minute = floordiv(end_wall - wall_midnight(new_wall), 60)
        if end_minute > close:
            closures = self.closures.get(code, set())
            day = local_date
            for _ in range(4000):
                day = date.fromordinal(day.toordinal() + 1)
                nxt = self.reg.row_in_force(code, day)
                if nxt is not None and nxt["working"] == "Y" \
                        and day not in closures:
                    break
            target_wall = (day_secs(day.year, day.month, day.day)
                           + nxt["open"] * 60)
            instant, _kind, shift = zone.resolve(target_wall)
        return instant, floordiv(target_wall - old_wall, 60), shift

    # ---------------- stage 7: travel, busy, attendance, load ----------------

    def load_legs(self):
        root = ET.parse(self.path("itineraries")).getroot()
        legs = []
        for el in root.iter():
            if xcal_local(el.tag) != "leg":
                continue
            status = el.get("status")
            if status is not None and status != "confirmed":
                continue
            dep = arr = None
            for child in el:
                tag = xcal_local(child.tag)
                if tag == "depart":
                    dep = child
                elif tag == "arrive":
                    arr = child
            dep_office = dep.get("office")
            arr_office = arr.get("office")
            dep_wall = parse_basic(to_basic(dep.get("local")))[0]
            arr_wall = parse_basic(to_basic(arr.get("local")))[0]
            dz = self.office_zone(dep_office)
            az = self.office_zone(arr_office)
            d_inst, d_kind, d_shift = dz.resolve(dep_wall)
            a_inst, a_kind, a_shift = az.resolve(arr_wall)
            local_shift = (wall_date(arr_wall).toordinal()
                           - wall_date(dep_wall).toordinal())
            utc_shift = (wall_date(a_inst).toordinal()
                         - wall_date(d_inst).toordinal())
            legs.append({
                "leg_id": el.get("id"),
                "attendee": el.get("attendee"),
                "depart_office": dep_office,
                "arrive_office": arr_office,
                "depart_utc": fmt_utc(d_inst),
                "arrive_utc": fmt_utc(a_inst),
                "depart_classification": d_kind,
                "arrive_classification": a_kind,
                "depart_shift_minutes": d_shift,
                "arrive_shift_minutes": a_shift,
                "duration_minutes": floordiv(a_inst - d_inst, 60),
                "local_date_shift_days": local_shift,
                "utc_date_shift_days": utc_shift,
                "date_line_crossing": local_shift != utc_shift,
                "blocked_from_utc": fmt_utc(d_inst - 120 * 60),
                "blocked_to_utc": fmt_utc(a_inst + 90 * 60),
                "_depart": d_inst,
                "_arrive": a_inst,
            })
        legs.sort(key=lambda l: (l["_depart"], l["leg_id"]))
        self.legs = legs
        self.legs_by_att = {}
        for leg in legs:
            self.legs_by_att.setdefault(leg["attendee"], []).append(leg)
        for att in self.legs_by_att:
            self.legs_by_att[att].sort(key=lambda l: (l["_arrive"], l["leg_id"]))

    def effective_office(self, attendee, instant):
        best = None
        for leg in self.legs_by_att.get(attendee, []):
            if leg["_arrive"] <= instant:
                best = leg
            else:
                break
        if best is not None:
            return best["arrive_office"]
        return self.home_office.get(attendee, self.default_office)

    def load_busy(self):
        conn = open_sqlite(self.path("freebusy"))
        raw = {}
        for source, attendee, fbtype, start, finish, withdrawn in conn.execute(
                "SELECT source, attendee, fbtype, start, finish, withdrawn "
                "FROM periods"):
            if withdrawn not in (None, "", 0) and int(withdrawn) != 0:
                continue
            kind = (fbtype or "BUSY").strip() or "BUSY"
            if kind.upper() == "FREE":
                continue
            s = parse_basic(to_basic(start))[0]
            if is_duration_value(finish):
                sign, weeks, days, tail = parse_duration(finish)
                e = s + sign * ((weeks * 7 + days) * 86400 + tail)
            else:
                e = parse_basic(to_basic(finish))[0]
            raw.setdefault(attendee, []).append((s, e, kind))
        conn.close()
        self.busy = {}
        for att in raw:
            items = sorted(raw[att])
            merged = []
            for s, e, kind in items:
                if merged and s <= merged[-1][1]:
                    prev = merged[-1]
                    merged[-1] = (prev[0], max(prev[1], e), prev[2] + [kind])
                else:
                    merged.append((s, e, [kind]))
            self.busy[att] = [(s, e, busy_type(kinds)) for s, e, kinds in merged]


    def local_minutes(self, zone, start, end):
        """(local start date, start minute, end minute) for an occurrence."""
        start_wall = zone.to_wall(start)
        end_wall = zone.to_wall(end)
        midnight = wall_midnight(start_wall)
        return (wall_date(start_wall), floordiv(start_wall - midnight, 60),
                floordiv(end_wall - midnight, 60))

    def build_attendance(self):
        rows = []
        for occ in self.settled:
            for att in occ["attendees"]:
                office = self.effective_office(att, occ["start"])
                code = self.office_code(office)
                zone = self.office_zone(office)
                local_date, start_min, end_min = self.local_minutes(
                    zone, occ["start"], occ["end"])
                local_start = fmt_wall(zone.to_wall(occ["start"]))
                closed = local_date in self.closures.get(code, set())
                row = self.reg.row_in_force(code, local_date)
                non_working = (row is None or row["working"] != "Y")
                if closed:
                    rows.append((att, occ["id"], office, "office-holiday",
                                 local_start, 0))
                if non_working:
                    rows.append((att, occ["id"], office, "non-working-day",
                                 local_start, 0))
                if closed or non_working:
                    continue
                open_min, close_min = row["open"], row["close"]
                if start_min < open_min or end_min > close_min:
                    outside = max(open_min - start_min, end_min - close_min)
                    rows.append((att, occ["id"], office,
                                 "outside-working-window", local_start,
                                 outside))
        rows.sort(key=lambda r: (r[0], r[1], r[3]))
        self.attendance_rows = rows

    def build_load(self):
        by_att = {}
        for occ in self.occurrences:
            for att in occ["attendees"]:
                by_att.setdefault(att, []).append(occ)
        steps = []
        summary = {}
        over_cap = []
        for att in sorted(by_att):
            occs = sorted(by_att[att], key=lambda o: (o["start"], o["id"]))
            debt = 0
            peak = 0
            prev_office = None
            prev_end_date = None
            for index, occ in enumerate(occs, 1):
                office = self.effective_office(att, occ["start"])
                code = self.office_code(office)
                zone = self.office_zone(office)
                local_date = wall_date(zone.to_wall(occ["start"]))
                row = self.reg.row_in_force(code, local_date)
                solar_min = self.reg.solar_minute(occ["start"], code)
                deviation = max(row["solar_open"] - solar_min,
                                solar_min - row["solar_close"])
                cost = floordiv(deviation, 15)
                if prev_end_date is None:
                    rest = 0
                else:
                    rest = (local_date.toordinal()
                            - prev_end_date.toordinal()) - 1
                decay = 3 * (rest - 1) if rest > 1 else 0
                debt = max(-30, debt - decay + cost)
                changed = (prev_office is not None and office != prev_office)
                if changed:
                    debt = 0
                peak = max(peak, debt)
                steps.append((att, index, occ["id"], office, deviation, cost,
                              rest, decay, changed, debt))
                end_zone = zone
                prev_end_date = wall_date(end_zone.to_wall(occ["end"]))
                prev_office = office
            peak = max(0, peak)
            summary[att] = {"peak_debt": peak, "final_debt": debt}
            if peak > 8:
                over_cap.append({"attendee": att, "peak_debt": peak,
                                 "excess": peak - 8})
        self.load_steps = steps
        self.load_attendees = summary
        self.load_over_cap = over_cap

    def build_travel(self):
        rows = []
        for leg in self.legs:
            start = leg["_depart"] - 120 * 60
            finish = leg["_arrive"] + 90 * 60
            for occ in self.settled:
                if leg["attendee"] not in occ["attendees"]:
                    continue
                if occ["start"] >= finish or occ["end"] <= start:
                    continue
                airborne = (occ["start"] < leg["_arrive"]
                            and occ["end"] > leg["_depart"])
                rows.append((occ["id"], leg["attendee"], leg["leg_id"],
                             "airborne" if airborne else "ground-buffer"))
        rows.sort(key=lambda r: (r[0], r[2]))
        self.travel_rows = rows

    def build_busy_conflicts(self):
        rows = []
        for occ in self.settled:
            for att in occ["attendees"]:
                for start, finish, kind in self.busy.get(att, []):
                    if occ["start"] >= finish or occ["end"] <= start:
                        continue
                    rows.append((occ["id"], att, fmt_utc(start),
                                 fmt_utc(finish), kind))
        rows.sort(key=lambda r: (r[0], r[2], r[1]))
        self.busy_rows = rows

    # ---------------- stage 8: synchronisation ----------------

    def projection(self, comps):
        items = []
        for comp in sorted(comps, key=lambda c: (c.rid_raw, c.sequence)):
            office = comp.office or ""
            start = self.res.instant(comp.dtstart, comp.dtstart_tzid)
            duration, _source = self.component_duration(comp, start, office)
            items.append({
                "attendees": sorted(set(comp.refs)),
                "duration_seconds": duration,
                "office": office,
                "recurrence_id": comp.rid_raw,
                "sequence": comp.sequence,
                "start_utc": fmt_utc(start),
                "summary": comp.summary or "",
                "uid": comp.uid,
            })
        return items

    def build_sync(self):
        book = parse_yaml(open(self.path("status"), encoding="utf-8").read())
        status = book.get("collections") or {}
        self.sync_rows = []
        self.sync_collections = []
        total_resources = 0
        total_changed = 0
        for col in self.collections:
            cid = col["id"]
            uids = set(uid for uid, _rid in self.local[cid])
            uids |= set(uid for uid, _rid in self.server[cid])
            revs = {}
            for side in ("local", "server"):
                entries = (((status.get(cid) or {}).get(side) or {})
                           .get("entries") or [])
                table = {}
                for item in entries:
                    table[item["href"]] = int(item["revision"])
                revs[side] = table
            merged_by_uid = {}
            for (c2, u, _r), comp in self.merged.items():
                if c2 == cid:
                    merged_by_uid.setdefault(u, []).append(comp)
            local_by_uid = {}
            for (u, _r), comp in self.local[cid].items():
                local_by_uid.setdefault(u, []).append(comp)
            server_by_uid = {}
            for (u, _r), comp in self.server[cid].items():
                server_by_uid.setdefault(u, []).append(comp)
            rows = []
            for uid in uids:
                href = self.col_href[cid] + uid + ".ics"
                merged = merged_by_uid.get(uid, [])
                local = local_by_uid.get(uid, [])
                server = server_by_uid.get(uid, [])
                merged_proj = self.projection(merged)
                text = json_text(merged_proj)
                etag = '"' + hashlib.sha256(text.encode("utf-8")).hexdigest() + '"'
                changed_local = self.projection(local) != merged_proj
                changed_server = self.projection(server) != merged_proj
                base = max(revs["local"].get(href, 0), revs["server"].get(href, 0))
                revision = base + (1 if (changed_local or changed_server) else 0)
                rows.append((href, etag, revision, changed_local, changed_server))
            rows.sort(key=lambda r: r[0])
            digest = hashlib.sha256()
            for href, etag, _rev, _cl, _cs in rows:
                digest.update(("%s\t%s\n" % (href, etag)).encode("utf-8"))
            for href, etag, revision, changed_local, changed_server in rows:
                self.sync_rows.append((cid, href, etag, revision,
                                       changed_local, changed_server))
                if changed_local or changed_server:
                    total_changed += 1
            total_resources += len(rows)
            self.sync_collections.append({
                "collection": cid,
                "href": col["href"],
                "sync_token": cid + "-" + digest.hexdigest(),
                "resources": len(rows),
            })
        self.sync_counts = {
            "collections": len(self.collections),
            "resources": total_resources,
            "changed_resources": total_changed,
        }

    # ---------------- stage 9: chargeback ----------------

    def build_chargeback(self):
        offices = {}
        per_collection = {}
        for occ in self.settled:
            office = occ["office"]
            bps = self.gov.bps_of(office)
            on_date = wall_date(occ["start"])
            for att in occ["attendees"]:
                rate = self.reg.rate_in_force(att, on_date)
                if rate is None:
                    rate = 0
                base = int((Decimal(rate) * Decimal(occ["duration"])
                            / Decimal(3600)).quantize(
                                Decimal(1), rounding=ROUND_HALF_EVEN))
                converted = int((Decimal(base) * Decimal(bps)
                                 / Decimal(10000)).quantize(
                                     Decimal(1), rounding=ROUND_HALF_UP))
                entry = offices.setdefault(office, {"lines": 0, "base_cents": 0,
                                                    "converted_cents": 0,
                                                    "fx_bps": bps})
                entry["lines"] += 1
                entry["base_cents"] += base
                entry["converted_cents"] += converted
                key = (office, occ["collection"])
                per_collection[key] = per_collection.get(key, 0) + base
        self.chargeback_offices = {
            "offices": offices,
            "totals": {
                "lines": sum(e["lines"] for e in offices.values()),
                "base_cents": sum(e["base_cents"] for e in offices.values()),
                "converted_cents": sum(e["converted_cents"]
                                       for e in offices.values()),
            },
        }
        allocations = {}
        for office in sorted(offices):
            entry = offices[office]
            office_base = entry["base_cents"]
            converted = entry["converted_cents"]
            cols = sorted(c for (o, c) in per_collection if o == office)
            shares = []
            if office_base == 0:
                for cid in cols:
                    shares.append((cid, 0, Decimal(0)))
            else:
                for cid in cols:
                    exact = (Decimal(converted) * Decimal(per_collection[(office, cid)])
                             / Decimal(office_base))
                    whole = int(exact.to_integral_value(rounding="ROUND_FLOOR"))
                    shares.append((cid, whole, exact - whole))
            left = converted - sum(w for _c, w, _f in shares)
            ranked = sorted(shares, key=lambda s: (-s[2], s[0]))
            bonus = {}
            for i in range(left):
                cid = ranked[i % len(ranked)][0] if ranked else None
                if cid is None:
                    break
                bonus[cid] = bonus.get(cid, 0) + 1
            for cid, whole, _frac in shares:
                allocations.setdefault(cid, {})[office] = whole + bonus.get(cid, 0)
        totals = {}
        for cid in allocations:
            totals[cid] = sum(allocations[cid].values())
        self.chargeback_collections = {"allocations": allocations,
                                       "totals": totals}

    # ---------------- stage 10: audit, drift ----------------

    def build_audit(self):
        draft = parse_yaml(open(self.path("escalation_draft"),
                                encoding="utf-8").read())
        snapshot = read_delimited(self.path("office_snapshot"), ",")
        payroll = read_delimited(self.path("payroll_export"), ";")
        cache = read_delimited(self.path("zone_cache"), "\t")
        rows = []
        settling = draft.get("settling") or {}
        in_force = {
            "buffer_minutes": self.gov.buffer_minutes,
            "quantum_minutes": self.gov.quantum_minutes,
            "round_cap": self.gov.round_cap,
            "pin_rank": self.gov.pin_rank,
            "default_rank": self.gov.default_rank,
        }
        for key in sorted(in_force):
            lower = settling.get(key)
            lower = "" if lower is None else str(lower)
            value = str(in_force[key])
            rows.append(("settling-parameter", key, value, "escalation_draft",
                         lower, value == lower))
        draft_ranks = draft.get("class_ranks") or {}
        classes = set(self.gov.class_ranks) | set(draft_ranks)
        for cls in sorted(classes):
            value = str(self.gov.rank_of(cls))
            lower = draft_ranks.get(cls)
            lower = "" if lower is None else str(lower)
            rows.append(("class-rank", cls, value, "escalation_draft", lower,
                         value == lower))
        draft_bps = draft.get("conversion_bps") or {}
        codes = set(self.gov.conversion) | set(draft_bps)
        for code in sorted(codes):
            listed = self.gov.listed_bps(code)
            value = "" if listed is None else str(listed)
            lower = draft_bps.get(code)
            lower = "" if lower is None else str(lower)
            rows.append(("conversion-bps", code, value, "escalation_draft",
                         lower, value == lower))
        snap_lon = {}
        snap_win = {}
        for row in snapshot:
            code = row["code"].strip()
            wd = row["weekday"].strip().upper()
            if wd == "MO":
                snap_lon[code] = row["longitude"].strip()
            snap_win[(code, wd)] = "%s-%s" % (row["open_minute"].strip(),
                                              row["close_minute"].strip())
        for code in sorted(self.reg.office_rows):
            value = self.reg.longitude(code)
            lower = snap_lon.get(code, "")
            rows.append(("office-longitude", code, value, "office_snapshot",
                         lower, value == lower))
        keys = []
        for code in self.reg.office_rows:
            for wd in WEEKDAYS:
                keys.append("%s:%s" % (code, wd))
        for key in sorted(keys):
            code, wd = key.split(":")
            target = self.win_start_date
            while WEEKDAYS[target.weekday()] != wd:
                target = date.fromordinal(target.toordinal() + 1)
            row = self.reg.row_in_force(code, target)
            value = "" if row is None else "%d-%d" % (row["open"], row["close"])
            lower = snap_win.get((code, wd), "")
            rows.append(("office-window", key, value, "office_snapshot", lower,
                         value == lower))
        export = {}
        for row in payroll:
            export[row["attendee"].strip()] = row["cents_per_hour"].strip()
        people = set(self.attendees) | set(export)
        for att in sorted(people):
            rate = self.reg.rate_in_force(att, self.win_start_date)
            value = str(rate if rate is not None else 0)
            lower = export.get(att, "")
            rows.append(("attendee-rate", att, value, "payroll_export", lower,
                         value == lower))
        cached = {}
        for row in cache:
            tzid = row["tzid"].strip()
            onset = to_basic(row["onset_utc"].strip())
            instant = parse_basic(onset)[0]
            if not (self.win_start <= instant < self.win_end):
                continue
            cached.setdefault(tzid, []).append(
                "%s/%s/%s" % (onset, row["from_minutes"].strip(),
                              row["to_minutes"].strip()))
        for tzid in sorted(self.zt.zones):
            zone = self.zt.zones[tzid]
            parts = []
            for onset, frm, to in zone.transitions:
                if self.win_start <= onset < self.win_end:
                    parts.append("%s/%d/%d" % (fmt_utc(onset), frm // 60,
                                               to // 60))
            value = ";".join(parts)
            lower = ";".join(sorted(cached.get(tzid, [])))
            rows.append(("zone-transitions", tzid, value, "zone_cache", lower,
                         value == lower))
        self.audit_rows = rows

    def build_drift(self):
        previous = json.load(open(self.path("previous_run"), encoding="utf-8"))
        listed = {}
        for item in previous.get("series_summary", []):
            listed[(item["collection"], item["uid"])] = int(
                item["occurrence_count"])
        present = set()
        for (cid, uid, _rid) in self.merged:
            if (cid, uid) in self.shadow:
                continue
            present.add((cid, uid))
        rows = []
        for key in sorted(set(listed) | present):
            cid, uid = key
            v5 = self.series_counts.get(key, 0)
            if key in listed:
                v3 = listed[key]
                rows.append((cid, uid, v3, v5, v5 - v3))
            else:
                rows.append((cid, uid, "", v5, ""))
        self.drift_rows = rows


    # ---------------- stage 11: the reports ----------------

    def pair_object(self, pair):
        return {
            "first": pair["first"],
            "second": pair["second"],
            "shared_attendees": list(pair["shared_attendees"]),
            "offices": list(pair["offices"]),
            "buffer_applied": pair["buffer_applied"],
            "overlap_minutes": pair["overlap_minutes"],
        }

    def write_reports(self):
        writer = Writer(self.out_dir)

        writer.jsonl("decisions.jsonl", self.decisions)

        writer.json("reconciliation.json", {
            "policy": self.store["conflict_policy"],
            "effective_revision": self.gov.effective_revision,
            "counts": self.counts,
            "duplicate_uids": self.duplicate_uids,
        })

        writer.jsonl("outbox_replay.jsonl", self.outbox_report)

        rows = []
        for occ in self.occurrences:
            code = self.office_code(occ["office"])
            zone = self.office_zone(occ["office"])
            local_start = zone.to_wall(occ["start"])
            local_end = zone.to_wall(occ["end"])
            solar = self.reg.solar_minute(occ["start"], code)
            row = self.reg.row_in_force(code, wall_date(local_start))
            in_window = (row is not None
                         and row["solar_open"] <= solar < row["solar_close"])
            rows.append((
                occ["id"], occ["collection"], occ["uid"], occ["office"],
                fmt_utc(occ["original"]), fmt_utc(occ["start"]),
                fmt_utc(occ["end"]), occ["duration"], occ["source"],
                floordiv(occ["shift"], 60), occ["override"],
                fmt_wall(local_start), fmt_wall(local_end),
                zone.offset_at(occ["start"]) // 60, solar, in_window,
                occ["class"], occ["attendees"], occ["summary"],
            ))
        writer.table("occurrences.csv", [
            "occurrence_id", "collection", "uid", "office", "original_utc",
            "start_utc", "end_utc", "duration_seconds", "duration_source",
            "applied_shift_minutes", "override", "local_start", "local_end",
            "utc_offset_minutes", "solar_minutes", "solar_in_window",
            "series_class", "required_attendees", "summary"], rows, ",")

        alias_rows = sorted(self.alias_rows, key=lambda r: (r[0], r[1]))
        writer.table("alias_resolutions.tsv",
                     ["occurrence_id", "ref", "resolved", "hops", "outcome"],
                     alias_rows, "\t")

        res_rows = sorted(self.resolution_rows, key=lambda r: (r[0], r[2]))
        writer.table("resolutions.tsv",
                     ["occurrence_id", "tzid", "nominal_local",
                      "classification", "shift_minutes", "utc_offset_minutes"],
                     res_rows, "\t")

        records = []
        records.extend(sorted(self.exdate_applied,
                              key=lambda r: (r["collection"], r["uid"],
                                             r["exdate_utc"])))
        records.extend(sorted(self.exdate_unmatched,
                              key=lambda r: (r["collection"], r["uid"],
                                             r["exdate_utc"])))
        records.extend(sorted(self.override_applied,
                              key=lambda r: (r["collection"], r["uid"],
                                             r["recurrence_id_utc"])))
        records.extend(sorted(self.override_rejected,
                              key=lambda r: (r["collection"], r["uid"],
                                             r["recurrence_id_utc"],
                                             r["reason"])))
        records.extend(sorted(self.shift_records,
                              key=lambda r: r["occurrence_id"]))
        writer.jsonl("exceptions.jsonl", records)

        rows = []
        for tzid in sorted(self.zt.zones):
            zone = self.zt.zones[tzid]
            for onset, frm, to in zone.transitions:
                if onset < self.win_end:
                    rows.append((tzid, zone.observance_count, fmt_utc(onset),
                                 frm // 60, to // 60))
        writer.table("zone_transitions.tsv",
                     ["tzid", "observance_count", "onset_utc",
                      "from_offset_minutes", "to_offset_minutes"], rows, "\t")

        writer.jsonl("conflicts.jsonl",
                     [self.pair_object(p) for p in self.conflicts_before])

        writer.table("settle_moves.csv",
                     ["round", "occurrence_id", "from_utc", "to_utc",
                      "deferred_minutes", "gap_shift_minutes", "reason_first",
                      "reason_second"], self.settle_moves, ",")

        rows = []
        for occ in sorted(self.settled, key=lambda o: o["id"]):
            rows.append((occ["id"], occ["office"], fmt_utc(occ["start"]),
                         fmt_utc(occ["end"])))
        writer.table("settled_schedule.csv",
                     ["occurrence_id", "office", "start_utc", "end_utc"],
                     rows, ",")

        writer.json("settle_summary.json", {
            "rounds": self.settle_rounds,
            "converged": self.settle_converged,
            "stop_reason": self.settle_stop,
            "buffer_minutes": self.gov.buffer_minutes,
            "quantum_minutes": self.gov.quantum_minutes,
            "round_cap": self.gov.round_cap,
            "pin_rank": self.gov.pin_rank,
            "default_rank": self.gov.default_rank,
            "effective_revision": self.gov.effective_revision,
            "residual_conflicts": [self.pair_object(p) for p in self.residual],
        })

        writer.table("load_steps.tsv",
                     ["attendee", "step", "occurrence_id", "effective_office",
                      "deviation_minutes", "cost_units", "rest_days",
                      "decay_applied", "office_changed", "debt_after"],
                     self.load_steps, "\t")

        writer.json("load_summary.json", {
            "floor": -30,
            "decay_per_rest_day": 3,
            "unit_minutes": 15,
            "cap": 8,
            "attendees": self.load_attendees,
            "over_cap": self.load_over_cap,
        })

        writer.table("attendance.psv",
                     ["attendee", "occurrence_id", "effective_office", "kind",
                      "local_start", "minutes_outside"],
                     self.attendance_rows, "|")

        legs = []
        for leg in self.legs:
            item = dict((k, v) for k, v in leg.items()
                        if not k.startswith("_"))
            legs.append(item)
        writer.json("legs.json", {
            "legs": legs,
            "counts": {
                "legs": len(legs),
                "date_line_crossings": sum(1 for l in legs
                                           if l["date_line_crossing"]),
                "blocked_occurrences": len(self.travel_rows),
                "freebusy_conflicts": len(self.busy_rows),
            },
        })

        writer.table("travel_blocks.csv",
                     ["occurrence_id", "attendee", "leg_id", "kind"],
                     self.travel_rows, ",")

        writer.table("busy_conflicts.tsv",
                     ["occurrence_id", "attendee", "block_start_utc",
                      "block_end_utc", "fbtype"], self.busy_rows, "\t")

        writer.table("sync_entries.tsv",
                     ["collection", "href", "etag", "revision",
                      "changed_local", "changed_server"], self.sync_rows, "\t")

        writer.json("sync_tokens.json", {
            "collections": self.sync_collections,
            "counts": self.sync_counts,
        })

        writer.json("chargeback_offices.json", self.chargeback_offices)
        writer.json("chargeback_collections.json", self.chargeback_collections)

        writer.table("authority_audit.csv",
                     ["subject", "key", "in_force", "source", "lower_value",
                      "agrees"], self.audit_rows, ",")

        writer.table("drift.csv",
                     ["collection", "uid", "v3_count", "v5_count", "delta"],
                     self.drift_rows, ",")

        order = list(writer.written)
        chain = hashlib.sha256(b"").hexdigest()
        links = []
        for name in order:
            data = open(os.path.join(self.out_dir, name), "rb").read()
            file_digest = hashlib.sha256(data).hexdigest()
            chain = hashlib.sha256(
                (chain + "\n" + name + "\n" + file_digest).encode("utf-8")
            ).hexdigest()
            links.append({"name": name, "file_sha256": file_digest,
                          "chain_sha256": chain})
        writer.json("manifest.json", {
            "algorithm": "sha256-chain",
            "order": order,
            "links": links,
            "chain_root": hashlib.sha256(b"").hexdigest(),
            "chain_head": chain,
        })
        self.chain_head = chain

    def run(self):
        self.load_authorities()
        self.load_replicas()
        self.replay_outbox()
        self.load_journal()
        self.merge()
        self.load_legs()
        self.load_busy()
        self.expand()
        self.settle()
        self.build_load()
        self.build_attendance()
        self.build_travel()
        self.build_busy_conflicts()
        self.build_sync()
        self.build_chargeback()
        self.build_audit()
        self.build_drift()
        self.write_reports()


REPORT_NAMES = (
    "decisions.jsonl", "reconciliation.json", "outbox_replay.jsonl",
    "occurrences.csv", "alias_resolutions.tsv", "resolutions.tsv",
    "exceptions.jsonl", "zone_transitions.tsv", "conflicts.jsonl",
    "settle_moves.csv", "settled_schedule.csv", "settle_summary.json",
    "load_steps.tsv", "load_summary.json", "attendance.psv", "legs.json",
    "travel_blocks.csv", "busy_conflicts.tsv", "sync_entries.tsv",
    "sync_tokens.json", "chargeback_offices.json",
    "chargeback_collections.json", "authority_audit.csv", "drift.csv",
    "manifest.json",
)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: schedule_repair.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    for name in REPORT_NAMES:
        stale = os.path.join(out_dir, name)
        if os.path.isfile(stale):
            os.remove(stale)
    Pass(data_dir, out_dir).run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

